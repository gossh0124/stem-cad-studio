"""wiring_validate.py — SSOT-driven pin direction validation + pin-level wiring (SWL Phase 2).

Reads pin direction / voltage_domain from data/component_datasheet_verified.json
(Phase 1 落地的 SSOT 欄位) and provides:

- `validate_wiring(brain, comps)`        — direction 相容性檢查,回傳 issue list
- `resolve_wiring_pin_level(brain, comps)` — pin-to-pin 結構（替代 component-level wiring）
- `ssot_pin_info(class_name, pin_name)`  — 單一 pin 的 direction + voltage_domain 查詢

向後相容:不變更 lib/wiring.py 既有 API,僅新增能力。
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_log = logging.getLogger("cadhllm.wiring_validate")

from .engine import (  # noqa: F401 — re-use engine mappings
    PIN_POOLS,
    WIRING_TEMPLATES,
    COMP_PIN_NEEDS,
    allocate_pins,
    normalize_brain,
    normalize_comps,
)

REPO = Path(__file__).resolve().parent.parent.parent
SSOT_PATH = REPO / "data" / "component_datasheet_verified.json"

# ── SSOT loader (lazy cache) ─────────────────────────────────
_ssot_cache: dict | None = None
_ssot_lock = threading.Lock()


def _load_ssot() -> dict:
    global _ssot_cache
    with _ssot_lock:
        if _ssot_cache is None:
            _ssot_cache = json.loads(SSOT_PATH.read_text(encoding="utf-8"))
        return _ssot_cache


# Mapping: wiring.py 用的 short name → SSOT class name
_SHORT_TO_CLASS: dict[str, str] = {
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

# Mapping: wiring.py 用的 tag → SSOT pin name（差異 alias）
_TAG_TO_SSOT_PIN: dict[tuple[str, str], str] = {
    ("SoilMoisture", "AO"): "AOUT",
    ("Light", "LDR"): "AOUT",
    ("LED_Single", "+"): "Anode",
    ("Pump", "VCC"): "VCC",
    ("Speaker", "SPK+"): "SPK1",
    ("Speaker", "SPK-"): "SPK2",
    ("Servo", "SIG"): "SIGNAL",
    ("Button", "SIG"): "A1",
    ("Switch", "SIG"): "COM",
}


def _to_ssot_pin_name(comp_short: str, tag: str) -> str:
    return _TAG_TO_SSOT_PIN.get((comp_short, tag), tag)


# ── SSOT pin info lookup ─────────────────────────────────────
def ssot_pin_info(class_name: str, pin_name: str) -> dict | None:
    """查 SSOT entry pin 的完整資訊（含 direction + voltage_domain）。"""
    ssot = _load_ssot()
    entry = ssot.get(class_name)
    if not entry:
        return None
    pin_layout = entry.get("pin_layout") or {}
    target = pin_name.upper()
    for group in pin_layout.get("header_groups", []):
        for field in ("pins", "large_pins", "small_pins"):
            for p in group.get(field, []) or []:
                if (p.get("name") or "").upper() == target:
                    return p
    return None


def _mcu_pin_info(brain_key: str, label: str) -> dict | None:
    """從 MCU SSOT entry 查 pin。label 為 wiring.py allocate 出的形式
    （如 "D3" / "A0" / "P0" / "GPIO17"），嘗試多種變體匹配。"""
    cls = _SHORT_TO_CLASS.get(brain_key)
    if not cls:
        return None
    # Arduino Uno R3: A4/A5 在物理上等同於 SDA/SCL(I2C pin)
    # 當 wiring.py 把 SDA/SCL 分配到 A4/A5 時,以 I2C 角色為準
    if brain_key == "Arduino" and label in ("A4", "A5"):
        i2c_name = "SDA" if label == "A4" else "SCL"
        info = ssot_pin_info(cls, i2c_name)
        if info:
            return info
    # 直接匹配
    info = ssot_pin_info(cls, label)
    if info:
        return info
    # ESP32: GPIO17 / GPIO17/UART
    if brain_key == "ESP32":
        for prefix in ("GPIO", "VP/GPIO", "VN/GPIO"):
            info = ssot_pin_info(cls, f"{prefix}{label}")
            if info:
                return info
    # RPi: GPIO17 (但 wiring.py allocate 出 17 → label="D17", strip → "17")
    if brain_key == "RPi":
        stripped = label.lstrip("D")
        info = ssot_pin_info(cls, f"GPIO{stripped}")
        if info:
            return info
    return None


# ── Direction 相容性矩陣 ─────────────────────────────────────
# 從元件視角:A.dir × B.dir 是否合法。回傳 (ok, severity, reason)。
def _is_compatible(a: str, b: str) -> tuple[bool, str, str]:
    # 同類別處理
    if a == b:
        # power-power / gnd-gnd / i2c-i2c 都是允許並聯(同 rail / 同 bus)
        if a in ("power", "gnd", "i2c_bidir"):
            return True, "ok", ""
        # 雙向腳對雙向腳:GPIO 對 GPIO,OK
        if a == "digital_bidir":
            return True, "ok", ""
        # 兩端同方向(in-in / out-out)不相容
        if a in ("digital_in", "digital_out", "analog_in", "analog_out",
                 "pwm_in", "pwm_out"):
            return False, "error", f"兩端皆 {a},無對應源/匯"
        return True, "ok", ""

    # bidir 與任何 logic direction 相容（含 i2c_bidir,MCU GPIO 跑 I2C 是正常用法）
    if a == "digital_bidir" or b == "digital_bidir":
        # 但 bidir 不該直接接電源/地軌(MCU GPIO 接 5V/GND 會燒)
        if a in ("power", "gnd") or b in ("power", "gnd"):
            return False, "error", "digital_bidir 不應直接接電源軌"
        return True, "ok", ""

    # 配對:in × out 是合法的(信號源接信號匯)
    valid_pairs = {
        ("digital_in", "digital_out"),
        ("analog_in", "analog_out"),
        ("pwm_in", "pwm_out"),
        ("uart_tx", "uart_rx"),
    }
    if (a, b) in valid_pairs or (b, a) in valid_pairs:
        return True, "ok", ""

    # other 一端不阻擋,但標 warning
    if a == "other" or b == "other":
        return True, "warning", "一端為 other(機械接點 / 連接器 / 高壓接點),direction 不驗證"

    # power / gnd 與 logic pin
    if {a, b} & {"power", "gnd"}:
        return False, "error", f"電源/地不應接邏輯腳: {a} ↔ {b}"

    # 其他混合:warning
    return False, "warning", f"direction 異類混接: {a} ↔ {b}"


# ── Validation ──────────────────────────────────────────────
@dataclass
class WiringIssue:
    severity: str          # "error" | "warning"
    comp: str
    comp_pin: str
    comp_direction: str
    mcu_pin: str
    mcu_direction: str
    reason: str
    comp_vd: str = ""      # voltage_domain of component pin (ADR-1)
    mcu_vd: str = ""       # voltage_domain of MCU pin (ADR-1)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "comp": self.comp,
            "comp_pin": self.comp_pin,
            "comp_direction": self.comp_direction,
            "mcu_pin": self.mcu_pin,
            "mcu_direction": self.mcu_direction,
            "reason": self.reason,
            "comp_vd": self.comp_vd,
            "mcu_vd": self.mcu_vd,
        }


# ── Voltage domain cross-check (ADR-1) ──────────────────────

_BRAIN_DEFAULT_VD: dict[str, str] = {
    "Arduino": "logic_5V",
    "ESP32":   "logic_3V3",
    "RPi":     "logic_3V3",
    "Microbit":"logic_3V3",
}


def _norm_vd(vd: str) -> str:
    """Normalise voltage_domain string to lower-case for comparison."""
    return (vd or "").strip().lower()


def _check_voltage_domain(comp_vd: str, mcu_vd: str) -> tuple[bool, str, str]:
    """Check whether two voltage domains are compatible.

    Returns (is_ok, severity, reason).
      - is_ok=True  → no issue
      - is_ok=False → severity is "warning" with a Chinese reason string
    """
    cv = _norm_vd(comp_vd)
    mv = _norm_vd(mcu_vd)

    # Skip check when either side is unknown / power-only / gnd
    skip = {"", "n/a", "vin", "5v", "3v3", "power", "gnd"}
    if cv in skip or mv in skip:
        # Special case: logic pin connected to raw VIN rail
        if cv == "vin" or mv == "vin":
            other = mv if cv == "vin" else cv
            _vin_ok = {"", "n/a", "vin", "5v", "3v3", "power", "gnd"}
            if other not in _vin_ok:
                return (False, "warning",
                        "VIN 直供，確認元件耐壓（VIN 電壓可能超過元件額定值）")
        return True, "ok", ""

    # Same domain → compatible
    if cv == mv:
        return True, "ok", ""

    # 3.3V logic ↔ 5V logic mismatch
    is_3v3 = lambda v: v in ("logic_3v3", "3v3")   # noqa: E731
    is_5v  = lambda v: v in ("logic_5v",  "5v")    # noqa: E731
    if (is_3v3(cv) and is_5v(mv)) or (is_5v(cv) and is_3v3(mv)):
        return (False, "warning",
                "需 level shifter（3.3V ↔ 5V 邏輯電平不相容）")

    # Any other domain mismatch — generic warning
    return (False, "warning",
            f"電壓域不相容: {comp_vd} ↔ {mcu_vd}，請確認是否需要轉換電路")


def validate_wiring(brain: str, comps: list[str]) -> list[WiringIssue]:
    """檢查接線 pin direction 相容性及 voltage domain 相容性。
    回傳 issue list（空 list 表全 OK）。
    ADR-1: 加入 voltage domain cross-check，不相容時回傳 severity="warning"。
    """
    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    comps_norm = normalize_comps(comps)
    alloc = allocate_pins(brain_key, comps_norm)

    issues: list[WiringIssue] = []
    pin_prefix = "P" if brain_key == "Microbit" else "D"

    for comp_short in comps_norm:
        ssot_class = _SHORT_TO_CLASS.get(comp_short)
        if not ssot_class:
            _log.warning("SSOT class 未註冊: %s — 跳過 direction 驗證", comp_short)
            continue
        comp_pins_map = alloc["allocation"].get(comp_short, {})

        for tag, mcu_pin in comp_pins_map.items():
            ssot_pin_name = _to_ssot_pin_name(comp_short, tag)
            comp_pin_info = ssot_pin_info(ssot_class, ssot_pin_name)
            if not comp_pin_info:
                _log.warning("SSOT pin 未找到: %s.%s (class=%s) — 跳過此 pin 驗證",
                             comp_short, ssot_pin_name, ssot_class)
                continue
            comp_dir = comp_pin_info.get("direction", "other")
            comp_vd  = comp_pin_info.get("voltage_domain", "")

            # MCU pin 查詢:wiring.py allocate 出的 raw value 是 int (3, 5, 17) 或 str ("A0")
            mcu_label = f"{pin_prefix if isinstance(mcu_pin, int) else ''}{mcu_pin}"
            mcu_info = _mcu_pin_info(brain_key, mcu_label)
            mcu_dir = (mcu_info or {}).get("direction", "digital_bidir")
            mcu_vd  = (mcu_info or {}).get("voltage_domain", "") or _BRAIN_DEFAULT_VD.get(brain_key, "")

            # Direction compatibility check
            ok, severity, reason = _is_compatible(comp_dir, mcu_dir)
            if not ok:
                issues.append(WiringIssue(
                    severity=severity,
                    comp=comp_short,
                    comp_pin=tag,
                    comp_direction=comp_dir,
                    mcu_pin=mcu_label,
                    mcu_direction=mcu_dir,
                    reason=reason,
                    comp_vd=comp_vd,
                    mcu_vd=mcu_vd,
                ))
                continue  # skip vd check if direction already flagged

            # ADR-1: Voltage domain cross-check (only for logic pins)
            if comp_dir not in ("power", "gnd") and mcu_dir not in ("power", "gnd"):
                vd_ok, vd_sev, vd_reason = _check_voltage_domain(comp_vd, mcu_vd)
                if not vd_ok:
                    issues.append(WiringIssue(
                        severity=vd_sev,
                        comp=comp_short,
                        comp_pin=tag,
                        comp_direction=comp_dir,
                        mcu_pin=mcu_label,
                        mcu_direction=mcu_dir,
                        reason=vd_reason,
                        comp_vd=comp_vd,
                        mcu_vd=mcu_vd,
                    ))

    return issues


# ── Pin-level wiring resolver ────────────────────────────────
def resolve_wiring_pin_level(brain: str, comps: list[str]) -> dict:
    """產出 pin-to-pin 接線結構,包含每端 direction + voltage_domain。

    結構:
        {
            "SoilMoisture": {
                "label": "土壤濕度感測器",
                "connections": [
                    {"comp_pin": "VCC", "comp_dir": "power", "comp_vd": "5V",
                     "mcu_pin": "5V", "mcu_dir": "power", "mcu_vd": "5V",
                     "note": "", "color": "#ff4444"},
                    ...
                ]
            }
        }
    """
    from .engine import resolve_wiring

    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    comps_norm = normalize_comps(comps)
    base = resolve_wiring(brain_key, comps_norm)

    result: dict[str, dict] = {}
    pin_prefix = "P" if brain_key == "Microbit" else "D"
    mcu_class = _SHORT_TO_CLASS.get(brain_key)

    for comp_short, info in base.items():
        ssot_class = _SHORT_TO_CLASS.get(comp_short)
        connections: list[dict] = []

        for p in info.get("pins", []):
            tag = p["comp"]
            mcu_label = p["mcu"]
            # 元件端
            ssot_pin = _to_ssot_pin_name(comp_short, tag)
            comp_info = ssot_pin_info(ssot_class, ssot_pin) if ssot_class else None
            # VCC / GND 不在元件 SSOT pin 列表時退而給通用方向
            if tag == "VCC":
                comp_dir, comp_vd = "power", _power_vd_from_label(mcu_label)
            elif tag == "GND":
                comp_dir, comp_vd = "gnd", "n/a"
            else:
                comp_dir = (comp_info or {}).get("direction", "other")
                comp_vd = (comp_info or {}).get("voltage_domain", "logic_5V")

            # MCU 端
            mcu_info = ssot_pin_info(mcu_class, mcu_label) if mcu_class else None
            if mcu_label in ("GND", "GND_D", "GND2"):
                mcu_dir, mcu_vd = "gnd", "n/a"
            elif mcu_label in ("5V", "3V3", "VIN"):
                mcu_dir, mcu_vd = "power", mcu_label
            else:
                mcu_dir = (mcu_info or {}).get("direction", "digital_bidir")
                mcu_vd = (mcu_info or {}).get("voltage_domain", "logic_5V")

            connections.append({
                "comp_pin": tag,
                "comp_dir": comp_dir,
                "comp_vd": comp_vd,
                "mcu_pin": mcu_label,
                "mcu_dir": mcu_dir,
                "mcu_vd": mcu_vd,
                "note": p.get("note", ""),
                "color": p.get("color", "#44cc44"),
            })

        result[comp_short] = {
            "label": info.get("label", comp_short),
            "connections": connections,
        }

    return result


def _power_vd_from_label(label: str) -> str:
    if "3V3" in label or "3.3V" in label:
        return "3V3"
    if "VIN" in label:
        return "vin"
    return "5V"


# ── Self-test ───────────────────────────────────────────────
def _self_test() -> int:
    """快速驗:把 16 範本各跑一次 validate + pin-level resolve。"""
    samples = [
        ("Arduino", ["SoilMoisture", "Relay", "Pump", "Button"]),         # auto_waterer
        ("Arduino", ["NeoPixel", "PIR", "Light"]),                        # smart_nightlight
        ("Arduino", ["Speaker", "Servo", "PIR", "Button"]),                # talking_robot
        ("ESP32",   ["OLED", "DCMotor", "Ultrasonic"]),                   # esp32 mixed
    ]
    fails = 0
    for brain, comps in samples:
        issues = validate_wiring(brain, comps)
        pin_level = resolve_wiring_pin_level(brain, comps)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            print(f"  [FAIL] {brain} {comps}: {len(errors)} errors")
            for e in errors:
                print(f"    - {e.comp}.{e.comp_pin}({e.comp_direction}) ↔ "
                      f"{e.mcu_pin}({e.mcu_direction}): {e.reason}")
            fails += 1
        else:
            print(f"  [ OK ] {brain} {comps[:3]}{'...' if len(comps) > 3 else ''}  "
                  f"({sum(len(v['connections']) for v in pin_level.values())} pins)")
    return fails


if __name__ == "__main__":
    fails = _self_test()
    print(f"\n{'PASS' if fails == 0 else f'FAIL ({fails})'}")
    raise SystemExit(0 if fails == 0 else 1)
