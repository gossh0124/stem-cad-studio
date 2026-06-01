"""tests/test_services_shared.py -- Services layer shared modules tests.

Coverage: bridge_store (paths, save/load, EventRegistry, DecisionTrail),
constants (truncate_issues, type checks), models (Job/JobStatus/PhaseID),
swap_engine (CURATED_ALT, TRADEOFF, build/apply), gate_logic (preflight).
~42 tests total.
"""
from __future__ import annotations

import os
import sys
import time
import threading
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pathlib import Path

from services.shared.models import Job, JobStatus, PhaseID, PhaseResult
from services.shared.constants import (
    truncate_issues, GATE_TIMEOUT_S, CHOICE_SKIP_GATE,
    CHOICE_CONFIRM_SWAPS, MAX_GATE_ITERATIONS,
)


# ── bridge_store: path generation ────────────────────────────

class TestBridgeStorePaths:
    def test_drive_path_format(self):
        from services.shared.bridge_store import _drive_path, DRIVE_ROOT
        assert _drive_path("abc-123") == f"{DRIVE_ROOT}/state/abc-123.json"

    def test_local_path_format(self):
        from services.shared.bridge_store import _local_path, LOCAL_ROOT
        assert _local_path("xyz-456") == f"{LOCAL_ROOT}/xyz-456.json"

    def test_paths_contain_job_id(self):
        from services.shared.bridge_store import _drive_path, _local_path
        jid = str(uuid.uuid4())
        assert jid in _drive_path(jid)
        assert jid in _local_path(jid)

    def test_drive_root_respects_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CADHLLM_DRIVE_ROOT", str(tmp_path / "custom"))
        from services.shared import bridge_store
        assert bridge_store._default_drive_root() == str(tmp_path / "custom")

    def test_default_drive_root_local_mode(self, monkeypatch):
        monkeypatch.delenv("CADHLLM_DRIVE_ROOT", raising=False)
        from services.shared import bridge_store
        result = bridge_store._default_drive_root()
        assert "output" in result or "CADHLLM" in result


# ── bridge_store: save/load round-trip ───────────────────────

def _valid_bridge() -> dict:
    return {
        "project_name": "TestProject",
        "project_category": "Education",
        "cot_plan": {"parameter_hints": {}},
        "components": [],
        "enclosure_constraints": {"target_size": "compact"},
        "inventory_mentions": [],
    }


class TestBridgeStoreSaveLoad:
    def test_roundtrip(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path / "drive"))
        monkeypatch.setattr(bs, "LOCAL_ROOT", str(tmp_path / "local"))
        bridge = _valid_bridge()
        saved = bs.save_bridge("rt-001", bridge)
        assert os.path.exists(saved)
        assert bs.load_bridge("rt-001") == bridge

    def test_save_creates_dirs(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path / "a" / "b"))
        monkeypatch.setattr(bs, "LOCAL_ROOT", str(tmp_path / "c"))
        assert Path(bs.save_bridge("dir-001", _valid_bridge())).exists()

    def test_save_rejects_empty_bridge(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path / "d"))
        monkeypatch.setattr(bs, "LOCAL_ROOT", str(tmp_path / "e"))
        with pytest.raises(ValueError):
            bs.save_bridge("bad-001", {})

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path / "x"))
        monkeypatch.setattr(bs, "LOCAL_ROOT", str(tmp_path / "y"))
        assert bs.load_bridge("nope-999") is None

    def test_load_corrupt_returns_none(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path / "drv"))
        monkeypatch.setattr(bs, "LOCAL_ROOT", str(tmp_path / "loc"))
        d = tmp_path / "drv" / "state"
        d.mkdir(parents=True)
        (d / "bad.json").write_text("{broken!", encoding="utf-8")
        assert bs.load_bridge("bad") is None


# ── bridge_store: project_output_dir ─────────────────────────

class TestProjectOutputDir:
    def test_basic_slug(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path))
        r = bs.project_output_dir("j1", "My Project", "2026-01-15")
        assert "My_Project_2026-01-15" in str(r) and r.exists()

    def test_special_chars_replaced(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path))
        name = bs.project_output_dir("j2", "Hi!@#", "2026-05-01").name
        assert "@" not in name and "!" not in name

    def test_empty_name_defaults(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path))
        assert "project" in bs.project_output_dir("j3", "", "2026-03-01").name

    def test_long_name_truncated(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path))
        slug = bs.project_output_dir("j4", "A" * 100, "2026-04-01").name
        assert len(slug.split("_2026-04-01")[0]) <= 30

    def test_date_defaults_to_today(self, tmp_path, monkeypatch):
        import services.shared.bridge_store as bs
        from datetime import datetime
        monkeypatch.setattr(bs, "DRIVE_ROOT", str(tmp_path))
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in bs.project_output_dir("j5", "Test").name


# ── bridge_store: EventRegistry ──────────────────────────────

