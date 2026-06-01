"""Unit tests for lib/cad/shell.py -- validation, constants, and edge cases.

Split from test_shell.py to stay under 500-line limit.
Groups covered:
  5. build_pcb_two_piece stress gate (PV5)
  6. build_assembly_two_piece input validation
  7. Module constants and configuration
  8. Dimension formula edge cases
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

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

# Re-use MockPCBSpec and factory from test_shell
from tests.test_shell import MockPCBSpec, MockSubComponent, _make_pcb_spec


# ================================================================
# Group 5: build_pcb_two_piece stress gate (integration with validation)
# ================================================================

class TestBuildTwoPieceStressGate:
    """Tests for build_pcb_two_piece's PV5 stress pre-check."""

    def test_unsafe_params_raise_value_error(self):
        """build_pcb_two_piece should raise when snap stress exceeds limit."""
        from lib.cad.shell import build_pcb_two_piece
        pcb = _make_pcb_spec()

        with pytest.raises(ValueError, match="PV5"):
            build_pcb_two_piece(
                pcb, snap_arm_t=3.0, snap_arm_h=4.0, snap_lip_d=1.5,
                material="PLA",
            )

    def test_wall_validation_before_stress(self):
        """Wall thickness validation runs before snap stress check."""
        from lib.cad.shell import build_pcb_two_piece
        pcb = _make_pcb_spec()

        with pytest.raises(ValueError, match="壁厚"):
            build_pcb_two_piece(pcb, wall=0.5)


# ================================================================
# Group 6: build_assembly_two_piece input validation
# ================================================================

class TestBuildAssemblyValidation:
    """Tests for build_assembly_two_piece input validation."""

    def test_empty_placements_raises(self):
        """Empty placements list should raise ValueError."""
        from lib.cad.shell import build_assembly_two_piece
        with pytest.raises(ValueError, match="placements 不可為空"):
            build_assembly_two_piece(placements=[])

    def test_wall_too_thin_raises(self):
        """Wall < 1.5mm should raise before build123d is imported."""
        from lib.cad.shell import build_assembly_two_piece
        with pytest.raises(ValueError, match="壁厚"):
            build_assembly_two_piece(
                placements=[{"x": 0, "y": 0, "L": 10, "W": 10, "H": 5,
                             "type": "Test", "role": "Brain", "face_out": ""}],
                wall=0.5,
            )


# ================================================================
# Group 7: Module constants and configuration
# ================================================================

class TestModuleConstants:
    """Tests for module-level constants sanity."""

    def test_min_wall_positive(self):
        """_MIN_WALL_MM should be a positive reasonable value."""
        assert _MIN_WALL_MM > 0
        assert _MIN_WALL_MM <= 3.0  # Shouldn't be unreasonably high

    def test_material_yield_strain_all_positive(self):
        """All material yield strains should be positive and < 1."""
        for mat, ys in _MATERIAL_YIELD_STRAIN.items():
            assert 0 < ys < 1, f"{mat} yield strain {ys} out of range"

    def test_safety_factor_reasonable(self):
        """Safety factor should be between 0 and 1."""
        assert 0 < _SNAP_FIT_SAFETY_FACTOR < 1

    def test_pin_pitch_standard(self):
        """Pin pitch should be 2.54mm standard."""
        assert _PIN_PITCH == 2.54

    def test_fallback_component_h_positive(self):
        """Fallback height should be a reasonable positive value."""
        assert 5 < _FALLBACK_COMPONENT_H < 30

    def test_top_display_classes_not_empty(self):
        """Display class set should contain known display types."""
        assert len(_TOP_DISPLAY_CLASSES) >= 3
        assert "Display-OLED-class" in _TOP_DISPLAY_CLASSES
        assert "Display-LCD-class" in _TOP_DISPLAY_CLASSES

    def test_material_table_has_common_materials(self):
        """Material table should have PLA, PETG, ABS, TPU."""
        for mat in ("PLA", "PETG", "ABS", "TPU"):
            assert mat in _MATERIAL_YIELD_STRAIN

    def test_yield_strain_ordering(self):
        """TPU > ABS > PETG > PLA in yield strain (ductility)."""
        assert (_MATERIAL_YIELD_STRAIN["TPU"] >
                _MATERIAL_YIELD_STRAIN["ABS"] >
                _MATERIAL_YIELD_STRAIN["PETG"] >
                _MATERIAL_YIELD_STRAIN["PLA"])


# ================================================================
# Group 8: Dimension formula edge cases
# ================================================================

class TestDimensionEdgeCases:
    """Tests for edge cases in dimension calculations."""

    def test_very_small_pcb(self):
        """Small PCB (20x15mm) should still produce valid shell dimensions."""
        pcb = _make_pcb_spec(length=20.0, width=15.0)
        spec = compute_two_piece_spec(pcb)
        assert spec.outer_l > spec.inner_l > 20.0
        assert spec.outer_w > spec.inner_w > 15.0
        assert spec.base_h > 0

    def test_very_large_pcb(self):
        """Large PCB (200x150mm) should scale correctly."""
        pcb = _make_pcb_spec(length=200.0, width=150.0)
        spec = compute_two_piece_spec(pcb)
        assert spec.inner_l == 200.0 + 5.0  # 2*2.5 padding
        assert spec.inner_w == 150.0 + 5.0

    def test_large_padding(self):
        """Large padding should produce wider gap between PCB and wall."""
        pcb = _make_pcb_spec()
        spec = compute_two_piece_spec(pcb, padding=10.0)
        assert spec.inner_l == 68.58 + 20.0  # 2*10 padding
        assert spec.inner_w == 53.34 + 20.0

    def test_thick_wall(self):
        """Thick wall should increase outer dimensions but not inner."""
        pcb = _make_pcb_spec()
        spec_thin = compute_two_piece_spec(pcb, wall=1.5)
        spec_thick = compute_two_piece_spec(pcb, wall=4.0)

        # Inner dimensions same
        assert abs(spec_thin.inner_l - spec_thick.inner_l) < 0.01
        # Outer dimensions larger with thick wall
        assert spec_thick.outer_l > spec_thin.outer_l

    def test_high_tolerance(self):
        """Higher tolerance should increase outer dimensions."""
        pcb = _make_pcb_spec()
        spec_low = compute_two_piece_spec(pcb, tol=0.1)
        spec_high = compute_two_piece_spec(pcb, tol=0.8)

        assert spec_high.outer_l > spec_low.outer_l
        assert spec_high.outer_w > spec_low.outer_w
        # Inner stays the same
        assert abs(spec_high.inner_l - spec_low.inner_l) < 0.01

    def test_tall_standoff(self):
        """Taller standoff should increase inner_h and base_h."""
        pcb = _make_pcb_spec()
        spec_short = compute_two_piece_spec(pcb, standoff_height=3.0)
        spec_tall = compute_two_piece_spec(pcb, standoff_height=10.0)

        assert spec_tall.inner_h > spec_short.inner_h
        assert spec_tall.base_h > spec_short.base_h
        diff = spec_tall.inner_h - spec_short.inner_h
        assert abs(diff - 7.0) < 0.01  # exactly 10-3=7mm difference
