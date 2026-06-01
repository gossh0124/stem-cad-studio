"""lib/bom_calculator.py — BOM 累加共用邏輯（SSOT）。

Phase 3 / Phase 7 / tools 共用的 power budget + cost 計算。
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, NamedTuple, Optional

_log = logging.getLogger(__name__)

from .specs import POWER_MA, PRICE_NTD, SUPPLY_V, POWER_BUDGET_MA, USB_BUDGET_MA, lookup_constant
from .wiring.constants import PASSIVE_CATALOG


class BomSummary(NamedTuple):
    rows: List[Dict[str, Any]]
    total_ma: float
    total_ntd: int
    supply_v: float
    power_type: str
    current_budget_ma: float


def _collect_passives(wiring: Optional[dict]) -> List[dict]:
    """從 wiring dict 蒐集所有 passive 物件（已含 location/purchasable/kind）。

    wiring 格式：{comp_short: {"pins": [{..., "passive": {...}}], "decoupling": [{...}]}}
    也接受 to_json() 輸出的頂層 "wiring" key。
    """
    if not wiring:
        return []
    # 相容 to_json() 包裝格式
    target = wiring.get("wiring", wiring)
    result: List[dict] = []
    for info in target.values():
        if not isinstance(info, dict):
            continue
        for pin in info.get("pins", []):
            pas = pin.get("passive")
            if pas:
                result.append(pas)
        for cap in info.get("decoupling", []):
            result.append(cap)
    return result


def calculate_bom(
    components: List[dict],
    wiring: Optional[dict] = None,
) -> BomSummary:
    """從 bridge components 計算 BOM 行列 + 功耗/成本彙總。

    Args:
        components: bridge component list（主動件）
        wiring: 可選，annotate_passives 後的 wiring dict，用於追加被動元件 rows。
                支援裸 wiring dict 或含頂層 "wiring" key 的 to_json() 輸出。
    """
    rows: List[Dict[str, Any]] = []
    total_ma = 0.0
    total_ntd = 0

    supply_v = 5.0
    power_type = "USB-5V-class"
    for comp in components:
        if comp.get("role") == "Power":
            power_type = comp.get("type", "USB-5V-class")
            supply_v = SUPPLY_V.get(power_type, 5.0)
            break

    current_budget_ma = POWER_BUDGET_MA.get(power_type, USB_BUDGET_MA)

    for comp in components:
        ctype = comp.get("type", "unknown")
        if ctype == "unknown":
            _log.debug("BOM component missing type: role=%s", comp.get("role", "?"))
        qty = comp.get("qty", 1)
        role = comp.get("role", "Unknown")
        label = comp.get("label", ctype)

        unit_ma = lookup_constant(POWER_MA, ctype, None)
        if unit_ma is None:
            _log.warning("BOM: unknown ctype=%r, using fallback 50mA", ctype)
            unit_ma = 50.0
        unit_ntd = lookup_constant(PRICE_NTD, ctype, None)
        if unit_ntd is None:
            _log.warning("BOM: unknown ctype=%r, using fallback 100NTD", ctype)
            unit_ntd = 100

        comp_ma = unit_ma * qty
        comp_ntd = unit_ntd * qty

        total_ma += comp_ma
        total_ntd += comp_ntd

        rows.append({
            "role": role, "type": ctype, "label": label, "qty": qty,
            "unit_ma": unit_ma, "total_ma": comp_ma,
            "unit_ntd": unit_ntd, "total_ntd": comp_ntd,
        })

    # ── 追加被動元件 rows（零功耗，不改動 total_ma）────────────────
    for pas in _collect_passives(wiring):
        kind = pas.get("kind", "R")
        catalog = PASSIVE_CATALOG.get(kind, PASSIVE_CATALOG["R"])
        location = pas.get("location", "external")
        purchasable = pas.get("purchasable", location == "external")
        refdes = pas.get("refdes", kind)
        value = pas.get("value", "")
        label = f"{refdes} {value}".strip() if value else refdes

        if purchasable:
            unit_ntd = catalog["unit_ntd"]
            row_ntd = unit_ntd
            total_ntd += row_ntd
        else:
            unit_ntd = 0
            row_ntd = 0

        rows.append({
            "role": "Passive",
            "type": kind,
            "label": label,
            "qty": 1 if purchasable else 0,
            "unit_ma": 0.0,
            "total_ma": 0.0,
            "unit_ntd": unit_ntd,
            "total_ntd": row_ntd,
            "location": location,
            "purchasable": purchasable,
            "note": "" if purchasable else "已含於模組",
        })

    return BomSummary(
        rows=rows,
        total_ma=total_ma,
        total_ntd=total_ntd,
        supply_v=supply_v,
        power_type=power_type,
        current_budget_ma=current_budget_ma,
    )
