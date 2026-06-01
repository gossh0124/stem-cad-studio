"""tests/test_firmware_arduino.py -- lib/firmware/arduino.py 單元測試。

測試 _gen_arduino 產生的 Arduino/ESP32 韌體碼：
  - 基本結構（header / setup / loop）
  - 各 sensor/output 組合的 code-gen 邏輯
  - reaction rules 連動
  - pin mapping 正確性
"""
from __future__ import annotations

import re
from datetime import date

import pytest

from lib.firmware.arduino import _gen_arduino


# ================================================================
# Helper
# ================================================================

def _code(brain: str = "Arduino",
           outputs: list[str] | None = None,
           sensors: list[str] | None = None,
           power: str = "USB-5V") -> str:
    return _gen_arduino(brain,
                        outputs or [],
                        sensors or [],
                        power)


# ================================================================
# Header / scaffolding
# ================================================================

class TestArduinoHeader:
    def test_header_contains_brain(self):
        code = _code(brain="Arduino")
        assert "Arduino" in code

    def test_header_contains_power(self):
        code = _code(power="USB-5V")
        assert "USB-5V" in code

    def test_header_contains_date(self):
        code = _code()
        today = date.today().strftime("%Y/%m/%d")
        assert today in code

    def test_header_contains_cadhllm(self):
        code = _code()
        assert "CADHLLM" in code

    def test_has_setup_function(self):
        code = _code()
        assert "void setup()" in code

    def test_has_loop_function(self):
        code = _code()
        assert "void loop()" in code

    def test_serial_begin_in_setup(self):
        code = _code()
        assert "Serial.begin(9600)" in code

    def test_system_ready_message(self):
        code = _code()
        assert "CADHLLM System Ready" in code


# ================================================================
# ESP32 specifics
# ================================================================

class TestESP32:
    def test_wifi_include(self):
        code = _code(brain="ESP32", outputs=["LED_Single"])
        assert "#include <WiFi.h>" in code

    def test_no_wifi_for_arduino(self):
        code = _code(brain="Arduino", outputs=["LED_Single"])
        assert "WiFi.h" not in code


# ================================================================
# Single output components
# ================================================================

class TestOutputLEDSingle:
    def test_led_pin_define(self):
        code = _code(outputs=["LED_Single"])
        assert "#define LED_PIN" in code

    def test_led_pinmode_in_setup(self):
        code = _code(outputs=["LED_Single"])
        assert "pinMode(LED_PIN, OUTPUT)" in code

    def test_led_blink_in_loop(self):
        code = _code(outputs=["LED_Single"])
        assert "ledState" in code
        assert "LED_BLINK_INTERVAL" in code


class TestOutputLEDRGB:
    def test_rgb_defines(self):
        code = _code(outputs=["LED_RGB"])
        assert "#define LED_R" in code
        assert "#define LED_G" in code
        assert "#define LED_B" in code

    def test_rgb_pinmode(self):
        code = _code(outputs=["LED_RGB"])
        assert "pinMode(LED_R, OUTPUT)" in code


class TestOutputNeoPixel:
    def test_neopixel_include(self):
        code = _code(outputs=["NeoPixel"])
        assert "Adafruit_NeoPixel.h" in code

    def test_neopixel_init(self):
        code = _code(outputs=["NeoPixel"])
        assert "Adafruit_NeoPixel strip" in code
        assert "strip.begin()" in code


class TestOutputServo:
    def test_servo_include(self):
        code = _code(outputs=["Servo"])
        assert "#include <Servo.h>" in code

    def test_servo_attach(self):
        code = _code(outputs=["Servo"])
        assert "myServo.attach(SERVO_PIN)" in code


class TestOutputDCMotor:
    def test_motor_defines(self):
        code = _code(outputs=["DCMotor"])
        assert "#define MOTOR_EN" in code
        assert "#define MOTOR_IN1" in code
        assert "#define MOTOR_IN2" in code

    def test_motor_pinmode(self):
        code = _code(outputs=["DCMotor"])
        assert "pinMode(MOTOR_IN1,OUTPUT)" in code


class TestOutputRelay:
    def test_relay_define(self):
        code = _code(outputs=["Relay"])
        assert "#define RELAY_PIN" in code

    def test_relay_active_low(self):
        code = _code(outputs=["Relay"])
        assert "Active-LOW" in code


class TestOutputOLED:
    def test_oled_include(self):
        code = _code(outputs=["OLED"])
        assert "Adafruit_SSD1306.h" in code

    def test_oled_begin(self):
        code = _code(outputs=["OLED"])
        assert "display.begin" in code


class TestOutputLCD:
    def test_lcd_include(self):
        code = _code(outputs=["LCD"])
        assert "LiquidCrystal_I2C.h" in code

    def test_lcd_init(self):
        code = _code(outputs=["LCD"])
        assert "lcd.init()" in code
        assert "lcd.backlight()" in code


class TestOutputBuzzer:
    def test_active_buzzer(self):
        code = _code(outputs=["Buzzer_Active"])
        assert "#define BUZZER_PIN" in code
        assert "pinMode(BUZZER_PIN, OUTPUT)" in code

    def test_passive_buzzer(self):
        code = _code(outputs=["Buzzer_Passive"])
        assert "#define BUZZER_PIN" in code


