"""tests/test_cad_mounts.py -- lib/cad/mounts.py Spec dataclass + registry 單元測試。

build123d 為重量級依賴，geometry builder 函式需 importskip。
Spec dataclass 與 registry 測試不需 build123d。
"""
from __future__ import annotations

import math
import pytest

from lib.cad.mounts import (
    ServoBracketSpec,
    DCMotorClampSpec,
    NEMA17FlangeSpec,
    WaterPumpSleeveSpec,
    SpeakerGrillSpec,
    ALL_MOUNTS,
    DEFAULT_MOUNT_SPECS,
    build_servo_sg90_bracket,
    build_dc_motor_clamp,
    build_nema17_flange,
    build_water_pump_sleeve,
    build_speaker_grill,
)


# ================================================================
# ServoBracketSpec datasheet values
# ================================================================

class TestServoBracketSpec:
    def test_default_servo_dimensions(self):
        s = ServoBracketSpec()
        assert s.servo_l == 23.0
        assert s.servo_w == 12.2
        assert s.servo_h == 22.5

    def test_frozen(self):
        s = ServoBracketSpec()
        with pytest.raises(AttributeError):
            s.servo_l = 99.0  # type: ignore[misc]

    def test_thermal_values_positive(self):
        s = ServoBracketSpec()
        assert s.thermal_typical_mw > 0
        assert s.thermal_idle_mw >= 0
        assert s.thermal_peak_mw > s.thermal_typical_mw

    def test_shaft_diameter(self):
        s = ServoBracketSpec()
        assert s.shaft_diameter == 5.5

    def test_screw_hole_smaller_than_ear(self):
        s = ServoBracketSpec()
        assert s.screw_hole_d < s.ear_thickness

    def test_bracket_floor_positive(self):
        s = ServoBracketSpec()
        assert s.bracket_floor_t > 0

    def test_custom_override(self):
        s = ServoBracketSpec(servo_l=25.0, ear_extra_l=8.0)
        assert s.servo_l == 25.0
        assert s.ear_extra_l == 8.0


# ================================================================
# DCMotorClampSpec
# ================================================================

class TestDCMotorClampSpec:
    def test_default_motor_diameter(self):
        s = DCMotorClampSpec()
        assert s.motor_d == pytest.approx(24.4)

    def test_clamp_shorter_than_motor(self):
        s = DCMotorClampSpec()
        assert s.clamp_l < s.motor_l

    def test_bolt_hole_m3(self):
        s = DCMotorClampSpec()
        assert s.bolt_hole_d == pytest.approx(3.2)

    def test_thermal_stall_higher_than_running(self):
        s = DCMotorClampSpec()
        assert s.thermal_peak_mw > s.thermal_typical_mw


# ================================================================
# NEMA17FlangeSpec
# ================================================================

class TestNEMA17FlangeSpec:
    def test_motor_size_42mm(self):
        s = NEMA17FlangeSpec()
        assert s.motor_size == pytest.approx(42.3)

    def test_screw_pitch_31mm(self):
        s = NEMA17FlangeSpec()
        assert s.motor_screw_pitch == pytest.approx(31.0)

    def test_flange_larger_than_motor(self):
        s = NEMA17FlangeSpec()
        assert s.flange_size > s.motor_size

    def test_mount_hole_larger_than_motor_screw(self):
        s = NEMA17FlangeSpec()
        assert s.mount_hole_d > s.motor_screw_hole_d

    def test_center_hole_fits_boss(self):
        s = NEMA17FlangeSpec()
        assert s.center_hole_d < s.motor_size


# ================================================================
# WaterPumpSleeveSpec
# ================================================================

class TestWaterPumpSleeveSpec:
    def test_default_pump_diameter(self):
        s = WaterPumpSleeveSpec()
        assert s.pump_d == 25.0

    def test_outlet_within_pump_height(self):
        s = WaterPumpSleeveSpec()
        assert s.outlet_z < s.pump_h

    def test_idle_zero(self):
        s = WaterPumpSleeveSpec()
        assert s.thermal_idle_mw == 0.0

    def test_cable_slot_smaller_than_pump(self):
        s = WaterPumpSleeveSpec()
        assert s.cable_slot_w < s.pump_d


# ================================================================
# SpeakerGrillSpec
# ================================================================

class TestSpeakerGrillSpec:
    def test_grill_wider_than_speaker(self):
        s = SpeakerGrillSpec()
        assert s.grill_outer_d > s.speaker_d

    def test_sound_holes_total(self):
        s = SpeakerGrillSpec()
        total = s.sound_ring_count * s.holes_per_ring + 1  # +1 center
        assert total == 37

    def test_sound_hole_smaller_than_speaker(self):
        s = SpeakerGrillSpec()
        assert s.sound_hole_d < s.speaker_d

    def test_thermal_peak_half_watt(self):
        s = SpeakerGrillSpec()
        assert s.thermal_peak_mw == 500.0


# ================================================================
# ALL_MOUNTS registry
# ================================================================

