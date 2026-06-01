"""方案 A — Arduino Uno R3 兩件式殼體（base + lid + snap-fit）。

輸出 output/phase_a_two_piece/：
  Arduino-Uno_base.stl/.step
  Arduino-Uno_lid.stl/.step
  base_view.png / lid_view.png
  assembly_closed.png    # base + lid 已組裝
  assembly_exploded.png  # 爆炸圖（lid 抬高顯示對位）
  assembly_cutaway.png   # 半剖視圖
"""
from __future__ import annotations
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ['PYVISTA_OFF_SCREEN'] = 'true'

from lib.pcb import ARDUINO_UNO_R3
from lib.cad import build_pcb_two_piece, export_step, export_stl_high_density

OUT = Path('output/phase_a_two_piece')
OUT.mkdir(parents=True, exist_ok=True)

print('=== Phase A — Two-Piece Arduino Uno R3 Enclosure ===')
print(f'PCB: {ARDUINO_UNO_R3.length} × {ARDUINO_UNO_R3.width} × {ARDUINO_UNO_R3.pcb_thickness}mm')

base_part, lid_part, spec = build_pcb_two_piece(ARDUINO_UNO_R3)

print(f'\n--- Spec ---')
print(f'Outer:    {spec.outer_l:.2f} × {spec.outer_w:.2f}mm')
print(f'Base:     height {spec.base_h:.2f}mm')
print(f'Lid:      thickness {spec.lid_h:.2f}mm')
print(f'Total H:  {spec.base_h + spec.lid_h:.2f}mm (assembled)')
print(f'Standoffs:    {spec.standoff_count} × {spec.standoff_height}mm')
print(f'Side cutouts: {spec.side_cutout_count} (USB-B + DC-Jack)')
print(f'Lid cutouts:  {spec.lid_cutout_count} (5 header groups)')
print(f'Snap arms:    {spec.snap_count}')
print(f'Snap params:  arm {spec.snap_arm_w}×{spec.snap_arm_t}×{spec.snap_arm_h} / lip {spec.snap_lip_d}d×{spec.snap_lip_h}h')

# Export
print('\n--- Exporting STEP/STL ---')
files = []
for name, part in [('base', base_part), ('lid', lid_part)]:
    step = OUT / f'Arduino-Uno_{name}.step'
    stl = OUT / f'Arduino-Uno_{name}.stl'
    export_step(part, step)
    tri = export_stl_high_density(part, stl, tolerance=0.05, angular_tolerance=0.1)
    print(f'  {name}: STEP {step.stat().st_size:,}b, STL {stl.stat().st_size:,}b ({tri:,} tris)')
    files.append((name, str(stl)))

# ── pyvista renders ────────────────────────────────────────
import numpy as np
import pyvista as pv
pv.OFF_SCREEN = True
pv.set_plot_theme('document')

base_mesh = pv.read(str(OUT / 'Arduino-Uno_base.stl'))
lid_mesh  = pv.read(str(OUT / 'Arduino-Uno_lid.stl'))


def render(meshes_with_offset, view_name, label, camera_offset=(1.0, -1.2, 0.8)):
    """meshes_with_offset = [(mesh, color, opacity, translate_z), ...]"""
    p = pv.Plotter(off_screen=True, window_size=(1600, 1100))
    pv.global_theme.allow_empty_mesh = True

    all_bounds = []
    for mesh, color, opacity, dz, edges in meshes_with_offset:
        m = mesh.copy()
        m.translate([0, 0, dz], inplace=True)
        p.add_mesh(m, color=color, opacity=opacity,
                   show_edges=edges, edge_color='#1a3a5c', line_width=0.3,
                   specular=0.4, specular_power=15)
        all_bounds.append(m.bounds)

    bx = np.array(all_bounds)
    cx = (bx[:, 0].min() + bx[:, 1].max()) / 2
    cy = (bx[:, 2].min() + bx[:, 3].max()) / 2
    cz = (bx[:, 4].min() + bx[:, 5].max()) / 2
    rad = max(bx[:, 1].max() - bx[:, 0].min(),
              bx[:, 3].max() - bx[:, 2].min(),
              bx[:, 5].max() - bx[:, 4].min()) * 1.6

    p.camera_position = [
        (cx + rad * camera_offset[0],
         cy + rad * camera_offset[1],
         cz + rad * camera_offset[2]),
        (cx, cy, cz),
        (0, 0, 1),
    ]
    p.add_axes(line_width=2)
    p.add_text(label, position='upper_left', font_size=14, color='black')
    out_path = OUT / f'{view_name}.png'
    p.screenshot(str(out_path), transparent_background=False)
    p.close()
    print(f'  saved: {out_path}')


