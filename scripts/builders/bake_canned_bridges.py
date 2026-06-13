"""tools/bake_canned_bridges.py — 為每個 v6/data.jsx 範本產生「免跑 LLM」的 canned bridge。

執行：.venv/Scripts/python.exe tools/bake_canned_bridges.py
輸出：v6/canned/{template_id}.json + v6/canned/_index.json

Canned bridge 內容（無 STL / 完整 firmware；前端 view 顯示 demo placeholder）：
- cot_plan + components（含 educational_rationale）
- enclosure_sizing / parameter_hints
- bom + power_budget + phase3_constraint_check
- schematic_svg（靜態 SVG，由 lib.schematic.generate_svg 產出）
- checkpoint_phase=5、_canned_demo=True

不依賴 LLM、不跑 PipelineRunner。直接 lookup registry/constants/templates。
"""
from __future__ import annotations
import json
import math
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/builders/ → repo root (3 levels)
sys.path.insert(0, str(ROOT))
# NOTE: canned template defs were moved from tools/ into lib/ during the V3
# migration (tools/ is dev-only, not shipped); imported as lib.canned_template_defs below.

from lib.registry import COMPONENT_REGISTRY  # noqa: E402
from lib.config import EDUCATIONAL_RATIONALE_TEMPLATES, AREA_COMPACT_MAX_MM2, AREA_MEDIUM_MAX_MM2  # noqa: E402
from lib.specs import POWER_MA, PRICE_NTD, POWER_BUDGET_MA, USB_BUDGET_MA  # noqa: E402
from services.pipeline_runner import _build_role_alternatives  # noqa: E402
from lib.wiring import to_json as wiring_to_json  # noqa: E402
from lib.schematic import generate_svg as schematic_generate_svg  # noqa: E402
from lib.canned_template_defs import TEMPLATE_DEFS  # noqa: E402

# ─── Scaffold 生成器 ─────────────────────────────────────────────

def _component_size_mm(ctype: str) -> tuple:
    """從 registry 取元件 length × width，缺則回 (40, 25)。"""
    spec = COMPONENT_REGISTRY.get(ctype)
    if spec:
        return spec.length_mm, spec.width_mm
    return 40.0, 25.0


def _supply_ma(components: list) -> int:
    """從 power role 元件決定供應電流上限（讀穿 specs.POWER_BUDGET_MA 單一官方源，#20）。"""
    for c in components:
        if c.get("role") == "Power":
            v = POWER_BUDGET_MA.get(c.get("type", ""))
            if v:
                return int(v)
    return int(USB_BUDGET_MA)  # 預設 USB 500mA


def _enclosure_sizing(components: list) -> dict:
    """對齊 pipeline_runner._auto_size_enclosure 的尺寸決策邏輯。"""
    non_housing = [c for c in components if c.get("role", "").lower() != "housing"]
    count = len(non_housing)
    if count == 0:
        return {}

    padding = 8.0
    total_area = 0.0
    max_dim = 0.0
    dims_found = 0
    for comp in non_housing:
        l, w = _component_size_mm(comp.get("type", ""))
        if comp.get("type", "") in COMPONENT_REGISTRY:
            dims_found += 1
        total_area += (l + padding) * (w + padding) * comp.get("qty", 1)
        max_dim = max(max_dim, l, w)

    if max_dim > 100 or total_area > AREA_MEDIUM_MAX_MM2:
        target, cap = "large", 220
    elif total_area > AREA_COMPACT_MAX_MM2 or count >= 6:
        target, cap = "medium", 220
    else:
        target, cap = "compact", 150

    size_zh = {"compact": "迷你", "medium": "一般", "large": "大型"}[target]
    rationale = f"共 {count} 個元件，估算佈局面積 {total_area:.0f} mm²，建議 {size_zh}尺寸（≤ {cap}mm）"
    return {
        "target_size": target, "max_dimension_mm": cap,
        "component_count": count,
        "estimated_area_mm2": round(total_area),
        "max_component_dim_mm": round(max_dim, 1),
        "rationale": rationale,
        "wall_thickness_mm": 2.0, "material": "PLA",
    }


