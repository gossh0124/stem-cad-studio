"""lib/cad/shell/enclosure_io.py — I/O cutouts, port holes, connector openings."""
from __future__ import annotations
from typing import List

from .shell_spec import _PIN_PITCH, _TOP_DISPLAY_CLASSES


def _apply_side_cutouts(bd, pcb_spec, outer_l, outer_w, L, W, pcb_top_z,
                        cutout_clearance, depth, base_top_z=None):
    """Cut side-wall openings for each protruding SubComponent.

    Side semantics (PCB local):
      left   = -X wall (PCB x=0 side)
      right  = +X wall (PCB x=L side)
      bottom = -Y wall (PCB y=0 side)
      top    = +Y wall (PCB y=W side)

    Rotation handling (EAGLE convention):
      R0/R180  -> body_l along X, body_w along Y
      R90/R270 -> body_l along Y, body_w along X
    """
    count = 0
    for sc in pcb_spec.sub_components:
        if not sc.protrudes or not sc.profile:
            continue
        side = sc.protrudes
        if side not in ('left', 'right', 'top', 'bottom'):
            continue

        if side in ('left', 'right'):
            cutout_w_axis = sc.body_l if sc.rotation in ('R90', 'R270') else sc.body_w
            cz = pcb_top_z + sc.z + sc.body_h / 2
            cy = sc.anchor_y - W / 2
            wall_x = -outer_l/2 if side == 'left' else +outer_l/2
        else:
            cutout_w_axis = sc.body_w if sc.rotation in ('R90', 'R270') else sc.body_l
            cz = pcb_top_z + sc.z + sc.body_h / 2
            cx = sc.anchor_x - L / 2
            wall_y = -outer_w/2 if side == 'bottom' else +outer_w/2

        if sc.profile == 'circle':
            cw = ch = max(cutout_w_axis, sc.body_h) + 2 * cutout_clearance
        else:
            cw = cutout_w_axis + 2 * cutout_clearance
            ch = sc.body_h + 2 * cutout_clearance

        if base_top_z is not None:
            cz_top = cz + ch / 2
            if cz_top > base_top_z - 0.1:
                new_top = base_top_z - 0.1
                cz_bot = cz - ch / 2
                ch = new_top - cz_bot
                cz = (new_top + cz_bot) / 2

        if side in ('left', 'right'):
            _cut_on_yz_plane(bd, wall_x, cy, cz, cw, ch, depth, sc.profile)
        else:
            _cut_on_xz_plane(bd, wall_y, cx, cz, cw, ch, depth, sc.profile)

        count += 1
    return count


def _cut_on_yz_plane(bd, wall_x, cy, cz, cw, ch, depth, profile):
    """Cut a profile-aware shape on the YZ plane at X=wall_x."""
    plane = bd.Plane.YZ.offset(wall_x)
    with bd.BuildSketch(plane) as sk:
        with bd.Locations((cy, cz)):
            _draw_profile(bd, profile, cw, ch)
    extrude_amount = depth if wall_x < 0 else -depth
    bd.extrude(sk.sketch, amount=extrude_amount, mode=bd.Mode.SUBTRACT)


def _cut_on_xz_plane(bd, wall_y, cx, cz, cw, ch, depth, profile):
    """Cut a profile-aware shape on the XZ plane at Y=wall_y."""
    plane = bd.Plane.XZ.offset(wall_y)
    with bd.BuildSketch(plane) as sk:
        with bd.Locations((cx, cz)):
            _draw_profile(bd, profile, cw, ch)
    extrude_amount = -depth if wall_y < 0 else depth
    bd.extrude(sk.sketch, amount=extrude_amount, mode=bd.Mode.SUBTRACT)


def _draw_profile(bd, profile, w, h):
    """Draw a profile shape in current sketch Locations center."""
    if profile == 'circle':
        bd.Circle(min(w, h) / 2)
    elif profile == 'stadium':
        bd.RectangleRounded(w, h, max(0.5, min(w, h) / 2 - 0.1))
    else:
        bd.RectangleRounded(w, h, 0.5)


