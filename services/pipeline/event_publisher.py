"""services/pipeline/event_publisher.py — SSE phase data broadcasting.

Extracted from pipeline_runner.py (STR6 四拆: event_publisher).
"""
from __future__ import annotations
import json as _json
import logging
from typing import Any, Callable, Dict, Optional

from ..shared.models import Job, PhaseID
from ..shared.constants import POWER_MA as _POWER_MA, lookup_constant as _lookup_constant

_log = logging.getLogger("cadhllm.event_publisher")


def emit(cb: Optional[Callable], msg: str):
    if cb:
        cb(msg)
    else:
        print(msg)


def overwrite_phase_result(job: Job, phase_val: int, result):
    """Replace the last phase result entry matching phase_val, or append."""
    for i in range(len(job.phase_results) - 1, -1, -1):
        if getattr(job.phase_results[i], 'phase', None) and job.phase_results[i].phase.value == phase_val:
            job.phase_results[i] = result
            return
    job.phase_results.append(result)


_PASSTHROUGH_ROLES = {"Brain", "Power", "Control"}

# NOTE: bridge_store.py has a parallel _CATEGORY_KEYWORDS (regex format).
# Keep categories in sync when editing either location.
_CATEGORY_KEYWORDS: Dict[str, list] = {
    "Gardening":       ["水", "土壤", "濕度", "農業", "澆", "環境", "溫度", "植物", "繼電器", "通斷"],
    "Smart_Home":      ["控制", "燈", "照明", "調", "省電", "氛圍", "LED", "繼電器", "通斷", "門", "窗", "偵測", "人體", "開關"],
    "Robotics":        ["馬達", "輪", "車", "避障", "遙控", "移動", "旋轉", "定位", "驅動", "距離"],
    "Interactive_Art": ["音", "聲", "光", "LED", "旋律", "播放", "顯示", "動畫", "彩", "按", "控制"],
    "Security":        ["偵測", "人體", "警報", "紅外線", "門禁", "安全", "監控", "距離", "繼電器", "通斷"],
    "Education":       ["教育", "計時", "顯示", "文字", "導覽", "學習", "溫度", "距離", "基礎"],
}


def build_role_alternatives(components: list, bridge: dict = None) -> Dict[str, list]:
    """Build per-role alternative candidates from TAXONOMY_CONFIG + COMPONENT_REGISTRY."""
    try:
        from lib.config import TAXONOMY_CONFIG, EDUCATIONAL_RATIONALE_TEMPLATES
        from lib.registry import COMPONENT_REGISTRY
    except ImportError:
        return {}

    taxonomy = TAXONOMY_CONFIG.get("component_taxonomy", {})
    rationale = EDUCATIONAL_RATIONALE_TEMPLATES

    category = (bridge or {}).get("project_category", "")
    keywords = _CATEGORY_KEYWORDS.get(category, [])

    picked = {c.get("type", "") for c in components if isinstance(c, dict)}

    _ROLE_MAP = {
        "Brain": "Brain", "Power": "Power", "Control": "Control",
        "Sensor": "Sensor", "Output": "Actuator", "Actuator": "Actuator",
        "Display": "Display", "Sound": "Sound", "Lighting": "Lighting",
    }

    result: Dict[str, list] = {}
    seen_roles = set()

    for comp in components:
        if not isinstance(comp, dict):
            continue
        role = comp.get("role", "")
        if role in seen_roles:
            continue
        seen_roles.add(role)

        tax_role = _ROLE_MAP.get(role, role)
        alt_types = taxonomy.get(tax_role, [])

        alts = []
        for t in alt_types:
            if t in picked:
                continue
            if keywords and tax_role not in _PASSTHROUGH_ROLES:
                reason_text = rationale.get(t, "")
                if reason_text and not any(kw in reason_text for kw in keywords):
                    continue
            spec = COMPONENT_REGISTRY.get(t)
            alt = {
                "type": t,
                "name": spec.name if spec else t.replace("-class", ""),
                "power_mw": round(spec.current_ma * spec.voltage_v) if spec else 0,
                "current_ma": round(spec.current_ma) if spec else 0,
                "reason": rationale.get(t, ""),
            }
            alts.append(alt)
        if alts:
            result[role] = alts

    return result


