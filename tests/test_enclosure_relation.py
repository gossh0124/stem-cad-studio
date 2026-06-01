"""tests/test_enclosure_relation.py — STR13: enclosure_relation 5-bucket dispatch tests."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.assembly_solver import solve, _build_comp_list, _Comp
from lib.registry import (
    COMPONENT_REGISTRY, ENCLOSURE_RELATIONS, ComponentSpec,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENCLOSURE_SPEC = {"inner_length": 100, "inner_width": 80, "inner_height": 50}
_EMPTY_WIRING = {}


def _solve_simple(components):
    """Run solve() with minimal config."""
    return solve(components, _EMPTY_WIRING, _ENCLOSURE_SPEC)


def _make_spec(enc_rel: str) -> ComponentSpec:
    """Create a minimal ComponentSpec with the given enclosure_relation."""
    return ComponentSpec(
        name="Test Component",
        class_name="Test-class",
        length_mm=20.0,
        width_mm=15.0,
        height_mm=10.0,
        weight_g=5.0,
        thermal_mw=100.0,
        enclosure_relation=enc_rel,
    )


def _build_with_fake_registry(entries: list[tuple[str, str]]) -> list[_Comp]:
    """Build _Comp list from [(class_name, enclosure_relation), ...] via a fake registry."""
    fake_reg = {
        cn: _make_spec(rel)
        for cn, rel in entries
    }
    components = [{"type": cn, "role": "Other"} for cn, _ in entries]
    return _build_comp_list(components, fake_reg)


# ---------------------------------------------------------------------------
# Class 1: 5-bucket dispatch
# ---------------------------------------------------------------------------

class TestEnclosureRelationDispatch:
    """Verify that solve() routes components to the correct output bucket."""

    def test_internal_goes_to_placements(self):
        # Arduino-Uno-class is 'internal' by registry
        result = _solve_simple([{"type": "Arduino-Uno-class", "role": "Brain"}])
        types = {p["type"] for p in result["placements"]}
        assert "Arduino-Uno-class" in types
        assert result["panel_placements"] == []
        assert result["external_refs"] == []
        assert result["embedded_refs"] == []

    def test_breadboard_goes_to_placements(self):
        # Sensor-MSGEQ7-class is 'breadboard' by registry
        result = _solve_simple([{"type": "Sensor-MSGEQ7-class", "role": "Sensor"}])
        types = {p["type"] for p in result["placements"]}
        assert "Sensor-MSGEQ7-class" in types
        assert result["panel_placements"] == []
        assert result["external_refs"] == []
        assert result["embedded_refs"] == []

    def test_panel_goes_to_panel_placements(self):
        # Button-class is 'panel' by registry
        result = _solve_simple([{"type": "Button-class", "role": "Input"}])
        types = {p["type"] for p in result["panel_placements"]}
        assert "Button-class" in types
        assert result["placements"] == []
        assert result["external_refs"] == []
        assert result["embedded_refs"] == []

    def test_external_goes_to_external_refs(self):
        # Battery-LiPo-class is 'external' by registry
        result = _solve_simple([{"type": "Battery-LiPo-class", "role": "Power"}])
        types = {p["type"] for p in result["external_refs"]}
        assert "Battery-LiPo-class" in types
        assert result["placements"] == []
        assert result["panel_placements"] == []
        assert result["embedded_refs"] == []

    def test_embedded_goes_to_embedded_refs(self):
        # Use a fake registry entry with enclosure_relation='embedded'
        fake_reg = {"Embedded-Sensor-class": _make_spec("embedded")}
        result = solve(
            [{"type": "Embedded-Sensor-class", "role": "Sensor"}],
            _EMPTY_WIRING,
            _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        types = {p["type"] for p in result["embedded_refs"]}
        assert "Embedded-Sensor-class" in types
        assert result["placements"] == []
        assert result["panel_placements"] == []
        assert result["external_refs"] == []

    def test_mixed_all_5_types_distribute_correctly(self):
        # Build one component of each relation via fake registry
        fake_reg = {
            "Int-class":   _make_spec("internal"),
            "BB-class":    _make_spec("breadboard"),
            "Panel-class": _make_spec("panel"),
            "Ext-class":   _make_spec("external"),
            "Emb-class":   _make_spec("embedded"),
        }
        comps = [
            {"type": "Int-class",   "role": "Brain"},
            {"type": "BB-class",    "role": "Sensor"},
            {"type": "Panel-class", "role": "Input"},
            {"type": "Ext-class",   "role": "Power"},
            {"type": "Emb-class",   "role": "Actuator"},
        ]
        result = solve(
            comps, _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        assert len(result["placements"]) == 2         # internal + breadboard
        assert len(result["panel_placements"]) == 1   # panel
        assert len(result["external_refs"]) == 1      # external
        assert len(result["embedded_refs"]) == 1      # embedded

    def test_internal_and_breadboard_share_pack_bucket(self):
        # Both should appear in placements, neither in other buckets
        fake_reg = {
            "Int-class": _make_spec("internal"),
            "BB-class":  _make_spec("breadboard"),
        }
        result = solve(
            [{"type": "Int-class", "role": "Brain"}, {"type": "BB-class", "role": "Sensor"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        pack_types = {p["type"] for p in result["placements"]}
        assert "Int-class" in pack_types
        assert "BB-class" in pack_types
        assert result["panel_placements"] == []
        assert result["external_refs"] == []
        assert result["embedded_refs"] == []

    def test_empty_components_returns_empty_buckets(self):
        result = _solve_simple([])
        assert result["placements"] == []
        assert result["panel_placements"] == []
        assert result["external_refs"] == []
        assert result["embedded_refs"] == []

    def test_unknown_component_type_skipped(self):
        # Components with no registry entry are silently skipped
        result = _solve_simple([{"type": "NonExistent-class", "role": "Brain"}])
        assert result["placements"] == []

    def test_enclosure_partition_decision_recorded(self):
        # The solve() function always records an enclosure_partition decision
        result = _solve_simple([{"type": "Arduino-Uno-class", "role": "Brain"}])
        steps = [d["step"] for d in result["decisions"]]
        assert "enclosure_partition" in steps

    def test_enclosure_partition_decision_counts_match(self):
        # Decision description should reflect actual counts
        fake_reg = {
            "Int-class":   _make_spec("internal"),
            "Panel-class": _make_spec("panel"),
        }
        result = solve(
            [{"type": "Int-class", "role": "Brain"}, {"type": "Panel-class", "role": "Input"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        partition_decision = next(
            d for d in result["decisions"] if d["step"] == "enclosure_partition"
        )
        desc = partition_decision["description"]
        # Verify it says 2 total components
        assert "2" in desc


# ---------------------------------------------------------------------------
# Class 2: Registry defaults
# ---------------------------------------------------------------------------

class TestEnclosureRelationDefaults:
    """Verify registry defaults for well-known component classes."""

    # MCUs and motors that should live inside the enclosure
    @pytest.mark.parametrize("cls", [
        "Arduino-Uno-class", "ESP32-class", "RaspberryPi-class", "Microbit-class",
        "Motor-Servo-class",  # no explicit field → defaults to internal
        "Sensor-TempHumid-class",
    ])
    def test_internal_components(self, cls):
        assert COMPONENT_REGISTRY[cls].enclosure_relation == "internal"

    @pytest.mark.parametrize("cls", [
        "Button-class", "Switch-class", "Lighting-LED-RGB-class",
        "Sensor-Ultrasonic-class", "Sensor-PIR-class",
        "Sensor-Light-class", "Sensor-IR-class",
    ])
    def test_panel_components(self, cls):
        assert COMPONENT_REGISTRY[cls].enclosure_relation == "panel"

    @pytest.mark.parametrize("cls", [
        "Battery-LiPo-class", "USB-5V-class", "Battery-AA-class",
        "Sensor-SoilMoisture-class",
    ])
    def test_external_components(self, cls):
        assert COMPONENT_REGISTRY[cls].enclosure_relation == "external"

    def test_embedded_components(self):
        assert COMPONENT_REGISTRY["Pump-Water-class"].enclosure_relation == "embedded"

    def test_sensor_msgeq7_is_breadboard(self):
        assert COMPONENT_REGISTRY["Sensor-MSGEQ7-class"].enclosure_relation == "breadboard"

    def test_default_when_not_specified_is_internal(self):
        spec = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10)
        assert spec.enclosure_relation == "internal"

    def test_skip_enclosure_true_becomes_external(self):
        # Legacy: skip_enclosure=True → enclosure_relation='external'
        spec = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                             skip_enclosure=True)
        assert spec.enclosure_relation == "external"
        assert spec.skip_enclosure is True

    def test_non_internal_sets_skip_enclosure(self):
        for rel in ("breadboard", "panel", "external", "embedded"):
            spec = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                                 enclosure_relation=rel)
            assert spec.skip_enclosure is True, f"{rel} should set skip_enclosure"

    def test_invalid_enclosure_relation_raises(self):
        with pytest.raises(ValueError, match="enclosure_relation"):
            ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                          enclosure_relation="invalid_value")


# ---------------------------------------------------------------------------
# Class 3: _build_comp_list and _prepare_components
# ---------------------------------------------------------------------------

class TestEnclosureRelationPrepareComponents:
    """Verify _build_comp_list correctly resolves enclosure_relation."""

    @pytest.mark.parametrize("rel", ["internal", "panel", "external", "breadboard", "embedded"])
    def test_all_relations_preserved_from_spec(self, rel):
        comps = _build_with_fake_registry([(f"{rel}-class", rel)])
        assert len(comps) == 1
        assert comps[0].enclosure_relation == rel

    def test_missing_registry_entry_skipped(self):
        # Components without a matching registry entry are dropped
        comps = _build_comp_list(
            [{"type": "Unknown-class", "role": "Brain"}],
            COMPONENT_REGISTRY,
        )
        assert comps == []

    def test_user_spec_fn_fallback_used(self):
        # user_spec_fn provides spec when registry lookup fails
        fake_spec = _make_spec("embedded")
        comps = _build_comp_list(
            [{"type": "Custom-class", "role": "Sensor"}],
            {},  # empty registry
            user_spec_fn=lambda cls: fake_spec if cls == "Custom-class" else None,
        )
        assert len(comps) == 1
        assert comps[0].enclosure_relation == "embedded"

    def test_spec_enclosure_relation_takes_precedence_over_component_dict(self):
        # _build_comp_list reads enclosure_relation from the spec, not from the component dict.
        # Even if the caller passes "enclosure_relation" in the dict, the spec wins.
        fake_reg = {"Test-class": _make_spec("panel")}
        comps = _build_comp_list(
            [{"type": "Test-class", "role": "Input", "enclosure_relation": "external"}],
            fake_reg,
        )
        # Spec says 'panel', component dict says 'external' → spec wins
        assert comps[0].enclosure_relation == "panel"

    def test_multiple_components_all_built(self):
        entries = [
            ("A-class", "internal"),
            ("B-class", "panel"),
            ("C-class", "external"),
        ]
        comps = _build_with_fake_registry(entries)
        assert len(comps) == 3
        rels = {c.type: c.enclosure_relation for c in comps}
        assert rels["A-class"] == "internal"
        assert rels["B-class"] == "panel"
        assert rels["C-class"] == "external"


# ---------------------------------------------------------------------------
# Class 4: Output structure
# ---------------------------------------------------------------------------

class TestEnclosureRelationOutputStructure:
    """Verify the output dict structure for each bucket."""

    def _run_all_five(self):
        fake_reg = {
            "Int-class":   _make_spec("internal"),
            "BB-class":    _make_spec("breadboard"),
            "Panel-class": _make_spec("panel"),
            "Ext-class":   _make_spec("external"),
            "Emb-class":   _make_spec("embedded"),
        }
        comps = [
            {"type": "Int-class",   "role": "Brain"},
            {"type": "BB-class",    "role": "Sensor"},
            {"type": "Panel-class", "role": "Input"},
            {"type": "Ext-class",   "role": "Power"},
            {"type": "Emb-class",   "role": "Actuator"},
        ]
        return solve(
            comps, _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )

    def test_placements_have_enclosure_relation_field(self):
        result = self._run_all_five()
        for p in result["placements"]:
            assert "enclosure_relation" in p, f"Missing field in {p}"

    def test_placements_enclosure_relation_is_internal_or_breadboard(self):
        result = self._run_all_five()
        for p in result["placements"]:
            assert p["enclosure_relation"] in ("internal", "breadboard"), (
                f"Placement {p['type']} has unexpected relation {p['enclosure_relation']}"
            )

    def test_panel_placements_have_required_fields(self):
        result = self._run_all_five()
        for p in result["panel_placements"]:
            for key in ("type", "role", "face", "u", "v", "L", "W", "H", "enclosure_relation"):
                assert key in p, f"panel_placement missing key '{key}': {p}"

    def test_panel_placements_enclosure_relation_is_panel(self):
        result = self._run_all_five()
        for p in result["panel_placements"]:
            assert p["enclosure_relation"] == "panel", (
                f"panel_placement {p['type']} has wrong relation {p['enclosure_relation']}"
            )

    def test_external_refs_have_required_fields(self):
        result = self._run_all_five()
        for ref in result["external_refs"]:
            for key in ("type", "role", "wire_exit_face", "wire_exit_u",
                        "wire_exit_v", "wire_exit_diameter", "enclosure_relation"):
                assert key in ref, f"external_ref missing key '{key}': {ref}"

    def test_external_refs_enclosure_relation_is_external(self):
        result = self._run_all_five()
        for ref in result["external_refs"]:
            assert ref["enclosure_relation"] == "external"

    def test_embedded_refs_have_required_fields(self):
        result = self._run_all_five()
        for ref in result["embedded_refs"]:
            for key in ("type", "role", "host_structure", "thermal_mw", "enclosure_relation"):
                assert key in ref, f"embedded_ref missing key '{key}': {ref}"

    def test_embedded_refs_enclosure_relation_is_embedded(self):
        result = self._run_all_five()
        for ref in result["embedded_refs"]:
            assert ref["enclosure_relation"] == "embedded"

    def test_result_always_has_all_four_list_keys(self):
        # Even with a single internal component, all 4 list keys are present
        result = _solve_simple([{"type": "Arduino-Uno-class", "role": "Brain"}])
        for key in ("placements", "panel_placements", "external_refs", "embedded_refs"):
            assert key in result, f"Missing top-level key '{key}'"
            assert isinstance(result[key], list)

    def test_external_wire_exit_defaults(self):
        # External components default to side-back wire exit with 6mm diameter
        result = _solve_simple([{"type": "Battery-LiPo-class", "role": "Power"}])
        ref = result["external_refs"][0]
        assert ref["wire_exit_face"] == "side-back"
        assert ref["wire_exit_diameter"] == 6.0

    def test_embedded_host_structure_default(self):
        fake_reg = {"Emb-class": _make_spec("embedded")}
        result = solve(
            [{"type": "Emb-class", "role": "Sensor"}],
            _EMPTY_WIRING, _ENCLOSURE_SPEC,
            user_spec_fn=lambda cls: fake_reg.get(cls),
        )
        assert result["embedded_refs"][0]["host_structure"] == "external_body"


# ---------------------------------------------------------------------------
# Class 5: Cross-layer consistency
# ---------------------------------------------------------------------------

class TestEnclosureRelationCrossLayer:
    """Verify that enclosure_relation values are consistent across the project."""

    def test_all_registry_components_have_valid_enclosure_relation(self):
        """Every entry in COMPONENT_REGISTRY must have a valid enclosure_relation."""
        for cls, spec in COMPONENT_REGISTRY.items():
            assert spec.enclosure_relation in ENCLOSURE_RELATIONS, (
                f"{cls}.enclosure_relation={spec.enclosure_relation!r} "
                f"is not in {sorted(ENCLOSURE_RELATIONS)}"
            )

    def test_enclosure_relations_frozenset_has_5_values(self):
        assert len(ENCLOSURE_RELATIONS) == 5
        assert ENCLOSURE_RELATIONS == frozenset(
            {"internal", "breadboard", "panel", "external", "embedded"}
        )

    def test_registry_contains_all_5_relation_types(self):
        """The registry should exercise all 5 bucket types."""
        relations_used = {spec.enclosure_relation for spec in COMPONENT_REGISTRY.values()}
        missing = ENCLOSURE_RELATIONS - relations_used
        assert not missing, (
            f"These enclosure_relation values are not used in any registry entry: {missing}"
        )

    def test_helpers_enclosure_relation_for_known_types(self):
        """data_generator_b_helpers.enclosure_relation_for() returns valid values."""
        from training.data_generator_b_helpers import enclosure_relation_for
        for cls in list(COMPONENT_REGISTRY.keys())[:10]:
            rel = enclosure_relation_for(cls)
            assert rel in ENCLOSURE_RELATIONS, (
                f"enclosure_relation_for({cls!r}) returned invalid {rel!r}"
            )

    def test_helpers_unknown_type_returns_internal(self):
        """Unknown class_name fallback must be 'internal'."""
        from training.data_generator_b_helpers import enclosure_relation_for
        assert enclosure_relation_for("Totally-Unknown-class") == "internal"

    def test_helpers_matches_registry_for_all_known_types(self):
        """Helper must agree with registry for every known component."""
        from training.data_generator_b_helpers import enclosure_relation_for
        mismatches = []
        for cls, spec in COMPONENT_REGISTRY.items():
            helper_val = enclosure_relation_for(cls)
            if helper_val != spec.enclosure_relation:
                mismatches.append(
                    f"{cls}: registry={spec.enclosure_relation!r} "
                    f"vs helper={helper_val!r}"
                )
        assert not mismatches, (
            "enclosure_relation mismatch between registry and helper:\n"
            + "\n".join(mismatches)
        )

    def test_json_snapshot_matches_registry(self):
        """_registry_enclosure_relation.json snapshot must match live registry."""
        import json
        _ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        snap_path = os.path.join(_ROOT, "training", "_registry_enclosure_relation.json")
        with open(snap_path, encoding="utf-8") as f:
            snapshot = json.load(f)
        mapping = snapshot["mapping"]
        mismatches = []
        for cls, snap_val in mapping.items():
            if cls not in COMPONENT_REGISTRY:
                continue  # snapshot may have extra entries; that's OK
            live_val = COMPONENT_REGISTRY[cls].enclosure_relation
            if live_val != snap_val:
                mismatches.append(f"{cls}: snapshot={snap_val!r}, registry={live_val!r}")
        assert not mismatches, (
            "JSON snapshot is out of sync with registry:\n" + "\n".join(mismatches)
        )
