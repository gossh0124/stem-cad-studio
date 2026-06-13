"""lib/cad/shell — PCB enclosure shell generation (build123d).

Coordinate system (shell local):
  enclosure center = (0, 0, 0)
  X = PCB long axis; Y = PCB short axis; Z = vertical, PCB surface above Z=0

Sub-modules:
  shell_spec.py     — Dataclasses, constants, validation
  enclosure_io.py   — I/O cutouts, port holes, connector openings
  enclosure_vents.py — Ventilation, wire grooves, fillet utilities
"""
from __future__ import annotations
from typing import List, Optional

from .shell_spec import (
    EnclosureSpec,
    AssemblySpec,
    TwoPieceSpec,
    validate_snap_fit_stress,
    _validate_wall_thickness,
    _FALLBACK_COMPONENT_H,
    _LIP_Z_OFFSET,
    _PIN_PITCH,
    _DEFAULT_PIN_HEIGHT,
    _MIN_WALL_MM,
    _MATERIAL_YIELD_STRAIN,
    _SNAP_FIT_SAFETY_FACTOR,
    _TOP_DISPLAY_CLASSES,
    _DEFAULT_FILLET_R,
)
from .enclosure_io import (
    _apply_side_cutouts,
    _apply_header_cutouts,
    _cut_assembly_io,
    _cut_top_display_windows,
    _cut_face_windows,
)
from .enclosure_vents import (
    _cut_wire_grooves_lid,
    _cut_louver_vents_base,
    _cut_louver_vents_lid,
    _apply_vertical_edge_fillet,
)
from .assembly_v3_build import build_assembly_from_scene


def build_pcb_enclosure(
    pcb_spec,
    padding: float = 2.5,
    wall: float = 2.0,
    tol: float = 0.3,
    with_lid: bool = True,
    cutout_clearance: float = 1.0,
    standoff_height: float = 5.0,
    standoff_outer_d: float = 5.0,
    standoff_inner_d: float = 2.5,
):
    """Build a single-piece 3D enclosure from PCBSpec (build123d Part).

    Returns:
        (part, EnclosureSpec)
    """
    _validate_wall_thickness(wall)
    import build123d as bd

    L = pcb_spec.length
    W = pcb_spec.width
    pcb_t = pcb_spec.pcb_thickness

    component_h = max((sc.body_h for sc in pcb_spec.sub_components),
                      default=_FALLBACK_COMPONENT_H)

    inner_l = L + 2 * padding
    inner_w = W + 2 * padding
    inner_h = standoff_height + pcb_t + component_h + padding

    outer_l = inner_l + 2 * (wall + tol)
    outer_w = inner_w + 2 * (wall + tol)
    outer_h = wall + inner_h + (wall if with_lid else 0)

    pcb_bottom_z = -outer_h / 2 + wall + standoff_height
    pcb_top_z = pcb_bottom_z + pcb_t

    cut_count = 0

    with bd.BuildPart() as enc:
        bd.Box(outer_l, outer_w, outer_h)

        cavity_h = inner_h + 0.5
        cavity_z = -outer_h/2 + wall + cavity_h/2 - 0.25
        with bd.Locations((0, 0, cavity_z)):
            bd.Box(inner_l, inner_w, cavity_h, mode=bd.Mode.SUBTRACT)

        if not with_lid:
            with bd.Locations((0, 0, outer_h/2)):
                bd.Box(inner_l + 2*tol, inner_w + 2*tol, wall + 2,
                       mode=bd.Mode.SUBTRACT)

        standoff_count = _add_pcb_standoffs(
            bd, pcb_spec, L, W,
            base_z=-outer_h/2 + wall,
            height=standoff_height,
            outer_d=standoff_outer_d, inner_d=standoff_inner_d,
        )

        cut_count += _apply_side_cutouts(
            bd, pcb_spec, outer_l, outer_w, L, W, pcb_top_z,
            cutout_clearance, depth=wall + 4,
            base_top_z=outer_h/2,
        )

        if with_lid and pcb_spec.header_groups:
            cut_count += _apply_header_cutouts(
                bd, pcb_spec, L, W,
                top_z=outer_h/2 - wall/2,
                depth=wall + 2,
            )

    spec_out = EnclosureSpec(
        outer_l=outer_l, outer_w=outer_w, outer_h=outer_h,
        inner_l=inner_l, inner_w=inner_w, inner_h=inner_h,
        wall=wall, tol=tol,
        pcb_top_z=pcb_top_z,
        pcb_bottom_z=pcb_bottom_z,
        standoff_height=standoff_height,
        cutout_count=cut_count,
        standoff_count=standoff_count,
    )
    return enc.part, spec_out


