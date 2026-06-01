"""
pin_maps.py — 全 MCU GPIO map 資料（SSOT for wiring.py / wiring_csp.py）

抽離自 wiring.py，確保 wiring.py 保持 < 500 行。
"""
from __future__ import annotations

# ── CSP 用常數（wiring_csp 也從這裡引入，避免三處重複定義）────
# ESP32 GPIO 34-39 are input-only (no output capability).
_INPUT_ONLY_PINS: dict[str, set] = {
    "ESP32": {34, 35, 36, 39},
}

# Hardware I2C pin pairs (SDA, SCL) per brain.
_I2C_HW_PINS: dict[str, tuple] = {
    "Arduino":  ("A4", "A5"),
    "ESP32":    (21, 22),
    "Microbit": (20, 19),
    "RPi":      (2, 3),
}

# ── 完整 GPIO map（含 SPI / UART）──────────────────────────────
_PIN_MAPS: dict[str, dict] = {
    "Arduino": {
        "pwm":     [3, 5, 6, 9, 10, 11],
        "digital": [2, 4, 7, 8, 12, 13],
        "analog":  ["A0", "A1", "A2", "A3", "A4", "A5"],
        "i2c":     {"sda": "A4", "scl": "A5"},
        "spi":     {"mosi": 11, "miso": 12, "sck": 13, "ss": 10},
        "uart":    {"tx": 1, "rx": 0},
    },
    "ESP32": {
        "pwm":       [2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19,
                      21, 22, 23, 25, 26, 27, 32, 33],
        "digital":   [2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19,
                      21, 22, 23, 25, 26, 27, 32, 33],
        "analog":    [32, 33, 34, 35, 36, 39],   # ADC1: 32-39
        "i2c":       {"sda": 21, "scl": 22},
        "spi":       {"mosi": 23, "miso": 19, "sck": 18, "ss": 5},
        "uart":      {"tx": 1, "rx": 3},
        "input_only": [34, 35, 36, 39],
    },
    "RPi": {
        "pwm":     [12, 13, 18, 19],   # hardware PWM
        "digital": [4, 5, 6, 7, 8, 9, 10, 11, 16, 17,
                    20, 21, 22, 23, 24, 25, 26, 27],
        "analog":  [],                  # RPi 無 ADC
        "i2c":     {"sda": 2, "scl": 3},
        "spi":     {"mosi": 10, "miso": 9, "sck": 11, "ce0": 8, "ce1": 7},
        "uart":    {"tx": 14, "rx": 15},
    },
    "Microbit": {
        "pwm":     [0, 1, 2],
        "digital": [0, 1, 2, 8, 9, 12, 13, 14, 15, 16],
        "analog":  [0, 1, 2, 3, 4, 10],  # P0-P4, P10
        "i2c":     {"sda": 20, "scl": 19},
        "spi":     {"mosi": 15, "miso": 14, "sck": 13},
    },
}
