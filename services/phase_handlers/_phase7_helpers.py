"""phase_handlers/_phase7_helpers.py — Phase VII BOM + Assembly SOP generation.

Extracted from phase7_handler.py to keep files under 500 lines.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

_logger = logging.getLogger(__name__)

from ..shared.models import Job
from ..shared.bridge_store import project_output_dir
from lib.bom_calculator import calculate_bom as _calculate_bom
from lib.config import ENCLOSURE_DEFAULTS as _ENC_DEFAULTS

_PRINT_TEMPS = {
    "PLA":  ("200-210°C", "60°C"),
    "PETG": ("230-245°C", "80°C"),
    "ABS":  ("240-260°C", "100°C"),
}


def _log(cb: Optional[Callable], msg: str) -> None:
    if cb:
        cb(f"[Phase VII] {msg}")
    else:
        print(f"[Phase VII] {msg}")


def write_final_bom(
    job: Job,
    bridge: dict,
    progress_cb: Optional[Callable[[str], None]],
) -> None:
    """HITL 完成後輸出最終 BOM.md，反映所有元件變更與 HITL 修正結果。"""
    components = bridge.get("components", [])
    if not components:
        return

    bom = _calculate_bom(components)
    rows = bom.rows
    total_ma = bom.total_ma
    total_ntd = bom.total_ntd

    hitl_history = bridge.get("hitl_history", [])
    score        = bridge.get("hitl_score", 0)
    enc          = bridge.get("enclosure_constraints", {})
    material     = enc.get("material", _ENC_DEFAULTS["material"])
    wall         = enc.get("wall_thickness_mm", _ENC_DEFAULTS["wall_thickness_mm"])
    cad_quality  = bridge.get("cad_quality", "unknown")
    if cad_quality == "unknown":
        _logger.debug("bridge missing cad_quality for job %s", job.job_id)

    lines = [
        f"# Final Bill of Materials -- {job.project_name}",
        f"> HITL score: **{score}/100**  |  CAD quality: **{cad_quality}**",
        f"> material: {material}  |  wall: {wall} mm",
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
        "## HITL corrections",
    ]
    if hitl_history:
        for h in hitl_history:
            lines.append(f"- [{h.get('timestamp','')}] `{h.get('action')}` "
                         f"-> {h.get('new_value', h.get('added', h.get('replaced', 'ok')))}")
    else:
        lines.append("- none (accepted directly)")

    content = "\n".join(lines) + "\n"
    bridge["final_bom"] = rows
    bridge["final_bom_total_ma"]  = round(total_ma, 1)
    bridge["final_bom_total_ntd"] = total_ntd

    proj_dir = bridge.get("_project_output_dir")
    if proj_dir:
        bom_dir = Path(proj_dir) / "bom"
    else:
        bom_dir = project_output_dir(job.job_id, job.project_name) / "bom"
    bom_dir.mkdir(parents=True, exist_ok=True)
    path = bom_dir / f"{job.job_id}_final_bom.md"
    try:
        path.write_text(content, encoding="utf-8")
        _log(progress_cb, f"[OK] final BOM.md -> {path}")
        bridge["final_bom_path"] = str(path)
    except OSError:
        pass


def write_assembly_sop(
    job: Job,
    bridge: dict,
    progress_cb: Optional[Callable[[str], None]],
) -> Optional[str]:
    """Generate assembly SOP markdown."""
    components = bridge.get("components", [])
    enc = bridge.get("enclosure_constraints", {})
    cad_out = bridge.get("cad_output", {})
    material = enc.get("material", _ENC_DEFAULTS["material"])
    wall = enc.get("wall_thickness_mm", _ENC_DEFAULTS["wall_thickness_mm"])
    snap = bridge.get("snap_fit_params", {})
    engine = cad_out.get("engine", "unknown")
    if engine == "unknown":
        _logger.debug("cad_output missing engine for job %s", job.job_id)
    needs_vent = bridge.get("power_budget", {}).get("needs_ventilation", False)

    lines = [
        f"# Assembly SOP -- {job.project_name}",
        "",
        "## Pre-print checklist",
        f"- Material: **{material}**",
        f"- Wall thickness: **{wall} mm**",
        f"- Layer height: 0.2 mm ({material})",
        f"- Nozzle temp: {_PRINT_TEMPS.get(material, ('200°C', '60°C'))[0]}",
        f"- Bed temp: {_PRINT_TEMPS.get(material, ('200°C', '60°C'))[1]}",
        "",
        "## Print manifest",
        "| # | File | Description |",
        "|---|------|-------------|",
        f"| 1 | `enclosure_bottom.stl` | Base (with snap slots{', vent grille' if needs_vent else ''}) |",
        f"| 2 | `enclosure_lid.stl` | Lid (with snap arms) |",
    ]
    manifest = cad_out.get("component_manifest", [])
    for i, m in enumerate(manifest, 3):
        lines.append(f"| {i} | `{m.get('stl', 'N/A')}` | {m.get('role', '')} -- {m.get('type', '')} |")

    lines += [
        "",
        "## Assembly steps",
        "",
        "### Step 1: Check print quality",
        "- Inspect base snap slots for clean edges",
        "- Inspect lid snap arms for completeness",
    ]
    if snap:
        lines.append(
            f"- Snap spec: arm_t {snap.get('snap_t', 1.5)}mm x "
            f"hang {snap.get('snap_hang', 5.0)}mm x "
            f"clearance {snap.get('clearance', 0.4)}mm"
        )

    lines += [
        "",
        "### Step 2: Install components",
    ]
    for i, comp in enumerate(components, 1):
        ctype = comp.get("type", "unknown")
        role = comp.get("role", "")
        lines.append(f"{i}. Place **{ctype}** ({role}) into slot, align with IO cutout")

    schematic_path = bridge.get("schematic_svg", "")
    schematic_ref = (
        f"   Schematic path: `{schematic_path}`"
        if schematic_path else
        "   (Schematic produced by Phase III, check Phase III output dir)"
    )
    lines += [
        "",
        "### Step 3: Wiring",
        "- Follow Phase III schematic for all connections.",
        f"   Schematic is the SSOT for pin-level mapping.",
        schematic_ref,
        "- Check power polarity",
        "- Dry-test before fixing",
        "",
        "### Step 4: Close lid",
        "- Align lid snap arms with base slots",
        "- Press until snap clicks",
        f"- {'CAD is PoC mode -- snaps may not be generated, use tape or screws' if engine != 'build123d' else 'Confirm all 4 corners snapped'}",
        "",
        "### Step 5: Functional test",
        "- Upload firmware to Brain board",
        "- Test each sensor and actuator",
        "- Confirm IO cutouts do not interfere with wires",
    ]

    if needs_vent:
        lines += [
            "",
            "## Thermal notes",
            "- Vent grilles on base side walls -- do not block",
            "- For extended use, orient vent side toward airflow",
        ]

    content = "\n".join(lines) + "\n"
    bridge["assembly_sop_generated"] = True

    proj_dir = bridge.get("_project_output_dir")
    if proj_dir:
        sop_dir = Path(proj_dir) / "sop"
    else:
        sop_dir = project_output_dir(job.job_id, job.project_name) / "sop"
    sop_dir.mkdir(parents=True, exist_ok=True)
    path = sop_dir / f"{job.job_id}_assembly_sop.md"
    try:
        path.write_text(content, encoding="utf-8")
        _log(progress_cb, f"[OK] Assembly SOP -> {path}")
        bridge["assembly_sop_path"] = str(path)
        return str(path)
    except OSError:
        return None
