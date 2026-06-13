"""assembly_v3_build.py — build the two-piece enclosure STL directly from the V3
SceneGraph (lib.assembly_solver.assembly_solver_v3.solve_v3), so the printed STL is
sourced from the SAME solver as the 3D view (resolves UND-A4 V2/V3 divergence).

Coordinate handling — the V3 scene is y-up, enclosure-CENTRE origin; the shell is
built z-up, enclosure-CENTRE origin. A scene point P = [X, Yup, Z] maps to the
builder frame as:
    builder_x = P[0]                       (already centred — NO −inner/2)
    builder_y = P[2]                       (scene depth axis → builder Y)
    builder_z = -base_h/2 + wall + P[1]    (P[1] = height above the inner floor)
Module/port/hole CENTRES are used directly (NO +L/2 recovery — V3 gives centres).

This is the V3-native replacement for build_assembly_two_piece(placements,...). It is
ADDITIVE: the V2 path stays until phase4_handler is switched + V2 retired (Phase 2b B-3).
"""
from __future__ import annotations

import math
from typing import Optional

from .shell_spec import (
    _DEFAULT_FILLET_R,
    _WIRE_DIA_MM, _WIRE_GROOVE_CLEARANCE, _WIRE_GROOVE_DEPTH,
    AssemblySpec, _validate_wall_thickness,
)
from .enclosure_io import _cut_on_yz_plane, _cut_on_xz_plane
from .enclosure_vents import (
    _apply_vertical_edge_fillet, _cut_louver_vents_base, _cut_louver_vents_lid,
)

# A shell_port whose centre is within this distance of an inner wall is treated as
# an edge connector facing that wall → cut a side IO opening (replaces V2 face_out).
_SIDE_IO_WALL_TOL_MM = 4.0


def _scene_xy(p):
    """Scene [X,Yup,Z] → builder (x, y) on the floor plane (already centre-origin)."""
    return p[0], p[2]


def _v3_wire_grooves(bd, wires: list, lid_h: float) -> int:
    """Lid-bottom routing grooves from V3 wires[].path3d (floor projection: x=p[0], y=p[2])."""
    groove_w = _WIRE_DIA_MM + 2 * _WIRE_GROOVE_CLEARANCE
    groove_d = _WIRE_GROOVE_DEPTH
    groove_z = -lid_h / 2 + groove_d / 2
    count = 0
    for w in wires:
        path = w.get("path3d", [])
        if len(path) < 2:
            continue
        for i in range(1, len(path)):
            x1, y1 = _scene_xy(path[i - 1])
            x2, y2 = _scene_xy(path[i])
            dx, dy = x2 - x1, y2 - y1
            length = (dx * dx + dy * dy) ** 0.5
            if length < 0.5:
                continue
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            angle = math.degrees(math.atan2(dy, dx))
            with bd.Locations((mid_x, mid_y, groove_z)):
                bd.Box(length + groove_w, groove_w, groove_d * 2,
                       rotation=(0, 0, angle), mode=bd.Mode.SUBTRACT)
        count += 1
    return count


def _v3_panel_cutouts(bd, face_cutouts: list, lid_h: float, clearance: float) -> int:
    """Lid panel openings from V3 enclosure.face_cutouts. Branches on shape (rect/round);
    class gating is gone — the solver already selected FACE_RELATIONS parts."""
    count = 0
    depth = lid_h + 2
    for fc in face_cutouts:
        if fc.get("face") != "top":
            continue
        cx, cy = _scene_xy(fc["center"])
        shape = fc.get("shape")
        if shape == "round":
            r = float(fc["diameter"]) / 2 + clearance
            with bd.Locations((cx, cy, 0)):
                bd.Cylinder(r, depth, mode=bd.Mode.SUBTRACT)
        else:  # rect
            cw = float(fc["width"]) + 2 * clearance
            ch = float(fc["height"]) + 2 * clearance
            with bd.Locations((cx, cy, 0)):
                bd.Box(cw, ch, depth, mode=bd.Mode.SUBTRACT)
        count += 1
    return count


def _v3_wall_holes(bd, holes: list, outer_l: float, outer_w: float,
                   base_h: float, wall: float) -> int:
    """Round wall bores from V3 enclosure.holes (cross-wall wiring). face ∈ x±/y±;
    centre[1] = height above the inner floor."""
    count = 0
    depth = wall + 4
    for h in holes:
        face = h.get("face", "")
        cx, cy = _scene_xy(h["center"])
        cz = -base_h / 2 + wall + h["center"][1]
        r = float(h.get("diameter", 4.0)) / 2
        if face == "x-":
            _cut_on_yz_plane(bd, -outer_l / 2, cy, cz, 2 * r, 2 * r, depth, "circle")
        elif face == "x+":
            _cut_on_yz_plane(bd, +outer_l / 2, cy, cz, 2 * r, 2 * r, depth, "circle")
        elif face == "y-":
            _cut_on_xz_plane(bd, -outer_w / 2, cx, cz, 2 * r, 2 * r, depth, "circle")
        elif face == "y+":
            _cut_on_xz_plane(bd, +outer_w / 2, cx, cz, 2 * r, 2 * r, depth, "circle")
        else:
            continue
        count += 1
    return count


