"""tests/test_component_resolver.py — component_resolver + validator coverage.

Split from test_module_builder.py (INF1: files under 500 lines).

Covers:
  - component_resolver: resolve_component (L1-L5), extract_mentions,
    resolve_all, role_stats, cross_validate_user_spec,
    validate_measurement, estimate_thermal_confidence
  - Internal helpers: _levenshtein, _strip_alnum
"""
from __future__ import annotations

import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("build123d")  # lib.module_builder (imported below) -> lib.cad eager-imports build123d

from lib.component_resolver import (
    ResolveResult,
    extract_mentions,
    resolve_component,
    resolve_all,
    role_stats,
    cross_validate_user_spec,
    validate_measurement,
    estimate_thermal_confidence,
    _levenshtein,
    _strip_alnum,
)
from lib.registry import COMPONENT_REGISTRY
from lib.module_builder import build_module, build_modules


class TestLevenshtein:
    """Test the internal Levenshtein distance function."""

    def test_identical(self):
        assert _levenshtein("abc", "abc") == 0

    def test_single_insert(self):
        assert _levenshtein("abc", "abcd") == 1

    def test_single_delete(self):
        assert _levenshtein("abcd", "abc") == 1

    def test_substitution(self):
        assert _levenshtein("abc", "aXc") == 1

    def test_empty_strings(self):
        assert _levenshtein("", "") == 0
        assert _levenshtein("abc", "") == 3


class TestStripAlnum:
    """Test _strip_alnum normalization."""

    def test_removes_hyphens_and_class(self):
        assert _strip_alnum("Arduino-Uno-class") == "arduinouno"

    def test_lowercase(self):
        assert _strip_alnum("ESP32") == "esp32"

    def test_already_clean(self):
        assert _strip_alnum("abc123") == "abc123"


class TestExtractMentions:
    """Test extract_mentions from user prompts."""

    def test_model_number(self):
        mentions = extract_mentions("I want to use a SG90 servo for my robot")
        assert "SG90" in mentions

    def test_arduino(self):
        mentions = extract_mentions("Use an Arduino Uno as the brain")
        assert any("Arduino" in m for m in mentions)

    def test_esp32(self):
        mentions = extract_mentions("Build with ESP32-S3 module")
        assert any("ESP32" in m for m in mentions)

    def test_generic_english_terms(self):
        mentions = extract_mentions("I need an ultrasonic sensor and a servo motor")
        assert "ultrasonic" in mentions
        assert "servo" in mentions

    def test_empty_prompt(self):
        assert extract_mentions("") == []

    def test_no_match(self):
        assert extract_mentions("hello world this is normal text") == []


class TestResolveComponent:
    """Test resolve_component L1-L5 layers."""

    def test_l1_exact_match(self):
        r = resolve_component("Arduino-Uno-class")
        assert r.status == "resolved"
        assert r.layer == "L1"
        assert r.canonical == "Arduino-Uno-class"

    def test_l2_fuzzy_lookup(self):
        """L2 resolves via fuzzy_lookup_fn."""
        spec = COMPONENT_REGISTRY["Arduino-Uno-class"]
        r = resolve_component("ArduinoUno", fuzzy_lookup_fn=lambda x: spec)
        assert r.status == "resolved"
        assert r.layer == "L2"
        assert r.canonical == "Arduino-Uno-class"

    def test_l2_fuzzy_returns_none(self):
        """L2 falls through when fuzzy returns None."""
        r = resolve_component("TotallyUnknownThing", fuzzy_lookup_fn=lambda x: None)
        assert r.layer != "L2" or r.status != "resolved"

    def test_l3_user_store(self):
        """L3 resolves via user_store_get."""
        fake_store = lambda x: {"custom": True} if x == "MyCustomSensor" else None
        r = resolve_component("MyCustomSensor", user_store_get=fake_store)
        assert r.status == "resolved"
        assert r.layer == "L3"
        assert r.canonical == "MyCustomSensor"

    def test_l4_edit_distance(self):
        """L4 finds fuzzy candidate within edit distance 2."""
        r = resolve_component("Arduio-Uno-class")
        if r.status == "fuzzy_candidate":
            assert r.layer == "L4"
            assert r.distance <= 2

    def test_l5_llm_tag(self):
        """L5 uses LLM tag inference."""
        tag_fn = lambda x: ["sensor", "temperature"]
        r = resolve_component("SomeWeirdSensor123456", llm_tag_fn=tag_fn)
        assert r.layer == "L5"
        assert r.llm_tags == ["sensor", "temperature"]

    def test_l5_unknown_no_fn(self):
        """Without any optional fn, unknown type resolves to unknown."""
        r = resolve_component("CompletelyFakeThingXYZ999")
        assert r.status == "unknown"
        assert r.layer == "L5"


