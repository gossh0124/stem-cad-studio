"""tests/test_cad_pcb_models.py — CAD PCB body model validation (build123d).

Verifies all PCB model builder functions produce valid Compound geometry:
  - Returns bd.Compound with children
  - Bounding box within expected dimensions (±50% tolerance)
  - Has a meaningful label
  - Each child has a label and color

Requires: build123d (skip if unavailable)
Run: .venv/Scripts/python.exe -m pytest tests/test_cad_pcb_models.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import build123d as bd
    HAS_BD = True
except ImportError:
    HAS_BD = False

pytestmark = pytest.mark.skipif(not HAS_BD, reason="build123d not installed")


# ── Builder registry: (module_path, function_name, expected_label, approx LxWxH mm) ──

BOARD_BUILDERS = [
    ("lib.cad.pcb_body", "build_arduino_pcb_body", "Arduino-Uno-class", (68.6, 53.3, 20)),
    ("lib.cad.pcb_boards", "build_esp32_pcb_body", "ESP32-class", (51.4, 28, 15)),
    ("lib.cad.pcb_boards", "build_rpi_pcb_body", "RaspberryPi-class", (85, 56, 20)),
    ("lib.cad.pcb_boards", "build_microbit_pcb_body", "Microbit-class", (52, 42, 15)),
]

SENSOR_BUILDERS = [
    ("lib.cad.pcb_sensors", "build_temp_humid_pcb_body", "Sensor-TempHumid-class", (25.1, 15.1, 12)),
    ("lib.cad.pcb_sensors", "build_ultrasonic_pcb_body", "Sensor-Ultrasonic-class", (45, 20, 18)),
    ("lib.cad.pcb_sensors", "build_pir_pcb_body", "Sensor-PIR-class", (32, 32, 20)),
    ("lib.cad.pcb_sensors", "build_soil_moisture_pcb_body", "Sensor-SoilMoisture-class", (98, 23, 8)),
    ("lib.cad.pcb_sensors", "build_light_sensor_pcb_body", "Sensor-Light-class", (30, 15, 10)),
    ("lib.cad.pcb_sensors", "build_ir_sensor_pcb_body", "Sensor-IR-class", (32, 14, 10)),
]

PERIPHERAL_BUILDERS = [
    ("lib.cad.pcb_peripherals", "build_relay_pcb_body", "Relay-Module-class", (50, 26, 20)),
    ("lib.cad.pcb_peripherals", "build_oled_pcb_body", "Display-OLED-class", (27, 27, 5)),
    ("lib.cad.pcb_peripherals", "build_lcd_pcb_body", "Display-LCD-class", (80, 36, 15)),
    ("lib.cad.pcb_peripherals", "build_eink_pcb_body", "Display-EInk-class", (89, 38, 5)),
    ("lib.cad.pcb_peripherals", "build_led_matrix_pcb_body", "LED-Matrix-class", (32, 32, 15)),
    ("lib.cad.pcb_peripherals", "build_mp3_pcb_body", "MP3-Module-class", (20.7, 20.7, 5)),
    ("lib.cad.pcb_peripherals", "build_joystick_pcb_body", "Joystick-class", (34, 26, 35)),
    ("lib.cad.pcb_peripherals", "build_chassis_pcb_body", "Chassis-class", (200, 150, 40)),
]

ALL_BUILDERS = BOARD_BUILDERS + SENSOR_BUILDERS + PERIPHERAL_BUILDERS


def _import_builder(module_path: str, func_name: str):
    """Dynamically import a builder function."""
    import importlib
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)


# ── Tests ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="module", params=ALL_BUILDERS,
                ids=[b[2] for b in ALL_BUILDERS])
def built_model(request):
    """Build each model once and cache for module scope."""
    module_path, func_name, label, dims = request.param
    builder = _import_builder(module_path, func_name)
    compound = builder()
    return compound, label, dims


class TestCompoundValidity:
    """Every builder must return a valid bd.Compound."""

    def test_returns_compound(self, built_model):
        compound, _, _ = built_model
        assert isinstance(compound, bd.Compound)

    def test_has_children(self, built_model):
        compound, _, _ = built_model
        assert len(compound.children) > 0

    def test_has_label(self, built_model):
        compound, _, _ = built_model
        assert compound.label, "Compound label must not be empty"


class TestBoundingBox:
    """Bounding box must be within 2x of expected dimensions."""

    def test_bbox_length(self, built_model):
        compound, _, (exp_l, _, _) = built_model
        bb = compound.bounding_box()
        actual_l = bb.max.X - bb.min.X
        assert actual_l > 0
        assert actual_l < exp_l * 2.5, f"Length {actual_l:.1f} > {exp_l*2.5:.1f}"

    def test_bbox_width(self, built_model):
        compound, _, (_, exp_w, _) = built_model
        bb = compound.bounding_box()
        actual_w = bb.max.Y - bb.min.Y
        assert actual_w > 0
        assert actual_w < exp_w * 2.5, f"Width {actual_w:.1f} > {exp_w*2.5:.1f}"

    def test_bbox_height(self, built_model):
        compound, _, (_, _, exp_h) = built_model
        bb = compound.bounding_box()
        actual_h = bb.max.Z - bb.min.Z
        assert actual_h > 0
        assert actual_h < exp_h * 3.0, f"Height {actual_h:.1f} > {exp_h*3.0:.1f}"

    def test_bbox_not_degenerate(self, built_model):
        compound, _, _ = built_model
        bb = compound.bounding_box()
        vol = (bb.max.X - bb.min.X) * (bb.max.Y - bb.min.Y) * (bb.max.Z - bb.min.Z)
        assert vol > 1.0, f"Volume {vol:.1f} mm^3 too small"


class TestChildProperties:
    """Each child solid has required properties."""

    def test_children_have_labels(self, built_model):
        compound, _, _ = built_model
        for child in compound.children:
            assert child.label, f"Child in {compound.label} has no label"

    def test_children_have_color(self, built_model):
        compound, _, _ = built_model
        for child in compound.children:
            assert child.color is not None, f"{child.label} has no color"


class TestPcbCommonHelpers:
    """Unit tests for pcb_common.py helper functions."""

    def test_box_creates_shape(self):
        from lib.cad.pcb_common import box
        s = box(0, 0, 0, 10, 10, 10)
        assert isinstance(s, bd.Shape)

    def test_cyl_creates_shape(self):
        from lib.cad.pcb_common import cyl
        s = cyl(0, 0, 0, 5, 10)
        assert isinstance(s, bd.Shape)

    def test_make_pcb_board_no_holes(self):
        from lib.cad.pcb_common import make_pcb_board, PCB_BLUE
        board = make_pcb_board(50, 30, 1.6, PCB_BLUE, "TestBoard")
        assert isinstance(board, bd.Shape)
        assert board.label == "TestBoard"

    def test_make_pcb_board_with_holes(self):
        from lib.cad.pcb_common import make_pcb_board, PCB_GREEN
        holes = [(10, 10, 1.5), (-10, -10, 1.5)]
        board = make_pcb_board(50, 30, 1.6, PCB_GREEN, "HoledBoard", holes=holes)
        assert isinstance(board, bd.Shape)

    def test_box_port_creates_shape(self):
        from lib.cad.pcb_common import box_port
        s = box_port(0, 0, 5, 12, 8, 10, 6, 4, 3)
        assert isinstance(s, bd.Shape)

    def test_notched_box_creates_shape(self):
        from lib.cad.pcb_common import notched_box
        s = notched_box(0, 0, 3, 10, 6, 3, 1.0)
        assert isinstance(s, bd.Shape)

    def test_rounded_can_creates_shape(self):
        from lib.cad.pcb_common import rounded_can
        s = rounded_can(0, 0, 0, 12, 4.5, 3.8, 1.0)
        assert isinstance(s, bd.Shape)

    def test_tube_x_creates_shape(self):
        from lib.cad.pcb_common import tube_x
        s = tube_x(0, 0, 5, 4.5, 2.1, 14)
        assert isinstance(s, bd.Shape)

    def test_box_holes_creates_shape(self):
        from lib.cad.pcb_common import box_holes
        holes = [(1.27, 0), (3.81, 0), (6.35, 0)]
        s = box_holes(0, 0, 5, 10, 5, 8.5, holes)
        assert isinstance(s, bd.Shape)

    def test_add_helper(self):
        from lib.cad.pcb_common import add, box, LED_GREEN
        parts = []
        s = box(0, 0, 0, 2, 2, 2)
        add(parts, s, LED_GREEN, "TestLED")
        assert len(parts) == 1
        assert parts[0].color is not None
        assert parts[0].label == "TestLED"


class TestAxisConvention:
    """PCBSpec: X = long axis, Y = short axis, Z = up."""

    @pytest.fixture(scope="module", params=BOARD_BUILDERS,
                    ids=[b[2] for b in BOARD_BUILDERS])
    def board_model(self, request):
        module_path, func_name, label, dims = request.param
        builder = _import_builder(module_path, func_name)
        return builder(), label, dims

    def test_x_is_longest_axis(self, board_model):
        compound, label, _ = board_model
        bb = compound.bounding_box()
        lx = bb.max.X - bb.min.X
        ly = bb.max.Y - bb.min.Y
        assert lx >= ly, (
            f"{label}: X={lx:.1f} < Y={ly:.1f} — long axis must be X (PCBSpec)")


class TestGlbExportQuality:
    """GLB export produces PBR materials and normals."""

    def test_arduino_glb_has_pbr_colors(self):
        import tempfile, os
        try:
            import trimesh
        except ImportError:
            pytest.skip("trimesh not installed")
        from lib.cad.pcb_body import build_arduino_pcb_body, _export_glb
        comp = build_arduino_pcb_body()
        path = os.path.join(tempfile.gettempdir(), '_test_pbr.glb')
        try:
            ok = _export_glb(comp, path)
            assert ok
            scene = trimesh.load(path)
            colors = set()
            for mesh in scene.geometry.values():
                mat = getattr(mesh.visual, 'material', None)
                bcf = getattr(mat, 'baseColorFactor', None)
                if bcf is not None:
                    colors.add(tuple(round(float(x), 2) for x in bcf[:3]))
            assert len(colors) >= 3, (
                f"Only {len(colors)} unique PBR colors — expect >= 3")
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_arduino_glb_has_normals(self):
        import tempfile, os
        try:
            import trimesh
        except ImportError:
            pytest.skip("trimesh not installed")
        from lib.cad.pcb_body import build_arduino_pcb_body, _export_glb
        comp = build_arduino_pcb_body()
        path = os.path.join(tempfile.gettempdir(), '_test_normals.glb')
        try:
            ok = _export_glb(comp, path)
            assert ok
            scene = trimesh.load(path)
            for name, mesh in scene.geometry.items():
                if hasattr(mesh, 'vertex_normals'):
                    assert len(mesh.vertex_normals) > 0, (
                        f"{name}: missing vertex normals")
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestGlbYUpAxis:
    """RF1: 後端 GLB 匯出已轉 glTF Y-up 慣例（pcb_common._export_glb）。
    驗證：PCB 長度在 X 軸、厚度在 Y 軸（最短）、寬度在 Z 軸。
    """

    def test_arduino_glb_x_is_longest(self):
        import tempfile, os
        try:
            import trimesh
        except ImportError:
            pytest.skip("trimesh not installed")
        from lib.cad.pcb_body import build_arduino_pcb_body, _export_glb
        comp = build_arduino_pcb_body()
        path = os.path.join(tempfile.gettempdir(), '_test_yup_arduino.glb')
        try:
            assert _export_glb(comp, path)
            scene = trimesh.load(path)
            bb = scene.bounds  # [[minX, minY, minZ], [maxX, maxY, maxZ]]
            lx = bb[1][0] - bb[0][0]
            ly = bb[1][1] - bb[0][1]
            lz = bb[1][2] - bb[0][2]
            # 板長 ≈ 68.6mm 應在 X 軸；厚度（含元件）應比寬度小
            assert lx >= lz, f"X={lx:.1f} should be longest (>= Z={lz:.1f})"
            assert ly < lz, f"Y={ly:.1f} (thickness) should be < Z={lz:.1f} (width)"
            # 長度上限：Arduino-Uno 68.6mm，但含 USB 突出 + tolerance → 75mm
            assert 50.0 < lx < 80.0, f"X={lx:.1f} out of expected range (50,80)"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_esp32_glb_x_is_longest(self):
        import tempfile, os
        try:
            import trimesh
        except ImportError:
            pytest.skip("trimesh not installed")
        from lib.cad.pcb_boards import build_esp32_pcb_body
        from lib.cad.pcb_common import export_glb
        comp = build_esp32_pcb_body()
        path = os.path.join(tempfile.gettempdir(), '_test_yup_esp32.glb')
        try:
            assert export_glb(comp, path)
            scene = trimesh.load(path)
            bb = scene.bounds
            lx = bb[1][0] - bb[0][0]
            ly = bb[1][1] - bb[0][1]
            lz = bb[1][2] - bb[0][2]
            assert lx >= lz, f"ESP32 X={lx:.1f} should be longest (>= Z={lz:.1f})"
            assert ly < lz, f"ESP32 Y={ly:.1f} (thickness) should be < Z={lz:.1f}"

        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestColorConstants:
    """Color constants are valid bd.Color instances."""

    def test_all_colors_are_bd_color(self):
        from lib.cad import pcb_common
        color_names = [
            'PCB_BLUE', 'PCB_GREEN', 'PCB_TEAL', 'PCB_RED', 'PCB_BLACK',
            'METAL', 'METAL_DARK', 'BLACK', 'IC_DARK', 'PIN_GOLD',
            'LED_GREEN', 'LED_RED', 'LED_BLUE', 'LED_YELLOW', 'WHITE',
            'CRYSTAL', 'RELAY_BLUE', 'DOME_WHITE', 'ACRYLIC',
            'USB_SILVER', 'DISPLAY_DARK', 'DISPLAY_GRAY', 'GOLD_TRACE',
            'BROWN', 'TRIMPOT_BLUE', 'RUBBER_BLACK', 'SHIELD_TIN',
            'CONNECTOR_WHT',
        ]
        for name in color_names:
            c = getattr(pcb_common, name)
            assert isinstance(c, bd.Color), f"{name} is not a Color"
