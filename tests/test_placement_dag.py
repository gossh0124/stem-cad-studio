"""Tests for ADR-9: Dependency DAG + topological sort for placement ordering."""
from __future__ import annotations

import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from lib.assembly_solver.placement_dag import (
    build_placement_dag,
    topological_sort_layers,
    compute_placement_order,
    _classify_tier,
    _TIER_MCU,
    _TIER_POWER,
    _TIER_INTERNAL,
    _TIER_PANEL,
    _TIER_EXTERNAL,
)


def _make_comp(type_name, role="", enclosure_relation="internal"):
    return {
        "type": type_name,
        "role": role,
        "enclosure_relation": enclosure_relation,
    }


class TestClassifyTier:
    """Test component tier classification."""

    def test_mcu_by_role(self):
        comp = _make_comp("Arduino-Uno-class", role="Brain")
        assert _classify_tier(comp) == _TIER_MCU

    def test_mcu_by_type(self):
        comp = _make_comp("arduino-mega-class", role="")
        assert _classify_tier(comp) == _TIER_MCU

    def test_esp32_mcu(self):
        comp = _make_comp("esp32-devkit-class", role="")
        assert _classify_tier(comp) == _TIER_MCU

    def test_power_by_role(self):
        comp = _make_comp("LiPo-Battery-class", role="Power")
        assert _classify_tier(comp) == _TIER_POWER

    def test_power_by_type(self):
        comp = _make_comp("battery-holder-class", role="")
        assert _classify_tier(comp) == _TIER_POWER

    def test_internal_default(self):
        comp = _make_comp("LED-class", role="Indicator")
        assert _classify_tier(comp) == _TIER_INTERNAL

    def test_panel_enclosure(self):
        comp = _make_comp("Button-class", role="Input", enclosure_relation="panel")
        assert _classify_tier(comp) == _TIER_PANEL

    def test_external_enclosure(self):
        comp = _make_comp("Servo-class", role="Actuator", enclosure_relation="external")
        assert _classify_tier(comp) == _TIER_EXTERNAL


class TestBuildPlacementDag:
    """Test DAG construction."""

    def test_single_mcu(self):
        comps = [_make_comp("Arduino-Uno-class", role="Brain")]
        graph = build_placement_dag(comps)
        assert graph["Arduino-Uno-class"] == set()

    def test_mcu_dependency(self):
        """All non-MCU components should depend on MCU."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("LED-class", role="Indicator"),
            _make_comp("Servo-class", role="Actuator"),
        ]
        graph = build_placement_dag(comps)
        assert "Arduino-Uno-class" in graph["LED-class"]
        assert "Arduino-Uno-class" in graph["Servo-class"]
        assert graph["Arduino-Uno-class"] == set()

    def test_power_dependency(self):
        """Internal components should depend on power source."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("Battery-Holder-class", role="Power"),
            _make_comp("LED-class", role="Indicator"),
        ]
        graph = build_placement_dag(comps)
        assert "Battery-Holder-class" in graph["LED-class"]
        # Power depends on MCU only
        assert "Arduino-Uno-class" in graph["Battery-Holder-class"]

    def test_external_depends_on_all(self):
        """External components depend on all internal/panel components."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("LED-class", role="Indicator"),
            _make_comp("Servo-class", role="Actuator", enclosure_relation="external"),
        ]
        graph = build_placement_dag(comps)
        assert "Arduino-Uno-class" in graph["Servo-class"]
        assert "LED-class" in graph["Servo-class"]

    def test_i2c_bus_ordering(self):
        """I2C components ordered by bus trunk direction when bus_routes provided."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("OLED-class", role="Display"),
            _make_comp("LCD-class", role="Display"),
        ]
        bus_routes = [{
            "bus_type": "i2c",
            "drops": [
                {"from_trunk_pct": 0.3, "to": "LCD-class"},
                {"from_trunk_pct": 0.8, "to": "OLED-class"},
            ],
        }]
        graph = build_placement_dag(comps, bus_routes=bus_routes)
        # OLED (further on trunk) should depend on LCD (earlier on trunk)
        assert "LCD-class" in graph["OLED-class"]


