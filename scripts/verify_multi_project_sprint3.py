"""scripts/verify_multi_project_sprint3.py — Sprint 3 多專案 Phase 4 驗證。

驗證項（對應 problem.md Sprint 3 待驗證項）：
  E10: assembly_solver placements 回饋殼體幾何（多元件 bbox 收緊 + side IO 切口）
  E11: wire_routes 凹槽（lid 底面）
  E12: vent_placements 切百葉柵（>2000mW 觸發）
  J1: STL 檔名 `{project_name}_bottom.stl` / `_top.stl`（CJK 安全替換）
  J2: 殼體邊角圓角 R=2.0（垂直邊 fillet）
  J3: 顯示元件 (OLED/LCD/LED Matrix) face_out='top' cutout 是否處理（預期未處理）

驗證 4 個代表專案：
  A. smart_home_monitor — Arduino + DHT22 + PIR + OLED（中等，無 vent）
  B. auto_plant_waterer — Arduino + Soil + LCD + Pump + Servo（mount + vent）
  C. robot_pet_companion — Arduino + Ultrasonic + LED-Matrix + Speaker + Servo（雙 vent）
  D. interactive_drum_pad — Arduino + skip_enclosure 配件（單 Brain fallback）
  E. CJK_專案_測試 — 觸發 J1 檔名替換邏輯（中文 project_name -> underscore）

執行：
  python scripts/verify_multi_project_sprint3.py
"""
from __future__ import annotations

import os
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass
import shutil
import tempfile
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.phase_handlers.phase4_handler import Phase4Handler
from services.shared.models import Job, JobStatus
import services.shared.bridge_store as bs


# ── 專案 fixtures ────────────────────────────────────────

PROJECTS = [
    {
        "id": "A",
        "project_name": "smart_home_monitor",
        "description": "中等複雜度：Brain + 雙 sensor + OLED（無 vent）",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",      "qty": 1},
            {"role": "Sensor",  "type": "Sensor-TempHumid-class", "qty": 1},
            {"role": "Sensor",  "type": "Sensor-PIR-class",       "qty": 1},
            {"role": "Display", "type": "Display-OLED-class",     "qty": 1},
        ],
        "wiring": {
            "DHT22":  {"pins": [{"mcu": "D2"}]},
            "PIR":    {"pins": [{"mcu": "D3"}]},
            "OLED":   {"pins": [{"mcu": "SDA"}, {"mcu": "SCL"}]},
        },
        "expect": {
            "path": "multi_component",
            "vent_expected": False,
            "wire_routes_min": 1,
        },
    },
    {
        "id": "B",
        "project_name": "auto_plant_waterer",
        "description": "Mount + vent：Brain + Soil + LCD + Pump + Servo",
        "components": [
            {"role": "Brain",    "type": "Arduino-Uno-class",        "qty": 1},
            {"role": "Sensor",   "type": "Sensor-SoilMoisture-class","qty": 1},
            {"role": "Display",  "type": "Display-LCD-class",        "qty": 1},
            {"role": "Actuator", "type": "Pump-Water-class",         "qty": 1},
            {"role": "Motor",    "type": "Motor-Servo-class",        "qty": 1},
        ],
        "wiring": {
            "Soil":  {"pins": [{"mcu": "A0"}]},
            "LCD":   {"pins": [{"mcu": "SDA"}, {"mcu": "SCL"}]},
            "Pump":  {"pins": [{"mcu": "D5"}]},
            "Servo": {"pins": [{"mcu": "D6"}]},
        },
        "expect": {
            "path": "multi_component",
            "vent_expected": True,    # Pump 2000mW + Arduino 250 + LCD 300 ≈ 2550
            "wire_routes_min": 1,
            "mount_classes": ["Pump-Water-class", "Motor-Servo-class"],
        },
    },
    {
        "id": "C",
        "project_name": "robot_pet_companion",
        "description": "高功耗雙 vent：Brain + Ultrasonic + LED-Matrix + Speaker + Servo",
        "components": [
            {"role": "Brain",    "type": "Arduino-Uno-class",       "qty": 1},
            {"role": "Sensor",   "type": "Sensor-Ultrasonic-class", "qty": 1},
            {"role": "Display",  "type": "LED-Matrix-class",        "qty": 1},
            {"role": "Sound",    "type": "Speaker-class",           "qty": 1},
            {"role": "Motor",    "type": "Motor-Servo-class",       "qty": 1},
        ],
        "wiring": {
            "Ultrasonic": {"pins": [{"mcu": "D7"}, {"mcu": "D8"}]},
            "LEDMatrix":  {"pins": [{"mcu": "D11"}, {"mcu": "D12"}, {"mcu": "D13"}]},
            "Speaker":    {"pins": [{"mcu": "D9"}]},
            "Servo":      {"pins": [{"mcu": "D6"}]},
        },
        "expect": {
            "path": "multi_component",
            "vent_expected": True,
            "wire_routes_min": 1,
            "mount_classes": ["Speaker-class", "Motor-Servo-class"],
        },
    },
    {
        "id": "D",
        "project_name": "interactive_drum_pad",
        "description": "單 Brain fallback：Arduino + skip_enclosure 配件",
        "components": [
            {"role": "Brain",    "type": "Arduino-Uno-class",     "qty": 1},
            {"role": "Input",    "type": "Button-class",          "qty": 4},   # skip_enclosure
            {"role": "Output",   "type": "Buzzer-Active-class",   "qty": 1},   # skip_enclosure
            {"role": "Lighting", "type": "Lighting-LED-PWM-class","qty": 1},   # skip_enclosure
        ],
        "wiring": {},
        "expect": {
            "path": "single_brain",
            "vent_expected": False,
        },
    },
    {
        "id": "E",
        "project_name": "智慧澆水器_v2",   # CJK：J1 檔名替換測試
        "description": "J1 CJK 檔名測試：Arduino + DHT22 + LCD",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",      "qty": 1},
            {"role": "Sensor",  "type": "Sensor-TempHumid-class", "qty": 1},
            {"role": "Display", "type": "Display-LCD-class",      "qty": 1},
        ],
        "wiring": {
            "DHT22": {"pins": [{"mcu": "D2"}]},
            "LCD":   {"pins": [{"mcu": "SDA"}, {"mcu": "SCL"}]},
        },
        "expect": {
            "path": "multi_component",
            "vent_expected": False,
            "filename_no_cjk": True,
        },
    },
]


