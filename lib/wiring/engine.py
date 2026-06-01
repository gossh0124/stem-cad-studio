"""
wiring.py — Pin 分配 + 接線解析（SSOT for UI + Phase III）

移植自 ui/js/features.js _allocatePins / _resolveWiring，
確保前後端 pin mapping 一致。
"""
from __future__ import annotations
import logging
from typing import List

from lib.pin_maps import _PIN_MAPS, _INPUT_ONLY_PINS, _I2C_HW_PINS
from lib.wiring.constants import MCU_POWER_PASSIVES
from .wiring_data import (  # noqa: F401 — re-exported for backward compat
    PinNeed,
    WireExtra,
    WiringTemplate,
    COMP_PIN_NEEDS,
    _TAXONOMY_TO_SHORT,
    _BRAIN_TO_KEY,
    COMP_LIBS,
    WIRING_TEMPLATES,
)

_log = logging.getLogger(__name__)


class PinAllocationError(Exception):
    """無法為元件分配 MCU pin（pool 耗盡 / tag 不符 / 未映射）。

    Phase 0 接線硬化：不再靜默回 '?' 帶進接線/韌體，改 fail-fast 讓上層（phase3）
    明確得知 pin 不足而非產出含 '?' 的無效圖/程式碼。
    """


# ── MCU Pin Pools (向後相容 alias → _PIN_MAPS) ───────────────
# 外部程式碼（tests、wiring_csp）直接 import PIN_POOLS 仍可正常使用。
# _PIN_MAPS 是完整版（含 spi/uart），PIN_POOLS 僅暴露 4 個核心欄位以保持相容。
PIN_POOLS: dict[str, dict] = {
    brain: {
        "pwm":     list(m["pwm"]),
        "digital": list(m["digital"]),
        "analog":  list(m["analog"]),
        "i2c":     dict(m["i2c"]),
    }
    for brain, m in _PIN_MAPS.items()
}


def normalize_comp(name: str) -> str:
    """Taxonomy 名稱 → COMP_PIN_NEEDS short name。"""
    clean = name.replace("-class", "").strip()
    if clean in COMP_PIN_NEEDS:
        return clean
    if clean in _TAXONOMY_TO_SHORT:
        return _TAXONOMY_TO_SHORT[clean]
    return clean


def normalize_brain(name: str) -> str:
    """Taxonomy Brain 名稱 → PIN_POOLS key。"""
    clean = name.replace("-class", "").strip()
    if clean in PIN_POOLS:
        return clean
    if clean in _BRAIN_TO_KEY:
        return _BRAIN_TO_KEY[clean]
    low = clean.lower()
    if "esp" in low:
        return "ESP32"
    if "micro" in low and "bit" in low:
        return "Microbit"
    if "rpi" in low or "raspberry" in low:
        return "RPi"
    return "Arduino"


def normalize_comps(comps: List[str]) -> List[str]:
    """批次正規化元件名稱，回傳 short names（保序、去重）。"""
    seen: set[str] = set()
    result: list[str] = []
    for c in comps:
        short = normalize_comp(c)
        if short not in seen:
            seen.add(short)
            result.append(short)
    return result



# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def _fifo_allocate(brain_key: str, comps: list[str], pool: dict) -> dict:
    """Legacy FIFO allocator — kept as fallback if CSP fails."""
    def _take(pin_type: str):
        if pin_type == "pwm":
            return (pool["pwm"].pop(0) if pool["pwm"]
                    else pool["digital"].pop(0) if pool["digital"] else "?")
        if pin_type == "analog":
            return pool["analog"].pop(0) if pool["analog"] else "?"
        return (pool["digital"].pop(0) if pool["digital"]
                else pool["pwm"].pop(0) if pool["pwm"] else "?")

    def _spi_pin(tag: str):
        """從 spi dict 取出對應腳位，找不到退回 digital pool。"""
        spi_map = pool.get("spi", {})
        key = tag.lower()
        if key in spi_map:
            return spi_map[key]
        return pool["digital"].pop(0) if pool["digital"] else "?"

    def _uart_pin(tag: str):
        """從 uart dict 取出對應腳位，找不到退回 digital pool。"""
        uart_map = pool.get("uart", {})
        key = tag.lower()
        if key in uart_map:
            return uart_map[key]
        return pool["digital"].pop(0) if pool["digital"] else "?"

    pin_prefix = "P" if brain_key == "Microbit" else "D"
    allocation: dict[str, dict[str, object]] = {}
    pin_labels: dict[str, str] = {}
    for comp in comps:
        needs = COMP_PIN_NEEDS.get(comp)
        if not needs:
            continue
        pins: dict[str, object] = {}
        parts: list[str] = []
        for n in needs:
            if n.type == "i2c":
                pins[n.tag] = pool["i2c"]["scl"] if n.tag == "SCL" else pool["i2c"]["sda"]
                parts.append(f"{n.tag}={pins[n.tag]}")
            elif n.type == "spi":
                pins[n.tag] = _spi_pin(n.tag)
                parts.append(f"{n.tag}={pins[n.tag]}")
            elif n.type == "uart":
                pins[n.tag] = _uart_pin(n.tag)
                parts.append(f"{n.tag}={pins[n.tag]}")
            else:
                pins[n.tag] = _take(n.type)
                prefix = "" if n.type == "analog" else pin_prefix
                parts.append(f"{n.tag}={prefix}{pins[n.tag]}")
        unalloc = [t for t, v in pins.items() if v == "?"]
        if unalloc:
            raise PinAllocationError(
                f"{comp}: 無可用 pin 給 {unalloc}（{brain_key} pin pool 耗盡）"
            )
        allocation[comp] = pins
        pin_labels[comp] = " / ".join(parts)
    return {"allocation": allocation, "pin_labels": pin_labels}