def _apply_header_cutouts(bd, pcb_spec, L, W, top_z, depth):
    """Cut header group slots/rects on the top plane. Returns count."""
    pin_index = pcb_spec.pin_index_map()
    count = 0
    for grp in pcb_spec.header_groups:
        grp_pins = [p for p in (pin_index.get(i) for i in grp.pin_indices)
                    if p is not None]
        if not grp_pins:
            continue
        xs = [p.x for p in grp_pins]
        ys = [p.y for p in grp_pins]
        cx = (min(xs) + max(xs)) / 2 - L / 2
        cy = (min(ys) + max(ys)) / 2 - W / 2
        cw = (max(xs) - min(xs)) + _PIN_PITCH + 2 * grp.clearance_mm
        if grp.profile == 'slot' and grp.rows == 1:
            ch = _PIN_PITCH + 2 * grp.clearance_mm
        else:
            ch = (max(ys) - min(ys)) + _PIN_PITCH + 2 * grp.clearance_mm
        _cut_slot_top(bd, top_z, cx, cy, cw, ch, depth, profile=grp.profile)
        count += 1
    return count


def _cut_slot_top(bd, top_z, cx, cy, w, h, depth, profile='slot'):
    """Cut slot/rect on the top face."""
    plane = bd.Plane.XY.offset(top_z)
    with bd.BuildSketch(plane) as sk:
        with bd.Locations((cx, cy)):
            if profile == 'slot':
                radius = min(w, h)/2 - 0.1
                bd.RectangleRounded(w, h, max(0.5, radius))
            else:
                bd.RectangleRounded(w, h, 0.8)
    bd.extrude(sk.sketch, amount=depth, both=True, mode=bd.Mode.SUBTRACT)


def _cut_assembly_io(
    bd, placements: List[dict],
    inner_l: float, inner_w: float,
    outer_l: float, outer_w: float,
    base_h: float, wall: float,
    clearance: float,
) -> int:
    """Cut IO openings for face_out='side-*' placements."""
    count = 0
    for p in placements:
        face_out = p.get("face_out", "")
        if not face_out.startswith("side-"):
            continue

        sx = p["x"] + p["L"] / 2
        sy = p["y"] + p["W"] / 2
        H = p["H"]

        cx = sx - inner_l / 2
        cy = sy - inner_w / 2
        cz = -base_h / 2 + wall + H / 2

        cw_along = (p["W"] if face_out in ("side-left", "side-right") else p["L"]) + 2 * clearance
        ch = H + 2 * clearance
        depth = wall + 4

        if face_out == "side-left":
            wall_x = -outer_l / 2
            _cut_on_yz_plane(bd, wall_x, cy, cz, cw_along, ch, depth, "rect")
        elif face_out == "side-right":
            wall_x = +outer_l / 2
            _cut_on_yz_plane(bd, wall_x, cy, cz, cw_along, ch, depth, "rect")
        elif face_out == "side-front":
            wall_y = -outer_w / 2
            _cut_on_xz_plane(bd, wall_y, cx, cz, cw_along, ch, depth, "rect")
        elif face_out == "side-back":
            wall_y = +outer_w / 2
            _cut_on_xz_plane(bd, wall_y, cx, cz, cw_along, ch, depth, "rect")
        else:
            continue
        count += 1
    return count


def _cut_top_display_windows(
    bd, placements: list, lid_h: float,
    inner_l: float, inner_w: float,
    clearance: float,
) -> int:
    """J3: Cut rectangular display windows on lid top for face_out='top' display components."""
    count = 0
    for p in placements:
        if p.get("face_out") != "top":
            continue
        if p.get("type") not in _TOP_DISPLAY_CLASSES:
            continue

        sx = p["x"] + p["L"] / 2
        sy = p["y"] + p["W"] / 2
        cx = sx - inner_l / 2
        cy = sy - inner_w / 2

        cw = p["L"] + 2 * clearance
        ch = p["W"] + 2 * clearance
        depth = lid_h + 2

        with bd.Locations((cx, cy, 0)):
            bd.Box(cw, ch, depth, mode=bd.Mode.SUBTRACT)
        count += 1
    return count
