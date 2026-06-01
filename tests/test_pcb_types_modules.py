"""tests/test_pcb_types_modules.py — PCB type system + module spec validation.

Covers:
  - lib/pcb/_types.py: NamedPin, MountingHole, SubComponent, HeaderGroup,
    PCBSpec (pin_index_map, find_pin, pins_in_group, thermal_profile,
    total_thermal_mw), derive_connector_ports_generic
  - lib/pcb/modules.py: 6 module specs + ALL_MODULES registry
  - lib/pcb/arduino_uno_r3.py, esp32_devkit_v1.py, microbit_v2.py,
    raspberry_pi_4b.py: structural validation

Run: .venv/Scripts/python.exe -m pytest tests/test_pcb_types_modules.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.pcb._types import (
    NamedPin, MountingHole, SubComponent, HeaderGroup, PCBSpec,
    derive_connector_ports_generic,
)
from lib.pcb.modules import (
    ALL_MODULES, HCSR04, DHT22, PIR_HCSR501,
    OLED_SSD1306, LCD_1602, RELAY_1CH, _make_inline_header,
)
from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3
from lib.pcb.esp32_devkit_v1 import ESP32_DEVKIT_V1
from lib.pcb.microbit_v2 import MICROBIT_V2
from lib.pcb.raspberry_pi_4b import RASPBERRY_PI_4B


# ── Fixtures ─────────────────────────────────────────────────

MAIN_BOARDS = [
    ("Arduino Uno R3", ARDUINO_UNO_R3, 68.6, 53.3, 32),
    ("ESP32 DevKit V1", ESP32_DEVKIT_V1, 51.4, 28.0, 30),
    ("micro:bit V2", MICROBIT_V2, 52.0, 42.0, 27),
    ("Raspberry Pi 4B", RASPBERRY_PI_4B, 85.0, 56.0, 40),
]

MODULE_SPECS = [
    ("HC-SR04", HCSR04, 45.0, 20.0, 4),
    ("DHT22", DHT22, 25.1, 15.1, 4),
    ("PIR HC-SR501", PIR_HCSR501, 32.0, 24.0, 3),
    ("OLED SSD1306", OLED_SSD1306, 27.0, 27.0, 4),
    ("LCD 1602", LCD_1602, 80.0, 36.0, 4),
    ("Relay 1CH", RELAY_1CH, 50.0, 26.0, 3),
]

ALL_SPECS = MAIN_BOARDS + MODULE_SPECS


# ── NamedPin dataclass ───────────────────────────────────────

class TestNamedPin:
    def test_creation(self):
        p = NamedPin(name="D2", x=1.0, y=2.0, pad_index=3)
        assert p.name == "D2"
        assert p.x == 1.0
        assert p.pad_index == 3

    def test_frozen(self):
        p = NamedPin(name="A0", x=0, y=0)
        with pytest.raises(AttributeError):
            p.name = "changed"

    def test_defaults(self):
        p = NamedPin(name="t", x=0, y=0)
        assert p.pad_index == 0
        assert p.function == ""
        assert p.arduino_pin == ""
        assert p.avr_port == ""


# ── MountingHole ─────────────────────────────────────────────

class TestMountingHole:
    def test_defaults(self):
        h = MountingHole(x=5, y=10)
        assert h.diameter == 3.2

    def test_custom_diameter(self):
        h = MountingHole(x=0, y=0, diameter=2.0)
        assert h.diameter == 2.0


# ── SubComponent ─────────────────────────────────────────────

class TestSubComponent:
    def test_thermal_defaults(self):
        sc = SubComponent(name="IC", package="QFP", anchor_x=0, anchor_y=0,
                          body_l=10, body_w=10, body_h=2)
        assert sc.thermal_typical_mw == 0.0
        assert sc.thermal_idle_mw == 0.0
        assert sc.thermal_peak_mw == 0.0
        assert sc.rth_ja_cw == 0.0
        assert sc.rth_sources == ()

    def test_protrudes_defaults(self):
        sc = SubComponent(name="IC", package="QFP", anchor_x=0, anchor_y=0,
                          body_l=10, body_w=10, body_h=2)
        assert sc.protrudes == ""
        assert sc.overhang == 0.0
        assert sc.profile == ""


# ── PCBSpec methods ──────────────────────────────────────────

@pytest.fixture
def simple_spec():
    pins = (
        NamedPin(name="VCC", x=1, y=1, pad_index=1, function="POWER", arduino_pin="+5V"),
        NamedPin(name="GND", x=3, y=1, pad_index=2, function="GND"),
        NamedPin(name="D2", x=5, y=1, pad_index=3, function="GPIO", arduino_pin="D2", avr_port="PD2"),
    )
    subs = (
        SubComponent(name="LED", package="0805", anchor_x=10, anchor_y=10,
                     body_l=2, body_w=1.2, body_h=0.8,
                     thermal_typical_mw=50.0, thermal_idle_mw=0.0, thermal_peak_mw=100.0),
        SubComponent(name="MCU", package="QFP-44", anchor_x=20, anchor_y=15,
                     body_l=10, body_w=10, body_h=1.6,
                     thermal_typical_mw=200.0, thermal_idle_mw=10.0, thermal_peak_mw=500.0),
    )
    return PCBSpec(
        name="TestBoard", length=50, width=30, pcb_thickness=1.6,
        pins=pins, pin_groups={"ALL": (1, 2, 3), "GPIO": (3,)},
        mounting_holes=(MountingHole(x=3, y=3), MountingHole(x=47, y=27)),
        sub_components=subs,
    )


class TestPCBSpecMethods:
    def test_pin_index_map(self, simple_spec):
        m = simple_spec.pin_index_map()
        assert len(m) == 3
        assert m[1].name == "VCC"
        assert m[3].name == "D2"

    def test_find_pin_by_name(self, simple_spec):
        p = simple_spec.find_pin("GND")
        assert p is not None
        assert p.pad_index == 2

    def test_find_pin_by_arduino(self, simple_spec):
        p = simple_spec.find_pin("D2")
        assert p is not None
        assert p.name == "D2"

    def test_find_pin_by_avr(self, simple_spec):
        p = simple_spec.find_pin("PD2")
        assert p is not None
        assert p.pad_index == 3

    def test_find_pin_missing(self, simple_spec):
        assert simple_spec.find_pin("NONEXISTENT") is None

    def test_pins_in_group(self, simple_spec):
        gpio = simple_spec.pins_in_group("GPIO")
        assert len(gpio) == 1
        assert gpio[0].name == "D2"

    def test_pins_in_group_all(self, simple_spec):
        all_pins = simple_spec.pins_in_group("ALL")
        assert len(all_pins) == 3

    def test_pins_in_group_missing(self, simple_spec):
        assert simple_spec.pins_in_group("NOPE") == ()

    def test_thermal_profile_typical(self, simple_spec):
        tp = simple_spec.thermal_profile("typical")
        assert len(tp) == 2
        names = {e["sub_name"] for e in tp}
        assert names == {"LED", "MCU"}

    def test_thermal_profile_idle(self, simple_spec):
        tp = simple_spec.thermal_profile("idle")
        assert len(tp) == 1
        assert tp[0]["sub_name"] == "MCU"

    def test_thermal_profile_peak(self, simple_spec):
        tp = simple_spec.thermal_profile("peak")
        assert len(tp) == 2

    def test_total_thermal_mw(self, simple_spec):
        assert simple_spec.total_thermal_mw("typical") == 250.0
        assert simple_spec.total_thermal_mw("idle") == 10.0
        assert simple_spec.total_thermal_mw("peak") == 600.0


# ── derive_connector_ports_generic ───────────────────────────

class TestDeriveConnectorPorts:
    def test_protruding_component(self):
        pins = (NamedPin(name="D0", x=1, y=1, pad_index=1),)
        subs = (
            SubComponent(name="USB-B", package="USB-B", anchor_x=0, anchor_y=25,
                         body_l=12, body_w=8, body_h=10, z=1.6,
                         protrudes="left", overhang=5, profile="rect"),
        )
        spec = PCBSpec(name="T", length=50, width=30, pcb_thickness=1.6,
                       pins=pins, pin_groups={}, mounting_holes=(),
                       sub_components=subs)
        ports = derive_connector_ports_generic(spec)
        assert len(ports) >= 1
        usb = [p for p in ports if p["name"] == "USB-B"]
        assert len(usb) == 1
        assert usb[0]["side"] == "left"
        assert usb[0]["port_type"] == "PWR"

    def test_usb_gets_pwr_type(self):
        pins = (NamedPin(name="D0", x=1, y=1, pad_index=1),)
        subs = (
            SubComponent(name="USB-C", package="USB-C", anchor_x=0, anchor_y=10,
                         body_l=9, body_w=7, body_h=3, protrudes="left",
                         overhang=3, profile="rect"),
        )
        spec = PCBSpec(name="T", length=50, width=30, pcb_thickness=1.6,
                       pins=pins, pin_groups={}, mounting_holes=(),
                       sub_components=subs)
        ports = derive_connector_ports_generic(spec)
        assert ports[0]["port_type"] == "PWR"

    def test_header_group_face_port(self):
        pins = tuple(
            NamedPin(name=f"P{i}", x=2.54*i, y=1.27, pad_index=i+1)
            for i in range(4)
        )
        hg = (HeaderGroup(name="HDR", pin_indices=(1,2,3,4),
                          profile="slot", port_type="GPIO"),)
        spec = PCBSpec(name="T", length=30, width=10, pcb_thickness=1.6,
                       pins=pins, pin_groups={}, mounting_holes=(),
                       sub_components=(), header_groups=hg)
        ports = derive_connector_ports_generic(spec)
        assert len(ports) == 1
        assert ports[0]["side"] == "face"
        assert ports[0]["port_type"] == "GPIO"
        assert ports[0]["width"] > 0
        assert ports[0]["height"] > 0

    def test_internal_ic_no_port(self):
        pins = (NamedPin(name="D0", x=1, y=1, pad_index=1),)
        subs = (
            SubComponent(name="MCU", package="QFP", anchor_x=20, anchor_y=15,
                         body_l=10, body_w=10, body_h=2),
        )
        spec = PCBSpec(name="T", length=50, width=30, pcb_thickness=1.6,
                       pins=pins, pin_groups={}, mounting_holes=(),
                       sub_components=subs)
        ports = derive_connector_ports_generic(spec)
        assert len(ports) == 0


# ── _make_inline_header ──────────────────────────────────────

class TestMakeInlineHeader:
    def test_pin_count(self):
        pins = _make_inline_header(("VCC", "GND", "D0"))
        assert len(pins) == 3

    def test_pin_spacing(self):
        pins = _make_inline_header(("A", "B", "C"), pitch=2.54, x_start=0)
        assert pins[0].x == 0
        assert abs(pins[1].x - 2.54) < 0.01
        assert abs(pins[2].x - 5.08) < 0.01

    def test_pad_indices_start_at_1(self):
        pins = _make_inline_header(("A", "B"))
        assert pins[0].pad_index == 1
        assert pins[1].pad_index == 2


# ── Module PCBSpecs parametrized ─────────────────────────────

@pytest.fixture(scope="module", params=MODULE_SPECS,
                ids=[s[0] for s in MODULE_SPECS])
def module_spec(request):
    return request.param


class TestModuleSpecs:
    def test_dimensions_positive(self, module_spec):
        _, spec, exp_l, exp_w, _ = module_spec
        assert spec.length == exp_l
        assert spec.width == exp_w
        assert spec.pcb_thickness > 0

    def test_pin_count(self, module_spec):
        _, spec, _, _, exp_pins = module_spec
        assert len(spec.pins) == exp_pins

    def test_has_sub_components(self, module_spec):
        _, spec, _, _, _ = module_spec
        assert len(spec.sub_components) > 0

    def test_has_header_groups(self, module_spec):
        _, spec, _, _, _ = module_spec
        assert len(spec.header_groups) > 0

    def test_pins_have_names(self, module_spec):
        _, spec, _, _, _ = module_spec
        for p in spec.pins:
            assert p.name, f"Pin {p.pad_index} has no name"

    def test_pin_indices_unique(self, module_spec):
        _, spec, _, _, _ = module_spec
        indices = [p.pad_index for p in spec.pins]
        assert len(indices) == len(set(indices))

    def test_sub_components_inside_pcb(self, module_spec):
        _, spec, _, _, _ = module_spec
        for sc in spec.sub_components:
            assert 0 <= sc.anchor_x <= spec.length * 1.5
            assert 0 <= sc.anchor_y <= spec.width * 1.5


# ── Main board PCBSpecs parametrized ─────────────────────────

@pytest.fixture(scope="module", params=MAIN_BOARDS,
                ids=[b[0] for b in MAIN_BOARDS])
def board_spec(request):
    return request.param


class TestMainBoards:
    def test_dimensions(self, board_spec):
        _, spec, exp_l, exp_w, _ = board_spec
        assert abs(spec.length - exp_l) < 1.0
        assert abs(spec.width - exp_w) < 1.0

    def test_pin_count(self, board_spec):
        _, spec, _, _, exp_pins = board_spec
        assert len(spec.pins) >= exp_pins

    def test_has_mounting_holes(self, board_spec):
        _, spec, _, _, _ = board_spec
        assert len(spec.mounting_holes) >= 0

    def test_has_sub_components(self, board_spec):
        _, spec, _, _, _ = board_spec
        assert len(spec.sub_components) > 0

    def test_pin_groups_non_empty(self, board_spec):
        _, spec, _, _, _ = board_spec
        assert len(spec.pin_groups) > 0

    def test_find_pin_works(self, board_spec):
        _, spec, _, _, _ = board_spec
        first = spec.pins[0]
        found = spec.find_pin(first.name)
        assert found is not None
        assert found.pad_index == first.pad_index

    def test_thermal_profile_returns_list(self, board_spec):
        _, spec, _, _, _ = board_spec
        tp = spec.thermal_profile("typical")
        assert isinstance(tp, list)

    def test_total_thermal_positive(self, board_spec):
        _, spec, _, _, _ = board_spec
        t = spec.total_thermal_mw("typical")
        assert t >= 0

    def test_derive_ports(self, board_spec):
        _, spec, _, _, _ = board_spec
        ports = derive_connector_ports_generic(spec)
        assert isinstance(ports, list)


# ── ALL_MODULES registry ─────────────────────────────────────

class TestAllModulesRegistry:
    def test_has_6_entries(self):
        assert len(ALL_MODULES) == 6

    def test_keys_end_with_class(self):
        for k in ALL_MODULES:
            assert k.endswith("-class"), f"{k} should end with -class"

    def test_values_are_pcbspec(self):
        for v in ALL_MODULES.values():
            assert isinstance(v, PCBSpec)

    def test_no_duplicate_names(self):
        names = [v.name for v in ALL_MODULES.values()]
        assert len(names) == len(set(names))
