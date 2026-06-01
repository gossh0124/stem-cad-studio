"""services/pipeline/gate_logic.py — Phase gate checks (P2 power, P3 constraint).

Extracted from pipeline_runner.py (STR6 四拆: gate_logic).
"""
from __future__ import annotations
import json as _json
import logging
from typing import Callable, Optional

from ..shared.models import Job, JobStatus, PhaseID
from ..shared.bridge_store import event_registry, decision_trail, _CORE_ROLES
from ..shared.constants import (
    truncate_issues, CHOICE_SKIP_GATE, CHOICE_CONFIRM_SWAPS,
    GATE_TIMEOUT_S,
)
from .swap_engine import build_swap_suggestions as _build_swap_suggestions_fn
from .swap_engine import apply_swaps as _apply_swaps_fn

_log = logging.getLogger("cadhllm.gate_logic")


def _rag_constraint_hints(bridge: dict, failed_cats: list) -> list:
    """RAG: 搜尋歷史成功案例，比對與當前專案的元件差異，提取 workaround 策略。"""
    try:
        from lib.rag import search_cases
    except ImportError:
        return []

    components = bridge.get("components", [])
    cat = bridge.get("project_category", "")
    comp_str = ", ".join(c.get("type", "") for c in components[:8])
    query = f"{cat} project with {comp_str}"

    try:
        results = search_cases(query, top_k=5, category_filter=cat)
        if not results:
            results = search_cases(query, top_k=5)
    except Exception:
        return []

    current_types = {c.get("type", "") for c in components}

    hints = []
    for r in results:
        hist_comps = r.get("components", [])
        if not hist_comps:
            continue
        hist_types = {
            c.get("type", "") for c in hist_comps if isinstance(c, dict)
        }
        if hist_types == current_types:
            continue

        hint_parts: list[str] = []

        # Brain 差異（GPIO 不足 / 功能擴充的關鍵）
        hist_brain = next(
            (c.get("type", "") for c in hist_comps
             if isinstance(c, dict) and c.get("role") == "Brain"), "")
        curr_brain = next(
            (c.get("type", "") for c in components
             if c.get("role") == "Brain"), "")
        if hist_brain and hist_brain != curr_brain:
            hint_parts.append(f"Brain: {hist_brain}")

        # Power 差異（功率超標的關鍵）
        hist_power = next(
            (c.get("type", "") for c in hist_comps
             if isinstance(c, dict) and c.get("role") == "Power"), "")
        curr_power = next(
            (c.get("type", "") for c in components
             if c.get("role") == "Power"), "")
        if hist_power and hist_power != curr_power:
            hint_parts.append(f"Power: {hist_power}")

        # 其他差異元件（可能是替代方案）
        skip = {hist_brain, hist_power, ""}
        other_added = (hist_types - current_types) - skip
        if other_added:
            hint_parts.append(f"額外使用 {', '.join(list(other_added)[:2])}")

        if hint_parts:
            hints.append({
                "project": r.get("project_name", ""),
                "hint": "; ".join(hint_parts),
            })

    return hints[:3]


_PHASE_REQUIRED_KEYS: dict[int, list[str]] = {
    2: ["components", "project_name"],
    3: ["components", "components_resolved", "project_name"],
    4: ["components", "bom", "power_budget", "wiring", "phase3_constraint_check"],
    5: ["cad_output"],
    6: ["cad_output", "viewer"],
}

_CONSTRAINT_LABELS: dict[str, str] = {
    "power": "總功率", "io": "I/O", "pin_current": "GPIO 電流",
    "wiring": "佈線", "geometry": "幾何", "interference": "干涉",
}


def phase_preflight(phase_id: PhaseID, bridge: dict) -> str | None:
    required = _PHASE_REQUIRED_KEYS.get(phase_id.value, [])
    missing_keys = [k for k in required if k not in bridge or bridge[k] is None]
    if missing_keys:
        return (
            f"Phase {phase_id.value} 要求 bridge 包含 {missing_keys}，"
            f"請確認前置 Phase 已正確完成"
        )

    components = bridge.get("components", [])
    roles = {c.get("role") for c in components if isinstance(c, dict)}

    if phase_id == PhaseID.P2:
        missing = _CORE_ROLES - roles
        if components and missing:
            return f"Phase II 要求核心角色齊全，缺少：{missing}"

    elif phase_id == PhaseID.P3:
        if not bridge.get("components_resolved"):
            return "Phase III 要求 components_resolved=True（Phase II 未完成規格補全）"
        missing = _CORE_ROLES - roles
        if missing:
            return f"Phase III 要求核心角色齊全，缺少：{missing}"

    elif phase_id == PhaseID.P4:
        check = bridge.get("phase3_constraint_check", {})
        if not check.get("overall_ok") and not check.get("user_override"):
            return "Phase IV 要求電氣約束通過（phase3_constraint_check.overall_ok=False）"

    return None


