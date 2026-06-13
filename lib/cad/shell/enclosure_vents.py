"""lib/cad/shell/enclosure_vents.py — Ventilation, wire grooves, fillet utilities."""
from __future__ import annotations

from .shell_spec import (
    _WIRE_DIA_MM, _WIRE_GROOVE_CLEARANCE, _WIRE_GROOVE_DEPTH,
    _VENT_SLIT_W, _VENT_SLIT_H, _VENT_SLIT_GAP,
)
from .enclosure_io import _cut_on_xz_plane, _cut_slot_top


def _cut_wire_grooves_lid(
    bd, wire_routes: list, lid_h: float,
    inner_l: float, inner_w: float,
) -> int:
    """E11: Cut wire routing grooves on lid bottom surface."""
    groove_w = _WIRE_DIA_MM + 2 * _WIRE_GROOVE_CLEARANCE
    groove_d = _WIRE_GROOVE_DEPTH
    groove_z_center = -lid_h / 2 + groove_d / 2

    count = 0
    for route in wire_routes:
        waypoints = route.get("waypoints", [])
        if len(waypoints) < 2:
            continue

        for i in range(1, len(waypoints)):
            x1, y1 = waypoints[i-1][0], waypoints[i-1][1]
            x2, y2 = waypoints[i][0], waypoints[i][1]

            cx1 = x1 - inner_l / 2
            cy1 = y1 - inner_w / 2
            cx2 = x2 - inner_l / 2
            cy2 = y2 - inner_w / 2

            dx = cx2 - cx1
            dy = cy2 - cy1
            length = (dx * dx + dy * dy) ** 0.5
            if length < 0.5:
                continue

            mid_x = (cx1 + cx2) / 2
            mid_y = (cy1 + cy2) / 2

            import math
            angle_deg = math.degrees(math.atan2(dy, dx))

            with bd.Locations((mid_x, mid_y, groove_z_center)):
                bd.Box(length + groove_w, groove_w, groove_d * 2,
                       rotation=(0, 0, angle_deg),
                       mode=bd.Mode.SUBTRACT)
        count += 1
    return count


def _cut_louver_vents_base(
    bd, vent_placements: list, outer_l: float, outer_w: float,
    base_h: float, wall: float,
) -> int:
    """E12: Cut louver vent slits on base side wall. Handles face='side_lower'."""
    count = 0
    for vent in vent_placements:
        face = vent.get("face", "")
        area_mm2 = vent.get("area_mm2", 0)
        if not area_mm2:
            continue
        if face != "side_lower":
            continue

        slit_area = _VENT_SLIT_W * _VENT_SLIT_H
        n_slits = max(2, int(area_mm2 / slit_area))

        wall_y = -outer_w / 2
        slit_z = -base_h / 2 + wall + _VENT_SLIT_H * 1.5
        total_w = n_slits * _VENT_SLIT_W + (n_slits - 1) * _VENT_SLIT_GAP
        span = outer_l - 2 * wall - 4
        if total_w > span:
            n_slits = max(2, int(span / (_VENT_SLIT_W + _VENT_SLIT_GAP)))
            total_w = n_slits * _VENT_SLIT_W + (n_slits - 1) * _VENT_SLIT_GAP
        # 即便重算後，最小 2 條 slit 仍可能超出可用牆面跨距（小型外殼）；
        # 此時不可硬切，否則會在外殼角落外側破牆。改為跳過此 vent 並記錄原因。
        if total_w > span:
            _log_vent_skip("base", face, total_w, span)
            continue

        start_x = -total_w / 2 + _VENT_SLIT_W / 2
        for i in range(n_slits):
            sx = start_x + i * (_VENT_SLIT_W + _VENT_SLIT_GAP)
            _cut_on_xz_plane(bd, wall_y, sx, slit_z,
                             _VENT_SLIT_W, _VENT_SLIT_H, wall + 2, "rect")
            count += 1
    return count


