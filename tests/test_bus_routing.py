"""Tests for ADR-8: I2C/Power bus trunk routing optimization."""
from __future__ import annotations

import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def _make_route(from_t, to_t, sig, mcu_pin="", comp_pin="",
                wp_start=None, wp_end=None):
    """Helper to build a minimal wire route dict."""
    wp_start = wp_start or [10.0, 5.0, 8.0]
    wp_end = wp_end or [50.0, 30.0, 8.0]
    return {
        "from": from_t,
        "to": to_t,
        "waypoints": [wp_start, wp_end],
        "signal_type": sig,
        "layer_z": 18.0,
        "routed_length_mm": 50.0,
        "color": "#44ddff",
        "mcu_pin": mcu_pin,
        "comp_pin": comp_pin,
    }


class TestOptimizeBusRouting:
    """Tests for optimize_bus_routing post-processing."""

    def test_empty_routes(self):
        from lib.assembly_solver.wiring import optimize_bus_routing
        result = optimize_bus_routing({"wire_routes": []}, [])
        assert result["bus_routes"] == []
        assert result["wire_routes"] == []

    def test_no_bus_signals(self):
        """Digital-only wiring should pass through unchanged."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "LED-class", "digital", "D2", "ANODE"),
            _make_route("Arduino-Uno-class", "Buzzer-class", "digital", "D3", "SIG"),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])
        assert result["bus_routes"] == []
        assert len(result["wire_routes"]) == 2

    def test_i2c_bus_creation(self):
        """Two I2C devices should consolidate into one bus trunk."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[30.0, 15.0, 8.0]),
            _make_route("Arduino-Uno-class", "LED-class", "digital", "D2", "ANODE"),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        # Should have one I2C bus route
        assert len(result["bus_routes"]) == 1
        bus = result["bus_routes"][0]
        assert bus["bus_type"] == "i2c"
        assert bus["trunk"]["from"] == "MCU_SDA"
        assert len(bus["drops"]) == 2
        assert bus["wire_count_saved"] >= 1

        # Digital wire should remain
        remaining = result["wire_routes"]
        assert any(r["signal_type"] == "digital" for r in remaining)
        # I2C individual wires should be removed
        assert not any(r["signal_type"] == "i2c" for r in remaining)

    def test_power_bus_creation(self):
        """Multiple power wires should consolidate into one bus trunk."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "power",
                        "5V", "VCC",
                        wp_start=[8.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "Servo-class", "power",
                        "5V", "VCC",
                        wp_start=[8.0, 5.0, 8.0],
                        wp_end=[40.0, 35.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "power",
                        "5V", "VCC",
                        wp_start=[8.0, 5.0, 8.0],
                        wp_end=[25.0, 10.0, 8.0]),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        assert len(result["bus_routes"]) == 1
        bus = result["bus_routes"][0]
        assert bus["bus_type"] == "power"
        assert bus["trunk"]["from"] == "MCU_5V"
        assert len(bus["drops"]) == 3
        assert bus["wire_count_saved"] == 2

    def test_both_buses(self):
        """I2C + Power should produce two bus routes."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[30.0, 15.0, 8.0]),
            _make_route("Arduino-Uno-class", "OLED-class", "power",
                        "5V", "VCC",
                        wp_start=[8.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "power",
                        "5V", "VCC",
                        wp_start=[8.0, 5.0, 8.0],
                        wp_end=[30.0, 15.0, 8.0]),
            _make_route("Arduino-Uno-class", "Buzzer-class", "digital",
                        "D3", "SIG"),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        assert len(result["bus_routes"]) == 2
        bus_types = {b["bus_type"] for b in result["bus_routes"]}
        assert bus_types == {"i2c", "power"}

        # Only digital remains
        assert len(result["wire_routes"]) == 1
        assert result["wire_routes"][0]["signal_type"] == "digital"

    def test_bus_optimization_stats(self):
        """Bus optimization stats should be accurate."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[30.0, 15.0, 8.0]),
            _make_route("Arduino-Uno-class", "Sensor-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[60.0, 25.0, 8.0]),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        stats = result["bus_optimization"]
        assert stats["original_wire_count"] == 3
        assert stats["wires_saved"] >= 2
        assert stats["reduction_pct"] > 0

    def test_single_i2c_no_bus(self):
        """Only one I2C device should NOT create a bus (need >= 2)."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LED-class", "digital", "D2", "ANODE"),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        # No bus created with only 1 I2C device
        assert len(result["bus_routes"]) == 0
        assert len(result["wire_routes"]) == 2

    def test_trunk_waypoints_ordered(self):
        """Trunk waypoints should be sorted by distance from MCU."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "Far-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[5.0, 5.0, 8.0],
                        wp_end=[80.0, 40.0, 8.0]),
            _make_route("Arduino-Uno-class", "Near-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[5.0, 5.0, 8.0],
                        wp_end=[20.0, 12.0, 8.0]),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        bus = result["bus_routes"][0]
        wps = bus["trunk"]["waypoints"]
        # Verify waypoints are in ascending distance order
        from lib.assembly_solver.wiring import _distance_2d
        mcu_pos = [5.0, 5.0]
        distances = [_distance_2d(mcu_pos, wp) for wp in wps]
        assert distances == sorted(distances)

    def test_drops_have_percentage(self):
        """Each drop should have a valid trunk percentage [0, 1]."""
        from lib.assembly_solver.wiring import optimize_bus_routing
        routes = [
            _make_route("Arduino-Uno-class", "OLED-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[50.0, 20.0, 8.0]),
            _make_route("Arduino-Uno-class", "LCD-class", "i2c",
                        "SDA", "SDA",
                        wp_start=[10.0, 5.0, 8.0],
                        wp_end=[30.0, 15.0, 8.0]),
        ]
        wiring_result = {"wire_routes": routes}
        result = optimize_bus_routing(wiring_result, [])

        for drop in result["bus_routes"][0]["drops"]:
            assert 0.0 <= drop["from_trunk_pct"] <= 1.0
            assert "to" in drop
            assert "drop_endpoint" in drop
