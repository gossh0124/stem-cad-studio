"""phase_handlers/base.py — 所有 Phase Handler 的抽象基底類別。

每個 Phase Handler 封裝一個 Phase 的核心邏輯，
透過 execute(job, bridge) → (bridge_out, artifacts) 介面對外暴露。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple

import logging

from ..shared.models import Job, JobStatus, PhaseID, PhaseResult
from ..shared.bridge_store import save_bridge as _raw_save_bridge

_log = logging.getLogger("cadhllm.phase_handler")


class PhaseHandler(ABC):
    """Phase Handler 抽象基底。

    子類必須實作：
      phase_id: PhaseID    — 對應的 Phase 編號
      execute()            — 核心業務邏輯
    """

    phase_id: PhaseID

    def run(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, PhaseResult]:
        """執行此 Phase，回傳 (更新後的 bridge, PhaseResult)。"""
        result = PhaseResult(phase=self.phase_id, status=JobStatus.RUNNING)
        if progress_cb:
            progress_cb(f"[Phase {self.phase_id.value}] 開始執行")
        try:
            bridge_out, artifacts = self.execute(job, bridge, progress_cb)
            result.finish(JobStatus.SUCCESS, artifacts)
            if progress_cb:
                progress_cb(f"[Phase {self.phase_id.value}] ✅ 完成")
            return bridge_out, result
        except Exception as exc:
            result.finish(JobStatus.FAILED, error=str(exc))
            if progress_cb:
                progress_cb(f"[Phase {self.phase_id.value}] ❌ 失敗：{exc}")
            raise

    @staticmethod
    def _save_bridge_safe(
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Optional[str]:
        """save_bridge with error handling; returns path or None."""
        try:
            return _raw_save_bridge(job.job_id, bridge)
        except RuntimeError as exc:
            _log.error("[Phase] bridge save failed: %s", exc)
            if progress_cb:
                progress_cb(f"⚠️ bridge JSON 儲存失敗：{exc}")
            return None

    @abstractmethod
    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]],
    ) -> Tuple[dict, Dict[str, Any]]:
        """
        執行 Phase 邏輯。
        Returns:
          bridge_out : 更新後的 bridge dict（只可新增欄位）
          artifacts  : 此 Phase 產出物路徑/摘要
        """
