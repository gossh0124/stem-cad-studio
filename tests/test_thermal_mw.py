"""tests/test_thermal_mw.py — STR15: THERMAL_MW cross-layer verification.

Validates that THERMAL_MW values in lib/specs.py are consistent across all
layers that consume them: registry, assembly_solver, ensemble_filter, and
the component datasheet JSON.
"""
import sys
import os
import json
import pytest

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.specs import THERMAL_MW, COMPONENT_NAME_ALIASES
from lib.registry import COMPONENT_REGISTRY

# Path to the authoritative datasheet JSON (SSOT)
_DATASHEET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "component_datasheet_verified.json",
)

# Thresholds mirrored from assembly_solver.py / ensemble_filter.py
_THERMAL_HOT_MW = 500      # assembly_solver._THERMAL_HOT_MW (> comparison)
_VENT_THRESHOLD_MW = 1500  # assembly_solver.THERMAL_TIER_MID — updated ADR-2
_ENSEMBLE_HOT_MW = 500     # ensemble_filter._score_thermal (>= comparison)

# Components that are purely structural/passive and should have 0mW
_KNOWN_ZERO_THERMAL = {"Button-class", "Switch-class", "Switch-Generic-class",
                       "Battery-LiPo-class", "Battery-AA-class",
                       "Chassis-Car-class",
                       "USB-5V-class"}

# MCU board classes that must always generate heat
_MCU_CLASSES = {"Arduino-Uno-class", "ESP32-class", "RaspberryPi-class",
                "Microbit-class"}

# Motor/actuator classes expected to be warmer than sensors
_MOTOR_CLASSES = {"Motor-DC-class", "Motor-Stepper-class", "Motor-Servo-class",
                  "Pump-Water-class"}

