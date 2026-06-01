"""phase_handlers/phase4_handler.py — Phase IV 機構工程（2026-05-08 重建 + Sprint 1/2 整合）。

Sprint 1（2026-05-08）：E10 + E11 + J1 + J2
  - 整合 assembly_solver placements 進殼體幾何（E10）
  - lid 底面切走線凹槽（E11）
  - 殼體邊角圓角 + 故事化命名（J1 + J2）
  - 多元件路徑：build_assembly_two_piece
  - 單 Brain 路徑：build_pcb_two_piece（向後相容）

新架構（取代被刪的 928 行舊版）：
  輸入：bridge.components（Phase 2/3 完成的元件清單）
  做法：
    1. mount dispatch（servo / motor / pump / speaker bracket）
    2. assembly_solver（placements / wire_routes / thermal_field）
    3. 主殼路徑：
       - 多元件 ≥2 → build_assembly_two_piece（含線槽 / 通風 / 圓角）
       - 單 Brain → build_pcb_two_piece（PCB cache 仍可用）
       - 否則 → 不產主殼
  輸出：bridge.cad_output{bottom_stl, lid_stl, spec, component_shells[]}

Layer 2 LoRA-B（E1，v3 CH3 階層式）：
  - 有 adapter → infer_plan_params() 兩階段推論（Plan + Params, 單 LoRA + control token）
                → result["compiled"] 合併 zone/face_out/joints 進 solver
                → bridge.cad_output.ch3_plan / ch3_params / ch3_source 紀錄推論軌跡
  - 無 adapter 或失敗 → 純 solver fallback（規則式 FFD）

繞過項目：
  - L 系列 Layer 4 進階（modular / cylinder / IP rating，scope 外）
"""
from __future__ import annotations
import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .base import PhaseHandler
from ._phase4_helpers import (
    resolve_brain_class as _resolve_brain_class,
    merge_lora_b_into_solver as _merge_lora_b_into_solver,
    ensure_dir as _ensure_dir,
    safe_project_name as _safe_project_name,
    has_multi_component_layout as _has_multi_component_layout,
    run_contract_validation as _run_contract_validation,
    _SAFE_PROJECT_NAME_FALLBACK,
)
from ..shared.models import Job, PhaseID
from ..shared.bridge_store import project_output_dir

_log = logging.getLogger("cadhllm.phase4")


