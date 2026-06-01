"""Phase C 驗證 — 用 build123d 從 PCBSpec 重建 Arduino Uno 殼體。

輸出（output/phase_c_verify/）：
  Arduino-Uno.step          — STEP B-rep
  Arduino-Uno.stl           — 高密度 STL（5000+ tris）
  Arduino-Uno_3d.png        — 3D 多視角渲染
  Arduino-Uno_2d_views.png  — 五面視圖 + 切口幾何標註
"""
from __future__ import annotations
import sys, os, struct
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.pcb import ARDUINO_UNO_R3
from lib.cad import build_pcb_enclosure, export_step, export_stl_high_density

OUT_DIR = Path('output/phase_c_verify')
OUT_DIR.mkdir(parents=True, exist_ok=True)

print('=== Phase C: Arduino Uno R3 Shell Build ===')
print(f'PCB: {ARDUINO_UNO_R3.length} × {ARDUINO_UNO_R3.width} × {ARDUINO_UNO_R3.pcb_thickness}mm')
print(f'Sub-components: {len(ARDUINO_UNO_R3.sub_components)}')
print(f'Header groups: {len(ARDUINO_UNO_R3.header_groups)}')

print('\n--- Building enclosure (build123d) ---')
part, encl = build_pcb_enclosure(
    ARDUINO_UNO_R3,
    padding=2.5, wall=2.0, tol=0.3,
    with_lid=True, cutout_clearance=1.0,
)
print(f'Outer: {encl.outer_l:.2f} × {encl.outer_w:.2f} × {encl.outer_h:.2f}mm')
print(f'Inner: {encl.inner_l:.2f} × {encl.inner_w:.2f} × {encl.inner_h:.2f}mm')
print(f'Cutouts: {encl.cutout_count}')
print(f'PCB top Z: {encl.pcb_top_z:.2f}mm')

print('\n--- Exporting STEP ---')
step_path = OUT_DIR / 'Arduino-Uno.step'
export_step(part, step_path)
print(f'STEP: {step_path} ({step_path.stat().st_size:,} bytes)')

print('\n--- Exporting STL (high-density) ---')
stl_path = OUT_DIR / 'Arduino-Uno.stl'
tri_count = export_stl_high_density(part, stl_path,
                                     tolerance=0.05, angular_tolerance=0.1)
print(f'STL: {stl_path} ({stl_path.stat().st_size:,} bytes, {tri_count:,} triangles)')

print('\n--- Generating 3D Render ---')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def read_stl(path):
    with open(path, 'rb') as f:
        f.read(80)
        n = struct.unpack('<I', f.read(4))[0]
        tris = np.zeros((n, 3, 3), dtype=np.float32)
        normals = np.zeros((n, 3), dtype=np.float32)
        for i in range(n):
            normals[i] = struct.unpack('<3f', f.read(12))
            for j in range(3):
                tris[i, j] = struct.unpack('<3f', f.read(12))
            f.read(2)
    return tris, normals


tris, normals = read_stl(str(stl_path))
print(f'Loaded {len(tris)} triangles for 3D rendering')

fig = plt.figure(figsize=(20, 7))
fig.suptitle(f'Arduino Uno R3 — Profile-Aware Shell (build123d, {tri_count} triangles)',
             fontsize=14, fontweight='bold')

views = [
    (25, -55, 'Isometric (View Left+Top)'),
    (10, 175, 'Right Side (USB+DC-Jack opposite)'),
    (88, -90, 'Top (Header Cutouts)'),
]

for i, (elev, azim, title) in enumerate(views):
    ax = fig.add_subplot(1, 3, i + 1, projection='3d')
    # Light source: top-front-left
    light_dir = np.array([-0.5, -0.3, 0.8])
    light_dir /= np.linalg.norm(light_dir)
    intensity = np.clip(np.dot(normals, light_dir), 0.2, 1.0)
    colors = np.zeros((len(tris), 4))
    colors[:, 0] = 0.30 + 0.50 * intensity   # R
    colors[:, 1] = 0.55 + 0.40 * intensity   # G
    colors[:, 2] = 0.85 + 0.10 * intensity   # B
    colors[:, 3] = 1.0
    mesh = Poly3DCollection(tris, alpha=1.0, facecolors=colors,
                             edgecolor='#1a3a5c', linewidth=0.05)
    ax.add_collection3d(mesh)

    xs, ys, zs = tris[:, :, 0], tris[:, :, 1], tris[:, :, 2]
    ax.set_xlim(xs.min() - 2, xs.max() + 2)
    ax.set_ylim(ys.min() - 2, ys.max() + 2)
    ax.set_zlim(zs.min() - 2, zs.max() + 2)
    ax.set_xlabel('X (mm)', fontsize=8)
    ax.set_ylabel('Y (mm)', fontsize=8)
    ax.set_zlabel('Z (mm)', fontsize=8)
    ax.view_init(elev=elev, azim=azim)
    ax.set_title(title, fontsize=10)

plt.tight_layout()
out_3d = OUT_DIR / 'Arduino-Uno_3d.png'
fig.savefig(out_3d, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'3D Render: {out_3d}')

print('\n--- Generating 2D Views (top + side) ---')
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon as MplPolygon

fig, (ax_top, ax_left) = plt.subplots(1, 2, figsize=(20, 8))

# 投影 STL 三角形：取每個三角形的 bbox 在投影面上的範圍
def project_silhouette(tris, axis='top'):
    """簡單投影：取每個三角形的 bbox 在投影面上的範圍。"""
    if axis == 'top':
        return tris[:, :, [0, 1]]
    elif axis == 'left':
        return tris[:, :, [1, 2]]
    return tris


def _add_projection_patches(ax, projected_tris, title, xlabel, ylabel):
    """將 projected_tris 加入 ax，設定範圍/標題/標籤。"""
    for t in projected_tris:
        ax.add_patch(MplPolygon(t, closed=True, facecolor='#9bc4e6',
                                edgecolor='#1a3a5c', linewidth=0.1, alpha=0.6))
    ax.set_xlim(projected_tris[:, :, 0].min() - 2, projected_tris[:, :, 0].max() + 2)
    ax.set_ylim(projected_tris[:, :, 1].min() - 2, projected_tris[:, :, 1].max() + 2)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, ls=':', alpha=0.3)


top_tris = project_silhouette(tris, 'top')
_add_projection_patches(ax_top, top_tris, 'Top View — Header Cutouts', 'X (mm)', 'Y (mm)')

left_tris = project_silhouette(tris, 'left')
_add_projection_patches(ax_left, left_tris, 'Left Side View — USB-B + DC-Jack Cutouts', 'Y (mm)', 'Z (mm)')

plt.tight_layout()
out_2d = OUT_DIR / 'Arduino-Uno_2d_views.png'
fig.savefig(out_2d, dpi=150, bbox_inches='tight')
plt.close(fig)
print(f'2D Views: {out_2d}')

print('\n=== Phase C Complete ===')
print(f'Files in {OUT_DIR}:')
for f in sorted(OUT_DIR.iterdir()):
    print(f'  {f.name}: {f.stat().st_size:,} bytes')
