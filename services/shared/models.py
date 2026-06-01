"""shared/models.py — Job 資料模型與狀態列舉。"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    PENDING          = "pending"
    RUNNING          = "running"
    WAITING_CLARIFY  = "waiting_clarify"   # Phase I 完成，等待用戶確認
    WAITING          = "waiting_hitl"      # Phase VII 等待人工輸入
    SUCCESS          = "success"
    FAILED           = "failed"
    CANCELLED        = "cancelled"


class PhaseID(int, Enum):
    P1  = 1
    P2  = 2
    P3  = 3
    P4  = 4
    P5  = 5
    P6  = 6
    P7  = 7


@dataclass
class PhaseResult:
    phase:      PhaseID
    status:     JobStatus
    started_at: float = field(default_factory=time.time)
    ended_at:   Optional[float] = None
    artifacts:  Dict[str, Any]  = field(default_factory=dict)
    error:      Optional[str]   = None

    def finish(self, status: JobStatus, artifacts: dict = None, error: str = None):
        self.ended_at = time.time()
        self.status   = status
        if artifacts:
            self.artifacts.update(artifacts)
        self.error = error

    def duration_s(self) -> Optional[float]:
        if self.ended_at:
            return round(self.ended_at - self.started_at, 2)
        return None


@dataclass
class Job:
    job_id:       str              = field(default_factory=lambda: str(uuid.uuid4()))
    project_name: str              = ""
    instruction:  str              = ""
    status:       JobStatus        = JobStatus.PENDING
    current_phase: Optional[int]   = None
    phase_results: List[PhaseResult] = field(default_factory=list)
    bridge_path:  Optional[str]    = None   # Drive 上的 bridge JSON 路徑
    lock_path:    Optional[str]    = None   # HITL lock 檔路徑
    created_at:   float            = field(default_factory=time.time)
    updated_at:   float            = field(default_factory=time.time)
    error:        Optional[str]    = None
    saved:        bool             = False   # 用戶確認儲存後才會列入「近期專案」

    def __post_init__(self):
        if self.project_name is not None:
            self.project_name = str(self.project_name).strip()
        if self.instruction is not None:
            self.instruction = str(self.instruction).strip()

    def touch(self):
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "job_id":        self.job_id,
            "project_name":  self.project_name,
            "instruction":   self.instruction,
            "status":        self.status.value,
            "current_phase": self.current_phase,
            "created_at":    self.created_at,
            "updated_at":    self.updated_at,
            "error":         self.error,
            "saved":         self.saved,
            "phase_results": [
                {
                    "phase":      r.phase.value,
                    "status":     r.status.value,
                    "started_at": r.started_at,
                    "ended_at":   r.ended_at,
                    "duration_s": r.duration_s(),
                    "artifacts":  r.artifacts,
                    "error":      r.error,
                }
                for r in self.phase_results
            ],
        }
