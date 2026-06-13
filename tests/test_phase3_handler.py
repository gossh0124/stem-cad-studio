"""tests/test_phase3_handler.py -- Phase 3 Handler unit tests.

Coverage targets:
  1. _check_io -- GPIO pin allocation validation
  2. _check_gpio_pin_current -- per-pin 20mA safety check (EW1)
  3. _check_3v3_rail -- 3.3V rail cumulative current check (EW2)
  4. _check_level_shift -- bidirectional level shift detection (EW4)
  5. _check_stall_current -- motor stall current budget (EW6)
  6. _check_wiring -- basic wiring constraint rules
  7. _check_interference -- 2D AABB keep-out zone collision

Groups 8-9 (execute integration, constants) split to test_phase3_handler_integration.py.
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from copy import deepcopy

from services.phase_handlers.phase3_handler import (
    Phase3Handler,
    _BRAIN_GPIO,
    _BRAIN_BUS,
    _COMPONENT_IO,
    _DISCRETE_COMPONENTS,
    _GPIO_DIRECT_COMPONENTS,
    _GPIO_MAX_MA_PER_PIN,
    _BUS_PROTOCOLS,
)
from services.shared.models import Job, PhaseID
from lib.bom_calculator import BomSummary


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def handler():
    return Phase3Handler()


@pytest.fixture
def basic_job():
    return Job(job_id="test-001", project_name="TestProject")


def _make_comp(role, ctype, qty=1, spec=None):
    """Helper to build a component dict."""
    return {
        "role": role,
        "type": ctype,
        "qty": qty,
        "spec": spec or {"length_mm": 50, "width_mm": 30, "height_mm": 10},
    }


def _basic_bridge(components=None):
    """Create minimal bridge dict for testing."""
    if components is None:
        components = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Power", "USB-5V-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),
        ]
    return {"components": components, "_project_output_dir": os.path.join(os.environ.get("TEMP", "/tmp"), "test_p3")}


# ═══════════════════════════════════════════════════════════════
# 1. _check_io -- GPIO pin allocation validation
# ═══════════════════════════════════════════════════════════════

class TestCheckIO:
    """GPIO availability vs component requirements."""

    def test_single_sensor_within_budget(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),
        ]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is True
        assert any(r["level"] == "OK" for r in results)

    def test_no_components_passes(self, handler):
        comps = [_make_comp("Brain", "Arduino-Uno-class")]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is True
        assert results[0]["msg"] == "無需額外 GPIO 驗證"

    def test_pwm_overflow_fails(self, handler):
        """Arduino-Uno has 6 PWM pins; 7 servos should fail."""
        comps = [_make_comp("Brain", "Arduino-Uno-class")]
        comps += [_make_comp("Actuator", "Motor-Servo-class") for _ in range(7)]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is False
        assert any("pwm" in r["rule"].lower() for r in results if r["level"] == "ERROR")

    def test_analog_overflow_fails(self, handler):
        """Arduino-Uno has 6 analog; 7 light sensors should fail."""
        comps = [_make_comp("Brain", "Arduino-Uno-class")]
        comps += [_make_comp("Sensor", "Sensor-Light-class") for _ in range(7)]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is False
        assert any("analog" in r["msg"].lower() for r in results if r["level"] == "ERROR")

    def test_esp32_has_more_gpio(self, handler):
        """ESP32 has 16 PWM; 10 servos should still pass."""
        comps = [_make_comp("Brain", "ESP32-class")]
        comps += [_make_comp("Actuator", "Motor-Servo-class") for _ in range(10)]
        ok, results = handler._check_io(comps, "ESP32-class", None)
        assert ok is True

    def test_qty_multiplied(self, handler):
        """qty=3 servos uses 3 PWM pins."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-Servo-class", qty=3),
        ]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is True  # 3 <= 6 PWM

    def test_qty_overflow(self, handler):
        """qty=7 servos exceeds 6 PWM."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-Servo-class", qty=7),
        ]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is False

    def test_unknown_brain_uses_defaults(self, handler):
        comps = [
            _make_comp("Brain", "UnknownBoard-class"),
            _make_comp("Sensor", "Sensor-Light-class"),
        ]
        ok, results = handler._check_io(comps, "UnknownBoard-class", None)
        # Default has analog:6, so 1 sensor passes
        assert ok is True

    def test_power_role_skipped(self, handler):
        """Power components are not counted toward GPIO."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Power", "USB-5V-class"),
        ]
        ok, results = handler._check_io(comps, "Arduino-Uno-class", None)
        assert ok is True


