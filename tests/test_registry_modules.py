"""tests/test_registry_modules.py — Per-module registry validation.

Covers all 6 registry modules:
  _reg_mcu.py, _reg_sensors.py, _reg_actuators.py,
  _reg_display.py, _reg_io.py, _reg_power.py

Tests: structure, naming, dimensions, ports, mounting holes,
electrical specs, tags, uniqueness constraints.
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from itertools import chain

from lib.registry._reg_mcu import MCU_COMPONENTS
from lib.registry._reg_sensors import SENSOR_COMPONENTS
from lib.registry._reg_actuators import ACTUATOR_COMPONENTS
from lib.registry._reg_display import DISPLAY_COMPONENTS
from lib.registry._reg_io import IO_COMPONENTS
from lib.registry._reg_power import POWER_COMPONENTS
from lib.registry.component_spec import ComponentSpec, ConnectorPort, MountingHole


# ── Fixtures & helpers ──────────────────────────────────────────

ALL_MODULES = {
    'MCU': MCU_COMPONENTS,
    'SENSOR': SENSOR_COMPONENTS,
    'ACTUATOR': ACTUATOR_COMPONENTS,
    'DISPLAY': DISPLAY_COMPONENTS,
    'IO': IO_COMPONENTS,
    'POWER': POWER_COMPONENTS,
}

VALID_PORT_TYPES = {
    'PWR', 'GND', 'GPIO', 'ANALOG', 'I2C', 'SPI', 'UART',
    'USB', 'AUDIO', 'EDGE', 'OTHER',
}

VALID_SIDE_VALUES = {'face', 'left', 'right', 'top', 'bottom'}


def _all_specs():
    """Yield (module_name, class_name, spec) for all components."""
    for mod_name, registry in ALL_MODULES.items():
        for cls_name, spec in registry.items():
            yield mod_name, cls_name, spec


def _all_specs_params():
    """Parametrize IDs for all specs."""
    return [
        pytest.param(mod, key, spec, id=f"{mod}/{key}")
        for mod, key, spec in _all_specs()
    ]


def _all_ports_params():
    """Parametrize IDs for all ports across all specs."""
    params = []
    for mod, key, spec in _all_specs():
        for port in spec.ports:
            params.append(pytest.param(mod, key, port, id=f"{mod}/{key}/{port.name}"))
    return params


def _specs_with_holes_params():
    """Parametrize for specs that have mounting holes."""
    params = []
    for mod, key, spec in _all_specs():
        for i, hole in enumerate(spec.mounting_holes):
            params.append(pytest.param(mod, key, hole, id=f"{mod}/{key}/hole_{i}"))
    return params


# ══════════════════════════════════════════════════════════════════
# 1. Non-empty dicts
# ══════════════════════════════════════════════════════════════════

class TestModulesNonEmpty:
    """Each registry module dict must be non-empty."""

    def test_mcu_non_empty(self):
        assert len(MCU_COMPONENTS) > 0

    def test_sensors_non_empty(self):
        assert len(SENSOR_COMPONENTS) > 0

    def test_actuators_non_empty(self):
        assert len(ACTUATOR_COMPONENTS) > 0

    def test_display_non_empty(self):
        assert len(DISPLAY_COMPONENTS) > 0

    def test_io_non_empty(self):
        assert len(IO_COMPONENTS) > 0

    def test_power_non_empty(self):
        assert len(POWER_COMPONENTS) > 0


# ══════════════════════════════════════════════════════════════════
# 2. class_name matches dict key
# ══════════════════════════════════════════════════════════════════

class TestClassNameMatchesKey:
    """ComponentSpec.class_name must exactly match the dict key."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_class_name_equals_key(self, mod, key, spec):
        assert spec.class_name == key, (
            f"{mod}: spec.class_name={spec.class_name!r} != key={key!r}"
        )


# ══════════════════════════════════════════════════════════════════
# 3. Positive dimensions
# ══════════════════════════════════════════════════════════════════

