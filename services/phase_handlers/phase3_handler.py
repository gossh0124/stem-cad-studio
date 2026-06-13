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
from lib.verification.l1_isolation import check_isolation as _check_isolation
from lib.verification.report import Verdict as _Verdict

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
        if brain_type and brain_type not in _BRAIN_BUS:
            # No-Silent-Fallback: an unrecognized MCU must not silently pass the
            # bus-capability gate (defaulting to "supported" gives false confidence).
            raise ValueError(
                f"[Phase III] 未知的 Brain 類型 '{brain_type}'，無法驗證 I2C/SPI 匯流排能力。\n"
                f"請將其加入 _BRAIN_BUS 對照表，或確認 Phase I 產生的 Brain type 正確。"
            )
        brain_bus = _BRAIN_BUS.get(brain_type, {})
        for comp in components:
            ctype = comp.get("type", "")
            spec  = comp.get("spec") or {}
            for port in spec.get("connector_ports", []):
                pname = port.get("name", "").lower()
                for proto in ("i2c", "spi"):
                    if proto in pname:
                        # Unknown/absent brain -> default to False (not supported)
                        # so the gate warns rather than silently passing.
                        if not brain_bus.get(proto, False):
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
                # SSOT integrity: the injected LDO has no `spec`, so it would be
                # absent from the already-computed BOM (line 88), power_budget
                # totals, and all geometry/interference reasoning (which skip
                # spec-less components) — a component/BOM divergence. We cannot
                # synthesize a datasheet spec here without fabricating data, so
                # rather than emit a silently-divergent spec-less component we
                # fail loudly. Phase II must supply the LDO spec, or the LDO must
                # be injected upstream (before BOM computation) with a resolved
                # spec so BOM/power_budget/geometry stay consistent.
                raise ValueError(
                    f"[Phase III] 電壓不符：{', '.join(ldo_reason)} 需要 3.3V，"
                    f"需注入 LDO-3V3-class 降壓模組，但無法在此解析其 spec。\n"
                    f"自動注入無 spec 的元件會造成 components/BOM/power_budget/幾何 不一致（SSOT divergence）。\n"
                    f"請於 Phase II 補全 LDO-3V3-class 規格，或在 BOM 計算前注入帶 spec 的 LDO。"
                )

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

        # -- Galvanic isolation (L1 旗艦契約,接進 runtime 自由輸入路徑) -----
        # 原本 lib/verification/l1_isolation 僅在 CI 對 canned 跑;自由輸入(LLM 生成)
        # 設計在 runtime 不受此把關(#28 finding 1)。此處對 runtime 產出的 netlist 跑
        # set 代數契約:控制地(GND) ∩ 負載地(EXT-GND) 必為 ∅。三值——PASS / FAIL(綁地,
        # 感性負載反電動勢 V=L·di/dt 可竄回 MCU)/ N/A(無隔離負載域)。FAIL 摺入
        # overall_ok → 經既有 P3 gate 攔截(非靜默)。同時把 verdict 化為 6E「Evaluate」
        # 教材:教育內容溯回機器 gate verdict,而非 LLM 自我宣稱(計畫書核心原則)。
        iso_results = _check_isolation((wiring_data or {}).get("nets", []))
        iso_ok = all(r.verdict != _Verdict.FAIL for r in iso_results)
        iso_details = [{"level": "OK" if r.verdict != _Verdict.FAIL else "ERROR",
                        "rule": r.name, "msg": r.message} for r in iso_results]
        self._emit_isolation_education(bridge, iso_results)
        self._log(progress_cb,
                  f"  {'✅' if iso_ok else '❌'} 電氣隔離："
                  + "；".join(r.message for r in iso_results))

        # -- 6E「Evaluate」教材:電源功率預算 verdict(DEC-H8 推廣,#28 B10) -----
        # 把上方 BOM 機器算出的真實總電流 / 官方供電容量(讀穿 verified.json)化為 6E
        # 教材 —— 與 isolation 同模式,教育內容溯回機器 verdict,非 LLM 自我宣稱。
        self._emit_power_education(bridge, power_ok=power_ok, total_ma=total_ma,
                                   budget_ma=current_budget_ma, power_type=power_type)

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
                  and geo_result.get("spatial_ok", True) and interf_ok and iso_ok)
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
                "isolation": {"ok": iso_ok, "details": iso_details},
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

    # -- 6E「Evaluate」教材:machine-verified isolation verdict ---------------
    def _emit_isolation_education(self, bridge: dict, iso_results):
        """把 galvanic isolation 的機器 verdict 化為 6E「Evaluate」教材,寫入
        engineering_decisions(前端 stem_concept 欄)。教育內容**溯回 gate verdict**,
        非 LLM 自我宣稱(計畫書核心原則:computable contracts, never self-declaration)。
        僅在隔離契約「適用」(有隔離負載域)時輸出 —— 無隔離負載的設計不產生隔離教學點。"""
        gi = next((r for r in iso_results if r.name == "galvanic_isolation"), None)
        if gi is None or gi.metric.get("applicable", True) is False:
            return
        if gi.verdict == _Verdict.FAIL:
            shared = "、".join(gi.metric.get("shared", [])) or "(見訊息)"
            desc = (
                f"❌ 電氣隔離違反:{shared} 同時落在控制地 (GND) 與負載地 (EXT-GND),兩地被綁定。"
                "感性負載(馬達/泵/線圈)關斷瞬間的反電動勢 V = L·di/dt 會經此共用接腳竄回 MCU,"
                "可能損毀微控制器。修正:以繼電器乾接點 / 光耦隔離兩地,使 set(GND) ∩ set(EXT-GND) = ∅。"
            )
        else:
            desc = (
                "✅ 電氣隔離通過:控制地 (GND) 與負載地 (EXT-GND) 經繼電器乾接點實體分離,兩地共用 0 隻接腳。"
                "感性負載關斷瞬間的反電動勢 V = L·di/dt(可達數十~數百伏)被侷限在負載迴路,"
                "無法竄回 MCU 控制地 —— 這正是繼電器乾接點隔離的安全意義。"
            )
        bridge.setdefault("engineering_decisions", []).append({
            "phase": "III",          # 管線階段(前端徽章 P{phase};此檢查跑在 Phase III)
            "6e_stage": "evaluate",  # 6E 語意:驗證改進(Evaluate)
            "category": "galvanic_isolation",
            "description": desc,
            "stem_concept": "電氣隔離 (galvanic isolation):控制地與負載地分離,阻斷感性負載反電動勢竄回 MCU",
        })

    def _emit_power_education(self, bridge: dict, *, power_ok: bool,
                             total_ma: float, budget_ma: float, power_type: str):
        """電源功率預算 verdict → 6E『Evaluate』教材。數值溯回 BOM 機器計算(真實總電流)
        + verified.json 讀穿的官方供電容量,非 LLM 自我宣稱(DEC-H8)。每設計皆適用。"""
        if power_ok:
            desc = (
                f"✅ 電源功率預算通過:全設計總電流 {total_ma:.0f} mA ≤ {power_type} 官方供電容量 "
                f"{budget_ma:.0f} mA。原理:元件工作電流總和須 ≤ 電源持續輸出能力,否則軌電壓被拉垮"
                f"(brown-out)→ MCU 重啟 / 感測讀數漂移。"
            )
        else:
            pct = round((total_ma / budget_ma - 1) * 100) if budget_ma else 0
            desc = (
                f"❌ 電源功率預算超標:總電流 {total_ma:.0f} mA > {power_type} 官方供電容量 "
                f"{budget_ma:.0f} mA(超出 {pct}%)。原理:抽載超過電源持續輸出能力 → 電壓驟降"
                f"(brown-out)、MCU 重啟或元件失效。修正:改用更大容量電源或降低負載。"
            )
        bridge.setdefault("engineering_decisions", []).append({
            "phase": "III",          # 管線階段(前端徽章 P{phase};此檢查跑在 Phase III)
            "6e_stage": "evaluate",  # 6E 語意:驗證改進(Evaluate)
            "category": "power_budget",
            "description": desc,
            "stem_concept": "電源功率預算 (power budget):負載總電流 ≤ 電源持續供電容量",
        })

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
