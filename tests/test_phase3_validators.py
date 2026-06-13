"""test_phase3_validators.py -- Phase III engineering constraint validators."""
import pytest

from services.phase_handlers._phase3_validators import (
    check_io,
    check_gpio_pin_current,
    check_3v3_rail,
    check_level_shift,
    check_stall_current,
    check_wiring,
    _BRAIN_GPIO,
    _COMPONENT_IO,
    _GPIO_DIRECT_COMPONENTS,
)


def _brain(btype="Arduino-Uno-class"):
    return {"role": "Brain", "type": btype, "qty": 1}


def _power():
    return {"role": "Power", "type": "USB-5V-class", "qty": 1}


def _control():
    return {"role": "Control", "type": "Button-class", "qty": 1}


def _comp(role, ctype, qty=1):
    return {"role": role, "type": ctype, "qty": qty}


# ── check_io ────────────────────────────────────────────────


class TestCheckIO:
    def test_basic_components_pass(self):
        comps = [_brain(), _power(), _control(),
                 _comp("Sensor", "Sensor-PIR-class")]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is True

    def test_too_many_digital_pins(self):
        comps = [_brain(), _power()]
        for i in range(20):
            comps.append(_comp("Control", "Button-class"))
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is False
        err = [r for r in results if r["level"] == "ERROR"]
        assert len(err) > 0

    def test_esp32_has_more_gpio(self):
        comps = [_brain("ESP32-class"), _power()]
        for i in range(15):
            comps.append(_comp("Control", "Button-class"))
        ok, _ = check_io(comps, "ESP32-class")
        assert ok is True

    def test_i2c_overflow_arduino(self):
        comps = [_brain(), _power(),
                 _comp("Display", "Display-OLED-class"),
                 _comp("Display", "Display-LCD-class")]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is False

    def test_brain_power_excluded_from_count(self):
        comps = [_brain(), _power()]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is True

    def test_empty_components(self):
        ok, results = check_io([], "Arduino-Uno-class")
        assert ok is True
        assert any("OK" in r["level"] for r in results)

    def test_multiple_servo_pwm(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Motor-Servo-class", qty=7)]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is False

    def test_analog_sensor_count(self):
        comps = [_brain(), _power(),
                 _comp("Sensor", "Sensor-Light-class"),
                 _comp("Sensor", "Sensor-SoilMoisture-class"),
                 _comp("Control", "Potentiometer-class"),
                 _comp("Control", "Joystick-class")]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is True

    def test_analog_overflow(self):
        comps = [_brain(), _power()]
        for _ in range(7):
            comps.append(_comp("Sensor", "Sensor-Light-class"))
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is False

    def test_unknown_brain_uses_defaults(self):
        comps = [_brain("Unknown-MCU-class"), _power(), _control()]
        ok, results = check_io(comps, "Unknown-MCU-class")
        assert ok is True

    def test_qty_multiplied(self):
        comps = [_brain(), _power(),
                 _comp("Sensor", "Sensor-Ultrasonic-class", qty=8)]
        ok, results = check_io(comps, "Arduino-Uno-class")
        assert ok is False

    @pytest.mark.parametrize("brain", list(_BRAIN_GPIO.keys()))
    def test_all_brains_with_simple_setup(self, brain):
        comps = [_brain(brain), _power(), _control()]
        ok, results = check_io(comps, brain)
        assert ok is True


# ── check_gpio_pin_current ──────────────────────────────────


class TestCheckGpioPinCurrent:
    def test_no_high_power_components(self):
        comps = [_brain(), _power(), _control()]
        ok, results = check_gpio_pin_current(comps)
        assert ok is True
        assert any("OK" in r["level"] for r in results)

    def test_motor_without_relay_fails(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Motor-DC-class")]
        ok, results = check_gpio_pin_current(comps)
        assert ok is False

    def test_motor_with_relay_passes(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Motor-DC-class"),
                 _comp("Actuator", "Relay-Module-class")]
        ok, results = check_gpio_pin_current(comps)
        assert ok is True

    def test_pump_without_relay_fails(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Pump-Water-class")]
        ok, results = check_gpio_pin_current(comps)
        assert ok is False

    def test_neopixel_without_relay(self):
        comps = [_brain(), _power(),
                 _comp("Lighting", "Lighting-NeoPixel-class")]
        ok, results = check_gpio_pin_current(comps)
        assert ok is False

    def test_relay_itself_self_driven(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Relay-Module-class")]
        ok, results = check_gpio_pin_current(comps)
        assert ok is True

    def test_brain_power_skipped(self):
        comps = [_brain(), _power()]
        ok, results = check_gpio_pin_current(comps)
        assert ok is True

    @pytest.mark.parametrize("ctype,ma", [
        (k, v) for k, v in _GPIO_DIRECT_COMPONENTS.items()
        if v > 20.0 and k != "Relay-Module-class"
    ])
    def test_high_power_without_relay_fails(self, ctype, ma):
        comps = [_brain(), _power(), _comp("Actuator", ctype)]
        ok, results = check_gpio_pin_current(comps)
        assert ok is False


# ── check_3v3_rail ──────────────────────────────────────────


class TestCheck3v3Rail:
    def test_no_3v3_components(self):
        comps = [_brain(), _power(), _control()]
        warnings = check_3v3_rail(comps)
        assert len(warnings) == 0

    def test_single_oled_under_budget(self):
        comps = [_brain(), _power(),
                 _comp("Display", "Display-OLED-class")]
        warnings = check_3v3_rail(comps)
        assert len(warnings) == 0

    def test_brain_power_excluded(self):
        comps = [_brain("ESP32-class"), _power()]
        warnings = check_3v3_rail(comps)
        assert len(warnings) == 0


# ── check_level_shift ──────────────────────────────────────


class TestCheckLevelShift:
    def test_no_level_shift_needed(self):
        comps = [_brain(), _power(), _control()]
        warnings = check_level_shift(comps, 5.0)
        assert len(warnings) == 0

    def test_discrete_components_skipped(self):
        comps = [_brain(), _power(),
                 _comp("Sensor", "Sensor-PIR-class")]
        warnings = check_level_shift(comps, 5.0)
        assert len(warnings) == 0

    def test_brain_power_excluded(self):
        comps = [_brain(), _power()]
        warnings = check_level_shift(comps, 5.0)
        assert len(warnings) == 0


# ── check_stall_current ────────────────────────────────────


class TestCheckStallCurrent:
    def test_no_motors(self):
        comps = [_brain(), _power(), _control()]
        warnings = check_stall_current(comps)
        assert len(warnings) == 0

    def test_single_motor_under_budget(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Motor-Servo-class")]
        warnings = check_stall_current(comps, budget_ma=2000.0)
        assert len(warnings) == 0

    def test_many_motors_over_budget(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Motor-DC-class", qty=5)]
        warnings = check_stall_current(comps, budget_ma=500.0)
        assert len(warnings) > 0

    def test_pump_stall_counted(self):
        comps = [_brain(), _power(),
                 _comp("Actuator", "Pump-Water-class", qty=1)]
        warnings = check_stall_current(comps, budget_ma=50.0)
        assert len(warnings) > 0


# ── check_wiring ────────────────────────────────────────────


class TestCheckWiring:
    def test_basic_setup_passes(self):
        comps = [_brain(), _power(), _control(),
                 _comp("Sensor", "Sensor-PIR-class")]
        ok, results = check_wiring(comps)
        assert ok is True

    def test_actuator_without_brain(self):
        comps = [_power(),
                 _comp("Actuator", "Motor-Servo-class")]
        ok, results = check_wiring(comps)
        assert ok is False

    def test_empty_components(self):
        # No-Silent-Fallback: with no Brain component present, the EW8 check
        # refuses to estimate against a default MCU and fails loud (ok=False)
        # instead of silently passing. (If lib.wiring is unavailable the EW8
        # block is skipped via ImportError and basic rules pass; assert the
        # honest verdict either way.)
        ok, results = check_wiring([])
        ew8_err = [r for r in results
                   if r["rule"] == "EW8" and r["level"] == "ERROR"]
        if ew8_err:
            assert ok is False
            assert any("Brain" in r["msg"] for r in ew8_err)
        else:
            assert ok is True