print('\n--- Renders ---')
# 1. Base alone (從上方斜看，可見 standoffs + 凹槽)
render([(base_mesh, '#5d8db5', 1.0, 0, True)],
       'base_view',
       'Base — standoffs + side cutouts + snap recesses',
       camera_offset=(0.6, -1.0, 0.7))

# 2. Lid alone (從下方斜看，可見 snap arms + header cutouts)
render([(lid_mesh, '#a5856b', 1.0, 0, True)],
       'lid_view',
       'Lid — header cutouts (top) + snap arms (bottom)',
       camera_offset=(0.4, -1.0, -0.5))

# 3. Closed assembly (lid 蓋在 base 上)
assembly_dz = (spec.base_h + spec.lid_h) / 2
render([
    (base_mesh, '#5d8db5', 1.0, 0, True),
    (lid_mesh,  '#a5856b', 0.85, assembly_dz, True),
],
       'assembly_closed',
       'Assembled — lid snapped on base',
       camera_offset=(0.7, -0.9, 0.7))

# 4. Exploded (lid 抬高 +20mm 顯示對位)
render([
    (base_mesh, '#5d8db5', 1.0, 0, True),
    (lid_mesh,  '#a5856b', 1.0, assembly_dz + 20, True),
],
       'assembly_exploded',
       'Exploded view — lid 20mm above base for alignment check',
       camera_offset=(0.7, -0.9, 0.6))

# 5. Cutaway (Y>0 半切，可見內腔結構)
print('\n--- Cutaway ---')
base_clipped = base_mesh.clip(normal=[0, 1, 0], origin=[0, 0, 0], invert=False)
lid_clipped  = lid_mesh.copy()
lid_clipped.translate([0, 0, assembly_dz], inplace=True)
lid_clipped  = lid_clipped.clip(normal=[0, 1, 0], origin=[0, 0, 0], invert=False)

p = pv.Plotter(off_screen=True, window_size=(1600, 1100))
p.add_mesh(base_clipped, color='#5d8db5', opacity=0.7,
           show_edges=True, edge_color='#1a3a5c', line_width=0.3)
p.add_mesh(lid_clipped, color='#a5856b', opacity=0.7,
           show_edges=True, edge_color='#3a2818', line_width=0.3)
bx = base_mesh.bounds
cx, cy, cz = (bx[0]+bx[1])/2, (bx[2]+bx[3])/2, (bx[4]+bx[5])/2
rad = max(bx[1]-bx[0], bx[3]-bx[2], bx[5]-bx[4]) * 1.7
p.camera_position = [
    (cx + rad*0.5, cy - rad*0.9, cz + rad*0.5),
    (cx, cy, cz), (0, 0, 1)]
p.add_axes(line_width=2)
p.add_text('Cutaway (Y>0 half) — base+lid+snap-fit interface',
           position='upper_left', font_size=14, color='black')
p.screenshot(str(OUT / 'assembly_cutaway.png'), transparent_background=False)
p.close()
print(f'  saved: {OUT / "assembly_cutaway.png"}')

# ── 4 視角合併圖 ────────────────────────────────────────────
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

fig, axes = plt.subplots(2, 2, figsize=(20, 15))
fig.suptitle(f'Arduino Uno R3 — Two-Piece Enclosure (build123d, snap-fit)',
             fontsize=16, fontweight='bold')
imgs = [
    (OUT / 'base_view.png', 'Base'),
    (OUT / 'lid_view.png', 'Lid (flipped to show snap arms)'),
    (OUT / 'assembly_exploded.png', 'Exploded (lid +20mm)'),
    (OUT / 'assembly_cutaway.png', 'Cutaway'),
]
for ax, (path, ttl) in zip(axes.ravel(), imgs):
    ax.imshow(mpimg.imread(str(path)))
    ax.set_title(ttl, fontsize=12)
    ax.axis('off')
plt.tight_layout()
fig.savefig(str(OUT / 'Arduino-Uno_two_piece_overview.png'),
            dpi=120, bbox_inches='tight')
plt.close(fig)
print(f'\nOverview: {OUT / "Arduino-Uno_two_piece_overview.png"}')

print('\n=== Phase A Complete ===')
for f in sorted(OUT.iterdir()):
    print(f'  {f.name}: {f.stat().st_size:,} bytes')
