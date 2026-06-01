"""ADR-8: I2C/Power bus trunk routing (post-processing optimization).

Consolidates individual point-to-point I2C and Power wires into
trunk + drop bus architecture, reducing wire count 30-50%.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _distance_2d(p1: List[float], p2: List[float]) -> float:
    """Euclidean distance using first two coords."""
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return (dx * dx + dy * dy) ** 0.5


def _find_mcu_pin_pos(routes: list, pin_prefix: str) -> Optional[List[float]]:
    """Find the MCU-side start position for a given pin prefix (e.g. 'SDA')."""
    for r in routes:
        mcu_pin = r.get("mcu_pin", "").upper()
        if pin_prefix in mcu_pin and r.get("waypoints"):
            return r["waypoints"][0]
    return None


def _build_bus_trunk(
    mcu_pos: List[float],
    targets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build trunk from MCU to farthest target; compute drop percentages."""
    if not targets:
        return {"waypoints": [], "drops": []}

    # Sort targets by distance from MCU (nearest first)
    sorted_targets = sorted(
        targets, key=lambda t: _distance_2d(mcu_pos, t["pos"])
    )

    farthest = sorted_targets[-1]
    trunk_waypoints = [mcu_pos[:2]]

    # Trunk direction vector
    trunk_dx = farthest["pos"][0] - mcu_pos[0]
    trunk_dy = farthest["pos"][1] - mcu_pos[1]
    trunk_len = (trunk_dx ** 2 + trunk_dy ** 2) ** 0.5
    if trunk_len < 0.01:
        trunk_len = 1.0

    # Project each target onto trunk to get drop percentage
    drops = []
    for t in sorted_targets:
        tx = t["pos"][0] - mcu_pos[0]
        ty = t["pos"][1] - mcu_pos[1]
        proj = (tx * trunk_dx + ty * trunk_dy) / (trunk_len * trunk_len)
        pct = max(0.0, min(1.0, proj))

        wp_x = mcu_pos[0] + pct * trunk_dx
        wp_y = mcu_pos[1] + pct * trunk_dy
        trunk_waypoints.append([round(wp_x, 1), round(wp_y, 1)])

        drops.append({
            "from_trunk_pct": round(pct, 3),
            "to": t["comp_type"],
            "drop_endpoint": [round(t["pos"][0], 1), round(t["pos"][1], 1)],
        })

    # Deduplicate and sort trunk waypoints by distance from start
    trunk_waypoints.append(farthest["pos"][:2])
    seen: set = set()
    unique_wps: List[List[float]] = []
    for wp in trunk_waypoints:
        key = (round(wp[0], 1), round(wp[1], 1))
        if key not in seen:
            seen.add(key)
            unique_wps.append([key[0], key[1]])
    unique_wps.sort(key=lambda w: _distance_2d(mcu_pos, w))

    return {"waypoints": unique_wps, "drops": drops}


def optimize_bus_routing(wiring_result: dict, comps: list) -> dict:
    """Post-process wiring to consolidate I2C and Power into bus trunks.

    Args:
        wiring_result: dict with "wire_routes" key from solve()
        comps: list of component dicts (with "type" key)

    Returns:
        dict with "bus_routes" added and individual bus wires removed.
    """
    routes = wiring_result.get("wire_routes", [])
    if not routes:
        return {**wiring_result, "bus_routes": []}

    i2c_routes = [r for r in routes if r.get("signal_type", r.get("signal")) == "i2c"]
    power_routes = [r for r in routes if r.get("signal_type", r.get("signal")) == "power"]

    bus_routes: List[Dict[str, Any]] = []
    removed_ids: set = set()

    # --- I2C Bus (requires >= 2 devices) ---
    if len(i2c_routes) >= 2:
        mcu_sda_pos = _find_mcu_pin_pos(routes, "SDA")
        if mcu_sda_pos:
            i2c_targets = []
            for r in routes:
                if r.get("signal_type") != "i2c":
                    continue
                wps = r.get("waypoints", [])
                if len(wps) >= 2:
                    i2c_targets.append({"comp_type": r["to"], "pos": wps[-1]})
                    removed_ids.add(id(r))

            trunk = _build_bus_trunk(mcu_sda_pos, i2c_targets)
            bus_routes.append({
                "bus_type": "i2c",
                "trunk": {
                    "from": "MCU_SDA",
                    "to": (i2c_targets[-1]["comp_type"] + "_SDA"
                           if i2c_targets else ""),
                    "waypoints": trunk["waypoints"],
                },
                "drops": trunk["drops"],
                "wire_count_saved": max(0, len(i2c_targets) - 1),
            })

    # --- Power Bus (requires >= 2 devices) ---
    if len(power_routes) >= 2:
        mcu_5v_pos = (_find_mcu_pin_pos(routes, "5V")
                      or _find_mcu_pin_pos(routes, "VCC")
                      or _find_mcu_pin_pos(routes, "3.3V"))
        if mcu_5v_pos:
            power_targets = []
            for r in routes:
                if r.get("signal_type") != "power":
                    continue
                wps = r.get("waypoints", [])
                if len(wps) >= 2:
                    power_targets.append({"comp_type": r["to"], "pos": wps[-1]})
                    removed_ids.add(id(r))

            trunk = _build_bus_trunk(mcu_5v_pos, power_targets)
            bus_routes.append({
                "bus_type": "power",
                "trunk": {
                    "from": "MCU_5V",
                    "to": (power_targets[-1]["comp_type"] + "_VCC"
                           if power_targets else ""),
                    "waypoints": trunk["waypoints"],
                },
                "drops": trunk["drops"],
                "wire_count_saved": max(0, len(power_targets) - 1),
            })

    # Remove merged individual routes
    remaining_routes = [r for r in routes if id(r) not in removed_ids]
    total_saved = sum(b.get("wire_count_saved", 0) for b in bus_routes)
    original_count = len(routes)

    return {
        **wiring_result,
        "wire_routes": remaining_routes,
        "bus_routes": bus_routes,
        "bus_optimization": {
            "original_wire_count": original_count,
            "optimized_wire_count": len(remaining_routes) + len(bus_routes),
            "wires_saved": total_saved,
            "reduction_pct": round(
                total_saved / max(original_count, 1) * 100, 1
            ),
        },
    }
