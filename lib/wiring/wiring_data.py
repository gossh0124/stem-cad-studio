"""
wiring_data.py — 接線資料表（dataclass + 靜態查表）

從 engine.py 拆出，避免 engine 超過 500 行。
engine.py 及外部模組均可直接 import 此模組，
此模組**不可反向 import engine**（避免循環依賴）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List  # noqa: F401 — kept for downstream compat


# ── Component Pin Needs ──────────────────────────────────────
@dataclass
class PinNeed:
    tag: str
    type: str       # "pwm" | "digital" | "analog" | "i2c"
    color: str = "#44cc44"


COMP_PIN_NEEDS: dict[str, list[PinNeed]] = {
    "NeoPixel":     [PinNeed("DIN",  "digital", "#44cc44")],
    "LED_Single":   [PinNeed("+",    "digital", "#ff4444")],
    "LED_RGB":      [PinNeed("R", "pwm", "#ff4444"),
                     PinNeed("G", "pwm", "#44cc44"),
                     PinNeed("B", "pwm", "#4488ff")],
    "Speaker":      [PinNeed("TX",  "digital", "#4488ff"),  # DFPlayer Mini (MP3-Module)
                     PinNeed("RX",  "digital", "#ffaa00")],
    "Buzzer_Active":  [PinNeed("SIG", "digital", "#ff4444")],
    "Buzzer_Passive": [PinNeed("SIG", "pwm",     "#ff4444")],
    "OLED":         [PinNeed("SDA", "i2c",     "#ffaa00"),
                     PinNeed("SCL", "i2c",     "#4488ff")],
    "LCD":          [PinNeed("SDA", "i2c",     "#ffaa00"),
                     PinNeed("SCL", "i2c",     "#4488ff")],
    "Servo":        [PinNeed("SIG", "pwm",     "#ffaa00")],
    "DCMotor":      [PinNeed("ENA", "pwm",     "#ff4444"),
                     PinNeed("IN1", "digital", "#44cc44"),
                     PinNeed("IN2", "digital", "#44aaff")],
    "Stepper":      [PinNeed("IN1", "digital", "#ff4444"),
                     PinNeed("IN2", "digital", "#44cc44"),
                     PinNeed("IN3", "digital", "#44aaff"),
                     PinNeed("IN4", "digital", "#ffaa00")],
    "Relay":        [PinNeed("IN",  "digital", "#44cc44")],
    # Pump: 無 MCU 信號腳，透過 Relay 控制供電
    "TempHumid":    [PinNeed("DATA","digital", "#44cc44")],
    "Ultrasonic":   [PinNeed("TRIG","digital", "#44cc44"),
                     PinNeed("ECHO","digital", "#ffaa00")],
    "PIR":          [PinNeed("OUT", "digital", "#44cc44")],
    "IR":           [PinNeed("OUT", "digital", "#44cc44")],  # FC-51 避障 / VS1838B 遙控接收，3-wire digital_out
    "SoilMoisture": [PinNeed("AO",  "analog",  "#44cc44")],
    "Light":        [PinNeed("LDR", "analog",  "#44cc44")],
    "MSGEQ7":       [PinNeed("OUT", "analog",  "#b392f0"),
                     PinNeed("STROBE", "digital", "#44cc44"),
                     PinNeed("RESET",  "digital", "#ff4444")],
    "Button":       [PinNeed("SIG", "digital", "#44cc44")],
    "Switch":       [PinNeed("SIG", "digital", "#44cc44")],
    # SPI 元件（CS tag 對應 spi map 的 ss 鍵）
    "SD_Card":      [PinNeed("SS",   "spi",     "#ff4444"),
                     PinNeed("MOSI", "spi",     "#44cc44"),
                     PinNeed("MISO", "spi",     "#4488ff"),
                     PinNeed("SCK",  "spi",     "#ffaa00")],
    # UART 元件
    "GPS_Module":   [PinNeed("TX",   "uart",    "#44cc44"),
                     PinNeed("RX",   "uart",    "#ffaa00")],
    "Bluetooth_HC05": [PinNeed("TX", "uart",    "#44cc44"),
                       PinNeed("RX", "uart",    "#ffaa00")],
}

# ── Taxonomy → Short Name Mapping ────────────────────────────
# UI 送來的名稱格式：Sensor-SoilMoisture（已去掉 -class），
# 需對應到 COMP_PIN_NEEDS 的 short name（SoilMoisture）。

_TAXONOMY_TO_SHORT: dict[str, str] = {
    # Sensors
    "Sensor-SoilMoisture": "SoilMoisture",
    "Sensor-TempHumid":    "TempHumid",
    "Sensor-Ultrasonic":   "Ultrasonic",
    "Sensor-PIR":          "PIR",
    "Sensor-IR":           "IR",   # FC-51 紅外避障
    "Remote":              "IR",   # VS1838B 紅外遙控接收（與 Sensor-IR 同 3-wire digital_out 接線）
    "Sensor-Light":        "Light",
    # Outputs / Actuators
    "Lighting-NeoPixel":   "NeoPixel",
    "Lighting-LED-PWM":    "LED_Single",
    "Lighting-LED-RGB":    "LED_RGB",
    "Lighting-LED-Strip":  "NeoPixel",
    "Motor-Servo":         "Servo",
    "Motor-DC":            "DCMotor",
    "Motor-Stepper":       "Stepper",
    "Relay-Module":        "Relay",
    "Pump-Water":          "Pump",
    "Display-OLED":        "OLED",
    "Display-LCD":         "LCD",
    "Display-EInk":        "LCD",
    "Buzzer-Active":       "Buzzer_Active",
    "Buzzer-Passive":      "Buzzer_Passive",
    "MP3-Module":          "Speaker",
    "LED-Matrix":          "OLED",
    "Sensor-MSGEQ7":       "MSGEQ7",
    "Button":              "Button",
    "Switch":              "Switch",
    "Switch-Generic":      "Switch",
}

_BRAIN_TO_KEY: dict[str, str] = {
    "Arduino-Uno": "Arduino", "Arduino-Nano": "Arduino",
    "ESP32": "ESP32", "ESP8266": "ESP32",
    "RaspberryPi": "RPi", "Microbit": "Microbit",
}


# ── Arduino / C++ Library includes ───────────────────────────
COMP_LIBS: dict[str, str] = {
    "NeoPixel":  "#include <Adafruit_NeoPixel.h>",
    "Speaker":   "#include <SoftwareSerial.h>",
    "OLED":      "#include <Adafruit_SSD1306.h>\n#include <Wire.h>",
    "LCD":       "#include <LiquidCrystal_I2C.h>\n#include <Wire.h>",
    "Servo":     "#include <Servo.h>",
    "Stepper":   "#include <Stepper.h>",
    "TempHumid": "#include <DHT.h>",
}


# ── Wiring Templates ────────────────────────────────────────
@dataclass
class WireExtra:
    comp: str
    tag: str | None
    note: str
    color: str = "#44cc44"
    fixed: str | None = None
    passive: dict | None = None  # SWL3: {"kind":"R"|"C","value":str,"topo":"series"|"pullup"|"divider"}


@dataclass
class WiringTemplate:
    label: str
    vcc: str | None
    extra: list[WireExtra] = field(default_factory=list)
    decoupling: str | None = None  # SWL3: IC 去耦電容值 (VCC-GND)，None=該元件不加


WIRING_TEMPLATES: dict[str, WiringTemplate] = {
    "NeoPixel": WiringTemplate("NeoPixel WS2812B 燈條", "5V", [
        WireExtra("DIN", "DIN", "資料線（300Ω 串聯電阻後接）", passive={"kind": "R", "value": "300Ω", "topo": "series"}),
    ], decoupling="100nF"),
    "LED_Single": WiringTemplate("單色 LED 指示燈", None, [
        WireExtra("+", "+", "長腳，串聯 220Ω 電阻", passive={"kind": "R", "value": "220Ω", "topo": "series"}),
    ]),
    "LED_RGB": WiringTemplate("RGB LED (4-pin)", None, [
        WireExtra("R", "R", "PWM，串聯 220Ω", passive={"kind": "R", "value": "220Ω", "topo": "series"}),
        WireExtra("G", "G", "PWM，串聯 220Ω", passive={"kind": "R", "value": "220Ω", "topo": "series"}),
        WireExtra("B", "B", "PWM，串聯 220Ω", passive={"kind": "R", "value": "220Ω", "topo": "series"}),
    ]),
    "Speaker": WiringTemplate("DFPlayer Mini 音樂模組", "5V", [
        WireExtra("TX", "TX", "SoftwareSerial TX（1kΩ 串聯）", passive={"kind": "R", "value": "1kΩ", "topo": "series"}),
        WireExtra("RX", "RX", "SoftwareSerial RX"),
        WireExtra("SPK+", None, "接 8Ω 喇叭正極", "#ff88cc", "SPK"),
        WireExtra("SPK-", None, "接 8Ω 喇叭負極", "#888888", "SPK-"),
    ], decoupling="100nF"),
    "Buzzer_Active": WiringTemplate("有源蜂鳴器模組", "5V", [
        WireExtra("SIG", "SIG", "HIGH/LOW 觸發"),
    ], decoupling="100nF"),
    "Buzzer_Passive": WiringTemplate("被動蜂鳴器", None, [
        WireExtra("SIG", "SIG", "需 PWM 腳（tone()）"),
    ]),
    "OLED": WiringTemplate("SSD1306 OLED 0.96\"", "3.3V", [
        WireExtra("SDA", "SDA", "I2C Data"),
        WireExtra("SCL", "SCL", "I2C Clock"),
    ], decoupling="100nF"),
    "LCD": WiringTemplate("LCD 1602 + I2C 模組", "5V", [
        WireExtra("SDA", "SDA", "I2C（接 I2C 背板）"),
        WireExtra("SCL", "SCL", "I2C（接 I2C 背板）"),
    ], decoupling="100nF"),
    "Servo": WiringTemplate("SG90 伺服馬達", "5V", [
        WireExtra("SIG", "SIG", "PWM 控制腳（50Hz）"),
    ]),
    "DCMotor": WiringTemplate("L298N 馬達驅動", "5V", [
        WireExtra("ENA", "ENA", "PWM 速度控制"),
        WireExtra("IN1", "IN1", "方向控制 A1"),
        WireExtra("IN2", "IN2", "方向控制 A2"),
        WireExtra("+12V", None, "外部 12V 電源", "#ff2200", "EXT"),
    ]),
    "Stepper": WiringTemplate("28BYJ-48 步進馬達 + ULN2003 驅動板", "5V", [
        WireExtra("IN1", "IN1", "線圈 A1"),
        WireExtra("IN2", "IN2", "線圈 A2"),
        WireExtra("IN3", "IN3", "線圈 B1"),
        WireExtra("IN4", "IN4", "線圈 B2"),
    ]),
    "Relay": WiringTemplate("5V 單路繼電器", "5V", [
        WireExtra("IN", "IN", "LOW 觸發"),
        WireExtra("COM", None, "公共接點", "#ff8800", "LOAD"),
    ], decoupling="100nF"),
    "Pump": WiringTemplate("微型水泵（透過繼電器控制）", None, [
        WireExtra("VCC", None, "由 Relay COM/NO 供電", "#ff8800", "Relay.COM"),
    ]),
    "TempHumid": WiringTemplate("DHT22 溫濕度感測器", "5V", [
        WireExtra("DATA", "DATA", "4.7kΩ 上拉至 VCC", passive={"kind": "R", "value": "4.7kΩ", "topo": "pullup"}),
    ], decoupling="100nF"),
    "Ultrasonic": WiringTemplate("HC-SR04 超音波距離感測", "5V", [
        WireExtra("TRIG", "TRIG", "觸發脈衝（10μs HIGH）"),
        WireExtra("ECHO", "ECHO", "回波輸入"),
    ], decoupling="100nF"),
    "PIR": WiringTemplate("HC-SR501 PIR 人體感測", "5V", [
        WireExtra("OUT", "OUT", "HIGH = 偵測到移動"),
    ], decoupling="100nF"),
    "IR": WiringTemplate("IR 數位模組（FC-51 避障 / VS1838B 遙控接收）", "5V", [
        WireExtra("OUT", "OUT", "GPIO 數位輸入：FC-51 LOW=偵測到障礙 / VS1838B=已解碼脈衝"),
    ], decoupling="100nF"),
    "SoilMoisture": WiringTemplate("土壤濕度感測器", "5V", [
        WireExtra("AO", "AO", "類比輸出（0–1023）"),
    ], decoupling="100nF"),
    "Light": WiringTemplate("LDR 光敏電阻", "5V", [
        WireExtra("LDR", "LDR", "10kΩ 分壓", passive={"kind": "R", "value": "10kΩ", "topo": "divider"}),
    ]),
    "MSGEQ7": WiringTemplate("MSGEQ7 音頻頻譜分析器", "5V", [
        WireExtra("OUT", "OUT", "類比輸出（7 頻段）"),
        WireExtra("STROBE", "STROBE", "頻段選擇觸發"),
        WireExtra("RESET", "RESET", "重置序列"),
    ], decoupling="100nF"),
    "Button": WiringTemplate("微動按鈕（含上拉）", None, [
        WireExtra("SIG", "SIG", "INPUT_PULLUP（按下=LOW）"),
    ]),
    "Switch": WiringTemplate("撥動開關", None, [
        WireExtra("SIG", "SIG", "INPUT_PULLUP（ON=LOW）"),
    ]),
}