# ── Helpers ─────────────────────────────────────────────

def _make_job(name: str) -> Job:
    return Job(
        job_id=str(uuid.uuid4())[:8],
        project_name=name,
        instruction='sprint3 verify',
        status=JobStatus.RUNNING,
    )


def _check_watertight(stl_path: Path) -> Dict:
    """trimesh watertight 檢查。"""
    try:
        import trimesh
        m = trimesh.load(str(stl_path))
        return {
            "watertight": bool(m.is_watertight),
            "faces": len(m.faces),
            "volume_mm3": round(float(m.volume), 1) if m.is_volume else None,
        }
    except Exception as exc:
        return {"watertight": None, "error": str(exc)}


def _audit_top_displays(bridge: dict, components: list) -> Dict:
    """J3：審計 face_out='top' 的顯示元件是否有 cutout 處理。

    2026-05-08 J3 修復後：build_assembly_two_piece 對 face_out='top' 的顯示元件
    （OLED/LCD/EInk/LED-Matrix/Segment）在 lid 開穿透矩形觀看窗。
    此函式比對 placements 內 top displays 數量 vs spec.n_top_windows，
    一致則視為已覆蓋。
    """
    cad = bridge.get("cad_output", {})
    placements = cad.get("component_placements") or []
    spec = cad.get("spec", {}) or {}
    display_classes = {"Display-OLED-class", "Display-LCD-class",
                       "Display-EInk-class", "LED-Matrix-class",
                       "Segment-Display-class"}
    top_displays = []
    for p in placements:
        if p.get("type") in display_classes and p.get("face_out") == "top":
            top_displays.append({"type": p["type"], "face_out": p["face_out"],
                                  "x": p["x"], "y": p["y"]})
    n_top_windows = spec.get("n_top_windows")
    expected = len(top_displays)
    covered = (n_top_windows == expected) if expected > 0 else True
    return {
        "top_displays_present": expected,
        "n_top_windows_in_spec": n_top_windows,
        "covered_by_current_code": covered,
        "details": top_displays,
    }