def _add_pcb_standoffs(bd, pcb_spec, L, W, base_z, height,
                       outer_d, inner_d):
    """Add standoff cylinders for each mounting hole in the base."""
    overlap = 0.3
    outer_h = height + overlap
    outer_z_center = base_z + height / 2 - overlap / 2

    inner_h = height - 1.0
    inner_z_center = base_z + height - inner_h / 2

    for hole in pcb_spec.mounting_holes:
        sx = hole.x - L / 2
        sy = hole.y - W / 2
        with bd.Locations((sx, sy, outer_z_center)):
            bd.Cylinder(radius=outer_d / 2, height=outer_h, mode=bd.Mode.ADD)
        with bd.Locations((sx, sy, inner_z_center)):
            bd.Cylinder(radius=inner_d / 2, height=inner_h, mode=bd.Mode.SUBTRACT)
    return len(pcb_spec.mounting_holes)


def compute_two_piece_spec(
    pcb_spec,
    padding: float = 2.5,
    wall: float = 2.0,
    tol: float = 0.3,
    standoff_height: float = 5.0,
    lid_thickness: float = 2.0,
    snap_arm_w: float = 4.0,
    snap_arm_t: float = 1.5,
    snap_arm_h: float = 11.0,
    snap_lip_h: float = 1.0,
    snap_lip_d: float = 0.5,
    snap_gap: float = 0.1,
) -> TwoPieceSpec:
    """Compute TwoPieceSpec dimensions (no build123d B-rep), for analysis scripts."""
    L, W = pcb_spec.length, pcb_spec.width
    component_h = max((sc.body_h for sc in pcb_spec.sub_components),
                      default=_FALLBACK_COMPONENT_H)
    inner_l = L + 2 * padding
    inner_w = W + 2 * padding
    inner_h = standoff_height + pcb_spec.pcb_thickness + component_h + padding
    outer_l = inner_l + 2 * (wall + tol)
    outer_w = inner_w + 2 * (wall + tol)
    base_h = wall + inner_h
    pcb_bottom_z = -base_h/2 + wall + standoff_height
    pcb_top_z = pcb_bottom_z + pcb_spec.pcb_thickness

    return TwoPieceSpec(
        outer_l=outer_l, outer_w=outer_w,
        base_h=base_h, lid_h=lid_thickness,
        inner_l=inner_l, inner_w=inner_w, inner_h=inner_h,
        wall=wall, tol=tol,
        pcb_top_z=pcb_top_z, pcb_bottom_z=pcb_bottom_z,
        standoff_height=standoff_height,
        standoff_count=len(pcb_spec.mounting_holes),
        side_cutout_count=sum(1 for sc in pcb_spec.sub_components
                              if sc.protrudes in ('left', 'right', 'top', 'bottom')
                              and sc.profile),
        lid_cutout_count=len(pcb_spec.header_groups),
        snap_count=4,
        snap_arm_w=snap_arm_w, snap_arm_t=snap_arm_t, snap_arm_h=snap_arm_h,
        snap_lip_h=snap_lip_h, snap_lip_d=snap_lip_d, snap_gap=snap_gap,
    )


