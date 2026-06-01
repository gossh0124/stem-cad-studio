"""pipeline/complement_engine.py — 互補元件建議引擎。

根據目前 bridge 的元件清單，從 RAG cases collection 檢索相似的歷史專案，
統計這些相似專案中頻繁出現但目前 bridge 缺少的元件，回傳建議清單。

純檢索 + 頻率統計，不呼叫 LLM。
與 swap_engine.py 平行，屬 pipeline 補足功能層。
"""
from __future__ import annotations

from typing import List, Optional

# ── 基礎角色排除清單 ──────────────────────────────────────────────
# Brain / Power / Control 幾乎每個專案都有，頻率接近 1.0，
# 不具備「你漏掉了這個」的建議意義，一律排除。
_EXCLUDED_ROLES = frozenset({"Brain", "Power", "Control"})


def _build_query(bridge: dict) -> str:
    """將 bridge 關鍵欄位組成 RAG query 字串。

    仿照 rag_cases._bridge_to_case_text 格式，讓向量距離最大化相關。
    """
    name = bridge.get("project_name", "")
    cat = bridge.get("project_category", "")
    comps = bridge.get("components", [])
    comp_str = ", ".join(
        f"{c.get('role', '')}:{c.get('type', '')}" for c in comps
    )
    return f"{name} ({cat}) | components: {comp_str}"


def suggest_complements(
    bridge: dict,
    top_k_cases: int = 5,
    max_suggestions: int = 3,
) -> List[dict]:
    """給定目前 bridge，建議學生漏掉但相似專案常見的元件。

    Parameters
    ----------
    bridge:
        目前 Phase I 輸出的 bridge dict（含 components 清單）。
    top_k_cases:
        要從 RAG 檢索幾個相似歷史專案。
    max_suggestions:
        最多回傳幾筆建議。

    Returns
    -------
    list[dict]
        每筆格式：
        {
            "type": str,           # 元件 class type
            "role": str,           # 元件角色（來自出現次數最多的 case）
            "frequency": float,    # 0..1，含此 type 的 case 比例
            "reason": str,         # 人讀原因說明
            "seen_in": list[str],  # 含此 type 的專案名稱清單
        }

    Notes
    -----
    邊界條件：
    - 若 RAG 回傳 0 筆 → 回傳 []（合法）
    - 若候選不足 max_suggestions → 回傳現有的
    - 若 lib.rag import 失敗 → raise ImportError（禁止靜默 fallback）
    """
    # ── Import 失敗要明確 raise，不能靜默回 [] ──────────────────
    try:
        from lib.rag import search_cases
    except Exception as exc:
        raise ImportError(
            f"complement_engine: 無法 import lib.rag.search_cases — {exc}"
        ) from exc

    # ── 組 query ──────────────────────────────────────────────────
    query = _build_query(bridge)
    category: Optional[str] = bridge.get("project_category")

    # ── 目前已有的 type 集合（用來差集排除） ─────────────────────
    current_types: frozenset[str] = frozenset(
        c.get("type", "") for c in bridge.get("components", [])
    )

    # ── 目前 bridge 內所有角色（排除 Brain/Power/Control 無論新舊）
    # 額外也排除 bridge 本身的角色中屬於 excluded 的 type
    excluded_types_by_role: frozenset[str] = frozenset(
        c.get("type", "")
        for c in bridge.get("components", [])
        if c.get("role", "") in _EXCLUDED_ROLES
    )

    # ── 呼叫 RAG ─────────────────────────────────────────────────
    cases = search_cases(query, top_k=top_k_cases, category_filter=category)
    n_cases = len(cases)
    if n_cases == 0:
        return []

    # ── 統計各 type 出現狀況 ──────────────────────────────────────
    # type_stats[type] = {
    #   "count": int,           # 幾個 case 含此 type
    #   "role_votes": {role: count},
    #   "seen_in": [project_name, ...],
    # }
    type_stats: dict[str, dict] = {}

    for case in cases:
        project_name = case.get("project_name", "")
        case_category = case.get("project_category", "")
        seen_types_this_case: set[str] = set()

        for comp in case.get("components", []):
            ctype = comp.get("type", "")
            crole = comp.get("role", "")
            if not ctype:
                continue
            # 每個 case 內同 type 只計算一次
            if ctype in seen_types_this_case:
                continue
            seen_types_this_case.add(ctype)

            if ctype not in type_stats:
                type_stats[ctype] = {
                    "count": 0,
                    "role_votes": {},
                    "seen_in": [],
                    "category": case_category,
                }
            stat = type_stats[ctype]
            stat["count"] += 1
            stat["role_votes"][crole] = stat["role_votes"].get(crole, 0) + 1
            stat["seen_in"].append(project_name)

    # ── 過濾 + 計算 frequency ─────────────────────────────────────
    candidates = []
    for ctype, stat in type_stats.items():
        # 排除 1：已在 bridge 裡的 type
        if ctype in current_types:
            continue
        # 排除 2：來自 Brain/Power/Control 角色的 type（即使在 cases 中出現）
        # 判斷依據：votes 最高角色屬於 _EXCLUDED_ROLES
        top_role = max(stat["role_votes"], key=stat["role_votes"].get)
        if top_role in _EXCLUDED_ROLES:
            continue

        frequency = stat["count"] / n_cases
        cat_label = bridge.get("project_category") or stat.get("category", "")
        reason = (
            f"在 {n_cases} 個相似的{cat_label}專案中有 {stat['count']} 個包含此元件"
        )

        candidates.append({
            "type": ctype,
            "role": top_role,
            "frequency": round(frequency, 4),
            "reason": reason,
            "seen_in": stat["seen_in"],
        })

    # ── 依 frequency 高到低排序，取前 max_suggestions ─────────────
    candidates.sort(key=lambda x: x["frequency"], reverse=True)
    return candidates[:max_suggestions]
