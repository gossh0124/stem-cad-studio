"""Step 6: A* wire routing, pin position resolution, signal classification."""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

from ._types import (
    _Comp, _Decision, _GRID_RES_MM, _CLEARANCE_MM,
    _WIRE_SIGNAL_COLORS, _LAYER_Z_OFFSET, _WIRE_OCCUPY_MARGIN,
)


def _resolve_brain_pin_pos(comp: _Comp, pin_name: str) -> Tuple[float, float]:
    pn = pin_name.strip().upper()
    if pn.startswith("D") and pn[1:].isdigit():
        idx = int(pn[1:])
        x = comp.x + comp.L * 0.3 + (idx / 13.0) * comp.L * 0.6
        return (x, comp.y + comp.W - 1.0)
    if pn.startswith("A") and pn[1:].isdigit():
        idx = int(pn[1:])
        x = comp.x + comp.L * 0.5 + (idx / 5.0) * comp.L * 0.35
        return (x, comp.y + 1.0)
    if pn in ("SDA", "A4"):
        return (comp.x + comp.L * 0.85, comp.y + 1.0)
    if pn in ("SCL", "A5"):
        return (comp.x + comp.L * 0.9, comp.y + 1.0)
    _POWER_POS = {"5V": 0.35, "VCC": 0.35, "3.3V": 0.30, "3V3": 0.30,
                  "GND": 0.25, "VIN": 0.40}
    if pn in _POWER_POS:
        return (comp.x + comp.L * _POWER_POS[pn], comp.y + 1.0)
    if pn in ("MOSI", "D11"):
        return (comp.x + comp.L * 0.6, comp.y + comp.W - 1.0)
    if pn in ("MISO", "D12"):
        return (comp.x + comp.L * 0.65, comp.y + comp.W - 1.0)
    if pn in ("SCK", "D13"):
        return (comp.x + comp.L * 0.7, comp.y + comp.W - 1.0)
    return (comp.x + comp.L / 2, comp.y + comp.W / 2)


def _resolve_peripheral_pin_pos(
    comp: _Comp, pin_index: int, total_pins: int,
) -> Tuple[float, float]:
    t = pin_index / max(total_pins - 1, 1) if total_pins > 1 else 0.5
    if comp.L >= comp.W:
        return (comp.x + comp.L * 0.2 + t * comp.L * 0.6,
                comp.y + comp.W / 2)
    return (comp.x + comp.L / 2,
            comp.y + comp.W * 0.2 + t * comp.W * 0.6)


def _riser_exit_point(
    comp: _Comp, px: float, py: float,
    inner_l: float, inner_w: float,
    clearance: float = 3.0,
) -> Tuple[float, float]:
    distances = {
        "left":   px - comp.x,
        "right":  (comp.x + comp.L) - px,
        "bottom": py - comp.y,
        "top":    (comp.y + comp.W) - py,
    }
    nearest = min(distances, key=distances.get)
    if nearest == "left":
        return (max(0.0, comp.x - clearance), py)
    if nearest == "right":
        return (min(inner_l, comp.x + comp.L + clearance), py)
    if nearest == "bottom":
        return (px, max(0.0, comp.y - clearance))
    return (px, min(inner_w, comp.y + comp.W + clearance))


def _classify_signal(mcu_pin: str, comp_pin: str) -> str:
    pn = mcu_pin.upper()
    if pn.startswith("A") and pn[1:].isdigit():
        return "analog"
    if "SDA" in pn or "SCL" in pn:
        return "i2c"
    if "MOSI" in pn or "MISO" in pn or "SCK" in pn or "SS" in pn:
        return "spi"
    if pn in ("5V", "VCC", "3.3V", "3V3", "VIN"):
        return "power"
    if pn == "GND":
        return "gnd"
    cp = comp_pin.upper()
    if cp in ("VCC", "V+", "BAT+"):
        return "power"
    if cp in ("GND", "V-", "BAT-"):
        return "gnd"
    return "digital"


