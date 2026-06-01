"""tests/test_pipeline_runner.py -- STR18: PipelineRunner central dispatcher tests.

Coverage targets:
  1. _phase_preflight -- gate logic for phase transitions
  2. _auto_size_enclosure -- enclosure sizing decisions
  3. PipelineRunner.__init__ -- factory configuration
  4. PipelineRunner._should_skip -- skip/resume logic
  5. PipelineRunner.run -- main dispatch loop (mocked handlers)
  6. PipelineRunner._overwrite_phase_result -- result replacement
  7. Error handling paths

Gate payload tests moved to test_gate_logic.py.
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock

from services.shared.models import Job, JobStatus, PhaseID, PhaseResult
from services.shared.constants import CHOICE_SKIP_GATE, CHOICE_CONFIRM_SWAPS


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.update = MagicMock()
    return q


@pytest.fixture
def basic_job():
    return Job(job_id="test-pipe-001", project_name="TestProject",
               instruction="make a smart nightlight")


@pytest.fixture
def basic_bridge():
    """Minimal valid bridge for testing (includes all _CORE_ROLES)."""
    return {
        "project_name": "TestProject",
        "project_category": "Smart_Home",
        "cot_plan": {"parameter_hints": {}},
        "components": [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "USB-5V-class", "qty": 1},
            {"role": "Control", "type": "Button-class", "qty": 1},
            {"role": "Sensor", "type": "Sensor-PIR-class", "qty": 1},
            {"role": "Actuator", "type": "Lighting-NeoPixel-class", "qty": 1},
        ],
        "enclosure_constraints": {"target_size": "compact", "max_dimension_mm": 150},
        "inventory_mentions": [],
        "_instruction": "make a smart nightlight",
        "bom": [],
        "power_budget": {"ok": True},
        "wiring": {},
        "phase3_constraint_check": {"overall_ok": True},
        "cad_output": {},
        "viewer": {},
    }


def _make_phase_result(phase_id, status=JobStatus.SUCCESS):
    pr = PhaseResult(phase=phase_id, status=status)
    pr.finish(status)
    return pr


# ── _phase_preflight ─────────────────────────────────────────

class TestPhasePreflight:
    """Tests for the _phase_preflight transition gate."""

    def test_p1_always_passes(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        assert _phase_preflight(PhaseID.P1, basic_bridge) is None

    def test_p2_passes_with_core_roles(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        assert _phase_preflight(PhaseID.P2, basic_bridge) is None

    def test_p2_fails_missing_core_role(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        basic_bridge["components"] = [
            {"role": "Sensor", "type": "PIR", "qty": 1},
        ]
        err = _phase_preflight(PhaseID.P2, basic_bridge)
        assert err is not None
        assert "核心角色" in err

    def test_p2_passes_empty_components(self):
        from services.pipeline_runner import _phase_preflight
        bridge = {"components": [], "project_name": "test"}
        assert _phase_preflight(PhaseID.P2, bridge) is None

    def test_p3_fails_without_resolved(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        err = _phase_preflight(PhaseID.P3, basic_bridge)
        assert err is not None
        assert "components_resolved" in err

    def test_p3_passes_resolved(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        basic_bridge["components_resolved"] = True
        assert _phase_preflight(PhaseID.P3, basic_bridge) is None

    def test_p4_fails_constraint_not_ok(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        basic_bridge["phase3_constraint_check"] = {"overall_ok": False}
        err = _phase_preflight(PhaseID.P4, basic_bridge)
        assert err is not None
        assert "Phase IV" in err

    def test_p4_passes_with_user_override(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        basic_bridge["phase3_constraint_check"] = {
            "overall_ok": False, "user_override": True
        }
        assert _phase_preflight(PhaseID.P4, basic_bridge) is None

    def test_p4_passes_when_ok(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        basic_bridge["phase3_constraint_check"] = {"overall_ok": True}
        assert _phase_preflight(PhaseID.P4, basic_bridge) is None

    def test_p5_p6_p7_no_gate(self, basic_bridge):
        from services.pipeline_runner import _phase_preflight
        for pid in (PhaseID.P5, PhaseID.P6, PhaseID.P7):
            assert _phase_preflight(pid, basic_bridge) is None


# ── _auto_size_enclosure ─────────────────────────────────────

class TestAutoSizeEnclosure:
    """Tests for automatic enclosure sizing logic."""

    def test_empty_components_returns_empty(self):
        from services.pipeline_runner import _auto_size_enclosure
        bridge = {"components": []}
        result = _auto_size_enclosure(bridge)
        assert result == {}

    def test_housing_excluded(self):
        from services.pipeline_runner import _auto_size_enclosure
        bridge = {"components": [{"role": "Housing", "type": "box", "qty": 1}]}
        result = _auto_size_enclosure(bridge)
        assert result == {}

    @patch("lib.registry.COMPONENT_REGISTRY", new={})
    def test_few_components_compact(self):
        from services.pipeline_runner import _auto_size_enclosure
        bridge = {
            "components": [
                {"role": "Brain", "type": "Arduino", "qty": 1},
                {"role": "Sensor", "type": "PIR", "qty": 1},
            ],
            "enclosure_constraints": {},
            "cot_plan": {},
        }
        result = _auto_size_enclosure(bridge)
        assert result.get("target_size") == "compact"
        assert result.get("component_count") == 2

    @patch("lib.registry.COMPONENT_REGISTRY", new={})
    def test_many_components_medium(self):
        from services.pipeline_runner import _auto_size_enclosure
        comps = [{"role": f"R{i}", "type": f"T{i}", "qty": 1} for i in range(7)]
        bridge = {
            "components": comps,
            "enclosure_constraints": {},
            "cot_plan": {},
        }
        result = _auto_size_enclosure(bridge)
        assert result.get("target_size") in ("medium", "large")

    @patch("lib.registry.COMPONENT_REGISTRY", new={})
    def test_emit_callback_called(self):
        from services.pipeline_runner import _auto_size_enclosure
        bridge = {
            "components": [{"role": "Brain", "type": "X", "qty": 1}],
            "enclosure_constraints": {},
            "cot_plan": {},
        }
        messages = []
        _auto_size_enclosure(bridge, emit=messages.append)
        assert len(messages) == 1


# ── PipelineRunner._should_skip ──────────────────────────────

class TestShouldSkip:
    """Tests for skip/resume logic."""

    def test_skip_phases_set(self, mock_queue):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue, skip_phases=[2, 4])
        assert runner._should_skip(2) is True
        assert runner._should_skip(4) is True
        assert runner._should_skip(1) is False
        assert runner._should_skip(3) is False

    def test_resume_from_skips_earlier(self, mock_queue):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue, resume_from=3)
        assert runner._should_skip(1) is True
        assert runner._should_skip(2) is True
        assert runner._should_skip(3) is False
        assert runner._should_skip(4) is False

    def test_no_skip_no_resume(self, mock_queue):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        for i in range(1, 8):
            if i == 6:
                assert runner._should_skip(i) is True  # VLM REMOVED
            else:
                assert runner._should_skip(i) is False


# ── PipelineRunner.__init__ ──────────────────────────────────

class TestPipelineRunnerInit:
    """Tests for PipelineRunner factory configuration."""

    def test_default_handlers_registered(self, mock_queue):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        assert PhaseID.P1 in runner._handlers
        assert PhaseID.P7 in runner._handlers
        assert PhaseID.P6 not in runner._handlers  # VLM REMOVED
        assert len(runner._handlers) == 6

    def test_max_gate_iterations_constant(self, mock_queue):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        assert runner.MAX_GATE_ITERATIONS == 5


# ── PipelineRunner.run (integration with mocked handlers) ────

class TestPipelineRunnerRun:
    """Tests for the main dispatch loop."""

    @patch("services.pipeline_runner.load_bridge", return_value=None)
    @patch("services.pipeline_runner.validate_bridge", return_value=[])
    @patch("services.pipeline_runner.decision_trail")
    @patch("services.pipeline_runner.event_registry")
    @patch("services.pipeline_runner._auto_size_enclosure", return_value={})
    def test_full_run_all_phases_skipped(
        self, mock_size, mock_evt, mock_trail, mock_validate, mock_load,
        mock_queue, basic_job,
    ):
        """Skip all phases via skip_phases to test loop mechanics."""
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue, skip_phases=[1, 2, 3, 4, 5, 6, 7])
        result = runner.run(basic_job)
        assert result.status == JobStatus.SUCCESS
        # Queue should have been updated with RUNNING at start
        calls = mock_queue.update.call_args_list
        assert len(calls) >= 1

    @patch("services.pipeline_runner.load_bridge", return_value=None)
    @patch("services.pipeline_runner.validate_bridge", return_value=[])
    @patch("services.pipeline_runner.decision_trail")
    @patch("services.pipeline_runner.event_registry")
    @patch("services.pipeline_runner._auto_size_enclosure", return_value={})
    def test_run_handler_exception_sets_failed(
        self, mock_size, mock_evt, mock_trail, mock_validate, mock_load,
        mock_queue, basic_job,
    ):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue, skip_phases=[2, 3, 4, 5, 6, 7])
        mock_handler = MagicMock()
        mock_handler.run = MagicMock(side_effect=RuntimeError("LLM timeout"))
        runner._handlers[PhaseID.P1] = mock_handler

        result = runner.run(basic_job, progress_cb=None)
        assert result.status == JobStatus.FAILED
        assert "LLM timeout" in result.error

    @patch("services.pipeline_runner.load_bridge", return_value=None)
    @patch("services.pipeline_runner.validate_bridge", return_value=[])
    @patch("services.pipeline_runner.decision_trail")
    @patch("services.pipeline_runner.event_registry")
    @patch("services.pipeline_runner._auto_size_enclosure", return_value={})
    def test_preflight_failure_raises(
        self, mock_size, mock_evt, mock_trail, mock_validate, mock_load,
        mock_queue, basic_job,
    ):
        """If preflight fails, run raises ValueError."""
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue, skip_phases=[1, 3, 4, 5, 6, 7])

        # P2 preflight requires core roles; mock load_bridge to return bad bridge
        mock_load.return_value = {
            "project_name": "T", "project_category": "Education",
            "cot_plan": {}, "components": [{"role": "Sensor", "type": "X"}],
            "enclosure_constraints": {}, "inventory_mentions": [],
        }
        mock_handler = MagicMock()
        mock_handler.run = MagicMock(return_value=(
            mock_load.return_value, _make_phase_result(PhaseID.P2)))
        runner._handlers[PhaseID.P2] = mock_handler

        with pytest.raises(ValueError, match="核心角色|要求"):
            runner.run(basic_job)


# ── PipelineRunner._overwrite_phase_result ───────────────────

class TestOverwritePhaseResult:
    """Tests for phase result overwrite in gate loops."""

    def test_overwrites_existing_result(self, basic_job):
        from services.pipeline_runner import PipelineRunner
        r1 = _make_phase_result(PhaseID.P2, JobStatus.RUNNING)
        r1.phase = PhaseID.P2
        basic_job.phase_results = [r1]

        r2 = _make_phase_result(PhaseID.P2, JobStatus.SUCCESS)
        r2.phase = PhaseID.P2
        PipelineRunner._overwrite_phase_result(basic_job, 2, r2)
        assert len(basic_job.phase_results) == 1
        assert basic_job.phase_results[0].status == JobStatus.SUCCESS

    def test_appends_if_not_found(self, basic_job):
        from services.pipeline_runner import PipelineRunner
        basic_job.phase_results = []
        r = _make_phase_result(PhaseID.P3, JobStatus.SUCCESS)
        r.phase = PhaseID.P3
        PipelineRunner._overwrite_phase_result(basic_job, 3, r)
        assert len(basic_job.phase_results) == 1


# ── _emit ────────────────────────────────────────────────────

class TestEmit:
    """Tests for the _emit utility."""

    def test_emit_with_callback(self):
        from services.pipeline_runner import PipelineRunner
        msgs = []
        PipelineRunner._emit(msgs.append, "hello")
        assert msgs == ["hello"]

    def test_emit_no_callback_prints(self, capsys):
        from services.pipeline_runner import PipelineRunner
        PipelineRunner._emit(None, "fallback msg")
        captured = capsys.readouterr()
        assert "fallback msg" in captured.out


# ── make_runner convenience ──────────────────────────────────

class TestMakeRunner:
    """Tests for the make_runner factory function."""

    def test_creates_runner(self, mock_queue):
        from services.pipeline_runner import make_runner
        runner = make_runner(mock_queue, resume_from=3)
        assert runner._resume_from == 3

    def test_passes_kwargs(self, mock_queue):
        from services.pipeline_runner import make_runner
        runner = make_runner(mock_queue, skip_phases=[1, 2],
                            phase7_timeout_s=60)
        assert 1 in runner._skip
        assert 2 in runner._skip
        assert 6 in runner._skip  # VLM REMOVED — P6 always skipped


# ── _stamp_checkpoint ────────────────────────────────────────

class TestStampCheckpoint:
    """Tests for checkpoint stamping."""

    def test_stamps_phase_and_ts(self):
        from services.pipeline_runner import PipelineRunner
        bridge = {}
        PipelineRunner._stamp_checkpoint(bridge, 3)
        assert bridge["checkpoint"]["last_phase"] == 3
        assert "ts" in bridge["checkpoint"]
        assert isinstance(bridge["checkpoint"]["ts"], float)
