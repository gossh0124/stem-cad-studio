"""component_resolver.py — L1-L5 元件解析 + prompt mention 提取 + 近似值互證。

Phase I LoRA 輸出後、Clarify 之前執行，將未知 / 拼錯 / 品牌變體
的 component.type 解析為 canonical name 或標記需用戶確認。
U6 Phase 2：用戶自填元件數值 vs 同 role REGISTRY 中位數 ± 2σ 互證。
U7/U8 共用：role_stats() public API + estimate_thermal_confidence()。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .registry import COMPONENT_REGISTRY
from .config import TAXONOMY_CONFIG


# ── 解析結果 ────────────────────────────────────────────────────

@dataclass
class ResolveResult:
    original: str
    canonical: Optional[str] = None
    layer: str = ""
    status: str = "unresolved"          # resolved | fuzzy_candidate | unknown | unresolved
    distance: int = 0
    equivalent_candidates: List[str] = field(default_factory=list)
    llm_tags: List[str] = field(default_factory=list)


# ── Mention 提取（Phase I 之前，不改 prompt） ────────────────────

_MODEL_PAT = re.compile(
    r'\b('
    r'[A-Z]{1,5}[\-]?\d{2,6}[A-Z]?'       # MG996R, BH1750, AHT20, SG90
    r'|ESP32[A-Za-z0-9\-]*'                 # ESP32-S3, ESP32-C3
    r'|ESP8266'
    r'|Arduino[\s\-]?\w+'                   # Arduino Uno, Arduino-Mega
    r'|Raspberry\s*Pi[\s\w]*'               # Raspberry Pi 4B
    r'|NodeMCU[\w]*'
    r'|Wemos[\s\-]?D\d'                     # Wemos D1
    r'|Funduino[\s\-]?\w*'
    r'|Micro:?bit[\s\w]*'
    r')\b',
    re.IGNORECASE,
)

_GENERIC_PAT = re.compile(
    r'\b('
    r'servo|stepper|relay|buzzer|oled|lcd|pump|potentiometer|joystick'
    r'|neopixel|led[\s\-]?strip|pir|ultrasonic|dht\d{2}'
    r'|伺服|馬達|繼電器|蜂鳴器|超音波|水泵|按鈕|搖桿|旋鈕|光感'
    r')\b',
    re.IGNORECASE,
)


def extract_mentions(prompt: str) -> List[str]:
    """從用戶 prompt 提取元件名稱（不改 prompt）。"""
    hits = set()
    for m in _MODEL_PAT.finditer(prompt):
        hits.add(m.group(0).strip())
    for m in _GENERIC_PAT.finditer(prompt):
        hits.add(m.group(0).strip())
    return sorted(hits)


# ── Levenshtein（純 Python 實作，189 targets 足夠快） ────────────

def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,
                curr[j] + 1,
                prev[j] + (0 if ca == cb else 1),
            ))
        prev = curr
    return prev[-1]


def _strip_alnum(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.replace("-class", "").lower())


# ── L4 edit-distance 候選表 ─────────────────────────────────────

def _build_edit_targets() -> List[Tuple[str, str]]:
    """回傳 [(stripped_key, canonical_name), ...] 供 edit-distance 比對。"""
    targets = []
    for key in COMPONENT_REGISTRY:
        targets.append((_strip_alnum(key), key))
    return targets


_EDIT_TARGETS: List[Tuple[str, str]] = []


def _get_edit_targets() -> List[Tuple[str, str]]:
    global _EDIT_TARGETS
    if not _EDIT_TARGETS:
        _EDIT_TARGETS = _build_edit_targets()
    return _EDIT_TARGETS


# ── 主解析函式 ──────────────────────────────────────────────────

def resolve_component(
    raw_type: str,
    fuzzy_lookup_fn=None,
    user_store_get=None,
    llm_tag_fn=None,
) -> ResolveResult:
    """L1-L5 解析單一 component.type。

    Parameters
    ----------
    raw_type : str
        LoRA 輸出的 component type 字串。
    fuzzy_lookup_fn : callable, optional
        Phase II 的 _fuzzy_lookup 函式（L2 複用）。
    user_store_get : callable, optional
        user_components_store.get_spec(class_name)（L3）。
    llm_tag_fn : callable, optional
        LLM tag 推斷函式，接收 raw_type 回傳 List[str]（L5）。
    """
    result = ResolveResult(original=raw_type)

    # L1: REGISTRY exact match
    if raw_type in COMPONENT_REGISTRY:
        result.canonical = raw_type
        result.layer = "L1"
        result.status = "resolved"
        return result

    # L2: Phase II fuzzy_lookup (strip + token + alias + composite)
    if fuzzy_lookup_fn is not None:
        spec = fuzzy_lookup_fn(raw_type)
        if spec is not None:
            for key, val in COMPONENT_REGISTRY.items():
                if val is spec:
                    result.canonical = key
                    break
            if result.canonical:
                result.layer = "L2"
                result.status = "resolved"
                return result

    # L3: user_components_store
    if user_store_get is not None:
        user_spec = user_store_get(raw_type)
        if user_spec is not None:
            result.canonical = raw_type
            result.layer = "L3"
            result.status = "resolved"
            return result
        bare = _strip_alnum(raw_type)
        if bare != raw_type:
            user_spec = user_store_get(bare)
            if user_spec is not None:
                result.canonical = bare
                result.layer = "L3"
                result.status = "resolved"
                return result

    # L4: edit-distance ≤ 2 + category guard
    raw_norm = _strip_alnum(raw_type)
    if len(raw_norm) >= 3:
        best_dist, best_canonical = 3, None
        for stripped, canonical in _get_edit_targets():
            d = _levenshtein(raw_norm, stripped)
            if d < best_dist:
                best_dist, best_canonical = d, canonical

        if best_canonical and best_dist <= 2:
            result.canonical = best_canonical
            result.distance = best_dist
            result.layer = "L4"
            result.status = "fuzzy_candidate"
            return result

    # L5: LLM tag inference（llm_tag_fn 接入後啟用）
    if llm_tag_fn is not None:
        tags = llm_tag_fn(raw_type)
        if tags:
            result.llm_tags = tags
            result.layer = "L5"
            result.status = "unknown"
            return result

    result.layer = "L5"
    result.status = "unknown"
    return result


# ── 批次解析 + mentions diff ────────────────────────────────────

def resolve_all(
    components: List[dict],
    raw_mentions: List[str],
    fuzzy_lookup_fn=None,
    user_store_get=None,
    llm_tag_fn=None,
) -> Dict[str, Any]:
    """解析所有 components + 比對 mentions，回傳結構化結果。"""
    resolved = []
    fuzzy_candidates = []
    unknowns = []

    lora_types_lower = set()
    for comp in components:
        ctype = comp.get("type", "")
        if not ctype:
            continue
        lora_types_lower.add(_strip_alnum(ctype))

        r = resolve_component(
            ctype,
            fuzzy_lookup_fn=fuzzy_lookup_fn,
            user_store_get=user_store_get,
            llm_tag_fn=llm_tag_fn,
        )

        comp["_resolve"] = {
            "status": r.status,
            "layer": r.layer,
            "original": r.original,
        }

        if r.status == "resolved":
            if r.canonical and r.canonical != ctype:
                comp["_resolve"]["mapped_to"] = r.canonical
                comp["type"] = r.canonical
            resolved.append(comp)
        elif r.status == "fuzzy_candidate":
            comp["_resolve"]["candidate"] = r.canonical
            comp["_resolve"]["distance"] = r.distance
            fuzzy_candidates.append(comp)
        else:
            comp["_resolve"]["equivalent_candidates"] = r.equivalent_candidates
            comp["_resolve"]["llm_tags"] = r.llm_tags
            unknowns.append(comp)

    # mentions diff: 用戶提到但 LoRA 沒產出的
    missing_mentions = []
    for mention in raw_mentions:
        mention_norm = _strip_alnum(mention)
        if mention_norm and mention_norm not in lora_types_lower:
            already_in = False
            for comp in components:
                comp_norm = _strip_alnum(comp.get("type", ""))
                if mention_norm in comp_norm or comp_norm in mention_norm:
                    already_in = True
                    break
            if not already_in:
                r = resolve_component(
                    mention,
                    fuzzy_lookup_fn=fuzzy_lookup_fn,
                    user_store_get=user_store_get,
                    llm_tag_fn=llm_tag_fn,
                )
                missing_mentions.append({
                    "mention": mention,
                    "resolve": {
                        "status": r.status,
                        "layer": r.layer,
                        "canonical": r.canonical,
                        "equivalent_candidates": r.equivalent_candidates,
                    },
                })

    return {
        "resolved": resolved,
        "fuzzy_candidates": fuzzy_candidates,
        "unknowns": unknowns,
        "missing_mentions": missing_mentions,
    }


# ── U6/U7/U8：驗證 API（delegated to component_validator.py）────
from .component_validator import (  # noqa: E402, F401
    role_stats,
    cross_validate_user_spec,
    validate_measurement,
    estimate_thermal_confidence,
)
