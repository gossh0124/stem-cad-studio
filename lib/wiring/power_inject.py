"""lib/wiring/power_inject.py — PB4 (Path B / D4): derive power injection from SSOT.

Maps a power source to the correct MCU power-input pin by VOLTAGE MATCHING, reading both
sides' pin_layout from verified.json. This replaces the frontend _injectPower hardcoding
(pinPlus='BAT+'/'V+', mcuPlusPin=(Arduino&&battery)?'VIN':'5V') which routed every ESP32
source to a '5V' pin that ESP32 does NOT have -> the power wire was dropped. Here the MCU
pin is chosen from the MCU's real PWR pins and asserted to exist (PowerInjectError otherwise).

Topology rules (see reference_mcu_usage): 5V->'5V' pin if present else 'VIN'; 7-12V->'VIN';
3.0-4.2V (LiPo)->'3V3'. The source + pin name (V+/VCC/DC+) is read from the source SSOT.

Salvaged from V2 lib/wiring/power_inject.py (S-power-inject, functional parity).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Single source: comp_class_map 是 leaf module(不從 wiring 包 import 任何東西),於此 import 既
# 保有 power_inject 的零循環 import 特性，又消除原本內聯的同份副本（解決舊有「須手動 in-sync」TODO）。
# 漂移防護見 tests/test_short_to_class_single_source.py。_POWER_SHORT_TO_CLASS（下方）是另一個
# 電源域子集，刻意獨立、非此 dedup 範圍。
from .comp_class_map import SHORT_TO_CLASS  # noqa: E402

_SSOT = Path(__file__).resolve().parent.parent.parent / "data" / "component_datasheet_verified.json"
_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_SSOT.read_text(encoding="utf-8"))
    return _cache


# Power-source short names (frontend _POWER_TYPE_TO_COMP keys) -> verified.json class.
# Power sources are not in SHORT_TO_CLASS above (that map is signal components).
_POWER_SHORT_TO_CLASS: dict[str, str] = {
    "BatteryAA": "Battery-AA-class",
    "BatteryLiPo": "Battery-LiPo-class",
    "USB5V": "USB-5V-class",
    "AcAdapter": "AC-Adapter-class",
    "ACAdapter": "AC-Adapter-class",
    "USBAdapter": "USB-Adapter-class",
}


def _resolve_power_class(power_short: str) -> str:
    # Hyphen variants ('USB-5V' / 'Battery-AA') append -class suffix to match verified.json;
    # no-hyphen frontend forms ('USB5V' / 'BatteryAA') go through _POWER_SHORT_TO_CLASS.
    return (SHORT_TO_CLASS.get(power_short)
            or _POWER_SHORT_TO_CLASS.get(power_short)
            or (power_short if power_short.endswith("-class") else f"{power_short}-class"))


class PowerInjectError(ValueError):
    """Raised when power injection cannot be derived (no PWR pin / infeasible voltage)."""


class UnknownPowerSourceError(PowerInjectError):
    """指定的電源源無法解析回 SSOT class(typo 或未支援,如 'SolarPanel')。

    與「電壓對 MCU 不可行」(resilient —— 走隔離負載 + 獨立 V_USB)**區別**:此為設計輸入
    錯誤,必須上拋(engine 不吞、API → 422),**絕不**靜默以 V_USB 替代或回 None
    (no-silent-fallback / DEC-H7)。"""


def _pwr_pin_names(spec: dict) -> list:
    out = []
    for hg in (spec.get("pin_layout") or {}).get("header_groups", []) or []:
        for p in hg.get("pins", []) or []:
            if str(p.get("type", "")).upper() == "PWR":
                out.append(p.get("name"))
    return out


def _source_voltage(spec: dict) -> Optional[float]:
    el = spec.get("electrical") or {}
    for k in ("output_voltage_v", "voltage_nominal_v", "voltage_output_v"):
        v = el.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


# Per-MCU power-INPUT pins + accepted source-voltage range [lo, hi] (input-capable ONLY:
# Arduino's 3V3 is a 50mA OUTPUT, excluded). From reference_mcu_usage feasibility matrix --
# this is what makes a 2xAA(3V)/LiPo(3.7V) -> Arduino combo INFEASIBLE (raise), not a silent
# pick of some existing pin. First matching (input-capable + in-range + present) pin wins.
_MCU_POWER_INPUTS: dict[str, list] = {
    "Arduino-Uno-class":  [("VIN", 6.0, 12.0), ("5V", 4.5, 5.5)],     # barrel/VIN 7-12; 5V pin
    "ESP32-class":        [("VIN", 4.5, 5.5), ("3V3", 3.0, 4.2)],     # USB/VIN 5V; LiPo->3V3
    "Microbit-class":     [("3V3", 2.7, 3.6)],                         # edge 3V (2xAA native)
    "RaspberryPi-class":  [("5V", 4.75, 5.25)],                        # strict 5V
}


def _choose_mcu_pin(mcu_class: str, mcu_spec: dict, src_v: Optional[float]) -> str:
    """Pick the MCU power-input pin for a source voltage, from the MCU's input-capable PWR
    pins + their accepted voltage range. Raises (infeasible) if none accepts src_v -- this
    enforces 0-anomaly: e.g. 5V->ESP32 picks VIN (not the absent '5V'); 3V->Arduino raises."""
    if src_v is None:
        raise PowerInjectError("source voltage unknown -- cannot choose MCU power pin")
    avail = {str(n).upper(): n for n in _pwr_pin_names(mcu_spec)}
    inputs = _MCU_POWER_INPUTS.get(mcu_class)
    if inputs is None:
        # Unknown MCU: existence-only fallback (no feasibility check available).
        for c in ("5V", "VIN", "3V3"):
            if c in avail:
                return avail[c]
        raise PowerInjectError(f"{mcu_class}: no known power-input pin among {sorted(avail.values())}")
    for name, lo, hi in inputs:
        if lo <= src_v <= hi and name.upper() in avail:
            return avail[name.upper()]
    raise PowerInjectError(
        f"{mcu_class}: no power-input pin accepts {src_v}V "
        f"(input pins: {[(n, lo, hi) for n, lo, hi in inputs]}) -- power source incompatible with this MCU")


def derive_power_injection(mcu_short: str, power_short: str) -> dict:
    """Derive the power-injection wiring (source PWR/GND pin -> MCU power pin) from SSOT.

    Returns {source, mcu, source_voltage_v, plus:{source_pin, mcu_pin}, minus:{...}}.
    Raises PowerInjectError on a missing class / no PWR pin / infeasible voltage.
    """
    ssot = _load()
    mcu_class = SHORT_TO_CLASS.get(mcu_short, mcu_short)
    mcu_spec = ssot.get(mcu_class)
    pwr_spec = ssot.get(_resolve_power_class(power_short))
    if mcu_spec is None:
        raise PowerInjectError(f"unknown MCU class for '{mcu_short}'")
    if pwr_spec is None:
        raise PowerInjectError(f"unknown power class for '{power_short}'")
    src_pins = _pwr_pin_names(pwr_spec)
    if not src_pins:
        raise PowerInjectError(f"power source '{power_short}' has no PWR pin in pin_layout")
    src_v = _source_voltage(pwr_spec)
    mcu_pin = _choose_mcu_pin(mcu_class, mcu_spec, src_v)
    return {
        "source": power_short,
        "mcu": mcu_short,
        "source_voltage_v": src_v,
        "plus": {"source_pin": src_pins[0], "mcu_pin": mcu_pin},
        "minus": {"source_pin": "GND", "mcu_pin": "GND"},
    }


def derive_load_power_injection(load_power_short: str) -> dict:
    """Load-domain power injection: external power V+ -> load rail (EXT-PWR, connects to
    driver/relay load input), GND common ground. **No MCU feasibility check** (this is the
    load domain, not MCU supply; e.g. garden battery supplies pump, not Arduino).
    Raises PowerInjectError on missing class / no PWR pin.
    """
    ssot = _load()
    pwr_spec = ssot.get(_resolve_power_class(load_power_short))
    if pwr_spec is None:
        raise PowerInjectError(f"unknown power class for '{load_power_short}'")
    src_pins = _pwr_pin_names(pwr_spec)
    if not src_pins:
        raise PowerInjectError(f"power source '{load_power_short}' has no PWR pin in pin_layout")
    return {
        "source": load_power_short,
        "voltage_v": _source_voltage(pwr_spec),
        "plus": {"source_pin": src_pins[0], "load_rail": "EXT-PWR"},
        "minus": {"source_pin": "GND", "load_rail": "GND"},
    }


_SOURCE_REFDES = {
    "BatteryAA": "BT1", "BatteryLiPo": "BT1", "Battery-AA-class": "BT1", "Battery-LiPo-class": "BT1",
    "USB5V": "V_USB", "USBAdapter": "V_USB", "AcAdapter": "V_DCIN", "ACAdapter": "V_DCIN",
}


def _source_refdes(power_short: str) -> str:
    return _SOURCE_REFDES.get(power_short, "PS1")


def derive_power_source_wiring(mcu_short: str, power_short: str,
                               has_ext_pwr: bool = False) -> list | None:
    """共地(Common Ground)+ 獨立供電架構:回傳「電源 device 清單」。

    每 device = {refdes, source, plus:{net_name,source_pin}, minus:{net_name:'GND',source_pin}}。
    **全系統共地**:所有 source 的負極都接 common GND('GND' net,與 Arduino GND 同節點)。
    規則(spec 2026-06-08):
      - 顯式源能供 MCU(derive_power_injection 成功)→ 它是 MCU 源(plus=mcu 電源 pin);
        has_ext_pwr 時同源亦供負載(另加一條 plus=EXT-PWR)。
      - 顯式源供不了 MCU(如 3V 電池)→ 它是**負載源**(plus=EXT-PWR);MCU 另由**獨立
        V_USB/V_DCIN(5–9V)**供電(plus=5V),**電池絕不接 MCU 5V/VIN**。
    皆無 device → None(不靜默)。

    DEC-H7 / no-silent-fallback (a):`power_short` 必須可解析回 SSOT class。不可解析者(typo /
    未支援的 'SolarPanel' 等)→ **raise `UnknownPowerSourceError`**,絕不靜默捏造 V_USB 替代或回
    None —— 否則使用者指定的源消失、負載軌(EXT-PWR)無源,而 API 仍回 200 綠(實測曾以
    to_json('Arduino',['Relay'],power='SolarPanel') 重現幽靈 V_USB + EXT-PWR 無源)。
    可解析但電壓供不了 MCU(如 3V 電池)是合法情形,仍走下方 V_USB-for-load 隔離分支。
    """
    _pclass = _resolve_power_class(power_short)
    if _load().get(_pclass) is None:
        raise UnknownPowerSourceError(
            f"unknown power source '{power_short}'（resolved class '{_pclass}' 不在 SSOT）"
            " —— 拒絕靜默以 V_USB 替代或回 None;請改用已註冊電源或補 SSOT")
    devs: list[dict] = []
    mcu_ok = False
    # Galvanic isolation:兩個完全不相交的地網路 —— 控制端 NET_GND_LOGIC('GND')
    # 與動力端 NET_GND_LOAD('EXT-GND')。繼電器乾接點物理斷路,兩域地嚴禁互連
    # (感性負載突波 V=L·di/dt 不得回灌 MCU GND)。
    LOGIC_GND = {"net_name": "GND", "source_pin": "GND"}
    LOAD_GND = {"net_name": "EXT-GND", "source_pin": "GND"}
    try:
        pinj = derive_power_injection(mcu_short, power_short)
        mcu_ok = True
        devs.append({
            "refdes": _source_refdes(power_short), "source": power_short,
            "plus": {"net_name": pinj["plus"]["mcu_pin"], "source_pin": pinj["plus"]["source_pin"]},
            "minus": dict(LOGIC_GND),
        })
    except PowerInjectError:
        pass
    if has_ext_pwr:
        try:
            linj = derive_load_power_injection(power_short)
            # 電池為負載專用源(MCU infeasible)→ 負極接 NET_GND_LOAD(隔離);
            # 否則(單一可行源同時供 MCU+負載)→ 同域 logic GND。
            devs.append({
                "refdes": _source_refdes(power_short), "source": power_short,
                "plus": {"net_name": linj["plus"]["load_rail"], "source_pin": linj["plus"]["source_pin"]},
                "minus": dict(LOAD_GND if not mcu_ok else LOGIC_GND),
            })
        except PowerInjectError:
            pass
        if not mcu_ok:
            # 電池供不了 MCU → MCU 走獨立 V_USB(5V),接 LOGIC GND。電池只在隔離的負載迴路。
            devs.append({
                "refdes": "V_USB", "source": "USB5V",
                "plus": {"net_name": "5V", "source_pin": "V+"},
                "minus": dict(LOGIC_GND),
            })
    return devs or None