def p2_power_gate_payload(job: Job, bridge: dict) -> tuple:
    pwr = bridge.get("power_warning_phase2") or {}
    if not pwr.get("warning"):
        return None, []

    total_ma = pwr.get("total_ma", 0)
    supply_ma = pwr.get("supply_ma", 500) or 500
    over_pct = round((total_ma / supply_ma - 1) * 100) if supply_ma else 0

    suggestions = _build_swap_suggestions_fn(bridge)

    # RAG: 歷史成功案例的 workaround 提示
    rag_hints = _rag_constraint_hints(bridge, ["總功率"])

    payload = {
        "__phase_data__": True,
        "phase": 2,
        "event_type": "fix_choice",
        "issues": [
            f"電氣超標 {total_ma:.0f} / {supply_ma:.0f} mA（超出 {over_pct}%）"
        ],
        "overbudget_detail": {
            "total_ma": round(total_ma, 1),
            "budget_ma": round(supply_ma, 1),
            "over_pct": over_pct,
        },
        "swap_suggestions": suggestions,
        "rag_hints": rag_hints,
        "options": [
            {"id": "confirm_swaps",
             "label": "確認替換 · 重新驗證",
             "description": "選擇要替換的元件後按此確認"},
        ],
        "timeout_s": 0,
        "job_id": job.job_id,
    }
    return payload, suggestions


def p3_gate_headline(bridge: dict, suggestions: list) -> str:
    p3chk = bridge.get("phase3_constraint_check", {})
    results = p3chk.get("results", {})
    failed: list = []
    for cat, data in results.items():
        if not data.get("ok", True):
            failed.append(_CONSTRAINT_LABELS.get(cat, cat))
    if not failed:
        failed = ["未知約束"]

    pb = bridge.get("power_budget", {})
    if "總功率" in failed and not pb.get("ok", True):
        total_ma, budget_ma = pb.get("total_ma", 0), pb.get("budget_ma", 500)
        head = f"⚠️ 電氣超標（{', '.join(failed)}；功率 {total_ma:.0f}/{budget_ma:.0f} mA）"
    else:
        head = f"⚠️ 電氣超標（違反：{', '.join(failed)}）"
    return f"{head}，提供 {len(suggestions)} 個替換方案，等待選擇…"


def p3_gate_payload(job: Job, bridge: dict) -> tuple:
    p3chk = bridge.get("phase3_constraint_check", {})
    if p3chk.get("overall_ok", True):
        return None, []

    pb = bridge.get("power_budget", {})
    total_ma = pb.get("total_ma", 0)
    budget_ma = pb.get("budget_ma", 500)
    power_failed = not pb.get("ok", True)
    overbudget_pct = (round((total_ma / budget_ma - 1) * 100)
                     if budget_ma and power_failed else 0)

    issues_detail: list = []
    for cat_data in p3chk.get("results", {}).values():
        if not cat_data.get("ok", True):
            for d in cat_data.get("details", []):
                msg = d.get("msg", "") if isinstance(d, dict) else str(d)
                if msg:
                    issues_detail.append(msg)

    suggestions = _build_swap_suggestions_fn(bridge)

    failed_cats = [_CONSTRAINT_LABELS.get(c, c) for c, d in p3chk.get("results", {}).items()
                   if not d.get("ok", True)]
    fallback_issue = (f"違反約束：{', '.join(failed_cats) or '未知'}"
                     + (f"（功率 {total_ma:.0f}/{budget_ma:.0f} mA）" if power_failed else ""))

    # RAG: 歷史成功案例的 workaround 提示
    rag_hints = _rag_constraint_hints(bridge, failed_cats)

    payload = {
        "__phase_data__": True,
        "phase": 3,
        "event_type": "fix_choice",
        "issues": truncate_issues(issues_detail) or [fallback_issue],
        "overbudget_detail": {
            "total_ma": round(total_ma, 1),
            "budget_ma": round(budget_ma, 1),
            "over_pct": overbudget_pct,
            "power_failed": power_failed,
            "failed_categories": failed_cats,
        } if power_failed else {
            "failed_categories": failed_cats,
            "power_failed": False,
        },
        "swap_suggestions": suggestions,
        "rag_hints": rag_hints,
        "options": [
            {"id": "confirm_swaps",
             "label": "確認替換 · 退回 Phase II 重新驗證",
             "description": "選擇要替換的元件後按此確認"},
        ],
        "timeout_s": 0,
        "job_id": job.job_id,
    }
    return payload, suggestions


def gate_emit_and_apply(
    job: Job,
    bridge: dict,
    payload: dict,
    suggestions: list,
    result: dict | None,
    progress_cb,
    queue,
    emit_fn: Callable,
) -> str:
    choice = (result or {}).get("choice_id", CHOICE_CONFIRM_SWAPS)
    if choice == CHOICE_SKIP_GATE and suggestions:
        emit_fn(progress_cb, "  ❌ 有替換方案時不允許 skip_gate")
        return "rerun_from_2"
    if choice == CHOICE_SKIP_GATE:
        pb = bridge.get("power_budget", {})
        decision_trail.log(job.job_id, "p3_constraint_gate", {
            "action": "skip_gate", "overall_ok": False,
            "total_ma": pb.get("total_ma", 0),
            "budget_ma": pb.get("budget_ma", 500),
        })
        emit_fn(progress_cb, "  ⏭ 使用者選擇忽略超標，繼續執行")
        return "continue"

    selected = (result or {}).get("selected_swaps", [])
    _apply_swaps_fn(bridge, suggestions, selected)

    pb = bridge.get("power_budget", {})
    total_ma, budget_ma = pb.get("total_ma", 0), pb.get("budget_ma", 500)
    decision_trail.log(job.job_id, "p3_constraint_gate", {
        "overall_ok": False,
        "total_ma": total_ma,
        "budget_ma": budget_ma,
        "selected_swaps": selected,
    })

    emit_fn(progress_cb, f"  ↩ 已選擇 {len(selected)} 項替換，退回 Phase II 重新驗證")
    return "rerun_from_2"


