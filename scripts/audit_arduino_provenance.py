"""scripts/audit_arduino_provenance.py — Pilot-2.1

整合 EAGLE BRD / KiCad mod / PDF datasheet 三來源，與 lib/pcb 現值 + verified.json 現值對照，
依 ADR-002 + ADR-006 規則自動判定每欄位的 tier，輸出 CSV-fillable rows 到 stdout。

實作的欄位類別（增量擴充）：
  --category physical     物理尺寸（length/width/thickness）
  --category mounting     mounting holes
  --category pads         JANALOG+JDIGITAL+ICSP 38 pads
  --category all          全部

Usage:
  .venv/Scripts/python.exe scripts/audit_arduino_provenance.py --category physical
  .venv/Scripts/python.exe scripts/audit_arduino_provenance.py --category mounting

輸出格式：CSV 行，欄序對齊 docs/ssot_arduino_pilot/01_field_audit.csv 表頭：
  field_path,libpcb_current_value,verified_json_current_value,
  source_A_eagle_brd,source_B_kicad_mod,source_C_official_pdf,
  tier,primary_source_drift_mm,secondary_source_check,
  blocker_reason,target_destination,notes
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRD = os.path.join(ROOT, "data", "pcb_sources", "arduino_uno_r3", "eagle_official", "UNO-TH_Rev3e.brd")
KICAD = os.path.join(ROOT, "data", "pcb_sources", "arduino_uno_r3", "Arduino_UNO_R3.kicad_mod")
VERIFIED = os.path.join(ROOT, "data", "component_datasheet_verified.json")


# ═══════════════════════════════════════════════════════════════════════
# EAGLE BRD: outline + holes
# ═══════════════════════════════════════════════════════════════════════

def extract_brd_outline_and_holes(brd_path: str) -> Tuple[Optional[Tuple[float, float]], List[dict]]:
    """從 BRD <plain> 抽 outline（layer 20 = Dimension）為 bbox + 抽 <hole> 為 mounting。

    回傳 ((length_mm, width_mm), [{x, y, drill}, ...])
    """
    tree = ET.parse(brd_path)
    root = tree.getroot()
    plain = root.find(".//plain")
    if plain is None:
        return None, []

    xs, ys = [], []
    for shp in plain.iter():
        if shp.get("layer") != "20":
            continue
        if shp.tag == "wire":
            xs += [float(shp.get("x1")), float(shp.get("x2"))]
            ys += [float(shp.get("y1")), float(shp.get("y2"))]
        elif shp.tag == "rectangle":
            xs += [float(shp.get("x1")), float(shp.get("x2"))]
            ys += [float(shp.get("y1")), float(shp.get("y2"))]
    outline = None
    if xs and ys:
        outline = (round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4))

    holes = []
    for hole in plain.findall("hole"):
        holes.append({
            "x": round(float(hole.get("x", "0")), 4),
            "y": round(float(hole.get("y", "0")), 4),
            "drill": round(float(hole.get("drill", "0")), 4),
        })
    return outline, holes


# ═══════════════════════════════════════════════════════════════════════
# KiCad mod: outline + holes (padless drills or pads at mounting positions)
# ═══════════════════════════════════════════════════════════════════════

def extract_kicad_outline_and_holes(kicad_path: str) -> Tuple[Optional[Tuple[float, float]], List[dict]]:
    """從 KiCad mod 抽 (fp_line ... layer "Edge.Cuts") bbox + 抽無 numbered pad 的 NPTH 或大 drill。

    回傳 ((length_mm, width_mm), [{x, y, drill}, ...])
    KiCad mod 座標為 footprint-local，回傳時不做 offset。
    """
    import re
    text = open(kicad_path, "r", encoding="utf-8").read()

    # outline: fp_line / fp_rect / fp_circle / fp_arc with Edge.Cuts layer
    # collect points from fp_line on Edge.Cuts
    xs, ys = [], []
    fp_line_pat = re.compile(r'\(fp_line\s+\(start\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)\s+\(end\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)[^)]*?\(layer\s+"Edge\.Cuts"', re.DOTALL)
    for m in fp_line_pat.finditer(text):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    outline = None
    if xs and ys:
        outline = (round(max(xs) - min(xs), 4), round(max(ys) - min(ys), 4))

    # holes: NPTH pads or numbered pads with shape 'circle' and large drill (typical >= 3mm for mounting)
    # KiCad common pattern: (pad "" np_thru_hole ...) for mounting
    npth_pat = re.compile(r'\(pad\s+""\s+np_thru_hole\s+\w+\s+\(at\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)[^)]*\)[^)]*?\(drill\s+(-?\d+\.?\d*)', re.DOTALL)
    holes = []
    for m in npth_pat.finditer(text):
        holes.append({
            "x": round(float(m.group(1)), 4),
            "y": round(float(m.group(2)), 4),
            "drill": round(float(m.group(3)), 4),
        })
    return outline, holes


# ═══════════════════════════════════════════════════════════════════════
# verified.json + lib/pcb (existing hardcoded baselines)
# ═══════════════════════════════════════════════════════════════════════

def load_verified_arduino() -> dict:
    return json.load(open(VERIFIED, "r", encoding="utf-8"))["Arduino-Uno-class"]


def libpcb_arduino_constants() -> dict:
    """直接寫死 lib/pcb/arduino_uno_r3.py 對應的 baseline，避免 import 副作用。"""
    return {
        "physical.length_mm": 68.58,
        "physical.width_mm": 53.34,
        "physical.pcb_thickness_mm": 1.6,
        "mounting_holes": [
            {"x": 13.97, "y": 2.54, "diameter": 3.2},
            {"x": 15.24, "y": 50.80, "diameter": 3.2},
            {"x": 66.04, "y": 7.62, "diameter": 3.2},
            {"x": 66.04, "y": 35.56, "diameter": 3.2},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# ADR-002 + ADR-006 tier judgment
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SourceVal:
    kind: str          # 'eagle_brd' / 'kicad_mod' / 'official_pdf'
    role: str          # 'primary' / 'secondary' （per-field, ADR-006）
    value: Optional[float]
    ref: str
    precision_digits: int = 3

    def has_value(self) -> bool:
        return self.value is not None


def judge_tier(sources: List[SourceVal]) -> dict:
    """套 ADR-002 + ADR-006 判定，回傳 {tier, primary_drift, secondary_check, consensus, blocker_reason, demotion_notes}。"""
    present = [s for s in sources if s.has_value()]
    if not present:
        return {"tier": "X", "primary_drift": None, "secondary_check": "n/a",
                "consensus": None, "blocker_reason": "no source has value", "demotion_notes": ""}

    # initial primary set (from kind classification)
    PRIMARY_KINDS = {"eagle_brd", "kicad_mod", "jedec_standard"}
    primaries = [s for s in present if s.kind in PRIMARY_KINDS]
    secondaries = [s for s in present if s.kind not in PRIMARY_KINDS]

    if not primaries:
        return {"tier": "X" if len(secondaries) < 2 else "C",
                "primary_drift": None, "secondary_check": "n/a",
                "consensus": None,
                "blocker_reason": "no primary source available",
                "demotion_notes": ""}

    # Pick EAGLE as anchor (highest precision); other primaries compared to it
    anchor = next((s for s in primaries if s.kind == "eagle_brd"), primaries[0])
    anchor.role = "primary"

    demotion_notes = []
    # ADR-006: per-field demotion of non-anchor primaries
    for s in primaries:
        if s is anchor:
            continue
        drift = abs(s.value - anchor.value)
        if drift == 0.0:
            s.role = "primary"
        else:
            # try round-check at s.precision_digits
            rounded_anchor = round(anchor.value, s.precision_digits)
            if abs(s.value - rounded_anchor) < 10 ** (-s.precision_digits) / 2 + 1e-9:
                # within rounding of anchor at s's precision → demote to secondary
                s.role = "secondary"
                demotion_notes.append(f"{s.kind} demoted to secondary: round-check pass (Δ={drift:.4f}mm)")
            else:
                # genuine mismatch → BLOCKER
                return {"tier": "C", "primary_drift": drift,
                        "secondary_check": "fail",
                        "consensus": None,
                        "blocker_reason": f"{s.kind} value {s.value} differs from anchor {anchor.value} by {drift:.4f}mm beyond rounding tolerance",
                        "demotion_notes": "; ".join(demotion_notes)}

    # recompute primaries after demotion
    primaries_final = [s for s in primaries if s.role == "primary"]
    secondaries_final = secondaries + [s for s in primaries if s.role == "secondary"]

    # ADR-002: primary drift must be 0
    primary_drift = 0.0
    for s in primaries_final:
        if s is anchor:
            continue
        d = abs(s.value - anchor.value)
        if d > 0.0:
            return {"tier": "C", "primary_drift": d,
                    "secondary_check": "fail",
                    "consensus": None,
                    "blocker_reason": f"primary drift {d:.4f}mm (should be 0.000)",
                    "demotion_notes": "; ".join(demotion_notes)}

    consensus = anchor.value

    # ADR-002: secondary round-check
    sec_check = "n/a"
    if secondaries_final:
        sec_check = "pass"
        for s in secondaries_final:
            rounded = round(consensus, s.precision_digits)
            if abs(s.value - rounded) > 10 ** (-s.precision_digits) / 2 + 1e-9:
                return {"tier": "C", "primary_drift": primary_drift,
                        "secondary_check": "fail",
                        "consensus": consensus,
                        "blocker_reason": f"secondary {s.kind} value {s.value} not round-equal to consensus {consensus} at precision {s.precision_digits}",
                        "demotion_notes": "; ".join(demotion_notes)}

    # tier: A if ≥3 sources, B if exactly 2
    n_sources = len(primaries_final) + len(secondaries_final)
    if n_sources >= 3:
        tier = "A"
    elif n_sources == 2:
        tier = "B"
    else:
        return {"tier": "C", "primary_drift": primary_drift,
                "secondary_check": sec_check,
                "consensus": consensus,
                "blocker_reason": f"only {n_sources} source (need ≥2 for tier-B)",
                "demotion_notes": "; ".join(demotion_notes)}

    return {"tier": tier, "primary_drift": primary_drift,
            "secondary_check": sec_check, "consensus": consensus,
            "blocker_reason": "", "demotion_notes": "; ".join(demotion_notes)}


# ═══════════════════════════════════════════════════════════════════════
# Category runners
# ═══════════════════════════════════════════════════════════════════════

def csv_row(field_path, libpcb_val, verified_val, src_a, src_b, src_c, judge, target="data/verified/boards/Arduino-Uno-class.json", note=""):
    """組裝一行 CSV，逗號內含空格時用引號（簡化：只在必要時加）。"""
    def fmt(v):
        if v is None or v == "" or str(v) == "None":
            return ""
        return str(v)
    fields = [
        fmt(field_path),
        fmt(libpcb_val),
        fmt(verified_val),
        fmt(src_a),
        fmt(src_b),
        fmt(src_c),
        fmt(judge.get("tier", "")),
        fmt(judge.get("primary_drift", "")),
        fmt(judge.get("secondary_check", "")),
        fmt(judge.get("blocker_reason", "")),
        fmt(target if judge.get("tier") in ("A", "B") else "(BLOCKED)"),
        fmt(note or judge.get("demotion_notes", "")),
    ]
    return ",".join(f.replace(",", ";") for f in fields)


def run_physical():
    brd_outline, _ = extract_brd_outline_and_holes(BRD)
    kicad_outline, _ = extract_kicad_outline_and_holes(KICAD)
    verified = load_verified_arduino()["physical"]
    libpcb = libpcb_arduino_constants()

    # length_mm
    sources = [
        SourceVal("eagle_brd", "primary", brd_outline[0] if brd_outline else None,
                  "UNO-TH_Rev3e.brd plain layer-20 bbox", 3),
        SourceVal("kicad_mod", "primary", kicad_outline[0] if kicad_outline else None,
                  "Arduino_UNO_R3.kicad_mod Edge.Cuts bbox", 2),
        SourceVal("official_pdf", "secondary", 68.6,
                  "A000066 §2 Mechanical (PDF figure dim, manual)", 1),
    ]
    j = judge_tier(sources)
    print(csv_row(
        "physical.length_mm",
        libpcb["physical.length_mm"], verified.get("length_mm"),
        f"{sources[0].value}", f"{sources[1].value}", f"{sources[2].value}",
        j,
    ))

    # width_mm
    sources = [
        SourceVal("eagle_brd", "primary", brd_outline[1] if brd_outline else None,
                  "UNO-TH_Rev3e.brd plain layer-20 bbox", 3),
        SourceVal("kicad_mod", "primary", kicad_outline[1] if kicad_outline else None,
                  "Arduino_UNO_R3.kicad_mod Edge.Cuts bbox", 2),
        SourceVal("official_pdf", "secondary", 53.4,
                  "A000066 §2 Mechanical", 1),
    ]
    j = judge_tier(sources)
    print(csv_row(
        "physical.width_mm",
        libpcb["physical.width_mm"], verified.get("width_mm"),
        f"{sources[0].value}", f"{sources[1].value}", f"{sources[2].value}",
        j,
    ))

    # pcb_thickness_mm — no direct BRD/KiCad value; rely on Arduino standard
    sources = [
        SourceVal("official_pdf", "secondary", 1.6,
                  "A000066 §2 PCB thickness", 1),
        SourceVal("manufacturer_spec_page", "secondary", 1.6,
                  "store.arduino.cc Uno R3 spec page", 1),
    ]
    j = judge_tier(sources)
    print(csv_row(
        "physical.pcb_thickness_mm",
        libpcb["physical.pcb_thickness_mm"], verified.get("pcb_thickness_mm"),
        "", "", f"{sources[0].value}",
        j,
        note=f"only secondary sources available (no BRD/KiCad value for thickness); {j.get('demotion_notes','')}",
    ))


def _match_hole(target: dict, holes: List[dict], offset_x: float = 0, offset_y: float = 0) -> Optional[dict]:
    """找最接近的 hole（位置容差 1mm）。回傳 hole dict + 套 offset 後 x/y。"""
    best = None
    best_d = float("inf")
    for h in holes:
        hx = h["x"] + offset_x
        hy = h["y"] + offset_y
        d = math.hypot(hx - target["x"], hy - target["y"])
        if d < best_d:
            best_d = d
            best = {**h, "x_abs": round(hx, 4), "y_abs": round(hy, 4), "match_dist": round(d, 4)}
    if best_d <= 1.0:
        return best
    return None


def run_mounting():
    _, brd_holes = extract_brd_outline_and_holes(BRD)
    _, kicad_holes = extract_kicad_outline_and_holes(KICAD)
    verified = load_verified_arduino()
    libpcb = libpcb_arduino_constants()

    # detect kicad offset: kicad pad 1 (POWER.1) at (0,0) -> EAGLE (27.94, 2.54)
    # use that same offset for mounting holes (footprint origin same)
    kicad_offset = (27.94, 2.54)

    for i, lib_h in enumerate(libpcb["mounting_holes"]):
        brd_match = _match_hole(lib_h, brd_holes)
        kicad_match = _match_hole(lib_h, kicad_holes, *kicad_offset)
        ver_h = verified.get("mounting_holes", [{}])[i] if i < len(verified.get("mounting_holes", [])) else {}

        for axis in ("x", "y"):
            field_attr_libpcb = "x" if axis == "x" else "y"
            field_attr_ver = f"{axis}_mm"
            sources = [
                SourceVal("eagle_brd", "primary",
                          brd_match[field_attr_libpcb] if brd_match else None,
                          f"UNO-TH_Rev3e.brd hole near ({lib_h['x']},{lib_h['y']})", 3),
                SourceVal("kicad_mod", "primary",
                          kicad_match[f"{axis}_abs"] if kicad_match else None,
                          f"Arduino_UNO_R3.kicad_mod NPTH near ({lib_h['x']},{lib_h['y']})", 2),
            ]
            # secondary: PDF mechanical drawing typically does not give exact mounting hole coords
            # leave only 2 sources → tier-B candidate
            j = judge_tier(sources)
            print(csv_row(
                f"mounting_holes[{i}].{axis}_mm",
                lib_h[field_attr_libpcb], ver_h.get(field_attr_ver),
                f"{sources[0].value}", f"{sources[1].value}", "",
                j,
                note=f"no PDF secondary; {j.get('demotion_notes','')}",
            ))

        # diameter_mm
        sources = [
            SourceVal("eagle_brd", "primary",
                      brd_match["drill"] if brd_match else None,
                      f"UNO-TH_Rev3e.brd hole drill", 3),
            SourceVal("kicad_mod", "primary",
                      kicad_match["drill"] if kicad_match else None,
                      f"Arduino_UNO_R3.kicad_mod NPTH drill", 2),
        ]
        j = judge_tier(sources)
        print(csv_row(
            f"mounting_holes[{i}].diameter_mm",
            lib_h["diameter"], ver_h.get("diameter_mm"),
            f"{sources[0].value}", f"{sources[1].value}", "",
            j,
            note=f"no PDF secondary; {j.get('demotion_notes','')}",
        ))


CATEGORY_RUNNERS = {
    "physical": run_physical,
    "mounting": run_mounting,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True, choices=list(CATEGORY_RUNNERS.keys()) + ["all"])
    args = ap.parse_args()

    if args.category == "all":
        for cat in CATEGORY_RUNNERS:
            print(f"# === {cat} ===")
            CATEGORY_RUNNERS[cat]()
    else:
        CATEGORY_RUNNERS[args.category]()


if __name__ == "__main__":
    main()
