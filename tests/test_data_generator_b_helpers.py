"""Unit tests for training/data_generator_b_helpers.py (STR22).

Coverage targets:
  1. enclosure_relation_for — all 5 enum values (internal, breadboard, panel, external, embedded)
  2. role_of — known and unknown component types
  3. face_out_for — Display/LED/Sensor/USB/Pump/Buzzer/generic paths
  4. placement_reason — weight/thermal/sensor/display/usb/pump/motor/fallback
  5. _template_in_scope — env filter + multiaxis filter
  6. vary_template — basic mutation + scope enforcement
  7. components_of — correct extraction
  8. env_cfg_of — known and default env lookup
"""
from __future__ import annotations
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
import pytest

from training.data_generator_b_helpers import (
    enclosure_relation_for,
    role_of,
    face_out_for,
    placement_reason,
    vary_template,
    components_of,
    env_cfg_of,
    _template_in_scope,
    WEIGHT_G,
    THERMAL_MW,
    CURRENT_MA,
    ZONES,
    FACE_OUTS,
    ENVIRONMENTS,
    CATEGORY_TEMPLATES,
)


# ── enclosure_relation_for ─────────────────────────────────────

class TestEnclosureRelationFor:
    """enclosure_relation_for: returns correct relation from registry SSOT."""

    def test_internal_default(self):
        """Components without explicit enclosure_relation default to 'internal'."""
        # Arduino-Uno-class has no explicit enclosure_relation in registry => internal
        result = enclosure_relation_for("Arduino-Uno-class")
        assert result == "internal"

    def test_panel_relation(self):
        """Button-class has enclosure_relation='panel'."""
        result = enclosure_relation_for("Button-class")
        assert result == "panel"

    def test_external_relation(self):
        """Battery-LiPo-class has enclosure_relation='external'."""
        result = enclosure_relation_for("Battery-LiPo-class")
        assert result == "external"

    def test_breadboard_relation(self):
        """Sensor-MSGEQ7-class has enclosure_relation='breadboard'."""
        result = enclosure_relation_for("Sensor-MSGEQ7-class")
        assert result == "breadboard"

    def test_unknown_component_returns_internal(self):
        """Unknown ctype not in registry falls back to 'internal'."""
        result = enclosure_relation_for("NonExistent-FooBar-class")
        assert result == "internal"

    def test_result_is_valid_enum(self):
        """All returned values must be in the 5 valid enum values."""
        valid = {"internal", "breadboard", "panel", "external", "embedded"}
        for ctype in ["Arduino-Uno-class", "Button-class", "Battery-LiPo-class",
                      "Sensor-MSGEQ7-class", "Remote-class", "Chassis-Car-class"]:
            assert enclosure_relation_for(ctype) in valid


# ── role_of ────────────────────────────────────────────────────

class TestRoleOf:
    def test_brain_role(self):
        assert role_of("Arduino-Uno-class") == "Brain"

    def test_power_role(self):
        assert role_of("USB-5V-class") == "Power"

    def test_sensor_role(self):
        assert role_of("Sensor-PIR-class") == "Sensor"

    def test_actuator_role(self):
        assert role_of("Motor-Servo-class") == "Actuator"

    def test_unknown_defaults_structural(self):
        assert role_of("Unknown-Widget-class") == "Structural"


# ── face_out_for ───────────────────────────────────────────────

