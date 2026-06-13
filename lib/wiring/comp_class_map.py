"""lib/wiring/comp_class_map.py — single source for the wiring short-name → verified.json
class-name map (PB2 / Path B).

Extracted to its own module so BOTH wiring_data.py (to derive COMP_PIN_NEEDS) and
validate.py can import it without a circular dependency. Imports nothing from the wiring
package — it is a leaf module.
"""
from __future__ import annotations

# wiring short name (used across the wiring/schematic/firmware layers) → verified.json class.
# MCUs + components. Components without a verified.json class (SD_Card/GPS_Module/
# Bluetooth_HC05) are intentionally absent and handled by _PIN_NEEDS_OVERRIDE in wiring_data.
SHORT_TO_CLASS: dict[str, str] = {
    "Arduino": "Arduino-Uno-class",
    "ESP32": "ESP32-class",
    "RPi": "RaspberryPi-class",
    "Microbit": "Microbit-class",
    "NeoPixel": "Lighting-NeoPixel-class",
    "LED_Single": "Lighting-LED-PWM-class",
    "LED_RGB": "Lighting-LED-RGB-class",
    "Speaker": "MP3-Module-class",
    "Buzzer_Active": "Buzzer-Active-class",
    "Buzzer_Passive": "Buzzer-Passive-class",
    "OLED": "Display-OLED-class",
    "LCD": "Display-LCD-class",
    "Servo": "Motor-Servo-class",
    "DCMotor": "L298N-Driver-class",
    "Stepper": "Motor-Stepper-class",
    "Relay": "Relay-Module-class",
    "Pump": "Pump-Water-class",
    "TempHumid": "Sensor-TempHumid-class",
    "Ultrasonic": "Sensor-Ultrasonic-class",
    "PIR": "Sensor-PIR-class",
    "IR": "Sensor-IR-class",
    "SoilMoisture": "Sensor-SoilMoisture-class",
    "Light": "Sensor-Light-class",
    "MSGEQ7": "Sensor-MSGEQ7-class",
    "Button": "Button-class",
    "Switch": "Switch-class",
}

# ── Multi-instance suffix (biped 2026-06-13) ──────────────────────────────
# Directly-MCU-driven components present in qty>1 (e.g. 4×SG90 on a biped) need
# DISTINCT signal pins per unit, so they cannot collapse to one wiring entry the
# way driver-mediated motors do (2×DC motor share one L298N). The bake gives such
# instances a "~N" suffix (Servo, Servo~2, Servo~3, …) so they stay distinct
# identities through allocation / wiring / nets, while every CLASS-level lookup
# (SHORT_TO_CLASS / COMP_PIN_NEEDS / template) strips the suffix via instance_base().
_INSTANCE_SEP = "~"


def instance_base(name: str) -> str:
    """Strip a trailing multi-instance suffix → base name. 'Servo~2' → 'Servo';
    'Motor-Servo-class~2' → 'Motor-Servo-class'. No suffix → returned unchanged."""
    return name.split(_INSTANCE_SEP, 1)[0]
