"""PB2 (Path B / D1): COMP_PIN_NEEDS is DERIVED from verified.json (hand table retired).

The runtime COMP_PIN_NEEDS is built by pin_needs_from_datasheet from pin_layout +
wiring_hints (mcu_pins/pwm_override/pin_aliases) + thin overrides. This drift-guard
asserts the derived table still equals the frozen hand golden (_PIN_NEEDS_GOLDEN) by
(tag, type) and key set — so the retire introduced no regression and future SSOT edits
that would change the wiring contract are caught. Color is a general UI rule, not compared.
"""
from lib.wiring.wiring_data import COMP_PIN_NEEDS, _PIN_NEEDS_GOLDEN


def _sig(needs):
    return sorted((n.tag, n.type) for n in needs)


class TestPinNeedsDerive:
    def test_derived_key_set_matches_golden(self):
        extra = sorted(set(COMP_PIN_NEEDS) - set(_PIN_NEEDS_GOLDEN))
        missing = sorted(set(_PIN_NEEDS_GOLDEN) - set(COMP_PIN_NEEDS))
        assert not extra and not missing, f"extra={extra} missing={missing}"

    def test_derived_equals_golden_by_tag_type(self):
        mism = {
            s: {"golden": _sig(_PIN_NEEDS_GOLDEN[s]), "derived": _sig(COMP_PIN_NEEDS[s])}
            for s in _PIN_NEEDS_GOLDEN
            if s in COMP_PIN_NEEDS and _sig(COMP_PIN_NEEDS[s]) != _sig(_PIN_NEEDS_GOLDEN[s])
        }
        assert not mism, f"derived != golden: {mism}"
