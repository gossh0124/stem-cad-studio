"""電源可行性檢查 — 從 validate.py 拆出以控制檔案 < 500 行（CLAUDE.md）。

對 brain 無對應供電軌的元件發 error（如 micro:bit 僅 3V3 → 接 5V 件不可行）。
保守判定：只在 brain 完全無該電壓軌時報，ESP32 VIN=5V / RPi 5V 不誤判。
"""
from __future__ import annotations

# rail 名 → 可供電壓（VIN/IOREF 在 USB 供電開發板上提供 5V）
_RAIL_V: dict[str, float] = {"5V": 5.0, "3V3": 3.3, "3.3V": 3.3, "VIN": 5.0, "IOREF": 5.0}


def _brain_supply_voltages(brain_key: str) -> set[float]:
    """brain 可提供的供電電壓集合,從 verified.json brain pin_layout PWR 腳衍生。"""
    from .validate import _SHORT_TO_CLASS, _load_ssot  # lazy：避免 top-level 循環 import
    cls = _SHORT_TO_CLASS.get(brain_key)
    if not cls:
        return set()
    spec = _load_ssot().get(cls, {})
    volts: set[float] = set()
    for g in spec.get("pin_layout", {}).get("header_groups", []):
        for p in g.get("pins", []):
            if p.get("type") == "PWR" or p.get("direction") == "power":
                v = _RAIL_V.get(p.get("name"))
                if v is not None:
                    volts.add(v)
    return volts


def _vcc_volts(vcc) -> float | None:
    import re
    if not vcc:
        return None
    m = re.search(r"[\d.]+", str(vcc))
    return float(m.group()) if m else None


def check_power_feasibility(brain_key: str, comps_norm: list[str]) -> list:
    """#1 電源可行性:brain 無對應供電軌時,對需該電壓的元件發 error。
    缺值/無 template 不臆造,跳過。回傳 WiringIssue list。"""
    from .validate import WiringIssue  # lazy：避免與 validate 循環 import
    avail = _brain_supply_voltages(brain_key)
    if not avail:
        return []
    issues: list = []
    try:
        from .template_gen import get_template
    except Exception:  # noqa: BLE001 — fail-open
        return []
    for comp_short in comps_norm:
        try:
            tmpl = get_template(comp_short)
        except Exception:  # noqa: BLE001
            continue
        req = _vcc_volts(getattr(tmpl, "vcc", None)) if tmpl else None
        if req is None:
            continue
        if req not in avail:
            issues.append(WiringIssue(
                severity="error",
                comp=comp_short,
                comp_pin="VCC",
                comp_direction="power",
                mcu_pin="(無)",
                mcu_direction="power",
                reason=f"{brain_key} 無 {req}V 供電腳（僅 {sorted(avail)}V），無法供電給需 {req}V 的 {comp_short}",
                comp_vd=f"{req}V",
                mcu_vd=f"{sorted(avail)}V",
            ))
    return issues