def _enrich_components(components: list) -> list:
    """從 registry 補 spec 摘要，從 EDUCATIONAL_RATIONALE_TEMPLATES 補敘述。"""
    enriched = []
    for c in components:
        ctype = c.get("type", "")
        spec = COMPONENT_REGISTRY.get(ctype)
        new = dict(c)
        if spec:
            new["spec"] = {
                "name": spec.name,
                "voltage_v": getattr(spec, "voltage_v", 5.0),
                "current_ma": getattr(spec, "current_ma", POWER_MA.get(ctype, 20)),
                "length_mm": spec.length_mm,
                "width_mm": spec.width_mm,
                "height_mm": getattr(spec, "height_mm", 10.0),
                "connector_ports": [
                    {"name": p.name, "type": getattr(p, "type", "digital")}
                    for p in (getattr(spec, "connector_ports", None) or [])
                ],
            }
        rationale = EDUCATIONAL_RATIONALE_TEMPLATES.get(ctype)
        if rationale:
            new["educational_rationale"] = rationale
        enriched.append(new)
    return enriched


def _build_bom(components: list) -> tuple:
    """回傳 (bom_rows, total_ma, total_ntd, total_mw)。"""
    rows = []
    total_ma = 0.0
    total_ntd = 0
    supply_v = 5.0
    for c in components:
        ctype = c.get("type", "")
        qty = c.get("qty", 1)
        spec = COMPONENT_REGISTRY.get(ctype)
        label = spec.name if spec else ctype
        unit_ma = POWER_MA.get(ctype, 20)
        unit_ntd = PRICE_NTD.get(ctype, 50)
        comp_ma = unit_ma * qty
        comp_ntd = unit_ntd * qty
        total_ma += comp_ma
        total_ntd += comp_ntd
        rows.append({
            "role": c.get("role", ""), "type": ctype,
            "label": label, "qty": qty,
            "unit_ma": unit_ma, "total_ma": comp_ma,
            "unit_ntd": unit_ntd, "total_ntd": comp_ntd,
        })
    total_mw = total_ma * supply_v
    return rows, total_ma, total_ntd, total_mw


def _phase3_check(power_ok: bool, total_ma: float, budget_ma: float, power_type: str) -> dict:
    """產生 phase3_constraint_check 結構（其餘子規則均假設 ok=True，因為無實際 wiring）。"""
    return {
        "overall_ok": power_ok,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "results": {
            "power": {
                "ok": power_ok,
                "details": [{
                    "level": "OK" if power_ok else "ERROR",
                    "rule": "PowerBudget",
                    "msg": f"{total_ma:.0f}/{budget_ma:.0f} mA ({power_type})",
                }],
            },
            "io":          {"ok": True, "details": []},
            "pin_current": {"ok": True, "details": []},
            "wiring":      {"ok": True, "details": []},
            "geometry":    {"ok": True, "details": {"spatial_ok": True}},
            "interference":{"ok": True, "details": {"ok": True}},
        },
    }


def _infer_clarify_hints(tpl: dict) -> dict:
    """從 category + power component 推導 clarify 預設答案。"""
    cat = tpl.get("category", "")
    env_map = {
        "Gardening": "陽台/半戶外", "Smart_Home": "室內", "Robotics": "室內",
        "Interactive_Art": "室內", "Security": "室內", "Education": "室內",
    }
    power_map = {
        "Battery-AA-class": "AA 電池",
        "Battery-LiPo-class": "太陽能 + 鋰電池",
        "USB-5V-class": "USB 插電",
        "AC-Adapter-class": "USB 插電",
        "USB-Adapter-class": "USB 插電",
    }
    power_type = next((c["type"] for c in tpl["components"] if c.get("role") == "Power"), "USB-5V-class")
    has_wifi = any("ESP32" in c["type"] or "ESP8266" in c["type"] for c in tpl["components"])
    return {
        "environment": env_map.get(cat, "室內"),
        "power_source": power_map.get(power_type, "USB 插電"),
        **({"connectivity": "WiFi + 手機 App"} if has_wifi else {}),
    }


_PIN_BUDGET: dict[str, int] = {
    "Sensor-SoilMoisture-class": 1, "Sensor-Light-class": 1,
    "Sensor-Ultrasonic-class": 2, "Sensor-PIR-class": 1,
    "Sensor-TempHumid-class": 1, "Remote-class": 1,
    "Display-OLED-class": 2,  # I2C
    "Display-LCD-class": 2,
    "Motor-DC-class": 2, "Motor-Stepper-class": 4, "Motor-Servo-class": 1,
    "Pump-Water-class": 1,
    "Relay-Module-class": 1,
    "Lighting-LED-PWM-class": 1, "Lighting-LED-RGB-class": 3,
    "Lighting-NeoPixel-class": 1,
    "MP3-Module-class": 2, "Buzzer-Active-class": 1, "Buzzer-Passive-class": 1,
    "Button-class": 1, "Switch-class": 1,
}

