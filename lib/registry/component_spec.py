"""component_spec.py — Physical component type definitions.

Contains: MountingHole, ConnectorPort, ComponentSpec dataclasses,
ENCLOSURE_RELATIONS constant, and TAG_VOCAB constants.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Union


# ── U1 Tags (dual-axis vocabulary) ─────────────────────────────────
# axis 1 = "MCU interface" -- closed vocabulary
# axis 2 = "what it does" -- open with prefix constraints
TAG_VOCAB_AXIS1: FrozenSet[str] = frozenset({
    # Communication bus
    "bus:i2c", "bus:spi", "bus:uart", "bus:1wire", "bus:rf", "bus:usb",
    # Single-wire GPIO control (by signal type)
    "gpio:digital", "gpio:pwm", "gpio:analog", "gpio:pulse",
    # Passive / mechanical / no MCU signal protocol
    "iface:passive",
})

# axis 2 open vocabulary, but prefix-constrained
TAG_VOCAB_AXIS2_PREFIXES: FrozenSet[str] = frozenset({
    "measure:",   # sensing
    "display:",   # display
    "actuate:",   # mechanical output
    "light:",     # lighting
    "sound:",     # sound
    "control:",   # user input
    "mcu:",       # controller board
    "power:",     # power supply
    "structure:", # structural parts
})


# Enclosure relation enum
# internal   = fully enclosed, gets individual shell
# breadboard = inside shell on mainboard/breadboard, skip individual shell
# panel      = panel-mount with cutout on shell face
# external   = fully external, only wire hole on shell wall
# embedded   = sunk into structural body (tank/chassis)
ENCLOSURE_RELATIONS: FrozenSet[str] = frozenset({
    "internal", "breadboard", "panel", "external", "embedded",
})


@dataclass(frozen=True)
class MountingHole:
    """PCB mounting hole position."""
    x: float       # mm, relative to component bottom-left
    y: float       # mm
    diameter: float  # mm


@dataclass(frozen=True)
class ConnectorPort:
    """Component electrical interface definition (for enclosure wall cutouts)."""
    name: str           # e.g. 'USB-B', 'VCC', 'TRIG'
    port_type: str      # 'USB'|'GPIO'|'I2C'|'UART'|'SPI'|'PWR'|'GND'|'ANALOG'|'AUDIO'|'EDGE'|'OTHER'
    x: float            # mm, port center X (relative to component bottom-left)
    y: float            # mm, port center Y
    width: float = 3.0  # mm, opening width
    height: float = 3.0 # mm, opening height
    side: str = 'face'  # 'left'|'right'|'top'|'bottom'|'face'
    z: float = 0.0      # mm, port bottom height above component base


@dataclass
class ComponentSpec:
    """Physical specification of a single component."""
    name: str
    # geometry L/W/H 由 registry_data Tier 1.5 從 verified.json physical 讀穿覆寫(B5-geo);
    # _reg_*.py 不再帶字面值。預設 0.0 僅為建構佔位 —— registry build 對 verified.json 缺值的
    # class 會 raise(no-silent-fallback),不會出貨 0;Motor-Stepper(WIP gap)仍保留 _reg 字面值。
    length_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    class_name: str = ""
    mounting_holes: List[MountingHole] = field(default_factory=list)
    ports: List[ConnectorPort] = field(default_factory=list)
    enclosure_relation: str = "internal"
    skip_enclosure: bool = False
    wire_clearance_mm: float = 8.0
    voltage_v: float = 5.0
    current_ma: float = 50.0
    weight_g: float = 10.0
    thermal_mw: float = 0.0
    mount_kind: str = ''
    tags: List[str] = field(default_factory=list)
    # v3: structured host metadata for embedded components
    # Accepts str (v2 legacy) or dict (v3 schema); only meaningful
    # when enclosure_relation == "embedded"
    host_structure: Optional[Union[str, dict]] = None

    def __post_init__(self):
        if self.enclosure_relation not in ENCLOSURE_RELATIONS:
            raise ValueError(
                f"enclosure_relation must be one of {sorted(ENCLOSURE_RELATIONS)}, "
                f"got {self.enclosure_relation!r} (class_name={self.class_name})"
            )
        # Bidirectional sync: ensure skip_enclosure is consistent with enclosure_relation
        if self.enclosure_relation != "internal":
            self.skip_enclosure = True
        elif self.skip_enclosure:
            self.enclosure_relation = "external"
        # v3: default host_structure for embedded components without one
        if self.enclosure_relation == "embedded" and self.host_structure is None:
            import warnings
            warnings.warn(
                f"{self.class_name}: embedded component has no host_structure; "
                "defaulting to 'external_body'. Upgrade to v3 dict schema.",
                stacklevel=2,
            )
            object.__setattr__(self, "host_structure", "external_body")

    def footprint_area(self) -> float:
        """Return footprint area (mm^2)."""
        return self.length_mm * self.width_mm

    def to_dict(self) -> dict:
        """Serialize to dict format expected by phase handlers."""
        d = {
            "length_mm": self.length_mm,
            "width_mm":  self.width_mm,
            "height_mm": self.height_mm,
            "voltage_v":  self.voltage_v,
            "current_ma": self.current_ma,
            "weight_g":   self.weight_g,
            "thermal_mw": self.thermal_mw,
            "wire_clearance_mm": self.wire_clearance_mm,
            "enclosure_relation": self.enclosure_relation,
            "skip_enclosure": self.skip_enclosure,
            "mounting_holes_count": len(self.mounting_holes),
            "tags": list(self.tags),
            "connector_ports": [
                {
                    "name": p.name,
                    "side": p.side,
                    "z_height": p.z,
                    "width": p.width,
                    "height": p.height,
                    "x": p.x,
                    "y": p.y,
                }
                for p in self.ports
            ],
        }
        if self.host_structure is not None:
            d["host_structure"] = self.host_structure
        return d
