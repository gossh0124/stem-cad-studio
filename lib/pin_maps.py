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


# ── MCU pin label convention (SSOT for engine.py / csp.py / validate.py) ──────
# The frontend whitelist (v6/config/mcu-ports.js) labels numeric pins per-MCU:
#   Arduino digital → Dxx (its analog/I2C pins are already named A0/A4);
#   ESP32 all → Dxx;  Microbit → Pxx;  RPi → GPxx.
# The prefix applies ONLY to bare-integer pins — named pins (A4, A0) pass through
# unchanged. The old rule (`"" if type=="analog" else "D"`) mis-prefixed Arduino
# I2C "A4" → "DA4" and mis-skipped ESP32 analog 32 → "32"; both were then dropped
# by the frontend whitelist (UND-S2). One function so the wiring engine, the CSP
# allocator and the validator all agree (to_json enrichment matches by label).
_MCU_PIN_PREFIX: dict[str, str] = {"Microbit": "P", "RPi": "GP"}


def mcu_pin_prefix(brain_key: str) -> str:
    """Per-MCU numeric-pin prefix matching the frontend MCU_PORTS whitelist."""
    return _MCU_PIN_PREFIX.get(brain_key, "D")


def label_mcu_pin(brain_key: str, raw_pin: object) -> str:
    """Canonical MCU pin label. Prefix applies to bare-integer pins only;
    named pins (A4 / A0 / GPIOxx) pass through unchanged."""
    s = str(raw_pin)
    return f"{mcu_pin_prefix(brain_key)}{s}" if s.isdigit() else s


def mcu_power_pin(brain_key: str, vcc_voltage: object) -> str:
    """Map a component's nominal VCC ('3.3V' / '5V') to the MCU power-rail pin
    label the frontend whitelist uses ('3V3'/'5V'; Microbit's 3.3V rail is '3V').

    A component template carries a voltage string, NOT a whitelist pin name, so
    'mcu' = '3.3V' was silently dropped by the schematic whitelist (UND-S2). A 5V
    load on Microbit (which has no 5V rail) keeps '5V' so it surfaces as a
    power-feasibility error rather than masquerading as the 3V rail."""
    v = str(vcc_voltage).strip().upper().replace("3.3V", "3V3").replace("3.3", "3V3")
    if v in ("3V3", "3V"):
        return "3V" if brain_key == "Microbit" else "3V3"
    if v in ("5V", "5"):
        return "5V"
    return str(vcc_voltage)  # already a canonical rail name (e.g. 'VIN')