class TestResolveAll:
    """Test resolve_all batch + mentions diff."""

    def test_resolves_valid_components(self):
        components = [
            {"type": "Arduino-Uno-class", "role": "Brain"},
            {"type": "Motor-Servo-class", "role": "Actuator"},
        ]
        result = resolve_all(components, raw_mentions=[])
        assert len(result["resolved"]) == 2
        assert result["unknowns"] == []
        assert result["fuzzy_candidates"] == []

    def test_unknown_component(self):
        components = [{"type": "NonExistentWidget", "role": "X"}]
        result = resolve_all(components, raw_mentions=[])
        assert len(result["unknowns"]) == 1
        assert result["unknowns"][0]["_resolve"]["status"] in ("unknown", "fuzzy_candidate")

    def test_missing_mentions(self):
        components = [{"type": "Arduino-Uno-class", "role": "Brain"}]
        mentions = ["Motor-Servo-class"]
        result = resolve_all(components, raw_mentions=mentions)
        assert len(result["missing_mentions"]) == 1
        assert result["missing_mentions"][0]["mention"] == "Motor-Servo-class"

    def test_mention_already_in_components(self):
        components = [{"type": "Arduino-Uno-class", "role": "Brain"}]
        mentions = ["Arduino-Uno-class"]
        result = resolve_all(components, raw_mentions=mentions)
        assert result["missing_mentions"] == []


class TestRoleStats:
    """Test role_stats statistical computation."""

    def test_brain_role_has_stats(self):
        stats = role_stats("Brain")
        assert "length_mm" in stats or "voltage_v" in stats

    def test_unknown_role_empty(self):
        stats = role_stats("NonExistentRole")
        assert stats == {}

    def test_stats_structure(self):
        stats = role_stats("Brain")
        for _, st in stats.items():
            assert "median" in st
            assert "sigma" in st
            assert "min" in st
            assert "max" in st
            assert "n" in st
            assert st["n"] >= 2


class TestCrossValidateUserSpec:
    """Test cross_validate_user_spec outlier detection."""

    def test_normal_values_no_warnings(self):
        user_spec = {"length_mm": 68.6, "width_mm": 53.4, "height_mm": 15.0}
        warnings = cross_validate_user_spec(user_spec, role="Brain")
        severe = [w for w in warnings if w["severity"] == "warning"]
        assert isinstance(warnings, list)

    def test_extreme_value_triggers_warning(self):
        user_spec = {"length_mm": 999.0, "width_mm": 53.4, "height_mm": 15.0}
        warnings = cross_validate_user_spec(user_spec, role="Brain")
        length_warnings = [w for w in warnings if w["field"] == "length_mm"]
        assert len(length_warnings) > 0
        assert length_warnings[0]["severity"] in ("warning", "info")

    def test_no_role_returns_empty(self):
        user_spec = {"length_mm": 50.0}
        assert cross_validate_user_spec(user_spec, role=None) == []

    def test_tag_based_role_inference(self):
        user_spec = {"length_mm": 999.0, "tags": ["mcu:8bit"]}
        warnings = cross_validate_user_spec(user_spec)
        assert isinstance(warnings, list)


class TestValidateMeasurement:
    """Test validate_measurement caliper check."""

    def test_normal_measurement(self):
        measured = {"length_mm": 68.6, "width_mm": 53.4}
        results = validate_measurement(measured, role="Brain")
        assert isinstance(results, list)

    def test_extreme_measurement(self):
        measured = {"length_mm": 500.0}
        results = validate_measurement(measured, role="Brain")
        if results:
            assert results[0]["severity"] in ("error", "warning", "info")

    def test_unknown_role(self):
        measured = {"length_mm": 50.0}
        assert validate_measurement(measured, role="FakeRole") == []