def push_phase_data(phase_id: PhaseID, bridge: dict, job: Job, progress_cb: Optional[Callable]) -> None:
    if not progress_cb:
        return
    try:
        if phase_id == PhaseID.P1:
            _p1: Dict[str, Any] = {"__phase_data__": True, "phase": 1}
            for k in ("cot_plan", "components", "project_name", "project_category"):
                if bridge.get(k) is not None:
                    _p1[k] = bridge[k]
            if bridge.get("_enclosure_sizing"):
                _p1["enclosure_sizing"] = bridge["_enclosure_sizing"]
            _p1["role_alternatives"] = build_role_alternatives(
                bridge.get("components", []), bridge)
            if bridge.get("_component_resolve"):
                _p1["component_resolve"] = bridge["_component_resolve"]
            progress_cb(_json.dumps(_p1))

        elif phase_id == PhaseID.P2:
            progress_cb(_json.dumps({
                "__phase_data__": True, "phase": 2,
                "components": bridge.get("components", []),
            }))

        elif phase_id == PhaseID.P3:
            bom = bridge.get("bom", [])
            if bom:
                p3chk = bridge.get("phase3_constraint_check", {})
                _p3: Dict[str, Any] = {
                    "__phase_data__": True, "phase": 3,
                    "bom": bom,
                    "power_budget": bridge.get("power_budget", {}),
                    "components": bridge.get("components", []),
                    "io_ok":      p3chk.get("results", {}).get("io",     {}).get("ok", True),
                    "wiring_ok":  p3chk.get("results", {}).get("wiring", {}).get("ok", True),
                    "overall_ok": p3chk.get("overall_ok", True),
                }
                chk_results = p3chk.get("results", {})
                checks = []
                for cat_key, cat_data in chk_results.items():
                    for detail in cat_data.get("details", []):
                        if isinstance(detail, dict) and "rule" in detail:
                            checks.append({
                                "cat": cat_key.upper(),
                                "rule": detail.get("rule", ""),
                                "detail": detail.get("msg", ""),
                                "status": "PASS" if detail.get("level") == "OK" else "WARN",
                            })
                if checks:
                    _p3["constraint_checks"] = checks
                wiring_obj = bridge.get("wiring")
                if wiring_obj:
                    _p3["wiring"] = wiring_obj
                progress_cb(_json.dumps(_p3))

        elif phase_id == PhaseID.P4:
            from pathlib import Path as _P
            cad_out = bridge.get("cad_output", {})
            stl_files = []
            if cad_out.get("bottom_stl"):
                stl_files.append({"name": _P(cad_out["bottom_stl"]).name, "label": "底座"})
            if cad_out.get("lid_stl"):
                stl_files.append({"name": _P(cad_out["lid_stl"]).name, "label": "頂蓋"})
            _p4: Dict[str, Any] = {
                "__phase_data__": True, "phase": 4,
                "stl_files": stl_files,
                "engine": cad_out.get("engine", "unknown"),
                "job_id": job.job_id,
            }
            if cad_out.get("component_placements"):
                _p4["component_placements"] = cad_out["component_placements"]
            if cad_out.get("thermal_field"):
                _p4["thermal_field"] = cad_out["thermal_field"]
            if cad_out.get("wire_routes"):
                _p4["wire_routes"] = cad_out["wire_routes"]
            if cad_out.get("spec"):
                _p4["spec"] = cad_out["spec"]
            if cad_out.get("panel_placements"):
                _p4["panel_placements"] = cad_out["panel_placements"]
            if cad_out.get("external_refs"):
                _p4["external_refs"] = cad_out["external_refs"]
            if cad_out.get("embedded_refs"):
                _p4["embedded_refs"] = cad_out["embedded_refs"]
            progress_cb(_json.dumps(_p4))

        elif phase_id == PhaseID.P5:
            viewer = bridge.get("viewer", {})
            phase_data: Dict[str, Any] = {
                "__phase_data__": True, "phase": 5,
                "viewer_url": viewer.get("html_path", ""),
                "stl_paths": viewer.get("stl_paths", []),
            }
            progress_cb(_json.dumps(phase_data))

        # VLM REMOVED — P6 no longer exists

    except (TypeError, ValueError):
        # No-Silent-Fallback: a serialization / payload-assembly failure here
        # means the UI silently loses this phase-data event. Surface it loudly
        # instead of dropping it: log with traceback, then re-raise.
        _log.exception(
            "push_phase_data failed to build/emit SSE phase-data for phase %s",
            getattr(phase_id, "value", phase_id),
        )
        raise