# ═══════════════════════════════════════════════════════════════
# 2. _check_gpio_pin_current -- EW1 per-pin 20mA check
# ═══════════════════════════════════════════════════════════════

class TestCheckGpioPinCurrent:
    """EW1: high-current components need relay/MOSFET driver."""

    def test_no_high_power_components_ok(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is True
        assert results[0]["msg"] == "無高功率 GPIO 直連元件"

    def test_motor_without_relay_fails(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-DC-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is False
        assert any("Relay" in r["msg"] or "MOSFET" in r["msg"]
                   for r in results if r["level"] == "ERROR")

    def test_motor_with_relay_passes(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-DC-class"),
            _make_comp("Control", "Relay-Module-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is True

    def test_motor_with_mosfet_passes(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-DC-class"),
            _make_comp("Control", "MOSFET-Driver-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is True

    def test_pump_without_relay_fails(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Pump-Water-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is False

    def test_brain_and_power_roles_skipped(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Power", "USB-5V-class"),
        ]
        ok, results = handler._check_gpio_pin_current(comps, None)
        assert ok is True


# ═══════════════════════════════════════════════════════════════
# 3. _check_3v3_rail -- EW2 cumulative 3.3V rail current
# ═══════════════════════════════════════════════════════════════

class TestCheck3v3Rail:
    """EW2: 3.3V rail total must stay under RAIL_3V3_BUDGET_MA (50mA)."""

    def test_single_3v3_sensor_within_budget(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),  # 1.5mA, 3.3V
        ]
        warnings = handler._check_3v3_rail(comps, None)
        assert warnings == []

    def test_multiple_3v3_sensors_exceed_budget(self, handler):
        """Many OLED displays at 20mA each on 3.3V rail exceed 50mA."""
        comps = [_make_comp("Brain", "Arduino-Uno-class")]
        # Display-OLED is 20mA at 3.3V; 3x = 60mA > 50mA budget
        comps += [_make_comp("Display", "Display-OLED-class") for _ in range(3)]
        warnings = handler._check_3v3_rail(comps, None)
        assert len(warnings) == 1
        assert "3.3V rail" in warnings[0]

    def test_5v_components_ignored(self, handler):
        """5V components should not count toward 3.3V rail."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Display", "Display-LCD-class"),  # 5V, 25mA
            _make_comp("Actuator", "Motor-Servo-class"),  # 5V
        ]
        warnings = handler._check_3v3_rail(comps, None)
        assert warnings == []

    def test_brain_power_skipped(self, handler):
        comps = [
            _make_comp("Brain", "ESP32-class"),  # 3.3V but role=Brain
            _make_comp("Power", "USB-5V-class"),
        ]
        warnings = handler._check_3v3_rail(comps, None)
        assert warnings == []


# ═══════════════════════════════════════════════════════════════
# 4. _check_level_shift -- EW4 bidirectional voltage check
# ═══════════════════════════════════════════════════════════════

class TestCheckLevelShift:
    """EW4: detect when component voltage > brain GPIO voltage."""

    def test_5v_comp_on_esp32_triggers_warning(self, handler):
        """ESP32 is 3.3V GPIO; Display-LCD (5V, non-discrete) needs level shifter."""
        comps = [
            _make_comp("Brain", "ESP32-class"),
            _make_comp("Display", "Display-LCD-class"),  # 5.0V, not discrete
        ]
        warnings = handler._check_level_shift(comps, 5.0, None)
        assert len(warnings) == 1
        assert "level shifter" in warnings[0]

    def test_3v3_comp_on_arduino_no_warning(self, handler):
        """Arduino Uno is 5V GPIO; 3.3V sensor has no upshift issue."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),  # 3.3V
        ]
        warnings = handler._check_level_shift(comps, 5.0, None)
        assert warnings == []

    def test_discrete_components_skipped(self, handler):
        """Discrete components (e.g., LED, button) bypass level shift check."""
        comps = [
            _make_comp("Brain", "ESP32-class"),
            _make_comp("Input", "Button-class"),  # in _DISCRETE_COMPONENTS
        ]
        warnings = handler._check_level_shift(comps, 5.0, None)
        assert warnings == []

    def test_no_brain_no_crash(self, handler):
        """If no Brain component, should not crash."""
        comps = [_make_comp("Sensor", "Sensor-Ultrasonic-class")]
        warnings = handler._check_level_shift(comps, 5.0, None)
        # No brain found, brain_v defaults to 5.0, so 5V comp vs 5V brain = no issue
        assert warnings == []


# ═══════════════════════════════════════════════════════════════
# 5. _check_stall_current -- EW6 motor stall budget
# ═══════════════════════════════════════════════════════════════

class TestCheckStallCurrent:
    """EW6: motor/pump stall current vs power budget."""

    def test_single_servo_under_usb_budget(self, handler):
        """One servo stalls at 500mA = USB budget (500mA) -- passes."""
        comps = [_make_comp("Actuator", "Motor-Servo-class")]
        warnings = handler._check_stall_current(comps, None, budget_ma=500.0)
        assert warnings == []

    def test_two_servos_exceed_usb_budget(self, handler):
        """Two servos stall at 1000mA > 500mA USB budget."""
        comps = [_make_comp("Actuator", "Motor-Servo-class", qty=2)]
        warnings = handler._check_stall_current(comps, None, budget_ma=500.0)
        assert len(warnings) == 1
        assert "stall" in warnings[0].lower() or "峰值" in warnings[0]

    def test_no_motors_returns_empty(self, handler):
        comps = [
            _make_comp("Sensor", "Sensor-TempHumid-class"),
            _make_comp("Display", "Display-OLED-class"),
        ]
        warnings = handler._check_stall_current(comps, None, budget_ma=500.0)
        assert warnings == []

    def test_pump_stall_exceeds_budget(self, handler):
        """Pump-Water stalls at 600mA > 500mA USB."""
        comps = [_make_comp("Actuator", "Pump-Water-class", qty=1)]
        warnings = handler._check_stall_current(comps, None, budget_ma=500.0)
        assert len(warnings) == 1

    def test_higher_budget_allows_more(self, handler):
        """AC-Adapter budget 2000mA can handle multiple motors."""
        comps = [
            _make_comp("Actuator", "Motor-DC-class", qty=2),  # stall 800*2=1600
        ]
        warnings = handler._check_stall_current(comps, None, budget_ma=2000.0)
        assert warnings == []


# ═══════════════════════════════════════════════════════════════
# 6. _check_wiring -- basic wiring constraint rules
# ═══════════════════════════════════════════════════════════════

class TestCheckWiring:
    """Wiring constraint validation."""

    def test_actuator_without_brain_fails(self, handler):
        comps = [_make_comp("Actuator", "Motor-Servo-class")]
        ok, results = handler._check_wiring(comps, None)
        assert ok is False
        assert any("Actuator" in r["msg"] and "Brain" in r["msg"]
                   for r in results if r["level"] == "ERROR")

    def test_actuator_with_brain_passes(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Actuator", "Motor-Servo-class"),
        ]
        ok, results = handler._check_wiring(comps, None)
        assert ok is True

    def test_sensor_only_passes(self, handler):
        """Sensors don't require Brain for wiring rule."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class"),
            _make_comp("Sensor", "Sensor-TempHumid-class"),
        ]
        ok, results = handler._check_wiring(comps, None)
        assert ok is True


# ═══════════════════════════════════════════════════════════════
# 7. _check_interference -- 2D AABB collision detection
# ═══════════════════════════════════════════════════════════════

class TestCheckInterference:
    """2D AABB keep-out zone collision detection."""

    def test_well_spaced_components_no_collision(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 68, "width_mm": 53, "height_mm": 10}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 15, "width_mm": 12, "height_mm": 8}),
        ]
        result = handler._check_interference(comps, None)
        assert result["ok"] is True
        assert result["collisions"] == []

    def test_single_component_skips(self, handler):
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 68, "width_mm": 53, "height_mm": 10}),
        ]
        result = handler._check_interference(comps, None)
        assert result["ok"] is True
        assert "不足 2 個" in result["msg"]

    def test_no_spec_components_skips(self, handler):
        comps = [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1, "spec": None},
            {"role": "Sensor", "type": "DHT22", "qty": 1, "spec": None},
        ]
        result = handler._check_interference(comps, None)
        assert result["ok"] is True

    def test_keepout_parameter_used(self, handler):
        """Custom keepout_mm parameter should be stored in result."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 50, "width_mm": 30, "height_mm": 10}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 20, "width_mm": 15, "height_mm": 8}),
        ]
        result = handler._check_interference(comps, None, keepout_mm=5.0)
        assert result["keepout_mm"] == 5.0

    def test_missing_length_mm_raises(self, handler):
        """spec exists but missing length_mm -> ValueError."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"width_mm": 30, "height_mm": 10}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 15, "width_mm": 12, "height_mm": 8}),
        ]
        with pytest.raises(ValueError, match="length_mm"):
            handler._check_interference(comps, None)

    def test_missing_width_mm_raises(self, handler):
        """spec exists but missing width_mm -> ValueError."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 68, "height_mm": 10}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 15, "width_mm": 12, "height_mm": 8}),
        ]
        with pytest.raises(ValueError, match="width_mm"):
            handler._check_interference(comps, None)


# ═══════════════════════════════════════════════════════════════
# 8. estimate_layout_chamfer -- geometry guard (V2 salvage)
# ═══════════════════════════════════════════════════════════════

class TestEstimateLayoutChamfer:
    """estimate_layout_chamfer: strict geometry key guard from V2."""

    def test_missing_geometry_raises(self, handler):
        """spec exists but missing height_mm -> ValueError."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 68, "width_mm": 53}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 15, "width_mm": 12, "height_mm": 8}),
        ]
        with pytest.raises(ValueError, match="height_mm"):
            handler._estimate_layout_chamfer(comps, None)

    def test_missing_length_mm_raises(self, handler):
        """spec exists but missing length_mm -> ValueError."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"width_mm": 53, "height_mm": 10}),
        ]
        with pytest.raises(ValueError, match="length_mm"):
            handler._estimate_layout_chamfer(comps, None)

    def test_complete_spec_no_raise(self, handler):
        """Full spec dict should not raise."""
        comps = [
            _make_comp("Brain", "Arduino-Uno-class",
                       spec={"length_mm": 68, "width_mm": 53, "height_mm": 10}),
            _make_comp("Sensor", "Sensor-TempHumid-class",
                       spec={"length_mm": 15, "width_mm": 12, "height_mm": 8}),
        ]
        # Should not raise; result depends on numpy availability
        try:
            result = handler._estimate_layout_chamfer(comps, None)
            assert result.get("status") in ("OK", "WARN", "SKIP")
        except ImportError:
            pytest.skip("numpy not available")

