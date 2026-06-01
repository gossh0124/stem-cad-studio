"""lib.rag — RAG (Retrieval-Augmented Generation) package.

Four Collections:
  components  : COMPONENT_REGISTRY full spec embedding
  cases       : Historical successful Phase I cases (bridge JSON)
  assembly    : Historical successful Phase IV assembly decisions
  comp_wiring : Wiring pin-pattern index for unknown component matching (Layer 2)

Tech stack:
  Vector DB  : LanceDB (embedded, zero-server)
  Embedding  : BAAI/bge-base-zh-v1.5 (200MB, 768-dim, excellent Chinese)
  Search     : ANN vector search + Metadata WHERE filter
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

# ── Re-export from submodules ─────────────────────────────────
from .rag_embedding import (
    COLL_ASSEMBLY,
    COLL_CASES,
    COLL_COMPONENTS,
    DISTANCE_THRESHOLDS,
    _get_db,
    _get_embed_model,
    _lock,
    _rag_db_path,
    _sanitize_filter,
    check_db_dimension_compat,
    embed_text,
    embed_texts,
)
from .rag_components import (
    build_component_index,
    resolve_abstract_functions,
    search_components,
)
from .rag_cases import (
    add_case,
    hyde_search_cases,
    search_cases,
)
from .rag_assembly import (
    add_assembly,
    search_assembly,
)
from .rag_wiring import (
    COLL_WIRING,
    search_similar_wiring,
)
from .rag_ch3 import phase4_params_context_builder  # noqa: F401

_log = logging.getLogger("cadhllm.rag")


# ════════════════════════════════════════════════════════════════
# Prompt Context Builder (RAG -> LLM Prompt injection)
# ════════════════════════════════════════════════════════════════

def build_phase1_context(instruction: str, top_k: int = 3) -> str:
    """Build RAG context string for Phase I prompt.

    Injected at the end of system prompt (doesn't change training format):
    - Similar historical case component combinations
    - Related component physical spec summaries
    """
    parts = []

    # (0) 抽象功能 → 假設元件（供 HyDE + 第 3 段共用，避免重複計算）
    func_matches = resolve_abstract_functions(instruction)

    # (1) 檢索歷史案例：輸入模糊（偵測到抽象功能、無明確元件名）時走 HyDE，
    #     用假設元件清單做嵌入以提升召回；否則用一般語意檢索。
    if func_matches:
        hypothetical = [
            {"role": "", "type": cls}
            for fm in func_matches for cls in fm["classes"]
        ]
        cases = hyde_search_cases(instruction, hypothetical, top_k=top_k)
    else:
        cases = search_cases(instruction, top_k=top_k)
    if cases:
        parts.append("=== 相似歷史專案（僅供參考，依實際需求調整） ===")
        for i, c in enumerate(cases, 1):
            comps = c.get("components", [])
            comp_str = ", ".join(
                f"{x.get('type', '')}" for x in comps
            )
            parts.append(
                f"[案例{i}] {c['project_name']} ({c['project_category']}): "
                f"{comp_str}"
            )

    # (2) Search related components (with physical layout — INF11 deep expansion)
    comp_results = search_components(instruction, top_k=5, include_physical=True)
    if comp_results:
        parts.append("=== 可能相關的元件（含接腳與安裝孔） ===")
        for cr in comp_results:
            line = (
                f"- {cr['name']} ({cr['class_name']}): "
                f"{cr['role']}, {cr['voltage_v']}V/{cr['current_ma']}mA"
            )
            if cr.get("dimensions_mm"):
                line += f", size={cr['dimensions_mm']}mm"
            if cr.get("tags"):
                line += f", tags={cr['tags']}"
            parts.append(line)
            if cr.get("connector_ports"):
                ports_str = "; ".join(
                    f"{p['name']}({p['side']})" for p in cr["connector_ports"][:6]
                )
                parts.append(f"  ports: {ports_str}")
            if cr.get("mounting_holes"):
                holes_str = ", ".join(
                    f"({h['x']},{h['y']})d{h['diameter']}" for h in cr["mounting_holes"]
                )
                parts.append(f"  mount_holes: {holes_str}")

    # (3) S3: 功能 → 元件推薦（func_matches 已於上方第 0 段計算）
    if func_matches:
        parts.append("=== 功能 → 元件推薦（依描述推導） ===")
        for fm in func_matches:
            classes_str = ", ".join(fm["classes"])
            parts.append(f"- {fm['reason']}：{classes_str}")

    if not parts:
        return ""
    return "\n".join(parts)


def build_phase4_context(
    bridge: dict,
    components: List[dict],
    top_k: int = 3,
) -> str:
    """Build RAG context string for Phase IV LoRA-B Plan stage prompt.

    Enhanced: 加入當前元件尺寸、走線摘要、重量/熱 metadata、佈局理由。
    """
    name = bridge.get("project_name", "")
    cat = bridge.get("project_category", "")
    comp_str = ", ".join(c.get("type", "") for c in components)
    query = f"{name} ({cat}) components: {comp_str}"

    results = search_assembly(query, top_k=top_k, category_filter=cat)
    if not results:
        results = search_assembly(query, top_k=top_k)

    if not results:
        return ""

    # 當前專案的元件尺寸摘要（幫助 Plan 理解空間約束）
    dim_lines: List[str] = []
    for c in components[:6]:
        spec = c.get("spec", {})
        ctype = c.get("type", "")
        role = c.get("role", "")
        if spec.get("length_mm"):
            dim_lines.append(
                f"  {ctype}({role}): "
                f"{spec['length_mm']}×{spec.get('width_mm', 0)}×"
                f"{spec.get('height_mm', 0)}mm"
            )

    parts = ["=== 相似組裝決策參考 ==="]
    if dim_lines:
        parts.append("當前元件尺寸：")
        parts.extend(dim_lines)

    for i, r in enumerate(results, 1):
        plan = r.get("plan", {})
        layout = plan.get("layout", [])
        layout_str = "; ".join(
            f"{item.get('component', '')}→{item.get('zone', '')}"
            f"({item.get('face_out', '')})"
            for item in layout[:6]
        )
        thermal = plan.get("thermal", {})
        joints = plan.get("joints", {})

        # 走線摘要
        cable = plan.get("cable_routing", [])
        cable_str = f", routes={len(cable)}" if cable else ""

        # 重量/熱 metadata（影響 thermal strategy 決策）
        meta_parts: List[str] = []
        weight = r.get("total_weight_g")
        if weight:
            meta_parts.append(f"weight={weight:.0f}g")
        thermal_mw = r.get("total_thermal_mw")
        if thermal_mw:
            meta_parts.append(f"thermal={thermal_mw:.0f}mW")
        meta_str = f" ({', '.join(meta_parts)})" if meta_parts else ""

        # 佈局理由（截斷至 120 字）
        rationale = plan.get("placement_rationale", "")
        rationale_str = (
            f" | rationale: {rationale[:120]}" if rationale else ""
        )

        parts.append(
            f"[參考{i}] {r['project_name']}{meta_str}: "
            f"layout=[{layout_str}], "
            f"thermal={thermal.get('strategy', 'n/a')}, "
            f"joints={joints.get('lid_method', 'n/a')}"
            f"{cable_str}{rationale_str}"
        )

    return "\n".join(parts)


# ════════════════════════════════════════════════════════════════
# Status & Management
# ════════════════════════════════════════════════════════════════

def get_status() -> Dict[str, Any]:
    """Return RAG system status."""
    from .rag_embedding import _embed_model, _EMBED_MODEL_NAME
    status = {
        "db_path": _rag_db_path(),
        "embed_model": _EMBED_MODEL_NAME,
        "embed_loaded": _embed_model is not None,
        "collections": {},
    }
    try:
        db = _get_db()
        for name in [COLL_COMPONENTS, COLL_CASES, COLL_ASSEMBLY, COLL_WIRING]:
            try:
                tbl = db.open_table(name)
                status["collections"][name] = len(tbl)
            except Exception:
                status["collections"][name] = 0
    except Exception as e:
        status["error"] = str(e)
    return status


def ensure_initialized():
    """Ensure RAG system is initialized (component index built).

    Suitable for calling at server startup.
    Checks embedding dimension compatibility and drops stale collections.
    """
    from .rag_embedding import _lock, check_db_dimension_compat
    with _lock:
        check_db_dimension_compat()
        build_component_index(force=False)


# ── Public API (for explicit import checks) ────────────────────
__all__ = [
    # Embedding
    "embed_text",
    "embed_texts",
    "COLL_COMPONENTS",
    "COLL_CASES",
    "COLL_ASSEMBLY",
    "COLL_WIRING",
    # Components
    "build_component_index",
    "search_components",
    "resolve_abstract_functions",
    # Cases
    "add_case",
    "search_cases",
    "hyde_search_cases",
    # Assembly
    "add_assembly",
    "search_assembly",
    # Wiring (Layer 2)
    "search_similar_wiring",
    # Context builders
    "build_phase1_context",
    "build_phase4_context",
    "phase4_params_context_builder",
    # Status
    "get_status",
    "ensure_initialized",
]
