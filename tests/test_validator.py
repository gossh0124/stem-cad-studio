"""test_validator.py -- AdvancedValidator and STEAM_JSON_SCHEMA tests."""
import copy
import pytest

from lib.validator import AdvancedValidator, STEAM_JSON_SCHEMA
from lib.config import TAXONOMY_CONFIG


def _make_valid_instance():
    return {
        "project_name": "Test Project",
        "project_category": "Education",
        "components": [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
        ],
        "enclosure_constraints": {
            "target_size": "compact",
            "wall_thickness_mm": 2.0,
            "material": "PLA",
        },
        "inventory_mentions": [],
    }


# ── normalize_type ──────────────────────────────────────────


class TestNormalizeType:
    def test_canonical_type_unchanged(self):
        t, converted = AdvancedValidator.normalize_type("Arduino-Uno-class")
        assert t == "Arduino-Uno-class"
        assert converted is False

    def test_aliased_type_converted(self):
        t, converted = AdvancedValidator.normalize_type("Microbit")
        assert t == "Microbit-class"
        assert converted is True

    def test_unknown_type_passthrough(self):
        t, converted = AdvancedValidator.normalize_type("NonExistent-class")
        assert t == "NonExistent-class"
        assert converted is False

    @pytest.mark.parametrize("alias,expected", [
        ("Arduino", "Arduino-Uno-class"),
        ("MicroBit", "Microbit-class"),
        ("Micro-Bit", "Microbit-class"),
        ("Speaker", "Speaker-class"),
        ("Servo", "Motor-Servo-class"),
        ("Display-OLED", "Display-OLED-class"),
        ("Sensor-PIR", "Sensor-PIR-class"),
    ])
    def test_all_aliases(self, alias, expected):
        t, converted = AdvancedValidator.normalize_type(alias)
        assert t == expected
        assert converted is True

    def test_empty_string(self):
        t, converted = AdvancedValidator.normalize_type("")
        assert t == ""
        assert converted is False


# ── validate ────────────────────────────────────────────────


