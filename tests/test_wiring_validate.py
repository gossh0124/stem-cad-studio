"""Tests for lib/wiring/validate.py — direction + voltage domain validation."""
from __future__ import annotations

import pytest

from lib.wiring.validate import (
    _is_compatible,
    _norm_vd,
    _check_voltage_domain,
    _to_ssot_pin_name,
    _SHORT_TO_CLASS,
    _BRAIN_DEFAULT_VD,
    WiringIssue,
    ssot_pin_info,
    _power_vd_from_label,
)


class TestIsCompatible:
    """_is_compatible direction matrix tests."""

    # Same direction — allowed cases
    def test_power_power_ok(self):
        ok, sev, _ = _is_compatible("power", "power")
        assert ok is True

    def test_gnd_gnd_ok(self):
        ok, sev, _ = _is_compatible("gnd", "gnd")
        assert ok is True

    def test_i2c_bidir_ok(self):
        ok, sev, _ = _is_compatible("i2c_bidir", "i2c_bidir")
        assert ok is True

    def test_digital_bidir_bidir_ok(self):
        ok, sev, _ = _is_compatible("digital_bidir", "digital_bidir")
        assert ok is True

    # Same direction — disallowed (both in or both out)
    def test_digital_in_in_fail(self):
        ok, sev, reason = _is_compatible("digital_in", "digital_in")
        assert ok is False
        assert sev == "error"

    def test_digital_out_out_fail(self):
        ok, sev, _ = _is_compatible("digital_out", "digital_out")
        assert ok is False

    def test_analog_in_in_fail(self):
        ok, sev, _ = _is_compatible("analog_in", "analog_in")
        assert ok is False

    # Valid pairs — in × out
    def test_digital_in_out_ok(self):
        ok, sev, _ = _is_compatible("digital_in", "digital_out")
        assert ok is True

    def test_digital_out_in_ok(self):
        ok, sev, _ = _is_compatible("digital_out", "digital_in")
        assert ok is True

    def test_analog_in_out_ok(self):
        ok, sev, _ = _is_compatible("analog_in", "analog_out")
        assert ok is True

    def test_pwm_in_out_ok(self):
        ok, sev, _ = _is_compatible("pwm_in", "pwm_out")
        assert ok is True

    def test_uart_tx_rx_ok(self):
        ok, sev, _ = _is_compatible("uart_tx", "uart_rx")
        assert ok is True

    def test_uart_rx_tx_ok(self):
        ok, sev, _ = _is_compatible("uart_rx", "uart_tx")
        assert ok is True

    # bidir compatibility
    def test_bidir_with_digital_in(self):
        ok, sev, _ = _is_compatible("digital_bidir", "digital_in")
        assert ok is True

    def test_bidir_with_digital_out(self):
        ok, sev, _ = _is_compatible("digital_bidir", "digital_out")
        assert ok is True

    def test_bidir_with_analog_in(self):
        ok, sev, _ = _is_compatible("digital_bidir", "analog_in")
        assert ok is True

    # bidir must NOT connect to power/gnd
    def test_bidir_power_fail(self):
        ok, sev, _ = _is_compatible("digital_bidir", "power")
        assert ok is False
        assert sev == "error"

    def test_bidir_gnd_fail(self):
        ok, sev, _ = _is_compatible("digital_bidir", "gnd")
        assert ok is False

    # power/gnd vs logic
    def test_power_digital_in_fail(self):
        ok, sev, _ = _is_compatible("power", "digital_in")
        assert ok is False

    def test_gnd_digital_out_fail(self):
        ok, sev, _ = _is_compatible("gnd", "digital_out")
        assert ok is False

    # "other" direction
    def test_other_with_anything_ok(self):
        ok, sev, _ = _is_compatible("other", "digital_in")
        assert ok is True
        assert sev == "warning"


class TestNormVd:
    """_norm_vd normalizes voltage domain strings."""

    def test_basic(self):
        assert _norm_vd("Logic_5V") == "logic_5v"

    def test_strips_whitespace(self):
        assert _norm_vd("  3V3  ") == "3v3"

    def test_none_becomes_empty(self):
        assert _norm_vd("") == ""

    def test_none_value(self):
        assert _norm_vd(None) == ""


