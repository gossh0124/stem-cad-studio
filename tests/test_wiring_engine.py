"""Tests for lib/wiring/engine.py — pin allocation + wiring resolution."""
from __future__ import annotations

import pytest

from lib.wiring.engine import (
    PIN_POOLS,
    COMP_PIN_NEEDS,
    WIRING_TEMPLATES,
    PinNeed,
    WiringTemplate,
    normalize_comp,
    normalize_brain,
    normalize_comps,
    allocate_pins,
    resolve_wiring,
    to_json,
    PinAllocationError,
)


class TestNormalizeComp:
    """normalize_comp maps taxonomy names to short names."""

    def test_direct_short_name(self):
        assert normalize_comp("NeoPixel") == "NeoPixel"

    def test_taxonomy_with_class_suffix(self):
        assert normalize_comp("Sensor-SoilMoisture-class") == "SoilMoisture"

    def test_taxonomy_without_class_suffix(self):
        assert normalize_comp("Sensor-SoilMoisture") == "SoilMoisture"

    def test_motor_servo(self):
        assert normalize_comp("Motor-Servo-class") == "Servo"
        assert normalize_comp("Motor-Servo") == "Servo"

    def test_display_oled(self):
        assert normalize_comp("Display-OLED") == "OLED"

    def test_lighting_neopixel(self):
        assert normalize_comp("Lighting-NeoPixel") == "NeoPixel"

    def test_unknown_passthrough(self):
        assert normalize_comp("UnknownWidget") == "UnknownWidget"

    def test_strips_whitespace(self):
        assert normalize_comp(" Sensor-PIR ") == "PIR"


class TestNormalizeBrain:
    """normalize_brain maps MCU names to PIN_POOLS keys."""

    def test_arduino_uno_class(self):
        assert normalize_brain("Arduino-Uno-class") == "Arduino"

    def test_arduino_nano(self):
        assert normalize_brain("Arduino-Nano") == "Arduino"

    def test_esp32_class(self):
        assert normalize_brain("ESP32-class") == "ESP32"

    def test_esp8266(self):
        assert normalize_brain("ESP8266") == "ESP32"

    def test_raspberry_pi(self):
        assert normalize_brain("RaspberryPi-class") == "RPi"

    def test_microbit(self):
        assert normalize_brain("Microbit-class") == "Microbit"

    def test_direct_key(self):
        assert normalize_brain("Arduino") == "Arduino"
        assert normalize_brain("ESP32") == "ESP32"

    def test_fallback_to_arduino(self):
        assert normalize_brain("UnknownBoard") == "Arduino"


class TestNormalizeComps:
    """normalize_comps batch-normalizes and deduplicates."""

    def test_basic_list(self):
        result = normalize_comps(["Sensor-PIR-class", "Relay-Module-class"])
        assert result == ["PIR", "Relay"]

    def test_deduplication(self):
        result = normalize_comps(["Sensor-PIR", "Sensor-PIR-class", "PIR"])
        assert result == ["PIR"]

    def test_preserves_order(self):
        result = normalize_comps(["Motor-Servo", "NeoPixel", "Button"])
        assert result == ["Servo", "NeoPixel", "Button"]

    def test_empty_list(self):
        assert normalize_comps([]) == []


class TestPinPools:
    """PIN_POOLS structure is correct for all MCUs."""

    def test_all_mcus_present(self):
        for key in ("Arduino", "ESP32", "RPi", "Microbit"):
            assert key in PIN_POOLS

    def test_pool_has_required_keys(self):
        for key, pool in PIN_POOLS.items():
            assert "pwm" in pool, f"{key} missing pwm"
            assert "digital" in pool, f"{key} missing digital"
            assert "analog" in pool, f"{key} missing analog"
            assert "i2c" in pool, f"{key} missing i2c"

    def test_i2c_has_sda_scl(self):
        for key, pool in PIN_POOLS.items():
            assert "sda" in pool["i2c"], f"{key} i2c missing sda"
            assert "scl" in pool["i2c"], f"{key} i2c missing scl"

    def test_arduino_has_enough_pins(self):
        pool = PIN_POOLS["Arduino"]
        assert len(pool["pwm"]) >= 5
        assert len(pool["digital"]) >= 4
        assert len(pool["analog"]) >= 4


