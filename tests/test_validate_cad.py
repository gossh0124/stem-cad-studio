"""tests/test_validate_cad.py — STR17: validate_cad.py 五項驗證測試。

不依賴真實 STL 檔：僅測 bbox / snap_fit / path resolve / missing-input 邏輯。
"""
from __future__ import annotations
from pathlib import Path
import pytest

from services.shared.validate_cad import (
    BBOX_LIMIT_MM,
    MIN_WALL_MM,
    _check_bbox,
    _check_exists,
    _check_snap_fit,
    _resolve_stl_path,
    validate_cad_output,
)


# ── _resolve_stl_path ────────────────────────────────────────

class TestResolveStlPath:
    def test_none_returns_none(self):
        assert _resolve_stl_path(None, Path("C:/proj")) is None

    def test_empty_returns_none(self):
        assert _resolve_stl_path("", Path("C:/proj")) is None

    def test_canned_url(self):
        p = _resolve_stl_path("/canned/auto_waterer/bottom.stl", Path("C:/proj"))
        assert p == Path("C:/proj/v6/canned/auto_waterer/bottom.stl")

    def test_absolute_path(self):
        p = _resolve_stl_path("C:/output/test.stl", Path("C:/proj"))
        assert p == Path("C:/output/test.stl")

    def test_relative_path(self):
        p = _resolve_stl_path("output/test.stl", Path("C:/proj"))
        assert p == Path("C:/proj/output/test.stl")


# ── _check_exists ────────────────────────────────────────────

class TestCheckExists:
    def test_none_path(self):
        ok, msg = _check_exists(None)
        assert not ok
        assert "missing" in msg

    def test_nonexistent(self, tmp_path):
        ok, msg = _check_exists(tmp_path / "nope.stl")
        assert not ok
        assert "not found" in msg

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.stl"
        f.write_bytes(b"")
        ok, msg = _check_exists(f)
        assert not ok
        assert "empty" in msg

    def test_valid_file(self, tmp_path):
        f = tmp_path / "good.stl"
        f.write_bytes(b"solid test\nendsolid\n")
        ok, msg = _check_exists(f)
        assert ok
        assert msg == ""


# ── _check_bbox ──────────────────────────────────────────────

class TestCheckBbox:
    def test_within_limits(self):
        spec = {"outer_l": 100, "outer_w": 80, "base_h": 30, "lid_h": 20}
        ok, msg = _check_bbox(spec)
        assert ok

    def test_length_exceeds(self):
        spec = {"outer_l": 350, "outer_w": 80, "base_h": 30, "lid_h": 20}
        ok, msg = _check_bbox(spec)
        assert not ok
        assert "L=" in msg

    def test_height_exceeds(self):
        spec = {"outer_l": 100, "outer_w": 80, "base_h": 200, "lid_h": 150}
        ok, msg = _check_bbox(spec)
        assert not ok
        assert "H=" in msg

    def test_multiple_exceed(self):
        spec = {"outer_l": 400, "outer_w": 400, "base_h": 200, "lid_h": 200}
        ok, msg = _check_bbox(spec)
        assert not ok
        assert "L=" in msg and "W=" in msg and "H=" in msg

    def test_empty_spec_passes(self):
        ok, msg = _check_bbox({})
        assert ok

    def test_at_limit_passes(self):
        spec = {"outer_l": 300, "outer_w": 300, "base_h": 150, "lid_h": 150}
        ok, msg = _check_bbox(spec)
        assert ok


# ── _check_snap_fit ──────────────────────────────────────────

class TestCheckSnapFit:
    def test_valid(self):
        ok, msg = _check_snap_fit({"wall": 2.0, "tol": 0.3})
        assert ok

    def test_wall_too_thin(self):
        ok, msg = _check_snap_fit({"wall": 1.0, "tol": 0.3})
        assert not ok
        assert "wall=" in msg

    def test_tol_too_low(self):
        ok, msg = _check_snap_fit({"wall": 2.0, "tol": 0.05})
        assert not ok
        assert "tol=" in msg

    def test_tol_too_high(self):
        ok, msg = _check_snap_fit({"wall": 2.0, "tol": 0.8})
        assert not ok
        assert "tol=" in msg

    def test_boundary_min(self):
        ok, _ = _check_snap_fit({"wall": MIN_WALL_MM, "tol": 0.1})
        assert ok

    def test_boundary_max(self):
        ok, _ = _check_snap_fit({"wall": 3.0, "tol": 0.5})
        assert ok


# ── validate_cad_output (integration, no STL) ────────────────

class TestValidateCadOutput:
    def test_none_input(self):
        result = validate_cad_output(None)
        assert result["invalid"] is True
        assert result["fail_count"] == 5
        assert "cad_output missing" in result["fail_reasons"]

    def test_empty_dict(self):
        result = validate_cad_output({})
        assert result["invalid"] is True
        assert not result["checks"]["exists"]

    def test_bbox_and_snap_pass_without_stl(self):
        cad = {
            "spec": {"outer_l": 100, "outer_w": 80,
                     "base_h": 30, "lid_h": 20,
                     "wall": 2.0, "tol": 0.3},
        }
        result = validate_cad_output(cad)
        assert result["checks"]["bbox_ok"] is True
        assert result["checks"]["snap_fit_ok"] is True
        assert not result["checks"]["exists"]

    def test_checks_keys(self):
        result = validate_cad_output(None)
        expected_checks = {"exists", "parseable", "watertight", "bbox_ok", "snap_fit_ok"}
        assert set(result["checks"].keys()) == expected_checks
