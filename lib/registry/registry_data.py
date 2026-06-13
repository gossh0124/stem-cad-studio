"""registry_data.py — COMPONENT_REGISTRY dictionary and PCB/mount application.

Datasheet Sources (RD3):
  Arduino Uno R3  -- Arduino A000066 product page
  ESP32-WROOM-32  -- Espressif ESP32-WROOM-32 datasheet v3.4
  DHT22 (AM2302)  -- Aosong AM2302 datasheet (typical 1.5mA, max 2.5mA)
  HC-SR04         -- Elecfreaks HC-SR04 datasheet (15mA typical)
  HC-SR501        -- MPJA HC-SR501 datasheet (65mA active, 50uA quiescent)
  SG90 Servo      -- TowerPro SG90 datasheet (200mA running, 500mA stall)
  SSD1306 OLED    -- Solomon Systech SSD1306 datasheet (20mA typical)
  WS2812B         -- WorldSemi WS2812B datasheet (60mA/LED max)
  DFPlayer Mini   -- DFRobot DFPlayer Mini wiki (200mA with speaker)
  28BYJ-48        -- Kiatronics 28BYJ-48 datasheet (240mA per phase)
  AMS1117-3.3     -- Advanced Monolithic Systems AMS1117 (800mA max, 50mA safe for MCU pin)
  Micro:bit V2    -- microbit.org hardware spec (30mA typical)
  Raspberry Pi 4B -- Raspberry Pi Foundation datasheet (600mA idle, 1.2A load)
  Physical dimensions: calipered from retail modules +/-0.5mm.

Component entries split by category into _reg_*.py sub-modules.
"""
from __future__ import annotations
from typing import Dict

from .component_spec import ComponentSpec, ConnectorPort, MountingHole

# Sub-module component dicts
from ._reg_mcu import MCU_COMPONENTS
from ._reg_sensors import SENSOR_COMPONENTS
from ._reg_actuators import ACTUATOR_COMPONENTS
from ._reg_display import DISPLAY_COMPONENTS
from ._reg_io import IO_COMPONENTS
from ._reg_power import POWER_COMPONENTS

# Phase A authoritative coordinate source (2026-05-08 triple-source cross-validated)
try:
    from ..pcb import (
        ALL_MODULES as _MODULES,
        derive_connector_ports_generic as _generic_port_specs,
    )
    from ..cad.mounts import ALL_MOUNTS as _MOUNTS
except ImportError:
    from pcb import (
        ALL_MODULES as _MODULES,
        derive_connector_ports_generic as _generic_port_specs,
    )
    from cad.mounts import ALL_MOUNTS as _MOUNTS


def _apply_pcb_module(spec, class_name):
    """Tier 2 module application: overwrite ComponentSpec with PCBSpec data."""
    pcb = _MODULES.get(class_name)
    if pcb is None:
        return spec
    spec.length_mm = pcb.length
    spec.width_mm = pcb.width
    spec.mounting_holes = [MountingHole(x=h.x, y=h.y, diameter=h.diameter)
                           for h in pcb.mounting_holes]
    spec.ports = [ConnectorPort(**s) for s in _generic_port_specs(pcb)]
    return spec


# -- Assemble the unified registry from sub-modules --
COMPONENT_REGISTRY: Dict[str, ComponentSpec] = {
    **MCU_COMPONENTS,
    **SENSOR_COMPONENTS,
    **ACTUATOR_COMPONENTS,
    **DISPLAY_COMPONENTS,
    **IO_COMPONENTS,
    **POWER_COMPONENTS,
}

# -- Tier 1.5: geometry (L/W/H) read-through from verified.json physical (SSOT, B5-geo) --
# Single source = data/component_datasheet_verified.json. registry is no longer authoritative
# for geometry; the per-component L/W/H literals in _reg_*.py are stripped and populated here
# (length_mm/width_mm/height_mm, with pcb_ prefix fallback, matching ssot_completeness /
# test_read_through_invariant._verified_value). Runs BEFORE Tier 2 so lib/pcb (the authoritative
# sub-mm coordinate source) still wins L/W for its 6 modules; height always from verified.json.
# verified.json physical L/W/H gap (Motor-Stepper, pending caliper measurement, WIP) keeps its
# _reg literal — listed in _GEOM_WIP_KEEP and frozen in test_read_through_invariant; any other
# missing class raises (no silent 0 — CLAUDE.md: data gaps must fail loud).
import json as _json
from pathlib import Path as _Path

