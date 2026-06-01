"""Tests for lib/pin_maps.py — MCU GPIO map data integrity."""
from __future__ import annotations

import pytest

from lib.pin_maps import _PIN_MAPS, _INPUT_ONLY_PINS, _I2C_HW_PINS


class TestPinMapsStructure:
    """_PIN_MAPS has correct structure for all MCUs."""

    def test_all_mcus_present(self):
        for mcu in ("Arduino", "ESP32", "RPi", "Microbit"):
            assert mcu in _PIN_MAPS

    def test_required_keys(self):
        for mcu, m in _PIN_MAPS.items():
            assert "pwm" in m, f"{mcu} missing pwm"
            assert "digital" in m, f"{mcu} missing digital"
            assert "analog" in m, f"{mcu} missing analog"
            assert "i2c" in m, f"{mcu} missing i2c"

    def test_i2c_has_sda_scl(self):
        for mcu, m in _PIN_MAPS.items():
            i2c = m["i2c"]
            assert "sda" in i2c, f"{mcu} i2c missing sda"
            assert "scl" in i2c, f"{mcu} i2c missing scl"

    def test_lists_are_lists(self):
        for mcu, m in _PIN_MAPS.items():
            assert isinstance(m["pwm"], list), f"{mcu} pwm not list"
            assert isinstance(m["digital"], list), f"{mcu} digital not list"
            assert isinstance(m["analog"], list), f"{mcu} analog not list"


class TestArduinoPins:
    """Arduino pin map specifics."""

    def test_pwm_pins(self):
        pwm = _PIN_MAPS["Arduino"]["pwm"]
        assert 3 in pwm
        assert 11 in pwm
        assert len(pwm) == 6

    def test_analog_format(self):
        analog = _PIN_MAPS["Arduino"]["analog"]
        assert "A0" in analog
        assert "A5" in analog

    def test_spi_present(self):
        spi = _PIN_MAPS["Arduino"]["spi"]
        assert spi["mosi"] == 11
        assert spi["miso"] == 12
        assert spi["sck"] == 13

    def test_uart_present(self):
        uart = _PIN_MAPS["Arduino"]["uart"]
        assert uart["tx"] == 1
        assert uart["rx"] == 0


class TestESP32Pins:
    """ESP32 pin map specifics."""

    def test_has_many_pwm_pins(self):
        assert len(_PIN_MAPS["ESP32"]["pwm"]) >= 15

    def test_analog_adc1(self):
        analog = _PIN_MAPS["ESP32"]["analog"]
        assert 32 in analog
        assert 36 in analog

    def test_input_only_in_map(self):
        m = _PIN_MAPS["ESP32"]
        assert "input_only" in m
        assert 34 in m["input_only"]
        assert 39 in m["input_only"]


class TestRPiPins:
    """RPi pin map specifics."""

    def test_no_analog(self):
        assert _PIN_MAPS["RPi"]["analog"] == []

    def test_has_spi_ce(self):
        spi = _PIN_MAPS["RPi"]["spi"]
        assert "ce0" in spi
        assert "ce1" in spi


class TestMicrobitPins:
    """Microbit pin map specifics."""

    def test_pwm_pins_0_1_2(self):
        assert _PIN_MAPS["Microbit"]["pwm"] == [0, 1, 2]

    def test_analog_includes_p0_p4(self):
        analog = _PIN_MAPS["Microbit"]["analog"]
        for p in (0, 1, 2, 3, 4):
            assert p in analog


class TestInputOnlyPins:
    """_INPUT_ONLY_PINS correctness."""

    def test_esp32_input_only(self):
        assert _INPUT_ONLY_PINS["ESP32"] == {34, 35, 36, 39}

    def test_only_esp32_has_input_only(self):
        assert "Arduino" not in _INPUT_ONLY_PINS


class TestI2CHwPins:
    """_I2C_HW_PINS hardware I2C pairs."""

    def test_all_mcus_present(self):
        for mcu in ("Arduino", "ESP32", "RPi", "Microbit"):
            assert mcu in _I2C_HW_PINS

    def test_arduino_i2c(self):
        assert _I2C_HW_PINS["Arduino"] == ("A4", "A5")

    def test_esp32_i2c(self):
        assert _I2C_HW_PINS["ESP32"] == (21, 22)

    def test_rpi_i2c(self):
        assert _I2C_HW_PINS["RPi"] == (2, 3)

    def test_tuples_length_2(self):
        for mcu, pair in _I2C_HW_PINS.items():
            assert len(pair) == 2, f"{mcu} I2C pair not length 2"