_SENSOR_CLASSES = {"Sensor-TempHumid-class", "Sensor-Ultrasonic-class",
                   "Sensor-PIR-class", "Sensor-SoilMoisture-class",
                   "Sensor-Light-class", "Sensor-IR-class", "Sensor-MSGEQ7-class"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_datasheet() -> dict:
    with open(_DATASHEET_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _registry_classes_with_heat() -> list[str]:
    """Return registry keys whose ComponentSpec.thermal_mw > 0."""
    return [k for k, v in COMPONENT_REGISTRY.items() if v.thermal_mw > 0]


# ===========================================================================
# Class TestThermalMwCompleteness
# ===========================================================================

class TestThermalMwCompleteness:
    """Structural completeness checks on the THERMAL_MW dict itself."""

    def test_thermal_mw_not_empty(self):
        """THERMAL_MW must be a non-empty dict."""
        assert isinstance(THERMAL_MW, dict)
        assert len(THERMAL_MW) > 0, "THERMAL_MW is empty"

    def test_all_keys_are_strings(self):
        """Every key in THERMAL_MW must be a str."""
        bad = [k for k in THERMAL_MW if not isinstance(k, str)]
        assert not bad, f"Non-string keys: {bad}"

    def test_all_values_are_numeric(self):
        """Every value must be int or float."""
        bad = {k: v for k, v in THERMAL_MW.items()
               if not isinstance(v, (int, float))}
        assert not bad, f"Non-numeric values: {bad}"

    def test_no_negative_values(self):
        """No component should have negative thermal dissipation."""
        neg = {k: v for k, v in THERMAL_MW.items() if v < 0}
        assert not neg, f"Negative THERMAL_MW entries: {neg}"

    def test_values_within_reasonable_bounds(self):
        """All values must be 0 ≤ mW ≤ 10000 (no component exceeds 10W)."""
        out_of_range = {k: v for k, v in THERMAL_MW.items()
                        if not (0.0 <= v <= 10000.0)}
        assert not out_of_range, f"Out-of-range THERMAL_MW entries: {out_of_range}"

    def test_keys_exist_in_registry_or_aliases(self):
        """Every THERMAL_MW key must resolve to a known registry class or alias."""
        all_known = set(COMPONENT_REGISTRY.keys()) | set(COMPONENT_NAME_ALIASES.keys())
        unknown = {k for k in THERMAL_MW if k not in all_known}
        assert not unknown, (
            f"THERMAL_MW keys not found in registry or aliases: {unknown}"
        )

    def test_registry_thermal_covered_by_specs(self):
        """Any registry component with thermal_mw > 0 must have a THERMAL_MW entry."""
        missing = [cls for cls in _registry_classes_with_heat()
                   if cls not in THERMAL_MW]
        assert not missing, (
            f"Registry components with thermal_mw > 0 but absent from THERMAL_MW: {missing}"
        )


# ===========================================================================
# Class TestThermalMwConsistency
# ===========================================================================

class TestThermalMwConsistency:
    """Semantic consistency across component categories."""

    def test_passive_components_have_zero_thermal(self):
        """Passive/structural components must have THERMAL_MW == 0."""
        non_zero = {k: THERMAL_MW[k] for k in _KNOWN_ZERO_THERMAL
                    if k in THERMAL_MW and THERMAL_MW[k] != 0.0}
        assert not non_zero, (
            f"Expected 0mW for passive components but got: {non_zero}"
        )

    def test_mcu_boards_have_positive_thermal(self):
        """All MCU board classes must generate heat (THERMAL_MW > 0)."""
        cold_mcus = {k: THERMAL_MW.get(k, "MISSING")
                     for k in _MCU_CLASSES
                     if THERMAL_MW.get(k, 0) <= 0}
        assert not cold_mcus, f"MCU boards should have THERMAL_MW > 0: {cold_mcus}"

    def test_motors_hotter_than_sensors_on_average(self):
        """Mean motor thermal should exceed mean sensor thermal."""
        motor_vals = [THERMAL_MW[k] for k in _MOTOR_CLASSES if k in THERMAL_MW]
        sensor_vals = [THERMAL_MW[k] for k in _SENSOR_CLASSES if k in THERMAL_MW]
        assert motor_vals, "No motor classes found in THERMAL_MW"
        assert sensor_vals, "No sensor classes found in THERMAL_MW"
        mean_motor = sum(motor_vals) / len(motor_vals)
        mean_sensor = sum(sensor_vals) / len(sensor_vals)
        assert mean_motor > mean_sensor, (
            f"Expected motors ({mean_motor:.0f}mW) hotter than sensors "
            f"({mean_sensor:.0f}mW)"
        )

    def test_registry_thermal_values_match_specs(self):
        """ComponentSpec.thermal_mw in registry must equal THERMAL_MW value.

        SSOT20: registry_data.py Tier-5 reads thermal_mw through from the specs
        cache, so registry == specs by construction (former STR15-DRIFT-02 xfail
        for 12 components defaulting to 0.0 is resolved and removed).
        """
        mismatches = {}
        for cls, spec in COMPONENT_REGISTRY.items():
            if cls in THERMAL_MW:
                expected = THERMAL_MW[cls]
                actual = spec.thermal_mw
                if abs(actual - expected) > 1e-6:
                    mismatches[cls] = {"registry": actual, "specs": expected}
        assert not mismatches, (
            f"THERMAL_MW vs registry mismatch: {mismatches}"
        )

    def test_usb_5v_zero_thermal(self):
        """USB-5V-class is a pass-through power module — should be 0 mW."""
        val = THERMAL_MW.get("USB-5V-class", "MISSING")
        assert val == 0.0, f"USB-5V-class should be 0mW, got {val}"

    def test_raspberry_pi_highest_mcu_thermal(self):
        """RaspberryPi-class should be the hottest MCU (Linux SBC)."""
        mcu_thermal = {k: THERMAL_MW[k] for k in _MCU_CLASSES if k in THERMAL_MW}
        assert mcu_thermal, "No MCU classes in THERMAL_MW"
        hottest = max(mcu_thermal, key=mcu_thermal.get)
        assert hottest == "RaspberryPi-class", (
            f"Expected RaspberryPi-class to be hottest MCU, got {hottest} "
            f"({mcu_thermal[hottest]}mW)"
        )


# ===========================================================================
# Class TestThermalMwSolverIntegration
# ===========================================================================

class TestThermalMwSolverIntegration:
    """Verify assembly_solver thresholds align with THERMAL_MW values."""

    def test_solver_threshold_constant_matches_expected(self):
        """assembly_solver._THERMAL_HOT_MW must be 500."""
        from lib import assembly_solver as asolver
        assert asolver._THERMAL_HOT_MW == 500, (
            f"Expected _THERMAL_HOT_MW=500, got {asolver._THERMAL_HOT_MW}"
        )

    def test_solver_tier_constants_defined(self):
        """ADR-2: Three-tier thermal constants must be module-level exports."""
        from lib import assembly_solver as asolver
        assert asolver.THERMAL_TIER_LOW == 500, (
            f"Expected THERMAL_TIER_LOW=500, got {asolver.THERMAL_TIER_LOW}"
        )
        assert asolver.THERMAL_TIER_MID == 1500, (
            f"Expected THERMAL_TIER_MID=1500, got {asolver.THERMAL_TIER_MID}"
        )
        assert asolver.THERMAL_TIER_HIGH == 3000, (
            f"Expected THERMAL_TIER_HIGH=3000, got {asolver.THERMAL_TIER_HIGH}"
        )

    def test_solver_vent_threshold_alias_matches_tier_mid(self):
        """_VENT_THRESHOLD_MW backward-compat alias must equal THERMAL_TIER_MID."""
        from lib import assembly_solver as asolver
        assert asolver._VENT_THRESHOLD_MW == asolver.THERMAL_TIER_MID, (
            f"_VENT_THRESHOLD_MW ({asolver._VENT_THRESHOLD_MW}) must equal "
            f"THERMAL_TIER_MID ({asolver.THERMAL_TIER_MID})"
        )

    def test_all_thermal_mw_keys_resolvable_by_registry(self):
        """assembly_solver builds components from registry; every THERMAL_MW key
        must be present in COMPONENT_REGISTRY for the solver to find it."""
        missing = [k for k in THERMAL_MW if k not in COMPONENT_REGISTRY]
        assert not missing, (
            f"THERMAL_MW keys absent from COMPONENT_REGISTRY (solver cannot look them up): {missing}"
        )

    def test_hot_set_classification_above_threshold(self):
        """Components with THERMAL_MW > 500 should be classified as 'hot' by solver."""
        hot_expected = {k for k, v in THERMAL_MW.items() if v > _THERMAL_HOT_MW}
        # Verify the set is non-empty (test is meaningful)
        assert hot_expected, "No components exceed _THERMAL_HOT_MW — threshold may be wrong"
        # Spot-check well-known hot components
        for cls in ("Motor-DC-class", "RaspberryPi-class", "Mist-Ultrasonic-class"):
            assert cls in hot_expected, f"{cls} expected in hot set but not found"

    def test_cold_set_classification_at_or_below_threshold(self):
        """Components with THERMAL_MW <= 500 should NOT be classified as hot."""
        cold_expected = {k for k, v in THERMAL_MW.items() if v <= _THERMAL_HOT_MW}
        for cls in _KNOWN_ZERO_THERMAL:
            if cls in THERMAL_MW:
                assert cls in cold_expected, (
                    f"{cls} has THERMAL_MW={THERMAL_MW[cls]} but should be <= {_THERMAL_HOT_MW}"
                )

    def test_vent_threshold_ge_not_gt(self):
        """ADR-2: THERMAL_TIER_MID (1500mW) is the HIGH-tier boundary (> comparison).
        Components above 1500mW should trigger active venting."""
        # Mist-Ultrasonic-class is 2500mW > 1500 — needs active venting
        assert THERMAL_MW.get("Mist-Ultrasonic-class", 0) > _VENT_THRESHOLD_MW, (
            "Mist-Ultrasonic-class (2500mW) should be > _VENT_THRESHOLD_MW(1500)"
        )
        # Components in the MID zone (500–1500mW) should have passive venting
        mid_zone = {k: v for k, v in THERMAL_MW.items()
                    if 500 < v <= _VENT_THRESHOLD_MW}
        assert mid_zone, "Expected some components in MID zone (500–1500mW)"

    def test_solver_can_run_full_pipeline_with_hot_component(self):
        """End-to-end: solver returns needs_venting=True (HIGH tier) when total > 1500mW."""
        from lib.assembly_solver import solve
        components = [
            {"type": "ESP32-class",    "role": "MCU"},      # 800mW
            {"type": "Motor-DC-class", "role": "Actuator"}, # 1500mW → total 2300mW
        ]
        enclosure = {"inner_l": 120, "inner_w": 80, "inner_h": 50}
        result = solve(components, {}, enclosure)
        tf = result.get("thermal_field", {})
        assert tf.get("thermal_tier") == "HIGH", (
            f"Expected thermal_tier=HIGH for 2300mW total, got {tf}"
        )
        assert tf.get("needs_venting") is True, (
            f"Expected needs_venting=True for 2300mW total, got thermal_field={tf}"
        )
        assert tf.get("passive_venting") is False, (
            "HIGH tier should not set passive_venting=True"
        )

    def test_solver_cold_pipeline_no_venting(self):
        """End-to-end: solver returns LOW tier for low-power components."""
        from lib.assembly_solver import solve
        components = [
            {"type": "Arduino-Uno-class",    "role": "MCU"},    # 250mW
            {"type": "Sensor-TempHumid-class", "role": "Sensor"}, # 12.5mW
        ]
        enclosure = {"inner_l": 120, "inner_w": 80, "inner_h": 50}
        result = solve(components, {}, enclosure)
        tf = result.get("thermal_field", {})
        assert tf.get("thermal_tier") == "LOW", (
            f"Expected thermal_tier=LOW for ~262.5mW total, got {tf}"
        )
        assert tf.get("needs_venting") is False, (
            f"Expected needs_venting=False for ~262.5mW total, got thermal_field={tf}"
        )

    def test_passive_zero_mw_not_estimated_by_thermal_index(self):
        """H10: 被動件 thermal_mw=0.0（SSOT 確認）+ 非空 thermal_index
        → 不應被 index 覆蓋估算，heat_sources 不含該元件。"""
        from lib.assembly_solver._types import _Comp
        from lib.assembly_solver.thermal import _validate_thermal
        passive = _Comp(
            type="Button-class", role="Output",
            L=10.0, W=10.0, H=5.0,
            weight_g=2.0, thermal_mw=0.0,
            ports=[],
        )
        # thermal_index 含 Button-class 估算值，但 mw=0.0 不是 None → 不應採用
        thermal_index = {"Button-class": {"total_typical_mw": 999}}
        result = _validate_thermal([passive], thermal_index, [])
        heat_types = [h["type"] for h in result["heat_sources"]]
        assert "Button-class" not in heat_types, (
            "被動件 mw=0.0 不應被 thermal_index 估算覆蓋"
        )
        assert result["total_power_mw"] == 0.0, (
            f"被動件總熱功率應為 0，得 {result['total_power_mw']}"
        )

# ===========================================================================
# Class TestThermalMwEnsembleFilter
# ===========================================================================

class TestThermalMwEnsembleFilter:
    """Verify ensemble_filter._score_thermal behaviour with THERMAL_MW."""

    def _score(self, compiled: dict, components: list) -> float:
        from lib.ensemble_filter import _score_thermal
        return _score_thermal(compiled, components)

    def test_no_hot_components_gives_full_score(self):
        """When no component exceeds 500mW, full score (15.0) is returned."""
        cold = [
            {"type": "Button-class"},
            {"type": "Sensor-TempHumid-class"},  # 12.5mW
            {"type": "Arduino-Uno-class"},        # 250mW — below 500
        ]
        score = self._score({}, cold)
        assert score == pytest.approx(15.0), (
            f"Expected 15.0 for cold components, got {score}"
        )

    def test_hot_component_no_strategy_reduces_score(self):
        """A hot component with no thermal strategy should reduce score by 8."""
        hot = [{"type": "Motor-DC-class"}]  # 1500mW — above 500 threshold
        score = self._score({}, hot)
        assert score == pytest.approx(7.0), (
            f"Expected 15.0 - 8.0 = 7.0 for hot component without strategy, got {score}"
        )

    def test_hot_component_with_strategy_gives_full_score(self):
        """A hot component WITH thermal.strategy should give full score (15.0)."""
        hot = [{"type": "Motor-DC-class"}]  # 1500mW
        compiled = {"thermal": {"strategy": "passive_vent"}}
        score = self._score(compiled, hot)
        assert score == pytest.approx(15.0), (
            f"Expected 15.0 with thermal strategy, got {score}"
        )

    def test_hot_component_with_vent_placement_partial_score(self):
        """vent_placement (but no strategy) reduces score by 3.0."""
        hot = [{"type": "Motor-DC-class"}]  # 1500mW
        compiled = {"thermal": {"vent_placement": "side_lower"}}
        score = self._score(compiled, hot)
        assert score == pytest.approx(12.0), (
            f"Expected 15.0 - 3.0 = 12.0 with vent_placement, got {score}"
        )

    def test_ensemble_hot_threshold_is_500_inclusive(self):
        """Ensemble filter uses >= 500 so exactly-500mW components are 'hot'."""
        # Motor-Servo-class is exactly 500mW
        at_threshold = [{"type": "Motor-Servo-class"}]
        score_no_strategy = self._score({}, at_threshold)
        assert score_no_strategy < 15.0, (
            f"Motor-Servo-class (500mW) should be flagged as hot (>= 500); "
            f"got score {score_no_strategy}"
        )

    def test_score_never_below_zero(self):
        """Score floor must be 0.0 — no negative scores."""
        hot = [{"type": "RaspberryPi-class"}]  # 3000mW
        score = self._score({}, hot)
        assert score >= 0.0, f"Score should never be negative, got {score}"

    def test_score_never_above_max(self):
        """Score ceiling must be 15.0 — max weight."""
        cold = [{"type": "Button-class"}]
        score = self._score({"thermal": {"strategy": "active_cooling"}}, cold)
        assert score <= 15.0, f"Score should never exceed 15.0, got {score}"


# ===========================================================================
# Class TestThermalMwDatasheetAlignment
# ===========================================================================

class TestThermalMwDatasheetAlignment:
    """Cross-check THERMAL_MW values against component_datasheet_verified.json."""

    @pytest.fixture(scope="class")
    def datasheet(self):
        return _load_datasheet()

    def test_datasheet_file_exists(self):
        assert os.path.isfile(_DATASHEET_PATH), (
            f"Datasheet file not found: {_DATASHEET_PATH}"
        )

    def test_all_thermal_mw_keys_covered_in_datasheet(self, datasheet):
        """Every THERMAL_MW key should appear in the datasheet JSON."""
        missing = [k for k in THERMAL_MW if k not in datasheet]
        assert not missing, (
            f"THERMAL_MW keys absent from datasheet: {missing}"
        )

    def test_datasheet_thermal_mw_matches_specs(self, datasheet):
        """For each entry where datasheet has thermal_mw, it must equal THERMAL_MW."""
        mismatches = {}
        for cls, data in datasheet.items():
            if cls == "_meta":
                continue
            # datasheet may nest thermal_mw in different sections
            ds_val = None
            for section in data.values():
                if isinstance(section, dict) and "thermal_mw" in section:
                    ds_val = section["thermal_mw"]
                    break
            if ds_val is None:
                continue
            spec_val = THERMAL_MW.get(cls)
            if spec_val is None:
                continue
            if abs(ds_val - spec_val) > 1e-6:
                mismatches[cls] = {"datasheet": ds_val, "specs": spec_val}
        assert not mismatches, (
            f"Datasheet vs THERMAL_MW mismatch: {mismatches}"
        )

    def test_l298n_driver_in_thermal_mw(self):
        """L298N-Driver-class must be present in THERMAL_MW.

        SSOT20: THERMAL_MW is derived from all 43 verified.json classes (incl.
        L298N-Driver, thermal_mw=3000mW), so the former STR15-DRIFT-01 xfail is
        resolved and removed.
        """
        assert "L298N-Driver-class" in THERMAL_MW

    def test_mcu_datasheet_thermal_consistency(self, datasheet):
        """MCU thermal values in datasheet must match THERMAL_MW (tight check)."""
        for cls in _MCU_CLASSES:
            if cls not in datasheet or cls not in THERMAL_MW:
                continue
            ds_val = None
            for section in datasheet[cls].values():
                if isinstance(section, dict) and "thermal_mw" in section:
                    ds_val = section["thermal_mw"]
                    break
            if ds_val is None:
                continue
            assert abs(ds_val - THERMAL_MW[cls]) < 1e-6, (
                f"{cls}: datasheet={ds_val}mW, THERMAL_MW={THERMAL_MW[cls]}mW"
            )
