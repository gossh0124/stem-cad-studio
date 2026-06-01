"""lib/verification/l1_netlist.py — VS-L1 schematic netlist 語義驗證。

電路圖的「正確」在 netlist（連接資料），不在渲染圖。本層驗證
resolve_wiring 輸出的 netlist：

  - connectivity        每個元件至少有接線（非孤立）
  - no_dangling         每個 pin 都有 MCU 目標（mcu 含 "?" = 未分配 = 角位未接線）
  - no_conflict         同一 MCU data pin 不被多元件搶用（I2C/SPI bus 除外）
  - direction           復用 lib.wiring.validate.validate_wiring（pin 方向 + 電壓域）
  - no_output_short     同一 MCU pin 不可有兩個 output 元件驅動（短路）
  - power_completeness  有 VCC 必有 GND，反之亦然（不完整電源迴路警告）

純函數 check_netlist(wiring) 可單測；check_wiring_netlist(brain, comps) 為便利包裝。
"""
from __future__ import annotations

import functools
import json
import logging
from pathlib import Path

from .report import CheckResult, VerificationReport, Verdict

_log = logging.getLogger("cadhllm.l1_netlist")

_REPO = Path(__file__).resolve().parent.parent.parent
_SSOT_PATH = _REPO / "data" / "component_datasheet_verified.json"

# ── Fallback whitelists（SSOT 不可用時退回）──────────────────
_NON_DATA_FALLBACK = {
    "5V", "3V3", "3.3V", "VIN", "VCC",
    "GND", "GND_D", "GND2", "AREF", "IOREF",
    "EXT", "SPK", "SPK-", "SPK1", "SPK2", "LOAD",
}

_BUS_KEYWORDS_FALLBACK = ("SDA", "SCL", "SCK", "MISO", "MOSI")
_BUS_PIN_ALIASES_FALLBACK = frozenset({"A4", "A5"})  # Arduino Uno I2C

# output 方向關鍵字（用於 Check 5 output-output 偵測）
_OUTPUT_DIR_KEYWORDS = ("_out",)


