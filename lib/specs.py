"""lib/specs.py — 元件硬體規格 SSOT（Single Source of Truth）。

所有元件功耗、單價、電壓、重量、發熱、BOM 連結、命名別名集中於此。
依賴方向：services → lib（此檔）；lib 內部模組直接 import。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict

# ── Component-specs cache loading ───────────────────────────
# Single combined cache derived from data/component_datasheet_verified.json (SSOT).
# Sections: voltage_v / weight_g / thermal_mw / power_ma. Each section is merged as
# _fallback[section] (low priority, for classes absent from verified.json or lacking
# the field) + the SSOT section (high priority). Regenerate via _rebuild_specs_cache().
_SPECS_CACHE_PATH = Path(__file__).parent.parent / "data" / "_component_specs_cache.json"
_VERIFIED_PATH = Path(__file__).parent.parent / "data" / "component_datasheet_verified.json"
_SPECS_LOCK = threading.Lock()
_SPECS_CACHE: dict | None = None

# verified.json field resolution per section (first match wins for voltage)
_VOLTAGE_KEYS = ("voltage_operating_v", "voltage_output_v", "output_voltage_v", "voltage_nominal_v")


def _load_specs_cache() -> dict:
    """Load the raw combined cache dict (lazy, thread-safe, double-checked)."""
    global _SPECS_CACHE
    if _SPECS_CACHE is not None:
        return _SPECS_CACHE
    with _SPECS_LOCK:
        if _SPECS_CACHE is not None:
            return _SPECS_CACHE
        if not _SPECS_CACHE_PATH.exists():
            raise FileNotFoundError(
                f"Specs cache not found: {_SPECS_CACHE_PATH}. "
                'Regenerate: python -c "from lib.specs import _rebuild_specs_cache; _rebuild_specs_cache()"'
            )
        with open(_SPECS_CACHE_PATH, encoding="utf-8") as fh:
            _SPECS_CACHE = json.load(fh)
        return _SPECS_CACHE


def _section(name: str) -> Dict[str, float]:
    """Return one merged section: _fallback[name] (low) overlaid by SSOT section (high)."""
    raw = _load_specs_cache()
    result: Dict[str, float] = {}
    for k, v in raw.get("_fallback", {}).get(name, {}).items():
        if not k.startswith("_"):
            result[k] = float(v)
    for k, v in raw.get(name, {}).items():
        result[k] = float(v)
    return result


def _derive_specs_from_verified() -> Dict[str, Dict[str, float]]:
    """Derive the four SSOT sections from verified.json (no _fallback merge)."""
    with open(_VERIFIED_PATH, encoding="utf-8") as fh:
        vj = json.load(fh)
    voltage: Dict[str, float] = {}
    weight: Dict[str, float] = {}
    thermal: Dict[str, float] = {}
    power: Dict[str, float] = {}
    for cls in (c for c in vj if not c.startswith("_")):
        elec = vj[cls].get("electrical", {})
        phys = vj[cls].get("physical", {})
        for key in _VOLTAGE_KEYS:
            if key in elec:
                voltage[cls] = float(elec[key])
                break
        # installed weight (battery holders carry weight_with_batteries_g)
        if "weight_with_batteries_g" in phys:
            weight[cls] = float(phys["weight_with_batteries_g"])
        elif "weight_g" in phys:
            weight[cls] = float(phys["weight_g"])
        if "thermal_mw" in elec:
            thermal[cls] = float(elec["thermal_mw"])
        if "current_typ_ma" in elec:
            power[cls] = float(elec["current_typ_ma"])
    return {"voltage_v": voltage, "weight_g": weight, "thermal_mw": thermal, "power_ma": power}


def _rebuild_specs_cache(write: bool = True) -> dict:
    """Regenerate data/_component_specs_cache.json from verified.json.

    The SSOT sections are recomputed from verified.json; the hand-maintained
    "_fallback" block (classes absent from verified.json or lacking the field) is
    preserved from the existing cache so non-derivable values are not lost.
    """
    derived = _derive_specs_from_verified()
    existing_fallback: dict = {}
    if _SPECS_CACHE_PATH.exists():
        with open(_SPECS_CACHE_PATH, encoding="utf-8") as fh:
            existing_fallback = json.load(fh).get("_fallback", {})
    cache = {
        "_meta": {
            "source": "data/component_datasheet_verified.json",
            "fields": {
                "voltage_v": "electrical." + "|".join(_VOLTAGE_KEYS),
                "weight_g": "physical.weight_with_batteries_g|weight_g",
                "thermal_mw": "electrical.thermal_mw",
                "power_ma": "electrical.current_typ_ma",
            },
            "note": 'Regenerate: python -c "from lib.specs import _rebuild_specs_cache; _rebuild_specs_cache()"',
        },
        "_fallback": existing_fallback,
        "voltage_v": dict(sorted(derived["voltage_v"].items())),
        "weight_g": dict(sorted(derived["weight_g"].items())),
        "thermal_mw": dict(sorted(derived["thermal_mw"].items())),
        "power_ma": dict(sorted(derived["power_ma"].items())),
    }
    if write:
        global _SPECS_CACHE
        _SPECS_CACHE = None  # invalidate in-process cache
        _SPECS_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return cache


# ── 功耗 (mA) — loaded from data/_component_specs_cache.json ─────
POWER_MA: Dict[str, float] = _section("power_ma")

# ── 單價 (NTD) ────────────────────────────────────────────
PRICE_NTD: Dict[str, int] = {
    "Arduino-Uno-class": 250,   "Arduino-Nano-class": 150,
    "ESP32-class": 180,         "ESP8266-class": 120,
    "RaspberryPi-class": 1500,  "Microbit-class": 650,
    "USB-5V-class": 80,         "Battery-LiPo-class": 60,
    "Battery-AA-class": 40,
    "Sensor-TempHumid-class": 90,   "Sensor-Ultrasonic-class": 50,
    "Sensor-PIR-class": 70,         "Sensor-SoilMoisture-class": 40,
    "Sensor-Light-class": 20,       "Sensor-MSGEQ7-class": 45,
    "Potentiometer-class": 15,  "Remote-class": 25,
    "Joystick-class": 40,       "Switch-Generic-class": 15,
    "Display-OLED-class": 120,  "Display-LCD-class": 90,
    "Display-EInk-class": 200,  "LED-Matrix-class": 80,
    "Motor-Servo-class": 120,   "Motor-DC-class": 180,
    "Motor-Stepper-class": 80,  "Relay-Module-class": 80,
    "Pump-Water-class": 150,
    "L298N-Driver-class": 120,
    "Buzzer-Active-class": 25,  "Buzzer-Passive-class": 20,
    "MP3-Module-class": 90,     "Speaker-class": 150,
    "Lighting-LED-PWM-class": 15,   "Lighting-NeoPixel-class": 120,
    "Lighting-LED-Strip-class": 80, "Lighting-LED-RGB-class": 25,
    "Mist-Atomizer-class": 80,  "Mist-Ultrasonic-class": 120,
    "Chassis-Car-class": 150,
    "Button-class": 10,         "Switch-class": 15,
    "AC-Adapter-class": 150,    "USB-Adapter-class": 120,
    "Sensor-IR-class": 30,
}

# ── 工作電壓 (V) — loaded from _component_specs_cache.json ──
# SSOT: verified.json electrical.voltage_operating_v (supplies use output/nominal).
# _fallback: ESP8266 (not in verified) + Speaker/Chassis (passive, no operating V).
VOLTAGE_V: Dict[str, float] = _section("voltage_v")

# ── 供電電壓 (V) ──────────────────────────────────────────
SUPPLY_V: Dict[str, float] = {
    "USB-5V-class":       5.0,
    "Battery-LiPo-class": 3.7,
    "Battery-AA-class":   3.0,
    "AC-Adapter-class":   5.0,
    "USB-Adapter-class":  5.0,
    "USB-Buck-5V-class":      5.0,
    "LiPo-Charger-class":     3.7,
    "BatteryHolder-AA-class":  3.0,
}

# ── 電流預算 ──────────────────────────────────────────────
USB_BUDGET_MA: float = 500.0
RAIL_3V3_BUDGET_MA: float = 50.0
THERMAL_THRESHOLD_MW: float = 2000.0

POWER_BUDGET_MA: Dict[str, float] = {
    "USB-5V-class":       500.0,
    "USB-Adapter-class":  500.0,
    "Battery-LiPo-class": 1500.0,
    "Battery-AA-class":   800.0,
    "AC-Adapter-class":   2000.0,
}

STALL_MA: Dict[str, float] = {
    "Motor-Servo-class":        500.0,
    "Motor-DC-class":           800.0,
    "Motor-Stepper-class":      500.0,
    "Pump-Water-class":         600.0,
    "Mist-Ultrasonic-class":    800.0,
    "L298N-Driver-class":       2000.0,
}

# ── BOM 採購連結 ──────────────────────────────────────────
BOM_URLS: Dict[str, str] = {
    "Arduino-Uno-class":    "https://www.lcsc.com/search?q=arduino+uno",
    "Arduino-Nano-class":   "https://www.lcsc.com/search?q=arduino+nano",
    "ESP32-class":          "https://www.lcsc.com/search?q=esp32+wroom",
    "ESP8266-class":        "https://www.lcsc.com/search?q=esp8266",
    "RaspberryPi-class":    "https://www.lcsc.com/search?q=raspberry+pi+4",
    "Microbit-class":       "https://www.lcsc.com/search?q=microbit",
    "USB-5V-class":         "https://www.lcsc.com/search?q=usb+5v+adapter",
    "Battery-LiPo-class":   "https://www.lcsc.com/search?q=lipo+battery+3.7v+tp4056",
    "Battery-AA-class":     "https://www.lcsc.com/search?q=aa+battery+holder",
    "Sensor-TempHumid-class":    "https://www.lcsc.com/search?q=dht22",
    "Sensor-Ultrasonic-class":   "https://www.lcsc.com/search?q=hc-sr04",
    "Sensor-PIR-class":          "https://www.lcsc.com/search?q=pir+motion+sensor",
    "Sensor-SoilMoisture-class": "https://www.lcsc.com/search?q=soil+moisture+sensor",
    "Sensor-Light-class":        "https://www.lcsc.com/search?q=ldr+photoresistor",
    "Potentiometer-class":  "https://www.lcsc.com/search?q=rotary+potentiometer+10k",
    "Remote-class":         "https://www.lcsc.com/search?q=ir+receiver+module+38khz",
    "Joystick-class":       "https://www.lcsc.com/search?q=joystick+module+ps2",
    "Switch-Generic-class": "https://www.lcsc.com/search?q=toggle+switch+spdt",
    "Display-OLED-class":  "https://www.lcsc.com/search?q=ssd1306+oled+0.96",
    "Display-LCD-class":   "https://www.lcsc.com/search?q=lcd+1602+i2c",
    "Display-EInk-class":  "https://www.lcsc.com/search?q=e-ink+display+2.9+inch+spi",
    "LED-Matrix-class":    "https://www.lcsc.com/search?q=max7219+led+matrix+8x8",
    "Motor-Servo-class":   "https://www.lcsc.com/search?q=sg90+servo",
    "Motor-DC-class":      "https://www.lcsc.com/search?q=l298n+motor+driver",
    "Motor-Stepper-class": "https://www.lcsc.com/search?q=28byj-48+stepper+motor+uln2003",
    "Relay-Module-class":  "https://www.lcsc.com/search?q=relay+module+5v",
    "Pump-Water-class":    "https://www.lcsc.com/search?q=mini+water+pump+5v",
    "Buzzer-Active-class":  "https://www.lcsc.com/search?q=active+buzzer+5v",
    "Buzzer-Passive-class": "https://www.lcsc.com/search?q=passive+buzzer+5v",
    "MP3-Module-class":     "https://www.lcsc.com/search?q=dfplayer+mini+mp3",
    "Speaker-class":        "https://www.lcsc.com/search?q=passive+speaker+36mm",
    "Lighting-LED-PWM-class":   "https://www.lcsc.com/search?q=led+5mm+white",
    "Lighting-NeoPixel-class":  "https://www.lcsc.com/search?q=ws2812b+led+strip",
    "Lighting-LED-Strip-class": "https://www.lcsc.com/search?q=led+strip+5v",
    "Lighting-LED-RGB-class":   "https://www.lcsc.com/search?q=rgb+led+5mm+common+cathode",
    "Mist-Atomizer-class":   "https://www.lcsc.com/search?q=piezoelectric+mist+atomizer",
    "Mist-Ultrasonic-class": "https://www.lcsc.com/search?q=ultrasonic+mist+maker",
    "Chassis-Car-class":    "https://www.lcsc.com/search?q=smart+car+chassis+robot",
    "Button-class":  "https://www.lcsc.com/search?q=tactile+push+button+6mm",
    "Switch-class":  "https://www.lcsc.com/search?q=slide+switch+spdt",
    "AC-Adapter-class":   "https://www.lcsc.com/search?q=ac+dc+adapter+5v",
    "USB-Adapter-class":  "https://www.lcsc.com/search?q=usb+charger+adapter+5v",
    "Sensor-IR-class": "https://www.lcsc.com/search?q=vs1838b+ir+receiver+38khz",
    "Sensor-MSGEQ7-class": "https://www.lcsc.com/search?q=msgeq7+graphic+equalizer",
    "L298N-Driver-class":  "https://www.lcsc.com/search?q=l298n+motor+driver+module",
}

# ── 命名別名（舊名 / 型號名 → taxonomy 名）───────────────
# SSOT：所有元件別名集中於此。bridge.py、phase2_handler.py 皆 import 此表。
COMPONENT_NAME_ALIASES: Dict[str, str] = {
    # ── Formal class-name aliases（舊名 / 型號 → canonical taxonomy 名）──
    "RaspberryPi-4B-class":      "RaspberryPi-class",
    "USB-Buck-5V-class":         "USB-5V-class",
    "LiPo-Charger-class":       "Battery-LiPo-class",
    "BatteryHolder-AA-class":    "Battery-AA-class",
    "DHT11-Sensor-class":        "Sensor-TempHumid-class",
    "DHT22-Sensor-class":        "Sensor-TempHumid-class",
    "HC-SR04-class":             "Sensor-Ultrasonic-class",
    "HC-SR501-PIR-class":        "Sensor-PIR-class",
    "SoilMoisture-class":        "Sensor-SoilMoisture-class",
    "LDR-class":                 "Sensor-Light-class",
    "OLED-SSD1306-class":        "Display-OLED-class",
    "LCD-1602-class":            "Display-LCD-class",
    "Servo-SG90-class":          "Motor-Servo-class",
    "DCMotor-L298N-class":       "Motor-DC-class",
    "L298N-class":               "L298N-Driver-class",
    "Relay-5V-class":            "Relay-Module-class",
    "WaterPump-class":           "Pump-Water-class",
    "Buzzer-class":              "Buzzer-Active-class",
    "DFPlayer-Speaker-class":    "Speaker-class",
    "NeoPixel-Strip-class":      "Lighting-NeoPixel-class",
    "LED-PWM-class":             "Lighting-LED-PWM-class",
    "Lighting-LED-Single-class": "Lighting-LED-PWM-class",
    "Sound-Buzzer-class":        "Buzzer-Active-class",
    "Sound-MP3-class":           "MP3-Module-class",
    "Sound-Speaker-class":       "Speaker-class",
    "Display-Matrix-class":      "LED-Matrix-class",
    "Mist-class":                "Mist-Atomizer-class",
    # ── 原 bridge.py _BRIDGE_ALIAS_MAPPING 搬入 ──
    "Switch-Generic-class":      "Button-class",
    "USB-Adapter-class":         "USB-5V-class",
    "AC-Adapter-class":          "USB-5V-class",
    "Sensor-Temperature-class":  "Sensor-TempHumid-class",
    "Display-LCD-I2C-class":     "Display-LCD-class",
    "Display-OLED-SSD1306-class": "Display-OLED-class",
}

# ── 模糊別名（小寫簡稱 / 通用詞 → taxonomy 名）─────────────
# 用於 Phase II fuzzy lookup：將使用者或 Phase I 產出的非正式名稱解析為 taxonomy 名。
# key 為全小寫、去除 - 和空格後的字串。
COMPONENT_SHORTHAND_ALIASES: Dict[str, str] = {
    # 縮寫 / 型號
    "rpi":                        "RaspberryPi-class",
    "raspberrypi":                "RaspberryPi-class",
    "hcsr04":                     "Sensor-Ultrasonic-class",
    "dht11":                      "Sensor-TempHumid-class",
    "dht22":                      "Sensor-TempHumid-class",
    "bmp280":                     "Sensor-TempHumid-class",
    "sg90":                       "Motor-Servo-class",
    # 單字簡稱
    "buzzer":                     "Buzzer-Active-class",
    "oled":                       "Display-OLED-class",
    "lcd":                        "Display-LCD-class",
    "servo":                      "Motor-Servo-class",
    "pump":                       "Pump-Water-class",
    "relay":                      "Relay-Module-class",
    "pir":                        "Sensor-PIR-class",
    "lipo":                       "Battery-LiPo-class",
    "stepper":                    "Motor-Stepper-class",
    "potentiometer":              "Potentiometer-class",
    "joystick":                   "Joystick-class",
    "remote":                     "Remote-class",
    "matrix":                     "LED-Matrix-class",
    "eink":                       "Display-EInk-class",
    "mp3":                        "MP3-Module-class",
    "mist":                       "Mist-Atomizer-class",
    # 多字別名（strip 後 key）
    "pushbutton":                 "Button-class",
    "usbpower":                   "USB-5V-class",
    "usb5v":                      "USB-5V-class",
    "aabattery":                  "Battery-AA-class",
    "lipobattery":                "Battery-LiPo-class",
    "pirmotionsensor":            "Sensor-PIR-class",
    "motionsensor":               "Sensor-PIR-class",
    "temperaturesensor":          "Sensor-TempHumid-class",
    "humiditysensor":             "Sensor-TempHumid-class",
    "temperaturehumiditysensor":  "Sensor-TempHumid-class",
    "temphumiditysensor":         "Sensor-TempHumid-class",
    "moisturesensor":             "Sensor-SoilMoisture-class",
    "distancesensor":             "Sensor-Ultrasonic-class",
    "lightsensor":                "Sensor-Light-class",
    "waterpump":                  "Pump-Water-class",
    "dcmotor":                    "Motor-DC-class",
    "servomotor":                 "Motor-Servo-class",
    "steppermotor":               "Motor-Stepper-class",
    "oleddisplay":                "Display-OLED-class",
    "lcddisplay":                 "Display-LCD-class",
    "einkdisplay":                "Display-EInk-class",
    "ledmatrix":                  "LED-Matrix-class",
    "relaymodule":                "Relay-Module-class",
    "neopixel":                   "Lighting-NeoPixel-class",
    "neopixelstrip":              "Lighting-NeoPixel-class",
    "ledstrip":                   "Lighting-LED-Strip-class",
    "rgbled":                     "Lighting-LED-RGB-class",
    "led":                        "Lighting-LED-RGB-class",
    "lightingledpwm":             "Lighting-LED-PWM-class",
    "ledpwm":                     "Lighting-LED-PWM-class",
    "nightlight":                 "Lighting-LED-PWM-class",
    "pwmled":                     "Lighting-LED-PWM-class",
    "irsensor":                   "Sensor-IR-class",
    "infrared":                   "Sensor-IR-class",
    "dfplayer":                   "MP3-Module-class",
    "activebuzzer":               "Buzzer-Active-class",
    "passivebuzzer":              "Buzzer-Passive-class",
    "atomizer":                   "Mist-Atomizer-class",
    "ultrasonicmist":             "Mist-Ultrasonic-class",
    "l298n":                      "L298N-Driver-class",
    "l298ndriver":                "L298N-Driver-class",
    "motordriver":                "L298N-Driver-class",
    "acadapter":                  "AC-Adapter-class",
    "usbadapter":                 "USB-Adapter-class",
    # 泛稱 → 預設對應
    "microcontroller":            "Arduino-Uno-class",
    "mcu":                        "Arduino-Uno-class",
    "controller":                 "Arduino-Uno-class",
    "board":                      "Arduino-Uno-class",
    "mainboard":                  "Arduino-Uno-class",
    "sensor":                     "Sensor-TempHumid-class",
    "motor":                      "Motor-DC-class",
    "display":                    "Display-OLED-class",
    "screen":                     "Display-OLED-class",
    "speaker":                    "Speaker-class",
    "light":                      "Lighting-LED-RGB-class",
    "lamp":                       "Lighting-LED-RGB-class",
    "battery":                    "Battery-LiPo-class",
    "switch":                     "Switch-class",
    "button":                     "Button-class",
    "fan":                        "Motor-DC-class",
    "gpio":                       "Arduino-Uno-class",
    "amplifier":                  "Speaker-class",
    "photoresistor":              "Sensor-Light-class",
    "ldr":                        "Sensor-Light-class",
    "piezo":                      "Buzzer-Passive-class",
    "solenoid":                   "Relay-Module-class",
}

# ── 元件重量 (g) — loaded from _component_specs_cache.json ──
# SSOT: verified.json physical.weight_g (battery holders use weight_with_batteries_g
# = as-installed weight, e.g. Battery-AA 56g incl. 2×AA cells, not 8g empty holder).
WEIGHT_G: Dict[str, float] = _section("weight_g")

# ── 元件發熱量 (mW) — loaded from _component_specs_cache.json ──
# SSOT: verified.json electrical.thermal_mw (all 43 classes; many small components
# derived as voltage_operating_v × current_typ_ma — see _ssot20_research_provenance).
THERMAL_MW: Dict[str, float] = _section("thermal_mw")


# ── 查表工具 ──────────────────────────────────────────────

def lookup_constant(table: dict, ctype: str, default):
    """Taxonomy 名稱優先直查；miss 時透過 COMPONENT_NAME_ALIASES 解析後再查。"""
    v = table.get(ctype)
    if v is not None:
        return v
    resolved = COMPONENT_NAME_ALIASES.get(ctype, "")
    return table.get(resolved, default)


def resolve_component_alias(class_name: str) -> str:
    """具體型號名稱解析為 taxonomy 名稱。無對應時原樣回傳。"""
    return COMPONENT_NAME_ALIASES.get(class_name, class_name)
