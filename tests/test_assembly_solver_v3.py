"""Tests for lib/assembly_solver_v3.py — Assembly V3 solver."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
pytest.importorskip("build123d")  # lib.assembly_solver.assembly_solver_v3 -> lib.cad eager-imports build123d
from lib.assembly_solver.assembly_solver_v3 import (
    solve_v3,
    _pack_maxrects,
    _to_yup,
    _extract_module_pairs,
    _classify_signal,
    _simplify_3d,
)
from lib.module_builder import build_modules, build_module


# ── Fixtures ──────────────────────────────────────────────

ENCLOSURE = {
    "inner_length": 90, "inner_width": 70,
    "inner_height": 45, "wall": 2.5,
}

COMPONENTS = [
    {"type": "Arduino-Uno-class", "role": "Brain"},
    {"type": "Relay-Module-class", "role": "Output"},
    {"type": "Sensor-SoilMoisture-class", "role": "Sensor"},
]

WIRING_LEGACY = {
    "Relay": {"label": "Relay", "pins": [
        {"comp": "IN", "mcu": "D5", "color": "#44cc44", "note": ""},
    ]},
    "SoilMoisture": {"label": "Soil", "pins": [
        {"comp": "AO", "mcu": "A0", "color": "#ffaa00", "note": ""},
    ]},
}

WIRING_CONNECTIONS = {
    "connections": [
        {"from": "Arduino-Uno.D5", "to": "Relay-Module.IN", "signal": "digital"},
        {"from": "Arduino-Uno.A0", "to": "Sensor-SoilMoisture.AO", "signal": "analog"},
    ],
}


# ── solve_v3 smoke ────────────────────────────────────────

def test_solve_v3_returns_scene_graph():
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    assert result["version"] == "3.0"
    assert result["coordinate_system"] == "y-up"
    assert "enclosure" in result
    assert "modules" in result
    assert "wires" in result
    assert "thermal_field" in result
    assert "decisions" in result
    # assembly step animation removed — no assembly_sequence key
    assert "assembly_sequence" not in result


def test_solve_v3_module_count():
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    assert len(result["modules"]) == 3


def test_solve_v3_connections_format():
    result = solve_v3(COMPONENTS, WIRING_CONNECTIONS, ENCLOSURE)
    assert len(result["modules"]) == 3
    assert len(result["wires"]) >= 1


def test_solve_v3_empty_components():
    result = solve_v3([], WIRING_LEGACY, ENCLOSURE)
    assert result["version"] == "3.0"
    assert result["modules"] == []
    assert result["wires"] == []


def test_solve_v3_module_fields():
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    mod = result["modules"][0]
    for key in ("id", "comp_type", "role", "position", "dimensions",
                "enclosure_relation", "meshes", "shell_ports",
                "thermal_mw"):
        assert key in mod, f"Missing field: {key}"
    assert len(mod["position"]) == 3
    assert len(mod["dimensions"]) == 3


def test_solve_v3_wire_fields():
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    if result["wires"]:
        w = result["wires"][0]
        for key in ("id", "from", "to", "signal", "color", "path3d", "style"):
            assert key in w, f"Missing wire field: {key}"
        assert len(w["path3d"]) >= 2
        assert all(len(p) == 3 for p in w["path3d"])


# ── MaxRects packing unit ────────────────────────────────

def _footprint(m, rot):
    """Effective (L, W) accounting for the packer's rotation flag."""
    return (m.width, m.length) if rot else (m.length, m.width)


def test_maxrects_no_overlap():
    modules = build_modules(COMPONENTS)
    pack = [m for m in modules if m.enclosure_relation in ("internal", "breadboard")]
    positions = _pack_maxrects(pack, 200, 200)  # roomy box -> no overflow fallback
    assert len(positions) == len(pack)
    # AABB overlap check (rotation-aware)
    for i in range(len(pack)):
        for j in range(i + 1, len(pack)):
            xi, yi, ri = positions[i]
            xj, yj, rj = positions[j]
            Li, Wi = _footprint(pack[i], ri)
            Lj, Wj = _footprint(pack[j], rj)
            ox = min(xi + Li, xj + Lj) - max(xi, xj)
            oy = min(yi + Wi, yj + Wj) - max(yi, yj)
            assert not (ox > 0.1 and oy > 0.1), (
                f"Overlap: modules {i} and {j}")


