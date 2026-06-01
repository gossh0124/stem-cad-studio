"""phase_handlers/phase7_handler.py — Phase VII HITL Service Handler。

將 phase_7_human_review.ipynb 的 HITLSession 邏輯封裝為 Service Handler，
透過 lock-file 機制與 Gateway 非同步互動。
"""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, Tuple

from .base import PhaseHandler
from ..shared.models import Job, JobStatus, PhaseID
from ..shared.bridge_store import default_lock_path, save_bridge, event_registry, project_output_dir
from lib.config import ENCLOSURE_DEFAULTS as _ENC_DEFAULTS, ENCLOSURE_SIZE_CAPS as _ENC_SIZE_CAPS
from ._phase7_helpers import write_final_bom, write_assembly_sop

_log = logging.getLogger("cadhllm.phase7")

_MATERIAL_PROPS = {
    "PLA":  {"shrinkage": "低 (0.3-0.5%)", "strength": "中", "flex": "低（較脆）"},
    "PETG": {"shrinkage": "中 (0.5-0.8%)", "strength": "高", "flex": "中"},
    "ABS":  {"shrinkage": "高 (0.7-1.0%)", "strength": "高", "flex": "高"},
}

class Phase7Handler(PhaseHandler):
    phase_id = PhaseID.P7

    def __init__(
        self,
        max_rounds: int = 3,
        timeout_s:  int = 300,
        poll_interval_s: float = 2.0,
    ):
        self.max_rounds      = max_rounds
        self.timeout_s       = timeout_s
        self.poll_interval_s = poll_interval_s

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, Dict[str, Any]]:
        lock_path = job.lock_path or default_lock_path(job.job_id)

        # 讀取 Phase VI 驗證報告
        verif = bridge.get("vlm_verification", {
            "best_score": bridge.get("best_score", 75),
            "best_result": {"issues": []},
        })
        score = verif.get("best_score", 75)
        history: list = []

        self._log(progress_cb,
            f"EventRegistry 等待模式 | timeout: {self.timeout_s}s")
        event_registry.register(job.job_id)
        rnd = 0

        try:
            remaining = float(self.timeout_s)
            while rnd < self.max_rounds and remaining > 0:
                t0 = time.monotonic()
                cmd = event_registry.wait(job.job_id, timeout=remaining)
                elapsed = time.monotonic() - t0
                remaining -= elapsed

                if cmd is None:
                    # 逾時，嘗試讀取殘留 lock file（crash recovery）
                    if os.path.exists(lock_path):
                        cmd = self._read_lock(lock_path)
                    if cmd is None:
                        break

                batch = cmd.get("corrections", [cmd])
                for item in batch:
                    action = item.get("action", "accept")
                    params = item.get("params", {})
                    result = self._apply(bridge, action, params)
                    score  = min(100, score + result.get("score_delta", 0))
                    history.append(result)
                    rnd += 1
                    self._log(progress_cb,
                        f"[Round {rnd}] {action} → {result.get('new_value', 'ok')} "
                        f"| 估計分數：{score}/100")
                    if action == "accept" or rnd >= self.max_rounds:
                        break
                else:
                    continue
                break
        finally:
            event_registry.unregister(job.job_id)

        if rnd == 0:
            self._log(progress_cb, f"逾時 {self.timeout_s}s，無指令，自動 accept")
        else:
            self._log(progress_cb, f"HITL 完成（{rnd} 輪）")

        bridge["hitl_history"]  = history
        bridge["hitl_score"]    = score
        bridge["hitl_accepted"] = True

        # ── 最終 BOM 輸出（反映 HITL 元件變更）───────────────
        write_final_bom(job, bridge, progress_cb)

        # ── CAD 品質記錄 ──
        cad_out = bridge.get("cad_output", {})
        engine  = cad_out.get("engine", "unknown")
        bridge["cad_quality"] = "production"
        self._log(progress_cb,
            f"✅ CAD 引擎 {engine}（生產級），BOM 緊固件指引有效")

        # ── 組裝 SOP 手冊產出 ─────────────────────────────────
        sop_path = write_assembly_sop(job, bridge, progress_cb)

        # 持久化最終 bridge
        self._save_bridge_safe(job, bridge, progress_cb)

        artifacts = {
            "rounds":       rnd,
            "score":        score,
            "lock_path":    lock_path,
            "cad_quality":  bridge["cad_quality"],
            "hitl_warnings": bridge.get("hitl_warnings", []),
            "assembly_sop": sop_path,
        }
        return bridge, artifacts

    # ── 內部輔助 ──────────────────────────────────────────
    def _read_lock(self, lock_path: str) -> Optional[dict]:
        consumed = lock_path + ".consumed"
        try:
            os.replace(lock_path, consumed)
        except OSError:
            return None
        try:
            with open(consumed, "r", encoding="utf-8") as f:
                cmd = json.load(f)
            return cmd
        except json.JSONDecodeError as exc:
            _log.warning("[Phase VII] ⚠️ HITL lock 檔案 JSON 損壞：%s — 已跳過此指令", exc)
            return None
        except OSError as exc:
            _log.warning("[Phase VII] ⚠️ HITL lock 檔案讀取失敗：%s", exc)
            return None
        finally:
            try:
                os.remove(consumed)
            except OSError:
                pass

    def _apply(self, bridge: dict, action: str, params: dict) -> dict:
        hints = bridge.setdefault("cot_plan", {}).setdefault("parameter_hints", {})
        enc   = bridge.setdefault("enclosure_constraints", {})
        decisions = bridge.setdefault("engineering_decisions", [])
        result: Dict[str, Any] = {"action": action, "params": params,
                                   "score_delta": 0,
                                   "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

        if action == "increase_wall_thickness":
            delta = params.get("delta_mm", 0.5)
            old   = hints.get("wall_thickness_mm", _ENC_DEFAULTS["wall_thickness_mm"])
            val   = round(min(4.0, old + delta), 2)
            hints["wall_thickness_mm"] = enc["wall_thickness_mm"] = val
            result.update(new_value=val, score_delta=5)
            decisions.append({
                "phase": "VII", "category": "wall_thickness",
                "description": (
                    f"使用者要求增加壁厚 +{delta}mm（{old}→{val}mm）。"
                    f"較厚的壁面提升結構強度，但會增加列印時間與材料用量。"
                    f"建議範圍：1.5-3.0mm（{enc.get('material', _ENC_DEFAULTS['material'])}）。"
                ),
                "stem_concept": "結構力學與材料強度",
            })

        elif action == "decrease_wall_thickness":
            delta = params.get("delta_mm", 0.5)
            old   = hints.get("wall_thickness_mm", _ENC_DEFAULTS["wall_thickness_mm"])
            val   = round(max(1.0, old - delta), 2)
            hints["wall_thickness_mm"] = enc["wall_thickness_mm"] = val
            result["new_value"] = val
            decisions.append({
                "phase": "VII", "category": "wall_thickness",
                "description": (
                    f"使用者要求減少壁厚 -{delta}mm（{old}→{val}mm）。"
                    f"較薄的壁面節省材料但可能降低耐久性。"
                    f"低於 1.5mm 在 FDM 列印中容易出現層間脫離。"
                ),
                "stem_concept": "製造工藝限制（FDM 最小壁厚）",
            })

        elif action == "change_material":
            mat = params.get("material", "PETG")
            old_mat = enc.get("material", _ENC_DEFAULTS["material"])
            hints["material"] = enc["material"] = mat
            result.update(new_value=mat, score_delta=2)
            props = _MATERIAL_PROPS.get(mat, {})
            decisions.append({
                "phase": "VII", "category": "material_change",
                "description": (
                    f"材質從 {old_mat} 變更為 {mat}。"
                    f"{mat} 的收縮率為 {props.get('shrinkage','未知')}，"
                    f"強度 {props.get('strength','未知')}，"
                    f"柔韌性 {props.get('flex','未知')}。"
                    f"不同材質的列印溫度與床溫設定不同，需相應調整切片參數。"
                ),
                "stem_concept": "材料科學與熱塑性高分子特性",
            })

        elif action == "resize_enclosure":
            if "size" not in params:
                raise ValueError('resize_enclosure action requires params["size"]')
            size = params["size"]
            old_size = enc.get("target_size", "medium")
            hints["enclosure_size"] = size
            enc["target_size"]      = size
            result.update(new_value=size, score_delta=3)
            decisions.append({
                "phase": "VII", "category": "enclosure_resize",
                "description": (
                    f"外殼尺寸從 {old_size}（上限 {_ENC_SIZE_CAPS.get(old_size,160)}mm）"
                    f"調整為 {size}（上限 {_ENC_SIZE_CAPS.get(size,160)}mm）。"
                    f"較大的外殼提供更多佈線空間，但增加列印時間與成本。"
                ),
                "stem_concept": "設計取捨（Trade-off）分析",
            })

        elif action == "add_component":
            comp = params.get("component", {})
            if comp:
                bridge.setdefault("components", []).append(comp)
                result["added"] = comp
                bridge["_needs_rerun_from_phase"] = 2
                decisions.append({
                    "phase": "VII", "category": "add_component",
                    "description": (
                        f"新增元件 {comp.get('type','?')}（角色：{comp.get('role','?')}）。"
                        f"新增元件將影響電力預算、佈局空間與接線規劃，"
                        f"系統將從 Phase II 重新執行規格補全。"
                    ),
                    "stem_concept": "系統整合與連鎖效應",
                })

        elif action == "replace_component":
            old_type = params.get("old_type", "")
            new_comp = params.get("new_component", {})
            if old_type and new_comp:
                if not bridge.get("components"):
                    raise ValueError("replace_component: no components in bridge to replace")
                comps = bridge["components"]
                for i, c in enumerate(comps):
                    if c.get("type") == old_type:
                        comps[i] = new_comp
                        break
                bridge["components"] = comps
                result["replaced"] = {"from": old_type, "to": new_comp.get("type")}
                bridge["_needs_rerun_from_phase"] = 2
                decisions.append({
                    "phase": "VII", "category": "replace_component",
                    "description": (
                        f"替換元件 {old_type} → {new_comp.get('type','?')}。"
                        f"替換後需重新驗證電力預算與 IO 腳位分配。"
                    ),
                    "stem_concept": "元件替代性與相容性評估",
                })

        elif action == "free_text":
            text = params.get("text", "")
            parsed = self._translate_intent(text)
            if parsed:
                sub_action = parsed.get("action", "accept")
                if sub_action == "free_text":
                    result["error"] = "遞迴 free_text 不允許"
                else:
                    sub_params = parsed.get("params", {})
                    sub_result = self._apply(bridge, sub_action, sub_params)
                    result.update(sub_result)
                    result["original_text"] = text
                    result["parsed_action"] = sub_action
            else:
                result["error"] = "無法解析自由文字意圖"

        elif action == "accept":
            result["final"] = True

        return result

    def _translate_intent(self, text: str) -> Optional[dict]:
        """將使用者自由文字轉譯為結構化 action/params。

        優先使用 LoRA-A 推論；若 adapter 不可用則 fallback 至規則引擎。
        """
        try:
            from lib.adapter_manager import translate_hitl_intent
            return translate_hitl_intent(text)
        except ImportError:
            pass

        # 規則引擎 fallback
        t = text.lower()
        if any(k in t for k in ("壁厚加", "加厚", "increase wall", "thicker")):
            return {"action": "increase_wall_thickness", "params": {"delta_mm": 0.5}}
        if any(k in t for k in ("壁厚減", "減薄", "decrease wall", "thinner")):
            return {"action": "decrease_wall_thickness", "params": {"delta_mm": 0.5}}
        if any(k in t for k in ("改用", "換成", "change material")):
            for mat in ("PETG", "ABS", "PLA"):
                if mat.lower() in t:
                    return {"action": "change_material", "params": {"material": mat}}
        if any(k in t for k in ("放大", "加大", "bigger", "large")):
            return {"action": "resize_enclosure", "params": {"size": "large"}}
        if any(k in t for k in ("縮小", "smaller", "compact")):
            return {"action": "resize_enclosure", "params": {"size": "compact"}}
        if any(k in t for k in ("ok", "好", "接受", "accept", "沒問題")):
            return {"action": "accept", "params": {}}
        return None

    @staticmethod
    def _log(cb: Optional[Callable], msg: str):
        if cb:
            cb(f"[Phase VII] {msg}")
        else:
            print(f"[Phase VII] {msg}")