class TestCheckVoltageDomain:
    """_check_voltage_domain checks VD compatibility."""

    def test_same_domain_ok(self):
        ok, sev, _ = _check_voltage_domain("logic_5V", "logic_5V")
        assert ok is True

    def test_3v3_vs_5v_warning(self):
        ok, sev, reason = _check_voltage_domain("logic_3V3", "logic_5V")
        assert ok is False
        assert sev == "warning"
        assert "level shifter" in reason

    def test_5v_vs_3v3_warning(self):
        ok, sev, _ = _check_voltage_domain("logic_5V", "logic_3V3")
        assert ok is False
        assert "level shifter" in _

    def test_unknown_skip(self):
        ok, sev, _ = _check_voltage_domain("", "logic_5V")
        assert ok is True

    def test_power_skip(self):
        ok, sev, _ = _check_voltage_domain("power", "logic_5V")
        assert ok is True

    def test_gnd_skip(self):
        ok, sev, _ = _check_voltage_domain("gnd", "logic_3V3")
        assert ok is True

    def test_vin_with_logic_warning(self):
        ok, sev, reason = _check_voltage_domain("vin", "logic_3v3")
        assert ok is False
        assert "VIN" in reason


class TestToSsotPinName:
    """_to_ssot_pin_name maps short tags to SSOT names."""

    def test_known_alias(self):
        assert _to_ssot_pin_name("SoilMoisture", "AO") == "AOUT"

    def test_known_alias_light(self):
        assert _to_ssot_pin_name("Light", "LDR") == "AOUT"

    def test_passthrough_unknown(self):
        assert _to_ssot_pin_name("PIR", "OUT") == "OUT"


class TestPowerVdFromLabel:
    """_power_vd_from_label extracts voltage domain from rail label."""

    def test_3v3(self):
        assert _power_vd_from_label("3V3") == "3V3"

    def test_3_3v(self):
        assert _power_vd_from_label("3.3V") == "3V3"

    def test_vin(self):
        assert _power_vd_from_label("VIN") == "vin"

    def test_5v_default(self):
        assert _power_vd_from_label("5V") == "5V"

    def test_unknown_defaults_5v(self):
        assert _power_vd_from_label("USB") == "5V"


class TestWiringIssue:
    """WiringIssue dataclass."""

    def test_to_dict(self):
        issue = WiringIssue(
            severity="error",
            comp="PIR",
            comp_pin="OUT",
            comp_direction="digital_out",
            mcu_pin="D3",
            mcu_direction="digital_out",
            reason="both output",
        )
        d = issue.to_dict()
        assert d["severity"] == "error"
        assert d["comp"] == "PIR"
        assert d["mcu_pin"] == "D3"
        assert d["comp_vd"] == ""
        assert d["mcu_vd"] == ""


class TestShortToClass:
    """_SHORT_TO_CLASS mapping completeness."""

    def test_all_mcus_mapped(self):
        for mcu in ("Arduino", "ESP32", "RPi", "Microbit"):
            assert mcu in _SHORT_TO_CLASS

    def test_all_values_end_with_class(self):
        for k, v in _SHORT_TO_CLASS.items():
            assert v.endswith("-class"), f"{k} -> {v} missing -class suffix"


class TestBrainDefaultVd:
    """_BRAIN_DEFAULT_VD has all MCU keys."""

    def test_arduino_5v(self):
        assert _BRAIN_DEFAULT_VD["Arduino"] == "logic_5V"

    def test_esp32_3v3(self):
        assert _BRAIN_DEFAULT_VD["ESP32"] == "logic_3V3"

    def test_rpi_3v3(self):
        assert _BRAIN_DEFAULT_VD["RPi"] == "logic_3V3"

    def test_microbit_3v3(self):
        assert _BRAIN_DEFAULT_VD["Microbit"] == "logic_3V3"