# ── sync/async gate helpers ──────────────────────────────────────
def _wait_for_gate_event(job_id: str, timeout: float) -> dict | None:
    """Sync: register -> wait -> unregister."""
    event_registry.register(job_id)
    try:
        return event_registry.wait(job_id, timeout=timeout)
    finally:
        event_registry.unregister(job_id)


async def _wait_for_gate_event_async(job_id: str, timeout: float) -> dict | None:
    """Async: register -> wait_async -> unregister."""
    event_registry.register(job_id)
    try:
        return await event_registry.wait_async(job_id, timeout=timeout)
    finally:
        event_registry.unregister(job_id)


def _gate_set_waiting(
    job: Job, bridge: dict, queue, progress_cb,
    payload: dict, phase_num: int,
) -> None:
    """Common pre-wait setup: update job status + emit payload."""
    job.status = JobStatus.WAITING
    job.current_phase = phase_num
    queue.update(job)
    if progress_cb:
        progress_cb(_json.dumps(payload))


# ── public gate functions ────────────────────────────────────────
def p2_power_gate(
    job: Job,
    bridge: dict,
    queue,
    progress_cb,
    emit_fn: Callable,
) -> str:
    payload, suggestions = p2_power_gate_payload(job, bridge)
    if payload is None:
        return "continue"
    if not suggestions:
        emit_fn(progress_cb, "⚠️ [Phase II] 電氣超標但無自動替換方案，繼續執行")
        return "continue"

    pwr = bridge.get("power_warning_phase2") or {}
    emit_fn(progress_cb,
        f"⚠️ [Phase II] 電氣超標（{pwr.get('total_ma',0):.0f}/"
        f"{pwr.get('supply_ma',0):.0f} mA），"
        f"提供 {len(suggestions)} 個替換方案，等待選擇…")

    _gate_set_waiting(job, bridge, queue, progress_cb, payload, 2)
    result = _wait_for_gate_event(job.job_id, timeout=GATE_TIMEOUT_S)
    return gate_emit_and_apply(job, bridge, payload, suggestions, result, progress_cb, queue, emit_fn)


async def p2_power_gate_async(
    job: Job,
    bridge: dict,
    queue,
    progress_cb,
    emit_fn: Callable,
) -> str:
    payload, suggestions = p2_power_gate_payload(job, bridge)
    if payload is None:
        return "continue"
    if not suggestions:
        emit_fn(progress_cb, "⚠️ [Phase II] 電氣超標但無自動替換方案，繼續執行")
        return "continue"

    pwr = bridge.get("power_warning_phase2") or {}
    emit_fn(progress_cb,
        f"⚠️ [Phase II] 電氣超標（{pwr.get('total_ma',0):.0f}/"
        f"{pwr.get('supply_ma',0):.0f} mA），"
        f"提供 {len(suggestions)} 個替換方案，等待選擇…")

    _gate_set_waiting(job, bridge, queue, progress_cb, payload, 2)
    result = await _wait_for_gate_event_async(job.job_id, timeout=GATE_TIMEOUT_S)
    return gate_emit_and_apply(job, bridge, payload, suggestions, result, progress_cb, queue, emit_fn)


def p3_constraint_gate(
    job: Job,
    bridge: dict,
    queue,
    progress_cb,
    emit_fn: Callable,
) -> str:
    payload, suggestions = p3_gate_payload(job, bridge)
    if payload is None:
        return "continue"

    emit_fn(progress_cb, p3_gate_headline(bridge, suggestions))
    _gate_set_waiting(job, bridge, queue, progress_cb, payload, 3)
    result = _wait_for_gate_event(job.job_id, timeout=GATE_TIMEOUT_S)
    return gate_emit_and_apply(job, bridge, payload, suggestions, result, progress_cb, queue, emit_fn)


async def p3_constraint_gate_async(
    job: Job,
    bridge: dict,
    queue,
    progress_cb,
    emit_fn: Callable,
) -> str:
    payload, suggestions = p3_gate_payload(job, bridge)
    if payload is None:
        return "continue"

    emit_fn(progress_cb, p3_gate_headline(bridge, suggestions))
    _gate_set_waiting(job, bridge, queue, progress_cb, payload, 3)
    result = await _wait_for_gate_event_async(job.job_id, timeout=GATE_TIMEOUT_S)
    return gate_emit_and_apply(job, bridge, payload, suggestions, result, progress_cb, queue, emit_fn)
