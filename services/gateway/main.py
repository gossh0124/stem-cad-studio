"""gateway/main.py — CADHLLM Microservices Gateway（精簡入口）。

啟動：uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 --reload

路由拆分至：
  routes_jobs.py    — Job CRUD + SSE generate
  routes_hitl.py    — HITL 互動端點
  routes_design.py  — 設計輔助 / 元件殼 / Artifact / User Components
"""
from __future__ import annotations
import asyncio
import json
import logging as _log_mod
import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as e:
    raise ImportError("請先安裝 FastAPI：pip install fastapi uvicorn") from e

from ..shared.auth import verify_ws_ticket
from ..shared.job_queue import JobQueue

# ── Route modules ────────────────────────────────────────
from .routes_jobs import router as jobs_router
from .routes_hitl import router as hitl_router
from .routes_design import router as design_router


# ── 全域單例 ──────────────────────────────────────────────
def _default_db_path() -> str:
    env = os.environ.get("CADHLLM_DB")
    if env:
        return env
    import sys as _sys
    if _sys.platform == "win32":
        return str(Path(__file__).parents[2] / "output" / "cadhllm_jobs.db")
    return "/tmp/cadhllm_jobs.db"


DB_PATH = _default_db_path()
_queue  = JobQueue(DB_PATH)

_ws_clients: Dict[str, List[WebSocket]] = {}

_UI_DIR = Path(__file__).parents[2] / "ui"
_V3_DIR = Path(__file__).parents[2] / "v3" / "variants" / "b"
_V4_DIR = Path(__file__).parents[2] / "v4"
_V6_DIR = Path(__file__).parents[2] / "v6"

_ZOMBIE_INTERVAL_S = int(os.environ.get("CADHLLM_ZOMBIE_INTERVAL", "120"))
_ZOMBIE_TIMEOUT_S  = int(os.environ.get("CADHLLM_ZOMBIE_TIMEOUT", "600"))

_gw_log = _log_mod.getLogger("cadhllm.gateway")
if "CADHLLM_ZOMBIE_INTERVAL" not in os.environ:
    _gw_log.info("CADHLLM_ZOMBIE_INTERVAL not set, using default: %d", _ZOMBIE_INTERVAL_S)
if "CADHLLM_ZOMBIE_TIMEOUT" not in os.environ:
    _gw_log.info("CADHLLM_ZOMBIE_TIMEOUT not set, using default: %d", _ZOMBIE_TIMEOUT_S)


async def _broadcast(job_id: str, message: dict):
    clients = _ws_clients.get(job_id, [])
    dead    = []
    for ws in clients:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.remove(ws)


def _scan_shells_l0() -> int:
    """Synchronous startup shell health check (advisory). Run via asyncio.to_thread."""
    shells_dir = Path(__file__).resolve().parent.parent.parent / "shells"
    _log = _log_mod.getLogger("cadhllm.gateway")
    if not shells_dir.exists():
        _log.warning("shells/ directory not found — skip L0 scan")
        return 0

    try:
        from lib.verification.l0_integrity import check_mesh
        from lib.verification.report import Verdict
    except ImportError:
        _log.info("L0 verification unavailable -- skip shell scan")
        return 0

    checked = 0
    failed = []
    for shell_dir in sorted(shells_dir.iterdir()):
        if not shell_dir.is_dir():
            continue
        for candidate in ("base_stl.stl", "mount_stl.stl", "pcb_body.stl"):
            shell_file = shell_dir / candidate
            if shell_file.exists():
                checked += 1
                rpt = check_mesh(str(shell_file))
                if rpt.verdict == Verdict.FAIL:
                    failed.append(f"{shell_dir.name}/{candidate}")

    if failed:
        for f in failed:
            _log.warning("L0 shell scan FAIL: %s", f)
    else:
        _log.info("L0 shell scan OK: %d files checked", checked)
    return len(failed)


