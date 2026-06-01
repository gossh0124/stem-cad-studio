"""lib/cad/tessellation.py — STL/STEP 匯出高密度 tessellation。

build123d 預設 tolerance=0.001 → 約 100~200 tris（小細節遺失）
高密度模式 tolerance=0.05 + angular=0.05 → 5000+ tris（cutout 清晰可見）
"""
from __future__ import annotations
from pathlib import Path
import struct


def export_stl_high_density(
    part,
    file_path: str | Path,
    tolerance: float = 0.05,
    angular_tolerance: float = 0.1,
) -> int:
    """高密度 STL 匯出。回傳三角形數。"""
    import build123d as bd
    file_path = str(file_path)
    bd.export_stl(part, file_path,
                  tolerance=tolerance,
                  angular_tolerance=angular_tolerance,
                  ascii_format=False)
    return _read_stl_tri_count(file_path)


def export_step(part, file_path: str | Path) -> None:
    """STEP B-rep 匯出（保留精確曲面）。"""
    import build123d as bd
    bd.export_step(part, str(file_path))


def _read_stl_tri_count(path: str) -> int:
    """讀 binary STL header 取三角形數。"""
    with open(path, 'rb') as f:
        f.read(80)
        return struct.unpack('<I', f.read(4))[0]