class TestAllocatePins:
    """allocate_pins assigns MCU pins to components."""

    def test_basic_allocation(self):
        result = allocate_pins("Arduino", ["SoilMoisture"])
        assert "allocation" in result
        assert "pin_labels" in result
        assert "SoilMoisture" in result["allocation"]

    def test_analog_pin_for_soil_moisture(self):
        result = allocate_pins("Arduino", ["SoilMoisture"])
        alloc = result["allocation"]["SoilMoisture"]
        assert "AO" in alloc

    def test_i2c_for_oled(self):
        result = allocate_pins("Arduino", ["OLED"])
        alloc = result["allocation"]["OLED"]
        assert "SDA" in alloc
        assert "SCL" in alloc

    def test_multiple_components(self):
        result = allocate_pins("Arduino", ["PIR", "Relay", "Button"])
        assert len(result["allocation"]) == 3

    def test_no_pin_collision(self):
        result = allocate_pins("Arduino", ["PIR", "Relay", "Button", "NeoPixel"])
        all_pins = []
        for comp, pins in result["allocation"].items():
            for tag, pin in pins.items():
                if tag in ("SDA", "SCL"):
                    continue  # i2c shared
                all_pins.append(pin)
        assert len(all_pins) == len(set(all_pins))

    def test_esp32_allocation(self):
        result = allocate_pins("ESP32", ["PIR", "OLED"])
        assert "PIR" in result["allocation"]
        assert "OLED" in result["allocation"]


class TestResolveWiring:
    """resolve_wiring produces wiring info with VCC/GND/signals."""

    def test_basic_resolve(self):
        result = resolve_wiring("Arduino", ["SoilMoisture"])
        assert "SoilMoisture" in result
        info = result["SoilMoisture"]
        assert "label" in info
        assert "pins" in info

    def test_has_vcc_gnd(self):
        result = resolve_wiring("Arduino", ["TempHumid"])
        pins = result["TempHumid"]["pins"]
        pin_comps = [p["comp"] for p in pins]
        assert "VCC" in pin_comps
        assert "GND" in pin_comps

    def test_pin_has_required_fields(self):
        result = resolve_wiring("Arduino", ["PIR"])
        for p in result["PIR"]["pins"]:
            assert "comp" in p
            assert "mcu" in p
            assert "color" in p


class TestToJson:
    """to_json returns complete API-ready structure."""

    def test_has_all_keys(self):
        result = to_json("Arduino", ["SoilMoisture", "Relay"])
        assert "brain" in result
        assert "allocation" in result
        assert "pin_labels" in result
        assert "wiring" in result
        assert "validation" in result
        assert "power_passives" in result

    def test_brain_normalized(self):
        result = to_json("Arduino-Uno-class", ["Sensor-PIR-class"])
        assert result["brain"] == "Arduino"


class TestWiringTemplates:
    """WIRING_TEMPLATES data integrity."""

    def test_all_comp_pin_needs_have_templates(self):
        no_template_ok = {"Pump", "SD_Card", "GPS_Module", "Bluetooth_HC05"}
        for comp in COMP_PIN_NEEDS:
            if comp in no_template_ok:
                continue
            assert comp in WIRING_TEMPLATES, f"{comp} in COMP_PIN_NEEDS but no template"

    def test_template_label_non_empty(self):
        for comp, tmpl in WIRING_TEMPLATES.items():
            assert tmpl.label, f"{comp} template has empty label"


# ================================================================
# Phase 0 接線硬化：'?' → PinAllocationError fail-fast
# ================================================================

class TestPinAllocationFailFast:
    """耗盡 / tag 不符時 fail-fast raise PinAllocationError，不靜默回 '?'。"""

    def test_pool_exhaustion_raises(self):
        # Microbit pin pool 極小；多個不同型元件必耗盡 → 應 raise（非回 '?'）
        many = ["Servo", "DCMotor", "Stepper", "Ultrasonic", "NeoPixel",
                "LED_Single", "Buzzer_Active", "Relay", "PIR", "Button",
                "TempHumid", "Light"]
        with pytest.raises(PinAllocationError):
            allocate_pins("Microbit", many)

    def test_valid_allocation_no_raise_no_questionmark(self):
        # 合法案例（pin 足夠）行為不變：不 raise、無 '?'
        r = allocate_pins("Arduino", ["TempHumid", "LED_Single", "PIR", "SoilMoisture"])
        assert "?" not in str(r["allocation"])
        assert set(r["allocation"]) == {"TempHumid", "LED_Single", "PIR", "SoilMoisture"}

    def test_resolve_wiring_valid_no_raise(self):
        rw = resolve_wiring("Arduino", ["TempHumid", "PIR"])
        assert set(rw) == {"TempHumid", "PIR"}
        # 無 '?' 漏進 pins
        for comp in rw.values():
            for pin in comp["pins"]:
                assert pin["mcu"] != "D?" and pin["mcu"] != "?"