def test_maxrects_within_bounds():
    modules = build_modules(COMPONENTS)
    pack = [m for m in modules if m.enclosure_relation in ("internal", "breadboard")]
    positions = _pack_maxrects(pack, 200, 200)
    for i, (x, y, rot) in enumerate(positions):
        assert x >= 0, f"Module {i} x={x} < 0"
        assert y >= 0, f"Module {i} y={y} < 0"


# ── Coordinate transform ────────────────────────────────

def test_to_yup_centre_origin():
    # Solver (45, 35, 10) with 90x70 enclosure -> Y-up centre
    result = _to_yup(45, 35, 10, 90, 70)
    assert result == [0.0, 10.0, 0.0], f"Got {result}"


def test_to_yup_corner():
    result = _to_yup(0, 0, 0, 80, 60)
    assert result == [-40.0, 0.0, -30.0]


# ── Signal classification ────────────────────────────────

def test_classify_power():
    assert _classify_signal("5V", "VCC") == "power"
    assert _classify_signal("GND", "GND") == "gnd"


def test_classify_analog():
    assert _classify_signal("A0", "AO") == "analog"


def test_classify_digital():
    assert _classify_signal("D5", "IN") == "digital"


def test_classify_i2c():
    assert _classify_signal("SDA", "SDA") == "i2c"
    assert _classify_signal("SCL", "SCL") == "i2c"


# ── Path simplification ─────────────────────────────────

def test_simplify_collinear():
    path = [(0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)]
    result = _simplify_3d(path)
    assert len(result) == 2  # start + end


def test_simplify_with_turn():
    path = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)]
    result = _simplify_3d(path)
    assert len(result) == 4  # all points kept (each turn)


# ── Thermal field ────────────────────────────────────────

def test_thermal_field():
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    tf = result["thermal_field"]
    assert tf["total_power_mw"] > 0
    assert isinstance(tf["needs_venting"], bool)


# ── AV3-4: ShellPort derivation (ports > 0) ──────────────────────────────────
# 每個 test 對應一個核心元件，確保 build_module 後 shell_ports 數量 > 0。

@pytest.mark.parametrize("comp_type,role,min_ports", [
    ("Arduino-Uno-class",     "Brain",  5),   # USB-B + DC-Jack + 5 header groups
    ("ESP32-class",           "Brain",  1),   # micro-USB + header(s)
    ("Display-OLED-class",    "Output", 1),   # I2C header
    ("Display-LCD-class",     "Output", 1),   # I2C header
    ("Motor-Servo-class",     "Output", 3),   # GND/VCC/SIGNAL + Shaft
    ("Motor-DC-class",        "Output", 2),   # M+/M- + Shaft
    ("Relay-Module-class",    "Output", 2),   # Control-Header (face) + Screw-Terminals (right via PCBSpec)
    ("Sensor-Ultrasonic-class","Sensor",1),   # 4Pin-Header (face) via PCBSpec
    ("Sensor-PIR-class",      "Sensor", 1),   # 3Pin-Header (face) via PCBSpec
    ("Sensor-TempHumid-class","Sensor", 1),   # 4Pin-Header (face) via PCBSpec
])
def test_shell_ports_not_empty(comp_type, role, min_ports):
    """AV3-4: _derive_shell_ports must return ≥ min_ports for each core component."""
    mod = build_module(comp_type, role)
    assert len(mod.shell_ports) >= min_ports, (
        f"{comp_type}: expected ≥{min_ports} shell_ports, got {len(mod.shell_ports)}"
    )


def test_arduino_shell_ports_contain_usb():
    """Arduino module must have a USB-type shell port for programming connector."""
    mod = build_module("Arduino-Uno-class", "Brain")
    usb_ports = [sp for sp in mod.shell_ports if sp.port_type == "USB" or "USB" in sp.name]
    assert usb_ports, (
        f"Arduino shell_ports has no USB port; "
        f"found: {[(sp.name, sp.port_type) for sp in mod.shell_ports]}"
    )


def test_relay_module_shell_ports_all_sides():
    """Relay module should expose both face (control pins) and a non-face side
    (screw terminals protrude right from PCBSpec override)."""
    mod = build_module("Relay-Module-class", "Output")
    sides = {sp.side for sp in mod.shell_ports}
    assert "face" in sides, (
        f"Relay module missing 'face' ports (control pins); sides found: {sides}"
    )
    non_face = sides - {"face"}
    assert non_face, (
        f"Relay module has only 'face' ports; expected screw terminal side port too. "
        f"shell_ports: {[(sp.name, sp.side) for sp in mod.shell_ports]}"
    )


