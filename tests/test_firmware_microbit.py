"""tests/test_firmware_microbit.py -- lib/firmware/microbit.py 單元測試。

測試 _gen_microbit 產生的 micro:bit MicroPython 韌體碼：
  - 基本結構（header / import / while True）
  - 各 sensor/output 組合的 code-gen 邏輯
  - reaction rules（PIR+Buzzer、Ultrasonic+Servo 等）
  - display 整合
"""
from __future__ import annotations

from datetime import date

import pytest

from lib.firmware.microbit import _gen_microbit


# ================================================================
# Helper
# ================================================================

def _code(outputs: list[str] | None = None,
           sensors: list[str] | None = None,
           power: str = "USB-5V",
           project_name: str = "",
           plan: str = "") -> str:
    return _gen_microbit(outputs or [],
                         sensors or [],
                         power,
                         project_name=project_name,
                         plan=plan)


# ================================================================
# Header / scaffolding
# ================================================================

class TestMicrobitHeader:
    def test_header_contains_microbit(self):
        code = _code()
        assert "micro:bit" in code

    def test_header_contains_power(self):
        code = _code(power="Battery-3V")
        assert "Battery-3V" in code

    def test_header_contains_date(self):
        code = _code()
        today = date.today().strftime("%Y/%m/%d")
        assert today in code

    def test_header_contains_cadhllm(self):
        code = _code()
        assert "CADHLLM" in code

    def test_microbit_import(self):
        code = _code()
        assert "from microbit import *" in code

    def test_while_true_loop(self):
        code = _code()
        assert "while True:" in code

    def test_display_scroll_cadhllm(self):
        code = _code()
        assert 'display.scroll("CADHLLM")' in code

    def test_sleep_at_end(self):
        code = _code()
        assert "sleep(200)" in code

    def test_ide_mention(self):
        code = _code()
        assert "Mu Editor" in code or "MakeCode" in code


# ================================================================
# Default behavior -- no outputs, no sensors
# ================================================================

class TestDefaultButtonLogic:
    def test_button_a_pressed(self):
        code = _code()
        assert "button_a.is_pressed()" in code

    def test_button_b_pressed(self):
        code = _code()
        assert "button_b.is_pressed()" in code

    def test_image_heart(self):
        code = _code()
        assert "Image.HEART" in code


# ================================================================
# Sensor imports and reading
# ================================================================

class TestSensorUltrasonic:
    def test_imports_machine(self):
        code = _code(sensors=["Ultrasonic"])
        assert "import machine" in code

    def test_imports_utime(self):
        code = _code(sensors=["Ultrasonic"])
        assert "import utime" in code

    def test_trig_write(self):
        code = _code(sensors=["Ultrasonic"])
        assert "write_digital(1)" in code

    def test_time_pulse(self):
        code = _code(sensors=["Ultrasonic"])
        assert "time_pulse_us" in code

    def test_dist_cm_variable(self):
        code = _code(sensors=["Ultrasonic"])
        assert "dist_cm" in code


class TestSensorTempHumid:
    def test_imports_i2c(self):
        code = _code(sensors=["TempHumid"])
        assert "from microbit import i2c" in code

    def test_temperature_call(self):
        code = _code(sensors=["TempHumid"])
        assert "temperature()" in code


class TestSensorLight:
    def test_light_read(self):
        code = _code(sensors=["Light"])
        assert "read_light_level()" in code

    def test_light_conditional(self):
        """Without ext display, Light should trigger display.show logic."""
        code = _code(sensors=["Light"])
        assert "light_val < 80" in code


class TestSensorSoilMoisture:
    def test_soil_analog(self):
        code = _code(sensors=["SoilMoisture"])
        assert "read_analog()" in code

    def test_soil_no_display_shows_image(self):
        code = _code(sensors=["SoilMoisture"])
        assert "Image.SAD" in code or "Image.HAPPY" in code


class TestSensorPIR:
    def test_pir_digital_read(self):
        code = _code(sensors=["PIR"])
        assert "read_digital()" in code


class TestSensorIR:
    def test_ir_digital_read(self):
        # Phase 1：IR 已建模（COMP_PIN_NEEDS["IR"] + WIRING_TEMPLATES["IR"]），
        # microbit firmware p('IR','OUT') 取得分配腳位，產出 read_digital()。
        code = _code(sensors=["IR"])
        assert "read_digital()" in code


# ================================================================
# Output components
# ================================================================

class TestOutputBuzzer:
    def test_music_import(self):
        code = _code(outputs=["Buzzer_Active"])
        assert "import music" in code

    def test_passive_buzzer_music(self):
        code = _code(outputs=["Buzzer_Passive"])
        assert "import music" in code

    def test_buzzer_button_trigger(self):
        code = _code(outputs=["Buzzer_Active"])
        assert "music.pitch(440, 200)" in code


