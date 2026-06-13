"""gateway/routes_jobs.py — Job CRUD + SSE generate 端點。"""
from __future__ import annotations
import asyncio
import json
import logging as _logging
import os
import traceback as _traceback
import queue as _thread_queue
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from fastapi.responses import StreamingResponse
from ..shared.auth import create_token, get_token_job_id, require_job_owner
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..shared.models import Job, JobStatus
from ..shared.bridge_store import (
    save_bridge, load_bridge, default_bridge, default_lock_path,
    event_registry, decision_trail,
)
from ..pipeline_runner import make_runner

router = APIRouter()
_log = _logging.getLogger("cadhllm.routes_jobs")


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    project_name: str = Field(..., min_length=1, max_length=200)
    instruction:  str = Field(..., min_length=1)
    max_rounds:   int = Field(3, ge=1, le=10)
    timeout_s:    int = Field(300, ge=30, le=3600)

    @field_validator("project_name")
    @classmethod
    def _slug_safe(cls, v: str) -> str:
        if not all(c.isalnum() or c in "-_ " for c in v if ord(c) < 128):
            raise ValueError("project_name contains invalid characters")
        return v.strip()


class ForkTemplateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$")


def _get_queue():
    from .main import _queue
    return _queue


def _job_or_404(job_id: str) -> Job:
    job = _get_queue().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' 不存在")
    return job


@router.post("/api/v1/jobs", status_code=201)
async def create_job(req: CreateJobRequest) -> dict:
    bridge = default_bridge(req.project_name, req.instruction)
    job = Job(
        project_name=req.project_name,
        instruction=req.instruction,
        status=JobStatus.PENDING,
    )
    job.lock_path = default_lock_path(job.job_id)
    job.bridge_path = save_bridge(job.job_id, bridge)
    _get_queue().enqueue(job)
    token = create_token(job.job_id)
    return {"job_id": job.job_id, "status": job.status.value,
            "bridge_path": job.bridge_path,
            "token": token,
            "stream_url": f"/api/v1/jobs/{job.job_id}/stream"}


async def _make_event_stream(runner, job, q):
    """SSE 事件串流生成器（stream_job 和 sse_generate 共用）。"""
    tq: _thread_queue.SimpleQueue = _thread_queue.SimpleQueue()
    loop = asyncio.get_running_loop()

    def _cb(msg: str):
        if msg and msg.startswith('{"__phase_data__"'):
            try:
                tq.put(json.loads(msg))
                return
            except json.JSONDecodeError:
                pass
        tq.put(msg)

    async def _run():
        try:
            await runner.run_async_segmented(job, progress_cb=_cb)
        except Exception as exc:
            tb = _traceback.format_exc()
            _log.error("Pipeline failed for job %s: %s\n%s", job.job_id, exc, tb)
            tq.put({"__error__": True, "message": str(exc), "traceback": tb[:1000]})
        finally:
            tq.put(None)

    task = asyncio.create_task(_run())

    yield f"data: {json.dumps({'event':'start','job_id':job.job_id})}\n\n"

    try:
        while True:
            try:
                msg = await asyncio.wait_for(
                    loop.run_in_executor(None, tq.get, True, 15.0),
                    timeout=16.0,
                )
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'event':'heartbeat'})}\n\n"
                continue
            if msg is None:
                break
            if isinstance(msg, dict):
                if msg.get("__error__"):
                    yield f"data: {json.dumps({'event':'error', 'message': msg['message'], 'traceback': msg.get('traceback', '')})}\n\n"
                else:
                    yield f"data: {json.dumps({'event':'phase_data', **msg})}\n\n"
            else:
                yield f"data: {json.dumps({'event':'progress','message':msg})}\n\n"
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    final_job = q.get(job.job_id)
    status    = final_job.status.value if final_job else "unknown"
    decision_trail.log(job.job_id, "pipeline_done", {"status": status})
    yield f"data: {json.dumps({'event':'done','status':status,'job_id':job.job_id})}\n\n"


