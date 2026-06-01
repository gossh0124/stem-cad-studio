"""
firmware — Firmware code generation package (SSOT for UI + Phase III).

Backward-compatible re-exports: `from lib.firmware import to_json` still works.
"""
from __future__ import annotations

from ..wiring import allocate_pins
from .templates import (
    REACTION_RULES,
    OUTPUT_FALLBACK,
    TEST_TEMPLATES,
    match_reactions,
    stem_header_lines,
    _wrap_text,
)
from .arduino import _gen_arduino
from .rpi import _gen_rpi
from .microbit import _gen_microbit


def generate_firmware(brain: str, power: str,
                      outputs: list[str], sensors: list[str],
                      project_name: str = "", plan: str = "") -> dict:
    brain_key = brain if brain != "auto" else "Arduino"
    if brain_key == "RPi":
        return {"code": _gen_rpi(outputs, sensors, power, project_name, plan),
                "lang": "python", "ext": ".py"}
    if brain_key == "Microbit":
        return {"code": _gen_microbit(outputs, sensors, power, project_name, plan),
                "lang": "python", "ext": ".py"}
    return {"code": _gen_arduino(brain_key, outputs, sensors, power, project_name, plan),
            "lang": "cpp", "ext": ".ino"}


def generate_test_code(brain: str, comps: list[str], *, _alloc_result: dict | None = None) -> dict[str, dict]:
    from ..wiring import normalize_comp
    brain_key = brain if brain != "auto" else "Arduino"
    norm_comps = [normalize_comp(c) for c in comps]
    result = _alloc_result or allocate_pins(brain_key, norm_comps)
    alloc = result["allocation"]

    codes: dict[str, dict] = {}
    for comp in norm_comps:
        gen = TEST_TEMPLATES.get(comp)
        if gen:
            pin_map = alloc.get(comp, {})
            codes[comp] = gen(pin_map)
    return codes


def to_json(brain: str, power: str,
            outputs: list[str], sensors: list[str],
            project_name: str = "", plan: str = "") -> dict:
    brain_key = brain if brain != "auto" else "Arduino"
    all_comps = outputs + sensors
    alloc = allocate_pins(brain_key, all_comps)
    fw = generate_firmware(brain, power, outputs, sensors, project_name, plan)
    tests = generate_test_code(brain, all_comps, _alloc_result=alloc)
    return {
        "firmware": fw,
        "test_codes": {k: v for k, v in tests.items()},
    }


__all__ = [
    "generate_firmware",
    "generate_test_code",
    "to_json",
    "REACTION_RULES",
    "OUTPUT_FALLBACK",
    "TEST_TEMPLATES",
    "match_reactions",
]
