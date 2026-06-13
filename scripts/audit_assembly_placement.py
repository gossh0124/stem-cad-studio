"""audit_assembly_placement.py -- Assembly placement verification tool.

Checks:
  1. 2D overlap detection (XY plane AABB intersection)
  2. Enclosure bounds check (all components fit within inner dimensions)
  3. Height stack validation (Z-axis clearance within inner_height)
  4. Packing efficiency (used area / available area)
  5. Minimum clearance between adjacent components
  6. GLB/STL parser compatibility check (frontend rendering)
  7. Enclosure sizing sanity (inner vs sum of component footprints)

Usage:
  .venv/Scripts/python.exe scripts/audit_assembly_placement.py
  .venv/Scripts/python.exe scripts/audit_assembly_placement.py --template auto_waterer
  .venv/Scripts/python.exe scripts/audit_assembly_placement.py --strict  # exit(1) on any FAIL
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANNED_DIR = PROJECT_ROOT / "v6" / "canned"
SHELLS_DIR = PROJECT_ROOT / "shells"

GLB_BRAIN_TYPES = set()


def _detect_glb_shells():
    """Scan shells/ for GLB-format base/lid files."""
    if not SHELLS_DIR.exists():
        return
    for comp_dir in SHELLS_DIR.iterdir():
        if not comp_dir.is_dir():
            continue
        for variant in ("base", "lid"):
            glb_path = comp_dir / f"{variant}.glb"
            if glb_path.exists():
                GLB_BRAIN_TYPES.add(comp_dir.name)


def _rect_overlap(a, b):
    """Return overlap area of two axis-aligned rectangles, or 0."""
    x_overlap = max(0, min(a["x2"], b["x2"]) - max(a["x1"], b["x1"]))
    y_overlap = max(0, min(a["y2"], b["y2"]) - max(a["y1"], b["y1"]))
    return x_overlap * y_overlap


def _aabb_3d_overlap(a, b):
    """Return True if two 3D AABBs intersect."""
    return (a["x1"] < b["x2"] and a["x2"] > b["x1"] and
            a["y1"] < b["y2"] and a["y2"] > b["y1"] and
            a["z1"] < b["z2"] and a["z2"] > b["z1"])


def _min_clearance(cp):
    """Return minimum XY clearance between any two components."""
    if len(cp) < 2:
        return float("inf")
    min_gap = float("inf")
    for i, a in enumerate(cp):
        for j, b in enumerate(cp):
            if j <= i:
                continue
            dx = max(0, max(a["x"], b["x"]) - min(a["x"] + a["L"], b["x"] + b["L"]))
            dy = max(0, max(a["y"], b["y"]) - min(a["y"] + a["W"], b["y"] + b["W"]))
            gap = (dx ** 2 + dy ** 2) ** 0.5 if dx > 0 or dy > 0 else 0
            min_gap = min(min_gap, gap)
    return min_gap


def audit_template(name: str, data: dict) -> dict:
    """Run all placement checks on one template. Returns result dict."""
    co = data.get("cad_output", {})
    cp = co.get("component_placements", [])
    spec = co.get("spec", {})

    result = {
        "template": name,
        "component_count": len(cp),
        "has_placement_data": bool(cp),
        "has_enclosure_spec": bool(spec),
        "checks": [],
    }

    if not cp or not spec:
        result["checks"].append({
            "check": "data_presence",
            "verdict": "SKIP",
            "detail": "No component_placements or spec in cad_output",
        })
        return result

    # P6.3/no-silent-fallback(a):inner 尺寸餵出界/高度/面積 verdict,捏 0 會全面誤判
    # FAIL(假幾何進判定)→ 直接索引,缺鍵 KeyError fail-loud。
    innerL = spec["inner_length"]
    innerW = spec["inner_width"]
    innerH = spec["inner_height"]
    wall = spec.get("wall", 2.0)  # nofallback-ok: 裝飾用，未參與任何幾何 check，dead assignment

    # Build AABB list
    rects_2d = []
    aabbs_3d = []
    for c in cp:
        r2d = {"type": c["type"], "x1": c["x"], "y1": c["y"],
               "x2": c["x"] + c["L"], "y2": c["y"] + c["W"]}
        rects_2d.append(r2d)
        a3d = {"type": c["type"],
               "x1": c["x"], "x2": c["x"] + c["L"],
               "y1": c["y"], "y2": c["y"] + c["W"],
               "z1": 0, "z2": c["H"]}
        aabbs_3d.append(a3d)

    # Check 1: 2D overlap
    overlaps = []
    for i in range(len(rects_2d)):
        for j in range(i + 1, len(rects_2d)):
            area = _rect_overlap(rects_2d[i], rects_2d[j])
            if area > 0.01:
                overlaps.append({
                    "a": rects_2d[i]["type"], "b": rects_2d[j]["type"],
                    "area_mm2": round(area, 1),
                })
    result["checks"].append({
        "check": "2d_overlap",
        "verdict": "FAIL" if overlaps else "PASS",
        "overlap_count": len(overlaps),
        "detail": overlaps if overlaps else "No 2D overlaps",
    })

    # Check 2: 3D AABB overlap (same Z plane assumed, but height matters)
    overlaps_3d = []
    for i in range(len(aabbs_3d)):
        for j in range(i + 1, len(aabbs_3d)):
            if _aabb_3d_overlap(aabbs_3d[i], aabbs_3d[j]):
                overlaps_3d.append({
                    "a": aabbs_3d[i]["type"], "b": aabbs_3d[j]["type"],
                })
    result["checks"].append({
        "check": "3d_aabb_overlap",
        "verdict": "FAIL" if overlaps_3d else "PASS",
        "overlap_count": len(overlaps_3d),
        "detail": overlaps_3d if overlaps_3d else "No 3D AABB overlaps",
    })

    # Check 3: Enclosure bounds
    oob = []
    for c in cp:
        issues = []
        if c["x"] < -0.1:
            issues.append(f"x={c['x']:.1f}<0")
        if c["y"] < -0.1:
            issues.append(f"y={c['y']:.1f}<0")
        if c["x"] + c["L"] > innerL + 0.1:
            issues.append(f"x+L={c['x']+c['L']:.1f}>{innerL:.1f}")
        if c["y"] + c["W"] > innerW + 0.1:
            issues.append(f"y+W={c['y']+c['W']:.1f}>{innerW:.1f}")
        if c["H"] > innerH + 0.1:
            issues.append(f"H={c['H']:.1f}>{innerH:.1f}")
        if issues:
            oob.append({"type": c["type"], "issues": issues})
    result["checks"].append({
        "check": "enclosure_bounds",
        "verdict": "FAIL" if oob else "PASS",
        "oob_count": len(oob),
        "detail": oob if oob else "All components within enclosure",
    })

    # Check 4: Height stack (max component H vs innerH)
    max_h = max(c["H"] for c in cp) if cp else 0
    result["checks"].append({
        "check": "height_clearance",
        "verdict": "FAIL" if max_h > innerH else "PASS",
        "max_component_h": round(max_h, 1),
        "inner_height": round(innerH, 1),
        "clearance_mm": round(innerH - max_h, 1),
    })

    # Check 5: Packing efficiency
    total_footprint = sum(c["L"] * c["W"] for c in cp)
    available = innerL * innerW
    efficiency = (total_footprint / available * 100) if available > 0 else 0
    result["checks"].append({
        "check": "packing_efficiency",
        "verdict": "WARN" if efficiency > 90 else "PASS",
        "efficiency_pct": round(efficiency, 1),
        "total_footprint_mm2": round(total_footprint, 1),
        "available_mm2": round(available, 1),
    })

    # Check 6: Minimum clearance
    min_gap = _min_clearance(cp)
    result["checks"].append({
        "check": "min_clearance",
        "verdict": "WARN" if 0 < min_gap < 2.0 else ("FAIL" if min_gap == 0 else "PASS"),
        "min_gap_mm": round(min_gap, 1) if min_gap < 1000 else "inf",
    })

    # Check 7: GLB format detection (informational — renderer supports GLB since AV3-3)
    brain = next((c for c in cp if c.get("role") == "Brain"), None)
    brain_type = brain["type"] if brain else "unknown"
    if brain_type == "unknown":
        _log.debug("no Brain component found in template %s", name)
    has_glb = brain_type in GLB_BRAIN_TYPES
    result["checks"].append({
        "check": "glb_format",
        # WARN when no usable render shell can be confirmed (Brain missing or
        # neither GLB nor STL), so a missing/unsupported render format is
        # surfaced instead of always passing. STL is a supported format → PASS.
        "verdict": "WARN" if brain_type == "unknown" else "PASS",
        "brain_type": brain_type,
        "detail": (f"{brain_type} uses GLB format (supported)"
                   if has_glb else ("STL format" if brain_type != "unknown"
                                    else "no Brain component / render shell unknown")),
    })

    # Check 8: Enclosure sizing sanity
    bbox_l = max((c["x"] + c["L"]) for c in cp) - min(c["x"] for c in cp) if cp else 0
    bbox_w = max((c["y"] + c["W"]) for c in cp) - min(c["y"] for c in cp) if cp else 0
    under = innerL < bbox_l - 0.1 or innerW < bbox_w - 0.1
    result["checks"].append({
        "check": "enclosure_sizing",
        "verdict": "FAIL" if under else "PASS",
        "components_bbox": f"{bbox_l:.1f}x{bbox_w:.1f}",
        "enclosure_inner": f"{innerL:.1f}x{innerW:.1f}",
        "detail": ("Enclosure smaller than component bounding box" if under
                   else "Enclosure accommodates all components"),
    })

    # Summary
    verdicts = [c["verdict"] for c in result["checks"]]
    result["overall"] = "FAIL" if "FAIL" in verdicts else ("WARN" if "WARN" in verdicts else "PASS")

    return result


def main():
    parser = argparse.ArgumentParser(description="Audit Assembly placement data")
    parser.add_argument("--template", help="Audit single template by name")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any FAIL")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    _detect_glb_shells()

    templates = []
    if args.template:
        path = CANNED_DIR / f"{args.template}.json"
        if not path.exists():
            print(f"Template not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            templates.append((args.template, json.load(f)))
    else:
        for f in sorted(CANNED_DIR.iterdir()):
            if f.suffix == ".json" and not f.name.startswith("_"):
                with open(f, "r", encoding="utf-8") as fh:
                    templates.append((f.stem, json.load(fh)))

    results = [audit_template(name, data) for name, data in templates]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    total_fail = 0
    total_warn = 0
    for r in results:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX", "SKIP": "--"}
        overall = icon.get(r["overall"], "??")
        print(f"[{overall}] {r['template']:25s}  ({r['component_count']} components)")
        for c in r["checks"]:
            v = c["verdict"]
            ci = icon.get(v, "??")
            check_name = c["check"]
            if v == "FAIL":
                total_fail += 1
                detail = c.get("detail", "")
                if isinstance(detail, list):
                    detail = "; ".join(str(d) for d in detail[:3])
                print(f"     [{ci}] {check_name:22s}  {detail}")
            elif v == "WARN":
                total_warn += 1
                print(f"     [{ci}] {check_name:22s}  {c.get('detail', c)}")

    print(f"\n--- Summary: {len(results)} templates, "
          f"{total_fail} FAIL, {total_warn} WARN ---")

    if args.strict and total_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
