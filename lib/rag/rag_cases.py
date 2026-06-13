"""rag_cases.py — Project case RAG (Collection 2: Cases).

Handles:
  - Adding successful Phase I cases to vector DB
  - Semantic search over historical cases
  - HyDE (Hypothetical Document Embedding) search
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .rag_embedding import (
    COLL_CASES,
    DISTANCE_THRESHOLDS,
    _get_db,
    _sanitize_filter,
    embed_text,
)

_log = logging.getLogger("cadhllm.rag")


def _bridge_to_case_text(bridge: dict) -> str:
    """Convert bridge JSON to case embedding text."""
    name = bridge.get("project_name", "")
    cat = bridge.get("project_category", "")
    plan = bridge.get("cot_plan", {}).get("high_level_plan", "")
    components = bridge.get("components", [])
    comp_str = ", ".join(
        f"{c.get('role', '')}:{c.get('type', '')}" for c in components
    )
    instruction = bridge.get("_instruction", "")
    return (
        f"{name} ({cat}) | "
        f"plan: {plan[:200]} | "
        f"components: {comp_str} | "
        f"instruction: {instruction[:200]}"
    )


def add_case(bridge: dict, case_id: Optional[str] = None):
    """Add a successful case to cases collection (with dedup)."""
    db = _get_db()
    cid = case_id or bridge.get("project_name", "unknown")
    pname = bridge.get("project_name", "")

    try:
        tbl = db.open_table(COLL_CASES)
        existing = tbl.search().where(
            f"case_id = '{_sanitize_filter(cid)}' AND "
            f"project_name = '{_sanitize_filter(pname)}'"
        ).limit(1).to_list()
        if existing:
            _log.info("Case already exists, skipping: %s (%s)", pname, cid)
            return
    except Exception as exc:
        _log.debug("Case dedup check failed (will insert): %s", exc)

    text = _bridge_to_case_text(bridge)
    vec = embed_text(text)

    record = {
        "case_id": cid,
        "project_name": pname,
        "project_category": bridge.get("project_category", ""),
        "text": text,
        "vector": vec,
        "components_json": json.dumps(
            bridge.get("components", []), ensure_ascii=False
        ),
        "bridge_json": json.dumps(bridge, ensure_ascii=False, default=str),
    }

    try:
        tbl = db.open_table(COLL_CASES)
        tbl.add([record])
    except Exception as exc:
        _log.debug("Case table open failed, creating: %s", exc)
        try:
            db.create_table(COLL_CASES, data=[record])
        except Exception as e2:
            # No-Silent-Fallback: a doubly-failed write must not be reported
            # as "Case indexed". Surface the failure to the caller.
            _log.error("Case write failed: %s", e2)
            raise RuntimeError(
                f"Failed to index case {record['case_id']!r} "
                f"({record['project_name']!r}): {e2}"
            ) from e2

    _log.info("Case indexed: %s (%s)", record["project_name"], record["case_id"])


def _dedup_by_project_name(
    rows: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """按 project_name 去重，每個專案只保留 _distance 最小（分數最佳）的那筆，
    最後回傳前 top_k 筆。

    此函式為純函數（不依賴 DB），可直接單元測試。

    Args:
        rows: 原始搜尋結果（每筆含 _distance / project_name 等欄位）。
        top_k: 最終回傳筆數上限。

    Returns:
        去重後前 top_k 筆，依 _distance 升冪排列。
    """
    seen: dict[str, dict] = {}
    for r in rows:
        pname = r.get("project_name", "")
        dist = r.get("_distance", float("inf"))
        if pname not in seen or dist < seen[pname].get("_distance", float("inf")):
            seen[pname] = r
    deduped = sorted(seen.values(), key=lambda r: r.get("_distance", float("inf")))
    return deduped[:top_k]


def search_cases(
    query: str,
    top_k: int = 3,
    category_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜尋最相似的歷史案例，並按 project_name 去重。

    synthetic 與 canned 可能有相同 project_name（例如 auto_waterer_demo），
    為避免回傳重複專案，先多取 top_k*4 筆候選，再按 project_name 去重，
    每個專案只保留 _distance 最小者，最後裁回 top_k。

    回傳結構與原版相同：list of {case_id, project_name, project_category,
    components, score}。
    """
    db = _get_db()
    try:
        tbl = db.open_table(COLL_CASES)
    except Exception as exc:
        _log.warning("Cases table not available: %s", exc)
        return []

    q_vec = embed_text(query)
    candidate_limit = max(top_k * 4, 20)
    search = tbl.search(q_vec).limit(candidate_limit)
    if category_filter:
        search = search.where(f"project_category = '{_sanitize_filter(category_filter)}'")

    raw_rows = search.to_list()

    # Distance threshold filtering — discard low-quality matches
    max_dist = DISTANCE_THRESHOLDS.get(COLL_CASES, 1.4)
    raw_rows = [r for r in raw_rows if r.get("_distance", 0.0) <= max_dist]

    deduped = _dedup_by_project_name(raw_rows, top_k)

    out = []
    for r in deduped:
        try:
            comps = json.loads(r.get("components_json", "[]"))
        except Exception as exc:
            _log.debug("components_json parse failed for %s: %s", r.get("case_id", "?"), exc)
            comps = []
        out.append({
            "case_id": r.get("case_id", ""),
            "project_name": r.get("project_name", ""),
            "project_category": r.get("project_category", ""),
            "components": comps,
            "score": r.get("_distance", 0.0),
        })
    return out


# ════════════════════════════════════════════════════════════════
# HyDE (Hypothetical Document Embedding)
# ════════════════════════════════════════════════════════════════

def hyde_search_cases(
    instruction: str,
    hypothetical_components: List[dict],
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """HyDE search: use hypothetical component list for embedding, retrieve real cases.

    When user input is vague (e.g. "make an auto-watering system"), Phase I
    quickly guesses component list, then uses this hypothetical doc for more
    precise retrieval.
    """
    comp_str = ", ".join(
        f"{c.get('role', '')}:{c.get('type', '')}" for c in hypothetical_components
    )
    hyde_text = f"{instruction} | components: {comp_str}"
    return search_cases(hyde_text, top_k=top_k)
