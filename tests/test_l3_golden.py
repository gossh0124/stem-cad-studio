"""tests/test_l3_golden.py — VS-L3 golden regression tests.

Uses auto_waterer canned bridge as first golden baseline.
"""
import json
import copy
from pathlib import Path

import pytest

from lib.verification.l3_golden import (
    extract_metrics,
    compare_golden,
    load_baseline,
)
from lib.verification.report import Verdict

_CANNED_DIR = Path(__file__).resolve().parent.parent / "v6" / "canned"


def _load_bridge(name: str) -> dict:
    path = _CANNED_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── extract_metrics ────────────────────────────────────────────

class TestExtractMetrics:
    def test_auto_waterer_component_count(self):
        bridge = _load_bridge("auto_waterer")
        m = extract_metrics(bridge)
        assert m["component_count"] == 5

    def test_auto_waterer_power(self):
        bridge = _load_bridge("auto_waterer")
        m = extract_metrics(bridge)
        assert m["total_ma"] == 355.0
        assert m["budget_ok"] is True

    def test_auto_waterer_bom_total(self):
        bridge = _load_bridge("auto_waterer")
        m = extract_metrics(bridge)
        assert m["bom_total_ntd"] == 560

    def test_empty_bridge(self):
        m = extract_metrics({})
        assert m["component_count"] == 0
        assert m["total_ma"] is None
        assert m["bom_total_ntd"] == 0


# ── compare_golden ─────────────────────────────────────────────

class TestCompareGolden:
    def test_auto_waterer_matches_baseline(self):
        bridge = _load_bridge("auto_waterer")
        rpt = compare_golden(bridge, "auto_waterer")
        assert rpt.verdict == Verdict.PASS
        warns = [c for c in rpt.checks if c.verdict == Verdict.WARN]
        assert len(warns) == 0, f"Unexpected drift: {[c.name for c in warns]}"

    def test_drift_detected(self):
        bridge = _load_bridge("auto_waterer")
        bridge = copy.deepcopy(bridge)
        bridge["components"].append({"role": "Sensor", "type": "DHT22-class", "qty": 1})
        rpt = compare_golden(bridge, "auto_waterer")
        drift_names = [c.name for c in rpt.checks if c.verdict == Verdict.WARN]
        assert "golden_component_count" in drift_names

    def test_missing_baseline_warns(self):
        bridge = _load_bridge("auto_waterer")
        rpt = compare_golden(bridge, "nonexistent_project_xyz")
        assert any(c.name == "baseline_exists" and c.verdict == Verdict.WARN
                   for c in rpt.checks)

    def test_baseline_exists_check(self):
        baseline = load_baseline("auto_waterer")
        assert baseline is not None
        assert baseline["component_count"] == 5
