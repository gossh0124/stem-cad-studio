"""tests/test_registry_data.py — COMPONENT_REGISTRY 資料結構、查詢、完整性驗證。
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from lib.registry import (
    COMPONENT_REGISTRY,
    ComponentSpec,
    ConnectorPort,
    MountingHole,
    TAG_VOCAB_AXIS1,
    TAG_VOCAB_AXIS2_PREFIXES,
    ENCLOSURE_RELATIONS,
)

# ── Registry structure ───────────────────────────────────────

class TestRegistryStructure:
    def test_registry_is_dict(self):
        assert isinstance(COMPONENT_REGISTRY, dict)

    def test_registry_not_empty(self):
        assert len(COMPONENT_REGISTRY) > 0

    def test_all_values_are_component_spec(self):
        for key, val in COMPONENT_REGISTRY.items():
            assert isinstance(val, ComponentSpec), f"{key} is not ComponentSpec"

    def test_all_keys_are_strings(self):
        for key in COMPONENT_REGISTRY:
            assert isinstance(key, str), f"key {key!r} is not str"


# ── Key naming convention ────────────────────────────────────

class TestKeyNaming:
    def test_keys_end_with_class(self):
        """All registry keys should end with '-class'."""
        for key in COMPONENT_REGISTRY:
            assert key.endswith("-class"), f"Key {key!r} does not end with '-class'"

    def test_no_duplicate_names(self):
        """ComponentSpec.name should be unique across the registry."""
        names = [spec.name for spec in COMPONENT_REGISTRY.values()]
        assert len(names) == len(set(names)), "Duplicate component names found"


# ── Lookups ──────────────────────────────────────────────────

class TestLookups:
    def test_arduino_exists(self):
        assert "Arduino-Uno-class" in COMPONENT_REGISTRY

    def test_esp32_exists(self):
        assert "ESP32-class" in COMPONENT_REGISTRY

    def test_sensor_ultrasonic_exists(self):
        assert "Sensor-Ultrasonic-class" in COMPONENT_REGISTRY

    def test_nonexistent_returns_none(self):
        assert COMPONENT_REGISTRY.get("Nonexistent-class") is None


# ── MCU components ───────────────────────────────────────────

class TestMCUComponents:
    def test_arduino_basic_fields(self):
        spec = COMPONENT_REGISTRY["Arduino-Uno-class"]
        assert spec.length_mm > 0
        assert spec.width_mm > 0
        assert spec.height_mm > 0
        assert spec.voltage_v > 0

    def test_esp32_basic_fields(self):
        spec = COMPONENT_REGISTRY["ESP32-class"]
        assert spec.length_mm > 0
        assert spec.width_mm > 0

    def test_mcu_components_have_class_name(self):
        for key in ("Arduino-Uno-class", "ESP32-class"):
            spec = COMPONENT_REGISTRY[key]
            assert spec.class_name == key


# ── Sensor components ────────────────────────────────────────

class TestSensorComponents:
    def test_ultrasonic_dimensions_plausible(self):
        spec = COMPONENT_REGISTRY["Sensor-Ultrasonic-class"]
        assert 30 <= spec.length_mm <= 60
        assert 10 <= spec.width_mm <= 30

    def test_pir_has_positive_current(self):
        spec = COMPONENT_REGISTRY["Sensor-PIR-class"]
        assert spec.current_ma > 0

    def test_temphumid_exists(self):
        assert "Sensor-TempHumid-class" in COMPONENT_REGISTRY


# ── Enclosure relations valid ────────────────────────────────

class TestEnclosureRelationIntegrity:
    def test_all_specs_have_valid_enclosure_relation(self):
        for key, spec in COMPONENT_REGISTRY.items():
            assert spec.enclosure_relation in ENCLOSURE_RELATIONS, (
                f"{key} has invalid enclosure_relation: {spec.enclosure_relation!r}"
            )


# ── Tags integrity ───────────────────────────────────────────

class TestTagsIntegrity:
    def test_tags_are_lists(self):
        for key, spec in COMPONENT_REGISTRY.items():
            assert isinstance(spec.tags, list), f"{key} tags is not list"

    def test_axis1_tags_valid(self):
        """Axis 1 tags (bus:*/gpio:*/iface:*) must be in TAG_VOCAB_AXIS1."""
        axis1_prefixes = ("bus:", "gpio:", "iface:")
        for key, spec in COMPONENT_REGISTRY.items():
            for tag in spec.tags:
                if any(tag.startswith(p) for p in axis1_prefixes):
                    assert tag in TAG_VOCAB_AXIS1, (
                        f"{key} has unknown axis1 tag: {tag!r}"
                    )

    def test_axis2_tags_have_valid_prefix(self):
        """Axis 2 tags must start with a known prefix from TAG_VOCAB_AXIS2_PREFIXES."""
        axis1_prefixes = ("bus:", "gpio:", "iface:")
        for key, spec in COMPONENT_REGISTRY.items():
            for tag in spec.tags:
                if any(tag.startswith(p) for p in axis1_prefixes):
                    continue  # axis1
                has_valid = any(tag.startswith(p) for p in TAG_VOCAB_AXIS2_PREFIXES)
                assert has_valid, (
                    f"{key} tag {tag!r} has no valid axis2 prefix"
                )


# ── Ports and mounting holes ─────────────────────────────────

class TestPortsAndHoles:
    def test_ports_are_connector_port_instances(self):
        for key, spec in COMPONENT_REGISTRY.items():
            for p in spec.ports:
                assert isinstance(p, ConnectorPort), f"{key} has non-ConnectorPort in ports"

    def test_mounting_holes_are_instances(self):
        for key, spec in COMPONENT_REGISTRY.items():
            for h in spec.mounting_holes:
                assert isinstance(h, MountingHole), f"{key} has non-MountingHole"

    def test_ultrasonic_has_ports(self):
        spec = COMPONENT_REGISTRY["Sensor-Ultrasonic-class"]
        # PCB module may consolidate pins into a single header port
        assert len(spec.ports) >= 1


# ── Physical plausibility ────────────────────────────────────

class TestPhysicalPlausibility:
    def test_dimensions_positive(self):
        for key, spec in COMPONENT_REGISTRY.items():
            assert spec.length_mm >= 0, f"{key} length_mm negative"
            assert spec.width_mm >= 0, f"{key} width_mm negative"
            assert spec.height_mm >= 0, f"{key} height_mm negative"

    def test_weight_non_negative(self):
        for key, spec in COMPONENT_REGISTRY.items():
            assert spec.weight_g >= 0, f"{key} weight_g negative"

    def test_voltage_positive(self):
        for key, spec in COMPONENT_REGISTRY.items():
            assert spec.voltage_v > 0, f"{key} voltage_v non-positive"

    def test_current_non_negative(self):
        """Passive components (switches) can have 0 current_ma."""
        for key, spec in COMPONENT_REGISTRY.items():
            assert spec.current_ma >= 0, f"{key} current_ma negative"
