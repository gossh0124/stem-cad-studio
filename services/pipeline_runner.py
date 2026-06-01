"""services/pipeline_runner.py — CADHLLM Pipeline orchestrator.

Thin coordinator that delegates to:
  - pipeline/gate_logic.py      — P2/P3 gate checks
  - pipeline/event_publisher.py — SSE phase data broadcasting
  - pipeline/async_executor.py  — async execution patterns
  - pipeline/phase_factory.py   — enclosure sizing + component resolution
"""
from __future__ import annotations
import logging
import os
import traceback
from typing import Callable, Dict, List, Optional

_log = logging.getLogger("cadhllm.pipeline_runner")

from .shared.models import Job, JobStatus, PhaseID
from .shared.job_queue import JobQueue
from .shared.bridge_store import (
    load_bridge, validate_bridge, default_bridge,
    event_registry, decision_trail,
)
from .shared.constants import MAX_GATE_ITERATIONS as _MAX_GATE_ITERS, GATE_TIMEOUT_S

# Phase Handlers
from .phase_handlers.phase1_handler import Phase1Handler, Phase1InputError
from .phase_handlers.phase2_handler import Phase2Handler
from .phase_handlers.phase3_handler import Phase3Handler
from .phase_handlers.phase4_handler import Phase4Handler
from .phase_handlers.phase5_handler import Phase5Handler
# VLM REMOVED — Phase6Handler is a no-op stub, pipeline skips P6
from .phase_handlers.phase7_handler import Phase7Handler

# Extracted modules (STR6)
from .pipeline import gate_logic, event_publisher, phase_factory
from .pipeline.async_executor import AsyncExecutorMixin
from .pipeline.clarify import apply_clarify_answers as _apply_clarify_answers

# ── Backward-compatible re-exports ────────────────────────
# Tests and tools import these names from this module.
_phase_preflight = gate_logic.phase_preflight
_auto_size_enclosure = phase_factory.auto_size_enclosure
_build_role_alternatives = event_publisher.build_role_alternatives


def _make_spec_returning_fuzzy(p2h):
    """Wrap Phase2Handler._fuzzy_lookup so it returns ComponentSpec instead of dict.

    component_resolver.py L2 uses identity comparison (`val is spec`) against
    COMPONENT_REGISTRY values (ComponentSpec objects).  Phase2Handler._fuzzy_lookup
    searches self._registry which is {key: spec.to_dict()} — plain dicts —
    so the `is` check never succeeds.

    This wrapper:
      1. Calls p2h._fuzzy_lookup(raw_type) to confirm a match exists.
      2. Re-resolves the same key against COMPONENT_REGISTRY to obtain the
         canonical ComponentSpec, enabling the identity check in resolver L2.
    """
    import re as _re
    from lib.registry import COMPONENT_REGISTRY as _REG

    def _strip(s: str) -> str:
        return _re.sub(r'[^a-z0-9]', '', s.replace("-class", "").lower())

    def _tokens(s: str) -> set:
        s2 = s.replace("-class", "")
        toks: set = set()
        for part in _re.findall(r'[a-zA-Z0-9]+', s2):
            for word in _re.findall(r'[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|$)', part):
                toks.add(word.lower())
        return toks

    # Build lookup tables once (same key-space as _fuzzy_lookup)
    _strip_to_key = {_strip(k): k for k in _REG}

    def wrapped(raw_type: str):
        # Ask p2h whether there is any match at all
        dict_result = p2h._fuzzy_lookup(raw_type)
        if dict_result is None:
            return None

        # Tier 1: strip match (mirrors _fuzzy_lookup Tier 1)
        raw_stripped = _strip(raw_type)
        if raw_stripped in _strip_to_key:
            return _REG[_strip_to_key[raw_stripped]]

        # Tier 2: token-set match (mirrors _fuzzy_lookup Tier 2)
        src_toks = _tokens(raw_type)
        if len(src_toks) > 1:
            for k, spec in _REG.items():
                if src_toks == _tokens(k):
                    return spec

        # Tier 3/4: alias / composite — best-effort dimension fingerprint
        for k, spec in _REG.items():
            if (spec.length_mm == dict_result.get("length_mm") and
                    spec.width_mm == dict_result.get("width_mm")):
                return spec

        # _fuzzy_lookup confirmed a hit but we cannot reverse-lookup — warn and skip L2
        _log.warning(
            "_make_spec_returning_fuzzy: could not reverse-map fuzzy hit for %r; "
            "L2 will be skipped for this component", raw_type
        )
        return None

    return wrapped


