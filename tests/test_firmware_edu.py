"""
test_firmware_edu.py — Tests for GA-B3 (REACTION_RULES educational coverage)
"""
import logging

import pytest

from lib.firmware.firmware_edu_coverage import check_edu_coverage


# ── Sample firmware code for testing ──────────────────────────
_SAMPLE_FIRMWARE = """
#include <DHT.h>
#include <Servo.h>

#define DHT_PIN 2
#define SERVO_PIN 9
#define LED_PIN 13
#define BUZZER_PIN 8

DHT dht(DHT_PIN, DHT22);
Servo myServo;

void setup() {
    Serial.begin(9600);
    dht.begin();
    myServo.attach(SERVO_PIN);
    pinMode(LED_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
}

void loop() {
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();

    if (temperature > 30) {
        digitalWrite(LED_PIN, HIGH);  // LED warning
        tone(BUZZER_PIN, 1000);       // buzzer alert
    } else {
        digitalWrite(LED_PIN, LOW);
        noTone(BUZZER_PIN);
    }

    myServo.write(map(temperature, 20, 40, 0, 180));
    delay(2000);
}
"""


class TestEduCoverage:
    """Test REACTION_RULES educational label coverage checker."""

    def test_full_coverage(self):
        """All labels are found in firmware code."""
        rules = [
            {"label": "LED 溫度警示"},
            {"label": "蜂鳴器超溫警報"},
            {"label": "馬達溫度連動"},
        ]
        result = check_edu_coverage(rules, _SAMPLE_FIRMWARE)
        assert result["total"] == 3
        assert result["covered"] == 3
        assert result["missing"] == []

    def test_partial_coverage(self):
        """Some labels missing from firmware code."""
        rules = [
            {"label": "LED 控制"},
            {"label": "GPS 定位追蹤"},   # No GPS keywords in sample
            {"label": "RFID 讀卡驗證"},  # No RFID keywords in sample
        ]
        result = check_edu_coverage(rules, _SAMPLE_FIRMWARE)
        assert result["total"] == 3
        assert result["covered"] == 1
        assert "GPS 定位追蹤" in result["missing"]
        assert "RFID 讀卡驗證" in result["missing"]

    def test_empty_rules(self):
        """Empty reaction_rules returns zero counts."""
        result = check_edu_coverage([], _SAMPLE_FIRMWARE)
        assert result == {"total": 0, "covered": 0, "missing": []}

    def test_empty_firmware(self):
        """Empty firmware means nothing is covered."""
        rules = [
            {"label": "LED 控制"},
            {"label": "馬達轉動"},
        ]
        result = check_edu_coverage(rules, "")
        assert result["total"] == 2
        assert result["covered"] == 0
        assert len(result["missing"]) == 2

    def test_low_coverage_warning(self, caplog):
        """Coverage < 70% emits a warning log."""
        rules = [
            {"label": "LED 控制"},
            {"label": "OLED 畫面"},
            {"label": "Stepper 旋轉"},
            {"label": "Relay 切換"},
            {"label": "LCD 背光"},
        ]
        # Only LED matches the sample firmware; others absent
        with caplog.at_level(logging.WARNING):
            result = check_edu_coverage(rules, _SAMPLE_FIRMWARE)
        assert result["covered"] / result["total"] < 0.7
        assert "coverage" in caplog.text.lower() or "70%" in caplog.text

    def test_english_label_matching(self):
        """English words in labels match code identifiers."""
        rules = [
            {"label": "DHT sensor reading"},
            {"label": "Servo motor control"},
        ]
        result = check_edu_coverage(rules, _SAMPLE_FIRMWARE)
        assert result["covered"] == 2

    def test_label_without_text_skipped(self):
        """Rules with empty labels are excluded from total count."""
        rules = [
            {"label": "LED 控制"},
            {"label": ""},
            {"label": "蜂鳴器警報"},
        ]
        result = check_edu_coverage(rules, _SAMPLE_FIRMWARE)
        assert result["total"] == 2
        assert result["covered"] == 2
