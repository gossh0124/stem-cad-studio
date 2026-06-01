"""Unit tests for lib/registry.py — SSOT 元件規格 registry。

Coverage targets (INF2):
  1. ComponentSpec basic load (Arduino-Uno fields)
  2. Non-existent component lookup
  3. list_components completeness (all keys → valid ComponentSpec)
  4. enclosure_relation covers all 5 enum values
  5. connector_ports field validation (5 components)
  6. current_typ_ma cross-check vs datasheet JSON (5 components)
  7. specs.py POWER_MA alignment with registry
"""
import json
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.registry import (
    COMPONENT_REGISTRY, ENCLOSURE_RELATIONS,
    ComponentSpec, ConnectorPort, MountingHole,
    TAG_VOCAB_AXIS1, TAG_VOCAB_AXIS2_PREFIXES,
    find_equivalent, _split_tags,
)
from lib.specs import POWER_MA

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATASHEET = os.path.join(_ROOT, "data", "component_datasheet_verified.json")


# ── ComponentSpec dataclass ────────────────────────────────

class TestComponentSpec:
    def test_valid_internal(self):
        s = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10)
        assert s.enclosure_relation == "internal"
        assert s.skip_enclosure is False

    def test_non_internal_sets_skip(self):
        s = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                          enclosure_relation="panel")
        assert s.skip_enclosure is True

    def test_skip_becomes_external(self):
        s = ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                          skip_enclosure=True)
        assert s.enclosure_relation == "external"

    def test_invalid_enclosure_raises(self):
        with pytest.raises(ValueError, match="enclosure_relation"):
            ComponentSpec(name="X", length_mm=10, width_mm=10, height_mm=10,
                          enclosure_relation="bogus")

    def test_footprint_area(self):
        s = ComponentSpec(name="X", length_mm=20, width_mm=15, height_mm=10)
        assert s.footprint_area() == 300.0

    def test_to_dict(self):
        s = ComponentSpec(
            name="X", class_name="X-class", length_mm=10, width_mm=10,
            height_mm=10,
            mounting_holes=[MountingHole(x=1, y=1, diameter=2)],
            ports=[ConnectorPort(name="U", port_type="USB", x=5, y=0,
                                 width=12, height=5)],
            tags=["bus:usb", "mcu:8bit"],
        )
        d = s.to_dict()
        assert d["length_mm"] == 10
        assert d["mounting_holes_count"] == 1
        assert d["connector_ports"][0]["name"] == "U"
        assert d["tags"] == ["bus:usb", "mcu:8bit"]


# ── Dataclass 邊界 ─────────────────────────────────────────

class TestDataclasses:
    def test_mounting_hole_frozen(self):
        h = MountingHole(x=1.0, y=2.0, diameter=3.0)
        with pytest.raises(AttributeError):
            h.x = 5.0

    def test_connector_port_defaults(self):
        p = ConnectorPort(name="P", port_type="GPIO", x=0, y=0)
        assert p.width == 3.0 and p.side == "face" and p.z == 0.0


# ── 1. Arduino-Uno 基本載入 ───────────────────────────────

class TestArduinoUnoSpec:
    def test_arduino_fields(self):
        spec = COMPONENT_REGISTRY["Arduino-Uno-class"]
        assert spec.class_name == "Arduino-Uno-class"
        assert spec.voltage_v == 5.0
        assert spec.current_ma == 50.0
        assert spec.footprint_area() == spec.length_mm * spec.width_mm
        assert 60 < spec.length_mm < 80   # ~68.6 mm
        assert 45 < spec.width_mm < 60    # ~53.4 mm


# ── 2. 不存在的元件 ───────────────────────────────────────

class TestNonExistent:
    def test_get_returns_none(self):
        assert COMPONENT_REGISTRY.get("NonExistent") is None

    def test_bracket_raises_keyerror(self):
        with pytest.raises(KeyError):
            _ = COMPONENT_REGISTRY["NonExistent"]


# ── 3. 元件清單完整性（合併維度 + tag + class_name 驗證） ─

class TestRegistryIntegrity:
    def test_minimum_count(self):
        assert len(COMPONENT_REGISTRY) >= 40

    @pytest.mark.parametrize("cn", list(COMPONENT_REGISTRY.keys()))
    def test_entry_invariants(self, cn):
        """Dimensions > 0, valid enclosure, >=2 tags, class_name matches."""
        spec = COMPONENT_REGISTRY[cn]
        assert isinstance(spec, ComponentSpec)
        assert spec.length_mm > 0 and spec.width_mm > 0 and spec.height_mm > 0
        assert spec.enclosure_relation in ENCLOSURE_RELATIONS
        assert len(spec.tags) >= 2, f"{cn}: need axis1+axis2 tag"
        assert spec.class_name == cn

    def test_mcu_have_ports(self):
        for cn, s in COMPONENT_REGISTRY.items():
            if any(t.startswith("mcu:") for t in s.tags):
                assert len(s.ports) > 0, f"MCU {cn} missing ports"


# ── 4. enclosure_relation 5 enum 覆蓋 ─────────────────────