_POWER_KEY: dict[str, str] = {
    "Battery-AA-class": "AA", "Battery-4AA-class": "Battery-4AA", "Battery-LiPo-class": "LiPo",
    "USB-5V-class": "USB-5V", "AC-Adapter-class": "DC-5V",
    "USB-Adapter-class": "USB-5V", "USB-Buck-5V-class": "USB-5V",
    "LiPo-Charger-class": "LiPo", "BatteryHolder-AA-class": "AA",
}

_OUTPUT_ROLES: frozenset[str] = frozenset({"Output", "Control"})
_SENSOR_ROLES: frozenset[str] = frozenset({"Sensor"})

# 直驅多實例件(biped 2026-06-13):qty>1 時每單元需獨立訊號腳(4×SG90 各一 PWM),
# 故展開為帶 ~N 尾綴的獨立 wiring 實例(Servo, Servo~2, …)。driver-mediated 件(DC 馬達
# 經 L298N 共驅動板)不在此集——維持單一 wiring(現況),qty 只進功耗/腳數預算。
_MULTI_INSTANCE_DIRECT: frozenset[str] = frozenset({"Motor-Servo-class"})


def build_canned_bridge(tpl_id: str, tpl: dict) -> dict:
    """主生成函式 — 從 TEMPLATE_DEF 構造 canned bridge JSON。"""
    components = _enrich_components(tpl["components"])
    sizing = _enclosure_sizing(components)
    bom, total_ma, total_ntd, total_mw = _build_bom(components)
    supply_ma = _supply_ma(components)
    power_type = next(
        (c.get("type") for c in components if c.get("role") == "Power"),
        "USB-5V-class",
    )
    power_ok = total_ma <= supply_ma
    p3check = _phase3_check(power_ok, total_ma, supply_ma, power_type)

    # 計算總 pin（粗略估算：除 Power/Housing 外每元件 1-3 pin）
    total_pins = sum(_PIN_BUDGET.get(c["type"], 0) * c.get("qty", 1)
                     for c in components if c.get("role") not in ("Power", "Housing"))

    subsystems = []
    for c in components:
        ctype = c.get("type", "")
        spec = COMPONENT_REGISTRY.get(ctype)
        rationale = EDUCATIONAL_RATIONALE_TEMPLATES.get(ctype, "")
        unit_ma = POWER_MA.get(ctype, 20)
        pins = _PIN_BUDGET.get(ctype, 0) if c.get("role") not in ("Power", "Housing") else 0
        subsystems.append({
            "role": c.get("role"),
            "part": spec.name if spec else ctype,
            "type": ctype,
            "reason": rationale or f"{ctype} 為此專案之 {c.get('role')} 元件",
            "power_mw": int(unit_ma * 5 * c.get("qty", 1)),
            "pins": pins * c.get("qty", 1),
        })

    role_alts = _build_role_alternatives(components, {"project_category": tpl["category"]})

    # 合成 wiring + schematic：lib.wiring / lib.schematic
    brain_type = next((c["type"] for c in components if c.get("role") == "Brain"), "Arduino-Uno-class")
    comp_names = []
    for c in components:
        if c.get("role") in ("Power", "Housing", "Brain"):
            continue
        ctype = c["type"]
        cqty = c.get("qty", 1)
        comp_names.append(ctype)
        if ctype in _MULTI_INSTANCE_DIRECT and cqty > 1:
            # 第 2..N 個單元帶 ~N 尾綴 → 獨立 wiring/allocation 實例(各配獨立 SIG 腳)
            comp_names.extend(f"{ctype}~{i}" for i in range(2, cqty + 1))
    try:
        wiring_data = wiring_to_json(brain_type, comp_names)
    except Exception as exc:
        # No-Silent-Fallback: a wiring synthesis failure would ship an
        # electrically-empty demo (empty allocation/pin_labels/wiring) that is
        # still indexed as a valid canned case. Abort this template instead.
        raise RuntimeError(
            f"{tpl_id} wiring 合成失敗：{exc} — refusing to bake a canned bridge "
            f"with empty wiring (brain={brain_type}, comps={comp_names})"
        ) from exc

    # schematic SVG — 從 components 拆出 outputs / sensors，展開 qty
    svg_outputs = []
    svg_sensors = []
    for c in tpl["components"]:
        role = c.get("role", "")
        ctype = c.get("type", "")
        qty = c.get("qty", 1)
        if role in _OUTPUT_ROLES:
            svg_outputs.extend([ctype] * qty)
        elif role in _SENSOR_ROLES:
            svg_sensors.extend([ctype] * qty)
    svg_power = _POWER_KEY.get(power_type, "USB-5V")
    try:
        schematic_svg = schematic_generate_svg(brain_type, svg_power, svg_outputs, svg_sensors)
    except Exception as exc:
        print(f"  [WARN]{tpl_id} schematic SVG 生成失敗：{exc}")
        schematic_svg = ""

    bridge = {
        "project_name": f"{tpl_id}_demo",
        "project_category": tpl["category"],
        "_instruction": tpl["prompt"],
        "_canned_demo": True,
        "checkpoint_phase": 5,
        "components_resolved": True,
        "cot_plan": {
            "high_level_plan": tpl["high_level_plan"],
            "subsystems": subsystems,
            "parameter_hints": {
                "enclosure_size": sizing.get("target_size", "compact"),
                "material": "PLA",
                "wall_thickness_mm": 2.0,
                "has_lid": True,
                **_infer_clarify_hints(tpl),
            },
            "power_summary": {
                "total_mw": int(total_mw),
                "budget_mw": int(supply_ma * 5),
            },
            "total_pins": total_pins,
        },
        "components": components,
        "enclosure_constraints": {
            "target_size": sizing.get("target_size", "compact"),
            "max_dimension_mm": sizing.get("max_dimension_mm", 150),
            "wall_thickness_mm": 2.0,
            "material": "PLA",
        },
        "enclosure_sizing": sizing,
        "inventory_mentions": [],
        "bom": bom,
        "power_budget": {
            "total_ma": round(total_ma, 1),
            "budget_ma": supply_ma,
            "ok": power_ok,
            "supply_v": 5.0,
            "power_source": power_type,
            "needs_ldo": False,
            "total_mw": round(total_mw, 1),
            "needs_ventilation": total_mw > 1500,
        },
        "phase3_constraint_check": p3check,
        "wiring_notes": [] if power_ok else [
            f"⚡ 功耗超標：總計 {total_ma:.0f} mA > 上限 {supply_ma:.0f} mA",
        ],
        "schematic_svg": schematic_svg,
        "scope_note": tpl.get("scope") == "layer4" and "（Layer 4 進階範本：未來迭代）" or "",
        "role_alternatives": role_alts,  # Extract view 多候選比較
        "wiring": wiring_data.get("wiring", {}),  # ELK schematic + per-component testCode
        "pin_allocation": wiring_data.get("allocation", {}),
        "pin_labels": wiring_data.get("pin_labels", {}),
    }

    # ── Phase 4: Assembly Solver → cad_output ──────────────────────
    wall = sizing.get("wall_thickness_mm", 2.0)
    cap = sizing.get("max_dimension_mm", 150)
    area = sizing.get("estimated_area_mm2", 8000)
    side = math.sqrt(area) * 1.15
    # B1 fix: use footprint estimate as floor only; solver's autosize owns the
    # final size via pack_compact/autosize_enclosure. The old min(side, cap-2*wall)
    # was an upper clamp that could starve large layouts and force OOB/overlap.
    inner_l = round(side, 1)
    inner_w = round(side * 0.75, 1)
    # B3 fix: inner_h must not be hardcoded to 60.0. Pass a small floor and let
    # solve_v3's autosize_enclosure shrink-wrap the real component stack heights.
    # The _MIN_INNER floor (20mm) is the absolute minimum; solve_v3 will grow it.
    _MIN_INNER_H = 20.0
    inner_h = _MIN_INNER_H
    # Post-solve advisory: warn if result exceeds manufacturability cap.
    if inner_l > cap - 2 * wall or inner_w > cap - 2 * wall:
        print(f"  [INFO]{tpl_id}: footprint estimate ({inner_l:.1f}x{inner_w:.1f}mm) "
              f"exceeds cap-2wall ({cap - 2 * wall:.1f}mm); solver will size to fit")
    enclosure_spec = {
        "inner_length": inner_l,
        "inner_width": inner_w,
        "inner_height": inner_h,
        "wall": wall,
        "tol": 0.3,
    }
    try:
        from lib.assembly_solver import solve as assembly_solve
        solver_result = assembly_solve(
            components=components,
            wiring_raw=wiring_data.get("wiring", {}),
            enclosure_spec=enclosure_spec,
        )
        bridge["cad_output"] = {
            "component_placements": solver_result.get("placements", []),
            "panel_placements": solver_result.get("panel_placements", []),
            "external_refs": solver_result.get("external_refs", []),
            "embedded_refs": solver_result.get("embedded_refs", []),
            "thermal_field": solver_result.get("thermal_field", {}),
            "wire_routes": solver_result.get("wire_routes", []),
            "decisions": solver_result.get("decisions", []),
            "spec": enclosure_spec,
            "engine": "build123d",
        }
    except Exception as exc:
        # No-Silent-Fallback: a solver crash would leave bridge without cad_output
        # (no placements/STL) yet main() would still index it as a valid case.
        raise RuntimeError(
            f"{tpl_id} assembly solver failed: {exc} — refusing to bake a canned "
            f"bridge without cad_output"
        ) from exc

    # ── Phase 4 V3: SceneGraph (auto-sized enclosure + reserved wall holes) ──
    try:
        from lib.assembly_solver.assembly_solver_v3 import solve_v3
        scene_graph_v3 = solve_v3(
            components=components,
            wiring_raw=wiring_data.get("wiring", {}),
            enclosure_spec=enclosure_spec,
        )
        bridge.setdefault("cad_output", {})["scene_graph_v3"] = scene_graph_v3
        # B3 fix: update stored spec to reflect v3's auto-sized inner dimensions
        # so test_assembly_placement's enclosure-bounds check reads the actual box,
        # not the floor seed (inner_h=_MIN_INNER_H=20mm).
        v3_inner = scene_graph_v3.get("enclosure", {}).get("inner")
        if v3_inner and len(v3_inner) == 3:
            actual_spec = dict(enclosure_spec)
            actual_spec["inner_length"] = v3_inner[0]
            actual_spec["inner_width"]  = v3_inner[1]
            actual_spec["inner_height"] = v3_inner[2]
            bridge["cad_output"]["spec"] = actual_spec
        if not scene_graph_v3.get("validation", {}).get("passed", False):
            # Always-green-gate fix: a FAILED geometry/placement validation must
            # block the bake, not just warn. Otherwise a broken scene ships
            # byte-identically to a passing one and is indexed as a valid demo.
            raise RuntimeError(
                f"{tpl_id} scene_graph_v3 validation FAILED — refusing to index a "
                f"canned bridge with an invalid scene graph"
            )
    except Exception as exc:
        # Re-raise so a solver crash aborts the bake instead of shipping a bridge
        # without scene_graph_v3 (no placements/STL) that main() would still index.
        raise RuntimeError(
            f"{tpl_id} assembly solver v3 failed: {exc}"
        ) from exc

    return bridge


def main() -> None:
    out_dir = ROOT / "v6" / "canned"
    out_dir.mkdir(parents=True, exist_ok=True)

    index = []
    for tpl_id, tpl in TEMPLATE_DEFS.items():
        bridge = build_canned_bridge(tpl_id, tpl)
        path = out_dir / f"{tpl_id}.json"
        path.write_text(
            json.dumps(bridge, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        index.append({
            "id": tpl_id,
            "name": tpl["name"],
            "category": tpl["category"],
            "scope": tpl.get("scope", "in_scope"),
            "components_count": len(tpl["components"]),
            "total_ma": bridge["power_budget"]["total_ma"],
            "budget_ma": bridge["power_budget"]["budget_ma"],
            "power_ok": bridge["power_budget"]["ok"],
        })
        print(f"  ✓ {tpl_id:25} {tpl['name']:8} "
              f"{bridge['power_budget']['total_ma']:>5.0f}/"
              f"{bridge['power_budget']['budget_ma']:>4d} mA "
              f"{'OK' if bridge['power_budget']['ok'] else '⚠ 超標'}")

    (out_dir / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ 已輸出 {len(index)} 個 canned bridge 至 {out_dir}")


if __name__ == "__main__":
    main()