class TestFaceOutFor:
    def test_display_returns_face(self):
        assert face_out_for("Display-OLED-class") == "face"

    def test_led_matrix_returns_face(self):
        assert face_out_for("LED-Matrix-class") == "face"

    def test_lighting_led_returns_face(self):
        # "LED" substring match
        assert face_out_for("Lighting-LED-RGB-class") == "face"

    def test_pir_sensor_returns_side_front(self):
        assert face_out_for("Sensor-PIR-class") == "side-front"

    def test_ultrasonic_returns_side_front(self):
        assert face_out_for("Sensor-Ultrasonic-class") == "side-front"

    def test_soil_moisture_returns_bottom(self):
        assert face_out_for("Sensor-SoilMoisture-class") == "bottom"

    def test_usb_returns_valid_choice(self):
        random.seed(42)
        result = face_out_for("USB-5V-class")
        assert result in ("side-back", "bottom")

    def test_pump_returns_bottom(self):
        assert face_out_for("Pump-Water-class") == "bottom"

    def test_buzzer_returns_top(self):
        assert face_out_for("Buzzer-Active-class") == "top"

    def test_speaker_returns_top(self):
        assert face_out_for("Speaker-class") == "top"

    def test_generic_returns_valid_side(self):
        random.seed(0)
        result = face_out_for("Relay-Module-class")
        assert result in ("side-front", "side-back", "side-left", "side-right")


# ── placement_reason ───────────────────────────────────────────

class TestPlacementReason:
    def test_heavy_component_mentions_weight(self):
        # Motor-DC-class weighs 30g
        reason = placement_reason("Motor-DC-class", "bottom-center")
        assert "重量" in reason or "30" in reason

    def test_high_thermal_mentions_heat(self):
        # RaspberryPi-class thermal = 3000mW
        reason = placement_reason("RaspberryPi-class", "mid-center")
        assert "發熱" in reason or "3000" in reason

    def test_sensor_mentions_detection(self):
        reason = placement_reason("Sensor-PIR-class", "top-center")
        assert "感測器" in reason

    def test_display_mentions_user_facing(self):
        reason = placement_reason("Display-OLED-class", "top-center")
        assert "顯示" in reason or "燈光" in reason

    def test_usb_mentions_maintenance(self):
        reason = placement_reason("USB-5V-class", "bottom-center")
        assert "電源" in reason or "USB" in reason

    def test_pump_mentions_water(self):
        reason = placement_reason("Pump-Water-class", "bottom-center")
        assert "水泵" in reason

    def test_motor_mentions_axis(self):
        reason = placement_reason("Motor-Servo-class", "mid-center")
        assert "馬達" in reason

    def test_fallback_generic_reason(self):
        # Joystick: weight=12, thermal not in dict => fallback
        reason = placement_reason("Joystick-class", "mid-left")
        assert "mid-left" in reason or "平衡佈局" in reason

    def test_max_two_reasons(self):
        # Motor-DC: heavy(30g) + Motor keyword => at most 2 joined by delimiter
        reason = placement_reason("Motor-DC-class", "bottom-center")
        parts = reason.split("；")
        assert len(parts) <= 2


# ── _template_in_scope ─────────────────────────────────────────

class TestTemplateInScope:
    def test_indoor_template_in_scope(self):
        t = {"env": "indoor_desktop", "aux": ["Sensor-PIR-class"]}
        assert _template_in_scope(t) is True

    def test_outdoor_env_out_of_scope(self):
        t = {"env": "outdoor_garden", "aux": []}
        assert _template_in_scope(t) is False

    def test_one_multiaxis_in_scope(self):
        t = {"env": "indoor_desktop", "aux": ["Motor-Servo-class", "Sensor-PIR-class"]}
        assert _template_in_scope(t) is True

    def test_two_multiaxis_out_of_scope(self):
        t = {"env": "indoor_desktop",
             "aux": ["Motor-Servo-class", "Motor-Stepper-class"]}
        assert _template_in_scope(t) is False

    def test_no_env_key_in_scope(self):
        t = {"aux": []}
        assert _template_in_scope(t) is True


# ── vary_template ──────────────────────────────────────────────

