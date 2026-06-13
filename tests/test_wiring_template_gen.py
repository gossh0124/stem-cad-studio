"""Tests for lib/wiring/template_gen.py."""
import pytest

from lib.wiring.template_gen import (
    _collect_pins,
    _find_passive,
    _resolve_vcc,
    _note_from_direction,
    _apply_override,
    _COMP_OVERRIDES,
    _DS_TO_SHORT,
    _SHORT_TO_DS,
    _POWER_SOURCE_CLASSES,
    template_from_datasheet,
    generate_all_templates,
    get_template,
    load_datasheet,
)
from lib.wiring.engine import WiringTemplate


class TestCollectPins:
    def test_empty_layout(self):
        assert _collect_pins({}) == []

    def test_single_group(self):
        data = {
            "pin_layout": {
                "header_groups": [
                    {"pins": [{"name": "VCC", "type": "PWR"}, {"name": "GND", "type": "GND"}]}
                ]
            }
        }
        pins = _collect_pins(data)
        assert len(pins) == 2
        assert pins[0]["name"] == "VCC"

    def test_multiple_groups_flatten(self):
        data = {
            "pin_layout": {
                "header_groups": [
                    {"pins": [{"name": "A"}]},
                    {"pins": [{"name": "B"}, {"name": "C"}]},
                ]
            }
        }
        pins = _collect_pins(data)
        assert len(pins) == 3


class TestFindPassive:
    def test_found(self):
        hints = {"passives": [{"pin": "SIG", "kind": "R", "value": "220", "topo": "series"}]}
        result = _find_passive("SIG", hints)
        assert result == {"kind": "R", "value": "220", "topo": "series"}

    def test_not_found(self):
        hints = {"passives": [{"pin": "OTHER", "kind": "R", "value": "1k", "topo": "series"}]}
        assert _find_passive("SIG", hints) is None

    def test_empty_hints(self):
        assert _find_passive("SIG", {}) is None


class TestResolveVcc:
    def test_hints_override(self):
        pins = [{"type": "PWR", "voltage_domain": "5V"}]
        hints = {"vcc": "3.3V"}
        assert _resolve_vcc(pins, hints) == "3.3V"

    def test_from_pin_5v(self):
        pins = [{"type": "PWR", "voltage_domain": "5V"}]
        assert _resolve_vcc(pins, {}) == "5V"

    def test_from_pin_3v3(self):
        pins = [{"type": "PWR", "voltage_domain": "3V3"}]
        assert _resolve_vcc(pins, {}) == "3.3V"

    def test_no_vcc(self):
        pins = [{"type": "GPIO"}]
        assert _resolve_vcc(pins, {}) is None


class TestNoteFromDirection:
    def test_known_directions(self):
        assert _note_from_direction("digital_in") != ""
        assert _note_from_direction("i2c_data") == "I2C Data"

    def test_unknown_direction(self):
        assert _note_from_direction("nonexistent") == ""


class TestApplyOverride:
    def test_no_override_returns_original(self):
        tmpl = WiringTemplate(label="Test", vcc="5V", extra=[], decoupling=None)
        result = _apply_override("NonExistentComp", tmpl)
        assert result is tmpl

    def test_override_replaces_fields(self):
        # S-wiring SSOT-derive retired Servo's override (now SSOT-derived); use a
        # KEPT genuine exception (DCMotor) to verify _apply_override replaces fields.
        tmpl = WiringTemplate(label="Original", vcc="3.3V", extra=[], decoupling=None)
        result = _apply_override("DCMotor", tmpl)
        assert result.label == "L298N 馬達驅動"
        assert result.vcc == "5V"
        assert len(result.extra) > 0

    def test_all_overrides_produce_valid_template(self):
        for short_name in _COMP_OVERRIDES:
            result = _apply_override(short_name, None)
            assert result is not None
            assert isinstance(result, WiringTemplate)


class TestMappingConsistency:
    def test_short_to_ds_is_inverse(self):
        for ds_key, short in _DS_TO_SHORT.items():
            assert _SHORT_TO_DS[short] == ds_key

    def test_all_overrides_have_ds_mapping(self):
        for short_name in _COMP_OVERRIDES:
            assert short_name in _SHORT_TO_DS or short_name in _DS_TO_SHORT.values(), \
                f"Override {short_name} has no DS mapping"


class TestTemplateFromDatasheet:
    def test_known_component(self):
        tmpl = template_from_datasheet("TempHumid")
        if tmpl is not None:
            assert isinstance(tmpl, WiringTemplate)
            assert tmpl.label != ""

    def test_unknown_returns_none(self):
        assert template_from_datasheet("CompletelyFakeComponent999") is None

    def test_power_source_classes_nonempty(self):
        # A4-A: frozenset must contain the five power source keys
        assert len(_POWER_SOURCE_CLASSES) == 5
        assert "Battery-AA-class" in _POWER_SOURCE_CLASSES
        assert "USB-5V-class" in _POWER_SOURCE_CLASSES

    def test_power_source_raises_value_error(self, monkeypatch):
        # A4-A: passing a power-source ds_key directly must fail-loud
        fake_ds = {
            "Battery-AA-class": {
                "identity": {"full_name": "AA Battery"},
                "pin_layout": {"header_groups": [
                    {"pins": [{"name": "V+", "type": "PWR", "voltage_domain": "1.5V",
                                "direction": "power"}]}
                ]},
                "wiring_hints": {},
            }
        }
        import lib.wiring.template_gen as tg
        monkeypatch.setattr(tg, "_datasheet_cache", fake_ds)
        with pytest.raises(ValueError, match="power source"):
            template_from_datasheet("Battery-AA-class")


class TestGenerateAllTemplates:
    def test_returns_dict(self):
        result = generate_all_templates()
        assert isinstance(result, dict)

    def test_overridden_components_present(self):
        result = generate_all_templates()
        for short_name in _COMP_OVERRIDES:
            if short_name in _DS_TO_SHORT.values():
                ds_key = _SHORT_TO_DS[short_name]
                ds = load_datasheet()
                if ds_key in ds:
                    assert short_name in result, f"Missing {short_name}"


class TestGetTemplate:
    def test_returns_template_or_none(self):
        result = get_template("Servo")
        assert result is None or isinstance(result, WiringTemplate)

    def test_unknown_returns_none(self):
        assert get_template("TotallyFakeXYZ") is None
