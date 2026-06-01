"""tests/test_power_ma_coverage.py — STR12: POWER_MA 全量交叉驗證。

Cross-validates specs.POWER_MA (42 entries) against:
  - lib/registry.COMPONENT_REGISTRY (.current_ma field)
  - data/component_datasheet_verified.json (.electrical.current_typ_ma)
  - training/data_generator_b_helpers.CURRENT_MA (training data drift detection)
  - specs.POWER_BUDGET_MA / STALL_MA structural invariants
"""
import json
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.specs import POWER_MA, POWER_BUDGET_MA, STALL_MA
from lib.registry import COMPONENT_REGISTRY

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATASHEET_PATH = os.path.join(_ROOT, "data", "component_datasheet_verified.json")

# Components present in POWER_MA but intentionally absent from COMPONENT_REGISTRY
# (planning-level specs not yet modelled as physical components)
_REGISTRY_EXEMPT = frozenset({"Arduino-Nano-class", "ESP8266-class"})

# Supply components: act as power sources, so current_ma in registry reflects
# output capacity, not consumption — POWER_MA correctly records 0.0 for them.
_SUPPLY_CLASSES = frozenset(
    POWER_BUDGET_MA.keys()
)

# SSOT20: helpers.CURRENT_MA now imports specs.POWER_MA directly (read-through),
# so drift is structurally impossible — the former _KNOWN_DRIFT xfail allowlist
# (which institutionalised real bugs like TempHumid 2.5 vs 1.5, Button 0.0 vs 0.5)
# has been removed; every entry must now assert exact equality.

# ── Helpers ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def datasheet():
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_helpers_current_ma():
    """Import training helpers CURRENT_MA with explicit path insertion."""
    training_dir = os.path.join(_ROOT, "training")
    if training_dir not in sys.path:
        sys.path.insert(0, training_dir)
    from data_generator_b_helpers import CURRENT_MA  # noqa: PLC0415
    return CURRENT_MA


# ── 1. TestPowerMaCompleteness ─────────────────────────────────────────────

class TestPowerMaCompleteness:
    def test_power_ma_count_exact(self):
        """POWER_MA must contain exactly 45 entries — accidental add/remove detection."""
        assert len(POWER_MA) == 45, (
            f"Expected 45 entries, got {len(POWER_MA)}. "
            f"Keys: {sorted(POWER_MA)}"
        )

    def test_all_power_ma_in_registry(self):
        """Every POWER_MA key must exist in COMPONENT_REGISTRY (exempt list allowed)."""
        missing = {
            cn for cn in POWER_MA
            if cn not in COMPONENT_REGISTRY and cn not in _REGISTRY_EXEMPT
        }
        assert missing == set(), (
            f"POWER_MA keys missing from COMPONENT_REGISTRY (not in exempt list): {missing}"
        )

    def test_all_registry_in_power_ma(self):
        """Every COMPONENT_REGISTRY key must exist in POWER_MA.

        Supply components (AC-Adapter, USB-Adapter) consume 0 mA and are
        correctly covered by POWER_MA with 0.0 — they must still be present.
        """
        missing = {cn for cn in COMPONENT_REGISTRY if cn not in POWER_MA}
        assert missing == set(), (
            f"COMPONENT_REGISTRY keys missing from POWER_MA: {missing}"
        )


# ── 2. TestPowerMaValueAlignment ───────────────────────────────────────────

class TestPowerMaValueAlignment:
    def test_no_negative_values(self):
        """All POWER_MA entries must be non-negative."""
        negatives = {cn: v for cn, v in POWER_MA.items() if v < 0}
        assert negatives == {}, f"Negative mA values found: {negatives}"

    @pytest.mark.parametrize("cn", sorted(POWER_MA))
    def test_registry_matches_specs(self, cn):
        """registry.current_ma must equal POWER_MA for every non-exempt entry.

        Supply components are skipped: their registry current_ma records output
        capacity (e.g. 2000 mA for AC-Adapter), while POWER_MA records 0
        (they supply, not consume).
        """
        if cn in _REGISTRY_EXEMPT:
            pytest.skip(f"{cn} not in COMPONENT_REGISTRY (planning-only entry)")
        if cn in _SUPPLY_CLASSES:
            pytest.skip(f"{cn} is a supply source — registry current_ma is output capacity")
        spec = COMPONENT_REGISTRY[cn]
        assert spec.current_ma == POWER_MA[cn], (
            f"{cn}: registry.current_ma={spec.current_ma} != POWER_MA={POWER_MA[cn]}"
        )

    @pytest.mark.parametrize("cn", sorted(POWER_MA))
    def test_datasheet_matches_specs(self, cn, datasheet):
        """POWER_MA must equal datasheet current_typ_ma for every entry present in JSON."""
        if cn not in datasheet:
            pytest.skip(f"{cn} not in datasheet JSON")
        electrical = datasheet[cn].get("electrical", {})
        if "current_typ_ma" not in electrical:
            pytest.skip(f"{cn} has no current_typ_ma in datasheet electrical section")
        ds_val = electrical["current_typ_ma"]
        assert POWER_MA[cn] == ds_val, (
            f"{cn}: POWER_MA={POWER_MA[cn]} != datasheet.current_typ_ma={ds_val}"
        )


# ── 3. TestHelpersCrossCheck ────────────────────────────────────────────────

class TestHelpersCrossCheck:
    @pytest.fixture(scope="class")
    def helpers_ma(self):
        return _load_helpers_current_ma()

    def test_helpers_no_extra_keys(self, helpers_ma):
        """helpers.CURRENT_MA must not contain keys absent from specs.POWER_MA."""
        extra = {cn for cn in helpers_ma if cn not in POWER_MA}
        assert extra == set(), (
            f"helpers.CURRENT_MA has keys not in specs.POWER_MA: {extra}"
        )

    @pytest.mark.parametrize("cn", sorted(
        set(__import__("lib.specs", fromlist=["POWER_MA"]).POWER_MA) &
        set(_load_helpers_current_ma())
    ))
    def test_helpers_current_ma_matches_specs(self, cn, helpers_ma):
        """helpers.CURRENT_MA[cn] must equal specs.POWER_MA[cn] (SSOT20 read-through)."""
        assert helpers_ma[cn] == POWER_MA[cn], (
            f"{cn}: helpers={helpers_ma[cn]} != specs={POWER_MA[cn]}"
        )


# ── 4. TestPowerBudgets ────────────────────────────────────────────────────

class TestPowerBudgets:
    def test_all_power_budget_keys_are_supply(self):
        """Every key in POWER_BUDGET_MA must be a supply component (POWER_MA == 0.0)."""
        non_supply = {
            cn for cn in POWER_BUDGET_MA
            if POWER_MA.get(cn, -1) != 0.0
        }
        assert non_supply == set(), (
            f"POWER_BUDGET_MA keys with non-zero POWER_MA (not supply components): "
            f"{non_supply}"
        )

    def test_stall_ma_subset_of_power_ma(self):
        """All STALL_MA keys must exist in POWER_MA."""
        missing = {cn for cn in STALL_MA if cn not in POWER_MA}
        assert missing == set(), (
            f"STALL_MA keys missing from POWER_MA: {missing}"
        )

    @pytest.mark.parametrize("cn", sorted(STALL_MA))
    def test_stall_exceeds_typical(self, cn):
        """STALL_MA[cn] must be strictly greater than POWER_MA[cn] (typical)."""
        assert STALL_MA[cn] > POWER_MA[cn], (
            f"{cn}: STALL_MA={STALL_MA[cn]} must exceed POWER_MA={POWER_MA[cn]}"
        )
