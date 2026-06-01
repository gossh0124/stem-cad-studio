"""tests/test_firmware_templates.py — Firmware template utilities + reaction rules.

Covers:
  - lib/firmware/templates.py: _wrap_text, stem_header_lines,
    REACTION_RULES, OUTPUT_FALLBACK, match_reactions
  - lib/wiring/constants.py: MCU_POWER_PASSIVES

Run: .venv/Scripts/python.exe -m pytest tests/test_firmware_templates.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.firmware.templates import (
    _wrap_text, stem_header_lines,
    REACTION_RULES, OUTPUT_FALLBACK, match_reactions,
)
from lib.wiring.constants import MCU_POWER_PASSIVES


# ── _wrap_text ───────────────────────────────────────────────

class TestWrapText:
    def test_empty_string(self):
        assert _wrap_text("") == []

    def test_short_ascii(self):
        result = _wrap_text("hello world", width=20)
        assert len(result) == 1
        assert result[0] == "hello world"

    def test_wraps_long_ascii(self):
        text = "a" * 100
        result = _wrap_text(text, width=30)
        assert len(result) >= 3
        for line in result:
            assert len(line) <= 31

    def test_cjk_double_width(self):
        text = "測試文字輸出"
        result = _wrap_text(text, width=6)
        assert len(result) >= 2

    def test_mixed_cjk_ascii(self):
        text = "ABC abc"
        result = _wrap_text(text, width=10)
        assert len(result) >= 1


# ── stem_header_lines ────────────────────────────────────────

class TestStemHeaderLines:
    def test_empty_returns_empty(self):
        lines = stem_header_lines([], [])
        assert lines == []

    def test_project_name_in_output(self):
        lines = stem_header_lines([], [], project_name="Test Project")
        joined = "\n".join(lines)
        assert "Test Project" in joined

    def test_plan_wrapped(self):
        lines = stem_header_lines([], [], plan="A" * 200)
        assert len(lines) >= 3

    def test_comment_prefix(self):
        lines = stem_header_lines([], [], project_name="X", comment_prefix="#")
        for line in lines:
            if line.strip():
                assert line.startswith("#")

    def test_default_prefix_is_double_slash(self):
        lines = stem_header_lines([], [], project_name="X")
        first_non_empty = next(l for l in lines if l.strip())
        assert first_non_empty.startswith("//")


# ── REACTION_RULES ───────────────────────────────────────────

class TestReactionRules:
    def test_not_empty(self):
        assert len(REACTION_RULES) > 10

    def test_keys_are_tuples(self):
        for k in REACTION_RULES:
            assert isinstance(k, tuple)
            assert len(k) == 2

    def test_values_have_required_keys(self):
        required = {"condition", "action", "else", "label"}
        for k, v in REACTION_RULES.items():
            assert required.issubset(v.keys()), f"{k} missing keys"

    def test_buzzer_variants_exist(self):
        buzzer_keys = [k for k in REACTION_RULES if "Buzzer" in k[1]]
        active = [k for k in buzzer_keys if k[1] == "Buzzer_Active"]
        passive = [k for k in buzzer_keys if k[1] == "Buzzer_Passive"]
        assert len(active) >= 1
        assert len(passive) >= 1

    @pytest.mark.parametrize("sensor,output", [
        ("SoilMoisture", "Relay"),
        ("PIR", "Buzzer"),
        ("PIR", "LED_Single"),
        ("Ultrasonic", "Buzzer"),
        ("Light", "LED_Single"),
        ("TempHumid", "Relay"),
    ])
    def test_known_rule_exists(self, sensor, output):
        assert (sensor, output) in REACTION_RULES


# ── OUTPUT_FALLBACK ──────────────────────────────────────────

class TestOutputFallback:
    def test_not_empty(self):
        assert len(OUTPUT_FALLBACK) > 5

    def test_values_are_strings(self):
        for v in OUTPUT_FALLBACK.values():
            assert isinstance(v, str)

    @pytest.mark.parametrize("output", [
        "LED_Single", "NeoPixel", "Servo", "DCMotor", "Relay",
    ])
    def test_known_fallback_exists(self, output):
        assert output in OUTPUT_FALLBACK


# ── match_reactions ──────────────────────────────────────────

class TestMatchReactions:
    def test_matching_pair(self):
        matched, handled = match_reactions(["PIR"], ["Buzzer"])
        assert len(matched) == 1
        assert matched[0]["sensor"] == "PIR"
        assert "Buzzer" in handled

    def test_no_match(self):
        matched, handled = match_reactions(["FakeSensor"], ["FakeOutput"])
        assert matched == []
        assert handled == set()

    def test_multiple_sensors(self):
        matched, handled = match_reactions(
            ["PIR", "Ultrasonic"],
            ["Buzzer", "LED_Single"],
        )
        assert len(matched) >= 3

    def test_handled_set_populated(self):
        matched, handled = match_reactions(["SoilMoisture"], ["Relay", "LED_Single"])
        assert "Relay" in handled


# ── MCU_POWER_PASSIVES ───────────────────────────────────────

class TestMCUPowerPassives:
    @pytest.mark.parametrize("mcu", ["Arduino", "ESP32", "Microbit", "RPi"])
    def test_mcu_key_exists(self, mcu):
        assert mcu in MCU_POWER_PASSIVES

    def test_arduino_has_caps(self):
        caps = MCU_POWER_PASSIVES["Arduino"]
        assert len(caps) == 2
        kinds = {c["kind"] for c in caps}
        assert kinds == {"C"}

    def test_esp32_bulk_cap(self):
        caps = MCU_POWER_PASSIVES["ESP32"]
        bulk = [c for c in caps if c["topo"] == "bulk"]
        assert len(bulk) == 1
        assert bulk[0]["value"] == "470uF" or "470" in bulk[0]["value"]

    def test_rpi_empty(self):
        assert MCU_POWER_PASSIVES["RPi"] == []

    def test_cap_entries_have_required_keys(self):
        required = {"kind", "value", "topo", "net"}
        for mcu, caps in MCU_POWER_PASSIVES.items():
            for cap in caps:
                assert required.issubset(cap.keys()), f"{mcu} cap missing keys"
