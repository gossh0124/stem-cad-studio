"""phase_handlers/_phase4_helpers.py — Phase IV helper functions.

Extracted to keep phase4_handler.py under 500 lines.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

_SAFE_PROJECT_NAME_FALLBACK = "assembly"


def resolve_brain_class(components: list[dict[str, Any]]) -> Optional[str]:
    """從 components 裡找 role='Brain' 的 class_name；找不到回傳 None。"""
    for c in components:
        if c.get("role", "").lower() == "brain":
            return c.get("type") or c.get("class_name")
    return None


def merge_lora_b_into_solver(
    solver_result: Dict[str, Any],
    lora_b_plan: Dict[str, Any],
    progress_cb: Optional[Callable[[str], None]],
    log_fn: Callable[[Optional[Callable], str], None],
    lora_b_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """將 LoRA-B Assembly Plan + Params 合併進 solver 結果。

    Plan 階段：覆寫 zone/face_out（佈局決策）；solver 保留 x/y 座標（packing 精度）。
    joints / thermal strategy / cable_routing 為 LoRA-B 獨有決策。

    Params 階段（P1-P3）：
      P1: enclosure_spec (wall/inner_dims) 寫入 solver_result 供後續 builder 使用
      P2: placements 座標參考 (_lora_b_x/y/z/rot)
      P3: cable_routing strategy 覆寫 wire_routes
    """
    placements = solver_result.get("placements", [])
    layout = lora_b_plan.get("layout", [])

    layout_map = {}
    for item in layout:
        comp_type = item.get("component", "")
        if comp_type:
            layout_map[comp_type] = item

    n_merged = 0
    for p in placements:
        lb = layout_map.get(p.get("type", ""))
        if lb is None:
            continue
        if lb.get("zone"):
            p["zone"] = lb["zone"]
        if lb.get("face_out"):
            p["face_out"] = lb["face_out"]
        p["_lora_b_reason"] = lb.get("reason", "")
        n_merged += 1

    if n_merged:
        log_fn(progress_cb, f"  📐 LoRA-B 佈局合併：{n_merged}/{len(placements)} 元件")

    if lora_b_plan.get("joints"):
        solver_result["joints"] = lora_b_plan["joints"]

    lb_thermal = lora_b_plan.get("thermal", {})
    if lb_thermal.get("strategy"):
        tf = solver_result.setdefault("thermal_field", {})
        tf["lora_b_strategy"] = lb_thermal["strategy"]
        tf["lora_b_vent_placement"] = lb_thermal.get("vent_placement", "")

    if lora_b_plan.get("cable_routing"):
        solver_result["lora_b_cable_routing"] = lora_b_plan["cable_routing"]

    solver_result["_lora_b_rationale"] = lora_b_plan.get("placement_rationale", "")

    # ── P1: Merge Params enclosure_spec ──
    if lora_b_params:
        enc = lora_b_params.get("enclosure_spec")
        if enc:
            solver_result["lora_b_enclosure_spec"] = enc
            log_fn(progress_cb,
                   f"  enclosure_spec 合併: wall={enc.get('wall')}, "
                   f"L={enc.get('inner_length')}x"
                   f"{enc.get('inner_width')}x{enc.get('inner_height')}")

        # ── P2: Merge Params placements coordinates ──
        params_placements = lora_b_params.get("placements", [])
        if params_placements:
            params_map = {p["element_id"]: p for p in params_placements
                          if "element_id" in p}
            # Map element_id back to component type via plan elements
            plan_elements = lora_b_plan.get("elements", [])
            eid_to_type = {e["id"]: e.get("component_type", "")
                           for e in plan_elements if "id" in e}

            n_coord = 0
            for p in placements:
                comp_type = p.get("type", "")
                # Find matching element_id by component type
                matching_eid = None
                for eid, etype in eid_to_type.items():
                    if etype == comp_type and eid in params_map:
                        matching_eid = eid
                        break
                if matching_eid:
                    pp = params_map[matching_eid]
                    p["_lora_b_x"] = pp.get("x")
                    p["_lora_b_y"] = pp.get("y")
                    p["_lora_b_z"] = pp.get("z")
                    p["_lora_b_rot"] = pp.get("rot_deg")
                    n_coord += 1
                    # Remove used mapping to handle duplicates
                    del eid_to_type[matching_eid]
            if n_coord:
                log_fn(progress_cb,
                       f"  座標參考合併: {n_coord}/{len(placements)} 元件")

        # ── P3: Merge cable_routing into wire_routes ──
        cable_routing = lora_b_plan.get("cable_routing", [])
        wire_routes = solver_result.get("wire_routes", [])
        if cable_routing and wire_routes:
            # Build lookup: to_type -> strategy
            cr_map = {cr.get("to_type", ""): cr.get("strategy", "")
                      for cr in cable_routing}
            n_path = 0
            for wr in wire_routes:
                # Match wire_route endpoint to component type in placements
                to_idx = wr.get("to")
                to_type = ""
                if isinstance(to_idx, int) and to_idx < len(placements):
                    to_type = placements[to_idx].get("type", "")
                strategy = cr_map.get(to_type)
                if strategy:
                    wr["_lora_b_path"] = strategy
                    n_path += 1
            if n_path:
                log_fn(progress_cb,
                       f"  走線路徑覆寫: {n_path}/{len(wire_routes)} 條")

    return solver_result


def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_project_name(bridge: dict) -> str:
    """從 bridge 取 project_name，做檔名安全處理。"""
    raw = bridge.get("project_name") or _SAFE_PROJECT_NAME_FALLBACK
    safe = "".join(c if (c.isascii() and c.isalnum()) or c in "-_" else "_"
                   for c in str(raw))
    return safe.strip("_") or _SAFE_PROJECT_NAME_FALLBACK


def has_multi_component_layout(placements: list[dict[str, Any]]) -> bool:
    """判定是否走 build_assembly_two_piece 路徑（≥2 個非 mount placement）。"""
    return bool(placements) and len(placements) >= 2


def run_contract_validation(
    bridge: Dict[str, Any],
    progress_cb: Optional[Callable[[str], None]],
    log_fn: Callable[[Optional[Callable], str], None],
    logger: Any,
) -> None:
    """執行 VS-IC contract validation（advisory，不 block pipeline）。

    驗證 bridge.cad_output.scene_graph_v3.modules 介接契約，結果寫入
    bridge["cad_validation"]。失敗只 warning，不拋例外。
    """
    try:
        from lib.verification.contract import check_cad_output_contract
        rpt = check_cad_output_contract(bridge)
        bridge["cad_validation"] = {
            "verdict": rpt.verdict.name,
            "checks": [
                {"name": c.name, "verdict": c.verdict.name, "message": c.message}
                for c in rpt.checks
            ],
        }
        if rpt.verdict.name != "PASS":
            logger.warning(
                "Phase IV contract validation FAILED: %s",
                [c.message for c in rpt.checks if c.verdict.name != "PASS"],
            )
            log_fn(progress_cb,
                   f"Contract validation {rpt.verdict.name}（advisory，不中止 pipeline）")
        else:
            log_fn(progress_cb, "Contract validation PASS")
    except Exception as val_exc:
        logger.warning("Contract validation error (skipped): %s", val_exc, exc_info=True)
        log_fn(progress_cb, "Contract validation error (skipped)")
