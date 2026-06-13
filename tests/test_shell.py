"""Unit tests for lib/cad/shell.py — PCB enclosure shell builder.

Tests focus on pure-logic functions (validation, dimension calculation,
tier/config parsing) without requiring build123d runtime.
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional

from lib.cad.shell import (
    validate_snap_fit_stress,
    _validate_wall_thickness,
    EnclosureSpec,
    AssemblySpec,
    TwoPieceSpec,
    compute_two_piece_spec,
    _FALLBACK_COMPONENT_H,
    _MIN_WALL_MM,
    _MATERIAL_YIELD_STRAIN,
    _SNAP_FIT_SAFETY_FACTOR,
    _PIN_PITCH,
    _TOP_DISPLAY_CLASSES,
)


# ════════════════════════════════════════════════════════════════════
# Test fixtures — lightweight PCBSpec mock
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MockMountingHole:
    x: float
    y: float
    diameter: float = 3.2


@dataclass(frozen=True)
class MockSubComponent:
    name: str = "USB-B"
    package: str = "THT"
    anchor_x: float = 0.0
    anchor_y: float = 25.0
    body_l: float = 12.0
    body_w: float = 9.0
    body_h: float = 11.0
    z: float = 0.0
    rotation: str = "R0"
    description: str = ""
    protrudes: str = "left"
    overhang: float = 3.0
    profile: str = "rect"
    thermal_typical_mw: float = 0.0
    thermal_idle_mw: float = 0.0
    thermal_peak_mw: float = 0.0
    thermal_formula: str = ""
    thermal_source: str = ""


@dataclass(frozen=True)
class MockHeaderGroup:
    name: str = "JDIGITAL"
    pin_indices: Tuple[int, ...] = (15, 16, 17, 18)
    profile: str = "slot"
    port_type: str = "digital"
    rows: int = 1
    clearance_mm: float = 1.0


@dataclass(frozen=True)
class MockNamedPin:
    name: str = "D0"
    x: float = 10.0
    y: float = 5.0
    pad_index: int = 0


@dataclass
class MockPCBSpec:
    name: str = "Arduino-Uno"
    length: float = 68.58
    width: float = 53.34
    pcb_thickness: float = 1.6
    pins: Tuple = ()
    pin_groups: Dict = field(default_factory=dict)
    mounting_holes: Tuple = ()
    sub_components: Tuple = ()
    header_groups: Tuple = ()

    def pin_index_map(self) -> dict:
        return {p.pad_index: p for p in self.pins}


def _make_pcb_spec(
    length=68.58,
    width=53.34,
    pcb_thickness=1.6,
    mounting_holes=None,
    sub_components=None,
    header_groups=None,
    pins=None,
):
    """Factory to create a MockPCBSpec with optional overrides."""
    return MockPCBSpec(
        length=length,
        width=width,
        pcb_thickness=pcb_thickness,
        mounting_holes=mounting_holes or (),
        sub_components=sub_components or (),
        header_groups=header_groups or (),
        pins=pins or (),
    )


# ════════════════════════════════════════════════════════════════════
# Group 1: validate_snap_fit_stress
# ════════════════════════════════════════════════════════════════════

class TestValidateSnapFitStress:
    """Tests for PV5 snap-fit stress validation."""

    def test_safe_pla_params_pass(self):
        """Nominal safe PLA parameters should pass."""
        result = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3, material="PLA"
        )
        assert result["ok"] is True
        assert result["material"] == "PLA"
        assert result["E_mpa"] == 3500

    def test_aggressive_pla_params_fail(self):
        """Thick arm + short height + large lip should fail for PLA."""
        result = validate_snap_fit_stress(
            snap_arm_t=2.0, snap_arm_h=5.0, snap_lip_d=1.0, material="PLA"
        )
        assert result["ok"] is False
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

    def test_petg_more_forgiving(self):
        """PETG has higher yield strain, same params that fail PLA may pass."""
        result_pla = validate_snap_fit_stress(
            snap_arm_t=1.5, snap_arm_h=8.0, snap_lip_d=0.5, material="PLA"
        )
        result_petg = validate_snap_fit_stress(
            snap_arm_t=1.5, snap_arm_h=8.0, snap_lip_d=0.5, material="PETG"
        )
        # PETG utilization should be lower than PLA (more forgiving)
        assert result_petg["utilization_pct"] < result_pla["utilization_pct"]

    def test_custom_e_mpa_overrides_default(self):
        """Explicit E_mpa should override material default."""
        result = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3,
            material="PLA", E_mpa=5000
        )
        assert result["E_mpa"] == 5000
        # Stress should be proportionally higher
        result_default = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3, material="PLA"
        )
        assert result["stress_mpa"] > result_default["stress_mpa"]

    def test_unknown_material_uses_defaults(self):
        """Unknown material should use fallback E=2000, yield=0.03."""
        result = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3,
            material="NYLON"
        )
        assert result["material"] == "NYLON"
        assert result["E_mpa"] == 2000

    def test_strain_formula_correctness(self):
        """Verify strain = 3*t*d / (2*h^2) is computed correctly."""
        t, h, d = 1.5, 8.0, 0.5
        expected_strain = 3 * t * d / (2 * h**2)
        result = validate_snap_fit_stress(
            snap_arm_t=t, snap_arm_h=h, snap_lip_d=d, material="PLA"
        )
        assert abs(result["strain_pct"] - expected_strain * 100) < 0.01

    def test_utilization_formula(self):
        """Utilization = strain / yield_strain, expressed as %."""
        t, h, d = 1.0, 10.0, 0.3
        strain = 3 * t * d / (2 * h**2)
        yield_strain = _MATERIAL_YIELD_STRAIN["PLA"]
        expected_util = (strain / yield_strain) * 100

        result = validate_snap_fit_stress(
            snap_arm_t=t, snap_arm_h=h, snap_lip_d=d, material="PLA"
        )
        assert abs(result["utilization_pct"] - expected_util) < 0.5

    def test_suggestions_include_material_swap_for_pla(self):
        """Failed PLA should suggest switching to PETG."""
        result = validate_snap_fit_stress(
            snap_arm_t=2.0, snap_arm_h=5.0, snap_lip_d=1.0, material="PLA"
        )
        assert result["ok"] is False
        suggestions_text = " ".join(result["suggestions"])
        assert "PETG" in suggestions_text

    def test_tpu_very_safe(self):
        """TPU (yield 15%) should easily pass even aggressive params."""
        result = validate_snap_fit_stress(
            snap_arm_t=2.0, snap_arm_h=6.0, snap_lip_d=0.8, material="TPU"
        )
        assert result["ok"] is True

    def test_case_insensitive_material(self):
        """Material name should be case-insensitive."""
        result_lower = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3, material="pla"
        )
        result_upper = validate_snap_fit_stress(
            snap_arm_t=1.0, snap_arm_h=10.0, snap_lip_d=0.3, material="PLA"
        )
        assert result_lower["strain_pct"] == result_upper["strain_pct"]
        assert result_lower["material"] == "PLA"


# ════════════════════════════════════════════════════════════════════
# Group 2: _validate_wall_thickness
# ════════════════════════════════════════════════════════════════════

class TestValidateWallThickness:
    """Tests for PV1 wall thickness validation."""

    def test_valid_wall_passes(self):
        """Wall >= _MIN_WALL_MM should pass and return the value."""
        assert _validate_wall_thickness(2.0) == 2.0
        assert _validate_wall_thickness(1.5) == 1.5
        assert _validate_wall_thickness(3.0) == 3.0

    def test_too_thin_wall_raises(self):
        """Wall < _MIN_WALL_MM should raise ValueError."""
        with pytest.raises(ValueError, match="壁厚"):
            _validate_wall_thickness(1.0)

    def test_zero_wall_raises(self):
        """Zero wall thickness should raise."""
        with pytest.raises(ValueError):
            _validate_wall_thickness(0.0)

    def test_negative_wall_raises(self):
        """Negative wall thickness should raise."""
        with pytest.raises(ValueError):
            _validate_wall_thickness(-1.0)

    def test_boundary_at_min(self):
        """Exactly _MIN_WALL_MM should pass."""
        result = _validate_wall_thickness(_MIN_WALL_MM)
        assert result == _MIN_WALL_MM

    def test_just_below_min_raises(self):
        """Just under _MIN_WALL_MM should raise."""
        with pytest.raises(ValueError):
            _validate_wall_thickness(_MIN_WALL_MM - 0.01)


# ════════════════════════════════════════════════════════════════════
# Group 3: EnclosureSpec / TwoPieceSpec / AssemblySpec dataclasses
# ════════════════════════════════════════════════════════════════════

class TestSpecDataclasses:
    """Tests for frozen dataclass specs (construction, immutability)."""

    def test_enclosure_spec_creation(self):
        """EnclosureSpec should store all fields correctly."""
        spec = EnclosureSpec(
            outer_l=80.0, outer_w=60.0, outer_h=30.0,
            inner_l=70.0, inner_w=50.0, inner_h=25.0,
            wall=2.0, tol=0.3,
            pcb_top_z=-5.0, pcb_bottom_z=-6.6,
            standoff_height=5.0,
            cutout_count=3, standoff_count=4,
        )
        assert spec.outer_l == 80.0
        assert spec.wall == 2.0
        assert spec.cutout_count == 3
        assert spec.standoff_count == 4

    def test_enclosure_spec_is_frozen(self):
        """EnclosureSpec should be immutable (frozen dataclass)."""
        spec = EnclosureSpec(
            outer_l=80.0, outer_w=60.0, outer_h=30.0,
            inner_l=70.0, inner_w=50.0, inner_h=25.0,
            wall=2.0, tol=0.3,
            pcb_top_z=-5.0, pcb_bottom_z=-6.6,
            standoff_height=5.0,
            cutout_count=3, standoff_count=4,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            spec.outer_l = 100.0

    def test_two_piece_spec_creation(self):
        """TwoPieceSpec should store snap-fit geometry params."""
        spec = TwoPieceSpec(
            outer_l=80.0, outer_w=60.0,
            base_h=28.0, lid_h=2.0,
            inner_l=70.0, inner_w=50.0, inner_h=25.0,
            wall=2.0, tol=0.3,
            pcb_top_z=-5.0, pcb_bottom_z=-6.6,
            standoff_height=5.0, standoff_count=4,
            side_cutout_count=1, lid_cutout_count=5,
            snap_count=4,
            snap_arm_w=4.0, snap_arm_t=1.5, snap_arm_h=8.0,
            snap_lip_h=1.0, snap_lip_d=0.5, snap_gap=0.1,
        )
        assert spec.snap_count == 4
        assert spec.snap_arm_t == 1.5
        assert spec.lid_h == 2.0

    def test_assembly_spec_creation(self):
        """AssemblySpec should store assembly-level metadata."""
        spec = AssemblySpec(
            outer_l=100.0, outer_w=80.0,
            base_h=50.0, lid_h=2.0,
            inner_l=90.0, inner_w=70.0, inner_h=45.0,
            wall=2.0, tol=0.3, fillet_r=2.0,
            n_components=4, n_io_cutouts=2,
            n_wire_grooves=3, n_vents=5,
            n_top_windows=1, project_name="plant_monitor",
        )
        assert spec.n_components == 4
        assert spec.project_name == "plant_monitor"
        assert spec.fillet_r == 2.0


# ════════════════════════════════════════════════════════════════════
# Group 4: compute_two_piece_spec (pure dimension calculation)
# ════════════════════════════════════════════════════════════════════

class TestComputeTwoPieceSpec:
    """Tests for compute_two_piece_spec — pure math, no build123d."""

    def test_basic_dimensions(self):
        """Verify inner/outer dimension formulas with default params."""
        pcb = _make_pcb_spec(length=68.58, width=53.34)
        spec = compute_two_piece_spec(pcb)

        # inner = PCB + 2*padding(2.5)
        assert abs(spec.inner_l - (68.58 + 5.0)) < 0.01
        assert abs(spec.inner_w - (53.34 + 5.0)) < 0.01
        # outer = inner + 2*(wall+tol) = inner + 2*(2.0+0.3)
        assert abs(spec.outer_l - (spec.inner_l + 4.6)) < 0.01
        assert abs(spec.outer_w - (spec.inner_w + 4.6)) < 0.01

    def test_base_height_formula(self):
        """base_h = wall + standoff + pcb_thickness + component_h + padding."""
        sub = MockSubComponent(body_h=11.0)
        pcb = _make_pcb_spec(sub_components=(sub,))
        spec = compute_two_piece_spec(pcb, wall=2.0, standoff_height=5.0, padding=2.5)

        expected_inner_h = 5.0 + 1.6 + 11.0 + 2.5  # standoff + pcb_t + comp_h + padding
        expected_base_h = 2.0 + expected_inner_h     # wall + inner_h
        assert abs(spec.base_h - expected_base_h) < 0.01

    def test_fallback_component_height(self):
        """Empty sub_components should use _FALLBACK_COMPONENT_H."""
        pcb = _make_pcb_spec(sub_components=())
        spec = compute_two_piece_spec(pcb, standoff_height=5.0, padding=2.5)

        expected_inner_h = 5.0 + 1.6 + _FALLBACK_COMPONENT_H + 2.5
        assert abs(spec.inner_h - expected_inner_h) < 0.01

    def test_tallest_component_wins(self):
        """Max body_h among sub_components determines inner_h."""
        sub1 = MockSubComponent(name="short", body_h=5.0)
        sub2 = MockSubComponent(name="tall", body_h=20.0)
        pcb = _make_pcb_spec(sub_components=(sub1, sub2))
        spec = compute_two_piece_spec(pcb, standoff_height=5.0, padding=2.5)

        expected_inner_h = 5.0 + 1.6 + 20.0 + 2.5
        assert abs(spec.inner_h - expected_inner_h) < 0.01

    def test_pcb_z_positions(self):
        """PCB bottom/top Z should be consistent with wall + standoff."""
        pcb = _make_pcb_spec()
        spec = compute_two_piece_spec(pcb, wall=2.0, standoff_height=5.0)

        expected_bottom = -spec.base_h / 2 + 2.0 + 5.0
        expected_top = expected_bottom + 1.6
        assert abs(spec.pcb_bottom_z - expected_bottom) < 0.01
        assert abs(spec.pcb_top_z - expected_top) < 0.01

    def test_standoff_count_from_mounting_holes(self):
        """standoff_count should equal number of mounting holes."""
        holes = (MockMountingHole(x=3.0, y=3.0), MockMountingHole(x=65.0, y=50.0))
        pcb = _make_pcb_spec(mounting_holes=holes)
        spec = compute_two_piece_spec(pcb)
        assert spec.standoff_count == 2

    def test_zero_mounting_holes(self):
        """Zero mounting holes gives standoff_count=0."""
        pcb = _make_pcb_spec(mounting_holes=())
        spec = compute_two_piece_spec(pcb)
        assert spec.standoff_count == 0

    def test_lid_cutout_count(self):
        """lid_cutout_count = number of header_groups."""
        groups = (
            MockHeaderGroup(name="G1"),
            MockHeaderGroup(name="G2"),
            MockHeaderGroup(name="G3"),
        )
        pcb = _make_pcb_spec(header_groups=groups)
        spec = compute_two_piece_spec(pcb)
        assert spec.lid_cutout_count == 3

    def test_side_cutout_count_only_left(self):
        """side_cutout_count counts every protruding side with a profile.

        This must match the geometry actually produced by _apply_side_cutouts,
        which cuts openings on left/right/top/bottom (not just 'left'). A
        component with no protrusion/profile is skipped.
        """
        sub_left = MockSubComponent(name="USB", protrudes="left", profile="rect")
        sub_right = MockSubComponent(name="DC", protrudes="right", profile="circle")
        sub_none = MockSubComponent(name="IC", protrudes="", profile="")
        pcb = _make_pcb_spec(sub_components=(sub_left, sub_right, sub_none))
        spec = compute_two_piece_spec(pcb)
        # left + right are counted; the no-protrusion component is skipped.
        assert spec.side_cutout_count == 2

    def test_snap_count_always_4(self):
        """compute_two_piece_spec always returns snap_count=4."""
        pcb = _make_pcb_spec()
        spec = compute_two_piece_spec(pcb)
        assert spec.snap_count == 4

    def test_custom_snap_params_stored(self):
        """Custom snap-fit params should flow through to spec."""
        pcb = _make_pcb_spec()
        spec = compute_two_piece_spec(
            pcb,
            snap_arm_w=5.0, snap_arm_t=1.2, snap_arm_h=12.0,
            snap_lip_h=1.5, snap_lip_d=0.4, snap_gap=0.2,
        )
        assert spec.snap_arm_w == 5.0
        assert spec.snap_arm_t == 1.2
        assert spec.snap_arm_h == 12.0
        assert spec.snap_lip_h == 1.5
        assert spec.snap_lip_d == 0.4
        assert spec.snap_gap == 0.2

    def test_lid_height_matches_param(self):
        """lid_h should match the lid_thickness parameter."""
        pcb = _make_pcb_spec()
        spec = compute_two_piece_spec(pcb, lid_thickness=3.0)
        assert spec.lid_h == 3.0

