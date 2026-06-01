"""phase_handlers/phase3_handler.py — Phase III Engineering Constraints Handler.

Validates Power Budget / IO conflicts, produces BOM.md + wiring_notes.
Delegates validation logic to _phase3_validators and wiring/geometry to _phase3_wiring.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import time as _time

from .base import PhaseHandler
from ..shared.models import Job, PhaseID
from ..shared.bridge_store import project_output_dir
from ..shared.constants import (
    VOLTAGE_V as _VOLTAGE_V,
    USB_BUDGET_MA as _USB_BUDGET_MA,
    THERMAL_THRESHOLD_MW as _THERMAL_THRESHOLD_MW,
    lookup_constant as _lookup,
)
from lib.bom_calculator import calculate_bom as _calculate_bom

# Validator functions (extracted)
from ._phase3_validators import (
    check_io,
    check_gpio_pin_current,
    check_3v3_rail,
    check_level_shift,
    check_stall_current,
    check_wiring,
    _DISCRETE_COMPONENTS,
    _BRAIN_GPIO,
    _COMPONENT_IO,
    _GPIO_DIRECT_COMPONENTS,
    _GPIO_MAX_MA_PER_PIN,
)

# Wiring/geometry functions (extracted)
from ._phase3_wiring import (
    generate_wiring,
    estimate_layout_chamfer,
    check_interference,
)

# I2C/SPI bus protocols -- shared devices on same pins (boolean capacity, not additive)
_BUS_PROTOCOLS = {"i2c", "spi"}

# Brain bus resources (i2c/spi boolean: one bus supports unlimited devices)
_BRAIN_BUS: Dict[str, dict] = {
    "Arduino-Uno-class":     {"i2c": True, "spi": True, "uart": 1, "pwm": 6},
    "Arduino-Nano-class":    {"i2c": True, "spi": True, "uart": 1, "pwm": 6},
    "ESP32-class":           {"i2c": True, "spi": True, "uart": 3, "pwm": 16},
    "ESP8266-class":         {"i2c": True, "spi": True, "uart": 2, "pwm": 4},
    "RaspberryPi-class":     {"i2c": True, "spi": True, "uart": 2, "pwm": 4},
    "Microbit-class":        {"i2c": True, "spi": False, "uart": 1, "pwm": 3},
}


class Phase3Handler(PhaseHandler):
    """Phase III: Engineering Constraints -- power validation + BOM output."""

    phase_id = PhaseID.P3

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, Dict[str, Any]]:
        components: List[dict] = bridge.get("components", [])
        if not components:
            raise ValueError(
                "[Phase III] bridge.components 為空，無法執行工程約束驗證。\n"
                "請確認 Phase I 正確產生元件列表，且 Phase II 已補全規格。"
            )

        warnings: List[str] = []

        for comp in components:
            if not comp.get("spec"):
                ctype = comp.get("type", "unknown")
                raise ValueError(
                    f"元件 '{ctype}' 缺少 spec（Phase II 應已補全）。\n"
                    "請確認 Phase II 正確執行。"
                )

        bom = _calculate_bom(components)
        bom_rows = bom.rows
        total_ma = bom.total_ma
        total_ntd = bom.total_ntd
        supply_v = bom.supply_v
        power_type = bom.power_type
        current_budget_ma = bom.current_budget_ma

        for row in bom_rows:
            self._log(progress_cb,
                f"  {row['type']} ×{row['qty']}: {row['total_ma']:.0f} mA / NT${row['total_ntd']}")

        # -- Power budget warning -----------------------------------------
        power_ok = total_ma <= current_budget_ma
        if not power_ok:
            msg = (f"⚡ 功耗超標：總計 {total_ma:.0f} mA > {power_type} 上限 {current_budget_ma:.0f} mA，"
                   f"建議使用外接電源或 DC-Jack")
            warnings.append(msg)
            self._log(progress_cb, msg)
        else:
            self._log(progress_cb, f"  ✅ 功耗合格：{total_ma:.0f} / {current_budget_ma:.0f} mA")

        # -- Thermal power density check ----------------------------------
        total_mw = total_ma * supply_v
        needs_ventilation = total_mw > _THERMAL_THRESHOLD_MW
        if needs_ventilation:
            msg = (f"🌡️ 熱功率 {total_mw:.0f} mW > 閾值 {_THERMAL_THRESHOLD_MW} mW，"
                   f"建議外殼加入散熱柵")
            warnings.append(msg)
            self._log(progress_cb, msg)
        else:
            self._log(progress_cb,
                f"  ✅ 熱功率合格：{total_mw:.0f} / {_THERMAL_THRESHOLD_MW} mW")

        # -- I2C/SPI bus validation (boolean) -----------------------------
        brain_type = next(
            (c.get("type", "") for c in components if c.get("role") == "Brain"), ""
        )
        brain_bus = _BRAIN_BUS.get(brain_type, {})
        for comp in components:
            ctype = comp.get("type", "")
            spec  = comp.get("spec") or {}
            for port in spec.get("connector_ports", []):
                pname = port.get("name", "").lower()
                for proto in ("i2c", "spi"):
                    if proto in pname:
                        if not brain_bus.get(proto, True):
                            msg = (f"⚠️  {ctype} 需要 {proto.upper()} 介面，"
                                   f"但 {brain_type} 不支援 {proto.upper()}")
                            warnings.append(msg)
                            self._log(progress_cb, msg)
                        break

        # -- Voltage step-down audit (auto-inject LDO) --------------------
        needs_ldo = False
        ldo_reason: List[str] = []
        for comp in components:
            if comp.get("role") in ("Power",):
                continue
            ctype  = comp.get("type", "")
            if ctype in _DISCRETE_COMPONENTS:
                continue
            comp_v = _lookup(_VOLTAGE_V, ctype, 5.0)
            if comp_v < supply_v - 0.5:
                needs_ldo = True
                ldo_reason.append(f"{ctype}({comp_v}V)")

        if needs_ldo:
            ldo_comp = {
                "role": "Power", "type": "LDO-3V3-class", "qty": 1,
                "label": "3.3V LDO Regulator (auto-injected)",
                "_auto_injected": True,
            }
            existing_types = {c.get("type") for c in components}
            if "LDO-3V3-class" not in existing_types:
                components.append(ldo_comp)
                bridge["components"] = components
                msg = (f"⚡ 電壓不符：{', '.join(ldo_reason)} 需要 3.3V，"
                       f"自動注入 LDO-3V3-class 降壓模組")
                warnings.append(msg)
                self._log(progress_cb, msg)

        # -- IO GPIO validation (delegated) -------------------------------
        io_ok, io_results = check_io(components, brain_type, progress_cb)

        # -- EW1: GPIO per-pin current (delegated) ------------------------
        pin_current_ok, pin_current_results = check_gpio_pin_current(
            components, progress_cb)
        if not pin_current_ok:
            for r in pin_current_results:
                if r["level"] == "ERROR":
                    warnings.append(f"⚠️ {r['msg']}")

        # -- EW2: 3.3V rail cumulative current (delegated) ----------------
        rail_3v3_warnings = check_3v3_rail(components, progress_cb)
        warnings.extend(rail_3v3_warnings)

        # -- EW4: Level shift bidirectional (delegated) -------------------
        level_shift_warnings = check_level_shift(
            components, supply_v, progress_cb)
        warnings.extend(level_shift_warnings)

        # -- EW6: Motor stall current budget (delegated) ------------------
        stall_warnings = check_stall_current(
            components, progress_cb, current_budget_ma)
        warnings.extend(stall_warnings)

        # -- Wiring constraint validation (delegated) ---------------------
        wiring_ok, wiring_results = check_wiring(components, progress_cb)

        # -- Geometry compatibility (delegated) ---------------------------
        geo_result = estimate_layout_chamfer(components, progress_cb)

        # -- Keep-out Zone / 2D AABB interference (delegated) -------------
        interference_result = check_interference(components, progress_cb)
        if not interference_result.get("ok", True):
            for pair in interference_result.get("collisions", []):
                warnings.append(f"⚠️ 干涉：{pair['a']} ↔ {pair['b']}（重疊 {pair['overlap_mm']:.1f}mm²）")

        # -- Pin allocation + Wiring + Schematic SVG (delegated) ----------
        wiring_data = generate_wiring(components, brain_type, progress_cb)
        if wiring_data:
            bridge["pin_allocation"] = wiring_data.get("allocation", {})
            bridge["wiring"] = wiring_data.get("wiring", {})
            bridge["schematic_svg"] = wiring_data.get("schematic_svg", "")

        # Write bridge
        bridge["bom"] = bom_rows
        bridge["power_budget"] = {
            "total_ma": round(total_ma, 1),
            "budget_ma": current_budget_ma,
            "ok": power_ok,
            "supply_v": supply_v,
            "power_source": power_type,
            "needs_ldo": needs_ldo,
            "total_mw": round(total_mw, 1),
            "needs_ventilation": needs_ventilation,
        }
        bridge["wiring_notes"] = warnings

        # Aggregate field (aligned with notebook phase3_constraint_check format)
        interf_ok = interference_result.get("ok", True)
        all_ok = (power_ok and io_ok and wiring_ok and pin_current_ok
                  and geo_result.get("spatial_ok", True) and interf_ok)
        bridge["phase3_constraint_check"] = {
            "overall_ok": all_ok,
            "timestamp": _time.strftime("%Y-%m-%d %H:%M"),
            "results": {
                "power":   {"ok": power_ok,   "details": [{"level": "OK" if power_ok else "ERROR",
                             "rule": "PowerBudget", "msg": f"{total_ma:.0f}/{current_budget_ma:.0f} mA ({power_type})"}]},
                "io":      {"ok": io_ok,      "details": io_results},
                "pin_current": {"ok": pin_current_ok, "details": pin_current_results},
                "wiring":  {"ok": wiring_ok,  "details": wiring_results},
                "geometry":{"ok": geo_result.get("spatial_ok", True), "details": geo_result},
                "interference": {"ok": interf_ok, "details": interference_result},
            },
            "geometry_estimate": geo_result,
        }

        # Output BOM.md
        bom_path = self._write_bom_md(job, bom_rows, total_ma, total_ntd,
                                      power_ok, warnings, progress_cb, bridge,
                                      budget_ma=current_budget_ma)
        self._save_bridge_safe(job, bridge, progress_cb)

        summary = (f"BOM {len(bom_rows)} 項 / 總功耗 {total_ma:.0f} mA ({total_mw:.0f} mW) / "
                   f"NT${total_ntd} / {'⚠️ 超標' if not power_ok else '✅ 合格'} / "
                   f"IO {'✅' if io_ok else '❌'} / Wiring {'✅' if wiring_ok else '❌'} / "
                   f"Geo {'✅' if geo_result.get('spatial_ok', True) else '⚠️'}"
                   f"{' / 🌡️ 需散熱' if needs_ventilation else ''}")
        self._log(progress_cb, summary)
        return bridge, {
            "power_ok": power_ok,
            "io_ok": io_ok,
            "wiring_ok": wiring_ok,
            "overall_ok": all_ok,
            "total_ma": round(total_ma, 1),
            "total_mw": round(total_mw, 1),
            "needs_ventilation": needs_ventilation,
            "total_ntd": total_ntd,
            "warnings": warnings,
            "bom_path": bom_path,
            "geo_result": geo_result,
            "summary": summary,
        }

    # -- Delegated methods (backward-compatible with tests) ------------------
    def _check_io(self, components, brain_type, progress_cb):
        return check_io(components, brain_type, progress_cb)

    def _check_gpio_pin_current(self, components, progress_cb):
        return check_gpio_pin_current(components, progress_cb)

    def _check_3v3_rail(self, components, progress_cb):
        return check_3v3_rail(components, progress_cb)

    def _check_level_shift(self, components, supply_v, progress_cb):
        return check_level_shift(components, supply_v, progress_cb)

    def _check_stall_current(self, components, progress_cb, budget_ma=_USB_BUDGET_MA):
        return check_stall_current(components, progress_cb, budget_ma)

    def _check_wiring(self, components, progress_cb):
        return check_wiring(components, progress_cb)

    def _generate_wiring(self, components, brain_type, progress_cb):
        return generate_wiring(components, brain_type, progress_cb)

    def _estimate_layout_chamfer(self, components, progress_cb, padding_mm=5.0):
        return estimate_layout_chamfer(components, progress_cb, padding_mm)

    def _check_interference(self, components, progress_cb, keepout_mm=3.0):
        return check_interference(components, progress_cb, keepout_mm)

    # -- BOM Markdown output -----------------------------------------------
    def _write_bom_md(
        self,
        job: Job,
        rows: List[dict],
        total_ma: float,
        total_ntd: int,
        power_ok: bool,
        warnings: List[str],
        progress_cb,
        bridge: Optional[dict] = None,
        budget_ma: float = 500.0,
    ) -> Optional[str]:
        lines = [
            f"# Bill of Materials — {job.project_name}",
            "",
            "| # | Role | Type | Qty | mA/unit | mA total | NT$/unit | NT$ total |",
            "|---|------|------|-----|---------|----------|---------|-----------|",
        ]
        for i, r in enumerate(rows, 1):
            lines.append(
                f"| {i} | {r['role']} | `{r['type']}` | {r['qty']} "
                f"| {r['unit_ma']:.0f} | {r['total_ma']:.0f} "
                f"| {r['unit_ntd']} | {r['total_ntd']} |"
            )
        lines += [
            f"|  | **TOTAL** | | | | **{total_ma:.0f}** | | **{total_ntd}** |",
            "",
            f"## Power Budget",
            f"- 總電流：**{total_ma:.0f} mA**（電源上限 {budget_ma:.0f} mA）",
            f"- 狀態：{'✅ 合格' if power_ok else '⚠️ 超標，建議外接電源'}",
        ]
        if warnings:
            lines += ["", "## Warnings"]
            for w in warnings:
                lines.append(f"- {w}")

        content = "\n".join(lines) + "\n"

        proj_dir = bridge.get("_project_output_dir") if bridge else None
        if proj_dir:
            bom_dir = Path(proj_dir) / "bom"
        else:
            bom_dir = project_output_dir(job.job_id, job.project_name) / "bom"
        bom_dir.mkdir(parents=True, exist_ok=True)
        path = str(bom_dir / f"{job.job_id}_bom.md")
        try:
            Path(path).write_text(content, encoding="utf-8")
            self._log(progress_cb, f"  BOM.md -> {path}")
            return path
        except OSError:
            return None

    @staticmethod
    def _log(cb: Optional[Callable], msg: str):
        prefix = "[Phase III] "
        if cb:
            cb(prefix + msg)
        else:
            print(prefix + msg)