def _scan_canned_baked() -> int:
    """Startup completeness check (advisory): warn if any canned demo lacks a baked
    assembly enclosure (cad_output.bottom_stl ref + the referenced STL on disk). Without
    it the demo renders components with no 外殼 (ghost-box shells). Run via to_thread."""
    import json
    canned_dir = Path(__file__).resolve().parent.parent.parent / "v6" / "canned"
    _log = _log_mod.getLogger("cadhllm.gateway")
    if not canned_dir.exists():
        return 0
    unbaked = []
    for bridge in sorted(canned_dir.glob("*.json")):
        if bridge.name == "_index.json":
            continue
        try:
            co = json.loads(bridge.read_text("utf-8")).get("cad_output", {}) or {}
        except (OSError, ValueError):
            continue
        ref = co.get("bottom_stl")
        if not ref:
            unbaked.append(bridge.stem)
        elif not (canned_dir.parent / str(ref).lstrip("/")).exists():
            unbaked.append(bridge.stem + "(ref-missing)")
    if unbaked:
        _log.warning(
            "Canned completeness: %d demo(s) lack baked assembly enclosure — components "
            "will render with NO shell. Fix: python -m scripts.builders.bake_canned_full  [%s]",
            len(unbaked), ", ".join(unbaked[:10]))
    else:
        _log.info("Canned completeness OK: all demos have baked enclosures")
    return len(unbaked)


async def _zombie_cleanup():
    while True:
        await asyncio.sleep(_ZOMBIE_INTERVAL_S)
        try:
            n_zombie  = _queue.purge_zombies(zombie_timeout_s=_ZOMBIE_TIMEOUT_S)
            n_term    = _queue.purge_unsaved_terminal(grace_s=30.0)
            if n_zombie or n_term:
                _log_mod.getLogger("cadhllm.gateway").info(
                    "Zombie sweep: deleted %d zombies, %d terminal unsaved", n_zombie, n_term)
            _queue.cleanup_old_steps(max_age_s=86400)
        except (sqlite3.OperationalError, OSError) as _exc:
            _log_mod.getLogger("cadhllm.gateway").warning("Zombie cleanup error: %s", _exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger = _log_mod.getLogger("cadhllm.gateway")

    _backend = os.environ.get("CADHLLM_BACKEND", "auto")
    if "CADHLLM_BACKEND" not in os.environ:
        _logger.info("CADHLLM_BACKEND not set, using default: %s", _backend)
    try:
        from lib.vllm_client import is_vllm_available, VLLM_BASE_URL
        if is_vllm_available():
            _logger.info("✓ vLLM server 可用 (%s)", VLLM_BASE_URL)
        elif _backend == "vllm":
            _logger.warning("✗ vLLM server 不可用 (%s)，CADHLLM_BACKEND=%s", VLLM_BASE_URL, _backend)
        else:
            _logger.info("vLLM 不可用，CADHLLM_BACKEND=%s → fallback transformers", _backend)
    except ImportError:
        _logger.info("vLLM client 未安裝，使用 transformers 推論")

    if os.environ.get("CADHLLM_SKIP_RAG"):
        # 前端視覺驗證 / 快速啟動用：跳過耗時的 RAG 索引建置（SentenceTransformer +
        # LanceDB）。Phase I 元件推論會不可用，但 canned fork 的 schematic/3D 不需 RAG。
        _logger.info("CADHLLM_SKIP_RAG=1 → 跳過 RAG 初始化（Phase I 推論不可用）")
    else:
        try:
            from lib.rag import ensure_initialized
            ensure_initialized()
            _logger.info("✓ RAG 元件索引已就緒")
        except Exception as e:
            _logger.warning("RAG 初始化跳過: %s", e)

    n_fails = await asyncio.to_thread(_scan_shells_l0)
    if n_fails:
        _logger.warning("%d shell(s) failed L0 — CAD output may show ghost boxes", n_fails)

    await asyncio.to_thread(_scan_canned_baked)

    import concurrent.futures
    _pool_size = int(os.environ.get("CADHLLM_THREAD_POOL", "80"))
    if "CADHLLM_THREAD_POOL" not in os.environ:
        _logger.info("CADHLLM_THREAD_POOL not set, using default: %d", _pool_size)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=_pool_size))
    task = asyncio.create_task(_zombie_cleanup())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── App 組裝 ─────────────────────────────────────────────
