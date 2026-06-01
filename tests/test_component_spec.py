"""tests/test_component_spec.py — ComponentSpec / MountingHole / ConnectorPort
dataclass 驗證、欄位約束、序列化、TAG_VOCAB / ENCLOSURE_RELATIONS 常數。
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import warnings
import pytest

from lib.registry.component_spec import (
    ComponentSpec,
    ConnectorPort,
    MountingHole,
    ENCLOSURE_RELATIONS,
    TAG_VOCAB_AXIS1,
    TAG_VOCAB_AXIS2_PREFIXES,
)


# ── MountingHole ─────────────────────────────────────────────

class TestMountingHole:
    def test_basic_creation(self):
        h = MountingHole(x=3.5, y=4.0, diameter=2.8)
        assert h.x == 3.5
        assert h.y == 4.0
        assert h.diameter == 2.8

    def test_frozen(self):
        h = MountingHole(x=0, y=0, diameter=3.0)
        with pytest.raises(AttributeError):
            h.x = 99

    def test_equality(self):
        a = MountingHole(x=1, y=2, diameter=3)
        b = MountingHole(x=1, y=2, diameter=3)
        assert a == b

    def test_inequality(self):
        a = MountingHole(x=1, y=2, diameter=3)
        b = MountingHole(x=1, y=2, diameter=4)
        assert a != b


# ── ConnectorPort ────────────────────────────────────────────

class TestConnectorPort:
    def test_basic_creation(self):
        p = ConnectorPort(name="USB-B", port_type="USB", x=10.0, y=5.0)
        assert p.name == "USB-B"
        assert p.port_type == "USB"
        assert p.x == 10.0
        assert p.y == 5.0

    def test_defaults(self):
        p = ConnectorPort(name="P", port_type="GPIO", x=0, y=0)
        assert p.width == 3.0
        assert p.height == 3.0
        assert p.side == "face"
        assert p.z == 0.0

    def test_custom_side_and_z(self):
        p = ConnectorPort(name="P", port_type="PWR", x=0, y=0,
                          side="left", z=5.5, width=8.0, height=4.0)
        assert p.side == "left"
        assert p.z == 5.5
        assert p.width == 8.0
        assert p.height == 4.0

    def test_frozen(self):
        p = ConnectorPort(name="P", port_type="GPIO", x=0, y=0)
        with pytest.raises(AttributeError):
            p.name = "changed"


# ── ComponentSpec __post_init__ ──────────────────────────────

class TestComponentSpecPostInit:
    def test_internal_default(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5)
        assert s.enclosure_relation == "internal"
        assert s.skip_enclosure is False

    def test_panel_sets_skip(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="panel")
        assert s.skip_enclosure is True

    def test_external_sets_skip(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="external")
        assert s.skip_enclosure is True

    def test_breadboard_sets_skip(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="breadboard")
        assert s.skip_enclosure is True

    def test_skip_enclosure_true_overrides_to_external(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          skip_enclosure=True)
        assert s.enclosure_relation == "external"
        assert s.skip_enclosure is True

    def test_invalid_enclosure_relation_raises(self):
        with pytest.raises(ValueError, match="enclosure_relation must be one of"):
            ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="nonexistent")

    def test_embedded_without_host_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                              enclosure_relation="embedded", class_name="Test-cls")
            assert len(w) == 1
            assert "host_structure" in str(w[0].message)
            assert s.host_structure == "external_body"

    def test_embedded_with_str_host(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="embedded",
                          host_structure="tank_body")
        assert s.host_structure == "tank_body"

    def test_embedded_with_dict_host(self):
        host = {"type": "chassis", "slot": "front"}
        s = ComponentSpec(name="A", length_mm=10, width_mm=10, height_mm=5,
                          enclosure_relation="embedded",
                          host_structure=host)
        assert s.host_structure == host


# ── footprint_area ───────────────────────────────────────────

class TestFootprintArea:
    def test_simple(self):
        s = ComponentSpec(name="A", length_mm=20, width_mm=15, height_mm=5)
        assert s.footprint_area() == 300.0

    def test_zero_dimension(self):
        s = ComponentSpec(name="A", length_mm=0, width_mm=10, height_mm=5)
        assert s.footprint_area() == 0.0


# ── to_dict ──────────────────────────────────────────────────

class TestToDict:
    def test_basic_keys(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3)
        d = s.to_dict()
        assert d["length_mm"] == 10
        assert d["width_mm"] == 8
        assert d["height_mm"] == 3
        assert d["voltage_v"] == 5.0  # default
        assert d["skip_enclosure"] is False

    def test_tags_serialized(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3,
                          tags=["bus:i2c", "measure:temp"])
        d = s.to_dict()
        assert d["tags"] == ["bus:i2c", "measure:temp"]

    def test_mounting_holes_count(self):
        holes = [MountingHole(x=1, y=1, diameter=3), MountingHole(x=5, y=5, diameter=3)]
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3,
                          mounting_holes=holes)
        d = s.to_dict()
        assert d["mounting_holes_count"] == 2

    def test_ports_serialized(self):
        ports = [ConnectorPort(name="USB", port_type="USB", x=5, y=10, side="left", z=2.0)]
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3, ports=ports)
        d = s.to_dict()
        assert len(d["connector_ports"]) == 1
        cp = d["connector_ports"][0]
        assert cp["name"] == "USB"
        assert cp["side"] == "left"
        assert cp["z_height"] == 2.0

    def test_host_structure_included_when_set(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3,
                          enclosure_relation="embedded", host_structure="body")
        d = s.to_dict()
        assert d["host_structure"] == "body"

    def test_host_structure_absent_when_none(self):
        s = ComponentSpec(name="A", length_mm=10, width_mm=8, height_mm=3)
        d = s.to_dict()
        assert "host_structure" not in d


# ── TAG_VOCAB constants ──────────────────────────────────────

class TestTagVocab:
    def test_axis1_is_frozenset(self):
        assert isinstance(TAG_VOCAB_AXIS1, frozenset)

    def test_axis1_has_bus_i2c(self):
        assert "bus:i2c" in TAG_VOCAB_AXIS1

    def test_axis1_has_gpio_digital(self):
        assert "gpio:digital" in TAG_VOCAB_AXIS1

    def test_axis1_has_iface_passive(self):
        assert "iface:passive" in TAG_VOCAB_AXIS1

    def test_axis2_prefixes_is_frozenset(self):
        assert isinstance(TAG_VOCAB_AXIS2_PREFIXES, frozenset)

    def test_axis2_has_measure_prefix(self):
        assert "measure:" in TAG_VOCAB_AXIS2_PREFIXES

    def test_axis2_has_actuate_prefix(self):
        assert "actuate:" in TAG_VOCAB_AXIS2_PREFIXES


# ── ENCLOSURE_RELATIONS constant ─────────────────────────────

class TestEnclosureRelations:
    def test_is_frozenset(self):
        assert isinstance(ENCLOSURE_RELATIONS, frozenset)

    def test_has_five_values(self):
        assert len(ENCLOSURE_RELATIONS) == 5

    def test_all_expected_values(self):
        expected = {"internal", "breadboard", "panel", "external", "embedded"}
        assert ENCLOSURE_RELATIONS == expected