class TestValidate:
    def test_valid_instance_passes(self):
        inst = _make_valid_instance()
        ok, msg, warnings, stats = AdvancedValidator.validate(inst)
        assert ok is True
        assert msg == "ok"

    def test_not_dict_fails(self):
        ok, msg, _, _ = AdvancedValidator.validate("not a dict")
        assert ok is False
        assert msg == "not_dict"

    def test_not_dict_list(self):
        ok, msg, _, _ = AdvancedValidator.validate([1, 2, 3])
        assert ok is False
        assert msg == "not_dict"

    def test_missing_project_name(self):
        inst = _make_valid_instance()
        del inst["project_name"]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False
        assert "Schema Error" in msg

    def test_missing_components(self):
        inst = _make_valid_instance()
        del inst["components"]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_empty_components_fails(self):
        inst = _make_valid_instance()
        inst["components"] = []
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_missing_enclosure_constraints(self):
        inst = _make_valid_instance()
        del inst["enclosure_constraints"]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_invalid_category_fails(self):
        inst = _make_valid_instance()
        inst["project_category"] = "InvalidCategory"
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False
        assert "Schema Error" in msg

    def test_missing_core_role_brain(self):
        inst = _make_valid_instance()
        inst["components"] = [
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
        ]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False
        assert "missing_core_Brain" in msg

    def test_missing_core_role_power(self):
        inst = _make_valid_instance()
        inst["components"] = [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
        ]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False
        assert "missing_core_Power" in msg

    def test_missing_core_role_control(self):
        inst = _make_valid_instance()
        inst["components"] = [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
        ]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False
        assert "missing_core_Control" in msg

    def test_category_normalize_home_automation(self):
        inst = _make_valid_instance()
        inst["project_category"] = "Home_Automation"
        ok, msg, warnings, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert inst["project_category"] == "Smart_Home"
        assert any("category_normalized" in w for w in warnings)

    def test_category_normalize_iot(self):
        inst = _make_valid_instance()
        inst["project_category"] = "IoT"
        ok, _, warnings, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert inst["project_category"] == "Smart_Home"

    def test_category_normalize_robot(self):
        inst = _make_valid_instance()
        inst["project_category"] = "Robot"
        ok, _, _, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert inst["project_category"] == "Robotics"

    def test_category_normalize_music(self):
        inst = _make_valid_instance()
        inst["project_category"] = "Music"
        ok, _, _, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert inst["project_category"] == "Interactive_Art"

    @pytest.mark.parametrize("alias,expected", list(AdvancedValidator._CATEGORY_NORMALIZE.items()))
    def test_all_category_aliases(self, alias, expected):
        inst = _make_valid_instance()
        inst["project_category"] = alias
        ok, _, _, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert inst["project_category"] == expected

    def test_unknown_type_generates_warning(self):
        inst = _make_valid_instance()
        inst["components"].append(
            {"role": "Sensor", "type": "Sensor-Unknown-class", "qty": 1}
        )
        ok, _, warnings, stats = AdvancedValidator.validate(inst)
        assert ok is True
        assert any("unknown_type" in w for w in warnings)
        assert "Sensor-Unknown-class" in stats["unknown_raw"]

    def test_type_in_wrong_role_generates_warning(self):
        inst = _make_valid_instance()
        inst["components"].append(
            {"role": "Sensor", "type": "Motor-Servo-class", "qty": 1}
        )
        ok, _, warnings, _ = AdvancedValidator.validate(inst)
        assert ok is True
        assert any("not_in_role" in w for w in warnings)

    def test_stats_raw_tax_hits(self):
        inst = _make_valid_instance()
        _, _, _, stats = AdvancedValidator.validate(inst)
        assert stats["raw_tax_hits"] >= 3

    def test_stats_norm_tax_hits_with_alias(self):
        inst = _make_valid_instance()
        inst["components"].append(
            {"role": "Brain", "type": "MicroBit-class", "qty": 1}
        )
        _, _, _, stats = AdvancedValidator.validate(inst)
        assert stats["norm_tax_hits"] >= 1

    def test_valid_with_cot_plan(self):
        inst = _make_valid_instance()
        inst["cot_plan"] = {
            "high_level_plan": "Test plan",
            "step_by_step": ["Step 1"],
            "subsystems": [
                {"role": "Brain", "part": "Arduino", "type": "Arduino-Uno-class", "reason": "Standard MCU"}
            ],
        }
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is True

    def test_cot_plan_subsystem_missing_reason_fails(self):
        inst = _make_valid_instance()
        inst["cot_plan"] = {
            "high_level_plan": "Plan",
            "step_by_step": ["S1"],
            "subsystems": [
                {"role": "Brain", "part": "Arduino", "type": "Arduino-Uno-class"}
            ],
        }
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_valid_enclosure_sizes(self):
        for size in ["compact", "medium", "large"]:
            inst = _make_valid_instance()
            inst["enclosure_constraints"]["target_size"] = size
            ok, _, _, _ = AdvancedValidator.validate(inst)
            assert ok is True

    def test_invalid_enclosure_size(self):
        inst = _make_valid_instance()
        inst["enclosure_constraints"]["target_size"] = "tiny"
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_component_qty_zero_fails(self):
        inst = _make_valid_instance()
        inst["components"][0]["qty"] = 0
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_component_missing_role_fails(self):
        inst = _make_valid_instance()
        del inst["components"][0]["role"]
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_wall_thickness_below_min_fails(self):
        inst = _make_valid_instance()
        inst["enclosure_constraints"]["wall_thickness_mm"] = 0.3
        ok, msg, _, _ = AdvancedValidator.validate(inst)
        assert ok is False

    def test_all_valid_categories(self):
        for cat in TAXONOMY_CONFIG["project_categories"]:
            inst = _make_valid_instance()
            inst["project_category"] = cat
            ok, _, _, _ = AdvancedValidator.validate(inst)
            assert ok is True, f"Category {cat} should be valid"


# ── auto_fix ────────────────────────────────────────────────


