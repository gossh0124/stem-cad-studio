"""Tests for lib/assembly_solver/embedded_validator.py."""
import pytest

from lib.assembly_solver.embedded_validator import validate_host_structure


class TestValidateHostStructure:
    def _valid(self):
        return {
            "kind": "water_tank",
            "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
        }

    def test_valid_passes(self):
        validate_host_structure(self._valid(), "Test")

    def test_all_kinds_accepted(self):
        for kind in ("water_tank", "chassis", "wearable_body", "external_body"):
            hs = self._valid()
            hs["kind"] = kind
            validate_host_structure(hs)

    def test_invalid_kind_raises(self):
        hs = self._valid()
        hs["kind"] = "spaceship"
        with pytest.raises(ValueError, match="kind"):
            validate_host_structure(hs, "BadComp")

    def test_missing_kind_raises(self):
        hs = {"entry_port": {"face": "top", "u": 0.5, "v": 0.5}}
        with pytest.raises(ValueError, match="kind"):
            validate_host_structure(hs)

    def test_all_faces_accepted(self):
        for face in ("top", "bottom", "left", "right", "front", "back"):
            hs = self._valid()
            hs["entry_port"]["face"] = face
            validate_host_structure(hs)

    def test_invalid_face_raises(self):
        hs = self._valid()
        hs["entry_port"]["face"] = "diagonal"
        with pytest.raises(ValueError, match="face"):
            validate_host_structure(hs, "BadFace")

    def test_u_out_of_range_raises(self):
        hs = self._valid()
        hs["entry_port"]["u"] = 1.5
        with pytest.raises(ValueError, match="u=1.5"):
            validate_host_structure(hs)

    def test_v_negative_raises(self):
        hs = self._valid()
        hs["entry_port"]["v"] = -0.1
        with pytest.raises(ValueError, match="v=-0.1"):
            validate_host_structure(hs)

    def test_boundary_values_pass(self):
        for u, v in [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)]:
            hs = self._valid()
            hs["entry_port"]["u"] = u
            hs["entry_port"]["v"] = v
            validate_host_structure(hs)

    def test_class_name_in_error_message(self):
        hs = self._valid()
        hs["kind"] = "bad"
        with pytest.raises(ValueError, match="Mist-Atomizer"):
            validate_host_structure(hs, "Mist-Atomizer")

    def test_missing_u_raises(self):
        # H7: entry_port 缺 u 鍵應 raise ValueError
        hs = {"kind": "water_tank", "entry_port": {"face": "top", "v": 0.5}}
        with pytest.raises(ValueError, match="u"):
            validate_host_structure(hs, "TestComp")

    def test_missing_v_raises(self):
        # H7: entry_port 缺 v 鍵應 raise ValueError
        hs = {"kind": "water_tank", "entry_port": {"face": "top", "u": 0.5}}
        with pytest.raises(ValueError, match="v"):
            validate_host_structure(hs, "TestComp")
