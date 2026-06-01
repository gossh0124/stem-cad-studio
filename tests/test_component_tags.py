"""Tests for lib/registry/component_tags.py."""
import pytest
from unittest.mock import patch
from dataclasses import dataclass

from lib.registry.component_tags import _split_tags, find_equivalent
from lib.registry.component_spec import TAG_VOCAB_AXIS1, TAG_VOCAB_AXIS2_PREFIXES


class TestSplitTags:
    def test_axis1_recognized(self):
        for tag in list(TAG_VOCAB_AXIS1)[:3]:
            ax1, ax2 = _split_tags([tag])
            assert tag in ax1
            assert ax2 == set()

    def test_axis2_recognized(self):
        prefixes = list(TAG_VOCAB_AXIS2_PREFIXES)
        if prefixes:
            test_tag = prefixes[0] + "test"
            ax1, ax2 = _split_tags([test_tag])
            assert test_tag in ax2
            assert ax1 == set()

    def test_mixed(self):
        ax1_tag = list(TAG_VOCAB_AXIS1)[0] if TAG_VOCAB_AXIS1 else None
        prefix = list(TAG_VOCAB_AXIS2_PREFIXES)[0] if TAG_VOCAB_AXIS2_PREFIXES else None
        if ax1_tag and prefix:
            ax2_tag = prefix + "foo"
            ax1, ax2 = _split_tags([ax1_tag, ax2_tag])
            assert ax1_tag in ax1
            assert ax2_tag in ax2

    def test_empty(self):
        ax1, ax2 = _split_tags([])
        assert ax1 == set()
        assert ax2 == set()

    def test_unknown_tag_neither(self):
        ax1, ax2 = _split_tags(["completely_random_xyz"])
        assert ax1 == set()
        assert ax2 == set()


@dataclass
class FakeSpec:
    tags: list
    voltage_v: float = 5.0
    current_ma: float = 100.0
    _footprint_l: float = 10.0
    _footprint_w: float = 10.0

    def footprint_area(self):
        return self._footprint_l * self._footprint_w


class TestFindEquivalent:
    def _make_registry(self):
        ax1 = list(TAG_VOCAB_AXIS1)[0] if TAG_VOCAB_AXIS1 else "digital"
        prefix = list(TAG_VOCAB_AXIS2_PREFIXES)[0] if TAG_VOCAB_AXIS2_PREFIXES else "fn:"
        ax2 = prefix + "sense"
        return {
            "Target-class": FakeSpec(tags=[ax1, ax2], voltage_v=5.0, current_ma=50.0),
            "Match-class": FakeSpec(tags=[ax1, ax2], voltage_v=5.0, current_ma=100.0),
            "NoOverlap-class": FakeSpec(tags=["zzz_unknown"], voltage_v=5.0, current_ma=100.0),
            "HighVolt-class": FakeSpec(tags=[ax1, ax2], voltage_v=12.0, current_ma=100.0),
            "LowCurrent-class": FakeSpec(tags=[ax1, ax2], voltage_v=5.0, current_ma=10.0),
        }

    def test_finds_match(self):
        reg = self._make_registry()
        result = find_equivalent(
            "Target-class",
            ["Match-class", "NoOverlap-class"],
            registry=reg,
        )
        assert "Match-class" in result

    def test_excludes_no_tag_overlap(self):
        reg = self._make_registry()
        result = find_equivalent(
            "Target-class",
            ["NoOverlap-class"],
            registry=reg,
        )
        assert "NoOverlap-class" not in result

    def test_excludes_voltage_diff(self):
        reg = self._make_registry()
        result = find_equivalent(
            "Target-class",
            ["HighVolt-class"],
            voltage_tol=0.5,
            registry=reg,
        )
        assert "HighVolt-class" not in result

    def test_excludes_insufficient_current(self):
        reg = self._make_registry()
        result = find_equivalent(
            "Target-class",
            ["LowCurrent-class"],
            registry=reg,
        )
        assert "LowCurrent-class" not in result

    def test_self_excluded(self):
        reg = self._make_registry()
        result = find_equivalent(
            "Target-class",
            ["Target-class", "Match-class"],
            registry=reg,
        )
        assert "Target-class" not in result

    def test_unknown_target(self):
        reg = self._make_registry()
        result = find_equivalent("NonExist", ["Match-class"], registry=reg)
        assert result == []

    def test_sorted_by_area_ratio(self):
        ax1 = list(TAG_VOCAB_AXIS1)[0] if TAG_VOCAB_AXIS1 else "digital"
        prefix = list(TAG_VOCAB_AXIS2_PREFIXES)[0] if TAG_VOCAB_AXIS2_PREFIXES else "fn:"
        ax2 = prefix + "act"
        reg = {
            "T": FakeSpec(tags=[ax1, ax2], _footprint_l=10, _footprint_w=10),
            "Close": FakeSpec(tags=[ax1, ax2], _footprint_l=11, _footprint_w=10),
            "Far": FakeSpec(tags=[ax1, ax2], _footprint_l=20, _footprint_w=20),
        }
        result = find_equivalent("T", ["Close", "Far"], registry=reg)
        assert result[0] == "Close"

    def test_empty_candidates(self):
        reg = self._make_registry()
        result = find_equivalent("Target-class", [], registry=reg)
        assert result == []
