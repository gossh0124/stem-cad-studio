"""lib/cad/pcb_common.py — PCB 模型共用工具（build123d）。

所有 pcb_*.py 模組共用的顏色常數、幾何輔助、GLB 匯出。
"""
from __future__ import annotations

import os
from typing import List, Tuple

import build123d as bd

# ── 顏色定義 ───────────────────────────────────────────────
PCB_BLUE     = bd.Color(0.05, 0.20, 0.55)
PCB_GREEN    = bd.Color(0.00, 0.40, 0.15)
PCB_TEAL     = bd.Color(0.00, 0.33, 0.42)
PCB_RED      = bd.Color(0.55, 0.05, 0.05)
PCB_BLACK    = bd.Color(0.08, 0.08, 0.10)
METAL        = bd.Color(0.78, 0.78, 0.82)
METAL_DARK   = bd.Color(0.45, 0.45, 0.50)
BLACK        = bd.Color(0.10, 0.10, 0.10)
IC_DARK      = bd.Color(0.12, 0.12, 0.14)
PIN_GOLD     = bd.Color(0.85, 0.70, 0.15)
LED_GREEN    = bd.Color(0.10, 0.85, 0.10)
LED_RED      = bd.Color(0.85, 0.10, 0.10)
LED_BLUE     = bd.Color(0.10, 0.30, 0.90)
LED_YELLOW   = bd.Color(0.90, 0.80, 0.10)
WHITE        = bd.Color(1.00, 1.00, 1.00)
CRYSTAL      = bd.Color(0.78, 0.78, 0.75)
RELAY_BLUE   = bd.Color(0.20, 0.35, 0.65)
DOME_WHITE   = bd.Color(0.92, 0.92, 0.90)
ACRYLIC      = bd.Color(0.70, 0.85, 0.95)
USB_SILVER   = bd.Color(0.82, 0.82, 0.85)
DISPLAY_DARK = bd.Color(0.05, 0.05, 0.06)
DISPLAY_GRAY = bd.Color(0.75, 0.78, 0.72)
GOLD_TRACE   = bd.Color(0.85, 0.75, 0.25)
BROWN        = bd.Color(0.30, 0.18, 0.08)
TRIMPOT_BLUE = bd.Color(0.15, 0.30, 0.70)
RUBBER_BLACK = bd.Color(0.05, 0.05, 0.05)
SHIELD_TIN   = bd.Color(0.70, 0.70, 0.72)
CONNECTOR_WHT = bd.Color(0.90, 0.90, 0.88)


# ── 幾何輔助 ───────────────────────────────────────────────
def box(cx, cy, cz, dx, dy, dz) -> bd.Solid:
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Box(dx, dy, dz)
    return bp.part


def cyl(cx, cy, cz, r, h) -> bd.Solid:
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Cylinder(r, h)
    return bp.part


def add(parts: list, solid: bd.Solid, color: bd.Color, label: str):
    solid.color = color
    solid.label = label
    parts.append(solid)


def make_pcb_board(length, width, thickness, color, label="PCB",
                   holes=None) -> bd.Solid:
    """建立 PCB 基板（含螺絲孔）。"""
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((0, 0, thickness / 2))):
            bd.Box(length, width, thickness)
        if holes:
            for hx, hy, hr in holes:
                with bd.Locations(bd.Location((hx, hy, thickness / 2))):
                    bd.Cylinder(hr, thickness + 0.2, mode=bd.Mode.SUBTRACT)
    s = bp.part
    s.color = color
    s.label = label
    return s


def add_pin_header(parts, pz, pins_xy, group, pitch=2.54,
                   plastic_h=8.5, is_male=False):
    """添加排針/排母。"""
    if not pins_xy:
        return
    xs = [p[0] for p in pins_xy]
    ys = [p[1] for p in pins_xy]
    span_x = max(xs) - min(xs) + pitch
    span_y = max(ys) - min(ys) + pitch
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    h = plastic_h if not is_male else 2.54
    add(parts, box(cx, cy, pz + h / 2, span_x, span_y, h),
        BLACK, f"Header_{group}")
    pin_h = 6.0 if is_male else 4.0
    for px, py in pins_xy:
        add(parts, cyl(px, py, pz + pin_h / 2, 0.32, pin_h),
            PIN_GOLD, f"Pin_{group}")


def add_smd_ic(parts, cx, cy, pz, dx, dy, dz, label="IC"):
    add(parts, box(cx, cy, pz + dz / 2, dx, dy, dz), IC_DARK, label)
    add(parts, cyl(cx - dx / 2 + 0.6, cy + dy / 2 - 0.6,
                   pz + dz + 0.02, 0.25, 0.04), WHITE, f"{label}_Pin1")


def add_trimpot(parts, cx, cy, pz, label="TrimPot"):
    add(parts, box(cx, cy, pz + 1.5, 3.0, 3.0, 3.0), TRIMPOT_BLUE, label)
    add(parts, cyl(cx, cy, pz + 3.2, 0.6, 0.4), WHITE, f"{label}_Slot")


def add_led(parts, cx, cy, pz, color, label="LED"):
    add(parts, box(cx, cy, pz + 0.4, 1.6, 0.8, 0.8), color, label)


