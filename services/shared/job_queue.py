"""shared/job_queue.py — SQLite 持久化 Job Queue。

Schema（單表）：
  jobs(job_id TEXT PK, data TEXT, status TEXT, updated_at REAL)

所有 Job 物件序列化為 JSON 存入 data 欄位，status / updated_at 額外索引加速查詢。
"""
from __future__ import annotations
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from .models import Job, JobStatus, PhaseResult, PhaseID

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    status     TEXT NOT NULL,
    updated_at REAL NOT NULL,
    saved      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_updated ON jobs(updated_at DESC);

CREATE TABLE IF NOT EXISTS processed_step_ids (
    step_id    TEXT PRIMARY KEY,
    job_id     TEXT NOT NULL,
    created_at REAL NOT NULL
);
"""


class JobQueue:
    """執行緒安全的 SQLite Job Queue。"""

    def __init__(self, db_path: str = "/tmp/cadhllm_jobs.db"):
        self._db_path = db_path
        self._lock    = threading.Lock()
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.executescript(_CREATE_TABLE)
                # Migration: add `saved` column to existing DBs（idx_saved 統一在最後建）
                cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
                if "saved" not in cols:
                    conn.execute("ALTER TABLE jobs ADD COLUMN saved INTEGER NOT NULL DEFAULT 0")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_saved ON jobs(saved)")
                conn.commit()
            finally:
                conn.close()

    def _exec(self, fn):
        """Execute fn(conn) under lock, ensuring connection is always closed."""
        with self._lock:
            conn = self._conn()
            try:
                result = fn(conn)
                conn.commit()
                return result
            finally:
                conn.close()

    # ── CRUD ──────────────────────────────────────────────
    def enqueue(self, job: Job) -> Job:
        job.touch()
        self._exec(lambda c: c.execute(
            "INSERT INTO jobs(job_id, data, status, updated_at, saved) VALUES(?,?,?,?,?)",
            (job.job_id, json.dumps(job.to_dict()), job.status.value, job.updated_at, int(job.saved)),
        ))
        return job

    def get(self, job_id: str) -> Optional[Job]:
        row = self._exec(lambda c: c.execute(
            "SELECT data FROM jobs WHERE job_id=?", (job_id,)
        ).fetchone())
        return self._row_to_job(row["data"]) if row else None

    def update(self, job: Job):
        job.touch()
        self._exec(lambda c: c.execute(
            "UPDATE jobs SET data=?, status=?, updated_at=?, saved=? WHERE job_id=?",
            (json.dumps(job.to_dict()), job.status.value, job.updated_at, int(job.saved), job.job_id),
        ))

    def list_by_status(self, status: JobStatus, limit: int = 50) -> List[Job]:
        rows = self._exec(lambda c: c.execute(
            "SELECT data FROM jobs WHERE status=? ORDER BY updated_at DESC LIMIT ?",
            (status.value, limit),
        ).fetchall())
        return [self._row_to_job(r["data"]) for r in rows]

    def list_saved(self, limit: int = 50) -> List[Job]:
        rows = self._exec(lambda c: c.execute(
            "SELECT data FROM jobs WHERE saved=1 ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall())
        return [self._row_to_job(r["data"]) for r in rows]

    def list_all(self, limit: int = 100) -> List[Job]:
        rows = self._exec(lambda c: c.execute(
            "SELECT data FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall())
        return [self._row_to_job(r["data"]) for r in rows]

    def delete(self, job_id: str):
        self._exec(lambda c: c.execute("DELETE FROM jobs WHERE job_id=?", (job_id,)))

    def purge_unsaved_terminal(self, grace_s: float = 30.0) -> int:
        """刪除「未儲存」的終結態 job（FAILED / CANCELLED）+ 殭屍 RUNNING/WAITING。

        grace_s：終結態 / 殭屍 須在此秒數之前最後更新，避免在 SSE 收尾期間誤刪。
        回傳：刪除筆數。
        """
        cutoff = time.time() - grace_s
        terminal = (JobStatus.FAILED.value, JobStatus.CANCELLED.value)
        result = self._exec(lambda c: c.execute(
            "DELETE FROM jobs WHERE saved=0 AND status IN (?,?) AND updated_at<?",
            (*terminal, cutoff),
        ))
        return result.rowcount if result else 0

    def purge_zombies(self, zombie_timeout_s: float) -> int:
        """直接刪除「未儲存」且過久未更新的 RUNNING / WAITING / WAITING_CLARIFY job。"""
        cutoff = time.time() - zombie_timeout_s
        live = (JobStatus.RUNNING.value, JobStatus.WAITING.value, JobStatus.WAITING_CLARIFY.value)
        result = self._exec(lambda c: c.execute(
            "DELETE FROM jobs WHERE saved=0 AND status IN (?,?,?) AND updated_at<?",
            (*live, cutoff),
        ))
        return result.rowcount if result else 0

    # ── 冪等性 step_id ────────────────────────────────────
    def is_step_processed(self, step_id: str) -> bool:
        row = self._exec(lambda c: c.execute(
            "SELECT 1 FROM processed_step_ids WHERE step_id=?", (step_id,)
        ).fetchone())
        return row is not None

    def mark_step_processed(self, step_id: str, job_id: str):
        self._exec(lambda c: c.execute(
            "INSERT OR IGNORE INTO processed_step_ids(step_id, job_id, created_at) VALUES(?,?,?)",
            (step_id, job_id, time.time()),
        ))

    def cleanup_old_steps(self, max_age_s: float = 86400):
        cutoff = time.time() - max_age_s
        self._exec(lambda c: c.execute(
            "DELETE FROM processed_step_ids WHERE created_at<?", (cutoff,)
        ))

    # ── 反序列化 ──────────────────────────────────────────
    @staticmethod
    def _row_to_job(data_json: str) -> Job:
        d = json.loads(data_json)
        phase_results = []
        for pr in d.get("phase_results", []):
            r = PhaseResult(
                phase      = PhaseID(pr["phase"]),
                status     = JobStatus(pr["status"]),
                started_at = pr.get("started_at", time.time()),
                ended_at   = pr.get("ended_at"),
                artifacts  = pr.get("artifacts", {}),
                error      = pr.get("error"),
            )
            phase_results.append(r)

        return Job(
            job_id       = d["job_id"],
            project_name = d.get("project_name", ""),
            instruction  = d.get("instruction", ""),
            status       = JobStatus(d["status"]),
            current_phase= d.get("current_phase"),
            phase_results= phase_results,
            bridge_path  = d.get("bridge_path"),
            lock_path    = d.get("lock_path"),
            created_at   = d.get("created_at", time.time()),
            updated_at   = d.get("updated_at", time.time()),
            error        = d.get("error"),
            saved        = bool(d.get("saved", False)),
        )