app = FastAPI(
    title="CADHLLM Gateway",
    version="1.0.0",
    description="CADHLLM Text-to-CAD Pipeline Gateway Service",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = os.environ.get("CADHLLM_CORS_ORIGINS", "").split(",") if os.environ.get("CADHLLM_CORS_ORIGINS") else [
    "http://localhost:8000", "http://localhost:8080", "http://localhost:8082",
    "http://127.0.0.1:8000", "http://127.0.0.1:8080", "http://127.0.0.1:8082",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ── 開發用 no-cache middleware：前端靜態檔一律不快取 ──
# 在 ASGI 層攔截：(1) 剝除請求的 if-none-match/if-modified-since 防 304
#                  (2) 剝除回應的 etag/last-modified，注入 no-cache
_DEV_NO_CACHE_EXT = (".jsx", ".css", ".html", ".js", ".json", ".stl", ".glb")  # +stl/glb: canned demo enclosures under /canned/ regen fresh on F5
_DEV_NO_CACHE_PREFIX = ("/api/shells/",)  # GLB/STL shell assets — 不快取，F5 即可取最新
_STRIP_REQ = {b"if-none-match", b"if-modified-since"}
_STRIP_RES = {b"etag", b"last-modified"}
_NOCACHE_HEADERS = [
    (b"cache-control", b"no-cache, no-store, must-revalidate"),
    (b"pragma", b"no-cache"),
    (b"expires", b"0"),
]

from starlette.types import ASGIApp, Receive, Scope, Send

class DevNoCacheMiddleware:
    """ASGI middleware：開發環境下前端靜態檔完全不快取。"""
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "").lower()
        needs_nocache = (
            any(path.endswith(ext) for ext in _DEV_NO_CACHE_EXT)
            or any(path.startswith(pfx) for pfx in _DEV_NO_CACHE_PREFIX)
            or path in ("", "/")
        )

        if needs_nocache:
            # 剝除請求中的條件快取 header → StaticFiles 不會回 304
            scope["headers"] = [
                (k, v) for k, v in scope.get("headers", [])
                if k.lower() not in _STRIP_REQ
            ]

            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    raw = message.get("headers", [])
                    # 移除 etag / last-modified / 舊 cache-control
                    filtered = []
                    for k, v in raw:
                        kl = k.lower() if isinstance(k, bytes) else k.lower().encode()
                        if kl in _STRIP_RES or kl == b"cache-control":
                            continue
                        filtered.append((k, v))
                    filtered.extend(_NOCACHE_HEADERS)
                    message["headers"] = filtered
                await send(message)

            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)

app.add_middleware(DevNoCacheMiddleware)


if (_UI_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_UI_DIR / "assets")), name="assets")
if (_UI_DIR / "styles").exists():
    app.mount("/styles", StaticFiles(directory=str(_UI_DIR / "styles")), name="styles")
if (_UI_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=str(_UI_DIR / "js")), name="js")

app.include_router(jobs_router)
app.include_router(hitl_router)
app.include_router(design_router)


# ── UI 靜態入口 ──────────────────────────────────────────
_NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}

@app.get("/")
async def serve_ui():
    v6_index = _V6_DIR / "index.html"
    if v6_index.exists():
        return FileResponse(str(v6_index), media_type="text/html", headers=_NO_CACHE)
    v4_index = _V4_DIR / "CADHLLM Redesign v4.html"
    if v4_index.exists():
        return FileResponse(str(v4_index), media_type="text/html", headers=_NO_CACHE)
    v3_index = _V3_DIR / "index.html"
    if v3_index.exists():
        return FileResponse(str(v3_index), media_type="text/html", headers=_NO_CACHE)
    fallback = _UI_DIR / "index.html"
    if fallback.exists():
        return FileResponse(str(fallback), media_type="text/html", headers=_NO_CACHE)
    return {"detail": "No UI found (checked v6/, v4/, v3/, ui/)"}


# ── WebSocket 端點 ───────────────────────────────────────
@app.websocket("/ws/{job_id}")
async def websocket_progress(ws: WebSocket, job_id: str, ticket: str = ""):
    if not await verify_ws_ticket(ws, job_id, ticket):
        return
    await ws.accept()
    _ws_clients.setdefault(job_id, []).append(ws)
    try:
        job = _queue.get(job_id)
        if job:
            await ws.send_json({"event": "connected", "job": job.to_dict()})
        else:
            await ws.send_json({"event": "error", "detail": f"job {job_id} not found"})

        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                if msg.strip().lower() in ("ping", ""):
                    await ws.send_json({"event": "pong"})
            except asyncio.TimeoutError:
                await ws.send_json({"event": "heartbeat"})

    except WebSocketDisconnect:
        pass
    finally:
        clients = _ws_clients.get(job_id, [])
        if ws in clients:
            clients.remove(ws)


# ── UI 靜態檔（必須放在所有 route 之後）────────────────
if _V6_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_V6_DIR)), name="v6-static")
elif _V4_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_V4_DIR)), name="v4-static")
elif _V3_DIR.exists():
    app.mount("/", StaticFiles(directory=str(_V3_DIR)), name="v3-static")