_VJ_GEOM = _json.loads(
    (_Path(__file__).resolve().parent.parent.parent / "data"
     / "component_datasheet_verified.json").read_text(encoding="utf-8")
)
_GEOM_WIP_KEEP = frozenset({"Motor-Stepper-class"})  # verified.json physical L/W/H gap (WIP)


def _vj_phys_lwh(class_name):
    p = _VJ_GEOM.get(class_name, {}).get("physical", {})
    return (p.get("length_mm") or p.get("pcb_length_mm"),
            p.get("width_mm") or p.get("pcb_width_mm"),
            p.get("height_mm"))


_geom_missing: list = []
for _cn, _spec in COMPONENT_REGISTRY.items():
    if _cn in _GEOM_WIP_KEEP:
        continue  # keep _reg literal (verified.json gap); guarded by #17 frozen inventory
    _L, _W, _H = _vj_phys_lwh(_cn)
    if _L and _W and _H:
        _spec.length_mm, _spec.width_mm, _spec.height_mm = float(_L), float(_W), float(_H)
    else:
        _geom_missing.append(_cn)
if _geom_missing:
    raise ValueError(
        "registry geometry read-through: missing verified.json physical L/W/H "
        "(no silent default): " + ", ".join(sorted(_geom_missing))
    )

# -- Tier 2 module auto-apply PCBSpec (overwrite length/width/mounting_holes/ports) --
for _class_name in _MODULES:
    if _class_name in COMPONENT_REGISTRY:
        _apply_pcb_module(COMPONENT_REGISTRY[_class_name], _class_name)

# -- Tier 4 mechanical mount: mount_kind from lib/cad/mounts.py:ALL_MOUNTS --
for _class_name, (_mount_kind, _label, _builder) in _MOUNTS.items():
    if _class_name in COMPONENT_REGISTRY:
        COMPONENT_REGISTRY[_class_name].mount_kind = _mount_kind

# -- Tier 5: voltage/current/weight/thermal read-through from lib.specs (SSOT) --
# Single source = data/component_datasheet_verified.json -> _component_specs_cache.json.
# registry no longer carries its own electrical/weight/thermal copies; the per-component
# values in _reg_*.py are stripped and populated here, eliminating silent dataclass
# defaults (the old voltage_v=5.0 / thermal_mw=0.0 drift). Missing values raise — no
# silent fallback (CLAUDE.md: data gaps must fail loud).
try:
    from ..specs import VOLTAGE_V as _VOLTAGE_V, POWER_MA as _POWER_MA, \
        WEIGHT_G as _WEIGHT_G, THERMAL_MW as _THERMAL_MW
except ImportError:
    from specs import VOLTAGE_V as _VOLTAGE_V, POWER_MA as _POWER_MA, \
        WEIGHT_G as _WEIGHT_G, THERMAL_MW as _THERMAL_MW

# Supplies record OUTPUT capacity in registry.current_ma (e.g. AC-Adapter 2000 mA),
# which intentionally differs from POWER_MA (consumption = 0). Keep their current_ma.
_SUPPLY_CURRENT_KEEP = frozenset({"AC-Adapter-class", "USB-Adapter-class"})
_specs_missing: list = []
for _cn, _spec in COMPONENT_REGISTRY.items():
    for _field, _table in (("voltage_v", _VOLTAGE_V), ("weight_g", _WEIGHT_G),
                           ("thermal_mw", _THERMAL_MW)):
        if _cn in _table:
            setattr(_spec, _field, float(_table[_cn]))
        else:
            _specs_missing.append(f"{_cn}.{_field}")
    if _cn not in _SUPPLY_CURRENT_KEEP:
        if _cn in _POWER_MA:
            _spec.current_ma = float(_POWER_MA[_cn])
        else:
            _specs_missing.append(f"{_cn}.current_ma")
if _specs_missing:
    raise ValueError(
        "registry SSOT read-through: missing specs-cache values (no silent default): "
        + ", ".join(sorted(_specs_missing))
    )

# -- H21 taxonomy-registry cross-check (fail-fast on misalignment) --
# Runs once at import time. Currently 43/43 aligned; guards against future drift.
try:
    from ..config import TAXONOMY_CONFIG as _TAXONOMY_CONFIG
except ImportError:
    from config import TAXONOMY_CONFIG as _TAXONOMY_CONFIG  # type: ignore[no-redef]

_tax_missing: list = [
    tk
    for types in _TAXONOMY_CONFIG.get("component_taxonomy", {}).values()
    for tk in types
    if tk not in COMPONENT_REGISTRY
]
if _tax_missing:
    raise AssertionError(
        "taxonomy-registry misalignment: taxonomy type_keys not found in"
        " COMPONENT_REGISTRY — " + ", ".join(sorted(_tax_missing))
    )
