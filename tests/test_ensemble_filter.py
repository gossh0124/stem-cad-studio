"""tests/test_ensemble_filter.py — CH4: Ensemble pre-filter 單元測試。"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from lib.ensemble_filter import (
    score_candidate, pre_filter, get_n_candidates,
    _score_spatial, _score_cutout_alignment, _score_printability,
    _score_thermal, _score_clearance,
)


# ── Fixtures ──────────────────────────────────────────────────────────

def _make_candidate(layout=None, joints=None, thermal=None, cable=None,
                    plan=None, params=None, error=None):
    compiled = {}
    if layout is not None:
        compiled["layout"] = layout
    if joints is not None:
        compiled["joints"] = joints
    if thermal is not None:
        compiled["thermal"] = thermal
    if cable is not None:
        compiled["cable_routing"] = cable
    return {
        "plan": plan or {},
        "params": params or {},
        "compiled": compiled,
        "source": "ch3_lora_b",
        **({"error": error} if error else {}),
    }


_COMPONENTS = [
    {"type": "Arduino-Uno-class", "role": "Brain", "qty": 1},
    {"type": "Sensor-Ultrasonic-class", "role": "Sensor", "qty": 1},
    {"type": "Motor-Servo-class", "role": "Actuator", "qty": 1},
]

_SOLVER = {
    "placements": [
        {"type": "Arduino-Uno-class", "x": 10, "y": 10},
        {"type": "Sensor-Ultrasonic-class", "x": 30, "y": 10},
        {"type": "Motor-Servo-class", "x": 10, "y": 40},
    ],
}


# ── TestScoreSpatial ──────────────────────────────────────────────────

class TestScoreSpatial:
    def test_full_coverage(self):
        layout = [
            {"component": "Arduino-Uno-class", "zone": "top-center"},
            {"component": "Sensor-Ultrasonic-class", "zone": "mid-left"},
            {"component": "Motor-Servo-class", "zone": "bottom-center"},
        ]
        score = _score_spatial({"layout": layout}, _SOLVER["placements"], _COMPONENTS)
        assert score == 25.0

    def test_duplicate_zones_penalized(self):
        layout = [
            {"component": "A", "zone": "top-center"},
            {"component": "B", "zone": "top-center"},
        ]
        score = _score_spatial({"layout": layout}, [], _COMPONENTS)
        assert score < 25.0

    def test_empty_layout(self):
        score = _score_spatial({}, [], _COMPONENTS)
        assert score < 25.0

    def test_low_coverage(self):
        layout = [{"component": "A", "zone": "top-center"}]
        score = _score_spatial({"layout": layout}, [], _COMPONENTS)
        assert score < 25.0


# ── TestScorePrintability ─────────────────────────────────────────────

class TestScorePrintability:
    def test_with_lid_method(self):
        score = _score_printability(
            {"joints": {"lid_method": "snap_fit_4x"}}, {})
        assert score == 20.0

    def test_without_joints(self):
        score = _score_printability({}, {})
        assert score < 20.0

    def test_plan_fallback_joints(self):
        score = _score_printability(
            {}, {"joints": {"lid_method": "screw_4x_M3"}})
        assert score == 20.0


# ── TestScoreThermal ──────────────────────────────────────────────────

class TestScoreThermal:
    def test_no_hot_components(self):
        cold = [{"type": "Button-class"}]
        score = _score_thermal({}, cold)
        assert score == 15.0

    def test_hot_with_strategy(self):
        hot = [{"type": "RaspberryPi-class"}]
        score = _score_thermal({"thermal": {"strategy": "passive_vent"}}, hot)
        assert score == 15.0

    def test_hot_no_strategy(self):
        hot = [{"type": "RaspberryPi-class"}]
        score = _score_thermal({}, hot)
        assert score < 15.0


# ── TestScoreClearance ────────────────────────────────────────────────

class TestScoreClearance:
    def test_with_cable_routing(self):
        score = _score_clearance(
            {"layout": [{"component": "A"}], "cable_routing": {"path": "channel_bottom"}},
            [],
        )
        assert score == 15.0

    def test_empty_layout(self):
        score = _score_clearance({}, [])
        assert score < 15.0


# ── TestScoreCandidate ────────────────────────────────────────────────

class TestScoreCandidate:
    def test_perfect_candidate(self):
        c = _make_candidate(
            layout=[
                {"component": "Arduino-Uno-class", "zone": "top-center"},
                {"component": "Sensor-Ultrasonic-class", "zone": "mid-left"},
                {"component": "Motor-Servo-class", "zone": "bottom-center"},
            ],
            joints={"lid_method": "snap_fit_4x"},
            thermal={"strategy": "passive_vent"},
            cable={"path": "channel_bottom"},
        )
        total, bd = score_candidate(c, _SOLVER, _COMPONENTS)
        assert total > 50.0
        assert all(v >= 0 for v in bd.values())

    def test_empty_candidate(self):
        c = _make_candidate()
        total, bd = score_candidate(c, _SOLVER, _COMPONENTS)
        assert 0 <= total <= 100
        assert "spatial" in bd


# ── TestPreFilter ─────────────────────────────────────────────────────

class TestPreFilter:
    def test_selects_best(self):
        good = _make_candidate(
            layout=[
                {"component": "Arduino-Uno-class", "zone": "top-center"},
                {"component": "Sensor-Ultrasonic-class", "zone": "mid-left"},
                {"component": "Motor-Servo-class", "zone": "bottom-center"},
            ],
            joints={"lid_method": "snap_fit_4x"},
            thermal={"strategy": "passive_vent"},
            cable={"path": "channel_bottom"},
        )
        bad = _make_candidate()

        ranked = pre_filter([bad, good], _SOLVER, _COMPONENTS, top_k=1)
        assert len(ranked) == 1
        assert ranked[0][0] is good
        assert ranked[0][1] > 0

    def test_top_k_two(self):
        c1 = _make_candidate(layout=[{"component": "A", "zone": "z1"}])
        c2 = _make_candidate(layout=[{"component": "A", "zone": "z1"},
                                      {"component": "B", "zone": "z2"}])
        c3 = _make_candidate()

        ranked = pre_filter([c1, c2, c3], _SOLVER, _COMPONENTS, top_k=2)
        assert len(ranked) == 2
        assert ranked[0][1] >= ranked[1][1]

    def test_empty_list(self):
        ranked = pre_filter([], _SOLVER, _COMPONENTS)
        assert ranked == []


# ── TestGetNCandidates ────────────────────────────────────────────────

class TestGetNCandidates:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("CADHLLM_ENSEMBLE_N", raising=False)
        assert get_n_candidates() == 3

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("CADHLLM_ENSEMBLE_N", "5")
        assert get_n_candidates() == 5

    def test_invalid_env(self, monkeypatch):
        monkeypatch.setenv("CADHLLM_ENSEMBLE_N", "abc")
        assert get_n_candidates() == 3

    def test_minimum_one(self, monkeypatch):
        monkeypatch.setenv("CADHLLM_ENSEMBLE_N", "0")
        assert get_n_candidates() == 1