class TestPositiveDimensions:
    """All components must have length, width, height > 0."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_length_positive(self, mod, key, spec):
        assert spec.length_mm > 0, f"{key}: length_mm={spec.length_mm}"

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_width_positive(self, mod, key, spec):
        assert spec.width_mm > 0, f"{key}: width_mm={spec.width_mm}"

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_height_positive(self, mod, key, spec):
        assert spec.height_mm > 0, f"{key}: height_mm={spec.height_mm}"


# ══════════════════════════════════════════════════════════════════
# 4. Port type validity
# ══════════════════════════════════════════════════════════════════

class TestPortTypes:
    """All ConnectorPort.port_type must be in the allowed set."""

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_type_valid(self, mod, key, port):
        assert port.port_type in VALID_PORT_TYPES, (
            f"{mod}/{key}: port {port.name!r} has invalid port_type={port.port_type!r}"
        )


# ══════════════════════════════════════════════════════════════════
# 5. Port positive dimensions
# ══════════════════════════════════════════════════════════════════

class TestPortDimensions:
    """All ports must have positive width and height."""

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_width_positive(self, mod, key, port):
        assert port.width > 0, (
            f"{mod}/{key}: port {port.name!r} width={port.width}"
        )

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_height_positive(self, mod, key, port):
        assert port.height > 0, (
            f"{mod}/{key}: port {port.name!r} height={port.height}"
        )


# ══════════════════════════════════════════════════════════════════
# 6. Mounting holes positive diameter
# ══════════════════════════════════════════════════════════════════

class TestMountingHoles:
    """All mounting holes must have positive diameter."""

    @pytest.mark.parametrize("mod,key,hole", _specs_with_holes_params())
    def test_hole_diameter_positive(self, mod, key, hole):
        assert hole.diameter > 0, (
            f"{mod}/{key}: hole at ({hole.x},{hole.y}) diameter={hole.diameter}"
        )


# ══════════════════════════════════════════════════════════════════
# 7. class_name follows "*-class" pattern
# ══════════════════════════════════════════════════════════════════

class TestClassNamePattern:
    """All class_name values must end with '-class'."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_class_name_ends_with_class(self, mod, key, spec):
        assert spec.class_name.endswith("-class"), (
            f"{mod}: class_name={spec.class_name!r} does not end with '-class'"
        )


# ══════════════════════════════════════════════════════════════════
# 8. Tags non-empty lists of strings
# ══════════════════════════════════════════════════════════════════

class TestTags:
    """Tags must be a non-empty list of strings."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_tags_non_empty(self, mod, key, spec):
        assert len(spec.tags) > 0, f"{key}: tags list is empty"

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_tags_all_strings(self, mod, key, spec):
        for tag in spec.tags:
            assert isinstance(tag, str), f"{key}: tag {tag!r} is not a string"

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_tags_not_blank(self, mod, key, spec):
        for tag in spec.tags:
            assert tag.strip() != "", f"{key}: tag is blank"


# ══════════════════════════════════════════════════════════════════
# 9. No duplicate class_names across ALL modules
# ══════════════════════════════════════════════════════════════════

class TestNoDuplicateClassNames:
    """class_name must be globally unique across all 6 modules."""

    def test_no_cross_module_duplicates(self):
        all_class_names = []
        for registry in ALL_MODULES.values():
            all_class_names.extend(registry.keys())
        duplicates = [
            cn for cn in all_class_names if all_class_names.count(cn) > 1
        ]
        assert len(duplicates) == 0, f"Duplicate class_names: {set(duplicates)}"

    def test_total_count_matches_sum_of_modules(self):
        total = sum(len(r) for r in ALL_MODULES.values())
        all_keys = set()
        for registry in ALL_MODULES.values():
            all_keys.update(registry.keys())
        assert len(all_keys) == total, (
            f"Expected {total} unique keys but got {len(all_keys)} "
            "(some keys appear in multiple modules)"
        )


# ══════════════════════════════════════════════════════════════════
# 10. current_ma >= 0
# ══════════════════════════════════════════════════════════════════

class TestElectricalCurrentNonNegative:
    """current_ma must be >= 0 for all components."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_current_non_negative(self, mod, key, spec):
        assert spec.current_ma >= 0, (
            f"{key}: current_ma={spec.current_ma} is negative"
        )


