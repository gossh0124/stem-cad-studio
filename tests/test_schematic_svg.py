"""
test_schematic_svg.py — Tests for GA-B1 (SVG DOM builder) and GA-B2 (wiring_notes)
"""
import xml.etree.ElementTree as ET

import pytest

from lib.schematic import generate_svg
from lib.wiring.notes import generate_wiring_notes
from lib.wiring import resolve_wiring


# ── GA-B1: SVG DOM builder tests ──────────────────────────────

class TestSVGBasicOutput:
    """Test that SVG generation produces valid output."""

    def test_basic_output_is_svg_string(self):
        """generate_svg returns a non-empty string starting with <svg."""
        svg = generate_svg("Arduino", "USB-5V", ["LED_Single"], ["PIR"])
        assert isinstance(svg, str)
        assert svg.startswith("<svg")
        assert svg.endswith("</svg>")

    def test_xml_valid_parse(self):
        """Output is well-formed XML that can be parsed."""
        svg = generate_svg("Arduino", "USB-5V",
                           ["NeoPixel", "Servo"], ["TempHumid", "Ultrasonic"])
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")

    def test_svg_dimensions(self):
        """SVG has correct width/height attributes."""
        svg = generate_svg("Arduino", "USB-5V", ["LED_Single"], [])
        root = ET.fromstring(svg)
        assert root.get("width") == "800"
        assert root.get("height") == "480"

    def test_tooltip_exists_on_component(self):
        """Component <rect> elements contain <title> tooltip children."""
        svg = generate_svg("Arduino", "USB-5V", ["PIR"], [])
        root = ET.fromstring(svg)
        # Find any title elements (namespace-agnostic)
        titles = [el for el in root.iter() if el.tag.endswith("title")]
        assert len(titles) > 0
        # At least one title should have text content
        assert any(t.text for t in titles)

    def test_xml_escape_special_chars(self):
        """Special characters in labels are properly XML-escaped."""
        # Use a component label with special chars (e.g. LCD has +I2C)
        svg = generate_svg("Arduino", "USB-5V", ["LCD"], [])
        # Should parse without error — ET handles escaping automatically
        root = ET.fromstring(svg)
        # Find text elements containing I2C (the + is properly escaped)
        all_text = [el.text for el in root.iter() if el.text and "I2C" in el.text]
        assert len(all_text) > 0

    def test_backward_compat_no_wiring_notes(self):
        """generate_svg works without wiring_notes parameter."""
        svg = generate_svg("Arduino", "USB-5V", ["LED_Single"], ["PIR"])
        assert "<svg" in svg
        root = ET.fromstring(svg)
        assert root is not None

    def test_wiring_notes_tooltip_injected(self):
        """Wire paths contain <title> when wiring_notes is provided."""
        wiring = resolve_wiring("Arduino", ["PIR"])
        # Find the data pin to construct wire_id
        pir_spec = wiring.get("PIR", {})
        data_pins = [p for p in pir_spec.get("pins", [])
                     if p["mcu"] not in ("GND", "5V", "3.3V",
                                         "EXT", "SPK", "SPK-", "LOAD")]
        assert len(data_pins) > 0
        dp = data_pins[0]
        wire_id = f"MCU_{dp['mcu']}_to_PIR_{dp['comp']}"

        notes = {wire_id: "PIR sensor detects motion via digital HIGH"}
        svg = generate_svg("Arduino", "USB-5V", [], ["PIR"],
                           wiring_notes=notes)
        root = ET.fromstring(svg)
        # Find title elements with our injected text
        titles = [el.text for el in root.iter()
                  if el.tag.endswith("title") and el.text]
        assert any("motion" in t for t in titles if t)

    def test_empty_components(self):
        """generate_svg handles empty outputs and sensors gracefully."""
        svg = generate_svg("Arduino", "USB-5V", [], [])
        root = ET.fromstring(svg)
        assert root is not None

    def test_all_brain_types(self):
        """All brain types produce valid SVG."""
        for brain in ["Arduino", "ESP32", "RPi", "Microbit"]:
            svg = generate_svg(brain, "USB-5V", ["LED_Single"], [])
            root = ET.fromstring(svg)
            assert root is not None


# ── GA-B2: wiring_notes tests ─────────────────────────────────

class TestWiringNotes:
    """Test educational wiring note generation."""

    def test_digital_control_note(self):
        """Digital pins get HIGH/LOW explanation."""
        wiring = resolve_wiring("Arduino", ["PIR"])
        notes = generate_wiring_notes(wiring, ["PIR"], brain="Arduino")
        # Should have at least one note containing HIGH/LOW
        digital_notes = [v for v in notes.values() if "HIGH/LOW" in v]
        assert len(digital_notes) > 0

    def test_pwm_note(self):
        """PWM components get pulse-width modulation explanation."""
        wiring = resolve_wiring("Arduino", ["Servo"])
        notes = generate_wiring_notes(wiring, ["Servo"], brain="Arduino")
        pwm_notes = [v for v in notes.values() if "脈寬調變" in v or "PWM" in v]
        assert len(pwm_notes) > 0

    def test_i2c_note(self):
        """I2C components get bus communication explanation."""
        wiring = resolve_wiring("Arduino", ["OLED"])
        notes = generate_wiring_notes(wiring, ["OLED"], brain="Arduino")
        i2c_notes = [v for v in notes.values() if "I2C" in v]
        assert len(i2c_notes) > 0

    def test_analog_note(self):
        """Analog sensors get ADC explanation."""
        wiring = resolve_wiring("Arduino", ["SoilMoisture"])
        notes = generate_wiring_notes(wiring, ["SoilMoisture"], brain="Arduino")
        analog_notes = [v for v in notes.values() if "ADC" in v or "0-1023" in v]
        assert len(analog_notes) > 0

    def test_power_note(self):
        """Components with VCC get power supply explanation."""
        wiring = resolve_wiring("Arduino", ["PIR"])
        notes = generate_wiring_notes(wiring, ["PIR"], brain="Arduino")
        power_notes = [v for v in notes.values() if "供電" in v or "VCC" in v]
        assert len(power_notes) > 0

    def test_empty_components(self):
        """Empty component list returns empty dict."""
        notes = generate_wiring_notes({}, [], brain="Arduino")
        assert notes == {}

    def test_wire_id_format(self):
        """Wire IDs follow MCU_{pin}_to_{comp}_{comp_pin} format."""
        wiring = resolve_wiring("Arduino", ["LED_Single"])
        notes = generate_wiring_notes(wiring, ["LED_Single"], brain="Arduino")
        for wire_id in notes:
            assert wire_id.startswith("MCU_")
            assert "_to_" in wire_id