def _cut_louver_vents_lid(
    bd, vent_placements: list, outer_l: float, outer_w: float,
    lid_h: float, wall: float,
) -> int:
    """E12: Cut louver vent slits on lid top. Handles face='side_upper'/'top'/'top_grid'."""
    count = 0
    for vent in vent_placements:
        face = vent.get("face", "")
        area_mm2 = vent.get("area_mm2", 0)
        if not area_mm2:
            continue
        if face not in ("side_upper", "top", "top_grid"):
            continue

        slit_area = _VENT_SLIT_W * _VENT_SLIT_H
        n_slits = max(2, int(area_mm2 / slit_area))
        total_w = n_slits * _VENT_SLIT_W + (n_slits - 1) * _VENT_SLIT_GAP
        span = outer_l - 2 * wall - 4
        if total_w > span:
            n_slits = max(2, int(span / (_VENT_SLIT_W + _VENT_SLIT_GAP)))
            total_w = n_slits * _VENT_SLIT_W + (n_slits - 1) * _VENT_SLIT_GAP
        # 即便重算後，最小 2 條 slit 仍可能超出可用跨距（小型外殼）；
        # 此時不可硬切，否則會破壞蓋體邊緣。改為跳過此 vent 並記錄原因。
        if total_w > span:
            _log_vent_skip("lid", face, total_w, span)
            continue

        start_x = -total_w / 2 + _VENT_SLIT_W / 2
        for i in range(n_slits):
            sx = start_x + i * (_VENT_SLIT_W + _VENT_SLIT_GAP)
            _cut_slot_top(bd, top_z=+lid_h / 2, cx=sx, cy=0,
                          w=_VENT_SLIT_W, h=_VENT_SLIT_H,
                          depth=lid_h + 2, profile='slot')
            count += 1
    return count


def _apply_vertical_edge_fillet(bd, build_part, radius: float) -> float:
    """J2 Engage: Fillet vertical outer edges. Returns actual radius used.

    Only picks full-height edges (>= 0.9 * longest z edge) to avoid
    OCCT failures on short cutout corner edges. Falls back to half radius
    on failure, down to 0.3mm minimum.
    """
    if radius <= 0:
        return 0.0
    try:
        part = build_part.part
        z_edges = part.edges().filter_by(bd.Axis.Z)
        if not z_edges:
            return 0.0

        max_len = max(e.length for e in z_edges)
        outer_edges = [e for e in z_edges if e.length >= 0.9 * max_len]
        if not outer_edges:
            return 0.0
    except Exception as exc:
        _log_fillet_warn(exc, attempted=radius)
        return 0.0

    r = radius
    while r >= 0.3:
        try:
            bd.fillet(outer_edges, radius=r)
            if r != radius:
                _log_fillet_downgrade(radius, r)
            return r
        except Exception as exc:
            r *= 0.5
            if r < 0.3:
                _log_fillet_warn(exc, attempted=radius)
                return 0.0
    return 0.0


def _log_vent_skip(where: str, face: str, total_w: float, span: float):
    import logging
    logging.getLogger("cadhllm.cad.shell").warning(
        "louver vent 略過（%s, face=%s）：最小 2 條 slit 跨距 %.1fmm 超出可用牆面 %.1fmm，"
        "硬切會破牆，故不切此 vent。",
        where, face, total_w, span,
    )


def _log_fillet_warn(exc, attempted: float = 0.0):
    import logging
    logging.getLogger("cadhllm.cad.shell").warning(
        "fillet 失敗（已放棄邊角圓角，原本嘗試 R=%.2fmm）：%s",
        attempted, exc,
    )


def _log_fillet_downgrade(orig: float, actual: float):
    import logging
    logging.getLogger("cadhllm.cad.shell").info(
        "fillet 半徑由 R=%.2fmm 降級為 R=%.2fmm（OCCT 容忍度限制）",
        orig, actual,
    )