# ══════════════════════════════════════════════════════════════════
# 11. thermal_mw >= 0
# ══════════════════════════════════════════════════════════════════

class TestThermalNonNegative:
    """thermal_mw must be >= 0."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_thermal_non_negative(self, mod, key, spec):
        assert spec.thermal_mw >= 0, (
            f"{key}: thermal_mw={spec.thermal_mw} is negative"
        )


# ══════════════════════════════════════════════════════════════════
# 12. Port side values are valid
# ══════════════════════════════════════════════════════════════════

class TestPortSideValues:
    """All port side values must be in the valid set."""

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_side_valid(self, mod, key, port):
        assert port.side in VALID_SIDE_VALUES, (
            f"{mod}/{key}: port {port.name!r} has invalid side={port.side!r}"
        )


# ══════════════════════════════════════════════════════════════════
# 13. Specific module counts
# ══════════════════════════════════════════════════════════════════

class TestModuleCounts:
    """Verify expected component counts per module."""

    def test_mcu_count(self):
        # Uno, Arduino-Nano, ESP32, RaspberryPi (infra-dormant after deprecate), Microbit
        assert len(MCU_COMPONENTS) == 5

    def test_sensors_has_several(self):
        assert len(SENSOR_COMPONENTS) >= 5

    def test_actuators_has_several(self):
        assert len(ACTUATOR_COMPONENTS) >= 5

    def test_display_has_several(self):
        assert len(DISPLAY_COMPONENTS) >= 4

    def test_io_has_several(self):
        assert len(IO_COMPONENTS) >= 5

    def test_power_has_several(self):
        assert len(POWER_COMPONENTS) >= 4


# ══════════════════════════════════════════════════════════════════
# Additional structural tests
# ══════════════════════════════════════════════════════════════════

class TestComponentSpecTypes:
    """All values must be ComponentSpec instances."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_is_component_spec_instance(self, mod, key, spec):
        assert isinstance(spec, ComponentSpec), (
            f"{mod}/{key}: type is {type(spec).__name__}, expected ComponentSpec"
        )


class TestPortInstances:
    """All ports must be ConnectorPort instances."""

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_is_connector_port(self, mod, key, port):
        assert isinstance(port, ConnectorPort), (
            f"{mod}/{key}: port type is {type(port).__name__}"
        )


class TestMountingHoleInstances:
    """All mounting holes must be MountingHole instances."""

    @pytest.mark.parametrize("mod,key,hole", _specs_with_holes_params())
    def test_hole_is_mounting_hole(self, mod, key, hole):
        assert isinstance(hole, MountingHole), (
            f"{mod}/{key}: hole type is {type(hole).__name__}"
        )


class TestComponentNames:
    """Component names should be non-empty human-readable strings."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_name_non_empty(self, mod, key, spec):
        assert spec.name and spec.name.strip() != "", (
            f"{key}: name is empty or blank"
        )


class TestVoltage:
    """voltage_v should be positive for all components."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_voltage_positive(self, mod, key, spec):
        assert spec.voltage_v > 0, f"{key}: voltage_v={spec.voltage_v}"


class TestWeightNonNegative:
    """weight_g must be >= 0."""

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_weight_non_negative(self, mod, key, spec):
        assert spec.weight_g >= 0, f"{key}: weight_g={spec.weight_g}"


class TestEnclosureRelation:
    """enclosure_relation must be a valid value."""

    VALID_ENCLOSURE = {'internal', 'breadboard', 'panel', 'external', 'embedded'}

    @pytest.mark.parametrize("mod,key,spec", _all_specs_params())
    def test_enclosure_relation_valid(self, mod, key, spec):
        assert spec.enclosure_relation in self.VALID_ENCLOSURE, (
            f"{key}: enclosure_relation={spec.enclosure_relation!r}"
        )


class TestPortZNonNegative:
    """Port z (height above base) must be >= 0."""

    @pytest.mark.parametrize("mod,key,port", _all_ports_params())
    def test_port_z_non_negative(self, mod, key, port):
        assert port.z >= 0, (
            f"{mod}/{key}: port {port.name!r} z={port.z} is negative"
        )