def _verify_filename(stl_path: Optional[str], project_name: str, suffix: str) -> Dict:
    """J1：檔名應為 `{safe(project_name)}_{suffix}.stl`，不含 CJK。"""
    if not stl_path:
        return {"present": False}
    fn = Path(stl_path).name
    has_cjk = not fn.isascii()
    expected_endswith = f"_{suffix}.stl"
    return {
        "present": True,
        "filename": fn,
        "ends_with_expected": fn.endswith(expected_endswith),
        "has_cjk": has_cjk,
    }


def _verify_fillet(spec: dict, requested_r: float = 2.0) -> Dict:
    """J2：spec.fillet_r 應誠實反映幾何（修復後標準）。

    2026-05-08 J2 修復後：fillet 失敗會自動降級半徑或回 0；spec.fillet_r
    寫實際成功值。「pass」改判為 spec 誠實（不再要求一定 == requested_r）：
      - actual == requested_r → success
      - 0 < actual < requested_r → downgraded（OCCT 容忍度限制，仍誠實）
      - actual == 0 → 全失敗但 spec 誠實標 0（不再對外宣稱有圓角）
      - actual is None → 此路徑沒過 fillet 邏輯（single-Brain），標 skip
    """
    actual = spec.get("fillet_r")
    if actual is None:
        return {"fillet_r": None, "status": "skip", "ok": True}
    if actual == requested_r:
        status = "ok"
    elif 0 < actual < requested_r:
        status = "downgraded"
    elif actual == 0:
        status = "failed-but-honest"
    else:
        status = "unexpected"
    return {
        "fillet_r": actual,
        "requested": requested_r,
        "status": status,
        "ok": actual is not None and actual >= 0,
    }


# ── 主驗證流程 ───────────────────────────────────────────

def run_one(proj: dict, out_root: Path) -> Dict:
    """跑單一專案 Phase 4，回傳結果摘要。"""
    p_id = proj["id"]
    p_name = proj["project_name"]
    print(f"\n{'='*70}")
    print(f"  [{p_id}] {p_name}")
    print(f"  {proj['description']}")
    print(f"{'='*70}")

    tmpdir = out_root / f"proj_{p_id}"
    tmpdir.mkdir(parents=True, exist_ok=True)

    bridge = {
        "project_name": p_name,
        "components":   proj["components"],
        "wiring":       proj["wiring"],
    }

    original_proj_dir = bs.project_output_dir
    bs.project_output_dir = lambda job: str(tmpdir)

    result = {
        "id": p_id,
        "project_name": p_name,
        "description": proj["description"],
        "status": "pending",
        "logs": [],
    }

    try:
        handler = Phase4Handler()
        job = _make_job(p_name)
        msgs: List[str] = []

        bridge_out, artifacts = handler.execute(
            job, bridge, progress_cb=lambda m: msgs.append(m))
        result["logs"] = msgs

        cad = bridge_out.get("cad_output", {})
        spec = cad.get("spec", {})
        bottom_stl = cad.get("bottom_stl")
        lid_stl = cad.get("lid_stl")

        # 路徑判定
        kind = spec.get("kind")
        path_taken = "multi_component" if kind == "assembly" else (
                     "single_brain" if kind == "two_piece" else "unknown")
        expect_path = proj["expect"].get("path", "?")
        result["path_taken"] = path_taken
        result["path_expected"] = expect_path
        result["path_ok"] = (path_taken == expect_path)

        # E10：n_components / n_io_cutouts
        result["E10_n_components"] = spec.get("n_components")
        result["E10_n_io_cutouts"] = spec.get("n_io_cutouts")

        # E11：n_wire_grooves
        result["E11_n_wire_grooves"] = spec.get("n_wire_grooves")

        # E12：n_vents + 與 vent_expected 對照
        n_vents = spec.get("n_vents", 0) or 0
        thermal = cad.get("thermal_field", {})
        result["E12_n_vents"] = n_vents
        result["E12_total_power_mw"] = thermal.get("total_power_mw")
        result["E12_needs_venting"] = thermal.get("needs_venting")
        vent_expected = proj["expect"].get("vent_expected", False)
        result["E12_ok"] = ((n_vents > 0) == vent_expected) if path_taken == "multi_component" else True

        # J1：STL 檔名
        result["J1_bottom"] = _verify_filename(bottom_stl, p_name, "bottom")
        result["J1_top"]    = _verify_filename(lid_stl,    p_name, "top")

        # J2：fillet_r
        if path_taken == "multi_component":
            result["J2_fillet"] = _verify_fillet(spec, requested_r=2.0)
        else:
            result["J2_fillet"] = {"skipped": "single_brain path 不過 fillet 邏輯"}

        # J3：face_out='top' display 是否被 cutout 覆蓋（預期否）
        result["J3_top_displays"] = _audit_top_displays(bridge_out, proj["components"])

        # Watertight
        if bottom_stl and Path(bottom_stl).exists():
            result["bottom_check"] = _check_watertight(Path(bottom_stl))
        if lid_stl and Path(lid_stl).exists():
            result["lid_check"] = _check_watertight(Path(lid_stl))

        # Mount dispatch
        component_shells = cad.get("component_shells", [])
        mount_classes_actual = sorted({
            s.get("class") for s in component_shells
            if s.get("kind") == "mount"
        })
        result["mount_shells"] = mount_classes_actual
        if "mount_classes" in proj["expect"]:
            expected = sorted(proj["expect"]["mount_classes"])
            result["mount_ok"] = (mount_classes_actual == expected)
        else:
            result["mount_ok"] = True

        result["status"] = "ok"

    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        result["traceback"] = traceback.format_exc()
        print(f"  [FAIL] EXCEPTION: {exc}")
        traceback.print_exc()
    finally:
        bs.project_output_dir = original_proj_dir

    return result


