"""shared/bridge_store.py — Bridge JSON 讀寫封裝 + EventRegistry。

路徑策略：
  Drive: {DRIVE_ROOT}/state/{job_id}.json   (primary)
  Local: {tempdir}/cadhllm_state/{job_id}.json   (fallback / Colab-less env)
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import sys as _sys

def _default_drive_root() -> str:
    """Colab 時用 Drive，Windows/本地時用專案 output/ 目錄。"""
    env = os.environ.get("CADHLLM_DRIVE_ROOT")
    if env:
        return env
    if _sys.platform == "win32" or not Path("/content/drive").exists():
        # 本地模式：專案根目錄下的 output/
        return str(Path(__file__).parents[2] / "output")
    return "/content/drive/MyDrive/CADHLLM"

DRIVE_ROOT = _default_drive_root()
LOCAL_ROOT = os.environ.get("CADHLLM_LOCAL_STATE",
             str(Path(tempfile.gettempdir()) / "cadhllm_state"))


def _drive_path(job_id: str) -> str:
    return f"{DRIVE_ROOT}/state/{job_id}.json"

def _local_path(job_id: str) -> str:
    return f"{LOCAL_ROOT}/{job_id}.json"


import re as _re
import logging as _logging
from datetime import datetime as _dt

_log = _logging.getLogger("cadhllm.bridge_store")


def project_output_dir(job_id: str, project_name: str = "",
                       date_str: str = "") -> Path:
    """統一的專案輸出目錄：output/{project_slug}_{YYYY-MM-DD}/
    內含子目錄 cad/, bom/, firmware/, sop/, state/。
    """
    slug = _re.sub(r"[^\w]", "_", (project_name or "project"))[:30].strip("_") or "project"
    ds = date_str or _dt.now().strftime("%Y-%m-%d")
    base = Path(DRIVE_ROOT) / f"{slug}_{ds}"
    base.mkdir(parents=True, exist_ok=True)
    return base


# NOTE: event_publisher.py has a parallel _CATEGORY_KEYWORDS (list format).
# Keep categories in sync when editing either location.
_CATEGORY_KEYWORDS = {
    "Smart_Home":      r"light|lamp|bulb|switch|sensor|night|smart home|automation|夜燈|燈|開關|自動化|居家",
    "Robotics":        r"robot|motor|arm|wheel|servo|drive|chassis|機器人|馬達|輪|手臂",
    # 2026-05-08 移除 Wearables：戶外/穿戴 → Layer 4 進階未來工作
    "Interactive_Art": r"art|music|sound|color|led strip|neopixel|display|互動|藝術|音樂|燈效",
    "Gardening":       r"plant|soil|water|pump|irrigat|garden|植物|土壤|澆水|灌溉|盆栽",
    "Security":        r"security|alarm|lock|camera|detect|pir|motion|burglar|intruder|wifi alert|siren|安全|警報|鎖|監控|偵測|防盜|入侵",
    "Education":       r"learn|teach|stem|school|experiment|學習|教學|實驗|學校",
}


def _infer_default_category(instruction: str) -> str:
    """Keyword-based category inference from instruction text.

    Iterates in priority order; returns first match or 'Education' as fallback.
    Phase I LLM will overwrite this with a more accurate value.
    """
    import re
    text = instruction.lower()
    for cat, pattern in _CATEGORY_KEYWORDS.items():
        if re.search(pattern, text):
            return cat
    return "Education"


def default_bridge(project_name: str, instruction: str = "") -> dict:
    """Bridge JSON 初始結構 — 全專案唯一來源（SSOT）。"""
    wt = _ENC_DEFAULTS["wall_thickness_mm"]
    mat = _ENC_DEFAULTS["material"]
    maxd = _ENC_DEFAULTS["max_dimension_mm"]
    return {
        "project_name": project_name,
        "project_category": _infer_default_category(instruction),
        "cot_plan": {"parameter_hints": {"wall_thickness_mm": wt, "material": mat}},
        "components": [],
        "enclosure_constraints": {
            "target_size": "compact",
            "max_dimension_mm": maxd,
            "wall_thickness_mm": wt,
            "material": mat,
        },
        "inventory_mentions": [],
        "_instruction": instruction,
    }


def save_bridge(job_id: str, bridge: dict) -> str:
    """儲存 bridge JSON 到所有可用路徑（雙寫冗餘），回傳第一個成功的路徑。

    存檔前執行 L1 結構驗證（缺少必填欄位時拒絕寫入）。
    存檔後如果 bridge 有完整 components，自動索引到 RAG cases collection。
    """
    l1_issues = [i for i in validate_bridge(bridge, phase=0)
                 if "缺少必填欄位" in i or "不是 dict" in i or "為空" in i]
    if l1_issues:
        raise ValueError(
            f"[BridgeStore] bridge 結構驗證失敗，拒絕存檔 (job={job_id}): "
            + "; ".join(l1_issues)
        )
    errors: list[str] = []
    first_ok: str | None = None
    for path in (_drive_path(job_id), _local_path(job_id)):
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(bridge, f, indent=2, ensure_ascii=False)
            if first_ok is None:
                first_ok = path
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            _log.warning("[BridgeStore] 寫入失敗 %s: %s", path, exc)
    if first_ok:
        _rag_index_case(job_id, bridge)
        return first_ok
    raise RuntimeError(
        f"[BridgeStore] 無法寫入 bridge JSON (job={job_id}): "
        + "; ".join(errors)
    )


def _rag_index_case(job_id: str, bridge: dict):
    """在背景自動索引成功案例到 RAG（不阻塞主流程）。"""
    components = bridge.get("components", [])
    if not components or not bridge.get("components_resolved"):
        return
    try:
        from lib.rag import add_case
        add_case(bridge, case_id=job_id)
    except ImportError:
        pass
    except Exception as exc:
        _log.debug("[BridgeStore] RAG 索引跳過: %s", exc)


def load_bridge(job_id: str) -> Optional[dict]:
    """讀取 bridge JSON；Drive 優先，本地次之。損壞時跳過並嘗試下一路徑。"""
    errors: list[str] = []
    for path in (_drive_path(job_id), _local_path(job_id)):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            errors.append(f"{path}: 非 dict 類型 ({type(data).__name__})")
        except json.JSONDecodeError as exc:
            _log.error("[BridgeStore] JSON 損壞 %s: %s", path, exc)
            errors.append(f"{path}: JSON 解析失敗 ({exc})")
        except OSError as exc:
            _log.error("[BridgeStore] 讀取失敗 %s: %s", path, exc)
            errors.append(f"{path}: {exc}")
    if errors:
        _log.warning(
            "[BridgeStore] bridge JSON 載入失敗 (job=%s): %s",
            job_id, "; ".join(errors),
        )
    return None


def write_hitl_lock(job_id: str, command: dict) -> str:
    """Gateway 呼叫：寫入 HITL lock 檔，觸發 Phase VII 讀取。
    主路徑 Drive，失敗時降級至本地 temp。
    """
    errors: list[str] = []
    for base in (f"{DRIVE_ROOT}/hitl", f"{LOCAL_ROOT}/hitl"):
        lock_path = f"{base}/{job_id}.lock"
        try:
            Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
            with open(lock_path, "w", encoding="utf-8") as f:
                json.dump(command, f, ensure_ascii=False)
            return lock_path
        except OSError as exc:
            errors.append(f"{lock_path}: {exc}")
            _log.warning("[BridgeStore] HITL lock 寫入失敗 %s: %s", lock_path, exc)
    raise RuntimeError(
        f"[BridgeStore] ❌ HITL lock 寫入全部失敗 (job={job_id}): "
        + "; ".join(errors)
    )


def default_lock_path(job_id: str) -> str:
    """回傳第一個存在的 lock 路徑，或預設 Drive 路徑。"""
    for base in (f"{DRIVE_ROOT}/hitl", f"{LOCAL_ROOT}/hitl"):
        p = f"{base}/{job_id}.lock"
        if os.path.exists(p):
            return p
    return f"{DRIVE_ROOT}/hitl/{job_id}.lock"


# ── Bridge Schema 驗證 ─────────────────────────────────────────

_BRIDGE_REQUIRED_KEYS = {
    "project_name", "project_category", "cot_plan", "components",
    "enclosure_constraints", "inventory_mentions",
}

from lib.config import TAXONOMY_CONFIG as _TAXONOMY_CONFIG, ENCLOSURE_DEFAULTS as _ENC_DEFAULTS
_VALID_CATEGORIES = set(_TAXONOMY_CONFIG["project_categories"])
_CORE_ROLES = set(_TAXONOMY_CONFIG["core_roles"])


def validate_bridge(bridge: dict, phase: int = 0) -> list[str]:
    """驗證 bridge JSON 結構，回傳問題列表（空 = 通過）。

    phase: 當前 Phase 編號（1-7），用於判斷哪些欄位應已存在。
    """
    issues: list[str] = []

    if not isinstance(bridge, dict):
        return ["bridge 不是 dict"]

    if not bridge:
        return ["bridge 為空"]

    for key in _BRIDGE_REQUIRED_KEYS:
        if key not in bridge:
            issues.append(f"缺少必填欄位: {key}")

    cat = bridge.get("project_category", "")
    if cat and cat not in _VALID_CATEGORIES:
        issues.append(f"不合法的 project_category: {cat}")

    components = bridge.get("components", [])
    if not isinstance(components, list):
        issues.append("components 必須為 list")
    elif phase >= 2 and not components:
        issues.append("Phase II 之後 components 不可為空")
    else:
        roles_found = {c.get("role") for c in components if isinstance(c, dict)}
        if phase >= 2:
            for role in _CORE_ROLES:
                if role not in roles_found:
                    issues.append(f"缺少核心角色元件: {role}")

    enc = bridge.get("enclosure_constraints")
    if phase >= 1 and enc is not None:
        if not isinstance(enc, dict):
            issues.append("enclosure_constraints 必須為 dict")

    return issues


# ── EventRegistry：取代 file-lock 輪詢的執行緒事件驅動 ──────

class EventRegistry:
    """以 job_id 為鍵的事件註冊表，支援同步與非同步等待。

    Phase Handler 可透過 wait()（同步）或 wait_async()（非同步）等待信號，
    Gateway 在 async 端呼叫 signal() 喚醒等待方。
    wait_async() 不佔用 OS 執行緒，避免 thread pool starvation。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: Dict[str, threading.Event] = {}
        self._payloads: Dict[str, Optional[dict]] = {}
        self._async_events: Dict[str, Any] = {}
        self._async_loops: Dict[str, Any] = {}

    def register(self, job_id: str) -> threading.Event:
        with self._lock:
            ev = threading.Event()
            self._events[job_id] = ev
            self._payloads[job_id] = None
            return ev

    def signal(self, job_id: str, payload: dict) -> bool:
        """設定 payload 並喚醒等待中的執行緒/協程。回傳是否有對應的事件。"""
        with self._lock:
            ev = self._events.get(job_id)
            if ev is None:
                return False
            self._payloads[job_id] = payload
            ev.set()
            aev = self._async_events.get(job_id)
            loop = self._async_loops.get(job_id)
            if aev and loop:
                loop.call_soon_threadsafe(aev.set)
            return True

    def wait(self, job_id: str, timeout: float) -> Optional[dict]:
        """阻塞直到收到 signal 或逾時。回傳 payload 或 None（逾時）。"""
        ev = self._events.get(job_id)
        if ev is None:
            return None
        ev.wait(timeout=timeout)
        with self._lock:
            payload = self._payloads.get(job_id)
            if ev.is_set():
                ev.clear()
                self._payloads[job_id] = None
            return payload

    async def wait_async(self, job_id: str, timeout: float) -> Optional[dict]:
        """非同步等待，不佔用 OS 執行緒。"""
        import asyncio
        loop = asyncio.get_running_loop()
        aev = asyncio.Event()
        with self._lock:
            self._async_events[job_id] = aev
            self._async_loops[job_id] = loop
            if job_id not in self._events:
                ev = threading.Event()
                self._events[job_id] = ev
                self._payloads[job_id] = None
        try:
            await asyncio.wait_for(aev.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        with self._lock:
            payload = self._payloads.get(job_id)
            ev = self._events.get(job_id)
            if ev and ev.is_set():
                ev.clear()
                self._payloads[job_id] = None
            self._async_events.pop(job_id, None)
            self._async_loops.pop(job_id, None)
            return payload

    def unregister(self, job_id: str) -> None:
        with self._lock:
            self._events.pop(job_id, None)
            self._payloads.pop(job_id, None)
            self._async_events.pop(job_id, None)
            self._async_loops.pop(job_id, None)


event_registry = EventRegistry()


# ── Decision Trail：結構化事件日誌 ──────────────────────────

class DecisionTrail:
    """Append-only JSON-lines log of pipeline decisions for educational analysis."""

    def __init__(self) -> None:
        self._dir = Path(DRIVE_ROOT) / "trails"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, job_id: str) -> Path:
        return self._dir / f"{job_id}.jsonl"

    def log(self, job_id: str, event_type: str, data: dict | None = None) -> None:
        entry = {
            "ts": time.time(),
            "iso": _dt.now().isoformat(timespec="seconds"),
            "type": event_type,
            "data": data or {},
        }
        try:
            with self._lock:
                with open(self._path(job_id), "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def read(self, job_id: str) -> list[dict]:
        p = self._path(job_id)
        if not p.exists():
            return []
        entries = []
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries


decision_trail = DecisionTrail()
