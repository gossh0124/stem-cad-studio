"""Phase III engineering constraint validators.

Extracted from phase3_handler.py — contains all _check_* methods
for IO/GPIO/rail/level-shift/stall/wiring validation.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from ..shared.constants import (
    POWER_MA as _POWER_MA,
    VOLTAGE_V as _VOLTAGE_V,
    USB_BUDGET_MA as _USB_BUDGET_MA,
    STALL_MA as _STALL_MA,
    RAIL_3V3_BUDGET_MA as _RAIL_3V3_BUDGET_MA,
    lookup_constant as _lookup,
)

# ── Module-level constants (shared with main handler) ──────────────

_DISCRETE_COMPONENTS: frozenset = frozenset({
    "Sensor-Light-class",
    "Lighting-LED-PWM-class",  "Lighting-LED-RGB-class",
    "Sensor-PIR-class",
    "Button-class",            "Switch-class",           "Switch-Generic-class",
    "Potentiometer-class",     "Joystick-class",         "Remote-class",
    "Buzzer-Active-class",     "Buzzer-Passive-class",
    "Sensor-TempHumid-class",
    "Sensor-SoilMoisture-class",
    "Sensor-Ultrasonic-class",
})

_BRAIN_GPIO: Dict[str, dict] = {
    "Arduino-Uno-class":  {"digital": 14, "analog": 6,  "pwm": 6,  "i2c": 1, "spi": 1, "uart": 1},
    "Arduino-Nano-class": {"digital": 14, "analog": 8,  "pwm": 6,  "i2c": 1, "spi": 1, "uart": 1},
    "ESP32-class":        {"digital": 34, "analog": 18, "pwm": 16, "i2c": 2, "spi": 4, "uart": 3},
    "ESP8266-class":      {"digital": 17, "analog": 1,  "pwm": 4,  "i2c": 1, "spi": 1, "uart": 2},
    "RaspberryPi-class":  {"digital": 40, "analog": 0,  "pwm": 2,  "i2c": 2, "spi": 2, "uart": 2},
    "Microbit-class":     {"digital": 19, "analog": 6,  "pwm": 3,  "i2c": 1, "spi": 1, "uart": 1},
}

_COMPONENT_IO: Dict[str, dict] = {
    "Button-class":          {"digital": 1},
    "Switch-class":          {"digital": 1},
    "Sensor-PIR-class":          {"digital": 1},
    "Sensor-Light-class":        {"analog": 1},
    "Sensor-TempHumid-class":    {"digital": 1},
    "Sensor-Ultrasonic-class":   {"digital": 2},
    "Sensor-SoilMoisture-class": {"analog": 1},
    "Motor-Servo-class":         {"pwm": 1},
    "Motor-DC-class":            {"digital": 2},
    "Motor-Stepper-class":       {"digital": 4},
    "Relay-Module-class":        {"digital": 1},
    "Pump-Water-class":          {"digital": 1},
    "Display-OLED-class":        {"i2c": 1},
    "Display-LCD-class":         {"i2c": 1},
    "Display-EInk-class":        {"spi": 1},
    "LED-Matrix-class":          {"i2c": 1},
    "Buzzer-Active-class":       {"digital": 1},
    "Buzzer-Passive-class":      {"pwm": 1},
    "MP3-Module-class":          {"uart": 1},
    "Speaker-class":             {"uart": 1},
    "Lighting-LED-PWM-class":    {"pwm": 1},
    "Lighting-LED-RGB-class":    {"pwm": 3},
    "Lighting-LED-Strip-class":  {"pwm": 1},
    "Lighting-NeoPixel-class":   {"pwm": 1},
    "Switch-Generic-class":      {"digital": 1},
    "Potentiometer-class":       {"analog": 1},
    "Remote-class":              {"digital": 1},
    "Joystick-class":            {"analog": 2},
}

# EW1: GPIO per-pin max safe current (mA)
_GPIO_MAX_MA_PER_PIN = 20.0

_GPIO_DIRECT_COMPONENTS: dict[str, float] = {
    "Motor-Servo-class":        200.0,
    "Motor-DC-class":           300.0,
    "Motor-Stepper-class":      240.0,
    "Pump-Water-class":         220.0,
    "Lighting-LED-Strip-class": 200.0,
    "Lighting-NeoPixel-class":  480.0,
    "Mist-Atomizer-class":      350.0,
    "Mist-Ultrasonic-class":    500.0,
    "Relay-Module-class":        80.0,
    "MP3-Module-class":         200.0,
    "Speaker-class":            200.0,
    "LED-Matrix-class":         320.0,
}


# ── Helper ─────────────────────────────────────────────────────────

def _log(cb: Optional[Callable], msg: str) -> None:
    prefix = "[Phase III] "
    if cb:
        cb(prefix + msg)
    else:
        print(prefix + msg)


# ── Validators (functions, not methods) ────────────────────────────

def check_io(
    components: List[dict],
    brain_type: str,
    progress_cb: Optional[Callable] = None,
) -> Tuple[bool, List[dict]]:
    """IO GPIO pin budget validation."""
    results: List[dict] = []
    ok = True
    gpio = _BRAIN_GPIO.get(brain_type, {"digital": 20, "analog": 6, "pwm": 6,
                                         "i2c": 2, "spi": 2, "uart": 2})
    req: Dict[str, int] = {}
    for comp in components:
        if comp.get("role") in ("Brain", "Power"):
            continue
        ctype = comp.get("type", "")
        io_need = _COMPONENT_IO.get(ctype, {"digital": 1})
        qty = comp.get("qty", 1)
        for pin_type, count in io_need.items():
            req[pin_type] = req.get(pin_type, 0) + count * qty

    for pin_type, need in req.items():
        avail = gpio.get(pin_type, 0)
        if need == 0:
            continue
        if need > avail:
            msg = f"{brain_type} {pin_type} 腳位不足：需 {need}，有 {avail}"
            results.append({"level": "ERROR", "rule": f"GPIO-{pin_type}", "msg": msg})
            _log(progress_cb, f"  ❌ {msg}")
            ok = False
        else:
            results.append({"level": "OK", "rule": f"GPIO-{pin_type}",
                             "msg": f"{pin_type}: {need}/{avail} ✓"})
    if not req:
        results.append({"level": "OK", "rule": "GPIO", "msg": "無需額外 GPIO 驗證"})
    if ok:
        _log(progress_cb, f"  ✅ IO 驗證通過（{brain_type}）")
    return ok, results


def check_gpio_pin_current(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
) -> Tuple[bool, List[dict]]:
    """EW1: Check GPIO per-pin 20mA safe limit for directly-connected components."""
    results: List[dict] = []
    ok = True

    for comp in components:
        if comp.get("role") in ("Brain", "Power"):
            continue
        ctype = comp.get("type", "")
        comp_ma = _GPIO_DIRECT_COMPONENTS.get(ctype)
        if comp_ma is None:
            continue
        if comp_ma <= _GPIO_MAX_MA_PER_PIN:
            results.append({
                "level": "OK",
                "rule": "GPIO-PinCurrent",
                "msg": f"{ctype}: {comp_ma:.0f}mA ≤ {_GPIO_MAX_MA_PER_PIN:.0f}mA ✓",
            })
            continue

        has_relay = any(
            c.get("type") in ("Relay-Module-class",)
            for c in components
        )
        has_mosfet = any("mosfet" in (c.get("type", "").lower()) for c in components)

        if has_relay or has_mosfet:
            results.append({
                "level": "OK",
                "rule": "GPIO-PinCurrent",
                "msg": (f"{ctype}: {comp_ma:.0f}mA 超標，"
                        f"但已有 Relay/MOSFET 驅動 ✓"),
            })
        else:
            msg = (f"{ctype} 需 {comp_ma:.0f}mA，超過 GPIO {_GPIO_MAX_MA_PER_PIN:.0f}mA 限制，"
                   f"建議加 Relay-Module 或 MOSFET 驅動")
            results.append({"level": "ERROR", "rule": "GPIO-PinCurrent", "msg": msg})
            _log(progress_cb, f"  ❌ {msg}")
            ok = False

    if not results:
        results.append({
            "level": "OK",
            "rule": "GPIO-PinCurrent",
            "msg": "無高功率 GPIO 直連元件",
        })
    if ok:
        _log(progress_cb, "  ✅ GPIO per-pin 電流驗證通過")
    return ok, results


def check_3v3_rail(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
) -> List[str]:
    """EW2: Check cumulative 3.3V rail current against onboard LDO budget."""
    total_3v3_ma = 0.0
    items: List[str] = []
    for comp in components:
        if comp.get("role") in ("Brain", "Power"):
            continue
        ctype = comp.get("type", "")
        comp_v = _lookup(_VOLTAGE_V, ctype, 5.0)
        if abs(comp_v - 3.3) > 0.1:
            continue
        ma = _lookup(_POWER_MA, ctype, 0.0) * comp.get("qty", 1)
        if ma > 0:
            total_3v3_ma += ma
            items.append(f"{ctype}({ma:.0f}mA)")

    warnings: List[str] = []
    if total_3v3_ma > _RAIL_3V3_BUDGET_MA:
        msg = (f"⚡ 3.3V rail 超標：{', '.join(items)} 合計 {total_3v3_ma:.0f}mA "
               f"> 板載 LDO {_RAIL_3V3_BUDGET_MA:.0f}mA，"
               f"建議外接 LDO-3V3 模組或選用 ESP32（板載 500mA LDO）")
        warnings.append(msg)
        _log(progress_cb, f"  ❌ {msg}")
    else:
        _log(progress_cb,
            f"  ✅ 3.3V rail 合格：{total_3v3_ma:.0f}/{_RAIL_3V3_BUDGET_MA:.0f} mA")
    return warnings


def check_level_shift(
    components: List[dict],
    supply_v: float,
    progress_cb: Optional[Callable] = None,
) -> List[str]:
    """EW4: Bidirectional level shift check (both step-down and step-up)."""
    warnings: List[str] = []
    brain_type = next(
        (c.get("type", "") for c in components if c.get("role") == "Brain"), ""
    )
    brain_v = _lookup(_VOLTAGE_V, brain_type, 5.0)

    for comp in components:
        if comp.get("role") in ("Brain", "Power"):
            continue
        ctype = comp.get("type", "")
        if ctype in _DISCRETE_COMPONENTS:
            continue
        comp_v = _lookup(_VOLTAGE_V, ctype, 5.0)
        if comp_v > brain_v + 0.5:
            msg = (f"⚠️ {ctype}({comp_v}V) > {brain_type} GPIO({brain_v}V)，"
                   f"需要 level shifter 升壓（3.3V→5V）")
            warnings.append(msg)
            _log(progress_cb, f"  ❌ {msg}")

    if not warnings:
        _log(progress_cb, "  ✅ Level shift 檢查通過")
    return warnings


def check_stall_current(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
    budget_ma: float = _USB_BUDGET_MA,
) -> List[str]:
    """EW6: Cumulative motor/pump stall current vs power budget."""
    total_stall = 0.0
    items: List[str] = []
    for comp in components:
        ctype = comp.get("type", "")
        stall = _STALL_MA.get(ctype)
        if stall is None:
            continue
        qty = comp.get("qty", 1)
        total_stall += stall * qty
        items.append(f"{ctype}×{qty}({stall:.0f}mA)")

    warnings: List[str] = []
    if total_stall > budget_ma:
        msg = (f"⚡ 峰值電流風險：{', '.join(items)} stall 合計 {total_stall:.0f}mA "
               f"> 電源預算 {budget_ma:.0f}mA，"
               f"多馬達同時堵轉將觸發 USB 過流保護（brownout），"
               f"建議外接電源或加入電流限制電路")
        warnings.append(msg)
        _log(progress_cb, f"  ⚠️ {msg}")
    elif items:
        _log(progress_cb,
            f"  ✅ 峰值電流合格：stall {total_stall:.0f}/{budget_ma:.0f} mA")
    return warnings


def check_wiring(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
) -> Tuple[bool, List[dict]]:
    """Wiring constraint validation including EW8 pin direction compatibility."""
    results: List[dict] = []
    roles = {c.get("role", "") for c in components}
    types = {c.get("type", "") for c in components}
    ok = True

    if "Actuator" in roles and "Brain" not in roles:
        msg = "有 Actuator 但無 Brain 控制"
        results.append({"level": "ERROR", "rule": "Wiring", "msg": msg})
        _log(progress_cb, f"  ❌ {msg}")
        ok = False

    if any(t in types for t in ("Relay-5V-class",)):
        has_load = any(t in types for t in ("DCMotor-L298N-class", "WaterPump-class"))
        if not has_load:
            msg = "有 Relay 但無受控高功率負載，確認是否正確"
            results.append({"level": "WARN", "rule": "Wiring", "msg": msg})
            _log(progress_cb, f"  ⚠️  {msg}")

    # EW8: Pin direction compatibility check
    try:
        from lib.wiring import normalize_brain, normalize_comp
        from lib.wiring.validate import validate_wiring
        brain_type = next((c.get("type", "") for c in components
                           if c.get("role") == "Brain"), None)
        if not brain_type:
            raise ValueError(
                "找不到 Brain 元件，無法對真實 MCU 做 EW8 接線方向檢查"
                "（拒絕以預設 Arduino-Uno 估算，避免對使用者顯示假接線警告）"
            )
        brain_key = normalize_brain(brain_type)
        comp_shorts = [normalize_comp(c.get("type", ""))
                       for c in components
                       if c.get("role") not in ("Brain", "Power")]
        issues = validate_wiring(brain_key, comp_shorts)
        for issue in issues:
            rec = issue.to_dict() if hasattr(issue, "to_dict") else issue
            lvl = "ERROR" if rec.get("severity") == "error" else "WARN"
            msg = (f"EW8: {rec['comp']}.{rec['comp_pin']}({rec['comp_direction']}) "
                   f"↔ {rec['mcu_pin']}({rec['mcu_direction']}): {rec['reason']}")
            results.append({"level": lvl, "rule": "EW8", "msg": msg})
            if lvl == "ERROR":
                ok = False
                _log(progress_cb, f"  ❌ {msg}")
            else:
                _log(progress_cb, f"  ⚠️  {msg}")
    except Exception as e:  # noqa: BLE001 -- fail-open
        _log(progress_cb, f"  (EW8 skipped: {e})")

    results.append({"level": "OK", "rule": "Wiring", "msg": "基礎 Wiring 規則通過"})
    if ok:
        _log(progress_cb, "  ✅ Wiring 驗證通過")
    return ok, results