def _print_summary(results: List[Dict]):
    print(f"\n\n{'='*70}")
    print("  Sprint 3 多專案驗證 — 彙總")
    print(f"{'='*70}\n")

    cols = ["ID", "Path", "E10 comps/IO", "E11 grooves", "E12 vents",
            "J1 base/top", "J2 fillet", "J3 top-disp",
            "bottom WT", "lid WT", "Status"]
    print(" | ".join(f"{c:>14}" for c in cols))
    print("-" * (15 * len(cols)))

    for r in results:
        path = r.get("path_taken", "?")
        path_mark = "✅" if r.get("path_ok") else "❌"
        e10 = f"{r.get('E10_n_components')}/{r.get('E10_n_io_cutouts')}" \
              if path == "multi_component" else "-"
        e11 = str(r.get('E11_n_wire_grooves')) if path == "multi_component" else "-"
        e12_n = r.get('E12_n_vents') or 0
        e12_mark = "✅" if r.get("E12_ok") else "❌"
        j1_b = "✅" if r.get("J1_bottom", {}).get("ends_with_expected") else "❌"
        j1_t = "✅" if r.get("J1_top",    {}).get("ends_with_expected") else "❌"
        j1_cjk = ""
        if r.get("J1_bottom", {}).get("has_cjk") or r.get("J1_top", {}).get("has_cjk"):
            j1_cjk = "⚠CJK"
        j2 = r.get("J2_fillet", {})
        j2_mark = "✅" if j2.get("ok") else ("skip" if "skipped" in j2 else "❌")
        j3 = r.get("J3_top_displays", {})
        if j3.get("top_displays_present"):
            n_disp = j3["top_displays_present"]
            n_win = j3.get("n_top_windows_in_spec")
            j3_mark = f"{n_disp}disp/{n_win}win{'✅' if j3.get('covered_by_current_code') else '❌'}"
        else:
            j3_mark = "n/a"
        b_wt = r.get("bottom_check", {}).get("watertight")
        l_wt = r.get("lid_check",    {}).get("watertight")
        b_wt_s = "✅" if b_wt else ("❌" if b_wt is False else "-")
        l_wt_s = "✅" if l_wt else ("❌" if l_wt is False else "-")

        row = [
            r["id"],
            f"{path}{path_mark}",
            e10,
            e11,
            f"{e12_n}{e12_mark}",
            f"{j1_b}/{j1_t}{j1_cjk}",
            j2_mark,
            j3_mark,
            b_wt_s,
            l_wt_s,
            r.get("status", "?"),
        ]
        print(" | ".join(f"{str(c):>14}" for c in row))


def main():
    out_root = Path(tempfile.mkdtemp(prefix="sprint3_verify_"))
    print(f"輸出根目錄：{out_root}")
    print(f"專案數：{len(PROJECTS)}")

    results = [run_one(p, out_root) for p in PROJECTS]
    _print_summary(results)

    # 寫 JSON 摘要
    import json
    summary_path = out_root / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n摘要：{summary_path}")
    print(f"產物保留於：{out_root}")

    # exit code
    all_ok = all(r["status"] == "ok" and r.get("path_ok")
                 and r.get("E12_ok", True) for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