def _extract_component_pairs(
    wiring_raw: dict,
    comps: List[_Comp],
) -> List[Tuple[str, str, str, str, str, int, int]]:
    comp_types = {c.type for c in comps}
    type_by_short: Dict[str, str] = {}
    for ct in comp_types:
        short = ct.replace("-class", "").replace("-", "").lower()
        type_by_short[short] = ct
        parts = ct.replace("-class", "").split("-")
        for p in parts:
            if p.lower() not in ("class", "module", "sensor"):
                type_by_short[p.lower()] = ct

    brain_type = None
    for c in comps:
        if c.role == "Brain":
            brain_type = c.type
            break

    pairs: List[Tuple[str, str, str, str, str, int, int]] = []
    for comp_key, info in sorted(wiring_raw.items()):  # sorted for determinism across PYTHONHASHSEED
        matched_type = None
        ck_lower = comp_key.replace("-", "").lower()
        for short, ct in sorted(type_by_short.items()):  # sorted for determinism
            if short in ck_lower or ck_lower in short:
                matched_type = ct
                break

        if not matched_type or not brain_type:
            continue
        if matched_type == brain_type:
            continue

        pins = info.get("pins", [])
        if not pins:
            pairs.append((brain_type, matched_type, "digital", "", "", 0, 1))
            continue

        for idx, pin in enumerate(pins):
            mcu_pin = pin.get("mcu", "")
            comp_pin = pin.get("comp", pin.get("label", ""))

            if mcu_pin == "LOAD":
                continue

            if "." in mcu_pin:
                src_short = mcu_pin.split(".")[0].replace("-", "").lower()
                src_type = type_by_short.get(src_short)
                if src_type:
                    sig = _classify_signal(mcu_pin, comp_pin)
                    pairs.append((src_type, matched_type, sig,
                                  mcu_pin, comp_pin, idx, len(pins)))
                    continue

            sig = _classify_signal(mcu_pin, comp_pin)
            pairs.append((brain_type, matched_type, sig,
                          mcu_pin, comp_pin, idx, len(pins)))
    return pairs


def _route_wires(
    comps: List[_Comp],
    pairs: List[Tuple[str, str, str, str, str, int, int]],
    inner_l: float, inner_w: float, inner_h: float,
    decisions: List[_Decision],
) -> list:
    comp_map = {c.type: c for c in comps}
    res = _GRID_RES_MM
    max_comp_h = max((c.H for c in comps), default=10.0)

    layer_occupied: Dict[float, set] = {}
    routes = []
    total_length = 0.0
    n_pin2pin = 0
    layers_used: set = set()

    priority = {"power": 0, "gnd": 1}
    sorted_pairs = sorted(pairs, key=lambda p: priority.get(p[2], 2))

    for pair in sorted_pairs:
        from_type, to_type, sig_type = pair[0], pair[1], pair[2]
        mcu_pin, comp_pin, pin_idx, total_pins = pair[3], pair[4], pair[5], pair[6]

        c1 = comp_map.get(from_type)
        c2 = comp_map.get(to_type)
        if not c1 or not c2:
            continue

        if mcu_pin:
            p1 = _resolve_brain_pin_pos(c1, mcu_pin)
            n_pin2pin += 1
        else:
            p1 = (c1.x + c1.L / 2, c1.y + c1.W / 2)
        p2 = _resolve_peripheral_pin_pos(c2, pin_idx, total_pins)

        z_offset = _LAYER_Z_OFFSET.get(sig_type, 6.0)
        z_layer = round(max_comp_h + z_offset, 1)
        layers_used.add(z_layer)

        extra = layer_occupied.get(z_layer)
        waypoints_2d = _astar_2d(
            p1, p2, comps, inner_l, inner_w, c1, c2, extra)

        z_pin1 = round(c1.H, 1)
        z_pin2 = round(c2.H, 1)
        wp3d = []
        wp3d.append([round(p1[0], 1), round(p1[1], 1), z_pin1])
        if abs(z_pin1 - z_layer) > 0.5:
            ex1 = _riser_exit_point(c1, p1[0], p1[1], inner_l, inner_w)
            wp3d.append([round(ex1[0], 1), round(ex1[1], 1), z_pin1])
            wp3d.append([round(ex1[0], 1), round(ex1[1], 1), z_layer])
        for wx, wy in waypoints_2d[1:-1]:
            wp3d.append([round(wx, 1), round(wy, 1), z_layer])
        if abs(z_pin2 - z_layer) > 0.5:
            ex2 = _riser_exit_point(c2, p2[0], p2[1], inner_l, inner_w)
            wp3d.append([round(ex2[0], 1), round(ex2[1], 1), z_layer])
            wp3d.append([round(ex2[0], 1), round(ex2[1], 1), z_pin2])
        wp3d.append([round(p2[0], 1), round(p2[1], 1), z_pin2])

        occ = layer_occupied.setdefault(z_layer, set())
        m = _WIRE_OCCUPY_MARGIN
        for wx, wy in waypoints_2d:
            gx = int(wx / res)
            gy = int(wy / res)
            for dx in range(-m, m + 1):
                for dy in range(-m, m + 1):
                    occ.add((gx + dx, gy + dy))

        length_mm = 0.0
        for i in range(1, len(wp3d)):
            dx = wp3d[i][0] - wp3d[i - 1][0]
            dy = wp3d[i][1] - wp3d[i - 1][1]
            dz = wp3d[i][2] - wp3d[i - 1][2]
            length_mm += (dx * dx + dy * dy + dz * dz) ** 0.5
        total_length += length_mm

        route = {
            "from": from_type,
            "to": to_type,
            "waypoints": wp3d,
            "signal_type": sig_type,
            "layer_z": z_layer,
            "routed_length_mm": round(length_mm, 1),
            "color": _WIRE_SIGNAL_COLORS.get(sig_type, "#8888cc"),
        }
        if mcu_pin:
            route["mcu_pin"] = mcu_pin
        if comp_pin:
            route["comp_pin"] = comp_pin
        routes.append(route)

    n_layers = len(layers_used)
    decisions.append(_Decision(
        step="wire_route",
        principle="多層 3D 走線（pin-to-pin + riser + layer separation）",
        description=(
            f"3D A* 完成 {len(routes)} 條走線（{n_pin2pin} 條 pin-to-pin），"
            f"分佈於 {n_layers} 層 Z 平面，總長度 {total_length:.0f}mm。"
            "各訊號類型佔獨立 Z 層避免交叉；同層走線互為障礙物避免重疊。"
        ),
        formula="path = A*(pin_pos, obstacles ∪ same_layer_wires); z = f(signal_type)",
        six_e_stage="explain",
    ))
    return routes


