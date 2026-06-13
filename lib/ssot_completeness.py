"""lib/ssot_completeness.py — PB1: SSOT completeness gate (Path B / D5).

Before a component's circuit is rendered, assert its data/component_datasheet_verified.json
entry has the SSOT fields each derivation path needs. If incomplete (and not WIP-
whitelisted), surface an EXPLICIT, field-named gap — NEVER a silent fallback or generic
box. This is the enforcement mechanism for the design principle
[[feedback_template_best_free_input_no_fallback]]: free input either renders correctly
(complete SSOT) or shows a named warning naming exactly which SSOT field is missing.

Derivation paths checked:
  wiring     — needs ≥1 typed signal pin (pin_layout) + an operating/output voltage
  schematic  — needs identity.full_name + physical length/width (symbol label + size)
  3d         — needs _ui_hints.frontend_shape or extra_ports (3D ports)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent
_SSOT = _ROOT / "data" / "component_datasheet_verified.json"
_cache: Optional[dict] = None


def _load() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(_SSOT.read_text(encoding="utf-8"))
    return _cache


# Voltage keys (D5 C1 fix: include voltage_output_v so USB-5V-class passes, not WIP):
#   operating (logic) / output+nominal (power source) / output_v (USB-5V naming)
_VOLTAGE_KEYS = ("voltage_operating_v", "output_voltage_v",
                 "voltage_nominal_v", "voltage_output_v")
# A pin is a MCU-signal pin only if its direction is a real signal direction
# (power/gnd pins become rails, not signal needs).
_NON_SIGNAL_DIR = {"", "other", "nc", "power", "gnd"}

# Structural/passive classes that legitimately lack a field (exempt, not a gap):
_STRUCT_EXEMPT_VOLTAGE = {"Speaker-class", "Chassis-Car-class"}
_STRUCT_EXEMPT_PINS = {"Chassis-Car-class", "Switch-Generic-class"}

# Component CATEGORIES drive different wiring-completeness checks (one size does NOT
# fit all): power sources provide power (need a PWR pin, not a signal pin); driver-
# mediated loads connect to the MCU through a driver/relay (their MCU pins live on the
# driver class), so they are exempt from the typed-signal-pin requirement.
_POWER_SOURCE_CLASSES = {
    "AC-Adapter-class", "Battery-AA-class", "Battery-4AA-class", "Battery-LiPo-class",
    "USB-5V-class", "USB-Adapter-class",
}
_DRIVER_MEDIATED_CLASSES = {
    "Motor-DC-class",        # via L298N-Driver-class
    "Pump-Water-class",      # via Relay-Module-class
    "Mist-Atomizer-class",   # via onboard/external oscillator driver
    "Mist-Ultrasonic-class",
    "Lighting-LED-Strip-class",  # WS2812B DIN, single control line
}

# Acknowledged work-in-progress: render is blocked + flagged (banner), NOT a hard error.
# Adding here requires a one-line reason; PB0 fills the SSOT then the entry is removed.
WIP_WHITELIST: dict[str, dict[str, str]] = {
    "Button-class":         {"wiring": "mechanical A1/A2/B1/B2 pins not yet typed (logical SIG)"},
    "Switch-class":         {"wiring": "SPDT COM/NO/NC directions not yet typed (logical SIG)"},
    "USB-Adapter-class":    {"wiring": "no PWR+power pin in pin_layout (USB-OUT type=USB)"},
    "Motor-Stepper-class":  {"schematic": "physical length/width pending measurement"},
}

_PATHS = ("wiring", "schematic", "3d")


@dataclass
class Gap:
    path: str       # wiring | schematic | 3d
    field: str      # the exact SSOT field path that is missing/empty
    reason: str     # human-readable (never generic)


@dataclass
class CompletenessResult:
    class_name: str
    ok: bool          # no REAL (non-WIP) gaps → passes the CI gate (complete OR wip)
    complete: bool    # no gaps at all (does not even need a WIP entry)
    is_wip: bool      # blocked-but-flagged: all gaps are WIP-whitelisted
    gaps: list        # list[Gap] — REAL gaps only (excludes WIP-whitelisted)
    wip_paths: list   # paths covered by the WIP whitelist


def _typed_pin_count(spec: dict) -> int:
    n = 0
    for hg in (spec.get("pin_layout") or {}).get("header_groups", []) or []:
        for p in hg.get("pins", []) or []:
            if str(p.get("direction", "")).lower() not in _NON_SIGNAL_DIR:
                n += 1
    return n


def _any_voltage(spec: dict) -> bool:
    el = spec.get("electrical") or {}
    return any(isinstance(el.get(k), (int, float)) for k in _VOLTAGE_KEYS)


def _num_dim(spec: dict, *keys: str) -> bool:
    ph = spec.get("physical") or {}
    return any(isinstance(ph.get(k), (int, float)) and ph[k] > 0 for k in keys)


def _has_pwr_pin(spec: dict) -> bool:
    for hg in (spec.get("pin_layout") or {}).get("header_groups", []) or []:
        for p in hg.get("pins", []) or []:
            if str(p.get("type", "")).upper() == "PWR":
                return True
    return False


def _check_wiring(cls: str, spec: dict) -> list:
    gaps = []
    if cls in _POWER_SOURCE_CLASSES:
        # Power source: completeness = a PWR output pin for power injection (not a signal pin).
        if not _has_pwr_pin(spec):
            gaps.append(Gap("wiring", "pin_layout.header_groups[*].pins[type=PWR]",
                            "power source has no PWR pin — cannot derive power injection"))
        return gaps
    if cls in _DRIVER_MEDIATED_CLASSES:
        # Wired to the MCU through a driver/relay/single DIN; MCU pins live on the driver
        # class, so the signal-pin and voltage checks do not apply to this entry.
        return gaps
    if cls not in _STRUCT_EXEMPT_PINS and _typed_pin_count(spec) < 1:
        gaps.append(Gap("wiring", "pin_layout.header_groups[*].pins[*].direction",
                        "no typed signal pin (need >=1 pin with a real direction) — cannot derive pin needs"))
    if cls not in _STRUCT_EXEMPT_VOLTAGE and not _any_voltage(spec):
        gaps.append(Gap("wiring", "electrical.[" + "|".join(_VOLTAGE_KEYS) + "]",
                        "no operating/output voltage — cannot derive power rail"))
    return gaps


def _check_schematic(cls: str, spec: dict) -> list:
    gaps = []
    idn = (spec.get("identity") or {}).get("full_name")
    if not (isinstance(idn, str) and idn.strip()):
        gaps.append(Gap("schematic", "identity.full_name", "no full_name — symbol label cannot be derived"))
    if not _num_dim(spec, "length_mm", "pcb_length_mm"):
        gaps.append(Gap("schematic", "physical.[length_mm|pcb_length_mm]", "no length — symbol size cannot be derived"))
    if not _num_dim(spec, "width_mm", "pcb_width_mm"):
        gaps.append(Gap("schematic", "physical.[width_mm|pcb_width_mm]", "no width — symbol size cannot be derived"))
    return gaps


def _check_3d(cls: str, spec: dict) -> list:
    ui = spec.get("_ui_hints") or {}
    if not (ui.get("frontend_shape") or ui.get("extra_ports")):
        return [Gap("3d", "_ui_hints.[frontend_shape|extra_ports]",
                    "no frontend_shape/extra_ports — 3D ports cannot be derived")]
    return []


_CHECKS = {"wiring": _check_wiring, "schematic": _check_schematic, "3d": _check_3d}


def check_completeness(class_name: str, paths=_PATHS) -> CompletenessResult:
    """Check a verified.json class for the SSOT fields its render paths need.

    Returns CompletenessResult. Consumer contract:
      not ok            → SSOT_INCOMPLETE error (raise/422/named banner; never fall back)
      ok and is_wip     → blocked-but-flagged WIP banner
      complete          → derive + render
    """
    ssot = _load()
    spec = ssot.get(class_name)
    if spec is None:
        gaps = [Gap(p, "<class>", f"no verified.json entry for {class_name}") for p in paths]
        return CompletenessResult(class_name, ok=False, complete=False, is_wip=False,
                                  gaps=gaps, wip_paths=[])
    all_gaps: list = []
    for p in paths:
        all_gaps.extend(_CHECKS[p](class_name, spec))
    wip = WIP_WHITELIST.get(class_name, {})
    real, wip_hit = [], []
    for g in all_gaps:
        (wip_hit if g.path in wip else real).append(g)
    return CompletenessResult(
        class_name=class_name,
        ok=not real,
        complete=not all_gaps,
        is_wip=(not real) and bool(wip_hit),
        gaps=real,
        wip_paths=sorted({g.path for g in wip_hit}),
    )


def _resolve_class(name: str, ssot: dict) -> Optional[str]:
    """Map an API/component name (class, class-minus-suffix, or wiring short name)
    to a verified.json class key. Returns None for unknown names (not this gate's job)."""
    if name in ssot:
        return name
    if f"{name}-class" in ssot:
        return f"{name}-class"
    try:
        from lib.wiring.validate import _SHORT_TO_CLASS
    except ImportError:
        # Wiring module genuinely absent: unknown short name, not a completeness gap.
        # Any other failure (refactor/syntax regression removing _SHORT_TO_CLASS,
        # AttributeError, etc.) must propagate so an import regression can't
        # silently disable the SSOT completeness gate (false-green).
        return None
    return _SHORT_TO_CLASS.get(name)


def check_components(names: list, paths=("wiring",)) -> list:
    """For a list of component names, return [(name, CompletenessResult)] for those
    that are NOT ok (real incomplete, non-WIP). Used by the API to surface a named
    SSOT_INCOMPLETE error instead of silently rendering a broken circuit."""
    ssot = _load()
    bad = []
    for n in names:
        cls = _resolve_class(n, ssot)
        if cls is None:
            continue  # unknown name — engine handles unknown; not a completeness gap
        r = check_completeness(cls, paths)
        if not r.ok:
            bad.append((n, r))
    return bad


def incomplete_detail(bad: list) -> dict:
    """Structured 422 body for an SSOT_INCOMPLETE error (named gaps, never generic)."""
    return {
        "error": "SSOT_INCOMPLETE",
        "components": [
            {"component": n, "class": r.class_name,
             "missing": [{"path": g.path, "field": g.field, "reason": g.reason} for g in r.gaps]}
            for n, r in bad
        ],
    }


def audit_all(paths=_PATHS) -> dict:
    """Run check_completeness over every component class in verified.json.

    Returns {complete:[...], wip:[...], incomplete:{class: [Gap,...]}}.
    This is the PB0 driver: it lists exactly which SSOT fields to fill.
    """
    ssot = _load()
    classes = [c for c in ssot if not c.startswith("_")]
    out = {"complete": [], "wip": [], "incomplete": {}}
    for c in classes:
        r = check_completeness(c, paths)
        if r.complete:
            out["complete"].append(c)
        elif r.ok and r.is_wip:
            out["wip"].append(c)
        else:
            out["incomplete"][c] = r.gaps
    return out


if __name__ == "__main__":
    import sys
    res = audit_all()
    print(f"[SSOT completeness] {len(res['complete'])} complete / "
          f"{len(res['wip'])} wip / {len(res['incomplete'])} incomplete")
    for c, gaps in sorted(res["incomplete"].items()):
        print(f"\n  {c}:")
        for g in gaps:
            print(f"    [{g.path}] {g.field} — {g.reason}")
    sys.exit(1 if res["incomplete"] else 0)