class TestAutoFix:
    def setup_method(self):
        self.validator = AdvancedValidator()

    def test_fix_bad_category_normalize(self):
        data = _make_valid_instance()
        data["project_category"] = "Home_Automation"
        result = self.validator.auto_fix(data)
        assert result["project_category"] == "Smart_Home"

    def test_fix_unknown_category_defaults_education(self):
        data = _make_valid_instance()
        data["project_category"] = "CompletelyUnknown"
        result = self.validator.auto_fix(data)
        assert result["project_category"] == "Education"

    def test_fix_missing_class_suffix(self):
        data = _make_valid_instance()
        data["components"][0]["type"] = "Arduino-Uno"
        result = self.validator.auto_fix(data)
        assert result["components"][0]["type"] == "Arduino-Uno-class"

    def test_fix_class_suffix_idempotent(self):
        data = _make_valid_instance()
        result = self.validator.auto_fix(data)
        assert result["components"][0]["type"] == "Arduino-Uno-class"

    def test_fix_clears_inventory_mentions(self):
        data = _make_valid_instance()
        data["inventory_mentions"] = ["something"]
        result = self.validator.auto_fix(data)
        assert result["inventory_mentions"] == []

    def test_fix_adds_cot_plan_when_missing(self):
        data = _make_valid_instance()
        assert "cot_plan" not in data
        result = self.validator.auto_fix(data)
        assert "cot_plan" in result
        assert result["cot_plan"]["high_level_plan"] == "Auto-generated fallback plan"

    def test_fix_cot_plan_size_compact(self):
        data = _make_valid_instance()
        data["components"] = [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
        ]
        result = self.validator.auto_fix(data)
        assert result["cot_plan"]["parameter_hints"]["enclosure_size"] == "compact"

    def test_fix_cot_plan_size_large_with_rpi(self):
        data = _make_valid_instance()
        data["components"] = [
            {"role": "Brain", "type": "RaspberryPi-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
        ]
        result = self.validator.auto_fix(data)
        assert result["cot_plan"]["parameter_hints"]["enclosure_size"] == "large"

    def test_fix_cot_plan_size_large_many_components(self):
        data = _make_valid_instance()
        data["components"] = [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
            {"role": "Sensor", "type": "Sensor-PIR-class", "qty": 1},
            {"role": "Sensor", "type": "Sensor-Ultrasonic-class", "qty": 1},
            {"role": "Actuator", "type": "Motor-Servo-class", "qty": 1},
        ]
        result = self.validator.auto_fix(data)
        assert result["cot_plan"]["parameter_hints"]["enclosure_size"] == "large"

    def test_fix_preserves_existing_cot_plan(self):
        data = _make_valid_instance()
        data["cot_plan"] = {"high_level_plan": "My plan"}
        result = self.validator.auto_fix(data)
        assert result["cot_plan"]["high_level_plan"] == "My plan"

    def test_fix_valid_category_unchanged(self):
        for cat in TAXONOMY_CONFIG["project_categories"]:
            data = _make_valid_instance()
            data["project_category"] = cat
            result = self.validator.auto_fix(data)
            assert result["project_category"] == cat


# ── STEAM_JSON_SCHEMA structure ─────────────────────────────


class TestSchemaStructure:
    def test_schema_has_required_fields(self):
        assert "project_name" in STEAM_JSON_SCHEMA["required"]
        assert "components" in STEAM_JSON_SCHEMA["required"]
        assert "enclosure_constraints" in STEAM_JSON_SCHEMA["required"]

    def test_schema_component_requires_role_type_qty(self):
        comp_schema = STEAM_JSON_SCHEMA["properties"]["components"]["items"]
        assert "role" in comp_schema["required"]
        assert "type" in comp_schema["required"]
        assert "qty" in comp_schema["required"]

    def test_schema_enclosure_requires_target_size(self):
        enc_schema = STEAM_JSON_SCHEMA["properties"]["enclosure_constraints"]
        assert "target_size" in enc_schema["required"]

    def test_schema_inventory_mentions_max_zero(self):
        inv = STEAM_JSON_SCHEMA["properties"]["inventory_mentions"]
        assert inv["maxItems"] == 0
