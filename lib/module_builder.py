"""lib/module_builder.py — Assembly V3 Component Module builder.

Core concept: every electronic component is wrapped into a *ComponentModule*
containing PCB + optional shell (base/lid) + optional mount.  Shell cutouts
become wiring *ShellPorts*.

Coordinate system: module-local, PCB bottom-left = origin, X right, Y up.
Shell wall thickness expands outward (does not shift PCB origin).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports from project SSOT layers
# ---------------------------------------------------------------------------
try:
    from .registry import COMPONENT_REGISTRY, ComponentSpec, ConnectorPort
    from .pcb import PCB_REGISTRY
    from .pcb._types import PCBSpec, NamedPin, HeaderGroup
except ImportError:
    from registry import COMPONENT_REGISTRY, ComponentSpec, ConnectorPort  # type: ignore[no-redef]
    from pcb import PCB_REGISTRY  # type: ignore[no-redef]
    from pcb._types import PCBSpec, NamedPin, HeaderGroup  # type: ignore[no-redef]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SHELLS_DIR = Path(__file__).resolve().parent.parent / "shells"

# Default wall thickness (mm) when meta.json is unavailable
_DEFAULT_WALL_THICKNESS = 2.0

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Pin3D:
    """PCB pin in module-local 3-D coordinates."""
    name: str
    x: float
    y: float
    z: float
    function: str       # 'GPIO'|'ANALOG'|'POWER'|'GND'|'I2C'|'SPI'|'UART'|'NC'
    arduino_pin: str    # Arduino IDE naming (D7 / A0 / +5V / ...)


@dataclass
class ShellPort:
    """Shell opening -- wiring start / end point."""
    name: str
    port_type: str      # 'PWR'|'GPIO'|'ANALOG'|'I2C'|'SPI'|'USB'|'OTHER'
    side: str           # 'left'|'right'|'top'|'bottom'|'face'
    x: float
    y: float
    z: float
    width: float
    height: float
    pins: List[str]     # mapped PCB pin names


@dataclass
class MeshRef:
    """Reference to a 3-D model asset."""
    variant: str        # 'pcb_body'|'base'|'lid'|'mount'
    url: str            # e.g. '/api/shells/Arduino-Uno-class/stl?variant=pcb_body'
    format: str         # 'glb'|'stl'


@dataclass
class ComponentModule:
    """Fully-packaged component module."""
    comp_type: str
    role: str
    class_name: str

    # geometry (outer dimensions incl. shell wall)
    length: float
    width: float
    height: float
    weight_g: float
    thermal_mw: float

    enclosure_relation: str     # internal, breadboard, panel, external, embedded

    pins: List[Pin3D]           = field(default_factory=list)
    shell_ports: List[ShellPort] = field(default_factory=list)
    meshes: List[MeshRef]       = field(default_factory=list)
    assembly_steps: List[str]   = field(default_factory=list)
    host_structure: Optional[dict] = None     # for embedded modules (water tank etc.)

    def to_dict(self) -> dict:
        """Serialise for JSON transport / front-end consumption."""
        return {
            "comp_type": self.comp_type,
            "role": self.role,
            "class_name": self.class_name,
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "weight_g": self.weight_g,
            "thermal_mw": self.thermal_mw,
            "enclosure_relation": self.enclosure_relation,
            "pins": [
                {"name": p.name, "x": p.x, "y": p.y, "z": p.z,
                 "function": p.function, "arduino_pin": p.arduino_pin}
                for p in self.pins
            ],
            "shell_ports": [
                {"name": sp.name, "port_type": sp.port_type, "side": sp.side,
                 "x": sp.x, "y": sp.y, "z": sp.z,
                 "width": sp.width, "height": sp.height, "pins": sp.pins}
                for sp in self.shell_ports
            ],
            "meshes": [
                {"variant": m.variant, "url": m.url, "format": m.format}
                for m in self.meshes
            ],
            "assembly_steps": list(self.assembly_steps),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def _read_shell_meta(class_name: str) -> Optional[dict]:
    """Read shells/{class_name}/meta.json if it exists. Cached per class_name."""
    meta_path = _SHELLS_DIR / class_name / "meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to read %s", meta_path)
        return None


def _wall_thickness(class_name: str) -> float:
    """Return wall thickness (mm) from shell meta, or default."""
    meta = _read_shell_meta(class_name)
    if meta and "spec_dict" in meta:
        return float(meta["spec_dict"].get("wall", _DEFAULT_WALL_THICKNESS))
    return _DEFAULT_WALL_THICKNESS


def _has_shell(class_name: str) -> bool:
    """True if class_name has a base+lid shell (Tier 1 / two_piece)."""
    meta = _read_shell_meta(class_name)
    if meta is None:
        return False
    return meta.get("kind") == "two_piece"


def _has_mount(class_name: str) -> bool:
    """True if class_name has a mount bracket."""
    meta = _read_shell_meta(class_name)
    if meta is None:
        return False
    return meta.get("kind") == "mount"


# ---------------------------------------------------------------------------
# Pin3D conversion
# ---------------------------------------------------------------------------

def _pcb_pins_to_pin3d(
    pcb_spec: PCBSpec,
    wall_thickness: float = 0.0,
) -> List[Pin3D]:
    """Convert PCBSpec.pins (NamedPin) to module-local Pin3D.

    z = pcb_thickness + wall_thickness (bottom wall lifts PCB).
    """
    z = pcb_spec.pcb_thickness + wall_thickness
    return [
        Pin3D(
            name=p.name,
            x=p.x,
            y=p.y,
            z=z,
            function=p.function or "NC",
            arduino_pin=p.arduino_pin or p.name,
        )
        for p in pcb_spec.pins
    ]


# ---------------------------------------------------------------------------
# ShellPort derivation
# ---------------------------------------------------------------------------

def _build_header_pin_map(
    pcb_spec: PCBSpec,
) -> Dict[str, List[str]]:
    """Map header_group.name -> list of pin names via pin_indices."""
    idx_map = pcb_spec.pin_index_map()
    result: Dict[str, List[str]] = {}
    for grp in pcb_spec.header_groups:
        names = [idx_map[i].name for i in grp.pin_indices if i in idx_map]
        result[grp.name] = names
    return result


def _derive_shell_ports(
    comp_spec: ComponentSpec,
    pcb_spec: Optional[PCBSpec],
    wall_thickness: float = 0.0,
) -> List[ShellPort]:
    """Derive ShellPorts from ConnectorPort + HeaderGroup.

    Strategy by tier:
      Tier 1 (has shell):  ConnectorPort position + wall offset -> shell wall 3D
      Tier 2 (bare PCB):   HeaderGroup slot center -> direct port
      Tier 3 (no PCBSpec): component edge midpoint fallback
      Tier 4 (mount):      mount wire-exit position
    """
    ports: List[ShellPort] = []

    # Build header -> pin-names map if PCBSpec available
    header_pin_map: Dict[str, List[str]] = {}
    if pcb_spec is not None:
        header_pin_map = _build_header_pin_map(pcb_spec)

    for cp in comp_spec.ports:
        # Try matching ConnectorPort.name to a HeaderGroup name for pin list
        matched_pins = header_pin_map.get(cp.name, [])
        if not matched_pins:
            # Single-pin port: use port name itself
            matched_pins = [cp.name]

        # Shell offset: side ports shift outward by wall_thickness
        x, y, z = cp.x, cp.y, cp.z
        if wall_thickness > 0:
            if cp.side == "left":
                x = -wall_thickness
            elif cp.side == "right":
                x = comp_spec.length_mm + wall_thickness
            elif cp.side == "bottom":
                y = -wall_thickness
            elif cp.side == "top":
                y = comp_spec.width_mm + wall_thickness

        ports.append(ShellPort(
            name=cp.name,
            port_type=cp.port_type,
            side=cp.side,
            x=round(x, 2),
            y=round(y, 2),
            z=round(z, 2),
            width=cp.width,
            height=cp.height,
            pins=matched_pins,
        ))

    return ports


# ---------------------------------------------------------------------------
# Mesh detection
# ---------------------------------------------------------------------------

# File patterns to scan in shells/{class_name}/
_MESH_PATTERNS = {
    "pcb_body": [("pcb_body.glb", "glb"), ("pcb_body.stl", "stl")],
    "base":     [("base.glb", "glb"), ("base_stl.stl", "stl")],
    "lid":      [("lid.glb", "glb"), ("lid_stl.stl", "stl")],
    "mount":    [("mount.glb", "glb"), ("mount_stl.stl", "stl")],
}


def _determine_meshes(class_name: str) -> List[MeshRef]:
    """Detect available 3-D assets under shells/{class_name}/."""
    meshes: List[MeshRef] = []
    shell_dir = _SHELLS_DIR / class_name
    if not shell_dir.is_dir():
        return meshes

    for variant, candidates in _MESH_PATTERNS.items():
        for filename, fmt in candidates:
            if (shell_dir / filename).exists():
                url = f"/api/shells/{class_name}/stl?variant={variant}"
                meshes.append(MeshRef(variant=variant, url=url, format=fmt))
                break  # prefer first match per variant (glb > stl)

    return meshes


# ---------------------------------------------------------------------------
# Assembly step generation
# ---------------------------------------------------------------------------

def _determine_tier(class_name: str) -> int:
    """Classify component into assembly tier.

    Tier 1: has shell (base+lid)
    Tier 2: bare PCB (has PCBSpec, no shell)
    Tier 3: passive / no PCBSpec / no mount
    Tier 4: has mount bracket
    """
    if _has_shell(class_name):
        return 1
    if _has_mount(class_name):
        return 4
    if class_name in PCB_REGISTRY:
        return 2
    return 3


def _generate_assembly_steps(module: ComponentModule) -> List[str]:
    """Generate assembly animation step sequence based on asset tier."""
    tier = _determine_tier(module.class_name)

    if tier == 1:
        return [
            "pcb_appear",
            "shell_base_wrap",
            "shell_lid_close",
            "place_in_enclosure",
            "ports_highlight",
        ]
    if tier == 2:
        return [
            "pcb_appear",
            "place_in_enclosure",
            "ports_highlight",
        ]
    if tier == 4:
        return [
            "component_appear",
            "mount_attach",
            "place_external",
            "ports_highlight",
        ]
    # Tier 3 -- passive / simple component
    return [
        "component_appear",
        "place_in_enclosure",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_module(comp_type: str, role: str) -> ComponentModule:
    """Build a ComponentModule from COMPONENT_REGISTRY + PCB_REGISTRY.

    Parameters
    ----------
    comp_type : str
        Component class name (e.g. 'Arduino-Uno-class').
    role : str
        Functional role (e.g. 'Brain', 'Sensor', 'Output').

    Returns
    -------
    ComponentModule
        Fully-populated module ready for assembly layout.

    Raises
    ------
    KeyError
        If *comp_type* is not found in COMPONENT_REGISTRY.
    """
    # 1. ComponentSpec from registry
    comp_spec = COMPONENT_REGISTRY[comp_type]
    class_name = comp_spec.class_name or comp_type

    # 2. Optional PCBSpec
    pcb_spec: Optional[PCBSpec] = PCB_REGISTRY.get(class_name)

    # 3. Shell / mount detection
    has_shell = _has_shell(class_name)
    wall = _wall_thickness(class_name) if has_shell else 0.0

    # 4. Module outer dimensions
    length = comp_spec.length_mm + (2 * wall if has_shell else 0.0)
    width = comp_spec.width_mm + (2 * wall if has_shell else 0.0)
    height = comp_spec.height_mm + (wall if has_shell else 0.0)  # lid adds wall

    # 5. Pin3D
    pins: List[Pin3D] = []
    if pcb_spec is not None:
        pins = _pcb_pins_to_pin3d(pcb_spec, wall_thickness=wall)

    # 6. ShellPorts
    shell_ports = _derive_shell_ports(comp_spec, pcb_spec, wall_thickness=wall)

    # 7. Meshes
    meshes = _determine_meshes(class_name)

    # 8. Build the module (without assembly_steps first)
    import copy as _copy
    module = ComponentModule(
        comp_type=comp_type,
        role=role,
        class_name=class_name,
        length=round(length, 2),
        width=round(width, 2),
        height=round(height, 2),
        weight_g=comp_spec.weight_g,
        thermal_mw=comp_spec.thermal_mw,
        enclosure_relation=comp_spec.enclosure_relation,
        pins=pins,
        shell_ports=shell_ports,
        meshes=meshes,
        host_structure=_copy.deepcopy(getattr(comp_spec, "host_structure", None)),
    )

    # 9. Assembly steps
    module.assembly_steps = _generate_assembly_steps(module)

    return module


def build_modules(components: List[dict]) -> List[ComponentModule]:
    """Batch-build ComponentModules.

    Parameters
    ----------
    components : list of dict
        Each dict must have ``"type"`` (class_name) and ``"role"``.

    Returns
    -------
    list of ComponentModule
    """
    modules: List[ComponentModule] = []
    for comp in components:
        comp_type = comp.get("type", "")
        role = comp.get("role", "")
        if comp_type not in COMPONENT_REGISTRY:
            logger.warning("Unknown component type %r, skipping", comp_type)
            continue
        modules.append(build_module(comp_type, role))
    return modules