def test_solve_v3_modules_have_shell_ports():
    """Integration: all modules in a scene graph should have ≥ 1 shell_port."""
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    for mod in result["modules"]:
        assert len(mod["shell_ports"]) >= 1, (
            f"Module {mod['id']} ({mod['comp_type']}) has 0 shell_ports in scene graph"
        )


def test_solve_v3_shell_port_world_coords():
    """Shell ports in scene graph must have valid 3-element world coordinate."""
    result = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    for mod in result["modules"]:
        for sp in mod["shell_ports"]:
            assert "world" in sp, f"Shell port {sp.get('name')} missing 'world' key"
            assert len(sp["world"]) == 3, (
                f"Shell port {sp.get('name')} world={sp['world']} is not 3D"
            )
            assert all(isinstance(v, (int, float)) for v in sp["world"]), (
                f"Shell port {sp.get('name')} world has non-numeric: {sp['world']}"
            )


# ── Enclosure auto-sizing + buckets + wall holes (V3 redesign) ───────────────

EXTERNAL_COMPONENTS = [
    {"type": "Arduino-Uno-class", "role": "Brain"},
    {"type": "Sensor-SoilMoisture-class", "role": "Sensor"},
    {"type": "Battery-LiPo-class", "role": "Power"},   # enclosure_relation=external
]
EXTERNAL_WIRING = {"connections": [
    {"from": "Battery-LiPo.V+", "to": "Arduino-Uno.VIN", "signal": "power"},
    {"from": "Arduino-Uno.A0", "to": "Sensor-SoilMoisture.AO", "signal": "analog"},
]}


def _internal_oob_count(sg, tol=0.6):
    il, iw, _ih = sg["enclosure"]["inner"]
    hx, hz = il / 2, iw / 2
    n = 0
    for m in sg["modules"]:
        if m["enclosure_relation"] not in ("internal", "breadboard"):
            continue
        px, _py, pz = m["position"]
        L, W, _H = m["dimensions"]
        if (px - L / 2 < -hx - tol or px + L / 2 > hx + tol or
                pz - W / 2 < -hz - tol or pz + W / 2 > hz + tol):
            n += 1
    return n


def test_autosize_grows_when_input_too_small():
    tiny = {"inner_length": 20, "inner_width": 15, "inner_height": 8, "wall": 2.5}
    sg = solve_v3(COMPONENTS, WIRING_LEGACY, tiny)
    il, iw, _ = sg["enclosure"]["inner"]
    assert il > 20 and iw > 15, "enclosure did not grow to fit components"
    assert _internal_oob_count(sg) == 0, "internal modules OOB after autosize"
    assert sg["validation"]["passed"], sg["validation"]["issues"]


def test_autosize_footprint_driven_floor():
    a = solve_v3(COMPONENTS, WIRING_LEGACY,
                 {"inner_length": 20, "inner_width": 15, "inner_height": 8, "wall": 2.5})
    b = solve_v3(COMPONENTS, WIRING_LEGACY,
                 {"inner_length": 30, "inner_width": 20, "inner_height": 10, "wall": 2.5})
    # Both inputs are below the packed footprint -> same shrink-wrapped inner.
    assert a["enclosure"]["inner"][:2] == b["enclosure"]["inner"][:2]


def test_no_internal_module_overlap():
    sg = solve_v3(COMPONENTS, WIRING_LEGACY, ENCLOSURE)
    overlaps = [i for i in sg["validation"]["issues"]
                if i["check"] == "module_overlap_3d"]
    assert not overlaps, overlaps


def test_external_module_creates_wall_hole():
    sg = solve_v3(EXTERNAL_COMPONENTS, EXTERNAL_WIRING, ENCLOSURE)
    holes = sg["enclosure"]["holes"]
    assert len(holes) >= 1, "no wall hole reserved for external module"
    for h in holes:
        assert h["face"] in ("x+", "x-", "y+", "y-")
        assert len(h["center"]) == 3 and h["diameter"] > 0


def test_external_wire_marked_and_exits_shell():
    sg = solve_v3(EXTERNAL_COMPONENTS, EXTERNAL_WIRING, ENCLOSURE)
    cross = [w for w in sg["wires"] if w.get("crosses_wall")]
    assert cross, "external wire not marked crosses_wall"
    il, iw, _ = sg["enclosure"]["inner"]
    hx = il / 2
    # at least one endpoint of a crossing wire is outside the inner X bound
    ends_outside = any(abs(w["path3d"][0][0]) > hx or abs(w["path3d"][-1][0]) > hx
                       for w in cross)
    assert ends_outside, "crossing wire never exits the shell"


