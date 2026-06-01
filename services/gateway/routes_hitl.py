"""gateway/routes_hitl.py — HITL 互動端點（斷點 / 修正指令 / 批次）。"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..shared.auth import get_token_job_id, require_job_owner

from ..shared.models import JobStatus
from ..shared.bridge_store import write_hitl_lock, event_registry, decision_trail

router = APIRouter()


class HitlAction(str, Enum):
    """合法的 HITL 修正動作白名單，對應 phase7_handler.py 中的 action 分支。

    NOTE: Current whitelist is static. If actions grow beyond ~15 types,
    consider semantic validation (e.g., NLP intent classification) to handle
    free-form user input before mapping to discrete actions.
    """
    INCREASE_WALL_THICKNESS = "increase_wall_thickness"
    DECREASE_WALL_THICKNESS = "decrease_wall_thickness"
    CHANGE_MATERIAL          = "change_material"
    RESIZE_ENCLOSURE         = "resize_enclosure"
    ADD_COMPONENT            = "add_component"
    REPLACE_COMPONENT        = "replace_component"
    FREE_TEXT                = "free_text"
    ACCEPT                   = "accept"


_HITL_ALLOWED_ACTIONS = {a.value for a in HitlAction}


class HITLCommandRequest(BaseModel):
    action: str = Field(..., description="修正動作，如 increase_wall_thickness")
    params: Dict[str, Any] = Field(default_factory=dict)
    step_id: Optional[str] = Field(None, description="冪等性 key")


class HITLBatchRequest(BaseModel):
    corrections: List[HITLCommandRequest] = Field(..., min_length=1)


class BreakpointResponse(BaseModel):
    breakpoint_id: str = Field(..., description="斷點 ID（A/B/C）")
    value: str = Field("", description="使用者輸入值")


class FixChoiceRequest(BaseModel):
    choice_id: str = Field(..., description="修正選項 ID")
    selected_swaps: List[str] = Field(default=[], description="勾選的替換 ID")


_HITL_PARAM_LIMITS = {
    "wall_thickness_mm":    (1.2, 5.0),
    "internal_padding_mm":  (1.0, 8.0),
    "max_dimension_mm":     (50.0, 300.0),
    "chamfer_mm":           (0.0, 3.0),
}


def _get_queue():
    from .main import _queue
    return _queue


def _job_or_404(job_id: str):
    job = _get_queue().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")
    return job


def _validate_hitl_params(params: Dict[str, Any]) -> Optional[str]:
    for key, (lo, hi) in _HITL_PARAM_LIMITS.items():
        if key in params:
            try:
                val = float(params[key])
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if val < lo or val > hi:
                return f"{key} must be between {lo} and {hi} (got {val})"
    swap = params.get("swap_component")
    if swap:
        if not isinstance(swap, dict) or "index" not in swap or "new_type" not in swap:
            return "swap_component must have 'index' and 'new_type'"
    return None


@router.get("/api/v1/jobs/{job_id}/complements")
async def get_complements(
    job_id: str,
    token_job_id: str = Depends(get_token_job_id),
) -> dict:
    """On-demand 互補元件建議：依 job 現有 bridge，回傳相似歷史專案常見、
    但目前設計缺少的元件（對應「學生事後才想到要加功能」的情境）。

    與 swap_suggestions（同功能替換）互補：此端點是「新增」建議，
    純參考、不強制套用。檢索失敗或無相似案例時回傳空清單。
    """
    require_job_owner(token_job_id, job_id)
    from ..shared.bridge_store import load_bridge
    from ..pipeline.complement_engine import suggest_complements

    bridge = load_bridge(job_id)
    if not bridge:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 的 bridge 不存在")
    suggestions = suggest_complements(bridge)
    return {"job_id": job_id, "complements": suggestions}


@router.post("/api/v1/jobs/{job_id}/hitl")
async def send_hitl_command(job_id: str, req: HITLCommandRequest, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    q = _get_queue()
    if req.step_id and q.is_step_processed(req.step_id):
        return {"status": "already_processed", "step_id": req.step_id}

    job = _job_or_404(job_id)
    if job.status not in (JobStatus.WAITING, JobStatus.RUNNING):
        raise HTTPException(400, f"Job 狀態 {job.status.value} 不接受 HITL 指令")

    if req.action not in _HITL_ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action: {req.action!r}. Allowed: {sorted(_HITL_ALLOWED_ACTIONS)}",
        )

    if req.params:
        err = _validate_hitl_params(req.params)
        if err:
            raise HTTPException(400, f"參數驗證失敗：{err}")

    cmd = {"action": req.action, "params": req.params}
    lock_path = write_hitl_lock(job_id, cmd)
    event_registry.signal(job_id, cmd)
    decision_trail.log(job_id, "hitl_command", {"action": req.action, "params": req.params, "step_id": req.step_id})

    if req.step_id:
        q.mark_step_processed(req.step_id, job_id)

    await _broadcast(job_id, {"event": "hitl_sent", "command": cmd})
    return {"lock_path": lock_path, "command": cmd}


@router.post("/api/v1/jobs/{job_id}/hitl/batch")
async def send_hitl_batch(job_id: str, req: HITLBatchRequest, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    q = _get_queue()

    # 冪等性：過濾掉已處理的指令
    pending = []
    already = []
    for c in req.corrections:
        if c.step_id and q.is_step_processed(c.step_id):
            already.append(c.step_id)
        else:
            pending.append(c)

    if not pending:
        return {"status": "already_processed", "step_ids": already}

    job = _job_or_404(job_id)
    if job.status not in (JobStatus.WAITING, JobStatus.RUNNING):
        raise HTTPException(400, f"Job 狀態 {job.status.value} 不接受 HITL 指令")

    invalid = [c.action for c in pending if c.action not in _HITL_ALLOWED_ACTIONS]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action(s): {invalid}. Allowed: {sorted(_HITL_ALLOWED_ACTIONS)}",
        )

    cmd = {"corrections": [{"action": c.action, "params": c.params} for c in pending]}
    lock_path = write_hitl_lock(job_id, cmd)
    event_registry.signal(job_id, cmd)

    for c in pending:
        if c.step_id:
            q.mark_step_processed(c.step_id, job_id)

    await _broadcast(job_id, {"event": "hitl_batch_sent", "count": len(pending)})
    return {"lock_path": lock_path, "count": len(pending)}


@router.post("/api/v1/jobs/{job_id}/breakpoint")
async def respond_breakpoint(job_id: str, req: BreakpointResponse, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    _job_or_404(job_id)
    payload = {"breakpoint_id": req.breakpoint_id, "value": req.value}
    signaled = event_registry.signal(job_id, payload)
    if not signaled:
        raise HTTPException(400, f"Job {job_id} 目前沒有等待中的斷點")
    await _broadcast(job_id, {"event": "breakpoint_response", "payload": payload})
    return {"job_id": job_id, "breakpoint_id": req.breakpoint_id, "accepted": True}


@router.post("/api/v1/jobs/{job_id}/fix-choice")
async def respond_fix_choice(job_id: str, req: FixChoiceRequest, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    _job_or_404(job_id)
    payload = {"choice_id": req.choice_id, "selected_swaps": req.selected_swaps}
    signaled = event_registry.signal(job_id, payload)
    if not signaled:
        raise HTTPException(400, f"Job {job_id} 目前沒有等待中的修正選項")
    await _broadcast(job_id, {"event": "fix_choice_response", "payload": payload})
    return {"job_id": job_id, "choice_id": req.choice_id, "accepted": True}
