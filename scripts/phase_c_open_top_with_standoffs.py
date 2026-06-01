"""Phase C+ — 開頂殼 + 4 個 PCB standoffs，驗證 PCB 能實際裝入。

延伸 phase_c_arduino_shell.py：
  - with_lid=False（開頂，方案 C）
  - 加 4 個 standoffs 對位 mounting holes
  - 視覺化模擬 PCB 放入殼內後的對位（mounting hole 中心 vs standoff 中心）
"""
from __future__ import annotations
import sys, os, struct
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.pcb import ARDUINO_UNO_R3, JANALOG_PINS, JDIGITAL_PINS, ICSP_PINS, SUB_COMPONENTS
from lib.cad import build_pcb_enclosure, export_step, export_stl_high_density

OUT_DIR = Path('output/phase_c_assembly')
OUT_DIR.mkdir(parents=True, exist_ok=True)

print('=== Phase C+ : Open-Top Shell with PCB Standoffs ===')

part, encl = build_pcb_enclosure(
    ARDUINO_UNO_R3,
    padding=2.5, wall=2.0, tol=0.3,
    with_lid=False,                # 方案 C：開頂
    cutout_clearance=1.0,
    standoff_height=5.0,           # PCB 底距殼底 5mm
    standoff_outer_d=5.0,          # ⌀5mm 外圓
    standoff_inner_d=2.5,          # ⌀2.5mm 螺絲底孔（M2.5 自攻牙）
)
print(f'Outer: {encl.outer_l:.2f} × {encl.outer_w:.2f} × {encl.outer_h:.2f}mm')
print(f'Inner: {encl.inner_l:.2f} × {encl.inner_w:.2f} × {encl.inner_h:.2f}mm')
print(f'PCB bottom Z: {encl.pcb_bottom_z:.2f}mm  PCB top Z: {encl.pcb_top_z:.2f}mm')
print(f'Standoff: {encl.standoff_count} × {encl.standoff_height}mm')
print(f'Cutouts: {encl.cutout_count}')

step_path = OUT_DIR / 'Arduino-Uno_open_top.step'
stl_path  = OUT_DIR / 'Arduino-Uno_open_top.stl'
export_step(part, step_path)
tri = export_stl_high_density(part, stl_path, tolerance=0.05, angular_tolerance=0.1)
print(f'STEP: {step_path.stat().st_size:,} bytes')
print(f'STL : {stl_path.stat().st_size:,} bytes ({tri:,} tris)')

# ── PCB 對位驗證：standoff 中心 vs mounting hole 中心 ──────────
print('\n=== PCB Mounting Alignment Check ===')
L, W = ARDUINO_UNO_R3.length, ARDUINO_UNO_R3.width
print(f'PCB: {L} × {W} mm')
print(f'{"Hole":4s}  {"PCB 座標":18s}  {"殼體中心座標":24s}  {"應位於":12s}')
print('-' * 70)
for i, h in enumerate(ARDUINO_UNO_R3.mounting_holes, 1):
    sx_encl = h.x - L / 2
    sy_encl = h.y - W / 2
    print(f'{i:4d}  ({h.x:6.2f}, {h.y:6.2f})  ({sx_encl:7.2f}, {sy_encl:7.2f})  ⌀{h.diameter}')

# ── 組裝視覺化 ──────────────────────────────────────────────
import numpy as np
import pyvista as pv
pv.OFF_SCREEN = True
pv.set_plot_theme('document')

shell_mesh = pv.read(str(stl_path))
print(f'\nLoaded shell: {shell_mesh.n_points} pts, {shell_mesh.n_cells} cells')

# 模擬 PCB box + 元件（用 build123d 生成簡易 PCB 模型）
import build123d as bd
with bd.BuildPart() as pcb:
    bd.Box(L, W, ARDUINO_UNO_R3.pcb_thickness)
    # 加 4 個 mounting hole
    for h in ARDUINO_UNO_R3.mounting_holes:
        with bd.Locations((h.x - L/2, h.y - W/2, 0)):
            bd.Cylinder(radius=h.diameter/2, height=ARDUINO_UNO_R3.pcb_thickness + 1,
                        mode=bd.Mode.SUBTRACT)

# 把 PCB 放在 standoff 上方（pcb_bottom_z）
pcb_translated = pcb.part.translate((0, 0, encl.pcb_bottom_z + ARDUINO_UNO_R3.pcb_thickness/2))
pcb_stl_path = OUT_DIR / '_tmp_pcb.stl'
bd.export_stl(pcb_translated, str(pcb_stl_path), tolerance=0.05)
pcb_mesh = pv.read(str(pcb_stl_path))

