"""services/pipeline/async_executor.py — Async execution patterns (mixin).

Extracted from pipeline_runner.py (STR6 四拆: async_executor).
Provides AsyncExecutorMixin that PipelineRunner inherits.
"""
from __future__ import annotations
import asyncio
import traceback
from typing import Callable, List, Optional

from ..shared.models import Job, JobStatus, PhaseID
from ..shared.bridge_store import (
    load_bridge, validate_bridge, event_registry, decision_trail,
)
from . import gate_logic, event_publisher
from .clarify import apply_clarify_answers as _apply_clarify_answers
from ..phase_handlers._phase7_helpers import write_final_bom, write_assembly_sop


class AsyncExecutorMixin:
    """Async execution methods for PipelineRunner.

    Expects on self: _handlers, _queue, _should_skip, _resume_from,
    _clarify_timeout_s, _skip, _default_bridge, _stamp_checkpoint,
    MAX_GATE_ITERATIONS.
    """

    async def run_async(
        self,
        job: Job,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Job:
        """Whole pipeline in thread pool (legacy wrapper)."""
        return await asyncio.to_thread(self.run, job, progress_cb)

    async def run_async_segmented(
        self,
        job: Job,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Job:
        """Segmented async: HITL wait points use asyncio.Event, no OS thread."""
        _emit = event_publisher.emit
        is_resume = self._resume_from > 0
        if is_resume:
            _emit(progress_cb,
                f"🔄 Pipeline 從 Phase {self._resume_from} 恢復："
                f"{job.project_name} ({job.job_id})")
        else:
            _emit(progress_cb,
                f"🚀 Pipeline 開始：{job.project_name} ({job.job_id})")

        bridge = load_bridge(job.job_id) or self._default_bridge(job)

        job.status = JobStatus.RUNNING
        self._queue.update(job)
        decision_trail.log(job.job_id, "pipeline_start", {
            "project_name": job.project_name,
            "instruction": job.instruction[:200],
            "mode": "segmented_async",
            "resume_from": self._resume_from,
        })

        # ── Segment 1: Phase I (in thread) ──
        if not self._should_skip(1):
            bridge, job = await self._run_phases_in_thread(
                job, bridge, progress_cb, [PhaseID.P1])
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            # ── Clarify Gate (async, no thread occupied) ──
            _emit(progress_cb, "⏸ Phase I 完成 — 等待用戶確認 CLARIFY…")
            job.status = JobStatus.WAITING_CLARIFY
            job.current_phase = 1
            self._queue.update(job)

            event_registry.register(job.job_id)
            clarify_cmd = await event_registry.wait_async(
                job.job_id, timeout=self._clarify_timeout_s)
            event_registry.unregister(job.job_id)

            if clarify_cmd and clarify_cmd.get("action") == "cancel":
                _emit(progress_cb, "❌ 用戶取消 Pipeline")
                job.status = JobStatus.CANCELLED
                self._queue.update(job)
                return job
            if clarify_cmd and clarify_cmd.get("answers"):
                bridge["_clarify_answers"] = clarify_cmd["answers"]
                _apply_clarify_answers(
                    bridge, clarify_cmd["answers"],
                    emit=lambda m: _emit(progress_cb, m))
            decision_trail.log(job.job_id, "clarify_confirmed", {
                "had_answers": bool(
                    clarify_cmd and clarify_cmd.get("answers")),
                "timed_out": clarify_cmd is None,
            })
            _emit(progress_cb, "✓ CLARIFY 確認 — 繼續 Phase II")
            job.status = JobStatus.RUNNING
            self._queue.update(job)
        else:
            _emit(progress_cb, "✓  Phase 1 已完成（checkpoint）")

        # ── Segment 2a-1: Phase II (in thread) + P2 Power Gate ──
        phase2_only = [p for p in PhaseID
                       if p.value == 2 and not self._should_skip(p.value)]
        if phase2_only:
            bridge, job = await self._run_phases_in_thread(
                job, bridge, progress_cb, phase2_only)
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            for _gate_iter in range(self.MAX_GATE_ITERATIONS):
                gate_action = await gate_logic.p2_power_gate_async(
                    job, bridge, self._queue, progress_cb, _emit)
                if gate_action == "continue":
                    break
                _emit(progress_cb, "🔄 元件已替換，重跑 Phase II…")
                bridge, job = await self._run_phases_in_thread(
                    job, bridge, progress_cb, phase2_only)
                if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                    return job
            else:
                # 達到替換上限但 gate 從未回傳 "continue" → 電源警告仍未解除。
                # 不可強制繼續送進 CAD 生成;除非使用者明確 override(bridge
                # 上 power_warning_phase2.user_override),否則 fail job。
                _pwr = bridge.get("power_warning_phase2") or {}
                if _pwr.get("user_override"):
                    _emit(progress_cb,
                        f"⚠️ 已達 {self.MAX_GATE_ITERATIONS} 次 P2 替換上限，"
                        f"使用者 override,繼續")
                else:
                    _emit(progress_cb,
                        f"❌ 已達 {self.MAX_GATE_ITERATIONS} 次 P2 替換上限,"
                        f"電源約束仍未通過 — 中止 Pipeline")
                    job.status = JobStatus.FAILED
                    job.error = (
                        f"P2 power gate 在 {self.MAX_GATE_ITERATIONS} 次替換後"
                        f"仍未通過電源約束;未設定 user_override,中止。")
                    self._queue.update(job)
                    return job
            job.status = JobStatus.RUNNING
            self._queue.update(job)
        elif self._resume_from > 2:
            _emit(progress_cb, "✓  Phase 2 已完成（checkpoint）")

        # ── Segment 2a-2: Phase III (in thread) + P3 Constraint Gate ──
        phase3_only = [p for p in PhaseID
                       if p.value == 3 and not self._should_skip(p.value)]
        if phase3_only:
            bridge, job = await self._run_phases_in_thread(
                job, bridge, progress_cb, phase3_only)
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            for _gate_iter in range(self.MAX_GATE_ITERATIONS):
                gate_action = await gate_logic.p3_constraint_gate_async(
                    job, bridge, self._queue, progress_cb, _emit)
                if gate_action == "continue":
                    break
                _emit(progress_cb, "🔄 元件已替換，退回 Phase II 重新驗證…")
                if phase2_only:
                    bridge, job = await self._run_phases_in_thread(
                        job, bridge, progress_cb, phase2_only)
                    if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                        return job
                bridge, job = await self._run_phases_in_thread(
                    job, bridge, progress_cb, phase3_only)
                if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                    return job
            else:
                # 達到替換上限但 gate 從未回傳 "continue" → 電氣約束仍未通過
                # (phase3_constraint_check.overall_ok=False)。async 路徑無
                # phase_preflight 把關,不可強制繼續;除非 user_override,否則 fail。
                _check = bridge.get("phase3_constraint_check", {}) or {}
                if _check.get("user_override"):
                    _emit(progress_cb,
                        f"⚠️ 已達 {self.MAX_GATE_ITERATIONS} 次替換上限，"
                        f"使用者 override,繼續")
                else:
                    _emit(progress_cb,
                        f"❌ 已達 {self.MAX_GATE_ITERATIONS} 次替換上限,"
                        f"電氣約束仍未通過 — 中止 Pipeline")
                    job.status = JobStatus.FAILED
                    job.error = (
                        f"P3 constraint gate 在 {self.MAX_GATE_ITERATIONS} 次替換後"
                        f"仍未通過電氣約束 (overall_ok=False);未設定 user_override,中止。")
                    self._queue.update(job)
                    return job
            job.status = JobStatus.RUNNING
            self._queue.update(job)
        elif self._resume_from > 3:
            _emit(progress_cb, "✓  Phase 3 已完成（checkpoint）")

        # ── Segment 2b: Phase IV–VI (in thread) ──
        late_phases = [p for p in PhaseID
                       if 4 <= p.value <= 6
                       and not self._should_skip(p.value)]
        if late_phases:
            bridge, job = await self._run_phases_in_thread(
                job, bridge, progress_cb, late_phases)
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                return job

        # ── Phase VII HITL (async wait loop) ──
        if not self._should_skip(7):
            _emit(progress_cb, "⏸ Phase VII 等待人工輸入（HITL）")
            job.status = JobStatus.WAITING
            job.current_phase = 7
            self._queue.update(job)

            bridge, job = await self._run_phase7_async(
                job, bridge, progress_cb)
            if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
                return job

            rerun_from = bridge.pop("_needs_rerun_from_phase", None)
            if rerun_from is not None:
                _emit(progress_cb,
                    f"🔄 HITL 元件異動，退回 Phase {rerun_from} 重跑…")
                rerun_ids = [p for p in PhaseID
                             if p.value >= rerun_from and p != PhaseID.P7
                             and p.value not in self._skip]
                bridge, job = await self._run_phases_in_thread(
                    job, bridge, progress_cb, rerun_ids)

        if job.status in (JobStatus.RUNNING, JobStatus.WAITING,
                          JobStatus.WAITING_CLARIFY):
            job.status = JobStatus.SUCCESS
            self._queue.update(job)
            decision_trail.log(job.job_id, "pipeline_complete", {
                "total_phases": len(job.phase_results),
                "mode": "segmented_async",
            })
            _emit(progress_cb, "🎉 Pipeline 完成！")

        return job

    async def _run_phases_in_thread(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]],
        phase_ids: List[PhaseID],
    ) -> tuple:
        """Run a group of phases in thread pool (no HITL wait)."""
        _emit = event_publisher.emit

        def _segment():
            nonlocal bridge
            for phase_id in phase_ids:
                handler = self._handlers.get(phase_id)
                if handler is None:
                    continue
                job.current_phase = phase_id.value
                self._queue.update(job)
                try:
                    bridge, result = handler.run(job, bridge, progress_cb)
                    job.phase_results.append(result)
                    self._queue.update(job)
                    decision_trail.log(job.job_id, "phase_complete", {
                        "phase": phase_id.value,
                        "duration_s": result.duration_s(),
                        "status": result.status.value,
                    })
                    issues = validate_bridge(bridge, phase=phase_id.value)
                    if issues:
                        for iss in issues:
                            _emit(progress_cb,
                                f"⚠️ Bridge 驗證 (Phase {phase_id.value})"
                                f": {iss}")
                    self._stamp_checkpoint(bridge, phase_id.value)
                    event_publisher.push_phase_data(
                        phase_id, bridge, job, progress_cb)
                except Exception as exc:
                    tb = traceback.format_exc()
                    _emit(progress_cb,
                        f"❌ Phase {phase_id.value} 失敗："
                        f"{exc}\n{tb[:500]}")
                    job.status = JobStatus.FAILED
                    job.error = str(exc)
                    self._queue.update(job)
                    break
            return bridge, job

        bridge, job = await asyncio.to_thread(_segment)
        return bridge, job

    async def _run_phase7_async(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]],
    ) -> tuple:
        """Phase VII HITL wait loop — async event, no thread occupied."""
        from ..phase_handlers.phase7_handler import Phase7Handler
        handler: Phase7Handler = self._handlers[PhaseID.P7]
        max_rounds = handler.max_rounds
        timeout = float(handler.timeout_s)
        remaining = timeout
        rnd = 0
        history = []

        event_registry.register(job.job_id)
        try:
            while rnd < max_rounds and remaining > 0:
                import time as _t
                t0 = _t.monotonic()
                cmd = await event_registry.wait_async(
                    job.job_id, timeout=remaining)
                elapsed = _t.monotonic() - t0
                remaining -= elapsed

                if cmd is None:
                    break

                def _apply_cmd():
                    nonlocal bridge
                    batch = cmd.get("corrections", [cmd])
                    results = []
                    for item in batch:
                        action = item.get("action", "accept")
                        params = item.get("params", {})
                        r = handler._apply(bridge, action, params)
                        results.append(r)
                        if action == "accept":
                            break
                    return results

                results = await asyncio.to_thread(_apply_cmd)
                history.extend(results)
                rnd += len(results)

                if any(r.get("action") == "accept" for r in results):
                    break
        finally:
            event_registry.unregister(job.job_id)

        bridge["hitl_history"] = history
        bridge["hitl_accepted"] = True

        def _post_hitl():
            write_final_bom(job, bridge, progress_cb)
            write_assembly_sop(job, bridge, progress_cb)
            handler._save_bridge_safe(job, bridge, progress_cb)

        await asyncio.to_thread(_post_hitl)

        job.status = JobStatus.RUNNING
        self._queue.update(job)
        return bridge, job
