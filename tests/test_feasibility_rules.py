"""tests/test_feasibility_rules.py — CAPABILITY_RULES / MISSING_CAPABILITY_RULES /
LONG_RUN_PATTERNS 資料表驗證。
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import pytest

from lib.feasibility_rules import (
    CAPABILITY_RULES,
    MISSING_CAPABILITY_RULES,
    LONG_RUN_PATTERNS,
)


# ── CAPABILITY_RULES structure ───────────────────────────────

class TestCapabilityRulesStructure:
    def test_is_list(self):
        assert isinstance(CAPABILITY_RULES, list)

    def test_not_empty(self):
        assert len(CAPABILITY_RULES) >= 2

    def test_required_keys(self):
        required = {
            "rule_id", "description", "intent_patterns",
            "component_match", "severity", "issue",
            "why", "suggested_fix",
        }
        for rule in CAPABILITY_RULES:
            missing = required - set(rule.keys())
            assert not missing, f"Rule {rule.get('rule_id', '?')} missing keys: {missing}"

    def test_rule_ids_unique(self):
        ids = [r["rule_id"] for r in CAPABILITY_RULES]
        assert len(ids) == len(set(ids))

    def test_rule_ids_format(self):
        for rule in CAPABILITY_RULES:
            assert rule["rule_id"].startswith("CAP-"), (
                f"Rule ID {rule['rule_id']!r} does not start with 'CAP-'"
            )

    def test_severity_valid(self):
        for rule in CAPABILITY_RULES:
            assert rule["severity"] in ("error", "warning"), (
                f"Rule {rule['rule_id']} severity {rule['severity']!r} invalid"
            )


# ── CAPABILITY_RULES intent_patterns ─────────────────────────

class TestCapabilityIntentPatterns:
    def test_patterns_are_list(self):
        for rule in CAPABILITY_RULES:
            assert isinstance(rule["intent_patterns"], list)
            assert len(rule["intent_patterns"]) > 0

    def test_patterns_compile(self):
        """All intent_patterns should be valid regex."""
        for rule in CAPABILITY_RULES:
            for pat in rule["intent_patterns"]:
                try:
                    re.compile(pat)
                except re.error as e:
                    pytest.fail(f"Rule {rule['rule_id']} pattern {pat!r} invalid: {e}")

    def test_component_match_compiles(self):
        for rule in CAPABILITY_RULES:
            try:
                re.compile(rule["component_match"])
            except re.error as e:
                pytest.fail(f"Rule {rule['rule_id']} component_match invalid: {e}")


# ── CAP-001 servo-wheel rule ─────────────────────────────────

class TestCAP001:
    @pytest.fixture
    def rule(self):
        return next(r for r in CAPABILITY_RULES if r["rule_id"] == "CAP-001")

    def test_severity_is_error(self, rule):
        assert rule["severity"] == "error"

    def test_matches_servo(self, rule):
        assert re.search(rule["component_match"], "Motor-Servo-class")

    def test_does_not_match_dc_motor(self, rule):
        assert not re.search(rule["component_match"], "Motor-DC-class")

    def test_intent_matches_wheel(self, rule):
        matched = any(re.search(p, "wheel", re.IGNORECASE) for p in rule["intent_patterns"])
        assert matched

    def test_intent_matches_chinese_wheel(self, rule):
        matched = any(re.search(p, "drive") for p in rule["intent_patterns"])
        assert matched


# ── CAP-002 buzzer-mp3 rule ──────────────────────────────────

class TestCAP002:
    @pytest.fixture
    def rule(self):
        return next(r for r in CAPABILITY_RULES if r["rule_id"] == "CAP-002")

    def test_severity_is_warning(self, rule):
        assert rule["severity"] == "warning"

    def test_matches_buzzer(self, rule):
        assert re.search(rule["component_match"], "Buzzer-Active-class")
        assert re.search(rule["component_match"], "Buzzer-Passive-class")

    def test_does_not_match_mp3_module(self, rule):
        assert not re.search(rule["component_match"], "MP3-Module-class")

    def test_intent_matches_mp3(self, rule):
        matched = any(re.search(p, "mp3", re.IGNORECASE) for p in rule["intent_patterns"])
        assert matched


# ── MISSING_CAPABILITY_RULES structure ───────────────────────

class TestMissingCapabilityRulesStructure:
    def test_is_list(self):
        assert isinstance(MISSING_CAPABILITY_RULES, list)

    def test_not_empty(self):
        assert len(MISSING_CAPABILITY_RULES) >= 5

    def test_required_keys(self):
        required = {
            "rule_id", "intent_keywords",
            "required_category", "reason_zh", "reason_en",
        }
        for rule in MISSING_CAPABILITY_RULES:
            missing = required - set(rule.keys())
            assert not missing, f"Rule {rule.get('rule_id', '?')} missing keys: {missing}"

    def test_rule_ids_unique(self):
        ids = [r["rule_id"] for r in MISSING_CAPABILITY_RULES]
        assert len(ids) == len(set(ids))

    def test_rule_ids_format(self):
        for rule in MISSING_CAPABILITY_RULES:
            assert rule["rule_id"].startswith("MISS-"), (
                f"ID {rule['rule_id']!r} does not start with 'MISS-'"
            )

    def test_keywords_are_list(self):
        for rule in MISSING_CAPABILITY_RULES:
            assert isinstance(rule["intent_keywords"], list)
            assert len(rule["intent_keywords"]) > 0


# ── MISSING_CAPABILITY_RULES content ─────────────────────────

class TestMissingCapabilityContent:
    def test_light_rule_exists(self):
        light_rules = [r for r in MISSING_CAPABILITY_RULES if "Light" in r["required_category"]]
        assert len(light_rules) >= 1

    def test_temperature_rule_exists(self):
        temp_rules = [r for r in MISSING_CAPABILITY_RULES if "TempHumid" in r["required_category"]]
        assert len(temp_rules) >= 1

    def test_gps_rule_exists(self):
        gps_rules = [r for r in MISSING_CAPABILITY_RULES if "GPS" in r["required_category"]]
        assert len(gps_rules) >= 1

    def test_all_have_bilingual_reasons(self):
        for rule in MISSING_CAPABILITY_RULES:
            assert len(rule["reason_zh"]) > 0
            assert len(rule["reason_en"]) > 0


# ── LONG_RUN_PATTERNS ────────────────────────────────────────

class TestLongRunPatterns:
    def test_is_list(self):
        assert isinstance(LONG_RUN_PATTERNS, list)

    def test_not_empty(self):
        assert len(LONG_RUN_PATTERNS) >= 4

    def test_elements_are_tuples_of_two(self):
        for item in LONG_RUN_PATTERNS:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_patterns_compile(self):
        for pattern, hours in LONG_RUN_PATTERNS:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Pattern {pattern!r} invalid: {e}")

    def test_hours_positive(self):
        for pattern, hours in LONG_RUN_PATTERNS:
            assert hours > 0, f"Pattern {pattern!r} has non-positive hours: {hours}"

    def test_30_day_pattern_matches(self):
        pat_30d = next(
            (p, h) for p, h in LONG_RUN_PATTERNS
            if h >= 700
        )
        assert re.search(pat_30d[0], "30 day")

    def test_24h_pattern_matches(self):
        pat_24h = [
            (p, h) for p, h in LONG_RUN_PATTERNS
            if h == 24.0
        ]
        assert len(pat_24h) >= 1
        matched = any(re.search(p, "24h") for p, _ in pat_24h)
        assert matched
