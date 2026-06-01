"""Step 7: Thermal validation — tier classification, vent sizing, heat field."""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from ._types import (
    _Comp, _Decision,
    THERMAL_TIER_LOW, THERMAL_TIER_MID, THERMAL_TIER_HIGH,
    _H_CONV_W_M2K, _DT_MAX_C,
    _AMBIENT_C, _INFLUENCE_RADIUS_CAP_MM, _ACTIVE_FAN_CFM,
    _COLOR_LUT_DEFAULT,
)


def _validate_thermal(
    comps: List[_Comp],
    thermal_index: Optional[dict],
    decisions: List[_Decision],
    inner_l: float = 80, inner_w: float = 60, inner_h: float = 40,
) -> dict:
    heat_sources = []
    total_mw = 0.0

    for c in comps:
        mw = c.thermal_mw
        if mw is None and thermal_index:
            ti = thermal_index.get(c.type, {})
            mw = ti.get("total_typical_mw", 0)
        if mw is not None and mw > 0:
            is_estimated = c.thermal_mw is None and thermal_index is not None
            heat_sources.append({
                "type": c.type,
                "power_mw": round(mw, 1),
                "estimated": is_estimated,
                "spatial_kind": "point",
                "estimation_source": "V×I×η" if is_estimated else "datasheet",
                "user_confirmed": False,
            })
        if mw is not None:
            total_mw += mw

    total_w = total_mw / 1000.0
    if total_mw < THERMAL_TIER_LOW:
        thermal_tier = "LOW"
        needs_venting = False
        passive_venting = False
    elif total_mw <= THERMAL_TIER_MID:
        thermal_tier = "MID"
        needs_venting = False
        passive_venting = True
    else:
        thermal_tier = "HIGH"
        needs_venting = True
        passive_venting = False

    vent_placements = []
    if needs_venting or passive_venting:
        a_m2 = total_w / (_H_CONV_W_M2K * _DT_MAX_C)
        vent_area = max(40.0, a_m2 * 1e6)
        vent_type = "vent_slot" if needs_venting else "vent_opening"
        vent_placements.append({
            "face": "side_lower",
            "area_mm2": round(vent_area, 0),
            "type": vent_type,
        })
        if total_mw > 4000:
            vent_placements.append({
                "face": "side_upper",
                "area_mm2": round(vent_area * 0.6, 0),
                "type": vent_type,
            })

    a_shell_m2 = 2 * (inner_l * inner_w + inner_l * inner_h + inner_w * inner_h) / 1e6
    delta_t = total_w / (_H_CONV_W_M2K * a_shell_m2) if total_w > 0 else 0.0

    _tier_desc = {
        "LOW":  f"< {THERMAL_TIER_LOW}mW，密閉殼自然散熱即可。",
        "MID":  f"{THERMAL_TIER_LOW}–{THERMAL_TIER_MID}mW，建議增加被動通風開口。",
        "HIGH": f"> {THERMAL_TIER_MID}mW，必須設計主動通風槽（柵格）。",
    }
    if needs_venting or passive_venting:
        formula_str = (
            f"A_vent = P / (h·ΔT_max) = {total_w:.2f}W / "
            f"({_H_CONV_W_M2K}×{_DT_MAX_C}) = "
            f"{total_w / (_H_CONV_W_M2K * _DT_MAX_C) * 1e6:.0f} mm²"
        )
    else:
        formula_str = (
            f"dT = P / (h·A_shell) = {total_w:.2f} / "
            f"({_H_CONV_W_M2K}×{a_shell_m2:.4f}) = {delta_t:.1f}°C"
        )
    decisions.append(_Decision(
        step="thermal_validate",
        principle="散熱設計",
        description=(
            f"總熱功率 {total_mw:.0f}mW，Tier={thermal_tier}。"
            f"密閉殼估算溫升 dT~{delta_t:.1f}°C。"
            + _tier_desc[thermal_tier]
            + (f" 通風位置 {len(vent_placements)} 處（總面積 "
               f"{sum(v['area_mm2'] for v in vent_placements):.0f}mm²，"
               f"基於自然對流 h={_H_CONV_W_M2K} W/m²K、"
               f"容許溫升 {_DT_MAX_C}°C）。"
               if vent_placements else "")
        ),
        formula=formula_str,
        six_e_stage="explain",
    ))

    # --- ADR-6: Populate V3 thermal overlay ---
    thermal_overlay_sources = []
    for c in comps:
        mw = c.thermal_mw
        if mw is None and thermal_index:
            ti = thermal_index.get(c.type, {})
            mw = ti.get("total_typical_mw", 0)
        if mw is not None and mw > 0:
            a_surface_m2 = (c.L * c.W * 2 + c.L * c.H * 2 + c.W * c.H * 2) / 1e6
            power_w = mw / 1000.0
            surface_temp = (
                _AMBIENT_C + power_w / (_H_CONV_W_M2K * a_surface_m2)
                if a_surface_m2 > 0 else _AMBIENT_C
            )
            influence_r = min(
                math.sqrt(mw / 50.0) * 10.0,
                _INFLUENCE_RADIUS_CAP_MM,
            )
            thermal_overlay_sources.append({
                "type": c.type,
                "position": [c.x, c.y, 0.0],
                "surface_temp_c": round(surface_temp, 1),
                "influence_radius_mm": round(influence_r, 1),
                "thermal_mw": round(mw, 1),
            })

    total_surface_m2 = a_shell_m2
    estimated_dt = (
        (total_mw / 1000.0) / (_H_CONV_W_M2K * total_surface_m2)
        if total_surface_m2 > 0 and total_mw > 0 else 0.0
    )

    thermal_overlay = {
        "heat_sources": thermal_overlay_sources,
        "ambient_c": _AMBIENT_C,
        "estimated_dt_c": round(estimated_dt, 1),
        "color_lut": list(_COLOR_LUT_DEFAULT),
    }

    # --- ADR-4: Airflow overlay ---
    airflow_overlay: Optional[dict] = None
    if thermal_tier == "MID":
        vent_positions = [
            [v.get("face", "side_lower")]
            for v in vent_placements
        ]
        # Also search decisions for vent-type placements
        for d in decisions:
            if hasattr(d, 'step') and "vent" in d.step:
                pass  # already captured above
        airflow_overlay = {
            "mode": "passive",
            "vent_count": len(vent_placements),
            "vent_positions": vent_positions,
        }
    elif thermal_tier == "HIGH":
        fan_x = inner_l / 2.0
        fan_y = inner_w / 2.0
        fan_z = inner_h - 5.0
        airflow_overlay = {
            "mode": "active",
            "fan_position": [fan_x, fan_y, fan_z],
            "cfm": _ACTIVE_FAN_CFM,
        }

    result = {
        "heat_sources": heat_sources,
        "total_power_mw": round(total_mw, 1),
        "thermal_tier": thermal_tier,
        "needs_venting": needs_venting,
        "passive_venting": passive_venting,
        "vent_placements": vent_placements,
        "thermal_overlay": thermal_overlay,
    }
    if airflow_overlay is not None:
        result["airflow_overlay"] = airflow_overlay
    return result
