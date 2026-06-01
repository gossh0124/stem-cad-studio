"""tests/test_verification_report.py -- VerificationReport / CheckResult / gate 單元測試。"""
from __future__ import annotations

import json
import pytest

from lib.verification.report import (
    Verdict,
    BLOCKING_LAYERS,
    CheckResult,
    VerificationReport,
    gate,
)


# ================================================================
# Verdict enum
# ================================================================

class TestVerdict:
    def test_values(self):
        assert Verdict.PASS.value == "PASS"
        assert Verdict.FAIL.value == "FAIL"
        assert Verdict.WARN.value == "WARN"

    def test_is_str_subclass(self):
        assert isinstance(Verdict.PASS, str)

    def test_equality_with_str(self):
        assert Verdict.PASS == "PASS"


# ================================================================
# BLOCKING_LAYERS
# ================================================================

class TestBlockingLayers:
    def test_contains_l0_l1(self):
        assert "L0" in BLOCKING_LAYERS
        assert "L1" in BLOCKING_LAYERS

    def test_not_contains_l2_l3(self):
        assert "L2" not in BLOCKING_LAYERS
        assert "L3" not in BLOCKING_LAYERS

    def test_is_frozenset(self):
        assert isinstance(BLOCKING_LAYERS, frozenset)


# ================================================================
# CheckResult
# ================================================================

class TestCheckResult:
    def test_defaults(self):
        cr = CheckResult(layer="L0", name="exists", verdict=Verdict.PASS)
        assert cr.metric == {}
        assert cr.threshold is None
        assert cr.message == ""
        assert cr.evidence is None

    def test_is_blocking_fail_l0(self):
        cr = CheckResult(layer="L0", name="file_exists", verdict=Verdict.FAIL)
        assert cr.is_blocking_fail is True

    def test_is_blocking_fail_l1(self):
        cr = CheckResult(layer="L1", name="netlist", verdict=Verdict.FAIL)
        assert cr.is_blocking_fail is True

    def test_not_blocking_fail_l2(self):
        cr = CheckResult(layer="L2", name="overlap", verdict=Verdict.FAIL)
        assert cr.is_blocking_fail is False

    def test_not_blocking_fail_l3(self):
        cr = CheckResult(layer="L3", name="golden", verdict=Verdict.FAIL)
        assert cr.is_blocking_fail is False

    def test_pass_is_never_blocking(self):
        cr = CheckResult(layer="L0", name="ok", verdict=Verdict.PASS)
        assert cr.is_blocking_fail is False

    def test_warn_is_never_blocking(self):
        cr = CheckResult(layer="L1", name="w", verdict=Verdict.WARN)
        assert cr.is_blocking_fail is False

    def test_metric_preserved(self):
        cr = CheckResult(layer="L0", name="tris", verdict=Verdict.PASS,
                         metric={"n_faces": 5000, "variance": 1.2})
        assert cr.metric["n_faces"] == 5000
        assert cr.metric["variance"] == pytest.approx(1.2)


# ================================================================
# VerificationReport -- verdict aggregation
# ================================================================

class TestVerificationReportVerdict:
    def _make_report(self, checks: list[CheckResult]) -> VerificationReport:
        r = VerificationReport(artifact="test.stl", artifact_type="mesh")
        for c in checks:
            r.add(c)
        return r

    def test_all_pass(self):
        r = self._make_report([
            CheckResult("L0", "a", Verdict.PASS),
            CheckResult("L1", "b", Verdict.PASS),
        ])
        assert r.verdict == Verdict.PASS

    def test_l0_fail_makes_overall_fail(self):
        r = self._make_report([
            CheckResult("L0", "missing", Verdict.FAIL),
            CheckResult("L1", "ok", Verdict.PASS),
        ])
        assert r.verdict == Verdict.FAIL

    def test_l1_fail_makes_overall_fail(self):
        r = self._make_report([
            CheckResult("L0", "ok", Verdict.PASS),
            CheckResult("L1", "netlist", Verdict.FAIL),
        ])
        assert r.verdict == Verdict.FAIL

    def test_l2_fail_does_not_block(self):
        r = self._make_report([
            CheckResult("L0", "ok", Verdict.PASS),
            CheckResult("L2", "overlap", Verdict.FAIL),
        ])
        assert r.verdict == Verdict.PASS

    def test_l3_fail_does_not_block(self):
        r = self._make_report([
            CheckResult("L0", "ok", Verdict.PASS),
            CheckResult("L3", "golden", Verdict.FAIL),
        ])
        assert r.verdict == Verdict.PASS

    def test_has_nonblocking_fail(self):
        r = self._make_report([
            CheckResult("L0", "ok", Verdict.PASS),
            CheckResult("L2", "overlap", Verdict.FAIL),
        ])
        assert r.has_nonblocking_fail is True

    def test_no_nonblocking_fail(self):
        r = self._make_report([
            CheckResult("L0", "ok", Verdict.PASS),
            CheckResult("L1", "ok", Verdict.PASS),
        ])
        assert r.has_nonblocking_fail is False

    def test_empty_report_is_pass(self):
        r = VerificationReport(artifact="x", artifact_type="y")
        assert r.verdict == Verdict.PASS


