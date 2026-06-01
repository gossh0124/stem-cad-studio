"""rag_ch3.py — CH3 階層式 LoRA-B（Plan + Params）的 RAG context builder。

對應 `docs/CH3_HIERARCHICAL_SPEC.md` Q2：Params 階段（座標 + 旋轉 + 尺寸）
拿到 Plan 階段輸出後，用 element_layouts + cable_routing 範例做 few-shot
注入。Plan 階段已由 `lib.rag.build_phase4_context()` 提供 context；本檔
專責補 Params 階段。

抽離原因：`lib/rag.py` 已 667 行，超過專案 500 行上限；新階段相關函式
獨立成新檔，避免擠舊檔。

設計重點：
  - 僅 Params 階段呼叫；Plan 階段仍走 `build_phase4_context`。
  - query 由 plan_output 結構化欄位組成（elements / joints / thermal）。
  - 回傳 `str`，會被 prompt template inject 進 system_msg 尾部。
  - 容錯：找不到歷史案例時回空字串（不擋主流程）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

_log = logging.getLogger("cadhllm.rag.ch3")


def _plan_summary_query(bridge: dict, plan_output: dict) -> str:
    """組裝 Params 階段用的查詢字串（混合 bridge meta 與 Plan 結構摘要）。"""
    name = bridge.get("project_name", "")
    cat = bridge.get("project_category", "")

    elements = plan_output.get("elements") or []
    if not isinstance(elements, list):
        elements = []
    elem_str = ", ".join(
        f"{e.get('type', '')}:{e.get('role', '')}"
        for e in elements[:8]
        if isinstance(e, dict)
    )

    joints = plan_output.get("joints") or {}
    joint_method = joints.get("lid_method", "") if isinstance(joints, dict) else ""

    thermal = plan_output.get("thermal_strategy") or plan_output.get("thermal", {})
    if isinstance(thermal, dict):
        thermal_str = thermal.get("strategy", "none")
    else:
        thermal_str = str(thermal)

    return (
        f"{name} ({cat}) | "
        f"elements: {elem_str} | "
        f"joints: {joint_method} | "
        f"thermal: {thermal_str}"
    )


def _format_params_examples(results: List[Dict[str, Any]]) -> List[str]:
    """把 search_assembly 回傳的歷史 plan 拆成 Params 範例片段。

    重點抓 layout（element_layouts 雛型）+ cable_routing。
    每筆只取前 4 個 layout entry 以免 prompt 過長。
    """
    parts: List[str] = []
    for i, r in enumerate(results, 1):
        plan = r.get("plan") or {}
        if not isinstance(plan, dict):
            continue

        layout = plan.get("layout") or []
        layout_lines = []
        for item in layout[:4]:
            if not isinstance(item, dict):
                continue
            comp = item.get("component", "")
            zone = item.get("zone", "")
            face = item.get("face_out", "")
            rot = item.get("rotation", "")
            # 若歷史紀錄含座標就帶出來（v3 升級後會逐步累積）
            coord = item.get("position") or item.get("xy") or ""
            layout_lines.append(
                f"  {comp} @ zone={zone} face={face}"
                + (f" rot={rot}" if rot else "")
                + (f" pos={coord}" if coord else "")
            )

        cable = plan.get("cable_routing") or []
        cable_lines = []
        for cab in cable[:4]:
            if isinstance(cab, dict):
                src = cab.get("from", "")
                dst = cab.get("to", "")
                path = cab.get("path", cab.get("zone", ""))
                cable_lines.append(f"  {src} -> {dst}: {path}")
            elif isinstance(cab, str):
                cable_lines.append(f"  {cab}")

        header = f"[範例{i}] {r.get('project_name', '')}"
        block = [header]
        if layout_lines:
            block.append(" element_layouts:")
            block.extend(layout_lines)
        if cable_lines:
            block.append(" cable_routing:")
            block.extend(cable_lines)
        parts.append("\n".join(block))
    return parts


def phase4_params_context_builder(
    bridge: dict,
    plan_output: dict,
    top_k: int = 3,
) -> str:
    """為 Params 階段建構 RAG context 字串。

    Parameters
    ----------
    bridge : dict
        Phase III 完成的 bridge（含 components / project_name / category）。
    plan_output : dict
        Plan 階段 LoRA-B 輸出（含 elements / joints / thermal_strategy）。
    top_k : int
        檢索的歷史範本數量。

    Returns
    -------
    str
        few-shot context 片段；無命中時回空字串。

    Note
    ----
    `lib.rag.search_assembly` 已存在；本函式僅組 query + 後處理結果。
    避免循環依賴：在函式內部 lazy import。
    """
    try:
        from .rag_assembly import search_assembly
    except ImportError:
        from rag_assembly import search_assembly  # 純路徑 fallback

    query = _plan_summary_query(bridge, plan_output)
    cat = bridge.get("project_category") or None

    try:
        results = search_assembly(query, top_k=top_k, category_filter=cat)
        if not results:
            results = search_assembly(query, top_k=top_k)
    except Exception as exc:
        _log.warning("search_assembly 失敗，Params RAG context 略過：%s", exc)
        return ""

    if not results:
        return ""

    examples = _format_params_examples(results)
    if not examples:
        return ""

    parts = ["=== Params 階段參考範例（element_layouts + cable_routing） ==="]
    parts.extend(examples)
    parts.append(
        "（以上為歷史相似專案；請依當前 Plan 元素與 bridge 元件清單，"
        "輸出本案的座標/旋轉/尺寸 JSON。）"
    )
    return "\n".join(parts)