# ================================================================
# Sensor components
# ================================================================

class TestSensorTempHumid:
    def test_dht_include(self):
        code = _code(sensors=["TempHumid"])
        assert "#include <DHT.h>" in code

    def test_dht_begin(self):
        code = _code(sensors=["TempHumid"])
        assert "dht.begin()" in code

    def test_read_temperature(self):
        code = _code(sensors=["TempHumid"])
        assert "dht.readTemperature()" in code

    def test_serial_monitor_temp(self):
        code = _code(sensors=["TempHumid"])
        assert "Serial.print" in code


class TestSensorUltrasonic:
    def test_trig_echo_defines(self):
        code = _code(sensors=["Ultrasonic"])
        assert "#define TRIG_PIN" in code
        assert "#define ECHO_PIN" in code

    def test_pulse_in(self):
        code = _code(sensors=["Ultrasonic"])
        assert "pulseIn(ECHO_PIN" in code


class TestSensorPIR:
    def test_pir_define(self):
        code = _code(sensors=["PIR"])
        assert "#define PIR_PIN" in code

    def test_pir_read(self):
        code = _code(sensors=["PIR"])
        assert "digitalRead(PIR_PIN)" in code


class TestSensorSoilMoisture:
    def test_soil_define(self):
        code = _code(sensors=["SoilMoisture"])
        assert "#define SOIL_PIN" in code

    def test_soil_analog_read(self):
        code = _code(sensors=["SoilMoisture"])
        assert "analogRead(SOIL_PIN)" in code


class TestSensorLight:
    def test_light_define(self):
        code = _code(sensors=["Light"])
        assert "#define LIGHT_PIN" in code


# ================================================================
# Sensor + output reaction rules
# ================================================================

class TestReactions:
    def test_pir_buzzer_reaction(self):
        code = _code(outputs=["Buzzer_Active"], sensors=["PIR"])
        assert "motion == 1" in code

    def test_soil_relay_reaction(self):
        code = _code(outputs=["Relay"], sensors=["SoilMoisture"])
        assert "soilPct < 40" in code

    def test_ultrasonic_servo_reaction(self):
        code = _code(outputs=["Servo"], sensors=["Ultrasonic"])
        assert "dist_cm < 30" in code

    def test_light_led_reaction(self):
        code = _code(outputs=["LED_Single"], sensors=["Light"])
        assert "lightPct < 30" in code


# ================================================================
# OLED / LCD display integration with sensors
# ================================================================

class TestDisplayIntegration:
    def test_oled_shows_temp(self):
        code = _code(outputs=["OLED"], sensors=["TempHumid"])
        assert "Temp:" in code
        assert "display.display()" in code

    def test_oled_shows_dist(self):
        code = _code(outputs=["OLED"], sensors=["Ultrasonic"])
        assert "Dist:" in code

    def test_lcd_shows_temp(self):
        code = _code(outputs=["LCD"], sensors=["TempHumid"])
        assert "T:" in code

    def test_oled_no_sensors_shows_ready(self):
        code = _code(outputs=["OLED"])
        assert "CADHLLM Ready" in code

    def test_lcd_no_sensors_shows_ready(self):
        code = _code(outputs=["LCD"])
        assert "CADHLLM Ready" in code


# ================================================================
# Timer / millis logic
# ================================================================

class TestTimerLogic:
    def test_millis_used(self):
        code = _code(outputs=["LED_Single"])
        assert "millis()" in code

    def test_loop_interval(self):
        code = _code(sensors=["TempHumid"])
        assert "LOOP_INTERVAL" in code
        assert "prevMillis_loop" in code


# ================================================================
# Stepper component
# ================================================================

class TestStepper:
    def test_stepper_include(self):
        code = _code(outputs=["Stepper"])
        assert "#include <Stepper.h>" in code

    def test_stepper_defines(self):
        code = _code(outputs=["Stepper"])
        assert "#define STEP_IN1" in code
        assert "#define STEP_IN2" in code
        assert "#define STEP_IN3" in code
        assert "#define STEP_IN4" in code

    def test_stepper_speed(self):
        code = _code(outputs=["Stepper"])
        assert "setSpeed" in code


# ================================================================
# Multiple outputs / sensors combo
# ================================================================

class TestCombinations:
    def test_multiple_sensors(self):
        code = _code(sensors=["TempHumid", "Ultrasonic"])
        assert "dht.readTemperature()" in code
        assert "pulseIn" in code

    def test_multiple_outputs(self):
        code = _code(outputs=["LED_Single", "Servo"])
        assert "#define LED_PIN" in code
        assert "#define SERVO_PIN" in code

    def test_empty_outputs_header(self):
        code = _code(outputs=[])
        assert "()" in code or "Outputs:" in code

    def test_empty_sensors_header(self):
        code = _code(sensors=[])
        assert "Sensors:" in code


# ================================================================
# Output header lists
# ================================================================

class TestOutputListHeader:
    def test_outputs_listed(self):
        code = _code(outputs=["LED_Single", "Servo"])
        assert "LED_Single" in code
        assert "Servo" in code

    def test_sensors_listed(self):
        code = _code(sensors=["PIR", "Light"])
        assert "PIR" in code
        assert "Light" in code