def test_external_assembly_validation_passes():
    sg = solve_v3(EXTERNAL_COMPONENTS, EXTERNAL_WIRING, ENCLOSURE)
    assert sg["validation"]["passed"], sg["validation"]["issues"]


# ── Panel face-mounting + cutouts (mounting method) ──────────────────────────

PANEL_COMPONENTS = [
    {"type": "Arduino-Uno-class", "role": "Brain"},
    {"type": "Potentiometer-class", "role": "Control"},   # threaded round hole
    {"type": "Switch-class", "role": "Control"},          # threaded round hole
    {"type": "Lighting-LED-RGB-class", "role": "Output"}, # press-fit round hole
    {"type": "Button-class", "role": "Control"},          # rect cutout
]
PANEL_WIRING = {"connections": [
    {"from": "Arduino-Uno.A0", "to": "Potentiometer.Wiper", "signal": "analog"},
    {"from": "Arduino-Uno.D2", "to": "Switch.Term-COM", "signal": "digital"},
    {"from": "Arduino-Uno.D3", "to": "Lighting-LED-RGB.R", "signal": "pwm"},
    {"from": "Arduino-Uno.D4", "to": "Button.Pin-A1", "signal": "digital"},
]}


def test_panel_modules_mounted_on_lid():
    sg = solve_v3(PANEL_COMPONENTS, PANEL_WIRING, ENCLOSURE)
    ih = sg["enclosure"]["inner"][2]
    panels = [m for m in sg["modules"] if m["enclosure_relation"] == "panel"]
    assert panels, "no panel modules found"
    for m in panels:
        cz = m["position"][1]   # scene Y (height)
        assert cz > ih * 0.5, f"panel {m['id']} not on the lid (y={cz}, ih={ih})"


def test_panel_cutouts_follow_mount_method():
    sg = solve_v3(PANEL_COMPONENTS, PANEL_WIRING, ENCLOSURE)
    by_type = {c["comp_type"]: c for c in sg["enclosure"]["face_cutouts"]}
    assert by_type["Potentiometer-class"]["shape"] == "round"
    assert by_type["Potentiometer-class"]["mount"] == "threaded"
    assert by_type["Switch-class"]["shape"] == "round"
    assert by_type["Lighting-LED-RGB-class"]["mount"] == "press_fit"
    assert by_type["Button-class"]["shape"] == "rect"


def test_panel_assembly_validation_passes():
    sg = solve_v3(PANEL_COMPONENTS, PANEL_WIRING, ENCLOSURE)
    assert sg["validation"]["passed"], sg["validation"]["issues"]


def test_panel_not_treated_as_wall_crossing():
    """Panel wires stay internal — no hole reserved for a panel part."""
    sg = solve_v3(PANEL_COMPONENTS, PANEL_WIRING, ENCLOSURE)
    assert sg["enclosure"]["holes"] == [], "panel wrongly reserved a wall hole"
    assert not any(w.get("crosses_wall") for w in sg["wires"])


def test_embedded_module_uses_host_entry_port():
    """Embedded module (Mist-Atomizer) should sit at host entry_port (u,v) on host,
    not at the generic outside-cursor fallback. host_structure surfaces in the
    scene graph so the renderer can show the host structure."""
    sg = solve_v3(
        [{"type": "Arduino-Uno-class", "role": "Brain"},
         {"type": "Mist-Atomizer-class", "role": "Actuator"}],
        {"connections": [{"from": "Arduino-Uno.D2", "to": "Mist-Atomizer.IN",
                          "signal": "digital"}]},
        ENCLOSURE)
    emb = [m for m in sg["modules"] if m["enclosure_relation"] == "embedded"]
    assert emb, "embedded module missing"
    assert "host_structure" in emb[0], "scene_mod must surface host_structure"
    hs = emb[0]["host_structure"]
    assert hs["kind"] == "water_tank"
    assert hs["entry_port"]["face"] == "top"


def test_hole_coverage_gate_not_evergreen():
    """A crossing wire with no reserved hole must FAIL validation (real gate)."""
    from lib.assembly_solver.ic_validation import validate_assembly
    scene = {
        "enclosure": {"inner": [80, 60, 40], "holes": []},
        "modules": [],
        "wires": [{"id": "w0", "crosses_wall": True,
                   "path3d": [[0, 0, 0], [1, 1, 1]]}],
    }
    res = validate_assembly(scene)
    assert not res.passed, "hole_coverage gate should fail when holes are missing"