class TestVaryTemplate:
    @pytest.fixture
    def base_template(self):
        return {
            "name": "test_project",
            "brain": "Arduino-Uno-class",
            "power": "USB-5V-class",
            "control": "Button-class",
            "aux": ["Sensor-PIR-class", "Buzzer-Active-class"],
            "env": "indoor_desktop",
        }

    def test_returns_new_dict(self, base_template):
        random.seed(99)
        result = vary_template(base_template)
        assert result is not base_template
        assert result["aux"] is not base_template["aux"]

    def test_result_stays_in_scope(self, base_template):
        """After vary, result must pass _template_in_scope."""
        for seed in range(50):
            random.seed(seed)
            result = vary_template(base_template)
            assert _template_in_scope(result), f"seed={seed} produced out-of-scope"

    def test_outdoor_env_corrected(self):
        """If random mutation gives outdoor env, vary_template fixes it."""
        # Force env to outdoor then verify correction
        t = {
            "name": "x", "brain": "ESP32-class", "power": "USB-5V-class",
            "control": "Button-class", "aux": ["Sensor-PIR-class"],
            "env": "outdoor_park",
        }
        result = vary_template(t)
        assert not result.get("env", "").startswith("outdoor")


# ── components_of ──────────────────────────────────────────────

class TestComponentsOf:
    def test_basic_extraction(self):
        t = {"brain": "A", "power": "B", "control": "C", "aux": ["D", "E"]}
        assert components_of(t) == ["A", "B", "C", "D", "E"]

    def test_empty_aux(self):
        t = {"brain": "A", "power": "B", "control": "C", "aux": []}
        assert components_of(t) == ["A", "B", "C"]

    def test_duplicate_aux(self):
        t = {"brain": "A", "power": "B", "control": "C", "aux": ["D", "D"]}
        assert components_of(t) == ["A", "B", "C", "D", "D"]


# ── env_cfg_of ─────────────────────────────────────────────────

class TestEnvCfgOf:
    def test_indoor_desktop(self):
        t = {"env": "indoor_desktop"}
        cfg = env_cfg_of(t)
        assert cfg["name"] == "indoor_desktop"
        assert cfg["waterproof"] is False

    def test_indoor_humid(self):
        t = {"env": "indoor_humid"}
        cfg = env_cfg_of(t)
        assert cfg["name"] == "indoor_humid"

    def test_soil_contact(self):
        t = {"env": "soil_contact"}
        cfg = env_cfg_of(t)
        assert cfg["name"] == "soil_contact"

    def test_unknown_env_defaults_first(self):
        t = {"env": "nonexistent_biome"}
        cfg = env_cfg_of(t)
        assert cfg["name"] == ENVIRONMENTS[0]["name"]

    def test_missing_env_key_defaults(self):
        t = {}
        cfg = env_cfg_of(t)
        assert cfg["name"] == "indoor_desktop"


# ── SSOT constant integrity ────────────────────────────────────

class TestSSOTConstants:
    def test_weight_g_all_positive(self):
        for ctype, w in WEIGHT_G.items():
            assert w > 0, f"{ctype} has non-positive weight"

    def test_thermal_mw_non_negative(self):
        # SSOT20: THERMAL_MW now reads through specs (all 43 classes), which
        # legitimately includes passive components at 0.0 (Battery-AA, Button,
        # Switch, Chassis, USB-5V). Positivity of active components is asserted
        # in test_thermal_mw.py; here we only require non-negative.
        for ctype, t in THERMAL_MW.items():
            assert t >= 0, f"{ctype} has negative thermal"

    def test_current_ma_non_negative(self):
        for ctype, c in CURRENT_MA.items():
            assert c >= 0, f"{ctype} has negative current"

    def test_zones_has_10_entries(self):
        assert len(ZONES) == 10

    def test_face_outs_has_7_entries(self):
        assert len(FACE_OUTS) == 7

    def test_environments_has_3_entries(self):
        assert len(ENVIRONMENTS) == 3

    def test_category_templates_has_6_categories(self):
        assert len(CATEGORY_TEMPLATES) == 6
        expected = {"Gardening", "Smart_Home", "Robotics",
                    "Interactive_Art", "Security", "Education"}
        assert set(CATEGORY_TEMPLATES.keys()) == expected
