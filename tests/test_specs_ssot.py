"""tests/test_specs_ssot.py — SSOT20: full voltage/weight/thermal/current unification gate.

Closes the gaps left by the per-field tests (test_weight_g, test_thermal_mw,
test_power_ma_coverage):
  - VOLTAGE has no dedicated test — covered here (registry == specs == verified).
  - The combined cache (data/_component_specs_cache.json) must not drift from
    verified.json — asserted by re-deriving and comparing (regen consistency).
  - helpers reads through specs (identity), no third hardcoded copy.
  - No silent dataclass defaults: every registry class resolves a real SSOT value.

Single source of truth: data/component_datasheet_verified.json
  -> lib.specs combined cache -> registry (Tier-5 read-through) / helpers.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib import specs as S
from lib.registry import COMPONENT_REGISTRY

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VERIFIED_PATH = os.path.join(_ROOT, "data", "component_datasheet_verified.json")
_CACHE_PATH = os.path.join(_ROOT, "data", "_component_specs_cache.json")

# Supplies record OUTPUT capacity in registry.current_ma (intentionally != POWER_MA=0).
_SUPPLY_CURRENT_KEEP = frozenset({"AC-Adapter-class", "USB-Adapter-class"})
# Passive/structural parts with no meaningful DC operating voltage (kept in _fallback).
_VOLTAGE_FALLBACK_EXPECTED = frozenset({"Speaker-class", "Chassis-Car-class"})
_VOLTAGE_KEYS = ("voltage_operating_v", "voltage_output_v", "output_voltage_v", "voltage_nominal_v")


@pytest.fixture(scope="module")
def verified():
    with open(_VERIFIED_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cache():
    with open(_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _vj_voltage(elec: dict):
    for k in _VOLTAGE_KEYS:
        if k in elec:
            return float(elec[k])
    return None


def _vj_installed_weight(phys: dict):
    if "weight_with_batteries_g" in phys:
        return float(phys["weight_with_batteries_g"])
    if "weight_g" in phys:
        return float(phys["weight_g"])
    return None


# ── 1. Cache <-> verified.json regen consistency (no stale cache) ──────────────

class TestCacheRegenConsistency:
    def test_cache_ssot_sections_match_verified(self, verified):
        """Re-deriving from verified.json must reproduce the cache SSOT sections
        exactly — otherwise the committed cache is stale (data drift)."""
        derived = S._derive_specs_from_verified()
        raw = S._load_specs_cache()
        for section in ("voltage_v", "weight_g", "thermal_mw", "power_ma"):
            assert raw.get(section) == derived[section], (
                f"cache section '{section}' is stale vs verified.json; "
                f"run _rebuild_specs_cache(). "
                f"diff keys: "
                f"{set(raw.get(section, {})) ^ set(derived[section])}"
            )

    def test_rebuild_is_idempotent(self):
        """_rebuild_specs_cache(write=False) must equal the on-disk cache."""
        rebuilt = S._rebuild_specs_cache(write=False)
        raw = S._load_specs_cache()
        for section in ("voltage_v", "weight_g", "thermal_mw", "power_ma"):
            assert rebuilt[section] == raw[section], f"section {section} not idempotent"


# ── 2. No silent defaults: every registry class resolves a real SSOT value ─────

class TestNoSilentDefaults:
    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_voltage_present(self, cn):
        assert cn in S.VOLTAGE_V, f"{cn} missing from VOLTAGE_V (would hit dataclass default 5.0)"

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_weight_present(self, cn):
        assert cn in S.WEIGHT_G, f"{cn} missing from WEIGHT_G"

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_thermal_present(self, cn):
        assert cn in S.THERMAL_MW, f"{cn} missing from THERMAL_MW (would hit default 0.0)"

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_current_present(self, cn):
        assert cn in S.POWER_MA, f"{cn} missing from POWER_MA"


# ── 3. registry read-through: registry == specs (the unification) ─────────────

class TestRegistryReadThrough:
    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_voltage_matches_specs(self, cn):
        assert COMPONENT_REGISTRY[cn].voltage_v == S.VOLTAGE_V[cn], (
            f"{cn}: registry.voltage_v={COMPONENT_REGISTRY[cn].voltage_v} "
            f"!= specs.VOLTAGE_V={S.VOLTAGE_V[cn]}"
        )

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_weight_matches_specs(self, cn):
        assert COMPONENT_REGISTRY[cn].weight_g == S.WEIGHT_G[cn]

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_thermal_matches_specs(self, cn):
        assert COMPONENT_REGISTRY[cn].thermal_mw == S.THERMAL_MW[cn]

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_registry_current_matches_specs(self, cn):
        """Non-supply registry.current_ma == POWER_MA; supplies keep output capacity."""
        if cn in _SUPPLY_CURRENT_KEEP:
            assert COMPONENT_REGISTRY[cn].current_ma > 0, (
                f"{cn} should retain a positive output-capacity current_ma"
            )
        else:
            assert COMPONENT_REGISTRY[cn].current_ma == S.POWER_MA[cn]


# ── 4. specs <-> verified.json (the authoritative values) ─────────────────────

class TestSpecsMatchVerified:
    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_voltage_matches_verified(self, cn, verified):
        """Where verified.json carries a voltage, specs.VOLTAGE_V must equal it."""
        if cn not in verified:
            pytest.skip(f"{cn} not in verified.json")
        vjv = _vj_voltage(verified[cn].get("electrical", {}))
        if vjv is None:
            assert cn in _VOLTAGE_FALLBACK_EXPECTED, (
                f"{cn} has no voltage in verified.json but is not a known passive fallback"
            )
            return
        assert S.VOLTAGE_V[cn] == vjv, (
            f"{cn}: specs.VOLTAGE_V={S.VOLTAGE_V[cn]} != verified={vjv}"
        )

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_weight_matches_verified_installed(self, cn, verified):
        if cn not in verified:
            pytest.skip(f"{cn} not in verified.json")
        w = _vj_installed_weight(verified[cn].get("physical", {}))
        assert w is not None and S.WEIGHT_G[cn] == w, (
            f"{cn}: specs.WEIGHT_G={S.WEIGHT_G.get(cn)} != verified as-installed={w}"
        )

    @pytest.mark.parametrize("cn", sorted(COMPONENT_REGISTRY))
    def test_thermal_matches_verified(self, cn, verified):
        if cn not in verified:
            pytest.skip(f"{cn} not in verified.json")
        elec = verified[cn].get("electrical", {})
        if "thermal_mw" not in elec:
            pytest.skip(f"{cn} no thermal_mw in verified.json")
        assert S.THERMAL_MW[cn] == float(elec["thermal_mw"])


# ── 5. helpers read-through (no third hardcoded copy) ─────────────────────────

class TestHelpersReadThrough:
    @pytest.fixture(scope="class")
    def helpers(self):
        training_dir = os.path.join(_ROOT, "training")
        if training_dir not in sys.path:
            sys.path.insert(0, training_dir)
        import data_generator_b_helpers as h  # noqa: PLC0415
        return h

    def test_helpers_weight_is_specs(self, helpers):
        assert helpers.WEIGHT_G == S.WEIGHT_G

    def test_helpers_thermal_is_specs(self, helpers):
        assert helpers.THERMAL_MW == S.THERMAL_MW

    def test_helpers_current_is_power_ma(self, helpers):
        assert helpers.CURRENT_MA == S.POWER_MA


# ── 6. Voltage sanity + known corrections + passive fallback ──────────────────

class TestVoltageSanity:
    @pytest.mark.parametrize("cn", sorted(S.VOLTAGE_V))
    def test_voltage_in_reasonable_range(self, cn):
        v = S.VOLTAGE_V[cn]
        assert 1.8 <= v <= 48.0, f"{cn}: voltage {v}V outside [1.8, 48]V"

    def test_passive_voltage_from_fallback(self, cache):
        """Speaker / Chassis voltage must come from cache _fallback, not SSOT section."""
        ssot_v = cache.get("voltage_v", {})
        fb_v = cache.get("_fallback", {}).get("voltage_v", {})
        for cn in _VOLTAGE_FALLBACK_EXPECTED:
            assert cn not in ssot_v, f"{cn} should not be in SSOT voltage section"
            assert cn in fb_v, f"{cn} should be in voltage _fallback"

    def test_known_voltage_corrections(self):
        """Regression guard for the real errors SSOT20 fixed."""
        assert S.VOLTAGE_V["Sensor-PIR-class"] == 5.0, "HC-SR501 supply is 5V (not 3.3 output level)"
        assert S.VOLTAGE_V["L298N-Driver-class"] == 5.0, "L298N logic is 5V (not 7.0 motor-supply min)"
        assert S.VOLTAGE_V["Sensor-SoilMoisture-class"] == 3.3

    def test_battery_aa_installed_weight(self):
        """Battery-AA weight is as-installed (56g incl. 2×AA), not 48 nor 8."""
        assert S.WEIGHT_G["Battery-AA-class"] == 56.0


# ── 7. Provenance audit: added voltage/thermal must be sourced ─────────────────

class TestProvenance:
    def test_added_fields_have_provenance(self, verified):
        """Every voltage/thermal value added to verified.json must record sources."""
        prov = verified.get("_ssot20_research_provenance", {})
        assert prov, "_ssot20_research_provenance block missing"
        missing = []
        for cn, entry in prov.items():
            for field, rec in entry.items():
                srcs = rec.get("sources", [])
                if len([s for s in srcs if "http" in s or "n/a" in s]) < 3:
                    missing.append(f"{cn}.{field}")
        assert not missing, f"provenance entries with <3 sources: {missing}"