def allocate_pins(brain: str, comps: list[str], *,
                  use_spi: bool = False, use_uart: bool = False) -> dict:
    """
    分配 MCU 腳位給元件列表（CSP solver，FIFO 作為 fallback）。

    Args:
        brain:    MCU 名稱（支援 taxonomy 名 e.g. "Arduino-Uno-class"）
        comps:    元件列表（支援 taxonomy 名 e.g. "Sensor-SoilMoisture"）
        use_spi:  若 True，pool 中包含 SPI 腳位（供 SPI 元件分配）
        use_uart: 若 True，pool 中包含 UART 腳位（供 UART 元件分配）

    Returns:
        {
            "allocation": { "SoilMoisture": {"AO": "A0"}, ... },
            "pin_labels": { "SoilMoisture": "AO=A0", ... }
        }
    """
    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    comps = normalize_comps(comps)
    raw = PIN_POOLS.get(brain_key, PIN_POOLS["Arduino"])
    full_map = _PIN_MAPS.get(brain_key, _PIN_MAPS["Arduino"])

    def _fresh_pool() -> dict:
        return {
            "pwm": list(raw["pwm"]), "digital": list(raw["digital"]),
            "analog": list(raw["analog"]), "i2c": dict(raw["i2c"]),
            "spi": dict(full_map.get("spi", {})),
            "uart": dict(full_map.get("uart", {})),
        }

    try:
        from .csp import csp_allocate
        allocation, pin_labels, conflicts = csp_allocate(
            brain_key, comps, _fresh_pool(), COMP_PIN_NEEDS
        )
    except PinAllocationError:
        raise  # FIFO fallback 內的耗盡 fail-fast，不可被當成 CSP 錯誤再吞
    except Exception as exc:  # noqa: BLE001
        _log.warning("CSP allocator error (%s) — falling back to FIFO", exc)
        return _fifo_allocate(brain_key, comps, _fresh_pool())
    if conflicts:
        _log.warning("CSP conflicts: %s — falling back to FIFO", conflicts)
        return _fifo_allocate(brain_key, comps, _fresh_pool())
    return {"allocation": allocation, "pin_labels": pin_labels}


def _resolve_template(comp: str) -> tuple[WiringTemplate | None, str]:
    """解析元件的 WiringTemplate，優先 datasheet 衍生，fallback 手寫。

    Returns:
        (template, source) — source 為 "datasheet" 或 "fallback"
    """
    try:
        from .template_gen import get_template
        tmpl = get_template(comp)
        if tmpl:
            _log.debug("template[%s] source=datasheet", comp)
            return tmpl, "datasheet"
    except Exception as exc:  # noqa: BLE001
        _log.debug("template_gen failed for %s: %s", comp, exc)

    tmpl = WIRING_TEMPLATES.get(comp)
    if tmpl:
        _log.debug("template[%s] source=fallback", comp)
    return tmpl, "fallback"