class PipelineRunner(AsyncExecutorMixin):
    """Execute Phase I–VII sequentially, broadcasting progress via cb.

    Usage (sync):
        runner = PipelineRunner(queue)
        runner.run(job, progress_cb=my_cb)

    Usage (async, segmented — from AsyncExecutorMixin):
        await runner.run_async_segmented(job, progress_cb=my_cb)
    """

    MAX_GATE_ITERATIONS = _MAX_GATE_ITERS

    def __init__(
        self,
        queue: JobQueue,
        skip_phases: Optional[List[int]] = None,
        phase7_timeout_s: int = 300,
        clarify_timeout_s: int = 600,
        resume_from: int = 0,
        **kwargs,  # absorb legacy max_vlm_rounds
    ):
        self._queue = queue
        self._clarify_timeout_s = clarify_timeout_s
        self._resume_from = resume_from
        # VLM REMOVED — P6 permanently skipped
        skip = set(skip_phases or [])
        skip.add(6)
        self._handlers = {
            PhaseID.P1: Phase1Handler(),
            PhaseID.P2: Phase2Handler(),
            PhaseID.P3: Phase3Handler(),
            PhaseID.P4: Phase4Handler(),
            PhaseID.P5: Phase5Handler(),
            PhaseID.P7: Phase7Handler(timeout_s=phase7_timeout_s),
        }
        self._skip = skip

    # ── Helpers ───────────────────────────────────────────

    @staticmethod
    def _default_bridge(job: Job) -> dict:
        return default_bridge(job.project_name, job.instruction)

    @staticmethod
    def _stamp_checkpoint(bridge: dict, phase: int):
        import time as _time
        bridge["checkpoint"] = {"last_phase": phase, "ts": _time.time()}

    def _should_skip(self, phase_val: int) -> bool:
        if phase_val in self._skip:
            return True
        if self._resume_from and phase_val < self._resume_from:
            return True
        return False

    @staticmethod
    def _emit(cb: Optional[Callable], msg: str):
        event_publisher.emit(cb, msg)

    @staticmethod
    def _overwrite_phase_result(job: Job, phase_val: int, result):
        event_publisher.overwrite_phase_result(job, phase_val, result)

    def _gate_emit_and_apply(self, job, bridge, payload, suggestions,
                             result, progress_cb) -> str:
        return gate_logic.gate_emit_and_apply(
            job, bridge, payload, suggestions, result,
            progress_cb, self._queue, event_publisher.emit)

    def _p2_power_gate_payload(self, job, bridge):
        return gate_logic.p2_power_gate_payload(job, bridge)

    def _p3_gate_payload(self, job, bridge):
        return gate_logic.p3_gate_payload(job, bridge)

    # ── Main entry ────────────────────────────────────────

    def run(
        self,
        job: Job,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Job:
        """Execute the full Pipeline, return final Job."""
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
            "resume_from": self._resume_from,
        })

        for phase_id in PhaseID:
            if self._should_skip(phase_id.value):
                if phase_id.value in self._skip:
                    _emit(progress_cb,
                        f"⏭  Phase {phase_id.value} 跳過")
                elif is_resume:
                    _emit(progress_cb,
                        f"✓  Phase {phase_id.value} 已完成（checkpoint）")
                continue

            handler = self._handlers.get(phase_id)
            if handler is None:
                continue

            preflight_err = gate_logic.phase_preflight(phase_id, bridge)
            if preflight_err:
                _emit(progress_cb,
                    f"⚠️ Phase {phase_id.value} pre-flight 失敗："
                    f"{preflight_err}")
                raise ValueError(preflight_err)

            if phase_id == PhaseID.P7:
                _emit(progress_cb,
                    "⏸  Phase VII 等待人工輸入（HITL）— lock-file 模式")
                job.status = JobStatus.WAITING
                job.current_phase = phase_id.value
                self._queue.update(job)
            else:
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
                    critical = [i for i in issues
                                if "缺少必填欄位" in i or "不可為空" in i]
                    for iss in issues:
                        _emit(progress_cb,
                            f"⚠️ Bridge 驗證 (Phase {phase_id.value})"
                            f": {iss}")
                    if critical and phase_id.value >= 2:
                        raise ValueError(
                            f"Bridge 結構驗證失敗"
                            f"（Phase {phase_id.value}）：\n"
                            + "\n".join(critical)
                        )

                if phase_id == PhaseID.P1:
                    phase_factory.auto_size_enclosure(
                        bridge,
                        emit=lambda m: _emit(progress_cb, m),
                    )
                    p2h = self._handlers.get(PhaseID.P2)
                    fuzzy_fn = _make_spec_returning_fuzzy(p2h) if p2h else None
                    phase_factory.resolve_components(
                        job, bridge, fuzzy_fn, progress_cb, _emit)

                self._stamp_checkpoint(bridge, phase_id.value)
                event_publisher.push_phase_data(
                    phase_id, bridge, job, progress_cb)

                if phase_id == PhaseID.P2:
                    for _gate_iter in range(self.MAX_GATE_ITERATIONS):
                        gate_action = gate_logic.p2_power_gate(
                            job, bridge, self._queue, progress_cb, _emit)
                        if gate_action == "continue":
                            break
                        _emit(progress_cb,
                            "🔄 元件已替換，重跑 Phase II…")
                        bridge, r2 = self._handlers[PhaseID.P2].run(
                            job, bridge, progress_cb)
                        self._overwrite_phase_result(job, 2, r2)
                        event_publisher.push_phase_data(
                            PhaseID.P2, bridge, job, progress_cb)
                    else:
                        _emit(progress_cb,
                            f"⚠️ 已達 {self.MAX_GATE_ITERATIONS} "
                            f"次替換上限，強制繼續")
                    job.status = JobStatus.RUNNING
                    self._queue.update(job)

                if phase_id == PhaseID.P3:
                    for _gate_iter in range(self.MAX_GATE_ITERATIONS):
                        gate_action = gate_logic.p3_constraint_gate(
                            job, bridge, self._queue, progress_cb, _emit)
                        if gate_action == "continue":
                            break
                        _emit(progress_cb,
                            "🔄 元件已替換，退回 Phase II 重新驗證…")
                        job.current_phase = 2
                        self._queue.update(job)
                        bridge, r2 = self._handlers[PhaseID.P2].run(
                            job, bridge, progress_cb)
                        self._overwrite_phase_result(job, 2, r2)
                        event_publisher.push_phase_data(
                            PhaseID.P2, bridge, job, progress_cb)
                        bridge, r3 = self._handlers[PhaseID.P3].run(
                            job, bridge, progress_cb)
                        self._overwrite_phase_result(job, 3, r3)
                        event_publisher.push_phase_data(
                            PhaseID.P3, bridge, job, progress_cb)
                    else:
                        _emit(progress_cb,
                            f"⚠️ 已達 {self.MAX_GATE_ITERATIONS} "
                            f"次替換上限，強制繼續")
                    job.status = JobStatus.RUNNING
                    self._queue.update(job)

                if phase_id == PhaseID.P1:
                    dev_mode = os.environ.get(
                        "CADHLLM_DEVELOPER_MODE", "")
                    _clarify_skip = (
                        bool(dev_mode.lower() in ("1", "true"))
                        or progress_cb is None
                    )
                    if _clarify_skip:
                        bridge["clarify_skipped"] = True
                        _log.info(
                            "Clarify skipped (developer_mode=%s, "
                            "progress_cb=%s)",
                            dev_mode, bool(progress_cb),
                        )
                    else:
                        _emit(progress_cb,
                            "⏸ Phase I 完成 — 等待用戶確認 CLARIFY…")
                        job.status = JobStatus.WAITING_CLARIFY
                        job.current_phase = phase_id.value
                        self._queue.update(job)
                        event_registry.register(job.job_id)
                        clarify_cmd = event_registry.wait(
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
                        _emit(progress_cb,
                            "✓ CLARIFY 確認 — 繼續 Phase II")
                        job.status = JobStatus.RUNNING
                        self._queue.update(job)

            except Phase1InputError as exc:
                # PR3: 抽象輸入 graceful — 只回友善引導，不噴 traceback
                _emit(progress_cb, f"⚠️ Phase {phase_id.value}：{exc}")
                job.status = JobStatus.FAILED
                job.error = str(exc)
                self._queue.update(job)
                return job
            except Exception as exc:
                tb = traceback.format_exc()
                _emit(progress_cb,
                    f"❌ Phase {phase_id.value} 失敗："
                    f"{exc}\n{tb[:500]}")
                job.status = JobStatus.FAILED
                job.error = str(exc)
                self._queue.update(job)
                return job

            if phase_id == PhaseID.P7:
                rerun_from = bridge.pop(
                    "_needs_rerun_from_phase", None)
                if rerun_from is not None:
                    _emit(progress_cb,
                        f"🔄 HITL 元件異動，自動退回 Phase "
                        f"{rerun_from} 重新執行…")
                    _rerun_ids = [
                        pid for pid in PhaseID
                        if pid.value >= rerun_from
                        and pid not in (PhaseID.P7,)
                        and pid.value not in self._skip
                    ]
                    for pid in _rerun_ids:
                        h = self._handlers.get(pid)
                        if h is None:
                            continue
                        pf_err = gate_logic.phase_preflight(
                            pid, bridge)
                        if pf_err:
                            _emit(progress_cb,
                                f"⚠️ HITL rerun Phase {pid.value} "
                                f"pre-flight 失敗：{pf_err}")
                            raise ValueError(pf_err)
                        job.current_phase = pid.value
                        self._queue.update(job)
                        try:
                            bridge, res = h.run(
                                job, bridge, progress_cb)
                            job.phase_results.append(res)
                            self._queue.update(job)
                        except Exception as exc2:
                            tb = traceback.format_exc()
                            _emit(progress_cb,
                                f"❌ Phase {pid.value} 重跑失敗："
                                f"{exc2}\n{tb[:500]}")
                            job.status = JobStatus.FAILED
                            job.error = (
                                f"HITL rerun Phase {pid.value} "
                                f"失敗：{exc2}"
                            )
                            self._queue.update(job)
                            return job

        if job.status in (JobStatus.RUNNING, JobStatus.WAITING,
                          JobStatus.WAITING_CLARIFY):
            job.status = JobStatus.SUCCESS
            self._queue.update(job)
            decision_trail.log(job.job_id, "pipeline_complete", {
                "total_phases": len(job.phase_results),
            })
            _emit(progress_cb, "🎉 Pipeline 完成！")

        return job


def make_runner(queue: JobQueue, **kwargs) -> PipelineRunner:
    """Build a PipelineRunner with optional resume_from."""
    return PipelineRunner(queue, **kwargs)