class TestAllMountsRegistry:
    def test_five_entries(self):
        assert len(ALL_MOUNTS) == 5

    def test_keys_are_class_names(self):
        expected = {
            "Motor-Servo-class",
            "Motor-DC-class",
            "Motor-Stepper-class",
            "Pump-Water-class",
            "Speaker-class",
        }
        assert set(ALL_MOUNTS.keys()) == expected

    def test_each_entry_is_3_tuple(self):
        for key, val in ALL_MOUNTS.items():
            assert len(val) == 3, f"{key} should have (kind, label, builder)"

    def test_builders_are_callable(self):
        for key, (kind, label, builder) in ALL_MOUNTS.items():
            assert callable(builder), f"{key} builder not callable"

    def test_kind_strings_unique(self):
        kinds = [v[0] for v in ALL_MOUNTS.values()]
        assert len(kinds) == len(set(kinds))


# ================================================================
# DEFAULT_MOUNT_SPECS
# ================================================================

class TestDefaultMountSpecs:
    def test_five_specs(self):
        assert len(DEFAULT_MOUNT_SPECS) == 5

    def test_servo_spec_type(self):
        assert isinstance(DEFAULT_MOUNT_SPECS["sg90_bracket"], ServoBracketSpec)

    def test_dc_motor_spec_type(self):
        assert isinstance(DEFAULT_MOUNT_SPECS["tt_motor_clamp"], DCMotorClampSpec)

    def test_nema17_spec_type(self):
        assert isinstance(DEFAULT_MOUNT_SPECS["nema17_flange"], NEMA17FlangeSpec)

    def test_water_pump_spec_type(self):
        assert isinstance(DEFAULT_MOUNT_SPECS["water_pump_sleeve"], WaterPumpSleeveSpec)

    def test_speaker_spec_type(self):
        assert isinstance(DEFAULT_MOUNT_SPECS["speaker_grill"], SpeakerGrillSpec)

    def test_keys_match_all_mounts_kinds(self):
        registry_kinds = {v[0] for v in ALL_MOUNTS.values()}
        assert set(DEFAULT_MOUNT_SPECS.keys()) == registry_kinds


# ================================================================
# Geometry builders (require build123d -- skip if unavailable)
# ================================================================

bd = pytest.importorskip("build123d", reason="build123d not installed")


class TestBuildServoSG90Bracket:
    def test_returns_part_and_info(self):
        part, info = build_servo_sg90_bracket()
        assert part is not None
        assert isinstance(info, dict)

    def test_info_name(self):
        _, info = build_servo_sg90_bracket()
        assert info["name"] == "Servo-SG90"

    def test_info_dimensions(self):
        s = ServoBracketSpec()
        _, info = build_servo_sg90_bracket()
        assert info["outer_l"] == pytest.approx(s.servo_l + 2 * s.ear_extra_l)
        assert info["outer_w"] == pytest.approx(s.servo_w + 2 * s.ear_thickness)

    def test_info_screw_holes(self):
        _, info = build_servo_sg90_bracket()
        assert info["screw_holes"] == 4

    def test_custom_spec(self):
        spec = ServoBracketSpec(servo_l=25.0)
        _, info = build_servo_sg90_bracket(spec)
        assert info["outer_l"] == pytest.approx(25.0 + 2 * spec.ear_extra_l)


class TestBuildDCMotorClamp:
    def test_returns_part_and_info(self):
        part, info = build_dc_motor_clamp()
        assert part is not None

    def test_info_bolt_holes(self):
        _, info = build_dc_motor_clamp()
        assert info["bolt_holes"] == 2

    def test_info_motor_d(self):
        _, info = build_dc_motor_clamp()
        assert info["motor_d"] == pytest.approx(24.4)


class TestBuildNEMA17Flange:
    def test_returns_part_and_info(self):
        part, info = build_nema17_flange()
        assert part is not None

    def test_info_screws(self):
        _, info = build_nema17_flange()
        assert info["motor_screws"] == 4
        assert info["mount_screws"] == 4

    def test_info_square_plate(self):
        _, info = build_nema17_flange()
        assert info["outer_l"] == info["outer_w"]


class TestBuildWaterPumpSleeve:
    def test_returns_part_and_info(self):
        part, info = build_water_pump_sleeve()
        assert part is not None

    def test_info_outlet(self):
        _, info = build_water_pump_sleeve()
        assert info["outlet_d"] == 8.0

    def test_outer_d_includes_wall(self):
        s = WaterPumpSleeveSpec()
        _, info = build_water_pump_sleeve()
        assert info["outer_d"] == pytest.approx(s.pump_d + 2 * s.sleeve_thickness)


class TestBuildSpeakerGrill:
    def test_returns_part_and_info(self):
        part, info = build_speaker_grill()
        assert part is not None

    def test_info_sound_holes(self):
        _, info = build_speaker_grill()
        assert info["sound_holes"] == 37  # 3 * 12 + 1

    def test_info_mount_holes(self):
        _, info = build_speaker_grill()
        assert info["mount_holes"] == 4
