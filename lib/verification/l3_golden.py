"""lib/verification/l3_golden.py — VS-L3 golden regression baseline.

Non-blocking layer. Loads a canned bridge, extracts key metrics,
compares against a stored baseline snapshot. Drift = WARN (not FAIL).

Metrics extracted:
  component_count     len(components)
  total_ma            power_budget.total_ma
  budget_ok           power_budget.ok
  bom_total_ntd       sum(bom[].total_ntd)
  enclosure_size      enclosure_constraints.target_size
  wall_thickness_mm   enclosure_constraints.wall_thickness_mm
  pin_count           cot_plan.total_pins
  wiring_nets         len(wiring)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .report import CheckResult, VerificationReport, Verdict

BASELINES_DIR = Path(__file__).resolve().parent / "baselines"


def extract_metrics(bridge: dict) -> Dict[str, Any]:
    """Extract comparable metrics from a bridge dict."""
    power = bridge.get("power_budget", {})
    enc = bridge.get("enclosure_constraints", {})
    bom = bridge.get("bom", [])
    cot = bridge.get("cot_plan", {})

    return {
        "component_count": len(bridge.get("components", [])),
        "total_ma": power.get("total_ma"),
        "budget_ok": power.get("ok"),
        "bom_total_ntd": sum(r.get("total_ntd", 0) for r in bom),
        "enclosure_size": enc.get("target_size"),
        "wall_thickness_mm": enc.get("wall_thickness_mm"),
        "pin_count": cot.get("total_pins"),
        "wiring_nets": len(bridge.get("wiring", {})),
    }


def save_baseline(name: str, metrics: Dict[str, Any]) -> Path:
    """Persist metrics as a golden baseline JSON file."""
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINES_DIR / f"{name}.json"
    path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_baseline(name: str) -> Optional[Dict[str, Any]]:
    """Load a previously saved baseline. Returns None if not found."""
    path = BASELINES_DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def compare_golden(
    bridge: dict,
    baseline_name: str,
    *,
    artifact_name: str | None = None,
) -> VerificationReport:
    """Compare bridge metrics against stored baseline.

    Each metric mismatch produces a WARN check (L3, non-blocking).
    If no baseline exists, all checks WARN with 'no baseline'.
    """
    rpt = VerificationReport(
        artifact=artifact_name or baseline_name,
        artifact_type="golden_regression",
    )
    current = extract_metrics(bridge)
    baseline = load_baseline(baseline_name)

    if baseline is None:
        rpt.add(CheckResult(
            "L3", "baseline_exists", Verdict.WARN,
            message=f"No baseline found for '{baseline_name}' -- run save_baseline first",
        ))
        return rpt

    rpt.add(CheckResult("L3", "baseline_exists", Verdict.PASS))

    for key, cur_val in current.items():
        base_val = baseline.get(key)
        if cur_val == base_val:
            rpt.add(CheckResult(
                "L3", f"golden_{key}", Verdict.PASS,
                metric={"value": cur_val},
            ))
        else:
            rpt.add(CheckResult(
                "L3", f"golden_{key}", Verdict.WARN,
                message=f"{key} drifted: baseline={base_val} current={cur_val}",
                metric={"baseline": base_val, "current": cur_val},
            ))

    return rpt
