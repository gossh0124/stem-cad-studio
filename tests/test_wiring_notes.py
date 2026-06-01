"""Tests for lib/wiring/notes.py."""
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from lib.wiring.notes import (
    _classify_pin_role,
    _make_digital_note,
    _make_pwm_note,
    _make_i2c_note,
    _make_analog_note,
    _make_power_note,
    generate_wiring_notes,
    _PWM_CONTROLLED,
    _PWM_ASPECT,
    _I2C_ADDRS,
)


@dataclass
class FakePinNeed:
    type: str
    tag: str = "SIG"


class TestClassifyPinRole:
    def test_i2c(self):
        assert _classify_pin_role("OLED", FakePinNeed(type="i2c")) == "i2c"

    def test_analog(self):
        assert _classify_pin_role("Sensor", FakePinNeed(type="analog")) == "analog"

    def test_pwm_controlled(self):
        assert _classify_pin_role("Servo", FakePinNeed(type="pwm")) == "pwm"

    def test_pwm_not_in_set(self):
        assert _classify_pin_role("Unknown", FakePinNeed(type="pwm")) == "digital"

    def test_digital_fallback(self):
        assert _classify_pin_role("LED", FakePinNeed(type="digital")) == "digital"


class TestNoteGenerators:
    def test_digital_note(self):
        note = _make_digital_note("HC-SR501", "D2")
        assert "HC-SR501" in note
        assert "D2" in note
        assert "HIGH/LOW" in note

    def test_pwm_note_servo(self):
        note = _make_pwm_note("SG90 Servo", "D9", "Servo")
        assert "SG90 Servo" in note
        assert "D9" in note
        assert "PWM" in note

    def test_pwm_aspect_lookup(self):
        for comp_key, aspect in _PWM_ASPECT.items():
            note = _make_pwm_note("Label", "D3", comp_key)
            assert aspect in note

    def test_pwm_unknown_aspect(self):
        note = _make_pwm_note("Label", "D3", "UnknownComp")
        assert "PWM" in note

    def test_i2c_note(self):
        note = _make_i2c_note("OLED Display", "Arduino", "0x3C")
        assert "OLED Display" in note
        assert "I2C" in note
        assert "0x3C" in note
        assert "SDA" in note

    def test_analog_note(self):
        note = _make_analog_note("LDR", "A0")
        assert "LDR" in note
        assert "A0" in note
        assert "ADC" in note

    def test_power_note(self):
        note = _make_power_note("Motor", "5V")
        assert "Motor" in note
        assert "5V" in note
        assert "GND" in note


class TestGenerateWiringNotes:
    def test_empty_components(self):
        result = generate_wiring_notes({}, [])
        assert result == {}

    def test_missing_comp_in_result(self):
        result = generate_wiring_notes({}, ["NonExistent"])
        assert result == {}

    def test_power_note_generated(self):
        wiring_result = {"LED": {"label": "LED", "pins": []}}
        with patch("lib.wiring.notes.WIRING_TEMPLATES") as mock_tmpl:
            mock_t = MagicMock()
            mock_t.vcc = "5V"
            mock_tmpl.get.return_value = mock_t
            with patch("lib.wiring.notes.COMP_PIN_NEEDS", {"LED": []}):
                result = generate_wiring_notes(wiring_result, ["LED"])
        assert any("VCC" in k for k in result.keys())

    def test_digital_pin_generates_note(self):
        pin_need = FakePinNeed(type="digital", tag="OUT")
        wiring_result = {
            "PIR": {
                "label": "HC-SR501",
                "pins": [{"mcu": "D2", "comp": "OUT"}],
            }
        }
        with patch("lib.wiring.notes.WIRING_TEMPLATES") as mock_tmpl:
            mock_tmpl.get.return_value = None
            with patch("lib.wiring.notes.COMP_PIN_NEEDS", {"PIR": [pin_need]}):
                result = generate_wiring_notes(wiring_result, ["PIR"])
        assert "MCU_D2_to_PIR_OUT" in result
        assert "HIGH/LOW" in result["MCU_D2_to_PIR_OUT"]

    def test_skips_power_pins(self):
        pin_need = FakePinNeed(type="digital", tag="SIG")
        wiring_result = {
            "X": {
                "label": "X",
                "pins": [
                    {"mcu": "GND", "comp": "GND"},
                    {"mcu": "5V", "comp": "VCC"},
                ],
            }
        }
        with patch("lib.wiring.notes.WIRING_TEMPLATES") as mock_tmpl:
            mock_tmpl.get.return_value = None
            with patch("lib.wiring.notes.COMP_PIN_NEEDS", {"X": [pin_need]}):
                result = generate_wiring_notes(wiring_result, ["X"])
        assert len(result) == 0
