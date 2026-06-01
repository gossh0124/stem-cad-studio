"""services/pipeline/phase_factory.py — Enclosure sizing + component resolution.

Extracted from pipeline_runner.py (STR6 四拆: phase_factory).
"""
from __future__ import annotations
import logging
from typing import Callable, Dict, Optional

from lib.config import AREA_COMPACT_MAX_MM2 as _AREA_COMPACT, AREA_MEDIUM_MAX_MM2 as _AREA_MEDIUM
from lib.component_resolver import (
    extract_mentions as _extract_mentions,
    resolve_all as _resolve_all,
    cross_validate_user_spec as _cross_validate,
)

_log = logging.getLogger("cadhllm.phase_factory")


def auto_size_enclosure(bridge: dict, emit: Optional[Callable[[str], None]] = None) -> dict:
    """Auto-determine enclosure size based on component count and dimensions."""
    components = bridge.get("components", [])
    non_housing = [c for c in components
                   if isinstance(c, dict) and c.get("role", "").lower() != "housing"]
    count = len(non_housing)
    if count == 0:
        return {}

    try:
        from lib.registry import COMPONENT_REGISTRY
        registry = COMPONENT_REGISTRY
    except ImportError:
        _log.warning("lib.registry not available; using empty registry for sizing")
        registry = {}

    total_area = 0.0
    max_dim = 0.0
    padding = 8.0
    dims_found = 0

    for comp in non_housing:
        comp_type = comp.get("type", "")
        spec = registry.get(comp_type)
        if spec:
            l = spec.length_mm + padding
            w = spec.width_mm + padding
            total_area += l * w * comp.get("qty", 1)
            max_dim = max(max_dim, spec.length_mm, spec.width_mm)
            dims_found += 1
        else:
            total_area += (40 + padding) * (25 + padding) * comp.get("qty", 1)

    if max_dim > 100 or total_area > _AREA_MEDIUM:
        target, cap = "large", 220
    elif total_area > _AREA_COMPACT or count >= 6:
        target, cap = "medium", 220
    else:
        target, cap = "compact", 150

    size_zh = {"compact": "迷你", "medium": "一般", "large": "大型"}[target]
    rationale_parts = [f"共 {count} 個元件"]
    if dims_found:
        rationale_parts.append(f"估算佈局面積 {total_area:.0f} mm²")
    if max_dim > 100:
        rationale_parts.append(f"最大元件長邊 {max_dim:.0f}mm 超過 100mm")
    rationale_parts.append(f"→ 選擇「{size_zh}」尺寸（≤ {cap}mm）")
    rationale = "，".join(rationale_parts)

    ec = bridge.setdefault("enclosure_constraints", {})
    ec["target_size"] = target
    ec["max_dimension_mm"] = cap

    hints = bridge.setdefault("cot_plan", {}).setdefault("parameter_hints", {})
    hints["enclosure_size"] = target

    sizing_info = {
        "target_size": target,
        "max_dimension_mm": cap,
        "component_count": count,
        "estimated_area_mm2": round(total_area),
        "max_component_dim_mm": round(max_dim, 1),
        "rationale": rationale,
    }
    bridge["_enclosure_sizing"] = sizing_info

    if emit:
        emit(f"📐 自動外殼尺寸：{rationale}")

    return sizing_info


