"""Shared data structures and constants for assembly_solver sub-modules."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

_log = logging.getLogger("cadhllm.assembly_solver")

_THERMAL_HOT_MW = 500
THERMAL_TIER_LOW = 500
THERMAL_TIER_MID = 1500
THERMAL_TIER_HIGH = 3000
_VENT_THRESHOLD_MW = THERMAL_TIER_MID
_H_CONV_W_M2K = 7.0
_DT_MAX_C = 40.0
_AMBIENT_C = 25.0
_INFLUENCE_RADIUS_CAP_MM = 40.0
_ACTIVE_FAN_CFM = 5.0
_COLOR_LUT_DEFAULT = [
    {"temp_c": 25, "color": "#0000ff"},
    {"temp_c": 35, "color": "#00ff00"},
    {"temp_c": 50, "color": "#ff0000"},
]
_GRID_RES_MM = 2
_CLEARANCE_MM = 3.0
_WIRE_SIGNAL_COLORS = {
    "power": "#ff4444", "gnd": "#333333",
    "analog": "#ffaa00", "digital": "#44cc44",
    "i2c": "#44ddff", "spi": "#dd44ff", "pwm": "#44cc44",
    "uart": "#44ddff",
}
_LAYER_Z_OFFSET = {
    "power": 2.0, "gnd": 4.0, "digital": 6.0, "pwm": 6.0,
    "analog": 8.0, "uart": 8.0, "i2c": 10.0, "spi": 10.0,
}
_WIRE_OCCUPY_MARGIN = 1


@dataclass
class _Comp:
    type: str
    role: str
    L: float
    W: float
    H: float
    weight_g: float
    thermal_mw: Optional[float]
    ports: list
    enclosure_relation: str = "internal"
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    zone: str = ""
    face_out: str = ""
    host_structure: Optional[Union[str, dict]] = None


@dataclass
class _Decision:
    step: str
    principle: str
    description: str
    formula: str = ""
    six_e_stage: str = "engineer"
