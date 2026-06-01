"""Phase C 高品質 3D 渲染（pyvista, off-screen）。

對 phase_c_arduino_shell.py 產出的 Arduino-Uno.stl 做：
  1. 4 個視角靜態圖（isometric / front-left / right / top）
  2. 半剖視圖（看內部結構）

採用 Verification Spine：
  - 渲染前：L0 check_mesh gate（STL 沒生出/退化 → 不硬畫，直接 FAIL）
  - 渲染後：L0 check_png gate（每張圖必須非空白，否則 FAIL）
  - 標題使用實際 mesh 數據，不再 hardcode triangle 數。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # CP950 終端安全

# 必須在 import pyvista 前設定
os.environ['PYVISTA_OFF_SCREEN'] = 'true'

import numpy as np
import pyvista as pv
from pathlib import Path

from lib.verification import check_mesh, check_png, Verdict, VerificationReport

pv.OFF_SCREEN = True
pv.set_plot_theme('document')   # white background

STL = Path('output/phase_c_verify/Arduino-Uno.stl')
OUT = Path('output/phase_c_verify')

if not STL.exists():
    print(f"[ERROR] STL not found: {STL}")
    print("  This script expects output from phase_c shell generator.")
    print("  Run the phase_c build first, or pass the correct STL path.")
    sys.exit(1)


def _center_and_radius(mesh, scale: float = 1.6):
    """Return (cx, cy, cz, radius) for camera positioning from mesh bounds."""
    b = mesh.bounds
    cx = (b[0] + b[1]) / 2
    cy = (b[2] + b[3]) / 2
    cz = (b[4] + b[5]) / 2
    radius = max(b[1] - b[0], b[3] - b[2], b[5] - b[4]) * scale
    return cx, cy, cz, radius


def main() -> int:
    # ── 渲染前 gate：STL 必須是有效 mesh ──────────────────────
    pre = check_mesh(str(STL), name='Arduino-Uno.stl(pre-render)')
    if pre.verdict == Verdict.FAIL:
        print(pre.render_text())
        print('\n[FAIL] STL invalid, skip render.')
        return 1

    mesh = pv.read(str(STL))
    n_tris = mesh.n_cells
    print(f'Loaded: {mesh.n_points} pts, {n_tris} cells')
    print(f'Bounds: {mesh.bounds}')

    produced: list[str] = []   # 待 L0 驗證的 PNG

    views = [
        dict(name='1_isometric', azim=-45, elev=25,
             label='Isometric — corner view'),
        dict(name='2_left_side', azim=180, elev=10,
             label='Left Side — USB-B (large stadium) + DC-Jack (circle)'),
        dict(name='3_top',       azim=0,   elev=90,
             label='Top View — 5 Header cutouts (Power/Analog/D0-7/D8-SCL/ICSP)'),
        dict(name='4_back',      azim=0,   elev=10,
             label='Back / Right Side — solid wall (no cutout)'),
    ]

    for v in views:
        p = pv.Plotter(off_screen=True, window_size=(1280, 960))
        p.add_mesh(mesh, color='#5d8db5', show_edges=True,
                   edge_color='#1a3a5c', line_width=0.3,
                   specular=0.4, specular_power=20,
                   diffuse=0.7, ambient=0.3)
        cx, cy, cz, radius = _center_and_radius(mesh, scale=1.6)
        az = np.deg2rad(v['azim'])
        el = np.deg2rad(v['elev'])
        cam_x = cx + radius * np.cos(el) * np.cos(az)
        cam_y = cy + radius * np.cos(el) * np.sin(az)
        cam_z = cz + radius * np.sin(el)
        p.camera_position = [(cam_x, cam_y, cam_z), (cx, cy, cz), (0, 0, 1)]
        p.add_axes(line_width=2, labels_off=False)
        p.add_text(v['label'], position='upper_left', font_size=12, color='black')

        out = OUT / f'shell_view_{v["name"]}.png'
        p.screenshot(str(out), transparent_background=False)
        p.close()
        produced.append(str(out))
        print(f'  saved: {out}')

    # ── 組合 4 視角為一張對照圖（標題用實際 mesh 數據）──────────
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg

    # watertight 用 trimesh 實際計算，不 hardcode
    try:
        import trimesh
        _tm = trimesh.load(str(STL), force='mesh')
        wt = bool(_tm.is_watertight)
    except Exception:  # noqa: BLE001
        wt = None

    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig.suptitle(f'Arduino Uno R3 — build123d Shell '
                 f'({n_tris:,} triangles, watertight={wt})',
                 fontsize=16, fontweight='bold')
    for ax, v in zip(axes.ravel(), views):
        img = mpimg.imread(str(OUT / f'shell_view_{v["name"]}.png'))
        ax.imshow(img)
        ax.set_title(v['label'], fontsize=12)
        ax.axis('off')
    plt.tight_layout()
    combined = OUT / 'Arduino-Uno_3d_pyvista.png'
    fig.savefig(str(combined), dpi=120, bbox_inches='tight')
    plt.close(fig)
    produced.append(str(combined))
    print(f'\nCombined 4-view: {combined}')

    # ── 半剖視圖 ────────────────────────────────────────────
    print('\n--- Cutaway view (X<0 half) ---')
    clipped = mesh.clip(normal=[1, 0, 0], origin=[0, 0, 0], invert=False)
    p = pv.Plotter(off_screen=True, window_size=(1600, 1000))
    p.add_mesh(clipped, color='#7da8c9', show_edges=True,
               edge_color='#1a3a5c', line_width=0.3, specular=0.5, diffuse=0.7)
    inner_face = clipped.copy()
    p.add_mesh(inner_face.extract_surface(), color='#c97d7d', opacity=0.4,
               show_edges=False)
    cx, cy, cz, radius = _center_and_radius(mesh, scale=1.5)
    p.camera_position = [
        (cx + radius * 0.5, cy + radius * 0.7, cz + radius * 0.6),
        (cx, cy, cz), (0, 0, 1),
    ]
    p.add_text('Cutaway (X>0 half) — Inner Cavity Visible',
               position='upper_left', font_size=14, color='black')
    p.add_axes(line_width=2)
    cutaway = OUT / 'Arduino-Uno_cutaway.png'
    p.screenshot(str(cutaway), transparent_background=False)
    p.close()
    produced.append(str(cutaway))
    print(f'  saved: {cutaway}')

    # ── 渲染後 gate：每張 PNG 必須非空白 ──────────────────────
    print('\n=== 產出圖片 L0 驗證 ===')
    reports = [check_png(pth) for pth in produced]
    for r in reports:
        print(r.render_text())
    n_fail = sum(1 for r in reports if r.verdict == Verdict.FAIL)
    if n_fail:
        print(f'\n[FAIL] {n_fail}/{len(reports)} images did not pass (blank/corrupt).')
        return 1
    print(f'\n[OK] All {len(reports)} images passed L0 verification.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
