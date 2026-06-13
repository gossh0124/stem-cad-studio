"""lib/ensemble_filter.py — CH4: Ensemble pre-filtering for LoRA-B candidates.

Generates N candidate assembly plans via LoRA-B temperature sampling,
scores each with lightweight geometric/printability rules, and returns
the top-scoring candidate. This avoids sending poor designs to the
downstream verification. (VLM REMOVED — Phase VI no longer exists)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger("cadhllm.ensemble_filter")

DEFAULT_N_CANDIDATES = 3
_ENV_KEY = "CADHLLM_ENSEMBLE_N"

# Scoring weights (total 100)
_W_SPATIAL   = 25.0
_W_CUTOUT    = 25.0
_W_PRINT     = 20.0
_W_THERMAL   = 15.0
_W_CLEARANCE = 15.0


def get_n_candidates() -> int:
    try:
        return max(1, int(os.environ.get(_ENV_KEY, DEFAULT_N_CANDIDATES)))
    except (TypeError, ValueError):
        return DEFAULT_N_CANDIDATES


def generate_candidates(
    bridge: dict,
    components: List[dict],
    n: int = 0,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    """Generate N LoRA-B candidate plans via temperature sampling.

    Each call to infer_plan_params uses do_sample=True with temperature=0.5,
    producing different outputs per call.
    """
    from lib.adapter_manager import infer_plan_params

    if n <= 0:
        n = get_n_candidates()

    candidates = []
    for i in range(n):
        try:
            result = infer_plan_params(bridge, components)
            compiled = result.get("compiled") or {}
            if compiled:
                candidates.append(result)
                if progress_cb:
                    progress_cb(f"  [Ensemble] 候選 {i+1}/{n} 生成完成")
            else:
                if progress_cb:
                    err = result.get("error", "empty compiled")
                    progress_cb(f"  [Ensemble] 候選 {i+1}/{n} 無效：{err}")
        except Exception as exc:
            _log.debug("Candidate %d failed: %s", i + 1, exc)
            if progress_cb:
                progress_cb(f"  [Ensemble] 候選 {i+1}/{n} 失敗：{exc}")
    return candidates


def score_candidate(
    candidate: dict,
    components: List[dict],
    registry: Optional[dict] = None,
) -> Tuple[float, Dict[str, float]]:
    """Score a candidate assembly plan using rule-based geometric checks.

    Returns (total_score, breakdown_dict) where total is 0-100. Solver-agnostic:
    scores the LoRA-B compiled plan + components + registry. (The former
    solver_result arg was vestigial — no scoring sub-fn read its placements — so it
    was removed during the V2 retirement; scoring is unchanged.)
    """
    compiled = candidate.get("compiled") or {}
    plan = candidate.get("plan") or {}

    spatial   = _score_spatial(compiled, components)
    cutout    = _score_cutout_alignment(compiled, components, registry)
    printing  = _score_printability(compiled, plan)
    thermal   = _score_thermal(compiled, components)
    clearance = _score_clearance(compiled)

    total = (
        spatial   * (_W_SPATIAL   / 25.0) +
        cutout    * (_W_CUTOUT    / 25.0) +
        printing  * (_W_PRINT     / 20.0) +
        thermal   * (_W_THERMAL   / 15.0) +
        clearance * (_W_CLEARANCE / 15.0)
    )
    breakdown = {
        "spatial": spatial,
        "cutout_alignment": cutout,
        "printability": printing,
        "thermal": thermal,
        "clearance": clearance,
    }
    return total, breakdown


def pre_filter(
    candidates: List[dict],
    components: List[dict],
    registry: Optional[dict] = None,
    top_k: int = 1,
) -> List[Tuple[dict, float, Dict[str, float]]]:
    """Score all candidates and return top-k as (candidate, score, breakdown)."""
    scored = []
    for c in candidates:
        total, bd = score_candidate(c, components, registry)
        scored.append((c, total, bd))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


# ── Scoring sub-functions (each returns 0-25 range) ──────────────────


def _score_spatial(compiled: dict, components: list) -> float:
    """Check if layout zones are unique and coverage is adequate."""
    score = 25.0
    layout = compiled.get("layout", [])

    zones = [item.get("zone", "") for item in layout if item.get("zone")]
    if zones:
        unique_ratio = len(set(zones)) / len(zones)
        if unique_ratio < 1.0:
            score -= 10.0 * (1.0 - unique_ratio)

    if not layout:
        score -= 5.0

    n_comps = len(components)
    n_assigned = len(layout)
    if n_comps > 0:
        coverage = min(n_assigned / n_comps, 1.0)
        if coverage < 0.5:
            score -= 8.0

    return max(0.0, score)


def _score_cutout_alignment(
    compiled: dict, components: list, registry: Optional[dict]
) -> float:
    """Check if face_out assignments match component port sides."""
    score = 25.0
    layout = compiled.get("layout", [])

    if not registry:
        try:
            from lib.registry import COMPONENT_REGISTRY
            registry = COMPONENT_REGISTRY
        except ImportError as exc:
            # registry is core infrastructure; an unscorable check must not
            # pass as a perfect score (always-green gate). Fail loud instead.
            raise RuntimeError(
                "_score_cutout_alignment cannot run: lib.registry import failed"
            ) from exc

    n_checked = 0
    n_aligned = 0
    for item in layout:
        comp_type = item.get("component", "")
        face_out = item.get("face_out", "")
        if not face_out or not comp_type:
            continue

        spec = registry.get(comp_type)
        if not spec or not spec.ports:
            continue

        side_ports = [p for p in spec.ports if p.side != "face"]
        if not side_ports:
            continue

        n_checked += 1
        dominant_side = max(
            set(p.side for p in side_ports),
            key=lambda s: sum(1 for p in side_ports if p.side == s),
        )
        _SIDE_TO_FACE = {
            "left": "side-left", "right": "side-right",
            "top": "side-back", "bottom": "side-front",
        }
        expected = _SIDE_TO_FACE.get(dominant_side, "")
        if face_out == expected or not expected:
            n_aligned += 1

    if n_checked > 0:
        ratio = n_aligned / n_checked
        score = 25.0 * ratio

    return max(0.0, score)


def _score_printability(compiled: dict, plan: dict) -> float:
    """Check wall thickness and joint method plausibility."""
    score = 20.0

    joints = compiled.get("joints", {}) or plan.get("joints", {})
    lid_method = joints.get("lid_method", "")
    if not lid_method:
        score -= 3.0

    return max(0.0, min(20.0, score))


def _score_thermal(compiled: dict, components: list) -> float:
    """Check if high-thermal components have thermal strategy."""
    score = 15.0

    try:
        from lib.specs import THERMAL_MW
    except ImportError as exc:
        # A missing thermal model must not inflate scores to full marks
        # (always-green gate). Fail loud instead of silently disabling the check.
        raise RuntimeError(
            "_score_thermal cannot run: lib.specs.THERMAL_MW import failed"
        ) from exc

    hot_types = {c.get("type", "") for c in components
                 if THERMAL_MW.get(c.get("type", ""), 0) >= 500}

    if not hot_types:
        return score

    thermal = compiled.get("thermal", {})
    if thermal.get("strategy"):
        return score
    elif thermal.get("vent_placement"):
        return score - 3.0
    else:
        score -= 8.0

    return max(0.0, score)


def _score_clearance(compiled: dict) -> float:
    """Check if layout has reasonable spacing (no packing anomalies)."""
    score = 15.0
    layout = compiled.get("layout", [])

    if not layout:
        return max(0.0, score - 5.0)

    cable = compiled.get("cable_routing", {})
    if cable and cable.get("path"):
        score = min(score, 15.0)
    elif len(layout) > 3 and not cable:
        score -= 4.0

    return max(0.0, score)