class TestEventRegistry:
    def test_signal_registered(self):
        from services.shared.bridge_store import EventRegistry
        reg = EventRegistry()
        reg.register("e1")
        assert reg.signal("e1", {"ok": True}) is True

    def test_signal_unregistered(self):
        from services.shared.bridge_store import EventRegistry
        assert EventRegistry().signal("nope", {}) is False

    def test_wait_receives_payload(self):
        from services.shared.bridge_store import EventRegistry
        reg = EventRegistry()
        reg.register("e2")
        payload = {"choice": "swap"}
        t = threading.Thread(target=lambda: (time.sleep(0.03), reg.signal("e2", payload)))
        t.start()
        assert reg.wait("e2", timeout=2.0) == payload
        t.join()

    def test_wait_timeout(self):
        from services.shared.bridge_store import EventRegistry
        reg = EventRegistry()
        reg.register("e3")
        assert reg.wait("e3", timeout=0.02) is None

    def test_unregister(self):
        from services.shared.bridge_store import EventRegistry
        reg = EventRegistry()
        reg.register("e4")
        reg.unregister("e4")
        assert reg.signal("e4", {}) is False


# ── bridge_store: DecisionTrail ──────────────────────────────

class TestDecisionTrail:
    def _make_trail(self, tmp_path):
        from services.shared.bridge_store import DecisionTrail
        trail = DecisionTrail.__new__(DecisionTrail)
        trail._dir = tmp_path / "trails"
        trail._dir.mkdir(parents=True, exist_ok=True)
        trail._lock = threading.Lock()
        return trail

    def test_log_and_read(self, tmp_path):
        trail = self._make_trail(tmp_path)
        trail.log("dt1", "start", {"phase": 1})
        trail.log("dt1", "end", {"phase": 1})
        entries = trail.read("dt1")
        assert len(entries) == 2
        assert entries[0]["type"] == "start" and "ts" in entries[0]

    def test_read_empty(self, tmp_path):
        assert self._make_trail(tmp_path).read("ghost") == []


# ── constants.py ─────────────────────────────────────────────

class TestConstants:
    def test_gate_timeout_positive(self):
        assert isinstance(GATE_TIMEOUT_S, (int, float)) and GATE_TIMEOUT_S > 0

    def test_max_iterations_positive_int(self):
        assert isinstance(MAX_GATE_ITERATIONS, int) and MAX_GATE_ITERATIONS > 0

    def test_choice_constants_distinct_strings(self):
        assert isinstance(CHOICE_SKIP_GATE, str)
        assert isinstance(CHOICE_CONFIRM_SWAPS, str)
        assert CHOICE_SKIP_GATE != CHOICE_CONFIRM_SWAPS

    def test_truncate_under_limit(self):
        assert truncate_issues(["a", "b"], limit=5) == ["a", "b"]

    def test_truncate_at_limit(self):
        assert truncate_issues(list("abcde"), limit=5) == list("abcde")

    def test_truncate_over_limit(self):
        r = truncate_issues(list(range(10)), limit=3)
        assert len(r) == 4 and "7" in r[-1]

    def test_truncate_empty(self):
        assert truncate_issues([], limit=5) == []


# ── models.py ────────────────────────────────────────────────

class TestJobStatus:
    def test_all_values(self):
        expected = {"pending", "running", "waiting_clarify", "waiting_hitl",
                    "success", "failed", "cancelled"}
        assert {s.value for s in JobStatus} == expected

    def test_str_enum(self):
        assert JobStatus.PENDING == "pending"
        assert isinstance(JobStatus.RUNNING, str)


class TestPhaseID:
    def test_values_1_to_7(self):
        assert {p.value for p in PhaseID} == {1, 2, 3, 4, 5, 6, 7}

    def test_int_enum_comparison(self):
        assert PhaseID.P1 < PhaseID.P7 and isinstance(PhaseID.P3, int)


class TestJob:
    def test_defaults(self):
        j = Job()
        assert j.status == JobStatus.PENDING and j.job_id and j.saved is False

    def test_strip_fields(self):
        j = Job(project_name="  x  ", instruction="  y  ")
        assert j.project_name == "x" and j.instruction == "y"

    def test_touch(self):
        j = Job()
        old = j.updated_at
        time.sleep(0.01)
        j.touch()
        assert j.updated_at > old

    def test_to_dict(self):
        d = Job(job_id="d1").to_dict()
        assert d["status"] == "pending" and "phase_results" in d


class TestPhaseResult:
    def test_creation_and_finish(self):
        pr = PhaseResult(phase=PhaseID.P2, status=JobStatus.RUNNING)
        assert pr.duration_s() is None
        time.sleep(0.01)
        pr.finish(JobStatus.SUCCESS, artifacts={"f": 1}, error=None)
        assert pr.ended_at and pr.duration_s() >= 0.01

    def test_finish_with_error(self):
        pr = PhaseResult(phase=PhaseID.P5, status=JobStatus.RUNNING)
        pr.finish(JobStatus.FAILED, error="boom")
        assert pr.error == "boom" and pr.status == JobStatus.FAILED


