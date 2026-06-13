"""Assembly V3 — negative / reverse / property tests.

Companion to test_assembly_solver_v3.py (which holds the positive happy-path
tests). Every validator we added should also prove its gate is *not* evergreen:
construct a broken case → assert it FAILS. Plus a few invariant/round-trip
properties (idempotency, rotation × 4 = identity, determinism).
"""
import copy
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
pytest.importorskip("build123d")  # lib.assembly_solver.assembly_solver_v3 -> lib.cad eager-imports build123d

from lib.assembly_solver.assembly_solver_v3 import solve_v3, _pack_maxrects
from lib.assembly_solver.ic_validation import (
    validate_assembly, clamp_wire_to_enclosure,
    validate_panel_internal_clearance, validate_panel_placement,
    validate_module_overlap_3d, validate_wire_shell_boundary,
)
from lib.assembly_solver.enclosure_fit import (
    _rotate_module, pack_compact,
)
from lib.module_builder import build_module


# ── shared fixtures ──────────────────────────────────────────────────────────

ENCLOSURE = {"inner_length": 90, "inner_width": 70, "inner_height": 45, "wall": 2.5}

COMPONENTS = [
    {"type": "Arduino-Uno-class", "role": "Brain"},
    {"type": "Relay-Module-class", "role": "Output"},
    {"type": "Sensor-SoilMoisture-class", "role": "Sensor"},
]

WIRING = {"connections": [
    {"from": "Arduino-Uno.D5", "to": "Relay-Module.IN", "signal": "digital"},
    {"from": "Arduino-Uno.A0", "to": "Sensor-SoilMoisture.AO", "signal": "analog"},
]}


# ════════════════════════════════════════════════════════════════════════════
# 1. NEGATIVE — every validator must FAIL on a known-broken scene
# ════════════════════════════════════════════════════════════════════════════

def test_panel_internal_collision_gate_not_evergreen():
    """Panel dipping into a tall internal must FAIL panel_internal_collision."""
    # internal at (0,0,0) up to (10,10,30); panel centred at lid (5,18,5)
    # → panel z [3,33] overlaps internal z [0,30] AND xy overlaps → collision.
    scene = {
        "enclosure": {"inner": [40, 30, 20], "holes": []},
        "modules": [
            {"id": "tall-int", "enclosure_relation": "internal",
             "position": [0, 0, 0], "dimensions": [10, 10, 30]},
            {"id": "deep-panel", "enclosure_relation": "panel",
             "position": [0, 18, 0], "dimensions": [10, 10, 30]},
        ],
        "wires": [],
    }
    issues = validate_panel_internal_clearance(scene["modules"], [40, 30, 20])
    assert any(i.check == "panel_internal_collision" for i in issues)
    assert not validate_assembly(scene).passed


def test_panel_face_bounds_gate_not_evergreen():
    """Panel whose footprint pokes off the lid must FAIL panel_face_bounds."""
    scene_inner = [40, 30, 20]
    panel = {"id": "off-lid", "enclosure_relation": "panel",
             "position": [25, 10, 0], "dimensions": [40, 10, 4]}
    issues = validate_panel_placement([panel], scene_inner)
    assert any(i.check == "panel_face_bounds" for i in issues)


def test_panel_overlap_gate_not_evergreen():
    """Two panels at the same lid spot must FAIL panel_overlap."""
    scene_inner = [40, 30, 20]
    a = {"id": "p1", "enclosure_relation": "panel",
         "position": [0, 18, 0], "dimensions": [10, 10, 4]}
    b = {"id": "p2", "enclosure_relation": "panel",
         "position": [0, 18, 0], "dimensions": [10, 10, 4]}
    issues = validate_panel_placement([a, b], scene_inner)
    assert any(i.check == "panel_overlap" for i in issues)


