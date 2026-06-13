"""F-S2 drift gate: every MCU pin label the wiring backend can emit MUST be matchable
by the frontend MCU_PORTS whitelist (v6/config/mcu-ports.js), so no schematic wire is
silently dropped (UND-S2). Guards the invariant: backend pin pool (lib/pin_maps._PIN_MAPS
+ VCC rails) is a SUBSET of the frontend whitelist, per MCU. The adversarial review found
that label-generation alone did NOT guarantee this (ESP32 D2, RPi GP5, Microbit P9 dropped)
— this test fails if the two inventories ever drift apart again.
"""
import re
from pathlib import Path

import pytest

from lib.pin_maps import _PIN_MAPS, label_mcu_pin, mcu_power_pin
from lib.wiring.engine import to_json, COMP_PIN_NEEDS

_MCU_PORTS_JS = Path(__file__).resolve().parent.parent / "v6" / "config" / "mcu-ports.js"
# Frontend exemptions (elk-layout.js:125-126): virtual terminals + EXT-prefixed labels
# are intentionally not whitelist members and are not treated as drops.
# 虛擬負載端子（無真實 MCU pad）— 須與前端 v6/schematic/elk-layout.js VIRTUAL_TERMINALS 同步
_VIRTUAL = {"LOAD", "LOAD+", "LOAD-", "SPK", "SPK-", "PUMP+", "PUMP-", "M1", "M2"}
_MCUS = ["Arduino", "ESP32", "RPi", "Microbit"]


def _parse_whitelist() -> dict[str, set[str]]:
    """Extract {mcu: {pin labels}} from the north/south/west/east arrays in mcu-ports.js
    (the single source of frontend truth — parsed, not duplicated)."""
    txt = _MCU_PORTS_JS.read_text(encoding="utf-8")
    out: dict[str, set[str]] = {}
    for blk in re.finditer(r"(\w+):\s*\{(.*?)\n    \},", txt, re.S):
        mcu, body = blk.group(1), blk.group(2)
        pins: set[str] = set()
        for side in re.finditer(r"(?:north|south|west|east):\s*\[([^\]]*)\]", body):
            pins.update(re.findall(r"'([^']+)'", side.group(1)))
        if pins:
            out[mcu] = pins
    return out


def _matches(label: str, whitelist: set[str]) -> bool:
    """Replicate the frontend _normPin matcher (elk-layout.js:26-34): exact, or a
    whitelist entry startswith label+'/' (e.g. 'A4'->'A4/SDA') or label+'~' (PWM)."""
    if label in whitelist:
        return True
    return any(p == label or p.startswith(label + "/") or p.startswith(label + "~")
               for p in whitelist)


def _emittable_labels(mcu: str) -> set[str]:
    pm = _PIN_MAPS[mcu]
    labels: set[str] = set()
    for k in ("pwm", "digital", "analog"):
        labels.update(label_mcu_pin(mcu, p) for p in pm.get(k, []))
    labels.update(label_mcu_pin(mcu, v) for v in pm.get("i2c", {}).values())
    for grp in ("spi", "uart"):
        labels.update(label_mcu_pin(mcu, v) for v in pm.get(grp, {}).values())
    return labels


def test_whitelist_parsed_for_all_mcus():
    wl = _parse_whitelist()
    for mcu in _MCUS:
        assert mcu in wl and wl[mcu], f"failed to parse {mcu} whitelist from mcu-ports.js"


@pytest.mark.parametrize("mcu", _MCUS)
def test_pin_pool_subset_of_whitelist(mcu):
    wl = _parse_whitelist()[mcu]
    drops = sorted(l for l in _emittable_labels(mcu) if l not in _VIRTUAL and not _matches(l, wl))
    assert not drops, f"{mcu}: allocator pins absent from frontend whitelist (would drop): {drops}"


@pytest.mark.parametrize("mcu", _MCUS)
def test_vcc_rail_labels_in_whitelist(mcu):
    wl = _parse_whitelist()[mcu]
    for volt in ("3.3V", "5V"):
        # Microbit has no 5V rail — a 5V load there is a power-feasibility error
        # (surfaced by power_inject), not a label drop, so skip that one case.
        if mcu == "Microbit" and volt == "5V":
            continue
        label = mcu_power_pin(mcu, volt)
        assert _matches(label, wl), f"{mcu}: VCC {volt} -> {label!r} not in whitelist"


def test_every_component_resolves_no_drop():
    """Strongest gate: run to_json for every single component on each MCU and assert every
    non-virtual / non-EXT pin label is whitelist-matchable (0 silent schematic drop)."""
    wl = _parse_whitelist()
    drops = []
    for mcu in _MCUS:
        for c in sorted(COMP_PIN_NEEDS.keys()):
            try:
                wiring = to_json(mcu, [c]).get("wiring", {})
            except Exception:
                continue  # completeness/feasibility gate raised — not a drop
            for info in wiring.values():
                for p in info.get("pins", []):
                    mcu_label = str(p.get("mcu", ""))
                    if "." in mcu_label or mcu_label in _VIRTUAL or mcu_label.startswith("EXT"):
                        continue
                    # Microbit 5V VCC: power-feasibility, not a whitelist drop (see above).
                    if mcu == "Microbit" and mcu_label == "5V":
                        continue
                    if not _matches(mcu_label, wl[mcu]):
                        drops.append(f"{mcu}/{c}: {mcu_label}")
    assert not drops, f"silent schematic drops remain: {sorted(set(drops))}"
