"""PB3 (Path B / D2): 7 wiring overrides retired — now derived from verified.json.

template_from_datasheet now honours wiring_hints.mcu_pins + pin_aliases (same fields
pin_needs uses), and the fabricated LDR divider was removed from SSOT, so these 7
components derive their wiring directly. The hand _COMP_OVERRIDES entries are inactive.
The full wiring suite (test_wiring*) is the equivalence gate proving the resolved wiring
for the canned demos is unchanged. Genuine exceptions remain.
"""
from lib.wiring.template_gen import _COMP_OVERRIDES, get_template, template_from_datasheet

_RETIRED = ["Stepper", "LED_Single", "LED_RGB", "Light", "Servo", "SoilMoisture", "MSGEQ7", "Relay"]
_KEPT = ["DCMotor", "Pump", "Speaker", "Button", "Switch"]


def _contract(t):
    if t is None:
        return None

    def pv(e):
        p = getattr(e, "passive", None) or {}
        return (e.comp, getattr(e, "tag", None), getattr(e, "fixed", None),
                p.get("kind"), p.get("value"), p.get("topo"))

    return (t.vcc, tuple(sorted((pv(e) for e in t.extra), key=str)), t.decoupling)


class TestOverridesRetired:
    def test_retired_not_in_overrides(self):
        for s in _RETIRED:
            assert s not in _COMP_OVERRIDES, f"{s} should be retired (now SSOT-derived)"

    def test_genuine_exceptions_kept(self):
        for s in _KEPT:
            assert s in _COMP_OVERRIDES, f"{s} is a genuine exception and must stay"

    def test_retired_get_template_is_pure_derive(self):
        # No override leaks: get_template == template_from_datasheet for retired comps,
        # and both are non-empty (derivation actually produced wiring).
        for s in _RETIRED:
            tmpl = get_template(s)
            assert tmpl is not None and tmpl.extra, f"{s}: derive produced no wiring"
            assert _contract(tmpl) == _contract(template_from_datasheet(s)), \
                f"{s}: get_template diverges from pure derive (override leaked?)"