def test_module_overlap_3d_gate_not_evergreen():
    """Two internal modules at the same xy/z must FAIL module_overlap_3d."""
    a = {"id": "m1", "enclosure_relation": "internal",
         "position": [0, 0, 0], "dimensions": [20, 10, 15]}
    b = {"id": "m2", "enclosure_relation": "internal",
         "position": [0, 0, 0], "dimensions": [20, 10, 15]}
    issues = validate_module_overlap_3d([a, b])
    assert any(i.check == "module_overlap_3d" for i in issues)


def test_wire_shell_boundary_gate_not_evergreen():
    """Interior wire waypoint outside the inner shell must FAIL boundary check."""
    wires = [{"id": "w-oob", "path3d": [[0, 5, 0], [99, 5, 0], [0, 5, 0]]}]
    issues = validate_wire_shell_boundary(wires, [40, 30, 20])
    assert any(i.check == "wire_shell_boundary" for i in issues)


def test_wire_shell_boundary_skips_cross_wall_endpoints():
    """Cross-wall wires legitimately exit at endpoints — only interior must be
    inside. The same x=99 OOB endpoint is OK when crosses_wall=True."""
    wires = [{"id": "w-cross", "crosses_wall": True,
              "path3d": [[99, 5, 0], [10, 5, 0], [99, 5, 0]]}]
    issues = validate_wire_shell_boundary(wires, [40, 30, 20])
    assert not issues   # interior point (10,5,0) is inside → no error


# ════════════════════════════════════════════════════════════════════════════
# 2. REVERSE / PROPERTY — invariants over operations
# ════════════════════════════════════════════════════════════════════════════

def test_rotate_module_4x_identity():
    """Rotating a module 90° CCW four times returns it to the original L/W
    and port positions (numerical equality within rounding tol)."""
    m0 = build_module("Arduino-Uno-class", "Brain")
    m4 = m0
    for _ in range(4):
        m4 = _rotate_module(m4)
    assert m4.length == m0.length and m4.width == m0.width
    # ports should match position-wise after 4 rotations
    orig_ports = sorted((sp.name, round(sp.x, 1), round(sp.y, 1)) for sp in m0.shell_ports)
    final_ports = sorted((sp.name, round(sp.x, 1), round(sp.y, 1)) for sp in m4.shell_ports)
    assert orig_ports == final_ports


def test_rotate_module_2x_swaps_back():
    """Two rotations = 180° → L/W back to original but port (x,y) flipped to
    diagonal corner. Specifically a port (px,py) → (L-px, W-py)."""
    m0 = build_module("Relay-Module-class", "Output")
    m2 = _rotate_module(_rotate_module(m0))
    assert m2.length == m0.length and m2.width == m0.width
    by_name_0 = {sp.name: (sp.x, sp.y) for sp in m0.shell_ports}
    by_name_2 = {sp.name: (sp.x, sp.y) for sp in m2.shell_ports}
    for name, (x0, y0) in by_name_0.items():
        x2, y2 = by_name_2[name]
        # within 0.5mm of 180° image
        assert abs(x2 - (m0.length - x0)) < 0.5, (name, x0, x2)
        assert abs(y2 - (m0.width - y0)) < 0.5, (name, y0, y2)


def test_clamp_wire_to_enclosure_idempotent():
    """Clamping an already-inside path twice = once (idempotency)."""
    inner = [40, 30, 20]
    path = [[5, 5, 5], [10, 10, 10], [-50, 50, 50]]  # last is OOB
    once = clamp_wire_to_enclosure(path, inner)
    twice = clamp_wire_to_enclosure(once, inner)
    assert once == twice


def test_solve_v3_deterministic():
    """Same input twice → same scene graph (no hidden randomness)."""
    a = solve_v3(COMPONENTS, WIRING, ENCLOSURE)
    b = solve_v3(COMPONENTS, WIRING, ENCLOSURE)
    # compare a few structural invariants (full dict compare can drift on float repr)
    assert a["enclosure"]["inner"] == b["enclosure"]["inner"]
    assert len(a["modules"]) == len(b["modules"])
    for ma, mb in zip(a["modules"], b["modules"]):
        assert ma["id"] == mb["id"]
        assert ma["position"] == mb["position"]
        assert ma["dimensions"] == mb["dimensions"]
    assert [w["path3d"] for w in a["wires"]] == [w["path3d"] for w in b["wires"]]


