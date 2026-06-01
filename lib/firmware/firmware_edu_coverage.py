"""
firmware_edu_coverage.py — REACTION_RULES educational label coverage checker.
Verifies educational labels are reflected in generated firmware code.
"""
from __future__ import annotations

import logging
import re

_log = logging.getLogger(__name__)

# Map Chinese component/action terms to code keywords for fuzzy matching
_LABEL_KEYWORDS: dict[str, list[str]] = {
    "LED": ["led", "LED", "digitalWrite", "analogWrite", "NeoPixel"],
    "蜂鳴器": ["buzzer", "tone", "noTone", "BUZZER"],
    "馬達": ["motor", "servo", "stepper", "Motor", "Servo"],
    "溫度": ["dht", "DHT", "temperature", "temp"],
    "濕度": ["humidity", "humid", "DHT"],
    "超音波": ["ultrasonic", "pulseIn", "TRIG", "ECHO"],
    "PIR": ["pir", "PIR", "motion", "digitalRead"],
    "土壤": ["soil", "moisture", "analogRead"],
    "光": ["ldr", "light", "LDR", "analogRead"],
    "OLED": ["oled", "OLED", "display", "SSD1306"],
    "LCD": ["lcd", "LCD", "LiquidCrystal"],
    "繼電器": ["relay", "RELAY", "Relay"],
    "按鈕": ["button", "Button", "INPUT_PULLUP"],
    "開關": ["switch", "Switch", "digitalRead"],
    "感測": ["sensor", "Sensor", "read"],
    "顯示": ["display", "print", "show"],
    "控制": ["control", "write", "digitalWrite"],
    "通訊": ["Serial", "Wire", "I2C", "SPI"],
    "PWM": ["analogWrite", "pwm", "PWM"],
}


def _extract_keywords(label: str) -> list[str]:
    """Extract searchable keywords from a Chinese/English label."""
    keywords: list[str] = []
    for term, code_words in _LABEL_KEYWORDS.items():
        if term in label:
            keywords.extend(code_words)
    # Also extract any English words from the label itself
    eng_words = re.findall(r"[A-Za-z_]\w+", label)
    keywords.extend(eng_words)
    return keywords


def _label_in_firmware(label: str, firmware_code: str) -> bool:
    """Check if a reaction rule label is represented in firmware code."""
    # Direct substring match (label appears as comment or identifier)
    if label in firmware_code:
        return True
    # Keyword-based fuzzy matching
    keywords = _extract_keywords(label)
    if not keywords:
        return False
    # At least one keyword must appear in the code
    code_lower = firmware_code.lower()
    for kw in keywords:
        if kw.lower() in code_lower:
            return True
    return False


def check_edu_coverage(reaction_rules: list, firmware_code: str) -> dict:
    """Check educational label coverage. Returns {total, covered, missing}."""
    if not reaction_rules:
        return {"total": 0, "covered": 0, "missing": []}

    total = len(reaction_rules)
    covered = 0
    missing: list[str] = []

    for rule in reaction_rules:
        if "label" not in rule:
            raise ValueError("reaction_rule missing label key")
        label = rule["label"]
        if not label:
            total -= 1
            continue
        if _label_in_firmware(label, firmware_code):
            covered += 1
        else:
            missing.append(label)

    coverage_pct = (covered / total * 100) if total > 0 else 0
    if coverage_pct < 70:
        _log.warning(
            "Educational coverage %.1f%% < 70%% threshold — "
            "missing labels: %s",
            coverage_pct, missing,
        )

    return {"total": total, "covered": covered, "missing": missing}