# ── SSOT-derived builders ────────────────────────────────────
@functools.lru_cache(maxsize=1)
def _load_ssot_data() -> dict | None:
    """Load SSOT JSON once; return None if file missing/corrupt."""
    try:
        return json.loads(_SSOT_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        _log.warning("SSOT load failed (%s), using fallback whitelists", exc)
        return None


def _iter_all_pins(ssot: dict):
    """Yield every pin dict across all component classes."""
    for cls_data in ssot.values():
        if not isinstance(cls_data, dict):
            continue
        pin_layout = (cls_data.get("pin_layout") or {})
        for group in pin_layout.get("header_groups", []):
            for field in ("pins", "large_pins", "small_pins"):
                for p in (group.get(field) or []):
                    yield p


def _build_non_data_from_ssot() -> set[str]:
    """Collect pin names with type PWR/GND/NC from SSOT, union with fallback."""
    ssot = _load_ssot_data()
    if ssot is None:
        return set(_NON_DATA_FALLBACK)
    derived = set()
    for p in _iter_all_pins(ssot):
        if p.get("type") in ("PWR", "GND", "NC"):
            name = p.get("name", "")
            if name:
                derived.add(name)
    # Union: SSOT 衍生 + fallback（fallback 含 wiring-engine alias 如 GND_D）
    return derived | _NON_DATA_FALLBACK


def _build_bus_dirs_from_ssot() -> frozenset[str]:
    """Collect direction values containing i2c/spi/uart from SSOT."""
    ssot = _load_ssot_data()
    if ssot is None:
        return frozenset()
    dirs = set()
    for p in _iter_all_pins(ssot):
        d = (p.get("direction") or "").lower()
        if any(proto in d for proto in ("i2c", "spi", "uart")):
            dirs.add(d)
    return frozenset(dirs)


# ── Lazy-init singletons ──────────────────────────────────────
_NON_DATA: set[str] | None = None
_BUS_DIRS: frozenset[str] | None = None


def _get_non_data() -> set[str]:
    global _NON_DATA
    if _NON_DATA is None:
        _NON_DATA = _build_non_data_from_ssot()
    return _NON_DATA


def _get_bus_dirs() -> frozenset[str]:
    global _BUS_DIRS
    if _BUS_DIRS is None:
        _BUS_DIRS = _build_bus_dirs_from_ssot()
    return _BUS_DIRS


def _is_dangling(mcu: str) -> bool:
    return (not mcu) or ("?" in mcu)


def _is_bus_pin(mcu: str, *, direction: str = "") -> bool:
    """I2C/SPI/UART 匯流排 pin 可合法被多元件共用。

    優先用 SSOT direction（精準）；fallback 用 pin 名稱關鍵字。
    """
    # SSOT direction 路徑
    bus_dirs = _get_bus_dirs()
    if direction and direction.lower() in bus_dirs:
        return True
    # Fallback: pin 名稱關鍵字
    u = (mcu or "").upper()
    if any(k in u for k in _BUS_KEYWORDS_FALLBACK):
        return True
    return u in _BUS_PIN_ALIASES_FALLBACK


def _is_output_dir(direction: str) -> bool:
    """direction 含 '_out' → 視為輸出（digital_out, pwm_out, analog_out）。"""
    d = (direction or "").lower()
    return any(kw in d for kw in _OUTPUT_DIR_KEYWORDS)


def check_netlist(wiring: dict, *, validate_issues: list | None = None,
                  name: str | None = None) -> VerificationReport:
    """純函數：驗證 resolve_wiring 輸出的 netlist 語義。"""
    rpt = VerificationReport(artifact=name or "<netlist>", artifact_type="netlist")
    wiring = wiring or {}
    non_data = _get_non_data()

    # 1. 連通性：每元件至少有接線
    isolated = [c for c, info in wiring.items() if not (info or {}).get("pins")]
    if isolated:
        rpt.add(CheckResult("L1", "connectivity", Verdict.FAIL,
                            message="元件無任何接線（孤立 / 角位未接線）",
                            metric={"isolated": isolated}))
    else:
        rpt.add(CheckResult("L1", "connectivity", Verdict.PASS,
                            metric={"n_comp": len(wiring)}))

    # 2. dangling pin：mcu 目標未分配（含 "?"）
    dangling = []
    for c, info in wiring.items():
        for p in (info or {}).get("pins", []):
            if _is_dangling(p.get("mcu", "")):
                dangling.append(f"{c}.{p.get('comp', '?')}→{p.get('mcu', '')}")
    if dangling:
        rpt.add(CheckResult("L1", "no_dangling_pin", Verdict.FAIL,
                            message="pin 無有效 MCU 目標（角位未接線）",
                            metric={"dangling": dangling[:10]}))
    else:
        rpt.add(CheckResult("L1", "no_dangling_pin", Verdict.PASS))

    # 3. data pin 衝突：同一 GPIO 被多元件搶用（電源/地/bus 除外）
    usage: dict = {}
    for c, info in wiring.items():
        for p in (info or {}).get("pins", []):
            mcu = p.get("mcu", "")
            direction = p.get("direction", "")
            if _is_dangling(mcu) or mcu in non_data or _is_bus_pin(mcu, direction=direction):
                continue
            usage.setdefault(mcu, []).append(f"{c}.{p.get('comp', '?')}")
    conflicts = {m: u for m, u in usage.items() if len(u) > 1}
    if conflicts:
        rpt.add(CheckResult("L1", "no_pin_conflict", Verdict.FAIL,
                            message="同一 MCU data pin 被多元件佔用（接線衝突）",
                            metric=conflicts))
    else:
        rpt.add(CheckResult("L1", "no_pin_conflict", Verdict.PASS,
                            metric={"n_data_pins": len(usage)}))

    # 4. direction / 電壓域相容（復用既有 validate_wiring 結果）
    if validate_issues is not None:
        errs = [i for i in validate_issues if getattr(i, "severity", "") == "error"]
        warns = [i for i in validate_issues if getattr(i, "severity", "") == "warning"]
        if errs:
            rpt.add(CheckResult("L1", "pin_direction_compat", Verdict.FAIL,
                                message="pin 方向/電壓域不相容（接線邏輯錯誤）",
                                metric={"errors": [f"{i.comp}.{i.comp_pin}↔{i.mcu_pin}: {i.reason}"
                                                   for i in errs[:6]]}))
        else:
            rpt.add(CheckResult("L1", "pin_direction_compat", Verdict.PASS,
                                metric={"n_checked": len(validate_issues)}))
        if warns:
            rpt.add(CheckResult("L2", "pin_direction_warnings", Verdict.WARN,
                                message="方向/電壓域警告（需 level shifter 等）",
                                metric={"warnings": [f"{i.comp}.{i.comp_pin}: {i.reason}"
                                                     for i in warns[:6]]}))

    # 5. OUTPUT-OUTPUT short circuit：同一 MCU pin 被 2+ output 元件驅動
    #    電源軌和 bus pin 已在 check 3 排除，此處只看 data pin
    out_usage: dict[str, list[str]] = {}
    for c, info in wiring.items():
        for p in (info or {}).get("pins", []):
            mcu = p.get("mcu", "")
            direction = p.get("direction", "")
            if _is_dangling(mcu) or mcu in non_data:
                continue
            if _is_bus_pin(mcu, direction=direction):
                continue
            if _is_output_dir(direction):
                out_usage.setdefault(mcu, []).append(
                    f"{c}.{p.get('comp', '?')}")
    shorts = {m: u for m, u in out_usage.items() if len(u) > 1}
    if shorts:
        rpt.add(CheckResult("L1", "no_output_short", Verdict.FAIL,
                            message="同一 MCU pin 被多個 output 驅動（短路風險）",
                            metric=shorts))
    else:
        rpt.add(CheckResult("L1", "no_output_short", Verdict.PASS,
                            metric={"n_outputs": sum(len(v) for v in out_usage.values())}))

    # 6. 電源完整性：有 VCC/5V/3V3 但無 GND（或反之）→ WARN
    _pwr_names = {"5V", "3V3", "3.3V", "VIN", "VCC", "VDD", "V+", "DC+"}
    _gnd_names = {"GND", "GND1", "GND2", "GND_D", "DC-", "M-"}
    incomplete_power: list[str] = []
    for c, info in wiring.items():
        pins = (info or {}).get("pins", [])
        mcu_set = {p.get("mcu", "") for p in pins}
        has_pwr = bool(mcu_set & _pwr_names)
        has_gnd = bool(mcu_set & _gnd_names)
        if has_pwr and not has_gnd:
            incomplete_power.append(f"{c}: VCC but no GND")
        elif has_gnd and not has_pwr:
            incomplete_power.append(f"{c}: GND but no VCC")
    if incomplete_power:
        rpt.add(CheckResult("L1", "power_completeness", Verdict.WARN,
                            message="電源迴路不完整（有 VCC 無 GND 或反之）",
                            metric={"incomplete": incomplete_power[:10]}))
    else:
        rpt.add(CheckResult("L1", "power_completeness", Verdict.PASS,
                            metric={"n_comp": len(wiring)}))

    return rpt


# ── Passive DRC helpers ───────────────────────────────────────

def _iter_passives(wiring: dict):
    """從 wiring dict 遍歷所有 passive 物件（含 pins 內嵌與 decoupling 清單）。

    Yields (comp_short, passive_dict)。
    """
    for comp_short, info in (wiring or {}).items():
        for pin in (info or {}).get("pins", []):
            pas = pin.get("passive")
            if isinstance(pas, dict):
                yield comp_short, pas
        for cap in (info or {}).get("decoupling", []):
            if isinstance(cap, dict):
                yield comp_short, cap


def passive_refdes_unique(wiring: dict, *, name: str | None = None) -> CheckResult:
    """DRC-P1（FAIL）：namespace 內 passive refdes 必須唯一，不可重複。"""
    from collections import Counter
    counts: Counter = Counter()
    for _c, pas in _iter_passives(wiring):
        rd = pas.get("refdes", "")
        if rd:
            counts[rd] += 1
    duplicates = {rd: cnt for rd, cnt in counts.items() if cnt > 1}
    if duplicates:
        return CheckResult(
            "L1", "passive_refdes_unique", Verdict.FAIL,
            message="passive refdes 在方案內重複（需唯一）",
            metric={"duplicates": duplicates},
        )
    return CheckResult(
        "L1", "passive_refdes_unique", Verdict.PASS,
        metric={"n_passives": sum(counts.values())},
    )


def passive_net_endpoints(wiring: dict, *, name: str | None = None) -> CheckResult:
    """DRC-P2（FAIL）：每個 passive 的 nets 必須恰 2 個且皆非空字串。"""
    bad: list[str] = []
    for comp_short, pas in _iter_passives(wiring):
        rd = pas.get("refdes", f"?@{comp_short}")
        nets = pas.get("nets", [])
        if not isinstance(nets, list) or len(nets) != 2:
            bad.append(f"{rd}: nets 長度={len(nets) if isinstance(nets, list) else 'N/A'}")
            continue
        for ep in nets:
            if not isinstance(ep, str) or not ep.strip():
                bad.append(f"{rd}: nets 含空字串端點 {nets!r}")
                break
    if bad:
        return CheckResult(
            "L1", "passive_net_endpoints", Verdict.FAIL,
            message="passive nets 未滿足「恰 2 端且皆非空字串」",
            metric={"bad": bad[:10]},
        )
    total = sum(1 for _ in _iter_passives(wiring))
    return CheckResult(
        "L1", "passive_net_endpoints", Verdict.PASS,
        metric={"n_passives": total},
    )


def passive_zero_power(wiring: dict, *, name: str | None = None) -> CheckResult:
    """DRC-P3（WARN）：被動 R/C/D 不應有功耗欄；若有 current_ma 應為 0。"""
    nonzero: list[str] = []
    for comp_short, pas in _iter_passives(wiring):
        kind = pas.get("kind", "")
        if kind not in ("R", "C", "D"):
            continue
        current_ma = pas.get("current_ma")
        if current_ma is not None and current_ma != 0:
            rd = pas.get("refdes", f"?@{comp_short}")
            nonzero.append(f"{rd}({kind}): current_ma={current_ma}")
    if nonzero:
        return CheckResult(
            "L2", "passive_zero_power", Verdict.WARN,
            message="被動元件（R/C/D）含非零 current_ma（應為 0）",
            metric={"nonzero": nonzero[:10]},
        )
    return CheckResult(
        "L2", "passive_zero_power", Verdict.PASS,
    )


def check_wiring_netlist(brain: str, comps: list, *, name: str | None = None) -> VerificationReport:
    """便利包裝：resolve_wiring + validate_wiring → netlist 驗證報告（含被動 DRC）。"""
    from lib.wiring import resolve_wiring, normalize_brain, normalize_comps, normalize_comp
    from lib.wiring.validate import validate_wiring

    bk = normalize_brain(brain) if brain != "auto" else "Arduino"
    cn = normalize_comps(comps)
    wiring = resolve_wiring(bk, cn)
    # 標註 passive(refdes/location/nets) 使被動 DRC 可驗（resolve_wiring 本身不標註）
    try:
        from lib.wiring.passives import annotate_passives
        comp_classes = {
            normalize_comp(c): (c if c.endswith("-class") else f"{c}-class")
            for c in comps
        }
        annotate_passives(wiring, [], comp_classes)
    except Exception:  # noqa: BLE001 — fail-open，標註失敗不擋既有檢查
        pass
    try:
        issues = validate_wiring(brain, comps)
    except Exception:  # noqa: BLE001 — direction 驗證失敗不應擋住其他檢查
        issues = []
    label = name or f"{bk}+{len(cn)}comps"
    rpt = check_netlist(wiring, validate_issues=issues, name=label)
    # 整合被動 DRC（refdes 唯一 / net 端點 / 零功耗）— 標註後才驗
    rpt.add(passive_refdes_unique(wiring))
    rpt.add(passive_net_endpoints(wiring))
    rpt.add(passive_zero_power(wiring))
    return rpt