def test_pack_compact_no_overlap_when_rotation_forced():
    """Long thin sensor + Arduino in a tight enclosure: rotation MUST happen and
    final positions must still be overlap-free (regression guard for the original
    'rotated packer didn't propagate rotation → overlaps' bug)."""
    from lib.module_builder import build_modules
    mods = build_modules([
        {"type": "Arduino-Uno-class", "role": "Brain"},
        {"type": "Sensor-SoilMoisture-class", "role": "Sensor"},  # 98mm long
        {"type": "Relay-Module-class", "role": "Output"},
    ])
    placed, pos, il, iw, _ih = pack_compact(mods, _pack_maxrects, 30, 20, 10)
    # All footprints must be overlap-free using the RETURNED (possibly rotated) modules.
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            ax, ay = pos[i]; bx, by = pos[j]
            ox = min(ax + placed[i].length, bx + placed[j].length) - max(ax, bx)
            oy = min(ay + placed[i].width, by + placed[j].width) - max(ay, by)
            assert not (ox > 0.1 and oy > 0.1), (
                f"overlap between placed[{i}]({placed[i].comp_type}) and "
                f"placed[{j}]({placed[j].comp_type})")


# ════════════════════════════════════════════════════════════════════════════
# 3. INPUT EDGE / BEHAVIOUR — input variations the solver should handle
# ════════════════════════════════════════════════════════════════════════════

def test_solve_v3_unknown_component_skipped():
    """No-Silent-Fallback: an unknown comp_type must NOT be silently dropped — a
    requested component vanishing from the physical assembly is a correctness bug,
    so solve_v3 must raise (was: silently skipped). Known ones never get a chance
    to mask the missing one."""
    import pytest
    comps = [
        {"type": "Arduino-Uno-class", "role": "Brain"},
        {"type": "Nonexistent-Foo-class", "role": "Sensor"},  # not in registry
    ]
    with pytest.raises(KeyError, match="Nonexistent-Foo-class"):
        solve_v3(comps, {}, ENCLOSURE)


def test_solve_v3_no_wiring_no_wires_no_crash():
    """Empty wiring → zero wires, scene graph still well-formed."""
    sg = solve_v3(COMPONENTS, {}, ENCLOSURE)
    assert sg["wires"] == []
    assert sg["validation"]["passed"], sg["validation"]["issues"]


def test_autosize_ih_grows_with_tall_panel():
    """ih must accommodate panel_max_h on top of internal_max_h + clearance,
    otherwise panels dip into internals (regression for AV3-4 ②)."""
    sg = solve_v3(
        [{"type": "Arduino-Uno-class", "role": "Brain"},     # H ≈ 16
         {"type": "Switch-class", "role": "Control"}],       # panel, H = 15
        {"connections": [{"from": "Arduino-Uno.D2", "to": "Switch.Term-COM",
                          "signal": "digital"}]},
        {"inner_length": 30, "inner_width": 20, "inner_height": 10, "wall": 2.5})
    ih = sg["enclosure"]["inner"][2]
    assert ih >= 16 + 15, f"ih={ih} did not grow to clear internal+panel"
    assert sg["validation"]["passed"], sg["validation"]["issues"]


def test_astar_no_fallback_for_multi_wire_brain():
    """Many wires sharing one brain → none should fall back to straight-line.
    (Regression guard for the wire-cell-blocking accumulator that produced 72%
    fallbacks; expected 0% now that wires are tube-allowed-to-parallel.)"""
    sg = solve_v3(COMPONENTS, WIRING, ENCLOSURE)
    # A* fallback produces a wire with exactly 2 points (start + end) at route_z;
    # a real route has additional waypoints.
    straight = [w for w in sg["wires"] if len(w["path3d"]) <= 2]
    assert not straight, f"{len(straight)} wires fell back to straight-line"