class TestTopologicalSortLayers:
    """Test Kahn's algorithm implementation."""

    def test_empty_graph(self):
        assert topological_sort_layers({}) == []

    def test_single_node(self):
        result = topological_sort_layers({"A": set()})
        assert result == [["A"]]

    def test_linear_chain(self):
        """A -> B -> C should produce three layers."""
        graph = {"A": set(), "B": {"A"}, "C": {"B"}}
        result = topological_sort_layers(graph)
        assert len(result) == 3
        assert result[0] == ["A"]
        assert result[1] == ["B"]
        assert result[2] == ["C"]

    def test_parallel_nodes(self):
        """Independent nodes should be in the same layer."""
        graph = {"A": set(), "B": {"A"}, "C": {"A"}, "D": {"A"}}
        result = topological_sort_layers(graph)
        assert len(result) == 2
        assert result[0] == ["A"]
        assert sorted(result[1]) == ["B", "C", "D"]

    def test_diamond_dag(self):
        """Diamond: A -> B,C -> D"""
        graph = {"A": set(), "B": {"A"}, "C": {"A"}, "D": {"B", "C"}}
        result = topological_sort_layers(graph)
        assert len(result) == 3
        assert result[0] == ["A"]
        assert sorted(result[1]) == ["B", "C"]
        assert result[2] == ["D"]

    def test_cycle_detection(self):
        """Cycle should raise ValueError."""
        graph = {"A": {"C"}, "B": {"A"}, "C": {"B"}}
        with pytest.raises(ValueError, match="Cycle detected"):
            topological_sort_layers(graph)

    def test_missing_dependency_ignored(self):
        """Dependencies on nodes not in graph should be skipped."""
        graph = {"A": {"MISSING"}, "B": {"A"}}
        result = topological_sort_layers(graph)
        assert len(result) == 2
        assert result[0] == ["A"]
        assert result[1] == ["B"]


class TestComputePlacementOrder:
    """Integration tests for the high-level API."""

    def test_empty_components(self):
        assert compute_placement_order([]) == []

    def test_typical_project(self):
        """Typical Arduino project placement ordering."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("Battery-Holder-class", role="Power"),
            _make_comp("OLED-class", role="Display"),
            _make_comp("Sensor-class", role="Sensor"),
            _make_comp("Servo-class", role="Actuator", enclosure_relation="external"),
        ]
        layers = compute_placement_order(comps)

        # MCU should be first layer
        assert "Arduino-Uno-class" in layers[0]
        # External should be last
        assert "Servo-class" in layers[-1]

        # Flatten to check all components present
        all_placed = [c for layer in layers for c in layer]
        assert set(all_placed) == {c["type"] for c in comps}

    def test_mcu_always_first(self):
        """MCU must always appear in the first layer."""
        comps = [
            _make_comp("LED-class", role="Indicator"),
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("Buzzer-class", role="Output"),
        ]
        layers = compute_placement_order(comps)
        assert "Arduino-Uno-class" in layers[0]

    def test_power_before_peripherals(self):
        """Power source should come before peripherals."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("LiPo-Battery-class", role="Power"),
            _make_comp("OLED-class", role="Display"),
            _make_comp("Servo-class", role="Actuator"),
        ]
        layers = compute_placement_order(comps)

        # Find layer index for each component
        layer_idx = {}
        for i, layer in enumerate(layers):
            for c in layer:
                layer_idx[c] = i

        assert layer_idx["Arduino-Uno-class"] < layer_idx["OLED-class"]
        assert layer_idx["LiPo-Battery-class"] < layer_idx["OLED-class"]
        assert layer_idx["LiPo-Battery-class"] < layer_idx["Servo-class"]

    def test_with_i2c_wiring(self):
        """I2C components should be detected from wiring info."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("OLED-class", role="Display"),
            _make_comp("Temp-Sensor-class", role="Sensor"),
        ]
        wiring = {
            "OLED": {
                "pins": [
                    {"mcu": "SDA", "comp": "SDA"},
                    {"mcu": "SCL", "comp": "SCL"},
                ]
            },
            "Temp-Sensor": {
                "pins": [
                    {"mcu": "SDA", "comp": "SDA"},
                    {"mcu": "SCL", "comp": "SCL"},
                ]
            },
        }
        layers = compute_placement_order(comps, wiring=wiring)
        # Should complete without error; MCU first
        assert "Arduino-Uno-class" in layers[0]
        all_placed = [c for layer in layers for c in layer]
        assert len(all_placed) == 3

    def test_deterministic_output(self):
        """Same input should always produce same output."""
        comps = [
            _make_comp("Arduino-Uno-class", role="Brain"),
            _make_comp("LED-class", role="Indicator"),
            _make_comp("Buzzer-class", role="Output"),
            _make_comp("Sensor-class", role="Sensor"),
        ]
        result1 = compute_placement_order(comps)
        result2 = compute_placement_order(comps)
        assert result1 == result2
