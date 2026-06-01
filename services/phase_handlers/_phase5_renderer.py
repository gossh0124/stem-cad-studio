"""Multiview PNG rendering helpers for Phase 5.

Extracted from phase5_handler.py to keep files under 500 lines.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

_log = logging.getLogger("cadhllm.phase5")


def render_multiview(
    bottom_stl: Optional[str],
    lid_stl: Optional[str],
    out_dir: Path,
    progress_cb: Optional[Callable[[str], None]],
    bridge: Optional[dict],
    log_fn: Callable,
) -> Dict[str, str]:
    import trimesh  # type: ignore
    import numpy as np

    views: Dict[str, str] = {}
    scene = trimesh.Scene()

    for label, stl_path in [("bottom", bottom_stl), ("lid", lid_stl)]:
        if not stl_path or not Path(stl_path).exists():
            continue
        mesh = trimesh.load(stl_path)
        if isinstance(mesh, trimesh.Trimesh):
            scene.add_geometry(mesh, node_name=label)

    if bridge:
        _load_extra_shells(scene, bridge, progress_cb, log_fn)

    if not scene.is_empty:
        angle_configs = {
            "front":      ([0, -1, 0.3], "Front"),
            "back":       ([0, 1, 0.3],  "Back"),
            "top":        ([0, 0, 1],    "Top"),
            "isometric":  ([1, -1, 0.8], "Isometric"),
            "side_left":  ([1, 0, 0.3],  "Left"),
            "side_right": ([-1, 0, 0.3], "Right"),
        }

        if sys.platform == "win32" or not os.environ.get("DISPLAY"):
            log_fn(progress_cb, "  headless 環境：直接使用 matplotlib 線框圖")
            _render_matplotlib(scene, angle_configs, out_dir, views, progress_cb, log_fn)
        else:
            rendered_any = False
            for view_name, (axis, label) in angle_configs.items():
                png_path = str(out_dir / f"view_{view_name}.png")
                try:
                    sc2 = scene.copy()
                    png = sc2.save_image(
                        resolution=(640, 480),
                        background=[20, 20, 30, 255],
                    )
                    if png:
                        Path(png_path).write_bytes(png)
                        views[view_name] = png_path
                        rendered_any = True
                        log_fn(progress_cb, f"  ✅ {view_name} → {png_path}")
                except Exception as e:
                    log_fn(progress_cb, f"  ⚠️  {view_name} 渲染失敗：{e}")

            if not rendered_any:
                _render_matplotlib(scene, angle_configs, out_dir, views, progress_cb, log_fn)

    return views


def _load_extra_shells(scene, bridge: dict, progress_cb, log_fn: Callable):
    import trimesh  # type: ignore
    import numpy as np

    cad_out = bridge.get("cad_output", {})
    component_shells = cad_out.get("component_shells", [])

    brain_class = None
    for c in bridge.get("components", []):
        if c.get("role") == "Brain":
            brain_class = c.get("type") or c.get("class_name")
            break

    if brain_class:
        repo_root = Path(__file__).resolve().parents[2]
        for ext in ("glb", "stl"):
            pcb_path = repo_root / "shells" / brain_class / f"pcb_body.{ext}"
            if pcb_path.exists():
                try:
                    pcb_mesh = trimesh.load(str(pcb_path))
                    if isinstance(pcb_mesh, trimesh.Scene):
                        for name, geom in pcb_mesh.geometry.items():
                            scene.add_geometry(geom, node_name=f"pcb_{name}")
                    elif isinstance(pcb_mesh, trimesh.Trimesh):
                        pcb_mesh.visual.face_colors = [0, 84, 107, 200]
                        scene.add_geometry(pcb_mesh, node_name="pcb_body")
                    log_fn(progress_cb, f"  📦 PCB body 載入 → {pcb_path.name}")
                    break
                except Exception as e:
                    log_fn(progress_cb, f"  ⚠️ PCB body 載入失敗：{e}")

    for shell in component_shells:
        stl_path = shell.get("stl") or shell.get("base_stl")
        if not stl_path or not Path(stl_path).exists():
            continue
        if shell.get("kind") in ("two_piece", "assembly_two_piece"):
            continue
        try:
            mesh = trimesh.load(stl_path)
            if isinstance(mesh, trimesh.Trimesh):
                mesh.visual.face_colors = [120, 120, 140, 180]
                label = shell.get("label", shell.get("class", "shell"))
                scene.add_geometry(mesh, node_name=f"shell_{label}")
                log_fn(progress_cb, f"  📦 Shell 載入 → {Path(stl_path).name}")
        except Exception as e:
            log_fn(progress_cb, f"  ⚠️ Shell 載入失敗：{e}")


def _render_matplotlib(scene, configs, out_dir, views, progress_cb, log_fn: Callable):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
        import numpy as np

        try:
            import trimesh as _tm
        except ImportError:
            _tm = None

        _TARGET_FACES = 8000

        all_verts = []
        for geom in scene.geometry.values():
            if not (hasattr(geom, "vertices") and hasattr(geom, "faces")):
                continue
            v = np.array(geom.vertices)
            f = np.array(geom.faces)
            if _tm is not None and len(f) > _TARGET_FACES:
                try:
                    decimated = _tm.Trimesh(vertices=v, faces=f)
                    decimated = decimated.simplify_quadratic_decimation(_TARGET_FACES)
                    v = np.array(decimated.vertices)
                    f = np.array(decimated.faces)
                except Exception as _de:
                    _log.debug("mesh decimation failed, keeping original: %s", _de)
            all_verts.append((v, f))

        if not all_verts:
            return

        view_angles = {
            "front":      (20, -60),
            "back":       (20, 120),
            "top":        (90, -90),
            "isometric":  (30, -45),
            "side_left":  (20, 0),
            "side_right": (20, 180),
        }
        for view_name, (elev, azim) in view_angles.items():
            fig = plt.figure(figsize=(6, 4.5), facecolor="#141420")
            ax = fig.add_subplot(111, projection="3d")
            ax.set_facecolor("#141420")
            ax.set_title(view_name.upper(), color="#44aaff", fontsize=10)
            for v, f in all_verts:
                poly = Poly3DCollection(
                    v[f], alpha=0.6,
                    facecolor="#2d6a9f", edgecolor="#4488cc", linewidth=0.3,
                )
                ax.add_collection3d(poly)
                ax.auto_scale_xyz(v[:, 0], v[:, 1], v[:, 2])
            ax.view_init(elev=elev, azim=azim)
            ax.tick_params(colors="#555")
            for pane in (ax.xaxis.pane, ax.yaxis.pane, ax.zaxis.pane):
                pane.fill = False
            png_path = str(out_dir / f"view_{view_name}.png")
            plt.savefig(
                png_path, dpi=100, bbox_inches="tight",
                facecolor=fig.get_facecolor(),
            )
            plt.close(fig)
            views[view_name] = png_path
            log_fn(progress_cb, f"  ✅ {view_name} (matplotlib) → {png_path}")
    except Exception as e:
        _log.warning("matplotlib fallback 失敗：%s", e)
        log_fn(progress_cb, f"  ⚠️  matplotlib fallback 失敗：{e}")
