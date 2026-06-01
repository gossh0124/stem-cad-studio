"""bridge.py — P1→P2 bridge: type resolution and contract conversion.

BOM 價格 / URL 從 lib/specs.py 動態取得（單一事實來源）。
"""
import logging
from typing import Dict, Any, List, Optional, Set, Tuple

_log = logging.getLogger(__name__)

from .specs import (
    PRICE_NTD as _PRICE_NTD,
    BOM_URLS as _BOM_URLS,
    COMPONENT_NAME_ALIASES as _BRIDGE_ALIAS_MAPPING,
    resolve_component_alias as _resolve_alias,
)
from .config import TAXONOMY_CONFIG


def build_bom(components: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """從已解析的 bridge components 建立 BOM 清單。

    components 中的 selected_type 可能是通用名（lib/registry 風格）或具體名（constants 風格），
    透過 resolve_component_alias 統一查詢，避免兩套命名造成漏配。
    """
    bom = []
    for c in components:
        cls = c.get("selected_type")
        if cls is None:
            raise ValueError(
                f"build_bom: component missing required 'selected_type' key (role={c.get('role', '?')!r})"
            )
        canonical = _resolve_alias(cls)
        bom.append({
            "class": cls,
            "role":  c.get("role", ""),
            "price_twd": _PRICE_NTD.get(canonical, 0),
            "url":       _BOM_URLS.get(canonical, ""),
        })
    return bom


def format_bom_dataframe(bom_list: List[Dict[str, Any]]) -> str:
    """將 BOM 清單格式化為 Markdown 表格。"""
    if not bom_list:
        return "No components."
    lines = [
        "| # | Role | Class | Price (TWD) | Source |",
        "|---|------|-------|-------------|--------|",
    ]
    total = 0
    for i, b in enumerate(bom_list, 1):
        url = b.get("url", "")
        link = f"[LCSC]({url})" if url else "—"
        lines.append(f"| {i} | {b['role']} | {b['class']} | {b['price_twd']} | {link} |")
        total += b["price_twd"]
    lines.append(f"| — | **合計** | — | **{total} TWD** | — |")
    return "\n".join(lines)


# P2_SUPPORTED_TYPES 從 TAXONOMY_CONFIG 動態生成，與 lib/config.py 保持同步。
# 靜態版本曾遺漏下列 TAXONOMY 中已有的 types（已透過動態化修正）：
#   AC-Adapter-class, USB-Adapter-class, Remote-class, Sensor-MSGEQ7-class,
#   Display-EInk-class, LED-Matrix-class, Buzzer-Passive-class,
#   Lighting-LED-PWM-class, Chassis-Car-class
P2_SUPPORTED_TYPES: Set[str] = {
    t
    for types in TAXONOMY_CONFIG["component_taxonomy"].values()
    for t in types
}

def flatten_manifest_to_component_requests(p1_output: dict) -> list:
    """將 P1 輸出展平為 P2 元件請求清單，支援多種格式。"""
    requests = []
    am = p1_output.get("abstract_manifest", {})
    aux = p1_output.get("auxiliary_manifest", [])

    if isinstance(am, dict):
        for role, role_data in am.items():
            if isinstance(role_data, dict):
                requests.append({
                    "role": role,
                    "source": "abstract_manifest",
                    "candidate_types": role_data.get("recommended_types", []),
                    "tags": role_data.get("tags", []),
                    "inventory_mentions": role_data.get("inventory_mentions", []),
                    "educational_rationale": role_data.get("educational_rationale", ""),
                })

    if isinstance(aux, list):
        for item in aux:
            if isinstance(item, dict):
                requests.append({
                    "role": item.get("role", "Unknown"),
                    "source": "auxiliary_manifest",
                    "candidate_types": item.get("recommended_types", []),
                    "tags": item.get("tags", []),
                    "inventory_mentions": [],
                    "educational_rationale": item.get("educational_rationale", ""),
                })

    return requests


def select_primary_type(candidates: list, p2_registry: set, inventory_mentions: list) -> Tuple[str, str, str]:
    """依優先序選擇元件類型，回傳 (selected_type, reason, status)。"""
    # 1. inventory match
    for cand in candidates:
        resolved = _BRIDGE_ALIAS_MAPPING.get(cand, cand)
        if resolved in p2_registry and any(resolved in str(m) for m in inventory_mentions):
            return resolved, "inventory_match", "resolved"
    # 2. first supported candidate
    for cand in candidates:
        resolved = _BRIDGE_ALIAS_MAPPING.get(cand, cand)
        if resolved in p2_registry:
            reason = "alias_resolved" if cand != resolved else "direct_match"
            return resolved, reason, "resolved"
    # 3. unresolved
    fallback = candidates[0] if candidates else "unknown"
    if fallback == "unknown":
        _log.warning("select_primary_type: no candidates, falling back to 'unknown'")
    return fallback, "unresolved", "unresolved"


def bridge_phase1_to_p2_contract(p1_output: dict, p2_registry: set = None) -> dict:
    """將 P1 輸出轉換為 P2 合約格式。"""
    if p2_registry is None:
        p2_registry = P2_SUPPORTED_TYPES
    requests = flatten_manifest_to_component_requests(p1_output)
    components = []

    for req in requests:
        selected_type, reason, status = select_primary_type(
            req["candidate_types"], p2_registry, req["inventory_mentions"]
        )
        components.append({
            "role": req["role"],
            "source": req["source"],
            "selected_type": selected_type,
            "candidate_types": req["candidate_types"],
            "selection_reason": reason,
            "resolution_status": status,
            "resolution_scope": "semantic",
            "tags": req["tags"],
            "educational_rationale": req["educational_rationale"],
        })

    inv_signals = p1_output.get("user_inventory_signals", {})
    has_edu = any(c.get("educational_rationale") for c in components)
    unresolved_count = sum(1 for c in components if c.get("resolution_status") == "unresolved")

    bom_list = build_bom(components)
    bom_total = sum(b["price_twd"] for b in bom_list)

    return {
        "project_category": p1_output.get("project_category", ""),
        "confidence_score": p1_output.get("confidence_score", 0.0),
        "components": components,
        "unresolved_count": unresolved_count,
        "inventory_signals": inv_signals,
        "stem_education_context": {
            "total_components": len(components),
            "has_education_content": has_edu,
            "pipeline_stage": "P1_to_P2_bridge",
        },
        "bom": bom_list,
        "bom_total_twd": bom_total,
    }
