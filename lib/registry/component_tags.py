"""component_tags.py — Tag system, validation, and search/filter helpers.

Contains: _split_tags, _validate_tags, find_equivalent.
"""
from __future__ import annotations
from typing import Dict, List

from .component_spec import (
    ComponentSpec,
    TAG_VOCAB_AXIS1,
    TAG_VOCAB_AXIS2_PREFIXES,
)
from .registry_data import COMPONENT_REGISTRY


# ── Tag classification helper ──────────────────────────────────────

def _split_tags(tags: List[str]) -> tuple[set[str], set[str]]:
    """Return (axis1_tags, axis2_tags)."""
    ax1 = {t for t in tags if t in TAG_VOCAB_AXIS1}
    ax2 = {t for t in tags
           if any(t.startswith(p) for p in TAG_VOCAB_AXIS2_PREFIXES)}
    return ax1, ax2


# ── U1 Tags completeness validation (fail fast on import) ─────────

def _validate_tags() -> None:
    for _cn, _spec in COMPONENT_REGISTRY.items():
        _ax1, _ax2 = _split_tags(_spec.tags)
        _unknown = set(_spec.tags) - _ax1 - _ax2
        if not _ax1:
            raise ValueError(
                f"{_cn}: missing axis 1 (interface) tag, must choose from TAG_VOCAB_AXIS1 "
                f"(current tags={_spec.tags})")
        if not _ax2:
            raise ValueError(
                f"{_cn}: missing axis 2 (function) tag, prefix must be in TAG_VOCAB_AXIS2_PREFIXES "
                f"(current tags={_spec.tags})")
        if _unknown:
            raise ValueError(
                f"{_cn}: unknown tag {_unknown} -- axis 1 must be in fixed vocab, "
                f"axis 2 must start with {sorted(TAG_VOCAB_AXIS2_PREFIXES)}")


_validate_tags()


# ── U2 Equivalent lookup ──────────────────────────────────────────

def find_equivalent(
    target_class: str,
    role_candidates: List[str],
    *,
    voltage_tol: float = 0.5,
    registry: Dict[str, "ComponentSpec"] | None = None,
) -> List[str]:
    """Find equivalents of target among role_candidates, sorted by footprint similarity.

    Hard constraints (all must pass):
      1. Both axis tags have >= 1 overlap
      2. |voltage_v diff| <= voltage_tol
      3. target.current_ma <= candidate.current_ma
    Soft sort: footprint area ratio (closer to 1 is better).
    """
    reg = registry or COMPONENT_REGISTRY
    target = reg.get(target_class)
    if target is None:
        return []

    t_ax1, t_ax2 = _split_tags(target.tags)

    matches: list[tuple[float, str]] = []
    for cn in role_candidates:
        if cn == target_class:
            continue
        cand = reg.get(cn)
        if cand is None:
            continue
        c_ax1, c_ax2 = _split_tags(cand.tags)
        if not (t_ax1 & c_ax1):
            continue
        if not (t_ax2 & c_ax2):
            continue
        if abs(cand.voltage_v - target.voltage_v) > voltage_tol:
            continue
        if target.current_ma > cand.current_ma:
            continue
        t_area = target.footprint_area() or 1.0
        c_area = cand.footprint_area() or 1.0
        score = abs(c_area / t_area - 1.0)
        matches.append((score, cn))

    matches.sort()
    return [cn for _, cn in matches]
