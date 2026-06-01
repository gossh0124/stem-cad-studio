"""audit_placement_supplementary.py -- Supplementary placement audit.

Checks NOT covered by audit_assembly_placement.py:
  1. Type name consistency: does stripped type have matching shells/ dir?
  2. Dimension plausibility: L/W/H vs datasheet SSOT reference
  3. Assembly rendering compatibility: pcb_body vs shell-only variants
  4. Cross-template consistency: same type => same L/W/H everywhere?

Usage:
  .venv/Scripts/python.exe scripts/audit_placement_supplementary.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANNED_DIR = PROJECT_ROOT / "v6" / "canned"
SHELLS_DIR = PROJECT_ROOT / "shells"
DATASHEET_PATH = PROJECT_ROOT / "data" / "component_datasheet_verified.json"

# Tolerances
DIM_TOLERANCE_PCT = 15.0   # % deviation from datasheet before flagging
DIM_TOLERANCE_ABS = 2.0    # mm absolute tolerance (small components)


def load_canned_templates():
    """Load all canned template JSON files."""
    templates = {}
    for f in sorted(CANNED_DIR.iterdir()):
        if f.suffix == ".json" and not f.name.startswith("_"):
            with open(f, "r", encoding="utf-8") as fh:
                templates[f.stem] = json.load(fh)
    return templates


def load_datasheet():
    """Load the SSOT datasheet."""
    with open(DATASHEET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_shell_dirs():
    """Return set of directory names under shells/."""
    if not SHELLS_DIR.exists():
        return set()
    return {d.name for d in SHELLS_DIR.iterdir() if d.is_dir()}


def get_shell_files(comp_type):
    """Return list of files in shells/{comp_type}/."""
    d = SHELLS_DIR / comp_type
    if not d.exists():
        return []
    return [f.name for f in d.iterdir() if f.is_file()]


def check_type_name_consistency(templates, shell_dirs):
    """Check 1: Does each component type have a matching shells/ directory?"""
    results = []
    all_types = set()
    for tname, tdata in templates.items():
        co = tdata.get("cad_output", {})
        for c in co.get("component_placements", []):
            all_types.add(c["type"])

    for ctype in sorted(all_types):
        has_shell = ctype in shell_dirs
        results.append({
            "type": ctype,
            "has_shell_dir": has_shell,
            "verdict": "PASS" if has_shell else "WARN",
            "detail": ("shells/{} exists".format(ctype)
                       if has_shell
                       else "No shells/{} directory -- will render as box".format(ctype)),
        })
    return results


def check_dimension_plausibility(templates, datasheet):
    """Check 2: Compare placement L/W/H against datasheet SSOT."""
    results = []
    seen = set()

    for tname, tdata in templates.items():
        co = tdata.get("cad_output", {})
        for c in co.get("component_placements", []):
            ctype = c["type"]
            key = (tname, ctype)
            if key in seen:
                continue
            seen.add(key)

            ds_entry = datasheet.get(ctype)
            if not ds_entry:
                results.append({
                    "template": tname,
                    "type": ctype,
                    "verdict": "SKIP",
                    "detail": "No datasheet entry for {}".format(ctype),
                })
                continue

            phys = ds_entry.get("physical", {})
            ref_l = phys.get("length_mm")
            ref_w = phys.get("width_mm")
            ref_h = phys.get("height_mm")

            if ref_l is None or ref_w is None or ref_h is None:
                results.append({
                    "template": tname,
                    "type": ctype,
                    "verdict": "SKIP",
                    "detail": "Incomplete datasheet dimensions",
                })
                continue

            place_l = c["L"]
            place_w = c["W"]
            place_h = c["H"]

            # Check if L/W might be swapped (rotated 90 deg)
            # Try both orientations
            deviations_normal = [
                ("L", place_l, ref_l),
                ("W", place_w, ref_w),
                ("H", place_h, ref_h),
            ]
            deviations_rotated = [
                ("L(rot)", place_l, ref_w),
                ("W(rot)", place_w, ref_l),
                ("H", place_h, ref_h),
            ]

            def calc_max_dev(devs):
                max_pct = 0
                for dim_name, actual, ref in devs:
                    if ref > 0:
                        pct = abs(actual - ref) / ref * 100
                        max_pct = max(max_pct, pct)
                    elif actual > 0:
                        max_pct = 999
                return max_pct

            max_dev_normal = calc_max_dev(deviations_normal)
            max_dev_rotated = calc_max_dev(deviations_rotated)

            # Use whichever orientation gives smaller deviation
            if max_dev_rotated < max_dev_normal:
                deviations = deviations_rotated
                rotated = True
                max_dev = max_dev_rotated
            else:
                deviations = deviations_normal
                rotated = False
                max_dev = max_dev_normal

            issues = []
            for dim_name, actual, ref in deviations:
                abs_diff = abs(actual - ref)
                if ref > 0:
                    pct = abs_diff / ref * 100
                else:
                    pct = 999 if actual > 0 else 0

                if abs_diff > DIM_TOLERANCE_ABS and pct > DIM_TOLERANCE_PCT:
                    issues.append(
                        "{}: placement={:.1f} vs datasheet={:.1f} ({:+.1f}mm, {:+.1f}%)".format(
                            dim_name, actual, ref,
                            actual - ref,
                            (actual - ref) / ref * 100 if ref > 0 else 999
                        )
                    )

            if issues:
                results.append({
                    "template": tname,
                    "type": ctype,
                    "verdict": "FAIL",
                    "rotated": rotated,
                    "placement_LWH": "{:.1f}x{:.1f}x{:.1f}".format(place_l, place_w, place_h),
                    "datasheet_LWH": "{:.1f}x{:.1f}x{:.1f}".format(ref_l, ref_w, ref_h),
                    "issues": issues,
                })
            else:
                results.append({
                    "template": tname,
                    "type": ctype,
                    "verdict": "PASS",
                    "rotated": rotated,
                    "placement_LWH": "{:.1f}x{:.1f}x{:.1f}".format(place_l, place_w, place_h),
                    "datasheet_LWH": "{:.1f}x{:.1f}x{:.1f}".format(ref_l, ref_w, ref_h),
                })

    return results


def check_rendering_compat(templates, shell_dirs):
    """Check 3: Does each component have pcb_body or only shell (base/lid) or mount?"""
    results = []
    all_types = set()
    for tname, tdata in templates.items():
        co = tdata.get("cad_output", {})
        for c in co.get("component_placements", []):
            all_types.add(c["type"])

    for ctype in sorted(all_types):
        files = get_shell_files(ctype)
        has_pcb_body_glb = "pcb_body.glb" in files
        has_pcb_body_stl = "pcb_body.stl" in files
        has_base_glb = "base.glb" in files
        has_lid_glb = "lid.glb" in files
        has_mount_glb = "mount.glb" in files
        has_meta = "meta.json" in files

        if not files:
            variant = "none"
            verdict = "FAIL"
            detail = "No shell files at all"
        elif has_pcb_body_glb:
            if has_base_glb and has_lid_glb:
                variant = "full (pcb_body + base/lid)"
                verdict = "PASS"
                detail = "Full 3D: pcb_body + enclosure shell"
            else:
                variant = "pcb_body only"
                verdict = "PASS"
                detail = "PCB body geometry available"
        elif has_mount_glb:
            variant = "mount only"
            verdict = "PASS"
            detail = "Mount geometry (motor/pump/speaker type)"
        elif has_base_glb:
            variant = "shell only (no pcb_body)"
            verdict = "WARN"
            detail = "Has enclosure shell but no pcb_body -- component renders as box inside"
        else:
            variant = "meta only"
            verdict = "WARN"
            detail = "Only meta.json, no 3D geometry"

        results.append({
            "type": ctype,
            "variant": variant,
            "files": files,
            "verdict": verdict,
            "detail": detail,
        })

    return results


def check_cross_template_consistency(templates):
    """Check 4: Same component type should have same L/W/H across templates."""
    # Collect all (L,W,H) tuples per type across all templates
    type_dims = defaultdict(list)

    for tname, tdata in templates.items():
        co = tdata.get("cad_output", {})
        for c in co.get("component_placements", []):
            ctype = c["type"]
            dims = (round(c["L"], 2), round(c["W"], 2), round(c["H"], 2))
            type_dims[ctype].append({"template": tname, "LWH": dims})

    results = []
    for ctype in sorted(type_dims.keys()):
        entries = type_dims[ctype]
        if len(entries) < 2:
            results.append({
                "type": ctype,
                "verdict": "SKIP",
                "appearances": len(entries),
                "detail": "Only appears in 1 template, nothing to compare",
            })
            continue

        unique_dims = set(e["LWH"] for e in entries)
        if len(unique_dims) == 1:
            lwh = list(unique_dims)[0]
            results.append({
                "type": ctype,
                "verdict": "PASS",
                "appearances": len(entries),
                "unique_dims": 1,
                "dim": "{:.1f}x{:.1f}x{:.1f}".format(*lwh),
                "detail": "Consistent across {} templates".format(len(entries)),
            })
        else:
            # Check if the differences might be rotation (L/W swapped)
            # Normalize to sorted(L,W) for comparison
            normalized = set()
            for lwh in unique_dims:
                key = (min(lwh[0], lwh[1]), max(lwh[0], lwh[1]), lwh[2])
                normalized.add(key)

            if len(normalized) == 1:
                detail_entries = []
                for e in entries:
                    detail_entries.append(
                        "  {}: {:.1f}x{:.1f}x{:.1f}".format(
                            e["template"], *e["LWH"]
                        )
                    )
                results.append({
                    "type": ctype,
                    "verdict": "INFO",
                    "appearances": len(entries),
                    "unique_dims": len(unique_dims),
                    "detail": "L/W swapped (rotation) across templates",
                    "entries": detail_entries,
                })
            else:
                detail_entries = []
                for e in entries:
                    detail_entries.append(
                        "  {}: {:.1f}x{:.1f}x{:.1f}".format(
                            e["template"], *e["LWH"]
                        )
                    )
                results.append({
                    "type": ctype,
                    "verdict": "FAIL",
                    "appearances": len(entries),
                    "unique_dims": len(unique_dims),
                    "detail": "INCONSISTENT dimensions across templates",
                    "entries": detail_entries,
                })

    return results


def main():
    templates = load_canned_templates()
    datasheet = load_datasheet()
    shell_dirs = get_shell_dirs()

    print("=" * 70)
    print("SUPPLEMENTARY PLACEMENT AUDIT")
    print("=" * 70)
    print("Templates: {}   Shell dirs: {}".format(len(templates), len(shell_dirs)))
    print()

    # --- Check 1: Type name consistency ---
    print("-" * 70)
    print("CHECK 1: Type Name -> shells/ Directory Mapping")
    print("-" * 70)
    c1 = check_type_name_consistency(templates, shell_dirs)
    c1_pass = sum(1 for r in c1 if r["verdict"] == "PASS")
    c1_warn = sum(1 for r in c1 if r["verdict"] == "WARN")
    for r in c1:
        icon = "OK" if r["verdict"] == "PASS" else "??"
        print("  [{}] {:40s} {}".format(icon, r["type"], r["detail"]))
    print("  --- {}/{} have shell dirs, {} missing ---".format(c1_pass, len(c1), c1_warn))
    print()

    # --- Check 2: Dimension plausibility ---
    print("-" * 70)
    print("CHECK 2: Dimension Plausibility (placement vs datasheet SSOT)")
    print("         Tolerance: {:.0f}% or {:.1f}mm".format(DIM_TOLERANCE_PCT, DIM_TOLERANCE_ABS))
    print("-" * 70)
    c2 = check_dimension_plausibility(templates, datasheet)
    c2_pass = sum(1 for r in c2 if r["verdict"] == "PASS")
    c2_fail = sum(1 for r in c2 if r["verdict"] == "FAIL")
    c2_skip = sum(1 for r in c2 if r["verdict"] == "SKIP")
    for r in c2:
        if r["verdict"] == "FAIL":
            rot = " [rotated]" if r.get("rotated") else ""
            print("  [XX] {} / {}{}".format(r["template"], r["type"], rot))
            print("        placement: {}  datasheet: {}".format(
                r["placement_LWH"], r["datasheet_LWH"]))
            for issue in r["issues"]:
                print("        -> {}".format(issue))
        elif r["verdict"] == "SKIP":
            print("  [--] {} / {} -- {}".format(r["template"], r["type"], r["detail"]))
        # PASS: silent
    print("  --- {}/{} PASS, {} FAIL, {} SKIP ---".format(
        c2_pass, len(c2), c2_fail, c2_skip))
    print()

    # --- Check 3: Rendering compatibility ---
    print("-" * 70)
    print("CHECK 3: Assembly Rendering Compatibility (pcb_body / shell / mount)")
    print("-" * 70)
    c3 = check_rendering_compat(templates, shell_dirs)
    for r in c3:
        icon = {"PASS": "OK", "WARN": "!!", "FAIL": "XX"}[r["verdict"]]
        print("  [{}] {:40s} {} -- {}".format(
            icon, r["type"], r["variant"], r["detail"]))
    c3_pass = sum(1 for r in c3 if r["verdict"] == "PASS")
    c3_warn = sum(1 for r in c3 if r["verdict"] == "WARN")
    c3_fail = sum(1 for r in c3 if r["verdict"] == "FAIL")
    print("  --- {} PASS, {} WARN, {} FAIL ---".format(c3_pass, c3_warn, c3_fail))
    print()

    # --- Check 4: Cross-template consistency ---
    print("-" * 70)
    print("CHECK 4: Cross-Template Dimension Consistency")
    print("-" * 70)
    c4 = check_cross_template_consistency(templates)
    for r in c4:
        if r["verdict"] == "SKIP":
            print("  [--] {:40s} only 1 template".format(r["type"]))
        elif r["verdict"] == "PASS":
            print("  [OK] {:40s} {} templates, consistent: {}".format(
                r["type"], r["appearances"], r.get("dim", "")))
        elif r["verdict"] == "INFO":
            print("  [~~] {:40s} {} templates, {} unique (L/W rotation)".format(
                r["type"], r["appearances"], r["unique_dims"]))
            for e in r.get("entries", []):
                print("      {}".format(e))
        elif r["verdict"] == "FAIL":
            print("  [XX] {:40s} {} templates, {} DIFFERENT dim sets".format(
                r["type"], r["appearances"], r["unique_dims"]))
            for e in r.get("entries", []):
                print("      {}".format(e))
    c4_pass = sum(1 for r in c4 if r["verdict"] == "PASS")
    c4_info = sum(1 for r in c4 if r["verdict"] == "INFO")
    c4_fail = sum(1 for r in c4 if r["verdict"] == "FAIL")
    c4_skip = sum(1 for r in c4 if r["verdict"] == "SKIP")
    print("  --- {} PASS, {} rotation-only, {} FAIL, {} single-template ---".format(
        c4_pass, c4_info, c4_fail, c4_skip))
    print()

    # --- Aggregate summary ---
    print("=" * 70)
    print("AGGREGATE SUMMARY")
    print("=" * 70)
    total_fail = c2_fail + c3_fail + c4_fail
    total_warn = c1_warn + c3_warn
    print("  Check 1 (type->shell mapping):    {} types, {} without shell dirs".format(
        len(c1), c1_warn))
    print("  Check 2 (dimension plausibility):  {}/{} PASS, {} FAIL".format(
        c2_pass, len(c2) - c2_skip, c2_fail))
    print("  Check 3 (rendering compat):        {} PASS, {} WARN, {} FAIL".format(
        c3_pass, c3_warn, c3_fail))
    print("  Check 4 (cross-template dims):     {} PASS, {} rotation, {} INCONSISTENT".format(
        c4_pass, c4_info, c4_fail))
    print()
    if total_fail > 0:
        print("  OVERALL: {} FAIL findings, {} WARN findings".format(total_fail, total_warn))
    else:
        print("  OVERALL: ALL PASS ({} warnings)".format(total_warn))
    print()


if __name__ == "__main__":
    main()