# ── swap_engine.py ───────────────────────────────────────────

class TestCuratedAlt:
    def test_not_empty_and_structure(self):
        from services.pipeline.swap_engine import CURATED_ALT
        assert len(CURATED_ALT) > 0
        for k, v in CURATED_ALT.items():
            assert k.endswith("-class")
            assert v["type"].endswith("-class") and isinstance(v["label"], str)

    def test_tradeoff_keys_match(self):
        from services.pipeline.swap_engine import CURATED_ALT, TRADEOFF
        for (src, dst) in TRADEOFF:
            alt = CURATED_ALT.get(src)
            assert alt is not None, f"{src} not in CURATED_ALT"
            assert alt["type"] == dst


class TestBuildSwapSuggestions:
    def test_empty_components(self):
        from services.pipeline.swap_engine import build_swap_suggestions
        assert build_swap_suggestions({"components": []}) == []

    def test_brain_power_skipped(self):
        from services.pipeline.swap_engine import build_swap_suggestions
        bridge = {"components": [
            {"type": "Arduino-Uno-class", "role": "Brain"},
            {"type": "USB-5V-class", "role": "Power"},
        ]}
        assert build_swap_suggestions(bridge) == []

    def test_known_component_suggestion(self):
        from services.pipeline.swap_engine import build_swap_suggestions
        r = build_swap_suggestions({"components": [{"type": "Speaker-class", "role": "Sound"}]})
        if r:
            assert r[0]["current"]["type"] == "Speaker-class"
            assert r[0]["saving_ma"] > 0 and "alternative" in r[0]

    def test_sorted_by_saving(self):
        from services.pipeline.swap_engine import build_swap_suggestions
        r = build_swap_suggestions({"components": [
            {"type": "Speaker-class", "role": "Sound"},
            {"type": "Motor-DC-class", "role": "Actuator"},
        ]})
        if len(r) >= 2:
            assert r[0]["saving_ma"] >= r[1]["saving_ma"]


class TestApplySwaps:
    def test_empty_selection_noop(self):
        from services.pipeline.swap_engine import apply_swaps
        b = {"components": [{"type": "Speaker-class", "role": "Sound"}]}
        apply_swaps(b, [{"id": "s0", "comp_index": 0, "alternative": {"type": "X"}}], [])
        assert b["components"][0]["type"] == "Speaker-class"

    def test_apply_single(self):
        from services.pipeline.swap_engine import apply_swaps
        b = {"components": [{"type": "Speaker-class", "role": "Sound", "spec": {}}]}
        apply_swaps(b, [{"id": "s0", "comp_index": 0, "alternative": {"type": "Buzzer-Active-class"}}], ["s0"])
        assert b["components"][0]["type"] == "Buzzer-Active-class"
        assert "spec" not in b["components"][0]

    def test_unknown_id_ignored(self):
        from services.pipeline.swap_engine import apply_swaps
        b = {"components": [{"type": "Speaker-class", "role": "Sound"}]}
        apply_swaps(b, [{"id": "s0", "comp_index": 0, "alternative": {"type": "X"}}], ["s99"])
        assert b["components"][0]["type"] == "Speaker-class"


# ── gate_logic.py: phase_preflight ───────────────────────────

class TestPhasePreflight:
    def test_p1_no_requirements(self):
        from services.pipeline.gate_logic import phase_preflight
        assert phase_preflight(PhaseID.P1, {"project_name": "t"}) is None

    def test_p2_missing_keys(self):
        from services.pipeline.gate_logic import phase_preflight
        r = phase_preflight(PhaseID.P2, {"project_name": "t"})
        assert r is not None and "components" in r

    def test_p2_pass(self):
        from services.pipeline.gate_logic import phase_preflight
        from services.shared.bridge_store import _CORE_ROLES
        comps = [{"type": f"T-{r}", "role": r} for r in _CORE_ROLES]
        assert phase_preflight(PhaseID.P2, {"components": comps, "project_name": "t"}) is None

    def test_p3_requires_resolved(self):
        from services.pipeline.gate_logic import phase_preflight
        from services.shared.bridge_store import _CORE_ROLES
        comps = [{"type": f"T-{r}", "role": r} for r in _CORE_ROLES]
        bridge = {"components": comps, "components_resolved": None, "project_name": "t"}
        assert phase_preflight(PhaseID.P3, bridge) is not None

    def test_p4_requires_constraint_ok(self):
        from services.pipeline.gate_logic import phase_preflight
        bridge = {
            "components": [{"role": "Brain", "type": "X"}],
            "components_resolved": True, "project_name": "t",
            "bom": {}, "power_budget": {}, "wiring": {},
            "phase3_constraint_check": {"overall_ok": False},
        }
        assert phase_preflight(PhaseID.P4, bridge) is not None
