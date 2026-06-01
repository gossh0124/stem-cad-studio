"""tests/test_tessellation.py -- lib/cad/tessellation.py 單元測試。

build123d 為重量級依賴：geometry export 函式以 importskip 保護。
_read_stl_tri_count 用合成 binary STL 測試，不需 build123d。
"""
from __future__ import annotations

import struct
import tempfile
from pathlib import Path

import pytest

from lib.cad.tessellation import (
    _read_stl_tri_count,
    export_stl_high_density,
    export_step,
)


# ================================================================
# _read_stl_tri_count -- synthetic binary STL
# ================================================================

def _write_synthetic_stl(path: Path, n_tris: int) -> None:
    """Write a minimal binary STL with the given triangle count.

    Binary STL format:
      - 80 bytes header
      - 4 bytes uint32 triangle count
      - each triangle: 12 * 4 bytes (normal + 3 vertices) + 2 bytes attribute
    """
    with open(path, "wb") as f:
        f.write(b"\x00" * 80)           # header
        f.write(struct.pack("<I", n_tris))  # triangle count
        for _ in range(n_tris):
            f.write(struct.pack("<12f", *([0.0] * 12)))  # normal + 3 vertices
            f.write(struct.pack("<H", 0))                 # attribute byte count


class TestReadStlTriCount:
    def test_zero_triangles(self, tmp_path):
        stl = tmp_path / "empty.stl"
        _write_synthetic_stl(stl, 0)
        assert _read_stl_tri_count(str(stl)) == 0

    def test_one_triangle(self, tmp_path):
        stl = tmp_path / "one.stl"
        _write_synthetic_stl(stl, 1)
        assert _read_stl_tri_count(str(stl)) == 1

    def test_many_triangles(self, tmp_path):
        stl = tmp_path / "many.stl"
        _write_synthetic_stl(stl, 9999)
        assert _read_stl_tri_count(str(stl)) == 9999

    def test_large_count(self, tmp_path):
        """Only write header + count, no actual triangle data."""
        stl = tmp_path / "large.stl"
        count = 123456
        with open(stl, "wb") as f:
            f.write(b"\x00" * 80)
            f.write(struct.pack("<I", count))
        assert _read_stl_tri_count(str(stl)) == count

    def test_path_as_string(self, tmp_path):
        stl = tmp_path / "str_path.stl"
        _write_synthetic_stl(stl, 42)
        assert _read_stl_tri_count(str(stl)) == 42

    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _read_stl_tri_count(str(tmp_path / "nope.stl"))

    def test_truncated_header_raises(self, tmp_path):
        stl = tmp_path / "truncated.stl"
        with open(stl, "wb") as f:
            f.write(b"\x00" * 40)  # incomplete header
        with pytest.raises(struct.error):
            _read_stl_tri_count(str(stl))


# ================================================================
# Binary STL format correctness
# ================================================================

class TestSyntheticStlFormat:
    def test_header_80_bytes(self, tmp_path):
        stl = tmp_path / "header.stl"
        _write_synthetic_stl(stl, 5)
        with open(stl, "rb") as f:
            header = f.read(80)
            assert len(header) == 80

    def test_triangle_record_50_bytes(self, tmp_path):
        stl = tmp_path / "record.stl"
        _write_synthetic_stl(stl, 1)
        with open(stl, "rb") as f:
            f.read(84)  # header + count
            record = f.read()
            assert len(record) == 50  # 12*4 + 2

    def test_file_size_matches(self, tmp_path):
        n = 10
        stl = tmp_path / "size.stl"
        _write_synthetic_stl(stl, n)
        expected = 80 + 4 + n * 50
        assert stl.stat().st_size == expected


# ================================================================
# export_stl_high_density / export_step (require build123d)
# ================================================================

bd = pytest.importorskip("build123d", reason="build123d not installed")


@pytest.fixture
def simple_box():
    """A simple 10x10x10 box for export tests."""
    with bd.BuildPart() as p:
        bd.Box(10, 10, 10)
    return p.part


class TestExportStlHighDensity:
    def test_returns_positive_tri_count(self, simple_box, tmp_path):
        stl = tmp_path / "box.stl"
        n = export_stl_high_density(simple_box, stl)
        assert n > 0

    def test_file_created(self, simple_box, tmp_path):
        stl = tmp_path / "box.stl"
        export_stl_high_density(simple_box, stl)
        assert stl.exists()
        assert stl.stat().st_size > 84  # at least header + count

    def test_path_object_accepted(self, simple_box, tmp_path):
        stl = tmp_path / "box_path.stl"
        n = export_stl_high_density(simple_box, stl)
        assert n > 0

    def test_string_path_accepted(self, simple_box, tmp_path):
        stl = str(tmp_path / "box_str.stl")
        n = export_stl_high_density(simple_box, stl)
        assert n > 0

    def test_custom_tolerance(self, simple_box, tmp_path):
        fine = tmp_path / "fine.stl"
        coarse = tmp_path / "coarse.stl"
        n_fine = export_stl_high_density(simple_box, fine,
                                         tolerance=0.01, angular_tolerance=0.05)
        n_coarse = export_stl_high_density(simple_box, coarse,
                                           tolerance=0.5, angular_tolerance=0.5)
        # finer tolerance should produce >= coarse triangles
        assert n_fine >= n_coarse


class TestExportStep:
    def test_file_created(self, simple_box, tmp_path):
        step = tmp_path / "box.step"
        export_step(simple_box, step)
        assert step.exists()
        assert step.stat().st_size > 0

    def test_string_path(self, simple_box, tmp_path):
        step = str(tmp_path / "box_str.step")
        export_step(simple_box, step)
        assert Path(step).exists()
