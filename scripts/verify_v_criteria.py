"""scripts/verify_v_criteria.py — V1/V2/V3/V5.1/V6 驗收檢查。

對應「驗收標準（用戶定義）」：
  V1  pipeline 流程順序 + bridge_store 契約
  V2  電氣規劃邏輯閉合 + 失敗時 gate 觸發
  V3  Schematic 涵蓋全部非 Brain/Power 元件
  V5.1 IO 孔位精度（REGISTRY pin 抽樣 vs datasheet）
  V6  測試代碼存在性（scripts/ 下檔案 + AST）

執行：
  python scripts/verify_v_criteria.py
"""
from __future__ import annotations

import os
import re
import sys
import ast
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

ROOT = Path(__file__).resolve().parents[1]


# ────────────────────────────────────────────────────────────────
# V1 — pipeline 順序 + bridge_store 契約
# ────────────────────────────────────────────────────────────────

def verify_v1() -> dict:
    """檢查 pipeline_runner 確實依 PhaseID 順序跑 + 各 Phase handler 存在。"""
    pr = ROOT / "services" / "pipeline_runner.py"
    src = pr.read_text(encoding='utf-8')

    handler_imports = re.findall(r"from \.phase_handlers\.phase(\d)_handler import Phase(\d)Handler", src)
    handler_ok = sorted(set(int(a) for a, b in handler_imports)) == [1, 2, 3, 4, 5, 6, 7]

    has_for_phase = bool(re.search(r"for\s+phase_id\s+in\s+PhaseID", src))
    has_save_after = bool(re.search(r"validate_bridge\(bridge,\s*phase=phase_id\.value\)", src))
    has_critical_block = bool(re.search(r"raise\s+ValueError\(\s*\n?\s*f?[\"']Bridge 結構驗證失敗", src))

    bs = (ROOT / "services" / "shared" / "bridge_store.py").read_text(encoding='utf-8')
    has_save_bridge = "def save_bridge" in bs
    has_load_bridge = "def load_bridge" in bs
    has_validate = "def validate_bridge" in bs

    return {
        "phase_handlers_imported": handler_ok,
        "iterates_PhaseID_in_order": has_for_phase,
        "validate_bridge_per_phase": has_save_after,
        "critical_failure_blocks": has_critical_block,
        "bridge_store_save_load_validate": has_save_bridge and has_load_bridge and has_validate,
        "ok": all([handler_ok, has_for_phase, has_save_after,
                   has_critical_block, has_save_bridge, has_load_bridge, has_validate]),
    }


# ────────────────────────────────────────────────────────────────
# V2 — 電氣規劃閉合 + 失敗時 gate 觸發
# ────────────────────────────────────────────────────────────────

def _run_p2_then_p3(components: list, project_name: str = "v_test") -> dict:
    """跑 Phase II（補 spec）→ Phase III（電氣 + Schematic）。回傳 bridge。"""
    from services.phase_handlers.phase2_handler import Phase2Handler
    from services.phase_handlers.phase3_handler import Phase3Handler
    from services.shared.models import Job, JobStatus
    import services.shared.bridge_store as bs
    import tempfile
    import uuid
    tmpdir = Path(tempfile.mkdtemp(prefix='v_p23_'))
    bs.project_output_dir = lambda job: str(tmpdir)

    bridge = {
        "project_name": project_name,
        "project_category": "Smart_Home",
        "cot_plan": {"parameter_hints": {"wall_thickness_mm": 2.0, "material": "PLA"}},
        "components": components,
        "enclosure_constraints": {
            "target_size": "compact", "max_dimension_mm": 150,
            "wall_thickness_mm": 2.0, "material": "PLA",
        },
        "inventory_mentions": [],
    }
    job = Job(job_id=str(uuid.uuid4())[:8], project_name=project_name,
              instruction="x", status=JobStatus.RUNNING)
    try:
        bridge, _ = Phase2Handler().execute(job, bridge, progress_cb=lambda m: None)
        bridge, _ = Phase3Handler().execute(job, bridge, progress_cb=lambda m: None)
        return bridge
    except Exception as exc:
        return {"_error": str(exc), "_traceback": __import__("traceback").format_exc()}