class TestOutputServo:
    def test_servo_machine_import(self):
        code = _code(outputs=["Servo"])
        assert "import machine as _m" in code

    def test_servo_button_a(self):
        code = _code(outputs=["Servo"])
        assert "write_analog(26)" in code

    def test_servo_button_b(self):
        code = _code(outputs=["Servo"])
        assert "write_analog(128)" in code


class TestOutputNeoPixel:
    def test_neopixel_import(self):
        code = _code(outputs=["NeoPixel"])
        assert "import neopixel" in code

    def test_neopixel_init(self):
        code = _code(outputs=["NeoPixel"])
        assert "neopixel.NeoPixel" in code

    def test_neopixel_button_trigger(self):
        code = _code(outputs=["NeoPixel"])
        assert "np.show()" in code


class TestOutputOLED:
    def test_oled_import(self):
        code = _code(outputs=["OLED"])
        assert "SSD1306_I2C" in code

    def test_oled_init(self):
        code = _code(outputs=["OLED"])
        assert "oled = SSD1306_I2C(128, 64, i2c)" in code

    def test_oled_no_sensor_shows_cadhllm(self):
        code = _code(outputs=["OLED"])
        assert "CADHLLM" in code

    def test_oled_show(self):
        code = _code(outputs=["OLED"])
        assert "oled.show()" in code


class TestOutputLCD:
    def test_lcd_import(self):
        code = _code(outputs=["LCD"])
        assert "I2cLcd" in code

    def test_lcd_init(self):
        code = _code(outputs=["LCD"])
        assert "lcd = I2cLcd(i2c, 0x27, 2, 16)" in code

    def test_lcd_no_sensor_ready(self):
        code = _code(outputs=["LCD"])
        assert "CADHLLM Ready" in code


# ================================================================
# Sensor + output reaction rules
# ================================================================

class TestReactions:
    def test_pir_buzzer(self):
        code = _code(outputs=["Buzzer_Active"], sensors=["PIR"])
        assert "if motion:" in code
        assert "music.pitch(1000, 200)" in code

    def test_pir_neopixel(self):
        code = _code(outputs=["NeoPixel"], sensors=["PIR"])
        assert "if motion:" in code
        assert "(255, 0, 0)" in code

    def test_ultrasonic_buzzer(self):
        code = _code(outputs=["Buzzer_Passive"], sensors=["Ultrasonic"])
        assert "dist_cm < 20" in code
        assert "music.pitch(2000, 100)" in code

    def test_ultrasonic_servo(self):
        code = _code(outputs=["Servo"], sensors=["Ultrasonic"])
        assert "angle" in code
        assert "write_analog" in code

    def test_soil_relay(self):
        code = _code(outputs=["Relay"], sensors=["SoilMoisture"])
        assert "soil_val > 600" in code
        assert "write_digital(1)" in code


# ================================================================
# Display with sensor integration
# ================================================================

class TestDisplaySensorIntegration:
    def test_oled_shows_temp(self):
        code = _code(outputs=["OLED"], sensors=["TempHumid"])
        assert "Temp:" in code

    def test_oled_shows_light(self):
        code = _code(outputs=["OLED"], sensors=["Light"])
        assert "Light:" in code

    def test_oled_shows_dist(self):
        code = _code(outputs=["OLED"], sensors=["Ultrasonic"])
        assert "Dist:" in code

    def test_oled_shows_soil(self):
        code = _code(outputs=["OLED"], sensors=["SoilMoisture"])
        assert "Soil:" in code

    def test_lcd_shows_temp(self):
        code = _code(outputs=["LCD"], sensors=["TempHumid"])
        assert "Temp:" in code

    def test_lcd_shows_ultrasonic(self):
        code = _code(outputs=["LCD"], sensors=["Ultrasonic"])
        assert "cm" in code


# ================================================================
# TempHumid without ext display
# ================================================================

class TestTempHumidNoDisplay:
    def test_scroll_temp(self):
        code = _code(sensors=["TempHumid"])
        assert "display.scroll" in code
        assert "C" in code


# ================================================================
# Project name / plan in header
# ================================================================

class TestProjectHeader:
    def test_project_name_in_header(self):
        code = _code(project_name="MyProject")
        assert "MyProject" in code

    def test_plan_in_header(self):
        code = _code(plan="This is a test plan")
        assert "This is a test plan" in code


# ================================================================
# Multiple component combos
# ================================================================

class TestCombinations:
    def test_multiple_sensors(self):
        code = _code(sensors=["TempHumid", "Ultrasonic"])
        assert "temperature()" in code
        assert "time_pulse_us" in code

    def test_buzzer_handled_by_reaction_not_button(self):
        """When buzzer is handled by PIR reaction, button trigger should NOT appear."""
        code = _code(outputs=["Buzzer_Active"], sensors=["PIR"])
        # The PIR reaction handles the buzzer
        assert "music.pitch(1000, 200)" in code
        # Default button trigger should be suppressed
        assert "music.pitch(440, 200)" not in code
