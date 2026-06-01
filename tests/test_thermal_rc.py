"""tests/test_thermal_rc.py -- IC-level RC thermal network solver tests.

Covers: build_thermal_network, solve_steady_state, compute_coupling_resistance,
thermal_rc_report, warnings, numpy fallback, edge cases.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.pcb._types import SubComponent, PCBSpec
from lib.assembly_solver.thermal_rc import (
    build_thermal_network, solve_steady_state, compute_coupling_resistance,
    thermal_rc_report, _distance_mm, _generate_warnings, _solve_diagonal,
    WARN_ELEVATED_C, WARN_CRITICAL_C, K_COPPER, K_FR4,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _sc(name='IC1', anchor_x=10.0, anchor_y=10.0, body_w=5.0,
        typical_mw=100.0, idle_mw=10.0, peak_mw=200.0, rth_ja=50.0):
    return SubComponent(
        name=name, package='QFN-32',
        anchor_x=anchor_x, anchor_y=anchor_y,
        body_l=5.0, body_w=body_w, body_h=1.0,
        thermal_typical_mw=typical_mw, thermal_idle_mw=idle_mw,
        thermal_peak_mw=peak_mw, rth_ja_cw=rth_ja,
        rth_sources=(
            {'source': 'datasheet', 'value': rth_ja, 'ref': 'DS'},
            {'source': 'jedec', 'value': rth_ja * 0.95, 'ref': 'JESD51'},
            {'source': 'empirical', 'value': rth_ja * 1.05, 'ref': 'calc'},
        ),
    )


def _pcb(scs, name='TestPCB', length=68.0, width=53.0, pcb_thickness=1.6):
    return PCBSpec(name=name, length=length, width=width,
                  pcb_thickness=pcb_thickness, pins=(), pin_groups={},
                  mounting_holes=(), sub_components=tuple(scs))


def _net(nodes, adjacency=None):
    """Shorthand to build a network dict."""
    return {'nodes': nodes, 'adjacency': adjacency or []}


def _node(name, rth_ja=50.0, power_mw=100.0, pos=(10, 10)):
    return {'name': name, 'package': 'QFN', 'rth_ja': rth_ja,
            'power_mw': power_mw, 'position': pos}


# ── distance & coupling ─────────────────────────────────────────────

class TestDistanceAndCoupling:
    def test_distance_same_point(self):
        assert _distance_mm(0, 0, 0, 0) == 0.0

    def test_distance_diagonal(self):
        assert _distance_mm(0, 0, 3, 4) == pytest.approx(5.0)

    def test_coupling_basic(self):
        a, b = _sc('A', anchor_x=0, anchor_y=0), _sc('B', anchor_x=20, anchor_y=0)
        r = compute_coupling_resistance(a, b, pcb_thickness=1.6)
        k_eff = 0.3 * K_COPPER + 0.7 * K_FR4
        expected = 0.020 / (k_eff * 1.6e-3 * 5e-3)
        assert r == pytest.approx(expected, rel=1e-6)

    def test_coupling_overlapping(self):
        a = _sc('A', anchor_x=5, anchor_y=5)
        b = _sc('B', anchor_x=5, anchor_y=5)
        assert compute_coupling_resistance(a, b) == 1.0

    def test_coupling_far_apart_high_resistance(self):
        a, b = _sc('A', anchor_x=0, anchor_y=0, body_w=2.0), \
               _sc('B', anchor_x=100, anchor_y=0, body_w=2.0)
        assert compute_coupling_resistance(a, b) > 100.0

    def test_thicker_pcb_lower_resistance(self):
        a, b = _sc('A', anchor_x=0, anchor_y=0), _sc('B', anchor_x=20, anchor_y=0)
        assert compute_coupling_resistance(a, b, pcb_thickness=3.2) < \
               compute_coupling_resistance(a, b, pcb_thickness=0.8)

    def test_higher_copper_lower_resistance(self):
        a, b = _sc('A', anchor_x=0, anchor_y=0), _sc('B', anchor_x=20, anchor_y=0)
        assert compute_coupling_resistance(a, b, copper_fraction=0.9) < \
               compute_coupling_resistance(a, b, copper_fraction=0.1)

    def test_zero_body_width_no_crash(self):
        a = _sc('A', anchor_x=0, anchor_y=0, body_w=0.0)
        b = _sc('B', anchor_x=10, anchor_y=0)
        assert compute_coupling_resistance(a, b) > 0

    def test_uses_min_body_width(self):
        a = _sc('A', anchor_x=0, anchor_y=0, body_w=2.0)
        b = _sc('B', anchor_x=10, anchor_y=0, body_w=10.0)
        r = compute_coupling_resistance(a, b)
        k_eff = 0.3 * K_COPPER + 0.7 * K_FR4
        expected = 0.010 / (k_eff * 1.6e-3 * 2.0e-3)
        assert r == pytest.approx(expected, rel=1e-6)


# ── build_thermal_network ───────────────────────────────────────────

class TestBuildNetwork:
    def test_empty_pcb(self):
        net = build_thermal_network(_pcb([]))
        assert net['nodes'] == [] and net['adjacency'] == []

    def test_single_node(self):
        net = build_thermal_network(_pcb([_sc('U1')]), mode='typical')
        assert len(net['nodes']) == 1
        assert net['nodes'][0]['name'] == 'U1'
        assert net['nodes'][0]['power_mw'] == 100.0

    def test_skip_zero_rth(self):
        net = build_thermal_network(_pcb([_sc('U1', rth_ja=50), _sc('U2', rth_ja=0)]))
        assert len(net['nodes']) == 1

    def test_close_nodes_have_coupling(self):
        net = build_thermal_network(_pcb([
            _sc('A', anchor_x=10, anchor_y=10, rth_ja=40),
            _sc('B', anchor_x=30, anchor_y=10, rth_ja=60),
        ]))
        assert len(net['adjacency']) == 1

    def test_far_nodes_no_coupling(self):
        net = build_thermal_network(_pcb([
            _sc('A', anchor_x=0, anchor_y=0), _sc('B', anchor_x=100, anchor_y=100),
        ], length=200, width=200))
        assert net['adjacency'] == []

    def test_mode_idle_and_peak(self):
        pcb = _pcb([_sc('U1', typical_mw=100, idle_mw=10, peak_mw=300)])
        assert build_thermal_network(pcb, mode='idle')['nodes'][0]['power_mw'] == 10.0
        assert build_thermal_network(pcb, mode='peak')['nodes'][0]['power_mw'] == 300.0


# ── solve_steady_state ──────────────────────────────────────────────

class TestSolveSteadyState:
    def test_empty(self):
        assert solve_steady_state(_net([])) == []

    def test_single_node(self):
        r = solve_steady_state(_net([_node('U1', 50.0, 100.0)]), ambient_c=25.0)
        assert r[0]['temp_c'] == pytest.approx(30.0, abs=0.01)
        assert r[0]['delta_t'] == pytest.approx(5.0, abs=0.01)

    def test_zero_power_all_ambient(self):
        r = solve_steady_state(_net([
            _node('U1', 50.0, 0.0), _node('U2', 30.0, 0.0, pos=(20, 10)),
        ]), ambient_c=25.0)
        assert all(nd['temp_c'] == pytest.approx(25.0, abs=0.01) for nd in r)

    def test_two_uncoupled(self):
        r = solve_steady_state(_net([
            _node('U1', 50.0, 200.0), _node('U2', 100.0, 50.0, pos=(80, 80)),
        ]), ambient_c=25.0)
        assert r[0]['temp_c'] == pytest.approx(35.0, abs=0.01)
        assert r[1]['temp_c'] == pytest.approx(30.0, abs=0.01)

    def test_two_coupled_heat_transfer(self):
        r = solve_steady_state(_net(
            [_node('U1', 50.0, 1000.0), _node('U2', 50.0, 0.0, pos=(20, 10))],
            [{'from': 'U1', 'to': 'U2', 'r_coupling': 100.0}],
        ), ambient_c=25.0)
        assert r[0]['temp_c'] < 75.0  # heat lost to U2
        assert r[1]['temp_c'] > 25.0  # warmed by U1

    def test_three_symmetric_nodes(self):
        nodes = [_node(n, 50.0, 100.0, p) for n, p in
                 [('A', (0, 0)), ('B', (10, 0)), ('C', (5, 8.66))]]
        adj = [{'from': 'A', 'to': 'B', 'r_coupling': 200.0},
               {'from': 'B', 'to': 'C', 'r_coupling': 200.0},
               {'from': 'A', 'to': 'C', 'r_coupling': 200.0}]
        r = solve_steady_state(_net(nodes, adj), ambient_c=25.0)
        assert r[0]['temp_c'] == pytest.approx(r[1]['temp_c'], abs=0.01)
        assert r[1]['temp_c'] == pytest.approx(r[2]['temp_c'], abs=0.01)

    def test_different_ambient(self):
        net = _net([_node('U1', 50.0, 100.0)])
        r25 = solve_steady_state(net, ambient_c=25.0)
        r40 = solve_steady_state(net, ambient_c=40.0)
        assert r25[0]['delta_t'] == pytest.approx(r40[0]['delta_t'], abs=0.01)
        assert r40[0]['temp_c'] == pytest.approx(r25[0]['temp_c'] + 15.0, abs=0.01)


# ── diagonal fallback ───────────────────────────────────────────────

class TestDiagonalFallback:
    def test_simple(self):
        r = _solve_diagonal(_net([_node('U1', 100.0, 500.0)]), ambient_c=20.0)
        assert r[0]['temp_c'] == pytest.approx(70.0, abs=0.01)

    def test_ignores_coupling(self):
        r = _solve_diagonal(_net(
            [_node('A', 50.0, 100.0), _node('B', 50.0, 0.0, pos=(10, 0))],
            [{'from': 'A', 'to': 'B', 'r_coupling': 100.0}],
        ), ambient_c=25.0)
        assert r[1]['temp_c'] == pytest.approx(25.0, abs=0.01)

    def test_no_numpy_uses_diagonal(self):
        import lib.assembly_solver.thermal_rc as mod
        orig = mod._HAS_NUMPY
        try:
            mod._HAS_NUMPY = False
            r = solve_steady_state(_net(
                [_node('U1', 50.0, 100.0), _node('U2', 50.0, 0.0, pos=(10, 0))],
                [{'from': 'U1', 'to': 'U2', 'r_coupling': 100.0}],
            ), ambient_c=25.0)
            assert r[1]['temp_c'] == pytest.approx(25.0, abs=0.01)
        finally:
            mod._HAS_NUMPY = orig

    def test_single_node_same_with_or_without_numpy(self):
        import lib.assembly_solver.thermal_rc as mod
        net = _net([_node('U1', 50.0, 200.0)])
        orig = mod._HAS_NUMPY
        try:
            mod._HAS_NUMPY = True
            r1 = solve_steady_state(net, ambient_c=25.0)
            mod._HAS_NUMPY = False
            r2 = solve_steady_state(net, ambient_c=25.0)
            assert r1[0]['temp_c'] == pytest.approx(r2[0]['temp_c'], abs=0.01)
        finally:
            mod._HAS_NUMPY = orig


# ── warnings ────────────────────────────────────────────────────────

class TestWarnings:
    def test_cool_no_warning(self):
        assert _generate_warnings([{'name': 'U1', 'temp_c': 40.0}]) == []

    def test_elevated(self):
        w = _generate_warnings([{'name': 'U1', 'temp_c': 75.0}])
        assert w[0]['level'] == 'elevated'

    def test_critical(self):
        w = _generate_warnings([{'name': 'U1', 'temp_c': 90.0}])
        assert w[0]['level'] == 'critical'

    def test_boundary_70_no_warn(self):
        assert _generate_warnings([{'name': 'U1', 'temp_c': 70.0}]) == []

    def test_boundary_85_elevated_not_critical(self):
        w = _generate_warnings([{'name': 'U1', 'temp_c': 85.0}])
        assert w[0]['level'] == 'elevated'

    def test_above_85_critical(self):
        w = _generate_warnings([{'name': 'U1', 'temp_c': 85.01}])
        assert w[0]['level'] == 'critical'

    def test_multiple(self):
        w = _generate_warnings([
            {'name': 'U1', 'temp_c': 75.0},
            {'name': 'U2', 'temp_c': 90.0},
            {'name': 'U3', 'temp_c': 40.0},
        ])
        assert len(w) == 2


# ── thermal_rc_report ───────────────────────────────────────────────

class TestReport:
    def test_structure(self):
        report = thermal_rc_report(_pcb([_sc('U1')], name='Board'), ambient_c=25.0)
        for k in ('nodes', 'max_temp_c', 'max_delta_t', 'ambient_c',
                  'coupling_count', 'warnings', 'board_name', 'mode'):
            assert k in report
        assert report['board_name'] == 'Board'

    def test_single_ic_values(self):
        report = thermal_rc_report(_pcb([_sc('MCU', rth_ja=50, typical_mw=200)]))
        assert report['max_temp_c'] == pytest.approx(35.0, abs=0.1)
        assert report['warnings'] == []

    def test_high_power_critical_warning(self):
        report = thermal_rc_report(_pcb([_sc('HOT', rth_ja=50, typical_mw=2000)]))
        assert report['max_temp_c'] > WARN_CRITICAL_C
        assert report['warnings'][0]['level'] == 'critical'

    def test_no_thermal_components(self):
        sc = SubComponent(name='Conn', package='USB', anchor_x=0, anchor_y=0,
                          body_l=10, body_w=8, body_h=5)
        report = thermal_rc_report(_pcb([sc]))
        assert report['nodes'] == [] and report['max_temp_c'] == 25.0

    def test_idle_lower_than_typical(self):
        pcb = _pcb([_sc('U1', typical_mw=100, idle_mw=5)])
        assert thermal_rc_report(pcb, mode='idle')['max_temp_c'] < \
               thermal_rc_report(pcb, mode='typical')['max_temp_c']

    def test_coupling_count(self):
        report = thermal_rc_report(_pcb([
            _sc('A', anchor_x=10, anchor_y=10, typical_mw=500),
            _sc('B', anchor_x=25, anchor_y=10, typical_mw=50),
        ]))
        assert report['coupling_count'] == 1


# ── Integration with real PCB specs ─────────────────────────────────

class TestRealPCBSpecs:
    def test_arduino_uno_r3(self):
        from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3
        report = thermal_rc_report(ARDUINO_UNO_R3, mode='typical')
        assert len(report['nodes']) >= 3
        assert report['max_temp_c'] > 25.0

    def test_esp32_devkit_v1(self):
        from lib.pcb.esp32_devkit_v1 import ESP32_DEVKIT_V1
        report = thermal_rc_report(ESP32_DEVKIT_V1, mode='typical')
        assert len(report['nodes']) >= 2
        assert report['max_temp_c'] > 25.0