def verify_v2() -> dict:
    """跑 Phase II → III 兩個情境：合規 vs 超標。"""
    pr = ROOT / "services" / "pipeline_runner.py"
    src = pr.read_text(encoding='utf-8')

    # 情境 A：合規（Arduino + DHT22 + OLED ≈ 50+1.5+20=71.5mA < 500）
    a_bridge = _run_p2_then_p3([
        {"role": "Brain",   "type": "Arduino-Uno-class",      "qty": 1},
        {"role": "Sensor",  "type": "Sensor-TempHumid-class", "qty": 1},
        {"role": "Display", "type": "Display-OLED-class",     "qty": 1},
    ], project_name="v2_compliant")
    if "_error" in a_bridge:
        return {"_error": a_bridge["_error"], "ok": False}
    a_pb = a_bridge.get("power_budget", {})
    a_chk = a_bridge.get("phase3_constraint_check", {})

    # 情境 B：超標（Pump 200mA + 4 顆 LED-Matrix 每顆 320mA = ~1480mA > 500）
    b_bridge = _run_p2_then_p3([
        {"role": "Brain",    "type": "Arduino-Uno-class",  "qty": 1},
        {"role": "Actuator", "type": "Pump-Water-class",   "qty": 1},
        {"role": "Display",  "type": "LED-Matrix-class",   "qty": 4},
    ], project_name="v2_overload")
    if "_error" in b_bridge:
        return {"_error": b_bridge["_error"], "ok": False}
    b_pb = b_bridge.get("power_budget", {})
    b_chk = b_bridge.get("phase3_constraint_check", {})

    return {
        "compliant_ma": a_pb.get("total_ma"),
        "compliant_overall_ok": a_chk.get("overall_ok"),
        "compliant_pass": a_pb.get("ok") is True and a_chk.get("overall_ok") is True,
        "overload_ma": b_pb.get("total_ma"),
        "overload_budget_ma": b_pb.get("budget_ma"),
        "overload_power_ok": b_pb.get("ok"),
        "overload_overall_ok": b_chk.get("overall_ok"),
        "overload_triggers_gate": b_chk.get("overall_ok") is False,
        "gate_definition_in_runner": "_p3_constraint_gate" in src,
        "skip_gate_allowed_by_design": "CHOICE_SKIP_GATE" in src,
        "ok": (a_chk.get("overall_ok") is True
               and b_chk.get("overall_ok") is False),
    }


# ────────────────────────────────────────────────────────────────
# V3 — Schematic 涵蓋全部 components（Brain 不算，Power 為 rail）
# ────────────────────────────────────────────────────────────────

def verify_v3() -> dict:
    """跑 Phase II→III 在 5 元件專案，確認 schematic_svg 含每個元件 token。"""
    components = [
        {"role": "Brain",    "type": "Arduino-Uno-class",        "qty": 1},
        {"role": "Sensor",   "type": "Sensor-TempHumid-class",   "qty": 1},
        {"role": "Sensor",   "type": "Sensor-PIR-class",         "qty": 1},
        {"role": "Display",  "type": "Display-OLED-class",       "qty": 1},
        {"role": "Motor",    "type": "Motor-Servo-class",        "qty": 1},
    ]
    out = _run_p2_then_p3(components, project_name="v3_test")
    if "_error" in out:
        return {"_error": out["_error"], "ok": False}
    svg = out.get("schematic_svg", "") or ""
    wiring = out.get("wiring", {}) or {}
    allocation = out.get("pin_allocation", {}) or {}

    # 每個非 Brain/Power 元件的短名
    from lib.wiring import normalize_comp
    expected_shorts = []
    for c in components:
        if c["role"] in ("Brain", "Power"):
            continue
        expected_shorts.append(normalize_comp(c["type"]))

    # SVG 是否含每個元件短名（label 文字或 text 節點）
    found = {s: (s in svg) for s in expected_shorts}
    coverage = sum(1 for v in found.values() if v) / max(1, len(found))

    # wiring 是否覆蓋每個元件
    wiring_keys = set(wiring.keys())
    wiring_coverage = sum(1 for s in expected_shorts if s in wiring_keys) / max(1, len(expected_shorts))

    return {
        "n_expected": len(expected_shorts),
        "expected_shorts": expected_shorts,
        "svg_bytes": len(svg),
        "components_in_svg": found,
        "svg_coverage_pct": round(coverage * 100, 1),
        "wiring_keys": sorted(wiring_keys),
        "wiring_coverage_pct": round(wiring_coverage * 100, 1),
        "n_wires": sum(len(w.get("pins", [])) for w in wiring.values()),
        "ok": coverage == 1.0 and wiring_coverage == 1.0,
    }


# ────────────────────────────────────────────────────────────────
# V5.1 — IO 孔位精度（REGISTRY 抽樣 vs datasheet 已知值）
# ────────────────────────────────────────────────────────────────