def _astar_2d(
    start: Tuple[float, float],
    goal: Tuple[float, float],
    comps: List[_Comp],
    inner_l: float, inner_w: float,
    skip1: _Comp, skip2: _Comp,
    extra_blocked: Optional[set] = None,
) -> List[Tuple[float, float]]:
    res = _GRID_RES_MM
    gw = max(1, int(inner_l / res))
    gh = max(1, int(inner_w / res))

    def to_grid(x, y):
        return (max(0, min(gw - 1, int(x / res))),
                max(0, min(gh - 1, int(y / res))))

    def to_world(gx, gy):
        return (gx * res + res / 2, gy * res + res / 2)

    blocked = set()
    margin = 1
    for c in comps:
        if c is skip1 or c is skip2:
            continue
        gx0 = max(0, int(c.x / res) - margin)
        gy0 = max(0, int(c.y / res) - margin)
        gx1 = min(gw, int((c.x + c.L) / res) + margin)
        gy1 = min(gh, int((c.y + c.W) / res) + margin)
        for bx in range(gx0, gx1):
            for by in range(gy0, gy1):
                blocked.add((bx, by))
    if extra_blocked:
        blocked |= extra_blocked

    sg = to_grid(*start)
    gg = to_grid(*goal)

    if sg == gg:
        return [start, goal]

    open_set: list = []
    heapq.heappush(open_set, (0.0, sg))
    came_from: Dict[tuple, tuple] = {}
    g_score: Dict[tuple, float] = {sg: 0.0}

    def h(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]

    visited = 0
    max_visits = gw * gh * 2

    while open_set and visited < max_visits:
        _, current = heapq.heappop(open_set)
        visited += 1
        if current == gg:
            path = [goal]
            node = gg
            while node in came_from:
                node = came_from[node]
                path.append(to_world(*node))
            path.append(start)
            path.reverse()
            return _simplify_path(path)

        for dx, dy in neighbors:
            nb = (current[0] + dx, current[1] + dy)
            if nb[0] < 0 or nb[0] >= gw or nb[1] < 0 or nb[1] >= gh:
                continue
            if nb in blocked:
                continue
            tentative = g_score[current] + 1.0
            if tentative < g_score.get(nb, float("inf")):
                came_from[nb] = current
                g_score[nb] = tentative
                heapq.heappush(open_set, (tentative + h(nb, gg), nb))

    return [start, goal]


def _simplify_path(path: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if len(path) <= 2:
        return path
    result = [path[0]]
    for i in range(1, len(path) - 1):
        prev = result[-1]
        nxt = path[i + 1]
        dx1 = path[i][0] - prev[0]
        dy1 = path[i][1] - prev[1]
        dx2 = nxt[0] - path[i][0]
        dy2 = nxt[1] - path[i][1]
        if abs(dx1 * dy2 - dy1 * dx2) > 0.01:
            result.append(path[i])
    result.append(path[-1])
    return result


# ---------------------------------------------------------------------------
# ADR-8: Bus trunk routing — delegated to bus_routing sub-module
# ---------------------------------------------------------------------------
from .bus_routing import optimize_bus_routing, _distance_2d  # noqa: F401,E402