def _v3_side_io(bd, modules: list, il: float, iw: float,
                outer_l: float, outer_w: float, base_h: float, wall: float,
                clearance: float) -> int:
    """Side-wall IO openings from V3 modules[].shell_ports — the V3-native replacement
    for V2 face_out='side-*'. A port whose centre sits within _SIDE_IO_WALL_TOL_MM of an
    inner wall is an edge connector facing that wall; cut a rect opening of its size."""
    count = 0
    depth = wall + 4
    for m in modules:
        for sp in m.get("shell_ports", []):
            # Only PCB-EDGE connectors face an enclosure wall. side=='face' ports are
            # top-surface pin headers (internal — D0~D7, ICSP, I2C headers); they must
            # NOT get a wall opening. This is the selectivity V2's face_out encoded.
            if sp.get("side") == "face":
                continue
            world = sp.get("world")
            if not world:
                continue
            px, py = _scene_xy(world)        # floor-plane centre (already centred)
            pz = -base_h / 2 + wall + world[1]
            pw = float(sp.get("width", 0) or 0)
            ph = float(sp.get("height", 0) or 0)
            if pw <= 0 or ph <= 0:
                continue
            # distance to each inner wall
            d = {"x-": abs(px - (-il / 2)), "x+": abs(px - il / 2),
                 "y-": abs(py - (-iw / 2)), "y+": abs(py - iw / 2)}
            face = min(d, key=d.get)
            if d[face] > _SIDE_IO_WALL_TOL_MM:
                continue  # not an edge connector facing a wall — no side opening
            cw = pw + 2 * clearance
            ch = ph + 2 * clearance
            if face == "x-":
                _cut_on_yz_plane(bd, -outer_l / 2, py, pz, cw, ch, depth, "rect")
            elif face == "x+":
                _cut_on_yz_plane(bd, +outer_l / 2, py, pz, cw, ch, depth, "rect")
            elif face == "y-":
                _cut_on_xz_plane(bd, -outer_w / 2, px, pz, cw, ch, depth, "rect")
            else:  # y+
                _cut_on_xz_plane(bd, +outer_w / 2, px, pz, cw, ch, depth, "rect")
            count += 1
    return count


def build_assembly_from_scene(
    scene: dict,
    project_name: str = "assembly",
    wall: Optional[float] = None,
    tol: float = 0.3,
    lid_thickness: float = 2.0,
    fillet_r: float = _DEFAULT_FILLET_R,
    cutout_clearance: float = 1.0,
):
    """Build a two-piece enclosure (base, lid, AssemblySpec) directly from a V3 SceneGraph.

    inner dims + wall come from scene['enclosure'] (already autosized by the solver — no
    bbox/padding derivation). All openings are V3-native: face_cutouts (panel), holes
    (wall bores), wires.path3d (grooves), thermal_field.vent_placements (louvers),
    shell_ports (side IO). Raises on an empty/invalid scene (no-fallback).
    """
    import build123d as bd

    enc = scene.get("enclosure") or {}
    inner = enc.get("inner")
    if not inner or len(inner) != 3:
        raise ValueError("scene['enclosure']['inner'] missing — cannot build (no fallback)")
    if not scene.get("modules"):
        raise ValueError("scene has no modules — cannot build assembly (no fallback)")
    il, iw, ih = (float(v) for v in inner)
    wall = float(enc.get("wall", 2.0)) if wall is None else wall
    _validate_wall_thickness(wall)

    outer_l = il + 2 * (wall + tol)
    outer_w = iw + 2 * (wall + tol)
    base_h = wall + ih
    lid_h = lid_thickness

    holes = enc.get("holes", []) or []
    face_cutouts = enc.get("face_cutouts", []) or []
    wires = scene.get("wires", []) or []
    vents = (scene.get("thermal_field") or {}).get("vent_placements", []) or []
    modules = scene.get("modules", [])

    with bd.BuildPart() as base:
        bd.Box(outer_l, outer_w, base_h)
        cavity_h = ih + 0.5
        cavity_z = -base_h / 2 + wall + cavity_h / 2 - 0.25
        with bd.Locations((0, 0, cavity_z)):
            bd.Box(il, iw, cavity_h, mode=bd.Mode.SUBTRACT)
        n_io = _v3_side_io(bd, modules, il, iw, outer_l, outer_w, base_h, wall, cutout_clearance)
        n_holes = _v3_wall_holes(bd, holes, outer_l, outer_w, base_h, wall)
        n_vent_base = _cut_louver_vents_base(bd, vents, outer_l, outer_w, base_h, wall)
        fillet_base = _apply_vertical_edge_fillet(bd, base, fillet_r) if fillet_r > 0 else 0.0

    with bd.BuildPart() as lid:
        bd.Box(outer_l, outer_w, lid_h)
        n_wire = _v3_wire_grooves(bd, wires, lid_h)
        n_panel = _v3_panel_cutouts(bd, face_cutouts, lid_h, cutout_clearance)
        n_vent_lid = _cut_louver_vents_lid(bd, vents, outer_l, outer_w, lid_h, wall)
        fillet_lid = _apply_vertical_edge_fillet(bd, lid, fillet_r) if fillet_r > 0 else 0.0

    actual_fillet = min(fillet_base, fillet_lid) if fillet_r > 0 else 0.0
    spec = AssemblySpec(
        outer_l=outer_l, outer_w=outer_w, base_h=base_h, lid_h=lid_h,
        inner_l=il, inner_w=iw, inner_h=ih, wall=wall, tol=tol,
        fillet_r=actual_fillet, n_components=len(modules),
        n_io_cutouts=n_io + n_holes, n_wire_grooves=n_wire,
        n_vents=n_vent_base + n_vent_lid, n_top_windows=n_panel,
        project_name=project_name,
    )
    return base.part, lid.part, spec
