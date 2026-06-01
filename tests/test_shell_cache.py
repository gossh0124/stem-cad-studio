"""Tests for lib/shell_cache.py."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.shell_cache import (
    fingerprint_for_spec,
    get_cached_shell,
    save_shell_to_cache,
    _fingerprint_pcb,
    _fingerprint_mount,
)


class TestFingerprint:
    def test_pcb_fingerprint_deterministic(self):
        from lib.pcb import ARDUINO_UNO_R3
        fp1 = fingerprint_for_spec(ARDUINO_UNO_R3)
        fp2 = fingerprint_for_spec(ARDUINO_UNO_R3)
        assert fp1 == fp2
        assert len(fp1) == 16

    def test_different_boards_different_fingerprint(self):
        from lib.pcb import ARDUINO_UNO_R3, ESP32_DEVKIT_V1
        fp_a = fingerprint_for_spec(ARDUINO_UNO_R3)
        fp_e = fingerprint_for_spec(ESP32_DEVKIT_V1)
        assert fp_a != fp_e

    def test_mount_fingerprint_deterministic(self):
        from dataclasses import dataclass

        @dataclass
        class FakeMount:
            width: float = 10.0
            height: float = 5.0
            thermal_mw: float = 100.0

        spec = FakeMount()
        fp1 = _fingerprint_mount(spec)
        fp2 = _fingerprint_mount(spec)
        assert fp1 == fp2

    def test_mount_fingerprint_ignores_thermal(self):
        from dataclasses import dataclass

        @dataclass
        class FakeMount:
            width: float = 10.0
            thermal_peak: float = 0.0

        spec_a = FakeMount(thermal_peak=100.0)
        spec_b = FakeMount(thermal_peak=999.0)
        assert _fingerprint_mount(spec_a) == _fingerprint_mount(spec_b)


class TestCacheRoundtrip:
    def test_save_and_get(self, tmp_path):
        src_file = tmp_path / "base.stl"
        src_file.write_text("solid test")

        with patch("lib.shell_cache.SHELLS_DIR", tmp_path / "shells"):
            save_shell_to_cache(
                class_name="Test-Class",
                fingerprint="abc123",
                kind="two_piece",
                files={"base_stl": str(src_file)},
            )
            result = get_cached_shell("Test-Class", "abc123")
            assert result is not None
            assert "base_stl" in result
            assert result["kind"] == "two_piece"

    def test_fingerprint_mismatch_returns_none(self, tmp_path):
        src_file = tmp_path / "base.stl"
        src_file.write_text("solid test")

        with patch("lib.shell_cache.SHELLS_DIR", tmp_path / "shells"):
            save_shell_to_cache(
                class_name="Test-Class",
                fingerprint="abc123",
                kind="two_piece",
                files={"base_stl": str(src_file)},
            )
            result = get_cached_shell("Test-Class", "different_fp")
            assert result is None

    def test_missing_entry_returns_none(self, tmp_path):
        with patch("lib.shell_cache.SHELLS_DIR", tmp_path / "shells"):
            result = get_cached_shell("NonExistent", "abc")
            assert result is None

    def test_extra_meta_preserved(self, tmp_path):
        src_file = tmp_path / "mount.stl"
        src_file.write_text("solid mount")

        with patch("lib.shell_cache.SHELLS_DIR", tmp_path / "shells"):
            save_shell_to_cache(
                class_name="Sensor-X",
                fingerprint="fp1",
                kind="mount",
                files={"mount_stl": str(src_file)},
                extra_meta={"tris": 500, "label": "test"},
            )
            result = get_cached_shell("Sensor-X", "fp1")
            assert result["tris"] == 500
            assert result["label"] == "test"