def resolve_components(
    job,
    bridge: dict,
    fuzzy_lookup_fn: Optional[Callable] = None,
    progress_cb: Optional[Callable] = None,
    emit_fn: Optional[Callable[[Optional[Callable], str], None]] = None,
) -> None:
    """L1-L5 component resolution + mentions diff."""
    from ..shared.models import Job

    _emit = emit_fn or (lambda cb, msg: cb(msg) if cb else print(msg))

    instruction = bridge.get("_instruction", job.instruction)
    raw_mentions = _extract_mentions(instruction)
    if raw_mentions:
        bridge["_raw_mentions"] = raw_mentions
        _emit(progress_cb, f"🔍 偵測到用戶提及元件：{', '.join(raw_mentions)}")

    components = bridge.get("components", [])
    if not components:
        return

    from ..shared.user_components_store import get_spec as _user_get_spec

    resolve_result = _resolve_all(
        components,
        raw_mentions,
        fuzzy_lookup_fn=fuzzy_lookup_fn,
        user_store_get=_user_get_spec,
        llm_tag_fn=None,
    )

    bridge["_component_resolve"] = {
        "n_resolved": len(resolve_result["resolved"]),
        "fuzzy_candidates": [
            {
                "original": c["_resolve"]["original"],
                "candidate": c["_resolve"].get("candidate", ""),
                "distance": c["_resolve"].get("distance", 0),
            }
            for c in resolve_result["fuzzy_candidates"]
        ],
        "unknowns": [
            {
                "original": c["_resolve"]["original"],
                "equivalent_candidates": c["_resolve"].get("equivalent_candidates", []),
            }
            for c in resolve_result["unknowns"]
        ],
        "missing_mentions": resolve_result["missing_mentions"],
    }

    # U6 Phase 2: user component cross-validation
    spec_warnings: list = []
    for comp in resolve_result["resolved"]:
        if comp.get("_resolve", {}).get("layer") != "L3":
            continue
        user_spec = _user_get_spec(comp["type"])
        if user_spec is None:
            continue
        from dataclasses import asdict
        ws = _cross_validate(asdict(user_spec), role=comp.get("role"))
        if ws:
            spec_warnings.append({
                "type": comp["type"],
                "role": comp.get("role", ""),
                "warnings": ws,
            })
    if spec_warnings:
        bridge["_component_resolve"]["spec_warnings"] = spec_warnings

    # S9: qty ambiguity detection
    _QTY_LIMITS = {"Brain": 1, "Power": 1, "Control": 1}
    _QTY_DEFAULT_MAX = 5
    qty_ambiguities: list = []
    for comp in components:
        role = comp.get("role", "")
        qty = comp.get("qty", 1)
        limit = _QTY_LIMITS.get(role, _QTY_DEFAULT_MAX)
        if qty > limit:
            qty_ambiguities.append({
                "type": comp.get("type", ""),
                "role": role,
                "current_qty": qty,
                "suggested_max": limit,
                "reason": (f"{role} 角色通常只需 {limit} 個"
                           if role in _QTY_LIMITS
                           else f"數量 {qty} 偏高，請確認是否正確"),
            })
    if qty_ambiguities:
        bridge["_component_resolve"]["qty_ambiguities"] = qty_ambiguities

    n_ok = len(resolve_result["resolved"])
    n_fuzzy = len(resolve_result["fuzzy_candidates"])
    n_unknown = len(resolve_result["unknowns"])
    n_missing = len(resolve_result["missing_mentions"])
    n_warns = len(spec_warnings)
    n_qty = len(qty_ambiguities)

    # S4: rare pairing detection via RAG
    try:
        from lib.rag import search_cases as _search_cases
        comp_types = [c.get("type", "") for c in components
                      if c.get("role") not in ("Brain", "Power")]
        if len(comp_types) >= 2:
            query = " ".join(t.replace("-class", "") for t in comp_types)
            hits = _search_cases(query, top_k=1)
            if hits:
                dist = hits[0].get("score", 999)
                if dist > 1.2:
                    bridge.setdefault("_warnings", []).append({
                        "level": "info",
                        "source": "S4_rare_pairing",
                        "msg": (f"元件組合 {', '.join(comp_types)} 在歷史案例中較少見"
                                f"（最近案例距離 {dist:.2f}），建議確認可行性"),
                    })
                    _emit(progress_cb,
                        f"ℹ️ 罕見元件配對：{', '.join(comp_types)}（案例距離 {dist:.2f}）")
            elif comp_types:
                bridge.setdefault("_warnings", []).append({
                    "level": "info",
                    "source": "S4_rare_pairing",
                    "msg": f"元件組合 {', '.join(comp_types)} 在案例庫中無先例",
                })
                _emit(progress_cb,
                    f"ℹ️ 罕見元件配對：{', '.join(comp_types)}（無歷史先例）")
    except (ImportError, KeyError) as e:
        _log.debug("RAG search skipped: %s", e)

    _emit(progress_cb,
        f"📋 元件解析：{n_ok} 已確認"
        + (f"、{n_fuzzy} 待確認" if n_fuzzy else "")
        + (f"、{n_unknown} 未知" if n_unknown else "")
        + (f"、{n_missing} 遺漏" if n_missing else "")
        + (f"、{n_warns} 近似值待確認" if n_warns else "")
        + (f"、{n_qty} 數量待確認" if n_qty else ""))
