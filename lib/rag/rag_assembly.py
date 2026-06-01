"""rag_assembly.py — Assembly/wiring RAG (Collection 3: Assembly).

Handles:
  - Adding successful Phase IV assembly decisions to vector DB
  - Semantic search over historical assembly decisions
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .rag_embedding import (
    COLL_ASSEMBLY,
    DISTANCE_THRESHOLDS,
    _get_db,
    _sanitize_filter,
    embed_text,
)

_log = logging.getLogger("cadhllm.rag")


def _assembly_to_text(plan: dict, bridge: dict) -> str:
    """Convert assembly decision to embedding text."""
    name = bridge.get("project_name", "")
    cat = bridge.get("project_category", "")
    rationale = plan.get("placement_rationale", "")
    layout = plan.get("layout", [])
    layout_str = ", ".join(
        f"{item.get('component', '')}@{item.get('zone', '')}"
        for item in layout
    )
    thermal = plan.get("thermal", {})
    strategy = thermal.get("strategy", "none")
    joints = plan.get("joints", {})
    lid = joints.get("lid_method", "")
    return (
        f"{name} ({cat}) | "
        f"layout: {layout_str} | "
        f"thermal: {strategy} | joints: {lid} | "
        f"rationale: {rationale[:200]}"
    )


def add_assembly(plan: dict, bridge: dict, assembly_id: Optional[str] = None):
    """Add a successful assembly decision to assembly collection."""
    db = _get_db()

    text = _assembly_to_text(plan, bridge)
    vec = embed_text(text)

    components = bridge.get("components", [])
    total_weight = sum(c.get("spec", {}).get("weight_g", 10.0) for c in components)
    total_thermal = sum(c.get("spec", {}).get("thermal_mw", 0.0) for c in components)

    record = {
        "assembly_id": assembly_id or bridge.get("project_name", "unknown"),
        "project_name": bridge.get("project_name", ""),
        "project_category": bridge.get("project_category", ""),
        "text": text,
        "vector": vec,
        "total_weight_g": total_weight,
        "total_thermal_mw": total_thermal,
        "thermal_strategy": plan.get("thermal", {}).get("strategy", "none"),
        "lid_method": plan.get("joints", {}).get("lid_method", ""),
        "plan_json": json.dumps(plan, ensure_ascii=False),
    }

    try:
        tbl = db.open_table(COLL_ASSEMBLY)
        tbl.add([record])
    except Exception:
        try:
            db.create_table(COLL_ASSEMBLY, data=[record])
        except Exception as e2:
            _log.warning("Assembly write failed: %s", e2)

    _log.info("Assembly decision indexed: %s", record["project_name"])


def search_assembly(
    query: str,
    top_k: int = 3,
    category_filter: Optional[str] = None,
    thermal_strategy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search most similar historical assembly decisions."""
    db = _get_db()
    try:
        tbl = db.open_table(COLL_ASSEMBLY)
    except Exception:
        return []

    q_vec = embed_text(query)
    search = tbl.search(q_vec).limit(top_k)

    where_clauses = []
    if category_filter:
        where_clauses.append(f"project_category = '{_sanitize_filter(category_filter)}'")
    if thermal_strategy:
        where_clauses.append(f"thermal_strategy = '{_sanitize_filter(thermal_strategy)}'")
    if where_clauses:
        search = search.where(" AND ".join(where_clauses))

    results = search.to_list()

    # Distance threshold filtering — discard low-quality matches
    max_dist = DISTANCE_THRESHOLDS.get(COLL_ASSEMBLY, 1.4)
    results = [r for r in results if r.get("_distance", 0.0) <= max_dist]

    out = []
    for r in results:
        try:
            plan = json.loads(r.get("plan_json", "{}"))
        except Exception:
            plan = {}
        out.append({
            "assembly_id": r.get("assembly_id", ""),
            "project_name": r.get("project_name", ""),
            "project_category": r.get("project_category", ""),
            "thermal_strategy": r.get("thermal_strategy", ""),
            "lid_method": r.get("lid_method", ""),
            "plan": plan,
            "score": r.get("_distance", 0.0),
        })
    return out