def verify_v51() -> dict:
    """REGISTRY port 抽樣檢查。

    當前 SSOT 採「header 整合區」表示法（非每 pin 一個 ConnectorPort）：
      - PIR / DHT22 / OLED / LCD: 單一 header 涵蓋全 pin 區域
      - Servo: 仍維持 GND/VCC/SIGNAL 3 pin（測 pin pitch 2.54mm ± 0.5mm）
      - Arduino: ports 為 USB/DC-Jack 等對外接口，mounting_holes 來自 lib/pcb（三來源交叉驗證）

    驗收：
      - 每元件至少 1 個 port，所有 port (x, y) 落在 board 範圍 [0, length_mm] × [0, width_mm]
      - Servo GND/VCC/SIGNAL pin 間距 2.54 ± 0.5 mm
      - Arduino mounting_holes 數量 = 4
    """
    from lib.registry import COMPONENT_REGISTRY

    def _within_board(spec) -> bool:
        for p in spec.ports:
            if not (0 <= p.x <= spec.length_mm + 0.5):
                return False
            if not (0 <= p.y <= spec.width_mm + 0.5):
                return False
        return True

    def _pin_pitch(spec, pin_names: list, axis: str) -> float:
        ports = {p.name: p for p in spec.ports}
        if not all(n in ports for n in pin_names):
            return -1.0
        coords = [getattr(ports[n], axis) for n in pin_names]
        diffs = [abs(coords[i+1] - coords[i]) for i in range(len(coords) - 1)]
        return round(sum(diffs) / len(diffs), 3) if diffs else -1.0

    results = []

    sample_classes = [
        'Sensor-PIR-class', 'Sensor-TempHumid-class',
        'Display-OLED-class', 'Display-LCD-class',
        'Motor-Servo-class', 'Arduino-Uno-class',
        'ESP32-class', 'Sensor-Ultrasonic-class', 'Pump-Water-class',
    ]
    for cls in sample_classes:
        spec = COMPONENT_REGISTRY.get(cls)
        if not spec:
            results.append({"component": cls, "test": "exists", "ok": False})
            continue
        in_board = _within_board(spec)
        results.append({
            "component": cls,
            "n_ports": len(spec.ports),
            "ports_within_board_bbox": in_board,
            "ok": in_board and len(spec.ports) >= 1,
        })

    # Servo pin pitch（仍是 per-pin 表示）
    servo = COMPONENT_REGISTRY['Motor-Servo-class']
    s_pitch = _pin_pitch(servo, ["GND", "VCC", "SIGNAL"], "x")
    results.append({
        "component": "Motor-Servo-class",
        "test": "GND/VCC/SIGNAL pin pitch",
        "expected_mm": 2.54,
        "actual_mm": s_pitch,
        "tol_mm": 0.5,
        "ok": abs(s_pitch - 2.54) < 0.5,
    })

    # Arduino mounting holes
    arduino = COMPONENT_REGISTRY['Arduino-Uno-class']
    n_holes = len(arduino.mounting_holes or [])
    results.append({
        "component": "Arduino-Uno-class",
        "test": "mounting holes count（lib/pcb 三來源交叉驗證 ≤0.004mm）",
        "expected": 4,
        "actual": n_holes,
        "ok": n_holes == 4,
    })

    # Brain 的 PCB-level pin 精度由 lib/pcb/<board>.py 提供（見 problem.md D2 已修復）
    return {
        "n_tests": len(results),
        "n_pass": sum(1 for r in results if r.get("ok")),
        "details": results,
        "note": "REGISTRY 已切換至「header 整合區」表示；per-pin pitch 僅 Servo 仍適用",
        "ok": all(r.get("ok") for r in results),
    }


# ────────────────────────────────────────────────────────────────
# V6 — 測試代碼存在性
# ────────────────────────────────────────────────────────────────

def verify_v6() -> dict:
    """掃 scripts/ 下 test_*.py / verify_*.py / phase_*.py 並 AST 驗證。"""
    scripts_dir = ROOT / "scripts"
    test_patterns = ["test_*.py", "verify_*.py", "phase_*.py"]
    found = []
    for pat in test_patterns:
        found.extend(sorted(scripts_dir.glob(pat)))

    results = []
    for f in found:
        try:
            ast.parse(f.read_text(encoding='utf-8'))
            results.append({"file": f.name, "ast_ok": True})
        except SyntaxError as exc:
            results.append({"file": f.name, "ast_ok": False, "err": str(exc)})

    return {
        "n_files": len(found),
        "n_ast_ok": sum(1 for r in results if r["ast_ok"]),
        "files": [r["file"] for r in results],
        "details": results,
        "ok": len(found) >= 5 and all(r["ast_ok"] for r in results),
    }


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

def _print(label: str, r: dict):
    mark = "✅" if r.get("ok") else "❌"
    print(f"\n{mark} {label}")
    for k, v in r.items():
        if k in ("ok",):
            continue
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        elif isinstance(v, list):
            preview = v if len(v) <= 6 else v[:6] + ["…"]
            print(f"  {k}: {preview}")
        else:
            print(f"  {k}: {v}")


def main():
    print("=" * 70)
    print("V1/V2/V3/V5.1/V6 驗收檢查")
    print("=" * 70)

    r1  = verify_v1();  _print("V1  pipeline 流程",       r1)
    r2  = verify_v2();  _print("V2  電氣規劃閉合 + gate", r2)
    r3  = verify_v3();  _print("V3  Schematic 涵蓋",      r3)
    r51 = verify_v51(); _print("V5.1 IO 孔位精度",         r51)
    r6  = verify_v6();  _print("V6  測試代碼呈現",         r6)

    summary = {
        "V1":   r1["ok"], "V2":   r2["ok"], "V3":   r3["ok"],
        "V5.1": r51["ok"], "V6":   r6["ok"],
    }
    print("\n" + "=" * 70)
    print("彙總：", summary)
    print("=" * 70)
    return 0 if all(summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