class Phase4Handler(PhaseHandler):
    """Phase IV — CAD 殼體生成。"""

    phase_id = PhaseID.P4

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, dict]:
        # 延遲 import 避免無 build123d 環境時 import 階段就掛
        from lib.pcb import PCB_REGISTRY
        from lib.cad import (
            build_pcb_two_piece,
            build_assembly_two_piece,
            export_step,
            export_stl_high_density,
        )
        from lib.cad.mounts import ALL_MOUNTS, DEFAULT_MOUNT_SPECS
        from lib.registry import COMPONENT_REGISTRY
        from lib import shell_cache

        components = bridge.get("components", [])
        if not components:
            self._log(progress_cb, "⚠️  bridge.components 為空，跳過 Phase 4")
            return bridge, {"summary": "no components"}

        proj_dir = _ensure_dir(Path(project_output_dir(job)) / "cad")
        bridge["_project_output_dir"] = str(proj_dir.parent)
        project_name = _safe_project_name(bridge)

        component_shells: List[Dict[str, Any]] = []
        bottom_stl: Optional[Path] = None
        lid_stl: Optional[Path] = None
        spec_dict: Dict[str, Any] = {}

        # PV5：從 bridge hints 取材料（預設 PLA）
        hints = bridge.get("cot_plan", {}).get("parameter_hints", {})
        material = (hints.get("material") or "PLA").upper()

        brain_class = _resolve_brain_class(components)
        brain_pcb_spec = PCB_REGISTRY.get(brain_class) if brain_class else None

        # ── (1) Tier 4 機械接合件（mount dispatch）─────────────────
        mount_class_set = set()
        for comp in components:
            class_name = comp.get("type") or comp.get("class_name")
            spec = COMPONENT_REGISTRY.get(class_name)
            if not spec or spec.skip_enclosure:
                continue
            if not getattr(spec, 'mount_kind', ''):
                continue
            if class_name not in ALL_MOUNTS:
                continue
            kind, label, builder = ALL_MOUNTS[class_name]
            mount_spec = DEFAULT_MOUNT_SPECS.get(kind)
            fp = shell_cache.fingerprint_for_spec(mount_spec) if mount_spec else 'na'
            cached = shell_cache.get_cached_shell(class_name, fp) if mount_spec else None
            try:
                stl = proj_dir / f'mount_{kind}.stl'
                step = proj_dir / f'mount_{kind}.step'
                if cached and cached.get('kind') == 'mount':
                    shutil.copy2(cached['mount_stl'], stl)
                    shutil.copy2(cached['mount_step'], step)
                    tris = cached.get('tris', 0)
                    self._log(progress_cb, f"  ⚡ {label} 快取命中（{fp}）")
                else:
                    part, info = builder()
                    tris = export_stl_high_density(part, stl)
                    export_step(part, step)
                    if mount_spec is not None:
                        shell_cache.save_shell_to_cache(
                            class_name, fp, 'mount',
                            files={'mount_stl': str(stl), 'mount_step': str(step)},
                            extra_meta={'tris': tris, 'label': label, 'mount_kind': kind},
                        )
                        self._log(progress_cb, f"  💾 {label} 寫入快取（{fp}）")
                component_shells.append({
                    "class": class_name,
                    "kind": "mount",
                    "mount_kind": kind,
                    "label": label,
                    "stl": str(stl),
                    "step": str(step),
                    "tris": tris,
                })
                mount_class_set.add(class_name)
                self._log(progress_cb, f"  ✅ {label}: {stl.name} ({tris}t)")
            except Exception as exc:
                self._log(progress_cb, f"  ❌ {label} 失敗：{exc}")
                _log.exception("mount 生成失敗")

        # ── (2) Assembly Solver ──────────────────────────────────
        # 用寬鬆預設 enclosure_spec 讓 solver packing；主殼 builder 會依
        # placements 動態收緊 bbox。
        solver_default_spec = {
            "inner_length": 200.0,
            "inner_width": 150.0,
            "inner_height": 60.0,
        }
        # user component fallback
        _user_spec_fn = None
        try:
            from services.shared.user_components_store import get_spec as _uc_get
            _user_spec_fn = _uc_get
        except ImportError:
            pass

        solver_result: Dict[str, Any] = {}
        try:
            from lib.assembly_solver import solve as assembly_solve
            from lib.thermal_index import load_thermal_index

            wiring_raw = bridge.get("wiring", {})
            thermal_idx = load_thermal_index()
            solver_result = assembly_solve(
                components=components,
                wiring_raw=wiring_raw,
                enclosure_spec=solver_default_spec,
                thermal_index=thermal_idx,
                user_spec_fn=_user_spec_fn,
            )
            n_place = len(solver_result.get("placements", []))
            n_wire = len(solver_result.get("wire_routes", []))
            self._log(progress_cb,
                      f"Assembly Solver: {n_place} placements, {n_wire} routes")
        except Exception as exc:
            self._log(progress_cb, f"⚠️  Assembly Solver failed: {exc}")
            _log.exception("assembly solver failed")

        # ── (2a-v3) Assembly Solver V3 (SceneGraph) ─────────────────
        scene_graph_v3: Dict[str, Any] = {}
        try:
            from lib.assembly_solver.assembly_solver_v3 import solve_v3
            wiring_raw_v3 = bridge.get("wiring", {})
            scene_graph_v3 = solve_v3(
                components=components,
                wiring_raw=wiring_raw_v3,
                enclosure_spec=solver_default_spec,
            )
            n_mod = len(scene_graph_v3.get("modules", []))
            n_wire_v3 = len(scene_graph_v3.get("wires", []))
            self._log(progress_cb,
                      f"Assembly V3: {n_mod} modules, {n_wire_v3} wires, "
                      f"{len(scene_graph_v3.get('assembly_sequence', []))} steps")
        except Exception as exc:
            self._log(progress_cb, f"⚠️  Assembly V3 Solver failed: {exc}")
            _log.exception("assembly solver v3 failed")

        # ── (2b) LoRA-B Layer 2 CH3 階層式組裝決策（Plan + Params）─────
        # v3 升級：infer_assembly_plan → infer_plan_params（單 LoRA + control token）
        # 回傳結構：{"plan": ..., "params": ..., "compiled": assembly_plan_dict, "source": "ch3_lora_b"}
        # 既有 _merge_lora_b_into_solver 消化 compiled（與舊 assembly_plan_dict 結構相容）
        #
        # CH4 Ensemble pre-filtering: generate N candidates, score by rules,
        # pick Top-1 before merging into solver — improves output quality.
        lora_b_plan: Dict[str, Any] = {}
        ch3_result: Dict[str, Any] = {}
        try:
            from lib.adapter_manager import _adapter_path
            if _adapter_path("lora_b") is not None:
                from lib.ensemble_filter import (
                    generate_candidates, pre_filter, get_n_candidates,
                )
                n = get_n_candidates()
                if n > 1:
                    self._log(progress_cb,
                              f"[CH4] Ensemble pre-filter: 生成 {n} 候選 LoRA-B 方案")
                    candidates = generate_candidates(
                        bridge, components, n=n, progress_cb=progress_cb)

                    if candidates:
                        ranked = pre_filter(
                            candidates, solver_result, components,
                            registry=COMPONENT_REGISTRY, top_k=1,
                        )
                        ch3_result = ranked[0][0]
                        best_score = ranked[0][1]
                        breakdown = ranked[0][2]
                        self._log(progress_cb,
                                  f"[CH4] Top-1 選定（score={best_score:.1f}/100, "
                                  f"spatial={breakdown['spatial']:.0f}, "
                                  f"cutout={breakdown['cutout_alignment']:.0f}, "
                                  f"print={breakdown['printability']:.0f}）")
                    else:
                        self._log(progress_cb,
                                  "⚠️  CH4 所有候選無效，使用 solver fallback")
                else:
                    from lib.adapter_manager import infer_plan_params
                    self._log(progress_cb,
                              "[CH3] infer_plan_params (single LoRA + control token)")
                    ch3_result = infer_plan_params(bridge, components)

                lora_b_plan = ch3_result.get("compiled") or {}
                if ch3_result.get("error"):
                    self._log(progress_cb,
                              f"⚠️  CH3 階段警告：{ch3_result['error']}")
                if lora_b_plan:
                    lora_b_params = ch3_result.get("params") or {}
                    solver_result = _merge_lora_b_into_solver(
                        solver_result, lora_b_plan, progress_cb, self._log,
                        lora_b_params=lora_b_params)
                    self._log(progress_cb,
                              f"🧠 CH3 決策合併完成"
                              f"（joints={lora_b_plan.get('joints', {}).get('lid_method', 'n/a')}）")
                    try:
                        from lib.rag import add_assembly
                        add_assembly(lora_b_plan, bridge)
                        self._log(progress_cb, "📚 組裝決策已索引至 RAG")
                    except ImportError:
                        pass
                    except Exception as rag_exc:
                        self._log(progress_cb, f"⚠️  RAG 索引失敗（不影響主流程）: {rag_exc}")
                else:
                    self._log(progress_cb, "⚠️  CH3 回傳空 compiled，使用 solver fallback")
            else:
                self._log(progress_cb, "ℹ️  LoRA-B adapter 不存在，使用 solver fallback")
        except Exception as exc:
            self._log(progress_cb, f"⚠️  CH3 infer_plan_params 失敗，使用 solver fallback：{exc}")
            _log.exception("LoRA-B infer_plan_params failed")

        # ── (3) 主殼路徑決策（E10）────────────────────────────────
        all_placements = solver_result.get("placements", [])
        non_mount_placements = [p for p in all_placements
                                if p.get("type") not in mount_class_set]
        thermal_field = solver_result.get("thermal_field", {})
        wire_routes = solver_result.get("wire_routes", [])
        vent_placements = thermal_field.get("vent_placements", [])

        bottom_name = f'{project_name}_bottom'
        lid_name = f'{project_name}_top'

        if _has_multi_component_layout(non_mount_placements):
            # ── 多元件路徑（E10 + E11 + E12 + J1 + J2）─────────────
            try:
                bottom_stl = proj_dir / f'{bottom_name}.stl'
                lid_stl = proj_dir / f'{lid_name}.stl'
                base_step = proj_dir / f'{bottom_name}.step'
                lid_step = proj_dir / f'{lid_name}.step'

                # LoRA-B enclosure_spec override
                _lb_enc = solver_result.get("lora_b_enclosure_spec", {})
                _lb_wall = _lb_enc.get("wall")
                _wall_arg = (_lb_wall
                             if _lb_wall and 1.5 <= _lb_wall <= 3.5
                             else 2.0)

                base_part, lid_part, asm_spec = build_assembly_two_piece(
                    placements=non_mount_placements,
                    project_name=project_name,
                    wire_routes=wire_routes,
                    vent_placements=vent_placements,
                    wall=_wall_arg,
                )
                tris_b = export_stl_high_density(base_part, bottom_stl)
                tris_l = export_stl_high_density(lid_part, lid_stl)
                export_step(base_part, base_step)
                export_step(lid_part, lid_step)

                spec_dict = {
                    "inner_length": asm_spec.inner_l,
                    "inner_width":  asm_spec.inner_w,
                    "inner_height": asm_spec.inner_h,
                    "wall":         asm_spec.wall,
                    "tol":          asm_spec.tol,
                    "outer_l":      asm_spec.outer_l,
                    "outer_w":      asm_spec.outer_w,
                    "base_h":       asm_spec.base_h,
                    "lid_h":        asm_spec.lid_h,
                    "fillet_r":     asm_spec.fillet_r,
                    "n_components": asm_spec.n_components,
                    "n_io_cutouts": asm_spec.n_io_cutouts,
                    "n_wire_grooves": asm_spec.n_wire_grooves,
                    "n_vents":      asm_spec.n_vents,
                    "n_top_windows": asm_spec.n_top_windows,
                    "material":     material,
                    "base_tris":    tris_b,
                    "lid_tris":     tris_l,
                    "kind":         "assembly",
                }
                component_shells.append({
                    "class": "assembly",
                    "kind": "assembly_two_piece",
                    "base_stl": str(bottom_stl),
                    "lid_stl": str(lid_stl),
                    "base_step": str(base_step),
                    "lid_step": str(lid_step),
                    "base_tris": tris_b,
                    "lid_tris": tris_l,
                })
                self._log(
                    progress_cb,
                    f"  ✅ 多元件主殼：{bottom_stl.name} + {lid_stl.name} "
                    f"(IO={asm_spec.n_io_cutouts} 線槽={asm_spec.n_wire_grooves} "
                    f"通風={asm_spec.n_vents})",
                )
            except Exception as exc:
                self._log(progress_cb, f"  ❌ 多元件主殼生成失敗：{exc}")
                _log.exception("assembly_two_piece 生成失敗")
                raise RuntimeError(
                    f"Phase IV 主殼生成失敗，pipeline 中止（PV3 fail-fast）：{exc}"
                ) from exc

        elif brain_pcb_spec is not None:
            # ── 單 Brain 路徑（向後相容，PCB cache 可用）──────────
            self._log(progress_cb, f"主殼：{brain_pcb_spec.name}（{brain_class}）")
            fp = shell_cache.fingerprint_for_spec(brain_pcb_spec)
            cached = shell_cache.get_cached_shell(brain_class, fp)
            try:
                bottom_stl = proj_dir / f'{bottom_name}.stl'
                lid_stl = proj_dir / f'{lid_name}.stl'
                base_step = proj_dir / f'{bottom_name}.step'
                lid_step = proj_dir / f'{lid_name}.step'

                if cached and cached.get('kind') == 'two_piece':
                    shutil.copy2(cached['base_stl'], bottom_stl)
                    shutil.copy2(cached['lid_stl'], lid_stl)
                    shutil.copy2(cached['base_step'], base_step)
                    shutil.copy2(cached['lid_step'], lid_step)
                    spec_dict = dict(cached.get('spec_dict') or {})
                    # 舊快取 spec_dict 缺 'kind' → 用快取頂層 'kind' 補上（向後相容）
                    spec_dict.setdefault('kind', cached.get('kind', 'two_piece'))
                    tris_b = spec_dict.get('base_tris', 0)
                    tris_l = spec_dict.get('lid_tris', 0)
                    self._log(progress_cb, f"  ⚡ 快取命中（{fp}）→ 直接複用")
                else:
                    base_part, lid_part, two_piece_spec = build_pcb_two_piece(
                        brain_pcb_spec, material=material)
                    tris_b = export_stl_high_density(base_part, bottom_stl)
                    tris_l = export_stl_high_density(lid_part, lid_stl)
                    export_step(base_part, base_step)
                    export_step(lid_part, lid_step)

                    spec_dict = {
                        "inner_length": two_piece_spec.inner_l,
                        "inner_width":  two_piece_spec.inner_w,
                        "inner_height": two_piece_spec.inner_h,
                        "wall":         two_piece_spec.wall,
                        "tol":          two_piece_spec.tol,
                        "outer_l":      two_piece_spec.outer_l,
                        "outer_w":      two_piece_spec.outer_w,
                        "base_h":       two_piece_spec.base_h,
                        "lid_h":        two_piece_spec.lid_h,
                        "material":     material,
                        "base_tris":    tris_b,
                        "lid_tris":     tris_l,
                        "kind":         "two_piece",
                    }
                    shell_cache.save_shell_to_cache(
                        brain_class, fp, 'two_piece',
                        files={
                            'base_stl':  str(bottom_stl),
                            'lid_stl':   str(lid_stl),
                            'base_step': str(base_step),
                            'lid_step':  str(lid_step),
                        },
                        extra_meta={'spec_dict': spec_dict},
                    )
                    self._log(progress_cb, f"  💾 寫入快取（{fp}）")

                component_shells.append({
                    "class": brain_class,
                    "kind": "two_piece",
                    "base_stl": str(bottom_stl),
                    "lid_stl": str(lid_stl),
                    "base_step": str(base_step),
                    "lid_step": str(lid_step),
                    "base_tris": tris_b,
                    "lid_tris": tris_l,
                })
                self._log(progress_cb,
                          f"  ✅ {bottom_stl.name} ({tris_b}t) + {lid_stl.name} ({tris_l}t)")
            except Exception as exc:
                self._log(progress_cb, f"  ❌ 主殼生成失敗：{exc}")
                _log.exception("主殼生成失敗")
                raise RuntimeError(
                    f"Phase IV 主殼生成失敗，pipeline 中止（PV3 fail-fast）：{exc}"
                ) from exc

        # ── (4) 寫 bridge ────────────────────────────────────────
        bridge["cad_output"] = {
            "subdir":            str(proj_dir),
            "project_name":      project_name,
            "bottom_stl":        str(bottom_stl) if bottom_stl else None,
            "lid_stl":           str(lid_stl) if lid_stl else None,
            "spec":              spec_dict,
            "component_shells":  component_shells,
        }
        if solver_result.get("placements"):
            bridge["cad_output"]["component_placements"] = solver_result["placements"]
        if solver_result.get("thermal_field"):
            bridge["cad_output"]["thermal_field"] = solver_result["thermal_field"]
        if solver_result.get("wire_routes"):
            bridge["cad_output"]["wire_routes"] = solver_result["wire_routes"]
        if solver_result.get("joints"):
            bridge["cad_output"]["joints"] = solver_result["joints"]
        if solver_result.get("_lora_b_rationale"):
            bridge["cad_output"]["assembly_rationale"] = solver_result["_lora_b_rationale"]
        if solver_result.get("panel_placements"):
            bridge["cad_output"]["panel_placements"] = solver_result["panel_placements"]
        if solver_result.get("external_refs"):
            bridge["cad_output"]["external_refs"] = solver_result["external_refs"]
        if solver_result.get("embedded_refs"):
            bridge["cad_output"]["embedded_refs"] = solver_result["embedded_refs"]
        if scene_graph_v3:
            bridge["cad_output"]["scene_graph_v3"] = scene_graph_v3
        # CH3 推論軌跡（v3 階層式 LoRA-B）
        if ch3_result:
            if ch3_result.get("plan"):
                bridge["cad_output"]["ch3_plan"] = ch3_result["plan"]
            if ch3_result.get("params"):
                bridge["cad_output"]["ch3_params"] = ch3_result["params"]
            if ch3_result.get("source"):
                bridge["cad_output"]["ch3_source"] = ch3_result["source"]
        if lora_b_plan:
            bridge.setdefault("engineering_decisions", []).append({
                "phase": "IV",
                "category": "assembly_lora_b",
                "description": (
                    f"LoRA-B 組裝決策：{lora_b_plan.get('joints', {}).get('lid_method', 'n/a')}"
                    f"（{lora_b_plan.get('joints', {}).get('reason', '')}）"
                ),
                "stem_concept": "AI-assisted mechanical design optimization",
            })

        for d in solver_result.get("decisions", []):
            bridge.setdefault("engineering_decisions", []).append({
                "phase": "IV",
                "category": f"assembly_{d['step']}",
                "description": d["description"],
                "stem_concept": d["principle"],
            })
        # ── (5) Contract Validation（advisory，不 block pipeline）──────
        _run_contract_validation(bridge, progress_cb, self._log, _log)

        self._save_bridge_safe(job, bridge, progress_cb)

        summary = (f"Phase 4：主殼 {'✓' if bottom_stl else '✗'} + "
                   f"{len(component_shells)} 個 component shell")
        self._log(progress_cb, summary)
        return bridge, {
            "out_dir": str(proj_dir),
            "summary": summary,
            "bottom_stl": str(bottom_stl) if bottom_stl else None,
            "lid_stl":    str(lid_stl) if lid_stl else None,
            "shells":     len(component_shells),
        }

    @staticmethod
    def _log(cb: Optional[Callable], msg: str):
        if cb:
            cb(f"[Phase IV] {msg}")
        else:
            print(f"[Phase IV] {msg}")
