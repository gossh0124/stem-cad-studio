"""tests/test_shared_models.py — STR17: services/shared 基礎設施測試。

覆蓋：models.py (Job, PhaseResult, JobStatus, PhaseID)
     constants.py (truncate_issues, re-exports)
"""
from __future__ import annotations
import time
import pytest

from services.shared.models import Job, JobStatus, PhaseID, PhaseResult
from services.shared.constants import (
    POWER_MA,
    PRICE_NTD,
    truncate_issues,
    lookup_constant,
    resolve_component_alias,
)


# ── JobStatus ────────────────────────────────────────────────

class TestJobStatus:
    def test_enum_values(self):
        assert JobStatus.PENDING.value == "pending"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.SUCCESS.value == "success"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELLED.value == "cancelled"

    def test_str_enum(self):
        assert str(JobStatus.PENDING) == "JobStatus.PENDING"
        assert JobStatus.PENDING == "pending"

    def test_all_statuses_exist(self):
        expected = {"pending", "running", "waiting_clarify", "waiting_hitl",
                    "success", "failed", "cancelled"}
        actual = {s.value for s in JobStatus}
        assert actual == expected


# ── PhaseID ──────────────────────────────────────────────────

class TestPhaseID:
    def test_seven_phases(self):
        assert len(PhaseID) == 7
        assert PhaseID.P1.value == 1
        assert PhaseID.P7.value == 7

    def test_int_enum(self):
        assert PhaseID.P3 + 1 == 4


# ── PhaseResult ──────────────────────────────────────────────

class TestPhaseResult:
    def test_create_default(self):
        pr = PhaseResult(phase=PhaseID.P1, status=JobStatus.RUNNING)
        assert pr.ended_at is None
        assert pr.duration_s() is None
        assert pr.artifacts == {}
        assert pr.error is None

    def test_finish_updates_fields(self):
        pr = PhaseResult(phase=PhaseID.P2, status=JobStatus.RUNNING,
                         started_at=time.time() - 1.0)
        pr.finish(JobStatus.SUCCESS, artifacts={"key": "val"}, error=None)
        assert pr.status == JobStatus.SUCCESS
        assert pr.ended_at is not None
        assert pr.artifacts == {"key": "val"}
        dur = pr.duration_s()
        assert dur is not None and dur >= 0.9

    def test_finish_with_error(self):
        pr = PhaseResult(phase=PhaseID.P4, status=JobStatus.RUNNING)
        pr.finish(JobStatus.FAILED, error="boom")
        assert pr.error == "boom"
        assert pr.status == JobStatus.FAILED

    def test_artifacts_merge(self):
        pr = PhaseResult(phase=PhaseID.P3, status=JobStatus.RUNNING,
                         artifacts={"a": 1})
        pr.finish(JobStatus.SUCCESS, artifacts={"b": 2})
        assert pr.artifacts == {"a": 1, "b": 2}


# ── Job ──────────────────────────────────────────────────────

class TestJob:
    def test_defaults(self):
        j = Job()
        assert j.status == JobStatus.PENDING
        assert j.saved is False
        assert len(j.job_id) == 36  # UUID format

    def test_touch_updates_timestamp(self):
        j = Job()
        old = j.updated_at
        time.sleep(0.01)
        j.touch()
        assert j.updated_at > old

    def test_to_dict_structure(self):
        j = Job(project_name="test", instruction="build LED")
        d = j.to_dict()
        assert d["project_name"] == "test"
        assert d["instruction"] == "build LED"
        assert d["status"] == "pending"
        assert isinstance(d["phase_results"], list)
        assert "created_at" in d
        assert "saved" in d

    def test_to_dict_with_phase_results(self):
        j = Job()
        pr = PhaseResult(phase=PhaseID.P1, status=JobStatus.SUCCESS,
                         started_at=1000.0, ended_at=1002.5)
        j.phase_results.append(pr)
        d = j.to_dict()
        assert len(d["phase_results"]) == 1
        pr_d = d["phase_results"][0]
        assert pr_d["phase"] == 1
        assert pr_d["status"] == "success"
        assert pr_d["duration_s"] == 2.5

    def test_to_dict_roundtrip_keys(self):
        j = Job()
        d = j.to_dict()
        expected_keys = {
            "job_id", "project_name", "instruction", "status",
            "current_phase",
            "created_at", "updated_at", "error", "saved", "phase_results",
        }
        assert set(d.keys()) == expected_keys


# ── constants.py ─────────────────────────────────────────────

class TestTruncateIssues:
    def test_under_limit(self):
        assert truncate_issues(["a", "b"], limit=5) == ["a", "b"]

    def test_at_limit(self):
        items = list(range(5))
        assert truncate_issues(items, limit=5) == items

    def test_over_limit(self):
        items = list(range(10))
        result = truncate_issues(items, limit=3)
        assert len(result) == 4
        assert result[:3] == [0, 1, 2]
        assert "7" in result[3]

    def test_empty(self):
        assert truncate_issues([]) == []


class TestReExports:
    def test_power_ma_dict(self):
        assert isinstance(POWER_MA, dict)
        assert len(POWER_MA) > 20

    def test_price_ntd_dict(self):
        assert isinstance(PRICE_NTD, dict)
        assert len(PRICE_NTD) > 10

    def test_lookup_constant(self):
        val = lookup_constant(POWER_MA, "Arduino-Uno-class", None)
        assert val is not None
        assert isinstance(val, (int, float))

    def test_resolve_alias(self):
        resolved = resolve_component_alias("LED")
        assert resolved is not None
