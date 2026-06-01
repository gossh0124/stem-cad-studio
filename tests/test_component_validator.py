"""tests/test_component_validator.py — role_stats / cross_validate_user_spec /
validate_measurement / estimate_thermal_confidence 驗證。
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
import pytest

from lib.component_validator import (
    role_stats,
    cross_validate_user_spec,
    validate_measurement,
    estimate_thermal_confidence,
    _role_for_type,
    _VALIDATE_FIELDS,
    _FIELD_LABELS,
)


# ── _role_for_type ───────────────────────────────────────────

class TestRoleForType:
    def test_known_sensor_type(self):
        result = _role_for_type("Sensor-Ultrasonic-class")
        assert result == "Sensor"

    def test_known_brain_type(self):
        result = _role_for_type("Arduino-Uno-class")
        assert result == "Brain"

    def test_known_actuator_type(self):
        result = _role_for_type("Motor-Servo-class")
        assert result == "Actuator"

    def test_unknown_type_returns_none(self):
        result = _role_for_type("Nonexistent-class")
        assert result is None


# ── role_stats ───────────────────────────────────────────────

class TestRoleStats:
    def test_sensor_stats_not_empty(self):
        stats = role_stats("Sensor")
        assert len(stats) > 0

    def test_stats_keys_are_validate_fields(self):
        stats = role_stats("Sensor")
        for key in stats:
            assert key in _VALIDATE_FIELDS

    def test_stats_have_expected_subkeys(self):
        stats = role_stats("Sensor")
        for field, s in stats.items():
            assert "median" in s
            assert "sigma" in s
            assert "min" in s
            assert "max" in s
            assert "n" in s

    def test_stats_median_between_min_and_max(self):
        stats = role_stats("Sensor")
        for field, s in stats.items():
            assert s["min"] <= s["median"] <= s["max"]

    def test_stats_sigma_non_negative(self):
        stats = role_stats("Sensor")
        for field, s in stats.items():
            assert s["sigma"] >= 0

    def test_stats_n_at_least_2(self):
        stats = role_stats("Sensor")
        for field, s in stats.items():
            assert s["n"] >= 2

    def test_nonexistent_role_returns_empty(self):
        stats = role_stats("NonexistentRole")
        assert stats == {}

    def test_brain_stats_not_empty(self):
        stats = role_stats("Brain")
        assert len(stats) > 0


# ── cross_validate_user_spec ─────────────────────────────────

class TestCrossValidateUserSpec:
    def test_normal_spec_no_warnings(self):
        """A spec with median values should produce no warnings."""
        stats = role_stats("Sensor")
        # Build a spec that sits at the median for every field
        user_spec = {}
        for f, s in stats.items():
            user_spec[f] = s["median"]
        result = cross_validate_user_spec(user_spec, role="Sensor")
        assert isinstance(result, list)
        # Median values should not trigger warnings
        assert len(result) == 0

    def test_extreme_voltage_triggers_warning(self):
        """An extremely high voltage should trigger a warning or info."""
        user_spec = {"voltage_v": 999.0}
        result = cross_validate_user_spec(user_spec, role="Sensor")
        # At least one entry about voltage
        voltage_warns = [w for w in result if w["field"] == "voltage_v"]
        assert len(voltage_warns) >= 1
        assert voltage_warns[0]["severity"] in ("warning", "info")

    def test_no_role_returns_empty(self):
        result = cross_validate_user_spec({"voltage_v": 5.0}, role=None)
        assert result == []

    def test_role_inferred_from_tags(self):
        user_spec = {
            "voltage_v": 999.0,
            "tags": ["gpio:digital", "measure:distance"],
        }
        result = cross_validate_user_spec(user_spec, role=None)
        # Should infer Sensor from measure: prefix
        voltage_warns = [w for w in result if w["field"] == "voltage_v"]
        assert len(voltage_warns) >= 1

    def test_empty_spec_returns_empty(self):
        result = cross_validate_user_spec({}, role="Sensor")
        assert result == []

    def test_zero_value_skipped(self):
        result = cross_validate_user_spec({"voltage_v": 0}, role="Sensor")
        assert result == []

    def test_negative_value_skipped(self):
        result = cross_validate_user_spec({"voltage_v": -5}, role="Sensor")
        assert result == []

    def test_warning_dict_structure(self):
        user_spec = {"voltage_v": 999.0}
        result = cross_validate_user_spec(user_spec, role="Sensor")
        if result:
            w = result[0]
            assert "field" in w
            assert "label" in w
            assert "unit" in w
            assert "user_value" in w
            assert "median" in w
            assert "sigma" in w
            assert "severity" in w


# ── validate_measurement ─────────────────────────────────────

class TestValidateMeasurement:
    def test_normal_measurement_returns_empty(self):
        stats = role_stats("Sensor")
        measured = {}
        for f in ("length_mm", "width_mm", "height_mm"):
            if f in stats:
                measured[f] = stats[f]["median"]
        result = validate_measurement(measured, "Sensor")
        assert result == []

    def test_extreme_measurement_flags(self):
        measured = {"length_mm": 9999.0}
        result = validate_measurement(measured, "Sensor")
        assert len(result) >= 1
        assert result[0]["severity"] in ("error", "warning", "info")

    def test_empty_measurement_returns_empty(self):
        result = validate_measurement({}, "Sensor")
        assert result == []

    def test_only_physical_fields_checked(self):
        """Only length_mm, width_mm, height_mm are checked."""
        measured = {"voltage_v": 9999.0, "length_mm": 9999.0}
        result = validate_measurement(measured, "Sensor")
        fields = [r["field"] for r in result]
        assert "voltage_v" not in fields

    def test_nonexistent_role(self):
        result = validate_measurement({"length_mm": 10}, "FakeRole")
        assert result == []

    def test_severity_ordering(self):
        """Deviation > 3 sigma should produce 'error'."""
        stats = role_stats("Sensor")
        if "length_mm" in stats:
            median = stats["length_mm"]["median"]
            sigma = stats["length_mm"]["sigma"]
            if sigma > 0:
                extreme = median + 4 * sigma
                result = validate_measurement({"length_mm": extreme}, "Sensor")
                if result:
                    assert result[0]["severity"] == "error"


# ── estimate_thermal_confidence ──────────────────────────────

class TestEstimateThermalConfidence:
    def test_unknown_role(self):
        result = estimate_thermal_confidence(100.0, "FakeRole")
        assert result["confidence"] == "unknown"
        assert result["needs_user_confirm"] is True

    def test_high_confidence(self):
        stats = role_stats("Sensor")
        th = stats.get("thermal_mw")
        if th:
            result = estimate_thermal_confidence(th["median"], "Sensor")
            assert result["confidence"] == "high"
            assert result["needs_user_confirm"] is False

    def test_low_confidence_extreme_value(self):
        stats = role_stats("Sensor")
        th = stats.get("thermal_mw")
        if th and th["sigma"] > 0:
            extreme = th["median"] + 5 * th["sigma"]
            result = estimate_thermal_confidence(extreme, "Sensor")
            assert result["confidence"] == "low"
            assert result["needs_user_confirm"] is True

    def test_result_keys(self):
        stats = role_stats("Sensor")
        th = stats.get("thermal_mw")
        if th:
            result = estimate_thermal_confidence(th["median"], "Sensor")
            expected_keys = {
                "confidence", "deviation_sigma", "median_mw",
                "range_min_mw", "range_max_mw", "n_peers",
                "needs_user_confirm",
            }
            assert set(result.keys()) == expected_keys


# ── _FIELD_LABELS / _VALIDATE_FIELDS constants ───────────────

class TestConstants:
    def test_validate_fields_has_7_entries(self):
        assert len(_VALIDATE_FIELDS) == 7

    def test_field_labels_match_validate_fields(self):
        for f in _VALIDATE_FIELDS:
            assert f in _FIELD_LABELS

    def test_field_labels_are_tuples_of_2(self):
        for f, val in _FIELD_LABELS.items():
            assert isinstance(val, tuple)
            assert len(val) == 2