# 加幾個簡易子元件（USB-B + DC-Jack + ATmega）
sub_meshes = []
for sc in ARDUINO_UNO_R3.sub_components:
    if sc.name not in ('USB-B', 'DC-Jack', 'ATmega328P'):
        continue
    # 在 PCB 上方繪製
    cx_pcb = sc.anchor_x - L/2
    cy_pcb = sc.anchor_y - W/2
    cz = encl.pcb_top_z + sc.body_h/2

    # 旋轉處理
    if sc.rotation in ('R90', 'R270'):
        bx_l, bx_w = sc.body_w, sc.body_l
    else:
        bx_l, bx_w = sc.body_l, sc.body_w

    box = pv.Box(bounds=(
        cx_pcb - bx_l/2, cx_pcb + bx_l/2,
        cy_pcb - bx_w/2, cy_pcb + bx_w/2,
        cz - sc.body_h/2, cz + sc.body_h/2,
    ))
    sub_meshes.append((sc.name, box))

# 渲染：殼體（半透明）+ PCB（綠）+ 元件（彩）
SC_COLOR = {'USB-B': '#e74c3c', 'DC-Jack': '#f39c12', 'ATmega328P': '#34495e'}

p = pv.Plotter(off_screen=True, window_size=(1600, 1100))
p.add_mesh(shell_mesh, color='#7da5c0', opacity=0.35,
           show_edges=True, edge_color='#2c3e50', line_width=0.4)
p.add_mesh(pcb_mesh, color='#27ae60', opacity=0.95,
           show_edges=False)
for name, box in sub_meshes:
    p.add_mesh(box, color=SC_COLOR.get(name, '#95a5a6'),
               opacity=0.85, show_edges=True, edge_color='black', line_width=0.3)
    p.add_point_labels(np.array([[box.center[0], box.center[1], box.center[2] + 1]]),
                        [name], font_size=14, point_size=0,
                        text_color='black', shape=None)

# Camera：isometric
bounds = shell_mesh.bounds
cx = (bounds[0]+bounds[1])/2
cy = (bounds[2]+bounds[3])/2
cz = (bounds[4]+bounds[5])/2
r = max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]) * 1.6
p.camera_position = [(cx + r*0.5, cy - r*0.7, cz + r*0.5),
                      (cx, cy, cz),
                      (0, 0, 1)]
p.add_axes(line_width=2)
p.add_text('Arduino Uno R3 Shell + PCB Assembly Preview',
           position='upper_left', font_size=14, color='black')
p.screenshot(str(OUT_DIR / 'assembly_preview.png'), transparent_background=False)
p.close()
print(f'\nAssembly preview: {OUT_DIR / "assembly_preview.png"}')

# Cutaway view（X>0 half，這樣 USB-B 跟 DC-Jack 都會在保留側可見）
p = pv.Plotter(off_screen=True, window_size=(1600, 1100))
pv.global_theme.allow_empty_mesh = True
clipped_shell = shell_mesh.clip(normal=[1, 0, 0], origin=[0, 0, 0], invert=False)
p.add_mesh(clipped_shell, color='#7da5c0', opacity=0.6,
           show_edges=True, edge_color='#2c3e50', line_width=0.3)
clipped_pcb = pcb_mesh.clip(normal=[1, 0, 0], origin=[0, 0, 0], invert=False)
p.add_mesh(clipped_pcb, color='#27ae60', opacity=0.95)
for name, box in sub_meshes:
    clipped_box = box.clip(normal=[1, 0, 0], origin=[0, 0, 0], invert=False)
    p.add_mesh(clipped_box, color=SC_COLOR.get(name, '#95a5a6'),
               opacity=0.85, show_edges=True, edge_color='black', line_width=0.3)
p.camera_position = [(cx - r*0.5, cy - r*0.7, cz + r*0.5),
                      (cx, cy, cz), (0, 0, 1)]
p.add_text('Cutaway (X>0 half) — Shell + PCB on Standoffs',
           position='upper_left', font_size=14, color='black')
p.add_axes(line_width=2)
p.screenshot(str(OUT_DIR / 'assembly_cutaway.png'), transparent_background=False)
p.close()
print(f'Cutaway preview: {OUT_DIR / "assembly_cutaway.png"}')

# 清理 tmp
pcb_stl_path.unlink()

print('\n=== Phase C+ Complete ===')
for f in sorted(OUT_DIR.iterdir()):
    print(f'  {f.name}: {f.stat().st_size:,} bytes')
