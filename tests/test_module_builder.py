"""tests/test_module_builder.py — module_builder coverage.

Covers: build_module, build_modules, internal helpers.
Resolver tests split to test_component_resolver.py (INF1).
"""
from __future__ import annotations

import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

# --------------------------------------------------------------------------
# Module builder imports
# --------------------------------------------------------------------------
from lib.module_builder import (
    Pin3D,
    ShellPort,
    MeshRef,
    ComponentModule,
    build_module,
    build_modules,
    _pcb_pins_to_pin3d,
    _derive_shell_ports,
    _determine_tier,
    _generate_assembly_steps,
    _wall_thickness,
    _has_shell,
    _has_mount,
    _build_header_pin_map,
    _DEFAULT_WALL_THICKNESS,
)

# --------------------------------------------------------------------------
# Fixtures / helpers
# --------------------------------------------------------------------------
from lib.registry import COMPONENT_REGISTRY, ComponentSpec, ConnectorPort


@pytest.fixture
def arduino_spec():
    """Return the Arduino-Uno-class ComponentSpec from SSOT registry."""
    return COMPONENT_REGISTRY["Arduino-Uno-class"]


@pytest.fixture
def mock_pcb_spec():
    """Minimal fake PCBSpec for testing pin conversion."""
    from lib.pcb._types import PCBSpec, NamedPin, HeaderGroup, MountingHole, SubComponent

    pins = (
        NamedPin(name="D0", x=2.54, y=0.0, pad_index=1, function="GPIO", arduino_pin="D0"),
        NamedPin(name="D1", x=5.08, y=0.0, pad_index=2, function="GPIO", arduino_pin="D1"),
        NamedPin(name="A0", x=10.0, y=52.0, pad_index=3, function="ANALOG", arduino_pin="A0"),
        NamedPin(name="+5V", x=20.0, y=52.0, pad_index=4, function="POWER", arduino_pin="+5V"),
    )
    header_groups = (
        HeaderGroup(
            name="JDIGITAL",
            pin_indices=(1, 2),
            profile="slot",
            port_type="GPIO",
        ),
        HeaderGroup(
            name="JANALOG",
            pin_indices=(3, 4),
            profile="slot",
            port_type="ANALOG",
        ),
    )
    return PCBSpec(
        name="TestPCB",
        length=68.6,
        width=53.4,
        pcb_thickness=1.6,
        pins=pins,
        pin_groups={"DIGITAL": (1, 2), "ANALOG": (3, 4)},
        mounting_holes=(),
        sub_components=(),
        header_groups=header_groups,
    )


# ==========================================================================
# Module Builder Tests
# ==========================================================================


class TestPin3DConversion:
    """Test _pcb_pins_to_pin3d."""

    def test_basic_conversion(self, mock_pcb_spec):
        pins = _pcb_pins_to_pin3d(mock_pcb_spec, wall_thickness=0.0)
        assert len(pins) == 4
        assert all(isinstance(p, Pin3D) for p in pins)
        # z = pcb_thickness + wall = 1.6 + 0 = 1.6
        assert pins[0].z == 1.6
        assert pins[0].name == "D0"
        assert pins[0].function == "GPIO"
        assert pins[0].arduino_pin == "D0"

    def test_with_wall_thickness(self, mock_pcb_spec):
        pins = _pcb_pins_to_pin3d(mock_pcb_spec, wall_thickness=2.0)
        # z = 1.6 + 2.0 = 3.6
        assert pins[0].z == pytest.approx(3.6)

    def test_nc_function_default(self):
        """Pins without function default to 'NC'."""
        from lib.pcb._types import PCBSpec, NamedPin

        spec = PCBSpec(
            name="Bare",
            length=10,
            width=10,
            pcb_thickness=1.0,
            pins=(NamedPin(name="X1", x=0, y=0, pad_index=1, function=""),),
            pin_groups={},
            mounting_holes=(),
            sub_components=(),
        )
        pins = _pcb_pins_to_pin3d(spec)
        assert pins[0].function == "NC"


class TestHeaderPinMap:
    """Test _build_header_pin_map."""

    def test_maps_groups_to_pin_names(self, mock_pcb_spec):
        mapping = _build_header_pin_map(mock_pcb_spec)
        assert "JDIGITAL" in mapping
        assert mapping["JDIGITAL"] == ["D0", "D1"]
        assert mapping["JANALOG"] == ["A0", "+5V"]