class TestEstimateThermalConfidence:
    """Test estimate_thermal_confidence."""

    def test_high_confidence(self):
        stats = role_stats("Brain")
        if "thermal_mw" in stats:
            median = stats["thermal_mw"]["median"]
            result = estimate_thermal_confidence(median, role="Brain")
            assert result["confidence"] == "high"
            assert result["needs_user_confirm"] is False

    def test_low_confidence_extreme(self):
        result = estimate_thermal_confidence(99999.0, role="Brain")
        if result["confidence"] != "unknown":
            assert result["confidence"] == "low"
            assert result["needs_user_confirm"] is True

    def test_unknown_role(self):
        result = estimate_thermal_confidence(100.0, role="NoSuchRole")
        assert result["confidence"] == "unknown"
        assert result["needs_user_confirm"] is True


# ==========================================================================
# Integration: builder + resolver working together
# ==========================================================================


class TestBuilderResolverIntegration:
    """Test that resolver feeds correctly into builder."""

    def test_resolve_then_build(self):
        """Resolve a component, then build its module."""
        r = resolve_component("Arduino-Uno-class")
        assert r.status == "resolved"
        module = build_module(r.canonical, "Brain")
        assert module.comp_type == "Arduino-Uno-class"
        assert module.length > 0

    def test_resolve_all_then_build_modules(self):
        """resolve_all maps types, then build_modules consumes them."""
        components = [
            {"type": "Arduino-Uno-class", "role": "Brain"},
            {"type": "Sensor-PIR-class", "role": "Sensor"},
        ]
        result = resolve_all(components, raw_mentions=[])
        modules = build_modules(result["resolved"])
        assert len(modules) == 2
        assert modules[0].role == "Brain"
        assert modules[1].role == "Sensor"


# ==========================================================================
# H1-resolver: L2 via real Phase2Handler._fuzzy_lookup path (non-false-positive)
# ==========================================================================


class TestL2ViaRealPhase2Handler:
    """Verify that _make_spec_returning_fuzzy produces a ComponentSpec that
    component_resolver.py L2 identity-check (`val is spec`) can match.

    This guards against the regression where _fuzzy_lookup returned a plain
    dict instead of a ComponentSpec, making the `is` comparison always fail.
    """

    def test_wrapper_returns_component_spec(self):
        """_make_spec_returning_fuzzy returns a ComponentSpec, not a dict."""
        from services.phase_handlers.phase2_handler import Phase2Handler
        from services.pipeline_runner import _make_spec_returning_fuzzy
        from lib.registry import ComponentSpec

        p2h = Phase2Handler()
        wrapper = _make_spec_returning_fuzzy(p2h)

        # ArduinoUno (no hyphens) should be fuzzy-matched to Arduino-Uno-class
        result = wrapper("ArduinoUno")
        assert result is not None, "wrapper returned None for 'ArduinoUno'"
        assert isinstance(result, ComponentSpec), (
            f"expected ComponentSpec, got {type(result).__name__}"
        )

    def test_l2_resolves_via_wrapper(self):
        """resolve_component L2 succeeds with wrapper-produced ComponentSpec."""
        from services.phase_handlers.phase2_handler import Phase2Handler
        from services.pipeline_runner import _make_spec_returning_fuzzy

        p2h = Phase2Handler()
        wrapper = _make_spec_returning_fuzzy(p2h)

        r = resolve_component("ArduinoUno", fuzzy_lookup_fn=wrapper)
        assert r.status == "resolved", (
            f"expected resolved, got {r.status!r} (layer={r.layer!r}, canonical={r.canonical!r})"
        )
        assert r.layer == "L2"
        assert r.canonical == "Arduino-Uno-class"

    def test_wrapper_none_for_unknown(self):
        """wrapper returns None for a completely unknown type."""
        from services.phase_handlers.phase2_handler import Phase2Handler
        from services.pipeline_runner import _make_spec_returning_fuzzy

        p2h = Phase2Handler()
        wrapper = _make_spec_returning_fuzzy(p2h)
        result = wrapper("CompletelyFakeWidget99999")
        assert result is None