# ================================================================
# VerificationReport -- counts / exit_code
# ================================================================

class TestReportCounts:
    def test_counts_basic(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        r.add(CheckResult("L0", "a", Verdict.PASS))
        r.add(CheckResult("L1", "b", Verdict.FAIL))
        r.add(CheckResult("L2", "c", Verdict.WARN))
        c = r.counts()
        assert c == {"PASS": 1, "FAIL": 1, "WARN": 1}

    def test_counts_empty(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        assert r.counts() == {"PASS": 0, "FAIL": 0, "WARN": 0}

    def test_exit_code_pass(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        r.add(CheckResult("L0", "ok", Verdict.PASS))
        assert r.exit_code() == 0

    def test_exit_code_blocking_fail(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        r.add(CheckResult("L0", "missing", Verdict.FAIL))
        assert r.exit_code() == 1

    def test_exit_code_nonblocking_fail_normal(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        r.add(CheckResult("L2", "visual", Verdict.FAIL))
        assert r.exit_code() == 0

    def test_exit_code_nonblocking_fail_strict(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        r.add(CheckResult("L2", "visual", Verdict.FAIL))
        assert r.exit_code(strict=True) == 1


# ================================================================
# VerificationReport -- extend / add
# ================================================================

class TestReportExtend:
    def test_add_returns_check(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        cr = CheckResult("L0", "x", Verdict.PASS)
        ret = r.add(cr)
        assert ret is cr

    def test_extend_adds_multiple(self):
        r = VerificationReport(artifact="a", artifact_type="b")
        checks = [
            CheckResult("L0", "a", Verdict.PASS),
            CheckResult("L1", "b", Verdict.WARN),
        ]
        r.extend(checks)
        assert len(r.checks) == 2


# ================================================================
# VerificationReport -- serialization
# ================================================================

class TestReportSerialization:
    def _sample_report(self) -> VerificationReport:
        r = VerificationReport(artifact="model.stl", artifact_type="mesh")
        r.add(CheckResult("L0", "file_exists", Verdict.PASS,
                          metric={"size_bytes": 1024}))
        r.add(CheckResult("L1", "watertight", Verdict.FAIL,
                          message="3 holes found"))
        return r

    def test_to_dict_keys(self):
        d = self._sample_report().to_dict()
        assert set(d.keys()) == {"artifact", "artifact_type", "verdict",
                                 "counts", "checks"}

    def test_to_dict_verdict_reflects_fail(self):
        d = self._sample_report().to_dict()
        assert d["verdict"] == "FAIL"

    def test_to_dict_checks_length(self):
        d = self._sample_report().to_dict()
        assert len(d["checks"]) == 2

    def test_to_json_is_valid(self):
        j = self._sample_report().to_json()
        parsed = json.loads(j)
        assert parsed["artifact"] == "model.stl"

    def test_to_json_indent(self):
        j = self._sample_report().to_json(indent=4)
        assert "\n    " in j

    def test_render_text_contains_artifact_name(self):
        txt = self._sample_report().render_text()
        assert "model.stl" in txt
        assert "mesh" in txt

    def test_render_text_contains_layer_names(self):
        txt = self._sample_report().render_text()
        assert "L0" in txt
        assert "L1" in txt

    def test_render_text_contains_counts_summary(self):
        txt = self._sample_report().render_text()
        assert "1 pass" in txt
        assert "1 fail" in txt

    def test_render_text_contains_metric(self):
        txt = self._sample_report().render_text()
        assert "size_bytes=1024" in txt


# ================================================================
# gate()
# ================================================================

class TestGate:
    def test_gate_pass(self, capsys):
        r = VerificationReport(artifact="ok.svg", artifact_type="svg")
        r.add(CheckResult("L0", "exists", Verdict.PASS))
        code = gate(r)
        assert code == 0

    def test_gate_fail(self, capsys):
        r = VerificationReport(artifact="bad.svg", artifact_type="svg")
        r.add(CheckResult("L0", "missing", Verdict.FAIL))
        code = gate(r)
        assert code == 1
        captured = capsys.readouterr()
        assert "exit 1" in captured.out

    def test_gate_strict(self, capsys):
        r = VerificationReport(artifact="warn.svg", artifact_type="svg")
        r.add(CheckResult("L2", "visual", Verdict.FAIL))
        assert gate(r, strict=False) == 0
        assert gate(r, strict=True) == 1
