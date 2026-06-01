"""lib/assembly_solver — 7-step constraint-based assembly solver.

Thin orchestrator: delegates to packing, wiring, thermal sub-modules.
Backward-compatible: `from lib.assembly_solver import solve` still works.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from ._types import _Comp, _Decision, THERMAL_TIER_LOW, THERMAL_TIER_MID, THERMAL_TIER_HIGH
from .packing import (
    _sort_by_weight, _classify_thermal, _assign_zones,
    _escalate_overflow, _pack_shelf_ffd,
    _check_collisions, _check_cog, _layout_panel, _orient_ports,
)
from .wiring import _extract_component_pairs, _route_wires
from .bus_routing import optimize_bus_routing
from .thermal import _validate_thermal
from .placement_dag import (
    build_placement_dag, topological_sort_layers, compute_placement_order,
)

# Backward-compat re-exports (used by tests and assembly_solver_v3)
from ._types import _CLEARANCE_MM, _THERMAL_HOT_MW, _VENT_THRESHOLD_MW  # noqa: F401

# Sub-module re-exports (so external callers can do `from lib.assembly_solver import ...`)
from . import assembly_solver_v3  # noqa: F401
from . import enclosure_fit       # noqa: F401
from . import ic_validation        # noqa: F401
from . import thermal_rc           # noqa: F401
from . import embedded_validator   # noqa: F401


def solve(
    components: List[dict],
    wiring_raw: dict,
    enclosure_spec: dict,
    thermal_index: Optional[dict] = None,
    user_spec_fn: Optional[Any] = None,
) -> dict:
    """Main entry (v2). Routes components by enclosure_relation into 5 buckets."""
    from lib.registry import COMPONENT_REGISTRY

    inner_l = enclosure_spec.get("inner_length", 80)
    inner_w = enclosure_spec.get("inner_width", 60)
    inner_h = enclosure_spec.get("inner_height", 40)

    comps_all = _build_comp_list(components, COMPONENT_REGISTRY, user_spec_fn)
    if not comps_all:
        return _empty_result()

    pack_comps = [c for c in comps_all if c.enclosure_relation in ("internal", "breadboard")]
    panel_comps = [c for c in comps_all if c.enclosure_relation == "panel"]
    external_comps = [c for c in comps_all if c.enclosure_relation == "external"]
    embedded_comps = [c for c in comps_all if c.enclosure_relation == "embedded"]

    decisions: List[_Decision] = []
    decisions.append(_Decision(
        step="enclosure_partition",
        principle="殼體關係分流",
        description=(
            f"依 enclosure_relation 分流 {len(comps_all)} 元件："
            f"pack(internal+breadboard)={len(pack_comps)}, "
            f"panel={len(panel_comps)}, external={len(external_comps)}, embedded={len(embedded_comps)}。"
            "Pack 元件參與殼內 packing，panel 元件分配殼面，external/embedded 僅作走線 endpoint。"
        ),
        formula="bucket = ComponentSpec.enclosure_relation",
    ))

    thermo_scope = pack_comps + panel_comps

    if thermo_scope:
        _sort_by_weight(thermo_scope, decisions)
        hot_set = _classify_thermal(thermo_scope, decisions)
        _assign_zones(thermo_scope, hot_set, decisions)

    if pack_comps:
        max_y, util = _pack_shelf_ffd(pack_comps, inner_l, inner_w, decisions)
        if util > 100 or max_y > inner_w:
            n_before = len(pack_comps)
            pack_comps, panel_comps, new_enc = _escalate_overflow(
                pack_comps, panel_comps,
                inner_l, inner_w, inner_h, util, decisions,
            )
            changed = (len(pack_comps) != n_before
                       or new_enc["inner_length"] != inner_l
                       or new_enc["inner_width"] != inner_w)
            inner_l = new_enc["inner_length"]
            inner_w = new_enc["inner_width"]
            inner_h = new_enc["inner_height"]
            if changed:
                _pack_shelf_ffd(pack_comps, inner_l, inner_w, decisions)
        _check_collisions(pack_comps, decisions, inner_l, inner_w, inner_h)
        _check_cog(thermo_scope, inner_l, inner_w, decisions)

    if panel_comps:
        _layout_panel(panel_comps, inner_l, inner_w, inner_h, decisions)

    if pack_comps:
        _orient_ports(pack_comps, inner_l, inner_w, decisions)

    for c in external_comps:
        c.x = max(0.0, inner_l / 2 - c.L / 2)
        c.y = 0.0
        c.face_out = "side-back"
        c.zone = "external-back"
    for c in embedded_comps:
        hs = c.host_structure
        if isinstance(hs, dict) and hs.get("entry_port"):
            ep = hs["entry_port"]
            dims = hs.get("dimensions", {})
            host_l = dims.get("length_mm", inner_l)
            host_w = dims.get("width_mm", inner_w)
            # u/v -> absolute mm on host face
            c.x = round(ep.get("u", 0.5) * host_l, 1)
            c.y = round(ep.get("v", 0.5) * host_w, 1)
            c.face_out = ep.get("face", "top")
            c.zone = f"embedded-{hs.get('kind', 'host')}"
        else:
            # v2 fallback -- legacy string or missing host_structure
            c.x = max(0.0, inner_l / 2 - c.L / 2)
            c.y = max(0.0, inner_w / 2 - c.W / 2)
            c.zone = "embedded-host"
            c.face_out = "bottom"

    pairs = _extract_component_pairs(wiring_raw, comps_all)
    wire_routes = _route_wires(comps_all, pairs, inner_l, inner_w, inner_h, decisions)

    thermal_field = _validate_thermal(thermo_scope, thermal_index, decisions,
                                      inner_l, inner_w, inner_h)

    placements = [
        {"type": c.type, "role": c.role,
         "x": round(c.x, 1), "y": round(c.y, 1),
         "L": c.L, "W": c.W, "H": c.H,
         "zone": c.zone, "face_out": c.face_out,
         "enclosure_relation": c.enclosure_relation}
        for c in pack_comps
    ]
    panel_placements = [_to_panel_placement(c) for c in panel_comps]
    external_refs = [_to_external_ref(c, inner_l, inner_w) for c in external_comps]
    embedded_refs = [_to_embedded_ref(c) for c in embedded_comps]

    overflow_escalations = [
        d.description for d in decisions if d.step == "overflow_escalate"
    ]
    return {
        "placements": placements,
        "panel_placements": panel_placements,
        "external_refs": external_refs,
        "embedded_refs": embedded_refs,
        "thermal_field": thermal_field,
        "wire_routes": wire_routes,
        "overflow_escalations": overflow_escalations,
        "decisions": [
            {"step": d.step, "principle": d.principle,
             "description": d.description, "formula": d.formula,
             "6e_stage": d.six_e_stage}
            for d in decisions
        ],
    }


def _to_panel_placement(c: _Comp) -> dict:
    return {
        "type": c.type, "role": c.role,
        "face": c.face_out, "u": round(c.x, 1), "v": round(c.y, 1),
        "L": c.L, "W": c.W, "H": c.H,
        "thermal_mw": c.thermal_mw,
        "enclosure_relation": "panel",
    }


def _to_external_ref(c: _Comp, inner_l: float, inner_w: float) -> dict:
    return {
        "type": c.type, "role": c.role,
        "wire_exit_face": "side-back",
        "wire_exit_u": round(inner_l / 2, 1),
        "wire_exit_v": 0.0,
        "wire_exit_diameter": 6.0,
        "enclosure_relation": "external",
    }


def _to_embedded_ref(c: _Comp) -> dict:
    hs = c.host_structure
    ref = {
        "type": c.type, "role": c.role,
        "host_structure": hs if hs else "external_body",
        "thermal_mw": c.thermal_mw,
        "enclosure_relation": "embedded",
        "x": c.x, "y": c.y,
        "face_out": c.face_out,
        "zone": c.zone,
    }
    # v3: expose wire_entry for downstream CAD
    if isinstance(hs, dict) and hs.get("wire_entry"):
        ref["wire_entry"] = hs["wire_entry"]
    return ref


def _build_comp_list(components: List[dict], registry, user_spec_fn=None) -> List[_Comp]:
    out = []
    for c in components:
        cls = c.get("type") or c.get("class_name", "")
        spec = registry.get(cls)
        if not spec and user_spec_fn:
            spec = user_spec_fn(cls)
        if not spec:
            continue
        rel = getattr(spec, "enclosure_relation", "internal")
        ports = []
        raw_ports = getattr(spec, "connector_ports", None) or getattr(spec, "ports", None) or []
        for p in raw_ports:
            _g = p.get if isinstance(p, dict) else lambda k, d=None: getattr(p, k, d)
            ports.append({
                "name": _g("name", ""),
                "side": _g("side", "face"),
                "port_type": _g("port_type", "OTHER"),
            })
        out.append(_Comp(
            type=cls, role=c.get("role", ""),
            L=spec.length_mm, W=spec.width_mm, H=spec.height_mm,
            weight_g=spec.weight_g, thermal_mw=spec.thermal_mw,
            ports=ports,
            enclosure_relation=rel,
            z=0.0,
            host_structure=copy.copy(getattr(spec, "host_structure", None)),
        ))
    return out


def _empty_result() -> dict:
    return {
        "placements": [], "panel_placements": [], "external_refs": [], "embedded_refs": [],
        "thermal_field": _empty_thermal(), "wire_routes": [], "decisions": [],
        "overflow_escalations": [],
    }


def _empty_thermal() -> dict:
    return {
        "heat_sources": [], "total_power_mw": 0,
        "thermal_tier": "LOW", "needs_venting": False,
        "passive_venting": False, "vent_placements": [],
    }