@router.get("/api/v1/jobs/{job_id}/stream")
async def stream_job(
    job_id: str,
    resume_from: int = 0,
    token_job_id: str = Depends(get_token_job_id),
):
    require_job_owner(token_job_id, job_id)
    q = _get_queue()
    job = _job_or_404(job_id)

    if resume_from > 0:
        if not load_bridge(job_id):
            raise HTTPException(404, f"找不到 Bridge JSON: {job_id}")
        job.status = JobStatus.PENDING
        job.error = None
        q.update(job)
        decision_trail.log(job.job_id, "pipeline_resume", {"resume_from": resume_from})
    else:
        decision_trail.log(job.job_id, "stream_start", {"job_id": job_id})

    skip_env = os.environ.get("SKIP_PHASES", "").strip()
    skip_phases = [int(x) for x in skip_env.split(",") if x.strip().isdigit()] if skip_env else []
    # VLM REMOVED — P6 always skipped by PipelineRunner
    runner = make_runner(
        q,
        phase7_timeout_s=30,
        skip_phases=skip_phases,
        resume_from=resume_from,
    )

    return StreamingResponse(
        _make_event_stream(runner, job, q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    return _job_or_404(job_id).to_dict()


@router.get("/api/v1/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    saved: Optional[bool] = None,
) -> List[dict]:
    q = _get_queue()
    if saved:
        jobs = q.list_saved(limit)
        if status:
            try:
                s = JobStatus(status)
            except ValueError:
                raise HTTPException(400, f"無效 status: {status}")
            jobs = [j for j in jobs if j.status == s]
    elif status:
        try:
            s = JobStatus(status)
        except ValueError:
            raise HTTPException(400, f"無效 status: {status}")
        jobs = q.list_by_status(s, limit)
    else:
        jobs = q.list_all(limit)
    return [j.to_dict() for j in jobs]


@router.post("/api/v1/jobs/{job_id}/save", status_code=200)
async def save_job(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    job = _job_or_404(job_id)
    if job.status != JobStatus.SUCCESS:
        raise HTTPException(400, f"僅成功完成的專案可儲存（current status: {job.status.value}）")
    if job.saved:
        return {"status": "already_saved", "job_id": job_id}
    job.saved = True
    _get_queue().update(job)
    return {"status": "saved", "job_id": job_id}


@router.delete("/api/v1/jobs/{job_id}/save", status_code=200)
async def unsave_job(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    job = _job_or_404(job_id)
    if not job.saved:
        return {"status": "not_saved", "job_id": job_id}
    job.saved = False
    _get_queue().update(job)
    return {"status": "unsaved", "job_id": job_id}


@router.delete("/api/v1/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str, token_job_id: str = Depends(get_token_job_id)):
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    job = _job_or_404(job_id)
    q = _get_queue()
    if job.status in (JobStatus.RUNNING, JobStatus.WAITING):
        job.status = JobStatus.CANCELLED
        q.update(job)
        await _broadcast(job_id, {"event": "cancelled", "job_id": job_id})
    q.delete(job_id)


@router.get("/api/v1/jobs/{job_id}/bridge")
async def get_bridge(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    _job_or_404(job_id)
    bridge = load_bridge(job_id)
    if bridge is None:
        raise HTTPException(404, "Bridge JSON 尚未產生")
    return bridge


@router.get("/api/v1/jobs/{job_id}/checkpoint")
async def get_checkpoint(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    job = _job_or_404(job_id)
    bridge = load_bridge(job_id)
    if bridge is None:
        return {"job_id": job_id, "has_checkpoint": False}
    checkpoint = bridge.get("checkpoint", bridge.get("_checkpoint", {}))
    return {
        "job_id": job_id,
        "has_checkpoint": bool(checkpoint),
        "last_phase": checkpoint.get("last_phase", 0),
        "timestamp": checkpoint.get("ts"),
        "job_status": job.status.value,
        "can_resume": job.status.value in ("failed", "cancelled", "success"),
    }


@router.get("/api/v1/jobs/{job_id}/trail")
async def get_decision_trail(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> List[dict]:
    require_job_owner(token_job_id, job_id)
    _job_or_404(job_id)
    return decision_trail.read(job_id)


@router.post("/api/v1/jobs/{job_id}/resume", status_code=202)
async def resume_job(job_id: str, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    from .main import _broadcast
    job = _job_or_404(job_id)
    if job.status != JobStatus.WAITING:
        raise HTTPException(400,
            f"只有 waiting_hitl 狀態的 Job 才能 resume（當前：{job.status.value}）")
    q = _get_queue()

    async def _resume():
        bridge = load_bridge(job_id) or {}
        from ..phase_handlers.phase7_handler import Phase7Handler
        handler = Phase7Handler()
        try:
            bridge_out, result = await asyncio.to_thread(
                handler.run, job, bridge, None
            )
            job.phase_results.append(result)
            job.status = JobStatus.SUCCESS
        except Exception as exc:
            tb = _traceback.format_exc()
            _log.error("Phase VII resume failed for job %s: %s\n%s", job_id, exc, tb)
            job.status = JobStatus.FAILED
            job.error  = str(exc)
        finally:
            q.update(job)
            await _broadcast(job_id, {"event": "done", "status": job.status.value, "job_id": job_id})

    asyncio.create_task(_resume())
    return {"job_id": job_id, "message": "Phase VII resume 已觸發"}


@router.post("/api/v1/jobs/{job_id}/confirm_clarify", status_code=202)
async def confirm_clarify(job_id: str, request: Request, token_job_id: str = Depends(get_token_job_id)) -> dict:
    require_job_owner(token_job_id, job_id)
    job = _job_or_404(job_id)
    if job.status != JobStatus.WAITING_CLARIFY:
        raise HTTPException(400,
            f"Job 不在 waiting_clarify 狀態（當前：{job.status.value}）")
    body = await request.json()
    answers = body.get("answers", {})
    signaled = event_registry.signal(job_id, {"action": "confirm", "answers": answers})
    if not signaled:
        raise HTTPException(409,
            "Pipeline 尚未進入等待狀態，請稍後重試")
    return {"job_id": job_id, "message": "CLARIFY 確認，pipeline 繼續"}


@router.post("/api/v1/projects/fork", status_code=201)
async def fork_template(req: ForkTemplateRequest) -> dict:
    canned_path = Path(__file__).resolve().parent.parent.parent / "v6" / "canned" / f"{req.template_id}.json"
    if not canned_path.exists():
        raise HTTPException(404, f"找不到範本 canned bridge: {req.template_id}")
    try:
        bridge = json.loads(canned_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"canned bridge 解析失敗: {exc}")

    bridge.pop("_canned_demo", None)
    bridge["forked_from_template"] = req.template_id
    bridge["project_name"] = f"{bridge.get('project_name', req.template_id)}_fork"

    # Verify the baked assembly enclosure actually exists before asserting SUCCESS.
    # Mirrors main._scan_canned_baked: cad_output.bottom_stl ref + the referenced STL
    # on disk. Without it the fork would render components with NO 外殼 (ghost boxes)
    # while still claiming a fully-successful phase-5 job — an always-green gate.
    cad_output = bridge.get("cad_output", {}) or {}
    bottom_stl_ref = cad_output.get("bottom_stl")
    canned_root = canned_path.parent.parent  # .../v6
    if not bottom_stl_ref:
        raise HTTPException(
            422,
            f"範本 '{req.template_id}' 尚未 bake 外殼（cad_output.bottom_stl 缺失），"
            f"無法 fork 為成功專案。請先執行 bake_canned_full。",
        )
    if not (canned_root / str(bottom_stl_ref).lstrip("/")).exists():
        raise HTTPException(
            422,
            f"範本 '{req.template_id}' 的外殼 STL 不存在於磁碟（{bottom_stl_ref}），"
            f"無法 fork 為成功專案。請先執行 bake_canned_full。",
        )

    checkpoint_phase = bridge.get("checkpoint_phase")
    if checkpoint_phase is None:
        raise HTTPException(
            422,
            f"範本 '{req.template_id}' 缺少 checkpoint_phase，無法判定完成階段。",
        )

    job = Job(
        project_name=bridge["project_name"],
        instruction=bridge.get("_instruction", ""),
        status=JobStatus.SUCCESS,
    )
    job.current_phase = checkpoint_phase
    job.lock_path = default_lock_path(job.job_id)
    job.bridge_path = save_bridge(job.job_id, bridge)
    _get_queue().enqueue(job)
    token = create_token(job.job_id)
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "bridge_path": job.bridge_path,
        "forked_from_template": req.template_id,
        "token": token,
        "stream_url": f"/api/v1/jobs/{job.job_id}/stream",
    }


@router.get("/api/generate", deprecated=True)
async def sse_generate(
    project: str = "my_project",
    instruction: str = Query(default="", max_length=2000),
    resume_job_id: str = "",
    resume_from: int = 0,
    token_job_id: str = Depends(get_token_job_id),
):
    q = _get_queue()

    if resume_job_id and resume_from > 0:
        require_job_owner(token_job_id, resume_job_id)
        existing_job = q.get(resume_job_id)
        if not existing_job:
            raise HTTPException(404, f"找不到 Job: {resume_job_id}")
        if not load_bridge(resume_job_id):
            raise HTTPException(404, f"找不到 Bridge JSON: {resume_job_id}")
        job = existing_job
        job.status = JobStatus.PENDING
        job.error = None
        q.update(job)
        decision_trail.log(job.job_id, "pipeline_resume", {
            "resume_from": resume_from,
        })
    else:
        if not instruction:
            raise HTTPException(400, "instruction 不能為空")
        bridge = default_bridge(project, instruction)
        job = Job(project_name=project, instruction=instruction, status=JobStatus.PENDING)
        job.lock_path   = default_lock_path(job.job_id)
        job.bridge_path = save_bridge(job.job_id, bridge)
        q.enqueue(job)
        decision_trail.log(job.job_id, "job_created", {"project": project, "instruction": instruction})

    skip_env = os.environ.get("SKIP_PHASES", "").strip()
    skip_phases = [int(x) for x in skip_env.split(",") if x.strip().isdigit()] if skip_env else []
    # VLM REMOVED — P6 always skipped by PipelineRunner
    runner = make_runner(
        q,
        phase7_timeout_s=30,
        skip_phases=skip_phases,
        resume_from=resume_from,
    )

    return StreamingResponse(
        _make_event_stream(runner, job, q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Deprecation": "true",
            "Link": '</api/v1/jobs>; rel="successor-version"',
        },
    )
