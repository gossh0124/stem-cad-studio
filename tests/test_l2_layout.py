"""tests/test_l2_layout.py — VS-L2 schematic layout quality tests.

Covers: _bbox_overlap, _seg_intersect, audit_schematic_layout, check_schematic_svg.
"""
import pytest

from lib.verification.l2_layout import (
    _bbox_overlap,
    _seg_intersect,
    audit_schematic_layout,
    check_schematic_svg,
)
from lib.verification.report import Verdict


# ── _bbox_overlap ──────────────────────────────────────────────

class TestBboxOverlap:
    def test_no_overlap(self):
        assert _bbox_overlap((0, 0, 10, 10), (20, 20, 10, 10)) is False

    def test_overlap(self):
        assert _bbox_overlap((0, 0, 10, 10), (5, 5, 10, 10)) is True

    def test_edge_touch_no_overlap(self):
        assert _bbox_overlap((0, 0, 10, 10), (10, 0, 10, 10)) is False

    def test_contained(self):
        assert _bbox_overlap((0, 0, 20, 20), (5, 5, 5, 5)) is True


# ── _seg_intersect ─────────────────────────────────────────────

class TestSegIntersect:
    def test_crossing(self):
        assert _seg_intersect((0, 0), (10, 10), (0, 10), (10, 0)) is True

    def test_parallel(self):
        assert _seg_intersect((0, 0), (10, 0), (0, 5), (10, 5)) is False

    def test_shared_endpoint_not_counted(self):
        assert _seg_intersect((0, 0), (10, 10), (0, 0), (10, 0)) is False

    def test_no_intersection(self):
        assert _seg_intersect((0, 0), (5, 0), (6, 0), (10, 0)) is False


# ── audit_schematic_layout ─────────────────────────────────────

class TestAuditSchematicLayout:
    def test_empty_pass(self):
        rpt = audit_schematic_layout([], [])
        assert rpt.verdict == Verdict.PASS
        assert len(rpt.checks) == 2

    def test_overlapping_labels_warn(self):
        labels = [
            {"text": "GND", "x": 0, "y": 0, "w": 20, "h": 10},
            {"text": "VCC", "x": 5, "y": 0, "w": 20, "h": 10},
        ]
        rpt = audit_schematic_layout(labels, [])
        overlap_check = [c for c in rpt.checks if c.name == "no_label_overlap"][0]
        assert overlap_check.verdict == Verdict.WARN
        assert overlap_check.metric["n"] == 1

    def test_non_overlapping_pass(self):
        labels = [
            {"text": "GND", "x": 0, "y": 0, "w": 10, "h": 10},
            {"text": "VCC", "x": 100, "y": 0, "w": 10, "h": 10},
        ]
        rpt = audit_schematic_layout(labels, [])
        overlap_check = [c for c in rpt.checks if c.name == "no_label_overlap"][0]
        assert overlap_check.verdict == Verdict.PASS

    def test_many_crossings_warn(self):
        wires = [
            (0, 0, 100, 100),
            (100, 0, 0, 100),
            (50, 0, 50, 100),
            (0, 50, 100, 50),
        ]
        rpt = audit_schematic_layout([], wires, max_crossings=1)
        cross_check = [c for c in rpt.checks if c.name == "wire_crossings_ok"][0]
        assert cross_check.verdict == Verdict.WARN
        assert cross_check.metric["crossings"] > 1

    def test_few_crossings_pass(self):
        wires = [
            (0, 0, 10, 0),
            (20, 0, 30, 0),
        ]
        rpt = audit_schematic_layout([], wires)
        cross_check = [c for c in rpt.checks if c.name == "wire_crossings_ok"][0]
        assert cross_check.verdict == Verdict.PASS
        assert cross_check.metric["crossings"] == 0


# ── check_schematic_svg ────────────────────────────────────────

_VALID_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
  <text x="10" y="20" font-size="12">GND</text>
  <text x="100" y="20" font-size="12">VCC</text>
  <path d="M 0 50 L 100 50" />
  <path d="M 50 0 L 50 100" />
</svg>"""

_OVERLAPPING_TEXT_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">
  <text x="10" y="20" font-size="12">GND</text>
  <text x="12" y="20" font-size="12">VCC</text>
</svg>"""


class TestCheckSchematicSvg:
    def test_valid_svg(self):
        rpt = check_schematic_svg(_VALID_SVG, name="test_schem")
        assert rpt.artifact == "test_schem"
        assert rpt.verdict == Verdict.PASS

    def test_invalid_svg_l0_fail(self):
        rpt = check_schematic_svg("<not-valid-xml!!!>", name="bad")
        assert rpt.verdict == Verdict.FAIL
        assert any(c.layer == "L0" for c in rpt.checks)

    def test_overlapping_text_detected(self):
        rpt = check_schematic_svg(_OVERLAPPING_TEXT_SVG)
        overlap_check = [c for c in rpt.checks if c.name == "no_label_overlap"][0]
        assert overlap_check.verdict == Verdict.WARN
