"""Tests for lib/bridge.py — P1->P2 bridge conversion."""
from __future__ import annotations

import pytest

from lib.bridge import (
    build_bom,
    format_bom_dataframe,
    flatten_manifest_to_component_requests,
    select_primary_type,
    bridge_phase1_to_p2_contract,
    P2_SUPPORTED_TYPES,
)


class TestBuildBom:
    """build_bom creates BOM from components list."""

    def test_basic_bom(self):
        components = [{"selected_type": "Arduino-Uno-class", "role": "Brain"}]
        bom = build_bom(components)
        assert len(bom) == 1
        assert bom[0]["class"] == "Arduino-Uno-class"
        assert bom[0]["role"] == "Brain"
        assert bom[0]["price_twd"] == 250

    def test_bom_with_alias(self):
        components = [{"selected_type": "DHT22-Sensor-class", "role": "Sensor"}]
        bom = build_bom(components)
        assert bom[0]["price_twd"] == 90  # Sensor-TempHumid-class price

    def test_bom_unknown_type(self):
        components = [{"selected_type": "Unknown-class", "role": "X"}]
        bom = build_bom(components)
        assert bom[0]["price_twd"] == 0
        assert bom[0]["url"] == ""

    def test_empty_components(self):
        assert build_bom([]) == []

    def test_multiple_components(self):
        components = [
            {"selected_type": "Arduino-Uno-class", "role": "Brain"},
            {"selected_type": "Sensor-PIR-class", "role": "Sensor"},
            {"selected_type": "Relay-Module-class", "role": "Actuator"},
        ]
        bom = build_bom(components)
        assert len(bom) == 3
        total = sum(b["price_twd"] for b in bom)
        assert total == 250 + 70 + 80


class TestFormatBomDataframe:
    """format_bom_dataframe produces markdown table."""

    def test_empty_returns_no_components(self):
        assert format_bom_dataframe([]) == "No components."

    def test_has_table_headers(self):
        bom = [{"role": "Brain", "class": "Arduino-Uno-class", "price_twd": 250, "url": ""}]
        result = format_bom_dataframe(bom)
        assert "Role" in result
        assert "Class" in result
        assert "Price" in result

    def test_has_total_row(self):
        bom = [
            {"role": "Brain", "class": "Arduino-Uno-class", "price_twd": 250, "url": ""},
            {"role": "Sensor", "class": "Sensor-PIR-class", "price_twd": 70, "url": "https://x"},
        ]
        result = format_bom_dataframe(bom)
        assert "320 TWD" in result

    def test_url_becomes_link(self):
        bom = [{"role": "X", "class": "Y", "price_twd": 10, "url": "https://example.com"}]
        result = format_bom_dataframe(bom)
        assert "[LCSC]" in result


class TestFlattenManifest:
    """flatten_manifest_to_component_requests handles various P1 formats."""

    def test_abstract_manifest_dict(self):
        p1 = {
            "abstract_manifest": {
                "Brain": {
                    "recommended_types": ["Arduino-Uno-class"],
                    "tags": ["control"],
                    "inventory_mentions": [],
                    "educational_rationale": "test",
                }
            },
            "auxiliary_manifest": [],
        }
        reqs = flatten_manifest_to_component_requests(p1)
        assert len(reqs) == 1
        assert reqs[0]["role"] == "Brain"
        assert reqs[0]["source"] == "abstract_manifest"

    def test_auxiliary_manifest_list(self):
        p1 = {
            "abstract_manifest": {},
            "auxiliary_manifest": [
                {"role": "Lighting", "recommended_types": ["Lighting-NeoPixel-class"], "tags": ["visual"]},
            ],
        }
        reqs = flatten_manifest_to_component_requests(p1)
        assert len(reqs) == 1
        assert reqs[0]["source"] == "auxiliary_manifest"

    def test_empty_manifests(self):
        p1 = {"abstract_manifest": {}, "auxiliary_manifest": []}
        assert flatten_manifest_to_component_requests(p1) == []

    def test_missing_keys_graceful(self):
        p1 = {}
        assert flatten_manifest_to_component_requests(p1) == []


class TestSelectPrimaryType:
    """select_primary_type priority logic."""

    def test_direct_match(self):
        registry = {"Arduino-Uno-class", "ESP32-class"}
        t, reason, status = select_primary_type(["Arduino-Uno-class"], registry, [])
        assert t == "Arduino-Uno-class"
        assert reason == "direct_match"
        assert status == "resolved"

    def test_alias_resolved(self):
        registry = {"Sensor-TempHumid-class"}
        t, reason, status = select_primary_type(["DHT22-Sensor-class"], registry, [])
        assert t == "Sensor-TempHumid-class"
        assert reason == "alias_resolved"

    def test_unresolved_fallback(self):
        registry = {"Arduino-Uno-class"}
        t, reason, status = select_primary_type(["NonExistent-class"], registry, [])
        assert t == "NonExistent-class"
        assert status == "unresolved"

    def test_empty_candidates(self):
        t, reason, status = select_primary_type([], set(), [])
        assert t == "unknown"
        assert status == "unresolved"

    def test_first_supported_wins(self):
        registry = {"ESP32-class", "Arduino-Uno-class"}
        t, _, _ = select_primary_type(
            ["NonExist", "ESP32-class", "Arduino-Uno-class"], registry, []
        )
        assert t == "ESP32-class"


class TestBridgePhase1ToP2:
    """bridge_phase1_to_p2_contract integration."""

    def test_basic_conversion(self):
        p1 = {
            "abstract_manifest": {
                "Brain": {"recommended_types": ["Arduino-Uno-class"], "tags": [], "inventory_mentions": [], "educational_rationale": ""},
                "Power": {"recommended_types": ["USB-5V-class"], "tags": [], "inventory_mentions": [], "educational_rationale": ""},
            },
            "auxiliary_manifest": [],
            "project_category": "Gardening",
            "confidence_score": 0.9,
        }
        result = bridge_phase1_to_p2_contract(p1)
        assert result["project_category"] == "Gardening"
        assert len(result["components"]) == 2
        assert "bom" in result
        assert result["bom_total_twd"] > 0

    def test_has_stem_context(self):
        p1 = {
            "abstract_manifest": {"Brain": {"recommended_types": ["ESP32-class"], "tags": [], "inventory_mentions": [], "educational_rationale": "IoT"}},
            "auxiliary_manifest": [],
        }
        result = bridge_phase1_to_p2_contract(p1)
        ctx = result["stem_education_context"]
        assert ctx["total_components"] == 1
        assert ctx["has_education_content"] is True


class TestP2SupportedTypes:
    """P2_SUPPORTED_TYPES is dynamically built from config."""

    def test_non_empty(self):
        assert len(P2_SUPPORTED_TYPES) > 30

    def test_contains_core_types(self):
        for t in ("Arduino-Uno-class", "ESP32-class", "USB-5V-class", "Button-class"):
            assert t in P2_SUPPORTED_TYPES

    def test_all_end_with_class(self):
        for t in P2_SUPPORTED_TYPES:
            assert t.endswith("-class"), f"{t} missing -class suffix"
