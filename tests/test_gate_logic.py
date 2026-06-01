"""tests/test_gate_logic.py -- Gate logic tests (split from test_pipeline_runner.py).

Coverage targets:
  1. PipelineRunner._gate_emit_and_apply -- swap gate shared logic
  2. PipelineRunner._p2_power_gate_payload -- power gate payload assembly
  3. PipelineRunner._p3_gate_payload -- constraint gate payload
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock

from services.shared.models import Job, JobStatus, PhaseID
from services.shared.constants import CHOICE_SKIP_GATE, CHOICE_CONFIRM_SWAPS


@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.update = MagicMock()
    return q


@pytest.fixture
def basic_job():
    return Job(job_id="test-gate-001", project_name="TestProject",
               instruction="make a smart nightlight")


# ── PipelineRunner._gate_emit_and_apply ──────────────────────

class TestGateEmitAndApply:
    """Tests for the gate shared logic."""

    @patch("services.pipeline_runner.decision_trail")
    def test_skip_gate_no_suggestions_continues(
        self, mock_trail, mock_queue, basic_job
    ):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {"power_budget": {"total_ma": 100, "budget_ma": 500}}
        result_cmd = {"choice_id": CHOICE_SKIP_GATE}
        payload = {}
        suggestions = []

        action = runner._gate_emit_and_apply(
            basic_job, bridge, payload, suggestions, result_cmd, None)
        assert action == "continue"

    def test_skip_gate_with_suggestions_blocked(self, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {"power_budget": {"total_ma": 100, "budget_ma": 500}}
        result_cmd = {"choice_id": CHOICE_SKIP_GATE}
        payload = {}
        suggestions = [{"id": "s1"}]
        msgs = []

        action = runner._gate_emit_and_apply(
            basic_job, bridge, payload, suggestions, result_cmd,
            msgs.append)
        assert action == "rerun_from_2"

    @patch("services.pipeline_runner.decision_trail")
    def test_confirm_swaps_applies(self, mock_trail, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {"power_budget": {"total_ma": 600, "budget_ma": 500},
                  "components": []}
        suggestions = [{"id": "s1", "from_type": "A", "to_type": "B"}]
        result_cmd = {"choice_id": CHOICE_CONFIRM_SWAPS,
                      "selected_swaps": ["s1"]}

        with patch('services.pipeline.gate_logic._apply_swaps_fn') as mock_apply:
            action = runner._gate_emit_and_apply(
                basic_job, bridge, {}, suggestions, result_cmd, None)
        assert action == "rerun_from_2"
        mock_apply.assert_called_once()


# ── _p2_power_gate_payload ───────────────────────────────────

class TestP2PowerGatePayload:
    """Tests for Phase II power gate payload assembly."""

    def test_no_warning_returns_none(self, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {"power_warning_phase2": {}}
        payload, suggestions = runner._p2_power_gate_payload(basic_job, bridge)
        assert payload is None
        assert suggestions == []

    def test_warning_builds_payload(self, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {
            "power_warning_phase2": {
                "warning": True, "total_ma": 800, "supply_ma": 500,
            },
            "components": [],
        }
        with patch('services.pipeline.gate_logic._build_swap_suggestions_fn', return_value=[
            {"id": "s1", "from_type": "X", "to_type": "Y"}
        ]):
            payload, suggestions = runner._p2_power_gate_payload(
                basic_job, bridge)
        assert payload is not None
        assert payload["phase"] == 2
        assert payload["event_type"] == "fix_choice"
        assert len(suggestions) == 1


# ── _p3_gate_payload ─────────────────────────────────────────

class TestP3GatePayload:
    """Tests for Phase III constraint gate payload."""

    def test_overall_ok_returns_none(self, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {"phase3_constraint_check": {"overall_ok": True}}
        payload, suggestions = runner._p3_gate_payload(basic_job, bridge)
        assert payload is None

    def test_not_ok_builds_payload(self, mock_queue, basic_job):
        from services.pipeline_runner import PipelineRunner
        runner = PipelineRunner(mock_queue)
        bridge = {
            "phase3_constraint_check": {
                "overall_ok": False,
                "results": {
                    "power": {"ok": False, "details": [
                        {"rule": "P1", "msg": "over budget", "level": "FAIL"}
                    ]},
                },
            },
            "power_budget": {"total_ma": 900, "budget_ma": 500, "ok": False},
            "components": [],
        }
        with patch('services.pipeline.gate_logic._build_swap_suggestions_fn', return_value=[]):
            payload, suggestions = runner._p3_gate_payload(basic_job, bridge)
        assert payload is not None
        assert payload["phase"] == 3
        assert "over budget" in payload["issues"][0]
