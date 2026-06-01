"""Tests for lib/wiring/csp.py — CSP pin allocator."""
from __future__ import annotations

import pytest

from lib.wiring.csp import (
    _Var,
    _is_output_need,
    _build_domains,
    _mrv_order,
    _forward_check,
    csp_allocate,
)
from lib.wiring.engine import COMP_PIN_NEEDS, PIN_POOLS
from lib.pin_maps import _PIN_MAPS, _I2C_HW_PINS, _INPUT_ONLY_PINS


def _fresh_pool(brain_key: str) -> dict:
    raw = PIN_POOLS[brain_key]
    full = _PIN_MAPS[brain_key]
    return {
        "pwm": list(raw["pwm"]),
        "digital": list(raw["digital"]),
        "analog": list(raw["analog"]),
        "i2c": dict(raw["i2c"]),
        "spi": dict(full.get("spi", {})),
        "uart": dict(full.get("uart", {})),
    }


class TestVar:
    """_Var dataclass."""

    def test_key_format(self):
        v = _Var(comp="PIR", tag="OUT", pin_type="digital")
        assert v.key == "PIR.OUT"

    def test_key_unique_for_different_tags(self):
        v1 = _Var(comp="DCMotor", tag="ENA", pin_type="pwm")
        v2 = _Var(comp="DCMotor", tag="IN1", pin_type="digital")
        assert v1.key != v2.key


class TestIsOutputNeed:
    """_is_output_need identifies output pin types."""

    def test_pwm_is_output(self):
        assert _is_output_need("pwm") is True

    def test_digital_is_output(self):
        assert _is_output_need("digital") is True

    def test_analog_not_output(self):
        assert _is_output_need("analog") is False

    def test_i2c_not_output(self):
        assert _is_output_need("i2c_sda") is False


class TestBuildDomains:
    """_build_domains creates appropriate candidate lists."""

    def test_i2c_sda_domain(self):
        v = _Var(comp="OLED", tag="SDA", pin_type="i2c_sda")
        domains = _build_domains("Arduino", [v], _fresh_pool("Arduino"))
        assert domains["OLED.SDA"] == ["A4"]

    def test_i2c_scl_domain(self):
        v = _Var(comp="OLED", tag="SCL", pin_type="i2c_scl")
        domains = _build_domains("Arduino", [v], _fresh_pool("Arduino"))
        assert domains["OLED.SCL"] == ["A5"]

    def test_analog_domain(self):
        v = _Var(comp="SoilMoisture", tag="AO", pin_type="analog")
        domains = _build_domains("Arduino", [v], _fresh_pool("Arduino"))
        assert "A0" in domains["SoilMoisture.AO"]

    def test_pwm_domain_excludes_input_only(self):
        v = _Var(comp="Servo", tag="SIG", pin_type="pwm")
        domains = _build_domains("ESP32", [v], _fresh_pool("ESP32"))
        for pin in domains["Servo.SIG"]:
            assert pin not in _INPUT_ONLY_PINS["ESP32"]

    def test_digital_domain_excludes_input_only(self):
        v = _Var(comp="PIR", tag="OUT", pin_type="digital")
        domains = _build_domains("ESP32", [v], _fresh_pool("ESP32"))
        for pin in domains["PIR.OUT"]:
            assert pin not in _INPUT_ONLY_PINS["ESP32"]


class TestMrvOrder:
    """_mrv_order sorts by most constrained first."""

    def test_smaller_domain_first(self):
        v1 = _Var(comp="A", tag="X", pin_type="digital")
        v2 = _Var(comp="B", tag="Y", pin_type="i2c_sda")
        domains = {"A.X": [1, 2, 3, 4, 5], "B.Y": [21]}
        ordered = _mrv_order([v1, v2], domains)
        assert ordered[0].key == "B.Y"

    def test_equal_domains_stable(self):
        v1 = _Var(comp="A", tag="X", pin_type="digital")
        v2 = _Var(comp="B", tag="Y", pin_type="digital")
        domains = {"A.X": [1, 2], "B.Y": [3, 4]}
        ordered = _mrv_order([v1, v2], domains)
        assert len(ordered) == 2


class TestCspAllocate:
    """csp_allocate end-to-end tests."""

    def test_single_component(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["SoilMoisture"], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert "SoilMoisture" in alloc
        assert "AO" in alloc["SoilMoisture"]

    def test_multiple_components_no_conflict(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["PIR", "Relay", "Button"], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert len(alloc) == 3

    def test_no_pin_collision(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["PIR", "Relay", "Button", "NeoPixel"],
            _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert not conflicts
        used_pins = []
        for comp, pins in alloc.items():
            for tag, pin in pins.items():
                if tag in ("SDA", "SCL"):
                    continue
                used_pins.append(pin)
        assert len(used_pins) == len(set(used_pins))

    def test_i2c_shared_across_devices(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["OLED", "LCD"], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert alloc["OLED"]["SDA"] == alloc["LCD"]["SDA"]
        assert alloc["OLED"]["SCL"] == alloc["LCD"]["SCL"]

    def test_esp32_allocation(self):
        alloc, labels, conflicts = csp_allocate(
            "ESP32", ["PIR", "OLED", "Servo"], _fresh_pool("ESP32"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert len(alloc) == 3

    def test_empty_comps(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", [], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert alloc == {}
        assert not conflicts

    def test_unknown_comp_skipped(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["NonExistentWidget"], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert alloc == {}
        assert not conflicts

    def test_many_components_arduino(self):
        comps = ["PIR", "Relay", "Button", "NeoPixel", "TempHumid", "Servo"]
        alloc, labels, conflicts = csp_allocate(
            "Arduino", comps, _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert len(alloc) == 6

    def test_pin_labels_format(self):
        alloc, labels, conflicts = csp_allocate(
            "Arduino", ["PIR"], _fresh_pool("Arduino"), COMP_PIN_NEEDS
        )
        assert "PIR" in labels
        assert "OUT=" in labels["PIR"]

    def test_microbit_prefix(self):
        alloc, labels, conflicts = csp_allocate(
            "Microbit", ["Button"], _fresh_pool("Microbit"), COMP_PIN_NEEDS
        )
        assert not conflicts
        assert "Button" in labels
        assert "P" in labels["Button"]
