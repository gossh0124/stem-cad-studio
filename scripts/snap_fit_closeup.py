"""Snap-fit 區域特寫渲染 — 顯示 lip / recess / wall 三者重疊狀態。"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['PYVISTA_OFF_SCREEN'] = 'true'

import numpy as np
import pyvista as pv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

pv.OFF_SCREEN = True
pv.set_plot_theme('document')

# 載入 base + lid，取出右上角的 snap-fit 區域
_BASE_STL = Path('output/phase_a_two_piece/Arduino-Uno_base.stl')
_LID_STL  = Path('output/phase_a_two_piece/Arduino-Uno_lid.stl')
for _p in (_BASE_STL, _LID_STL):
    if not _p.exists():
        print(f"[ERROR] STL not found: {_p}")
        print("  This script expects output from phase_a_two_piece build.")
        print("  Run the two-piece shell generator first, or update the path.")
        sys.exit(1)

base_mesh = pv.read(str(_BASE_STL))
lid_mesh = pv.read(str(_LID_STL))
lid_mesh.translate([0, 0, 12.05], inplace=True)   # 組裝後 lid 抬高至 base 上方

# Crop 到 +X 邊 +Y 邊的 snap arm 位置（單次 clip_box vs 6 次 clip）
crop_bounds = [18, 30, 28, 35, 0, 13]   # [xmin xmax ymin ymax zmin zmax]
base_crop = base_mesh.clip_box(crop_bounds, invert=False)
lid_crop  = lid_mesh.clip_box(crop_bounds, invert=False)
crop_x_min, crop_x_max, crop_y_min, crop_y_max, crop_z_min, crop_z_max = crop_bounds

p = pv.Plotter(off_screen=True, window_size=(1600, 1200))
pv.global_theme.allow_empty_mesh = True
p.add_mesh(base_crop, color='#5d8db5', opacity=1.0, show_edges=True,
           edge_color='#1a3a5c', line_width=0.6, label='Base')
p.add_mesh(lid_crop,  color='#a5856b', opacity=0.85, show_edges=True,
           edge_color='#3a2818', line_width=0.6, label='Lid + arm')

cx = (crop_x_min + crop_x_max) / 2
cy = (crop_y_min + crop_y_max) / 2
cz = (crop_z_min + crop_z_max) / 2
rad = max(crop_x_max - crop_x_min, crop_y_max - crop_y_min,
          crop_z_max - crop_z_min) * 1.5
p.camera_position = [
    (cx + rad * 0.4, cy + rad * 1.1, cz + rad * 0.5),
    (cx, cy, cz - 1),
    (0, 0, 1),
]
p.add_axes(line_width=2)
p.add_text('Snap-Fit Closeup (+X +Y corner): Base wall + recess + lid arm + lip',
           position='upper_left', font_size=14, color='black')
p.screenshot('output/phase_a_two_piece/snap_fit_closeup.png',
             transparent_background=False)
p.close()
print('saved: output/phase_a_two_piece/snap_fit_closeup.png')

# ── 平面幾何示意圖（YZ cross-section）─────────────────
fig, ax = plt.subplots(figsize=(14, 10))

# Base 外壁（assembly 座標）
wall_y_outer = 31.47
wall_y_inner = 31.47 - 2.0   # wall thickness 2mm
base_top_z   = 11.05
base_bot_z   = 0.0
ax.add_patch(mpatches.Rectangle((wall_y_inner, base_bot_z),
             wall_y_outer - wall_y_inner, base_top_z - base_bot_z,
             facecolor='#5d8db5', edgecolor='#1a3a5c', label='Base wall (2.0mm)'))

# Recess（在外壁挖空）
recess_y_min, recess_y_max = 30.27, 31.47
recess_z_min, recess_z_max = 5.15, 6.55
ax.add_patch(mpatches.Rectangle((recess_y_min, recess_z_min),
             recess_y_max - recess_y_min, recess_z_max - recess_z_min,
             facecolor='white', edgecolor='red', linewidth=2,
             linestyle='--', label='Recess (1.2 deep × 1.4 tall)'))

# Lid 平板
lid_y_min = -50  # extend left for visualization
lid_y_max = 35
lid_z_min = 11.05
lid_z_max = 13.05
ax.add_patch(mpatches.Rectangle((lid_y_min, lid_z_min),
             lid_y_max - lid_y_min, lid_z_max - lid_z_min,
             facecolor='#a5856b', edgecolor='#3a2818', alpha=0.6, label='Lid plate'))

# Snap arm
arm_y_min, arm_y_max = 31.97, 33.47
arm_z_min, arm_z_max = 5.05, 11.05
ax.add_patch(mpatches.Rectangle((arm_y_min, arm_z_min),
             arm_y_max - arm_y_min, arm_z_max - arm_z_min,
             facecolor='#d4a574', edgecolor='#3a2818', label='Snap arm (1.5×6mm)'))

# Lip box (current, buggy: 2.3mm wide)
lip_y_min, lip_y_max = 30.42, 32.72
lip_z_min, lip_z_max = 5.35, 6.35
ax.add_patch(mpatches.Rectangle((lip_y_min, lip_z_min),
             lip_y_max - lip_y_min, lip_z_max - lip_z_min,
             facecolor='#e74c3c', edgecolor='black', linewidth=1.5,
             alpha=0.7, label='Lip (current: 2.3mm wide ⚠️)'))

# 標註
ax.annotate('', xy=(arm_y_min, 11.5), xytext=(arm_y_max, 11.5),
            arrowprops=dict(arrowstyle='<->', color='gray'))
ax.text((arm_y_min+arm_y_max)/2, 11.7, '1.5mm arm',
        ha='center', fontsize=8, color='gray')

ax.annotate('', xy=(wall_y_outer, 12.5), xytext=(arm_y_min, 12.5),
            arrowprops=dict(arrowstyle='<->', color='blue'))
ax.text((wall_y_outer+arm_y_min)/2, 12.7, f'gap 0.5mm',
        ha='center', fontsize=8, color='blue')

# Lip 探出標註
ax.annotate('', xy=(wall_y_outer, 4.5), xytext=(lip_y_max, 4.5),
            arrowprops=dict(arrowstyle='<->', color='red'))
ax.text((wall_y_outer+lip_y_max)/2, 4.2,
        'lip 探出 1.25mm（外壁外）⚠️',
        ha='center', fontsize=9, color='red', fontweight='bold')

# Lip 進入 recess 的部分
ax.annotate('', xy=(lip_y_min, 7.0), xytext=(wall_y_outer, 7.0),
            arrowprops=dict(arrowstyle='<->', color='green'))
ax.text((lip_y_min+wall_y_outer)/2, 7.2,
        'lip 進入 recess 1.05mm ✅',
        ha='center', fontsize=9, color='green', fontweight='bold')

# Pin header indicator
header_z = -2.45 + 11.5
ax.axhline(header_z, color='purple', linestyle=':', label=f'Pin header top z={header_z:.2f}')
ax.axhline(11.05, color='gray', linestyle=':', alpha=0.5)
ax.text(15, 11.2, f'Lid 底 z={11.05}', fontsize=8, color='gray')
ax.text(15, header_z + 0.2, f'Header 頂 z={header_z:.2f} (差 2mm)', fontsize=8, color='purple')

ax.set_xlim(15, 36)
ax.set_ylim(-1, 14)
ax.set_aspect('equal')
ax.set_xlabel('Y (mm)')
ax.set_ylabel('Z (mm)')
ax.set_title('Snap-Fit 截面分析 (YZ plane @ X=23.45) — 顯示 lip 寬度 bug + 探出外壁',
             fontsize=12, fontweight='bold')
ax.legend(loc='upper right', fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
fig.savefig('output/phase_a_two_piece/snap_fit_geometry_diagram.png',
            dpi=150, bbox_inches='tight')
plt.close(fig)
print('saved: output/phase_a_two_piece/snap_fit_geometry_diagram.png')
