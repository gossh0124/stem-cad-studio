"""IC-level assembly validation: overlap, wire-shell boundary, proportions.

Provides four verification passes:
  1. IC-on-PCB port overlap (per component entry)
  2. Module-level 3D AABB overlap (enclosure interior)
  3. Wire path shell boundary enforcement
  4. Dimension proportion check vs datasheet SSOT
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_log = logging.getLogger("cadhllm.ic_validation")


@dataclass
class ValidationIssue:
    check: str
    severity: str  # "error" | "warning"
    component: str
    message: str
    details: Optional[dict] = None


@dataclass
class ValidationResult:
    passed: bool
    checks_run: int = 0
    checks_passed: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "issues": [
                {"check": i.check, "severity": i.severity,
                 "component": i.component, "message": i.message,
                 "details": i.details}
                for i in self.issues
            ],
        }


# -- 1. IC port overlap on PCB -----------------------------------------------

def _port_aabb(port: dict, comp_l: float, comp_w: float) -> Optional[Tuple[float, float, float, float]]:
    """Extract AABB (x1, y1, x2, y2) for an IC port from its cx/cy + params."""
    cx = port.get("cx", 0)
    cy = port.get("cy", 0)
    params = port.get("params", {})
    shape = port.get("shape", "")

    if shape in ("mounting-hole",):
        d = params.get("padDia", params.get("diameter", 3))
        hw = d / 2
        return (cx - hw, cy - hw, cx + hw, cy + hw)

    bw = params.get("bodyW", 0)
    bd = params.get("bodyD", params.get("bodyH", 0))

    if shape == "buzzer" or shape == "sensor-dome" or shape == "dome" or shape == "cylinder":
        d = params.get("diameter", bw)
        if d > 0:
            hw = d / 2
            return (cx - hw, cy - hw, cx + hw, cy + hw)

    if shape.startswith("ic-") or shape.startswith("conn-") or shape.startswith("res-") or \
       shape.startswith("cap-") or shape.startswith("led-") or shape.startswith("button-") or \
       shape.startswith("pot-") or shape in ("relay", "motor-servo", "motor-dc",
                                              "vreg-to220", "conn-screw-terminal",
                                              "crystal-hc49", "box"):
        if bw > 0 and bd > 0:
            hw, hd = bw / 2, bd / 2
            return (cx - hw, cy - hd, cx + hw, cy + hd)

    # AV3-7: pin-headers use pins/pitch/rows (no bodyW/bodyD) → branches above return
    # None and the overlap gate is blind to them. Derive housing AABB from the pin grid.
    if shape.startswith("conn-header") and not (bw > 0 and bd > 0):
        pins = params.get("pins")
        if pins:
            pitch = params.get("pitch", 2.54)
            rows = max(1, int(params.get("rows", 1)))
            lng = max(1, int(pins) // rows) * pitch  # along pin-run axis
            sht = rows * pitch                       # across rows
            vert = str(port.get("orientation") or params.get("orientation") or "h").startswith("v")
            hw, hd = (sht / 2, lng / 2) if vert else (lng / 2, sht / 2)
            return (cx - hw, cy - hd, cx + hw, cy + hd)

    if bw > 0:
        hw = bw / 2
        hd = (bd if bd > 0 else bw) / 2
        return (cx - hw, cy - hd, cx + hw, cy + hd)

    return None


def _aabb_overlap_area(a: Tuple, b: Tuple) -> float:
    x_ol = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    y_ol = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return x_ol * y_ol


_STACKING_SHAPES = frozenset({
    "sensor-dome", "dome", "buzzer", "cylinder",
})

_STACKING_KEYWORDS = frozenset({
    "heatsink", "outlet", "horn", "spring", "gearbox",
    "sensing", "transducer", "coil", "antenna", "piezo",
    "matrix", "cone", "pump", "disk", "logo",
})


def _is_stacking_pair(pa: dict, pb: dict) -> bool:
    """True if this port pair is an intentional 3D stack.

    Covers: dome over IC, transducer over PCB, heatsink on chip,
    housing enclosing subcomponents, piezo disk over driver IC, etc.
    """
    for a, b in [(pa, pb), (pb, pa)]:
        if a.get("shape", "") in _STACKING_SHAPES:
            return True
        la = a.get("label", "").lower()
        if any(kw in la for kw in _STACKING_KEYWORDS):
            return True
        if ("body" in la or "holder" in la) and a.get("shape") in ("box", "relay", "motor-servo", "motor-dc"):
            return True
    return False


def _is_overstated_footprint(port: dict) -> bool:
    """AV3-7: True if the port AABB is a housing/keep-out box (pin-header housing or
    mounting-hole pad ring) that overstates copper extent. On dense boards these
    legitimately border neighbours, so an overlap involving one is a review-adjacency."""
    shape = port.get("shape", "")
    return shape.startswith("conn-") or shape == "mounting-hole"


def validate_ic_port_overlap(component_dims: dict) -> List[ValidationIssue]:
    """Check IC/connector ports within each component entry for AABB overlap.

    Only compares ports on the SAME side. Excludes intentional 3D stacking patterns.
    Overlaps involving a header housing / mounting-hole pad ring → warning (AABB
    overstates copper); IC-vs-IC collisions → error (AV3-7: headers were blind before).
    """
    issues: List[ValidationIssue] = []
    for comp_type, spec in component_dims.items():
        ports = spec.get("ports", [])
        if len(ports) < 2:
            continue
        cl, cw = spec.get("l", 0), spec.get("w", 0)
        aabbs = []
        for p in ports:
            bb = _port_aabb(p, cl, cw)
            if bb is not None:
                aabbs.append((p.get("label", "?"), p.get("side", "face"), bb, p))

        for i in range(len(aabbs)):
            for j in range(i + 1, len(aabbs)):
                if aabbs[i][1] != aabbs[j][1]:
                    continue
                if _is_stacking_pair(aabbs[i][3], aabbs[j][3]):
                    continue
                area = _aabb_overlap_area(aabbs[i][2], aabbs[j][2])
                if area > 0.5:
                    overstated = _is_overstated_footprint(aabbs[i][3]) or _is_overstated_footprint(aabbs[j][3])
                    issues.append(ValidationIssue(
                        check="ic_port_overlap",
                        severity="warning" if overstated else "error",
                        component=comp_type,
                        message=f"{aabbs[i][0]} & {aabbs[j][0]} overlap {area:.1f}mm2"
                                + (" (header/hole footprint — review)" if overstated else ""),
                        details={"port_a": aabbs[i][0], "port_b": aabbs[j][0],
                                 "overlap_mm2": round(area, 2),
                                 "overstated_footprint": overstated},
                    ))
    return issues


# -- 2. Module 3D AABB overlap in enclosure ----------------------------------

def validate_module_overlap_3d(
    modules: List[dict],
    tol: float = 0.5,
) -> List[ValidationIssue]:
    """Check placed modules for 3D bounding-box overlap inside enclosure.

    Each module dict needs: id, position [x,y,z], dimensions [l,w,h],
    enclosure_relation.
    """
    issues: List[ValidationIssue] = []
    internal = [m for m in modules
                if m.get("enclosure_relation") in ("internal", "breadboard")]
    for i in range(len(internal)):
        a = internal[i]
        ap = a["position"]
        ad = a["dimensions"]
        ax1, ax2 = ap[0] - ad[0] / 2, ap[0] + ad[0] / 2
        az1, az2 = ap[1], ap[1] + ad[2]
        ay1, ay2 = ap[2] - ad[1] / 2, ap[2] + ad[1] / 2
        for j in range(i + 1, len(internal)):
            b = internal[j]
            bp = b["position"]
            bd = b["dimensions"]
            bx1, bx2 = bp[0] - bd[0] / 2, bp[0] + bd[0] / 2
            bz1, bz2 = bp[1], bp[1] + bd[2]
            by1, by2 = bp[2] - bd[1] / 2, bp[2] + bd[1] / 2
            if (ax1 < bx2 - tol and ax2 > bx1 + tol and
                    ay1 < by2 - tol and ay2 > by1 + tol and
                    az1 < bz2 - tol and az2 > bz1 + tol):
                issues.append(ValidationIssue(
                    check="module_overlap_3d",
                    severity="error",
                    component=f"{a['id']} & {b['id']}",
                    message=f"3D AABB overlap between {a['id']} and {b['id']}",
                ))
    return issues


# -- 3. Wire path shell boundary ---------------------------------------------

def validate_wire_shell_boundary(
    wires: List[dict],
    enclosure_inner: List[float],
) -> List[ValidationIssue]:
    """Verify all wire path3d waypoints are within enclosure inner bounds.

    Coordinate system: Y-up, origin at enclosure centre (XZ), floor at Y=0.
    Bounds: X in [-il/2, il/2], Z in [-iw/2, iw/2], Y in [0, ih].
    """
    issues: List[ValidationIssue] = []
    il, iw, ih = enclosure_inner
    hx, hz = il / 2, iw / 2
    tol = 1.0

    for w in wires:
        path = w.get("path3d", [])
        wire_id = w.get("id", "?")
        crosses = w.get("crosses_wall", False)
        last = len(path) - 1
        for pi, pt in enumerate(path):
            if len(pt) < 3:
                continue
            # Cross-wall wires legitimately start/end outside (they pass through a
            # reserved hole); only their interior must stay inside the shell.
            if crosses and (pi == 0 or pi == last):
                continue
            x, y, z = pt[0], pt[1], pt[2]
            oob = []
            if x < -hx - tol or x > hx + tol:
                oob.append(f"X={x:.1f} out [-{hx:.1f}, {hx:.1f}]")
            if y < -tol or y > ih + tol:
                oob.append(f"Y={y:.1f} out [0, {ih:.1f}]")
            if z < -hz - tol or z > hz + tol:
                oob.append(f"Z={z:.1f} out [-{hz:.1f}, {hz:.1f}]")
            if oob:
                issues.append(ValidationIssue(
                    check="wire_shell_boundary",
                    severity="error",
                    component=wire_id,
                    message=f"Wire {wire_id} point {pi} penetrates shell: {', '.join(oob)}",
                    details={"wire_id": wire_id, "point_index": pi,
                             "coords": [round(x, 1), round(y, 1), round(z, 1)]},
                ))
    return issues


# -- 4. Dimension proportion vs datasheet ------------------------------------

def validate_proportions(
    component_dims: dict,
    datasheet: Optional[dict] = None,
    tol_pct: float = 15.0,
) -> List[ValidationIssue]:
    """Sanity-check component dimensions against datasheet SSOT.

    Also checks internal consistency: no port extends beyond component footprint.
    """
    issues: List[ValidationIssue] = []
    for comp_type, spec in component_dims.items():
        cl, cw = spec.get("l", 0), spec.get("w", 0)
        if cl <= 0 or cw <= 0:
            issues.append(ValidationIssue(
                check="proportion_check",
                severity="error",
                component=comp_type,
                message=f"Zero/negative dimension: l={cl}, w={cw}",
            ))
            continue

        for p in spec.get("ports", []):
            bb = _port_aabb(p, cl, cw)
            if bb is None:
                continue
            label = p.get("label", "?")
            margin = 2.0
            if bb[0] < -margin or bb[1] < -margin:
                issues.append(ValidationIssue(
                    check="port_oob",
                    severity="warning",
                    component=comp_type,
                    message=f"Port {label} extends below origin: ({bb[0]:.1f}, {bb[1]:.1f})",
                ))
            if bb[2] > cl + margin or bb[3] > cw + margin:
                issues.append(ValidationIssue(
                    check="port_oob",
                    severity="warning",
                    component=comp_type,
                    message=f"Port {label} extends beyond footprint: ({bb[2]:.1f}>{cl}, {bb[3]:.1f}>{cw})",
                ))

        if datasheet and comp_type in datasheet:
            ds = datasheet[comp_type]
            ds_l = ds.get("length_mm", 0)
            ds_w = ds.get("width_mm", 0)
            if ds_l > 0 and abs(cl - ds_l) / ds_l * 100 > tol_pct:
                issues.append(ValidationIssue(
                    check="proportion_mismatch",
                    severity="warning",
                    component=comp_type,
                    message=f"Length {cl}mm vs datasheet {ds_l}mm ({abs(cl-ds_l)/ds_l*100:.0f}% diff)",
                ))
            if ds_w > 0 and abs(cw - ds_w) / ds_w * 100 > tol_pct:
                issues.append(ValidationIssue(
                    check="proportion_mismatch",
                    severity="warning",
                    component=comp_type,
                    message=f"Width {cw}mm vs datasheet {ds_w}mm ({abs(cw-ds_w)/ds_w*100:.0f}% diff)",
                ))

    return issues


# -- 4b. Panel face-mount placement ------------------------------------------

def validate_panel_placement(
    modules: List[dict], inner: List[float],
) -> List[ValidationIssue]:
    """Face-mounted panels must stay within the lid and not overlap each other."""
    issues: List[ValidationIssue] = []
    il, iw, _ih = inner
    hx, hz = il / 2, iw / 2
    tol = 1.0
    panels = [m for m in modules if m.get("enclosure_relation") == "panel"]
    for m in panels:
        px, _py, pz = m["position"]
        L, W, _H = m["dimensions"]
        if (px - L / 2 < -hx - tol or px + L / 2 > hx + tol or
                pz - W / 2 < -hz - tol or pz + W / 2 > hz + tol):
            issues.append(ValidationIssue(
                check="panel_face_bounds", severity="error", component=m["id"],
                message=f"panel {m['id']} extends beyond the lid face"))
    for i in range(len(panels)):
        ax, _ay, az = panels[i]["position"]
        aL, aW, _ = panels[i]["dimensions"]
        for j in range(i + 1, len(panels)):
            bx, _by, bz = panels[j]["position"]
            bL, bW, _ = panels[j]["dimensions"]
            ox = min(ax + aL / 2, bx + bL / 2) - max(ax - aL / 2, bx - bL / 2)
            oz = min(az + aW / 2, bz + bW / 2) - max(az - aW / 2, bz - bW / 2)
            if ox > 0.5 and oz > 0.5:
                issues.append(ValidationIssue(
                    check="panel_overlap", severity="error",
                    component=f"{panels[i]['id']} & {panels[j]['id']}",
                    message="panel footprints overlap on the lid"))
    return issues


# -- 4c. Panel vs internal 3D clearance --------------------------------------

def validate_panel_internal_clearance(
    modules: List[dict], inner: List[float],
) -> List[ValidationIssue]:
    """Panel mounted on the lid must not dip into a tall internal module below.

    Panels carry centre-based scene Y (= ih - H/2); internals carry bottom-based
    scene Y (= 0 for floor). 3D AABB cross-check between the two conventions.
    """
    issues: List[ValidationIssue] = []
    panels = [m for m in modules if m.get("enclosure_relation") == "panel"]
    internals = [m for m in modules
                 if m.get("enclosure_relation") in ("internal", "breadboard")]
    if not panels or not internals:
        return issues
    tol = 0.5
    for p in panels:
        ppx, ppy, ppz = p["position"]
        pL, pW, pH = p["dimensions"]
        p_x = (ppx - pL / 2, ppx + pL / 2)
        p_d = (ppz - pW / 2, ppz + pW / 2)  # depth (scene z)
        p_z = (ppy - pH / 2, ppy + pH / 2)  # height (centre convention)
        for it in internals:
            ix, iy, iz = it["position"]
            iL, iW, iH = it["dimensions"]
            i_x = (ix - iL / 2, ix + iL / 2)
            i_d = (iz - iW / 2, iz + iW / 2)
            i_z = (iy, iy + iH)             # height (bottom convention)
            ox = min(p_x[1], i_x[1]) - max(p_x[0], i_x[0])
            od = min(p_d[1], i_d[1]) - max(p_d[0], i_d[0])
            oz = min(p_z[1], i_z[1]) - max(p_z[0], i_z[0])
            if ox > tol and od > tol and oz > tol:
                issues.append(ValidationIssue(
                    check="panel_internal_collision",
                    severity="error",
                    component=f"{p['id']} & {it['id']}",
                    message=(
                        f"panel {p['id']} dips into internal {it['id']} "
                        f"(z overlap {oz:.1f}mm) — internal too tall under that panel"),
                ))
    return issues


# -- 5. Wall-hole coverage ----------------------------------------------------

def validate_hole_coverage(
    wires: List[dict], holes: List[dict],
) -> List[ValidationIssue]:
    """Every wire that crosses the wall needs a reserved pass-through hole."""
    issues: List[ValidationIssue] = []
    n_cross = sum(1 for w in wires if w.get("crosses_wall"))
    if n_cross > 0 and not holes:
        issues.append(ValidationIssue(
            check="hole_coverage",
            severity="error",
            component="enclosure",
            message=f"{n_cross} wire(s) cross the wall but no holes are reserved",
        ))
    return issues


# -- 6. Master validator ------------------------------------------------------

def validate_assembly(scene_graph: dict) -> ValidationResult:
    """Run all validation passes on a complete scene graph.

    Returns a ValidationResult with structured issues.
    """
    issues: List[ValidationIssue] = []
    checks_run = 0

    enclosure = scene_graph.get("enclosure", {})
    inner = enclosure.get("inner", [80, 60, 40])
    holes = enclosure.get("holes", [])
    modules = scene_graph.get("modules", [])
    wires = scene_graph.get("wires", [])
    # AV3-7: component_dims / datasheet must be plumbed through the scene graph so the
    # IC port-overlap and datasheet-proportion gates actually run in production. When
    # absent we skip those two checks (no silent green for them — they are not counted
    # as run), but we never fabricate dims/datasheet values.
    component_dims = scene_graph.get("component_dims", {})
    datasheet = scene_graph.get("datasheet")

    checks_run += 1
    mod_issues = validate_module_overlap_3d(modules)
    issues.extend(mod_issues)

    checks_run += 1
    wire_issues = validate_wire_shell_boundary(wires, inner)
    issues.extend(wire_issues)

    checks_run += 1
    hole_issues = validate_hole_coverage(wires, holes)
    issues.extend(hole_issues)

    checks_run += 1
    panel_issues = validate_panel_placement(modules, inner)
    issues.extend(panel_issues)

    checks_run += 1
    clearance_issues = validate_panel_internal_clearance(modules, inner)
    issues.extend(clearance_issues)

    # AV3-7: IC port-overlap (IC-vs-IC copper collision) + datasheet-proportion gate.
    # Only run when component_dims is actually present so we never validate fabricated
    # data; when present these are real, counted checks folded into passed=.
    counted_groups = [mod_issues, wire_issues, hole_issues,
                      panel_issues, clearance_issues]
    if component_dims:
        checks_run += 1
        port_issues = validate_ic_port_overlap(component_dims)
        issues.extend(port_issues)
        counted_groups.append(port_issues)

        checks_run += 1
        prop_issues = validate_proportions(component_dims, datasheet)
        issues.extend(prop_issues)
        counted_groups.append(prop_issues)

    errors = [i for i in issues if i.severity == "error"]
    checks_passed = checks_run - sum(1 for grp in counted_groups if grp)

    return ValidationResult(
        passed=len(errors) == 0,
        checks_run=checks_run,
        checks_passed=checks_passed,
        issues=issues,
    )


def clamp_wire_to_enclosure(
    path3d: List[List[float]],
    inner: List[float],
) -> List[List[float]]:
    """Clamp every wire waypoint to stay within enclosure inner bounds."""
    il, iw, ih = inner
    hx, hz = il / 2, iw / 2
    clamped = []
    for pt in path3d:
        if len(pt) < 3:
            clamped.append(pt)
            continue
        x = max(-hx, min(hx, pt[0]))
        y = max(0.0, min(ih, pt[1]))
        z = max(-hz, min(hz, pt[2]))
        clamped.append([round(x, 1), round(y, 1), round(z, 1)])
    return clamped
