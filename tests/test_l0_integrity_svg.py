"""test_l0_integrity_svg.py -- L0 SVG integrity checks."""
import pytest

from lib.verification.l0_integrity import check_svg
from lib.verification.report import Verdict


VALID_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" '
    'viewBox="0 0 100 100">'
    '<rect x="10" y="10" width="80" height="80" fill="blue"/>'
    '</svg>'
)

MINIMAL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">'
    '<circle cx="25" cy="25" r="10"/>'
    '</svg>'
)


class TestCheckSvgString:
    def test_valid_svg_passes(self):
        rpt = check_svg(VALID_SVG)
        assert rpt.verdict == Verdict.PASS
        assert rpt.artifact_type == "svg"

    def test_empty_svg_string_fails(self):
        rpt = check_svg("")
        assert rpt.verdict == Verdict.FAIL

    def test_invalid_xml(self):
        rpt = check_svg("<svg><unclosed")
        assert rpt.verdict == Verdict.FAIL
        parseable = [c for c in rpt.checks if c.name == "parseable"]
        assert parseable[0].verdict == Verdict.FAIL

    def test_svg_with_no_children(self):
        rpt = check_svg('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        has_content = [c for c in rpt.checks if c.name == "has_content"]
        assert len(has_content) > 0
        assert has_content[0].verdict == Verdict.FAIL

    def test_svg_missing_dimensions(self):
        rpt = check_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
        has_dims = [c for c in rpt.checks if c.name == "has_dimensions"]
        assert len(has_dims) > 0
        assert has_dims[0].verdict == Verdict.FAIL

    def test_svg_with_viewbox(self):
        rpt = check_svg(VALID_SVG)
        has_dims = [c for c in rpt.checks if c.name == "has_dimensions"]
        assert has_dims[0].verdict == Verdict.PASS

    def test_svg_width_height_only(self):
        rpt = check_svg(MINIMAL_SVG)
        has_dims = [c for c in rpt.checks if c.name == "has_dimensions"]
        assert has_dims[0].verdict == Verdict.PASS

    def test_report_counts(self):
        rpt = check_svg(VALID_SVG)
        counts = rpt.counts()
        assert counts["PASS"] >= 3
        assert counts["FAIL"] == 0

    def test_custom_name(self):
        rpt = check_svg(VALID_SVG, name="test-schematic")
        assert rpt.artifact == "test-schematic"

    def test_to_dict(self):
        rpt = check_svg(VALID_SVG)
        d = rpt.to_dict()
        assert d["artifact_type"] == "svg"
        assert d["verdict"] == "PASS"
        assert "checks" in d

    def test_to_json(self):
        rpt = check_svg(VALID_SVG)
        j = rpt.to_json()
        assert '"verdict": "PASS"' in j

    def test_exit_code_pass(self):
        rpt = check_svg(VALID_SVG)
        assert rpt.exit_code() == 0

    def test_exit_code_fail(self):
        rpt = check_svg("<svg><bad")
        assert rpt.exit_code() != 0

    def test_render_text(self):
        rpt = check_svg(VALID_SVG)
        text = rpt.render_text()
        assert "PASS" in text
        assert "svg" in text

    def test_complex_svg_from_schematic(self):
        from lib.schematic import generate_svg
        svg = generate_svg("Arduino", "USB-5V", ["LED_Single"], ["PIR"])
        rpt = check_svg(svg)
        assert rpt.verdict == Verdict.PASS
