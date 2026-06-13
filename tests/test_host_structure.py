"""tests/test_host_structure.py -- ER2 v3 host_structure unit tests.

Covers: validator, ComponentSpec field, solver placement (v3 + v2 fallback),
_to_embedded_ref output, and warning on missing host_structure.
"""
import sys
import os
import warnings

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.registry.component_spec import ComponentSpec
from lib.assembly_solver.embedded_validator import validate_host_structure
from lib.assembly_solver import solve, _build_comp_list, _to_embedded_ref
from lib.assembly_solver._types import _Comp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CANONICAL_HS = {
    "kind": "water_tank",
    "dimensions": {"length_mm": 120.0, "width_mm": 80.0, "height_mm": 60.0},
    "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
    "cavity": {
        "depth_mm": 20.0, "diam_mm": 28.0,
        "length_mm": None, "width_mm": None,
    },
    "wire_entry": {
        "face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 8.0,
    },
}

_ENCLOSURE_SPEC = {"inner_length": 100, "inner_width": 80, "inner_height": 50}
_EMPTY_WIRING = {}


def _make_spec(enc_rel, host_structure=None):
    """Create a minimal ComponentSpec with given enclosure_relation."""
    return ComponentSpec(
        name="Test Component",
        class_name="Test-class",
        length_mm=20.0, width_mm=15.0, height_mm=10.0,
        weight_g=5.0, thermal_mw=100.0,
        enclosure_relation=enc_rel,
        host_structure=host_structure,
    )


# ---------------------------------------------------------------------------
# 1. validate_host_structure -- valid dict
# ---------------------------------------------------------------------------

class TestHostStructureValidation:

    def test_host_structure_dict_valid(self):
        """validate_host_structure() passes for canonical Mist-Ultrasonic dict."""
        validate_host_structure(_CANONICAL_HS, "Mist-Ultrasonic-class")

    def test_host_structure_invalid_kind(self):
        """Raises ValueError for unknown kind."""
        bad = {**_CANONICAL_HS, "kind": "spaceship"}
        with pytest.raises(ValueError, match="kind"):
            validate_host_structure(bad, "Bad-class")

    def test_host_structure_u_out_of_range(self):
        """Raises ValueError for u > 1.0."""
        bad = {
            **_CANONICAL_HS,
            "entry_port": {"face": "top", "u": 1.5, "v": 0.5},
        }
        with pytest.raises(ValueError, match="entry_port.u"):
            validate_host_structure(bad, "Bad-class")


# ---------------------------------------------------------------------------
# 2. Solver placement tests
# ---------------------------------------------------------------------------

class TestEmbeddedPlacement:

    def test_legacy_string_passthrough(self):
        """Solver accepts host_structure='external_body' without error."""
        fake_reg = {"Emb-class": _make_spec("embedded", "external_body")}
        result = solve(
            [{"type": "Emb-class", "role": "Sensor"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        assert len(result["embedded_refs"]) == 1
        ref = result["embedded_refs"][0]
        assert ref["host_structure"] == "external_body"

    def test_embedded_placement_v3(self):
        """Solver sets c.x = u * host_l, c.face_out = entry_port.face."""
        fake_reg = {"Emb-class": _make_spec("embedded", _CANONICAL_HS)}
        result = solve(
            [{"type": "Emb-class", "role": "Sensor"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        ref = result["embedded_refs"][0]
        # u=0.5 * host_l=120.0 = 60.0
        assert ref["x"] == 60.0
        # v=0.5 * host_w=80.0 = 40.0
        assert ref["y"] == 40.0
        assert ref["face_out"] == "top"
        assert ref["zone"] == "embedded-water_tank"

    def test_embedded_entry_port_missing_uv_raises(self):
        """H7/NSF: entry_port dict present but missing u/v must raise, not silent-center 0.5."""
        bad_hs = {
            "kind": "water_tank",
            "dimensions": {"length_mm": 120.0, "width_mm": 80.0, "height_mm": 60.0},
            "entry_port": {"face": "top"},  # u/v deliberately absent
        }
        fake_reg = {"Emb-class": _make_spec("embedded", bad_hs)}
        with pytest.raises(ValueError, match="u/v"):
            solve(
                [{"type": "Emb-class", "role": "Sensor"}],
                _EMPTY_WIRING, _ENCLOSURE_SPEC,
                user_spec_fn=lambda cls: fake_reg.get(cls),
            )

    def test_embedded_placement_v2_fallback(self):
        """Missing dict -> solver uses inner_l/2, inner_w/2."""
        fake_reg = {"Emb-class": _make_spec("embedded", "external_body")}
        result = solve(
            [{"type": "Emb-class", "role": "Sensor"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        ref = result["embedded_refs"][0]
        # inner_l=100, comp L=20 -> x = max(0, 100/2 - 20/2) = 40.0
        assert ref["x"] == 40.0
        # inner_w=80, comp W=15 -> y = max(0, 80/2 - 15/2) = 32.5
        assert ref["y"] == 32.5
        assert ref["face_out"] == "bottom"
        assert ref["zone"] == "embedded-host"


# ---------------------------------------------------------------------------
# 3. _to_embedded_ref output
# ---------------------------------------------------------------------------

class TestToEmbeddedRef:

    def test_to_embedded_ref_v3(self):
        """Output dict contains wire_entry key when v3 dict is present."""
        c = _Comp(
            type="Emb-class", role="Sensor",
            L=20.0, W=15.0, H=10.0,
            weight_g=5.0, thermal_mw=100.0,
            ports=[],
            enclosure_relation="embedded",
            x=60.0, y=40.0,
            face_out="top",
            zone="embedded-water_tank",
            host_structure=_CANONICAL_HS,
        )
        ref = _to_embedded_ref(c)
        assert "wire_entry" in ref
        assert ref["wire_entry"]["face"] == "back"
        assert ref["wire_entry"]["hole_diam_mm"] == 8.0
        assert isinstance(ref["host_structure"], dict)
        assert ref["host_structure"]["kind"] == "water_tank"


# ---------------------------------------------------------------------------
# 4. ComponentSpec warning
# ---------------------------------------------------------------------------

class TestComponentSpecWarning:

    def test_component_spec_warns_no_host(self):
        """embedded entry with host_structure=None issues UserWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            spec = ComponentSpec(
                name="No Host",
                class_name="NoHost-class",
                length_mm=10.0, width_mm=10.0, height_mm=10.0,
                enclosure_relation="embedded",
                host_structure=None,
            )
            assert len(w) == 1
            assert "host_structure" in str(w[0].message)
            assert spec.host_structure == "external_body"
