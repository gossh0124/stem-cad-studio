"""Tests for lib/thermal_index.py."""
import json
from pathlib import Path

import pytest

from lib.thermal_index import (
    _pcb_entry,
    _mount_entry,
    build_thermal_index,
    write_thermal_index,
    load_thermal_index,
)


class TestPcbEntry:
    def test_arduino_has_sources(self):
        from lib.pcb import ARDUINO_UNO_R3
        entry = _pcb_entry("Arduino-Uno-class", ARDUINO_UNO_R3, "MCU")
        assert entry["tier"] == "MCU"
        assert entry["total_typical_mw"] > 0
        assert len(entry["sources"]) > 0

    def test_centroid_within_board(self):
        from lib.pcb import ARDUINO_UNO_R3
        entry = _pcb_entry("Arduino-Uno-class", ARDUINO_UNO_R3, "MCU")
        cx = entry["centroid"]["x"]
        cy = entry["centroid"]["y"]
        assert 0 <= cx <= ARDUINO_UNO_R3.length
        assert 0 <= cy <= ARDUINO_UNO_R3.width

    def test_dominant_is_highest_mw(self):
        from lib.pcb import ARDUINO_UNO_R3
        entry = _pcb_entry("Arduino-Uno-class", ARDUINO_UNO_R3, "MCU")
        dom = entry["dominant"]
        max_mw = max(s["mw"] for s in entry["sources"])
        assert dom["mw"] == max_mw

    def test_idle_less_than_typical(self):
        from lib.pcb import ESP32_DEVKIT_V1
        entry = _pcb_entry("ESP32-class", ESP32_DEVKIT_V1, "MCU")
        assert entry["total_idle_mw"] <= entry["total_typical_mw"]

    def test_peak_greater_than_typical(self):
        from lib.pcb import RASPBERRY_PI_4B
        entry = _pcb_entry("RaspberryPi-class", RASPBERRY_PI_4B, "MCU")
        assert entry["total_peak_mw"] >= entry["total_typical_mw"]

    def test_all_four_mcus(self):
        from lib.pcb import ARDUINO_UNO_R3, ESP32_DEVKIT_V1, MICROBIT_V2, RASPBERRY_PI_4B
        for name, spec in [
            ("Arduino-Uno-class", ARDUINO_UNO_R3),
            ("ESP32-class", ESP32_DEVKIT_V1),
            ("Microbit-class", MICROBIT_V2),
            ("RaspberryPi-class", RASPBERRY_PI_4B),
        ]:
            entry = _pcb_entry(name, spec, "MCU")
            assert entry["class_name"] == name
            assert entry["total_typical_mw"] >= 0


class TestMountEntry:
    def test_with_thermal_data(self):
        from dataclasses import dataclass

        @dataclass
        class FakeMount:
            thermal_typical_mw: float = 200.0
            thermal_idle_mw: float = 10.0
            thermal_peak_mw: float = 500.0
            thermal_formula: str = "test"
            thermal_source: str = "spec"

        entry = _mount_entry("Test-class", "servo", "TestServo", FakeMount())
        assert entry["tier"] == "Mount"
        assert entry["total_typical_mw"] == 200.0
        assert entry["total_idle_mw"] == 10.0
        assert entry["total_peak_mw"] == 500.0
        assert len(entry["sources"]) == 1
        assert entry["sources"][0]["sub_name"] == "TestServo"

    def test_without_thermal_data(self):
        from dataclasses import dataclass

        @dataclass
        class ColdMount:
            width: float = 10.0

        entry = _mount_entry("Cold-class", "box", "ColdBox", ColdMount())
        assert entry["total_typical_mw"] == 0.0
        assert entry["sources"] == []

    def test_non_dataclass_returns_empty(self):
        entry = _mount_entry("Bad", "x", "x", "not a dataclass")
        assert entry == {}


class TestBuildThermalIndex:
    def test_returns_dict(self):
        idx = build_thermal_index()
        assert isinstance(idx, dict)
        assert len(idx) > 0

    def test_contains_all_mcus(self):
        idx = build_thermal_index()
        for cn in ("Arduino-Uno-class", "ESP32-class",
                   "Microbit-class", "RaspberryPi-class"):
            assert cn in idx, f"Missing {cn}"
            assert idx[cn]["tier"] == "MCU"


class TestWriteLoadRoundtrip:
    def test_write_and_load(self, tmp_path):
        out = tmp_path / "thermal_index.json"
        write_thermal_index(out)
        assert out.exists()
        loaded = load_thermal_index(out)
        assert "Arduino-Uno-class" in loaded

    def test_load_creates_if_missing(self, tmp_path):
        out = tmp_path / "sub" / "thermal_index.json"
        loaded = load_thermal_index(out)
        assert out.exists()
        assert isinstance(loaded, dict)
