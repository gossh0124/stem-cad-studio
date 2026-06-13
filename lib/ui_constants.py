"""lib/ui_constants.py — 前端 UI 專用常數。

從 lib/specs.py 的 POWER_MA 自動派生 UI 功耗表，避免手動重複維護。
"""
from __future__ import annotations
from typing import Dict

from .specs import POWER_MA
from .config import ROLE_PALETTE, ROLE_COLOR_UNKNOWN  # Wave B: role 色單一 SSOT

# UI 端簡稱 → taxonomy -class 名稱
UI_KEY_TO_CLASS: Dict[str, str] = {
    "Arduino":      "Arduino-Uno-class",
    "ESP32":        "ESP32-class",
    "RPi":          "RaspberryPi-class",
    "Microbit":     "Microbit-class",
    "NeoPixel":     "Lighting-NeoPixel-class",
    "LED_Single":   "Lighting-LED-PWM-class",
    "LED_RGB":      "Lighting-LED-RGB-class",
    "LED_PWM":      "Lighting-LED-PWM-class",
    "Speaker":      "Speaker-class",
    "Buzzer":       "Buzzer-Active-class",
    "OLED":         "Display-OLED-class",
    "LCD":          "Display-LCD-class",
    "Servo":        "Motor-Servo-class",
    "DCMotor":      "Motor-DC-class",
    "Relay":        "Relay-Module-class",
    "Pump":         "Pump-Water-class",
    "TempHumid":    "Sensor-TempHumid-class",
    "Ultrasonic":   "Sensor-Ultrasonic-class",
    "PIR":          "Sensor-PIR-class",
    "SoilMoisture": "Sensor-SoilMoisture-class",
    "Light":        "Sensor-Light-class",
}

UI_COMP_MA: Dict[str, float] = {
    ui_key: POWER_MA.get(cls, 0.0)
    for ui_key, cls in UI_KEY_TO_CLASS.items()
}

UI_COMP_ALT: Dict[str, Dict[str, str]] = {
    "Speaker":  {"alt": "Buzzer",   "label": "被動蜂鳴器（Buzzer）"},
    "NeoPixel": {"alt": "LED_RGB",  "label": "RGB LED"},
    "DCMotor":  {"alt": "Servo",    "label": "伺服馬達（Servo）"},
    "Pump":     {"alt": "Relay",    "label": "繼電器（Relay）"},
    "LCD":      {"alt": "OLED",     "label": "OLED 小螢幕"},
}

UI_PROMPT_CORE_PATTERNS: Dict[str, str] = {
    "Speaker":      r"音樂|播放|mp3|speaker|喇叭|music|sound|audio",
    "NeoPixel":     r"燈光|燈效|led strip|燈條|neopixel|彩色燈|光效|夜燈|檯燈|color light|rgb light",
    "LED_PWM":      r"led|light up|glow|brightness|night light|夜燈|亮度調節|調光",
    "Buzzer":       r"蜂鳴|buzzer|嗶|警報|beep|alert",
    "OLED":         r"顯示|螢幕|oled|display|screen",
    "LCD":          r"lcd|顯示|螢幕|screen",
    "Servo":        r"舵機|servo|旋轉|轉動|rotate|angle",
    "DCMotor":      r"馬達|motor|車|移動|小車|drive|wheel",
    "Pump":         r"水泵|pump|澆水|澆花|灌溉|盆栽|植物|water|irrigat",
    "Relay":        r"繼電|relay|開關控制|switch control",
    "Ultrasonic":   r"超音波|距離|避障|ultrasonic|distance|obstacle",
    "PIR":          r"人體|移動感|pir|motion|presence|detects someone|nearby|proximity",
    "TempHumid":    r"溫度|溫濕度|dht|氣溫|temperature|humidity|temp",
    "SoilMoisture": r"土壤|土壤濕度|濕度感測|澆花|盆栽|植物|soil|moisture",
    "Light":        r"光感|光敏|亮度|ambient light|light sensor|ldr|photoresist|brightness",
}

UI_POWER_BUDGETS: Dict[str, int] = {
    "USB-5V": 500, "LiPo": 1500, "AA": 800, "DC-5V": 2000, "auto": 500,
}

# Wave B: 衍生自 ROLE_PALETTE（11 role 單一 SSOT）+ Unknown 降級;保留 'Output'
# 別名（= Actuator 色，向後相容舊呼叫端，TAXONOMY 正名為 Actuator）。
UI_ROLE_COLOR: Dict[str, str] = {
    **ROLE_PALETTE,
    "Output": ROLE_PALETTE["Actuator"],
    "Unknown": ROLE_COLOR_UNKNOWN,
}


def get_ui_constants() -> Dict:
    """回傳 UI 前端所需的完整元件常數（供 /api/v1/components 端點使用）。"""
    return {
        "comp_ma": UI_COMP_MA,
        "comp_alt": UI_COMP_ALT,
        "core_patterns": UI_PROMPT_CORE_PATTERNS,
        "power_budgets": UI_POWER_BUDGETS,
        "role_color": UI_ROLE_COLOR,
    }