class TestEnclosureRelation:
    def test_enum_has_five(self):
        assert ENCLOSURE_RELATIONS == frozenset(
            {"internal", "breadboard", "panel", "external", "embedded"})

    def test_embedded_valid(self):
        s = ComponentSpec(name="E", length_mm=10, width_mm=10, height_mm=10,
                          enclosure_relation="embedded")
        assert s.enclosure_relation == "embedded"
        assert s.skip_enclosure is True

    @pytest.mark.parametrize("rel", sorted(ENCLOSURE_RELATIONS))
    def test_all_values_accepted(self, rel):
        s = ComponentSpec(name="T", length_mm=1, width_mm=1, height_mm=1,
                          enclosure_relation=rel)
        assert s.enclosure_relation == rel


# ── 5. connector_ports 欄位驗證 ───────────────────────────

_PORT_TARGETS = [
    "Arduino-Uno-class", "ESP32-class", "Display-OLED-class",
    "Motor-Servo-class", "MP3-Module-class",
]

class TestConnectorPorts:
    @pytest.mark.parametrize("cn", _PORT_TARGETS)
    def test_port_fields(self, cn):
        spec = COMPONENT_REGISTRY[cn]
        assert len(spec.ports) > 0
        names = []
        for p in spec.ports:
            assert p.name and p.port_type
            assert isinstance(p.x, (int, float))
            assert isinstance(p.y, (int, float))
            names.append(p.name)
        assert len(names) == len(set(names)), f"{cn} duplicate port names"


# ── 6. current_typ_ma vs datasheet JSON ───────────────────

_XCHECK = [
    "Arduino-Uno-class", "ESP32-class", "Sensor-Ultrasonic-class",
    "Motor-Servo-class", "Display-OLED-class",
]

class TestDatasheetCrossCheck:
    @pytest.fixture(scope="class")
    def ds(self):
        with open(_DATASHEET, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.mark.parametrize("cn", _XCHECK)
    def test_current_match(self, ds, cn):
        ds_val = ds[cn]["electrical"]["current_typ_ma"]
        assert COMPONENT_REGISTRY[cn].current_ma == ds_val, (
            f"{cn}: reg={COMPONENT_REGISTRY[cn].current_ma} ds={ds_val}")


# ── 7. specs.py POWER_MA 對齊 ─────────────────────────────

class TestPowerMaAlignment:
    def test_common_keys_count(self):
        common = set(COMPONENT_REGISTRY) & set(POWER_MA)
        assert len(common) >= 30

    def test_values_match(self):
        _SUPPLY = {"power:usb_5v", "power:ac_dc"}
        for cn, pv in POWER_MA.items():
            spec = COMPONENT_REGISTRY.get(cn)
            if spec is None:
                continue
            if set(spec.tags) & _SUPPLY and pv == 0.0:
                continue  # adapter output != consumption
            assert spec.current_ma == pv, (
                f"{cn}: reg={spec.current_ma} POWER_MA={pv}")


# ── Tag 工具 ───────────────────────────────────────────────

class TestTags:
    def test_split_basic(self):
        ax1, ax2 = _split_tags(["bus:usb", "mcu:8bit", "measure:temperature"])
        assert "bus:usb" in ax1
        assert "mcu:8bit" not in ax1
        assert "measure:temperature" in ax2

    def test_split_empty(self):
        assert _split_tags([]) == (set(), set())

    def test_all_tags_valid(self):
        for cn, spec in COMPONENT_REGISTRY.items():
            ax1, ax2 = _split_tags(spec.tags)
            for t in ax1:
                assert t in TAG_VOCAB_AXIS1, f"{cn}: bad axis1 {t}"
            for t in ax2:
                assert any(t.startswith(p) for p in TAG_VOCAB_AXIS2_PREFIXES)


# ── find_equivalent ────────────────────────────────────────

class TestFindEquivalent:
    def test_unknown_target(self):
        assert find_equivalent("Nonexistent", ["Arduino-Uno-class"]) == []

    def test_self_excluded(self):
        assert "Arduino-Uno-class" not in find_equivalent(
            "Arduino-Uno-class", ["Arduino-Uno-class"])

    def test_voltage_mismatch(self):
        reg = {
            "A": ComponentSpec(name="A", class_name="A", length_mm=10,
                               width_mm=10, height_mm=10, voltage_v=5.0,
                               current_ma=50, tags=["bus:usb", "mcu:8bit"]),
            "B": ComponentSpec(name="B", class_name="B", length_mm=10,
                               width_mm=10, height_mm=10, voltage_v=12.0,
                               current_ma=50, tags=["bus:usb", "mcu:8bit"]),
        }
        assert find_equivalent("A", ["B"], registry=reg) == []

    def test_match_returned(self):
        reg = {
            "A": ComponentSpec(name="A", class_name="A", length_mm=10,
                               width_mm=10, height_mm=10, voltage_v=5.0,
                               current_ma=50, tags=["bus:usb", "mcu:8bit"]),
            "B": ComponentSpec(name="B", class_name="B", length_mm=12,
                               width_mm=12, height_mm=10, voltage_v=5.0,
                               current_ma=100, tags=["bus:usb", "mcu:8bit"]),
        }
        assert find_equivalent("A", ["B"], registry=reg) == ["B"]

    def test_current_too_low(self):
        reg = {
            "A": ComponentSpec(name="A", class_name="A", length_mm=10,
                               width_mm=10, height_mm=10, voltage_v=5.0,
                               current_ma=200, tags=["bus:usb", "mcu:8bit"]),
            "B": ComponentSpec(name="B", class_name="B", length_mm=10,
                               width_mm=10, height_mm=10, voltage_v=5.0,
                               current_ma=50, tags=["bus:usb", "mcu:8bit"]),
        }
        assert find_equivalent("A", ["B"], registry=reg) == []