def build_pcb_two_piece(
    pcb_spec,
    padding: float = 2.5,
    wall: float = 2.0,
    tol: float = 0.3,
    standoff_height: float = 5.0,
    standoff_outer_d: float = 5.0,
    standoff_inner_d: float = 2.5,
    cutout_clearance: float = 1.0,
    lid_thickness: float = 2.0,
    snap_arm_w: float = 4.0,
    snap_arm_t: float = 1.5,
    snap_arm_h: float = 11.0,
    snap_lip_h: float = 1.0,
    snap_lip_d: float = 0.5,
    snap_gap: float = 0.1,
    snap_recess_extra: float = 0.4,
    material: str = "PLA",
    class_name=None,
):
    """Build two-piece enclosure (base + lid + snap-fit).

    PV5: auto-validates snap-fit cantilever stress; raises if over limit.
    """
    _validate_wall_thickness(wall)
    snap_stress = validate_snap_fit_stress(
        snap_arm_t, snap_arm_h, snap_lip_d, material)
    if not snap_stress["ok"]:
        raise ValueError(
            f"PV5 snap-fit 應力不合格（{material}）：應變 {snap_stress['strain_pct']:.1f}% "
            f"/ yield 利用率 {snap_stress['utilization_pct']:.0f}% > 70%。"
            f"{'；'.join(snap_stress.get('suggestions', []))}"
        )
    import build123d as bd

    L = pcb_spec.length
    W = pcb_spec.width
    pcb_t = pcb_spec.pcb_thickness
    component_h = max((sc.body_h for sc in pcb_spec.sub_components),
                      default=_FALLBACK_COMPONENT_H)

    inner_l = L + 2 * padding
    inner_w = W + 2 * padding
    inner_h = standoff_height + pcb_t + component_h + padding

    outer_l = inner_l + 2 * (wall + tol)
    outer_w = inner_w + 2 * (wall + tol)

    base_h = wall + inner_h
    lid_h = lid_thickness

    pcb_bottom_z = -base_h/2 + wall + standoff_height
    pcb_top_z = pcb_bottom_z + pcb_t

    snap_arm_xs_pos_y = [-outer_l * 0.30, +outer_l * 0.30]
    snap_arm_xs_neg_y = [-outer_l * 0.20, +outer_l * 0.20]
    snap_layout = [
        (+1, snap_arm_xs_pos_y),
        (-1, snap_arm_xs_neg_y),
    ]
    snap_count = sum(len(xs) for _, xs in snap_layout)

    base_part, side_cut_count, standoff_n = _build_two_piece_base(
        bd, pcb_spec, outer_l, outer_w, base_h, inner_l, inner_w,
        wall, tol,
        standoff_height, standoff_outer_d, standoff_inner_d,
        cutout_clearance,
        pcb_top_z,
        snap_layout,
        snap_arm_w, snap_lip_h, snap_lip_d, snap_recess_extra,
        snap_arm_h,
    )

    lid_part, lid_cut_count = _build_two_piece_lid(
        bd, pcb_spec, outer_l, outer_w, lid_h, L, W,
        snap_layout,
        snap_arm_w, snap_arm_t, snap_arm_h,
        snap_lip_h, snap_lip_d, snap_gap,
        cutout_clearance,
        class_name,
    )

    spec = TwoPieceSpec(
        outer_l=outer_l, outer_w=outer_w,
        base_h=base_h, lid_h=lid_h,
        inner_l=inner_l, inner_w=inner_w, inner_h=inner_h,
        wall=wall, tol=tol,
        pcb_top_z=pcb_top_z, pcb_bottom_z=pcb_bottom_z,
        standoff_height=standoff_height, standoff_count=standoff_n,
        side_cutout_count=side_cut_count,
        lid_cutout_count=lid_cut_count,
        snap_count=snap_count,
        snap_arm_w=snap_arm_w, snap_arm_t=snap_arm_t, snap_arm_h=snap_arm_h,
        snap_lip_h=snap_lip_h, snap_lip_d=snap_lip_d, snap_gap=snap_gap,
    )
    return base_part, lid_part, spec