def resolve_wiring(brain: str, comps: list[str], *, _alloc_result: dict | None = None) -> dict:
    """解析完整接線資訊（含 VCC/GND/信號線）。

    Returns: {comp: {"label": str, "pins": [{"comp","mcu","color","note"}]}}
    """
    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    comps = normalize_comps(comps)
    result = _alloc_result or allocate_pins(brain_key, comps)
    alloc = result["allocation"]
    pin_prefix = "P" if brain_key == "Microbit" else "D"

    resolved: dict[str, dict] = {}
    for comp in comps:
        # CAG Layer 1: 優先從 datasheet 衍生 template
        tmpl, _src = _resolve_template(comp)
        if not tmpl:
            continue
        comp_pins = alloc.get(comp, {})
        pins: list[dict] = []
        if tmpl.vcc:
            pins.append({"comp": "VCC", "mcu": tmpl.vcc, "color": "#ff4444", "note": ""})
        pins.append({"comp": "GND", "mcu": "GND", "color": "#333333", "note": ""})
        for e in tmpl.extra:
            need = None
            for n in COMP_PIN_NEEDS.get(comp, []):
                if n.tag == e.tag:
                    need = n
                    break
            if e.fixed:
                pins.append({"comp": e.comp, "mcu": e.fixed,
                             "color": e.color, "note": e.note, "passive": dict(e.passive) if e.passive else None})
            else:
                if e.tag and e.tag not in comp_pins:
                    raise PinAllocationError(
                        f"resolve_wiring: {comp}.{e.tag} 未分配"
                        f"（WireExtra.tag 與 COMP_PIN_NEEDS 不符？）"
                    )
                pin_val = comp_pins.get(e.tag, "?") if e.tag else "?"
                prefix = "" if (need and need.type == "analog") else pin_prefix
                pins.append({"comp": e.comp, "mcu": f"{prefix}{pin_val}",
                             "color": need.color if need else "#44cc44",
                             "note": e.note, "passive": dict(e.passive) if e.passive else None})
        resolved[comp] = {"label": tmpl.label, "pins": pins}
        if tmpl.decoupling:  # SWL3: IC 去耦電容（VCC-GND），前端在元件旁畫 C 節點
            resolved[comp]["decoupling"] = [{"kind": "C", "value": tmpl.decoupling, "topo": "decoupling"}]

    return resolved


def to_json(brain: str, comps: list[str]) -> dict:
    """API-ready：一次回傳 allocation + wiring + pin_labels + validation。

    SWL Phase 4 (2026-05-13)：wiring 每個 pin 注入 SSOT direction + voltage_domain
    （comp_dir / comp_vd / mcu_dir / mcu_vd 四欄），並加 validation issue list。
    schematic-elk 從這些欄位繪 direction 箭頭與 voltage_domain 配色。
    """
    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    comps_norm = normalize_comps(comps)
    alloc = allocate_pins(brain_key, comps_norm)
    wiring = resolve_wiring(brain_key, comps_norm, _alloc_result=alloc)

    # SWL Phase 4: enrich pins with SSOT direction + voltage_domain
    validation: list[dict] = []
    try:
        from .validate import resolve_wiring_pin_level, validate_wiring
        pin_level = resolve_wiring_pin_level(brain_key, comps_norm)
        for comp, info in wiring.items():
            pl_info = pin_level.get(comp, {})
            conn_map = {(c["comp_pin"], str(c["mcu_pin"])): c
                        for c in pl_info.get("connections", [])}
            for p in info.get("pins", []):
                key = (p["comp"], str(p["mcu"]))
                conn = conn_map.get(key)
                if conn:
                    p["comp_dir"] = conn["comp_dir"]
                    p["comp_vd"] = conn["comp_vd"]
                    p["mcu_dir"] = conn["mcu_dir"]
                    p["mcu_vd"] = conn["mcu_vd"]
        validation = [i.to_dict() for i in validate_wiring(brain_key, comps_norm)]
    except Exception as e:  # noqa: BLE001 — fail-open: 不阻擋既有流程
        _log.debug("wiring_validate enrichment failed: %s", e)

    # 複製共享常數避免跨呼叫污染（MCU_POWER_PASSIVES 是 module-level）
    power_passives = [dict(p) for p in MCU_POWER_PASSIVES.get(brain_key, [])]

    # Phase 2 step 1：為被動元件補 refdes/location/purchasable（fail-open，不阻擋既有流程）
    try:
        from .passives import annotate_passives
        comp_classes = {
            normalize_comp(c): (c if c.endswith("-class") else f"{c}-class")
            for c in comps
        }
        annotate_passives(wiring, power_passives, comp_classes)
    except Exception as e:  # noqa: BLE001
        _log.debug("passive annotation failed: %s", e)

    return {
        "brain": brain_key,
        "allocation": alloc["allocation"],
        "pin_labels": alloc["pin_labels"],
        "wiring": wiring,
        "validation": validation,
        # SWL3: MCU 電源軌被動元件 — 由 MCU config 驅動（前端畫在 MCU 電源軌旁）
        "power_passives": power_passives,
    }