class TestShellPortDerivation:
    """Test _derive_shell_ports."""

    def test_no_ports_no_result(self, mock_pcb_spec):
        spec = ComponentSpec(
            name="Empty", length_mm=10, width_mm=10, height_mm=5, ports=[]
        )
        ports = _derive_shell_ports(spec, mock_pcb_spec, wall_thickness=0.0)
        assert ports == []

    def test_wall_offset_left(self, mock_pcb_spec):
        spec = ComponentSpec(
            name="WithPort", length_mm=68.6, width_mm=53.4, height_mm=10,
            ports=[ConnectorPort(name="USB", port_type="USB", x=5.0, y=0.0,
                                 width=12, height=5, side="left", z=3.0)],
        )
        ports = _derive_shell_ports(spec, mock_pcb_spec, wall_thickness=2.0)
        assert len(ports) == 1
        # left side: x = -wall_thickness = -2.0
        assert ports[0].x == -2.0

    def test_wall_offset_right(self, mock_pcb_spec):
        spec = ComponentSpec(
            name="WithPort", length_mm=68.6, width_mm=53.4, height_mm=10,
            ports=[ConnectorPort(name="P1", port_type="GPIO", x=68.6, y=26.0,
                                 width=3, height=3, side="right", z=1.0)],
        )
        ports = _derive_shell_ports(spec, mock_pcb_spec, wall_thickness=2.0)
        # right side: x = length_mm + wall = 68.6 + 2.0 = 70.6
        assert ports[0].x == pytest.approx(70.6)

    def test_pins_from_header_group(self, mock_pcb_spec):
        """Port named same as HeaderGroup gets its pin list."""
        spec = ComponentSpec(
            name="WithPort", length_mm=68.6, width_mm=53.4, height_mm=10,
            ports=[ConnectorPort(name="JDIGITAL", port_type="GPIO", x=5.0, y=0.0,
                                 width=10, height=3, side="bottom")],
        )
        ports = _derive_shell_ports(spec, mock_pcb_spec, wall_thickness=0.0)
        assert ports[0].pins == ["D0", "D1"]


class TestDetermineTier:
    """Test _determine_tier classification."""

    @patch("lib.module_builder._has_shell", return_value=True)
    @patch("lib.module_builder._has_mount", return_value=False)
    def test_tier1_shell(self, mock_mount, mock_shell):
        assert _determine_tier("SomeClass") == 1

    @patch("lib.module_builder._has_shell", return_value=False)
    @patch("lib.module_builder._has_mount", return_value=True)
    def test_tier4_mount(self, mock_mount, mock_shell):
        assert _determine_tier("SomeClass") == 4

    @patch("lib.module_builder._has_shell", return_value=False)
    @patch("lib.module_builder._has_mount", return_value=False)
    @patch("lib.module_builder.PCB_REGISTRY", {"InPCB": object()})
    def test_tier2_pcb(self, mock_mount, mock_shell):
        assert _determine_tier("InPCB") == 2

    @patch("lib.module_builder._has_shell", return_value=False)
    @patch("lib.module_builder._has_mount", return_value=False)
    @patch("lib.module_builder.PCB_REGISTRY", {})
    def test_tier3_passive(self, mock_mount, mock_shell):
        assert _determine_tier("Passive") == 3


class TestAssemblySteps:
    """Test _generate_assembly_steps."""

    @patch("lib.module_builder._determine_tier", return_value=1)
    def test_tier1_steps(self, _):
        m = ComponentModule(comp_type="X", role="Brain", class_name="X",
                            length=70, width=55, height=15, weight_g=25,
                            thermal_mw=250, enclosure_relation="internal")
        steps = _generate_assembly_steps(m)
        assert "shell_base_wrap" in steps
        assert "shell_lid_close" in steps

    @patch("lib.module_builder._determine_tier", return_value=3)
    def test_tier3_steps(self, _):
        m = ComponentModule(comp_type="X", role="Sensor", class_name="X",
                            length=10, width=10, height=5, weight_g=3,
                            thermal_mw=10, enclosure_relation="internal")
        steps = _generate_assembly_steps(m)
        assert steps == ["component_appear", "place_in_enclosure"]


class TestBuildModule:
    """Test build_module public API."""

    def test_build_arduino_module(self):
        module = build_module("Arduino-Uno-class", "Brain")
        assert module.comp_type == "Arduino-Uno-class"
        assert module.role == "Brain"
        assert module.length > 0
        assert module.width > 0
        assert module.height > 0
        assert isinstance(module.pins, list)
        assert isinstance(module.shell_ports, list)
        assert isinstance(module.assembly_steps, list)
        assert len(module.assembly_steps) > 0

    def test_build_unknown_raises_keyerror(self):
        with pytest.raises(KeyError):
            build_module("NonExistent-Widget-class", "Unknown")

    def test_to_dict_roundtrip(self):
        module = build_module("Arduino-Uno-class", "Brain")
        d = module.to_dict()
        assert d["comp_type"] == "Arduino-Uno-class"
        assert d["role"] == "Brain"
        assert isinstance(d["pins"], list)
        assert isinstance(d["shell_ports"], list)
        assert isinstance(d["meshes"], list)
        assert isinstance(d["assembly_steps"], list)


class TestBuildModules:
    """Test build_modules batch API."""

    def test_batch_builds_valid(self):
        comps = [
            {"type": "Arduino-Uno-class", "role": "Brain"},
            {"type": "Motor-Servo-class", "role": "Actuator"},
        ]
        modules = build_modules(comps)
        assert len(modules) == 2
        assert modules[0].comp_type == "Arduino-Uno-class"
        assert modules[1].comp_type == "Motor-Servo-class"

    def test_batch_unknown_raises(self):
        """No-Silent-Fallback: an unknown component must surface as a KeyError,
        not be silently dropped from the assembly batch."""
        comps = [
            {"type": "Arduino-Uno-class", "role": "Brain"},
            {"type": "DOES-NOT-EXIST", "role": "X"},
        ]
        with pytest.raises(KeyError):
            build_modules(comps)

    def test_batch_empty_input(self):
        assert build_modules([]) == []