def _build_two_piece_base(
    bd, pcb_spec, outer_l, outer_w, base_h, inner_l, inner_w,
    wall, tol,
    standoff_height, standoff_outer_d, standoff_inner_d,
    cutout_clearance,
    pcb_top_z,
    snap_layout,
    snap_arm_w, snap_lip_h, snap_lip_d, snap_recess_extra,
    snap_arm_h,
):
    """Build base: bottom + 4 walls + standoffs + side cutouts + snap recesses."""
    L, W = pcb_spec.length, pcb_spec.width

    lip_z_in_base = base_h/2 - snap_arm_h + snap_lip_h/2 + _LIP_Z_OFFSET

    with bd.BuildPart() as base:
        bd.Box(outer_l, outer_w, base_h)

        cavity_h = base_h - wall + 0.5
        cavity_z = -base_h/2 + wall + cavity_h/2 - 0.25
        with bd.Locations((0, 0, cavity_z)):
            bd.Box(inner_l, inner_w, cavity_h, mode=bd.Mode.SUBTRACT)

        standoff_count = _add_pcb_standoffs(
            bd, pcb_spec, L, W,
            base_z=-base_h/2 + wall,
            height=standoff_height,
            outer_d=standoff_outer_d, inner_d=standoff_inner_d,
        )

        side_cut_count = _apply_side_cutouts(
            bd, pcb_spec, outer_l, outer_w, L, W, pcb_top_z,
            cutout_clearance, depth=wall + 4,
            base_top_z=base_h/2,
        )

        recess_w = snap_arm_w + snap_recess_extra
        recess_h = snap_lip_h + snap_recess_extra
        recess_d = snap_lip_d + snap_recess_extra
        for y_sign, arm_xs in snap_layout:
            for ax in arm_xs:
                ry = y_sign * (outer_w/2 - recess_d/2)
                with bd.Locations((ax, ry, lip_z_in_base)):
                    bd.Box(recess_w, recess_d, recess_h, mode=bd.Mode.SUBTRACT)

    return base.part, side_cut_count, standoff_count


def _build_two_piece_lid(
    bd, pcb_spec, outer_l, outer_w, lid_h, L, W,
    snap_layout,
    snap_arm_w, snap_arm_t, snap_arm_h,
    snap_lip_h, snap_lip_d, snap_gap,
    cutout_clearance,
    class_name=None,
):
    """Build lid: flat plate + header cutouts + snap arms."""
    flange = snap_gap + snap_arm_t
    lid_outer_w = outer_w + 2 * flange

    with bd.BuildPart() as lid:
        bd.Box(outer_l, lid_outer_w, lid_h)

        lid_cut_count = _apply_header_cutouts(
            bd, pcb_spec, L, W, top_z=0.0, depth=lid_h + 2,
        )
        lid_cut_count += _cut_face_windows(
            bd, class_name, lid_top_z=0.0, depth=lid_h + 2,
        )

        for y_sign, arm_xs in snap_layout:
            for ax in arm_xs:
                arm_y = y_sign * (outer_w/2 + snap_gap + snap_arm_t/2)
                arm_z = -lid_h/2 - snap_arm_h/2
                with bd.Locations((ax, arm_y, arm_z)):
                    bd.Box(snap_arm_w, snap_arm_t, snap_arm_h, mode=bd.Mode.ADD)

                lip_y = y_sign * (outer_w/2 + snap_gap - snap_lip_d/2)
                lip_z = -lid_h/2 - snap_arm_h + snap_lip_h/2 + _LIP_Z_OFFSET
                with bd.Locations((ax, lip_y, lip_z)):
                    bd.Box(snap_arm_w, snap_lip_d, snap_lip_h, mode=bd.Mode.ADD)

    return lid.part, lid_cut_count

