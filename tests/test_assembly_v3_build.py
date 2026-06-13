"""Phase 2b B-2 gate: build_assembly_from_scene builds a valid two-piece enclosure
directly from a V3 SceneGraph, consuming every V3-native opening source (side IO from
shell_ports, wall holes, rect+round panel cutouts, wire grooves, louver vents) with the
y-up→z-up coordinate swap. Tests the builder in isolation from the solver via a synthetic
scene, so it pins the V3 contract the STL path now depends on.
"""
import pytest

from lib.cad.shell.assembly_v3_build import build_assembly_from_scene


def _scene():
    return {
        "version": "3.0", "coordinate_system": "y-up",
        "enclosure": {
            "inner": [80.0, 60.0, 40.0], "wall": 2.0,
            "holes": [
                {"face": "x-", "center": [-40.0, 10.0, 0.0], "diameter": 4.0, "comp_type": "Ext"},
                {"face": "y+", "center": [5.0, 12.0, 30.0], "diameter": 4.0, "comp_type": "Ext2"},
            ],
            "face_cutouts": [
                {"face": "top", "center": [0.0, 40.0, 0.0], "shape": "rect",
                 "width": 25.0, "height": 15.0, "mount": "cutout", "comp_type": "Display-OLED-class"},
                {"face": "top", "center": [10.0, 40.0, 10.0], "shape": "round",
                 "diameter": 7.0, "mount": "threaded", "comp_type": "Potentiometer-class"},
            ],
            "meshes": [],
        },
        "modules": [
            {"id": "m0", "comp_type": "Arduino-Uno-class", "role": "Brain",
             "position": [0, 9, 0], "dimensions": [68, 53, 14],
             "shell_ports": [
                 {"name": "USB", "side": "left", "world": [-39.0, 6.0, 0.0],
                  "port_type": "power", "width": 12.0, "height": 11.0, "pins": 1},
             ]},
            {"id": "m1", "comp_type": "Sensor-DHT22-class", "role": "Sensor",
             "position": [10, 5, 0], "dimensions": [20, 15, 8], "shell_ports": []},
        ],
        "wires": [
            {"path3d": [[0.0, 5.0, 0.0], [20.0, 5.0, 0.0], [20.0, 5.0, 12.0]]},
        ],
        "thermal_field": {"vent_placements": [{"face": "side_lower", "area_mm2": 120.0}]},
        "decisions": [],
    }


def test_builds_valid_two_piece_from_scene():
    base, lid, spec = build_assembly_from_scene(_scene(), project_name="t")
    # Non-empty solids
    assert base.volume > 1000, f"base volume too small: {base.volume}"
    assert lid.volume > 100, f"lid volume too small: {lid.volume}"
    # Outer dims derive from enclosure.inner (+wall+tol), NOT a bbox guess
    assert spec.inner_l == 80.0 and spec.inner_w == 60.0 and spec.inner_h == 40.0
    assert spec.outer_l == pytest.approx(80 + 2 * (2.0 + 0.3))
    assert spec.base_h == pytest.approx(2.0 + 40.0)


def test_all_v3_opening_sources_fire():
    _, _, spec = build_assembly_from_scene(_scene(), project_name="t")
    # 2 panel cutouts (1 rect + 1 round)
    assert spec.n_top_windows == 2, f"expected 2 panels, got {spec.n_top_windows}"
    # 1 wire groove route
    assert spec.n_wire_grooves == 1
    # side IO (USB port at -X wall) + 2 wall holes counted together
    assert spec.n_io_cutouts >= 3, f"expected >=3 io+holes, got {spec.n_io_cutouts}"
    # base louver vents (side_lower)
    assert spec.n_vents >= 2


def test_empty_scene_raises_no_fallback():
    with pytest.raises(ValueError):
        build_assembly_from_scene({"enclosure": {"inner": [80, 60, 40], "wall": 2}, "modules": []})
    with pytest.raises(ValueError):
        build_assembly_from_scene({"enclosure": {}, "modules": [{"id": "x"}]})