# ── 真實外型細節 helper（box-primitive → 挖孔/缺口/圓角；錨定 SSOT 座標）──
def box_holes(cx, cy, cz, dx, dy, dz, holes, hole=1.6, depth=6.0) -> bd.Solid:
    """方塊 + 由頂面往下挖每 pin 方孔（排針受孔）。holes: [(px,py),...] 絕對座標。"""
    top = cz + dz / 2
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Box(dx, dy, dz)
        for px, py in holes:
            with bd.Locations(bd.Location((px, py, top - depth / 2 + 0.01))):
                bd.Box(hole, hole, depth, mode=bd.Mode.SUBTRACT)
    return bp.part


def box_port(cx, cy, cz, dx, dy, dz, port_w, port_h, port_depth, dz_off=0.0) -> bd.Solid:
    """方塊殼 + 由 -X 面挖出插口開孔（USB-B / 連接器埠）。"""
    face_x = cx - dx / 2
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Box(dx, dy, dz)
        with bd.Locations(bd.Location((face_x + port_depth / 2 - 0.01, cy, cz + dz_off))):
            bd.Box(port_depth, port_w, port_h, mode=bd.Mode.SUBTRACT)
    return bp.part


def tube_x(cx, cy, cz, r_out, r_in, length) -> bd.Solid:
    """沿 X 軸的中空圓柱（DC 桶座：外圓柱 - 內孔）。"""
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz), (0, 90, 0))):
            bd.Cylinder(r_out, length)
            bd.Cylinder(r_in, length + 0.2, mode=bd.Mode.SUBTRACT)
    return bp.part


def notched_box(cx, cy, cz, dx, dy, dz, notch_r) -> bd.Solid:
    """方塊 + -X 端中央半圓缺口（DIP IC pin1 缺口）。"""
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Box(dx, dy, dz)
        with bd.Locations(bd.Location((cx - dx / 2, cy, cz))):
            bd.Cylinder(notch_r, dz + 0.2, mode=bd.Mode.SUBTRACT)
    return bp.part


def rounded_can(cx, cy, z_bottom, l, w, h, radius) -> bd.Solid:
    """圓角矩形截面拉伸（HC-49 晶振金屬罐）。"""
    with bd.BuildPart() as bp:
        with bd.BuildSketch(bd.Plane((cx, cy, z_bottom))):
            bd.RectangleRounded(l, w, radius)
        bd.extrude(amount=h)
    return bp.part


# ── GLB 匯出 ──────────────────────────────────────────────
def export_glb(compound: bd.Compound, path: str) -> bool:
    try:
        import trimesh
        import numpy as np
    except ImportError:
        return False

    import logging
    log = logging.getLogger(__name__)

    meshes: list = []
    errors: list[str] = []
    color_set: set[tuple] = set()
    n_teal = 0
    total = len(compound.children)

    for i, child in enumerate(compound.children):
        label = getattr(child, 'label', f'child_{i}')
        try:
            verts, faces = child.tessellate(tolerance=0.05)
            # RF1: build123d Z-up → glTF Y-up convention. (x,y,z) → (x, z, -y)
            verts_np = np.array([(v.X, v.Z, -v.Y) for v in verts],
                                dtype=np.float64)
            faces_np = np.array(faces, dtype=np.int64)
            if len(verts_np) == 0 or len(faces_np) == 0:
                continue
            m = trimesh.Trimesh(vertices=verts_np, faces=faces_np,
                                process=False)
            _ = m.vertex_normals
            c = child.color
            if c:
                cv = list(c)
                rgba = [int(cv[0]*255), int(cv[1]*255), int(cv[2]*255), 255]
            else:
                rgba = [0, 84, 107, 255]
                n_teal += 1
            color_set.add(tuple(rgba[:3]))
            pbr = trimesh.visual.material.PBRMaterial(
                baseColorFactor=[rgba[0] / 255.0, rgba[1] / 255.0,
                                 rgba[2] / 255.0, 1.0])
            m.visual = trimesh.visual.TextureVisuals(material=pbr)
            meshes.append(m)
        except Exception as exc:
            errors.append(f'{label}: {exc}')

    if n_teal:
        # No-Silent-Fallback: a child with no assigned color is a modeling bug.
        # The teal fallback masks lost per-component coloring — fail loudly.
        raise RuntimeError(
            f"GLB export integrity failure: {n_teal} child(ren) had color=None "
            f"(would silently get teal fallback rgba [0,84,107]). "
            f"Every component must have an explicit color."
        )
    if len(color_set) < 3 and len(meshes) > 10:
        # A board with >10 meshes but <3 unique colors rendered nearly monochrome
        # → per-component coloring was lost. This is an integrity violation, not a warning.
        raise RuntimeError(
            f"GLB export integrity failure: low color diversity "
            f"({len(color_set)} unique color(s) across {len(meshes)} meshes). "
            f"Per-component coloring appears to have been lost."
        )

    if errors:
        raise RuntimeError(
            f"GLB export incomplete: {len(errors)}/{total} mesh(es) failed to tessellate. "
            f"First error: {errors[0]}"
        )

    if not meshes:
        return False
    scene = trimesh.Scene(meshes)
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    scene.export(path, file_type='glb')
    return True


def export_pcb(compound: bd.Compound, output_dir: str, label: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    glb_path = os.path.join(output_dir, "pcb_body.glb")
    if export_glb(compound, glb_path):
        print(f"  [pcb] {label} GLB → {glb_path}")
        stl_path = os.path.join(output_dir, "pcb_body.stl")
        bd.export_stl(compound, stl_path, tolerance=0.05)
        return glb_path
    stl_path = os.path.join(output_dir, "pcb_body.stl")
    bd.export_stl(compound, stl_path, tolerance=0.05)
    print(f"  [pcb] {label} STL → {stl_path}")
    return stl_path
