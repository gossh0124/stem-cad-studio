"""run_server.py — CADHLLM Gateway 啟動腳本。

用法：
  python run_server.py              # 預設 port 8000
  python run_server.py --port 9000  # 指定 port
  python run_server.py --help
"""
import argparse
import logging
import os
import sys

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError) as exc:
        print(f"[run_server] reconfigure failed: {exc}", file=sys.stderr, flush=True)

    parser = argparse.ArgumentParser(description="CADHLLM Gateway Server")
    parser.add_argument("--host",    default="0.0.0.0",      help="監聽 host（預設 0.0.0.0）")
    parser.add_argument("--port",    default=8000, type=int,  help="監聽 port（預設 8000）")
    parser.add_argument("--reload",  action="store_true",     help="開發模式（auto-reload）")
    parser.add_argument("--db",      default=None,            help="SQLite 路徑（CADHLLM_DB）")
    parser.add_argument("--drive",   default=None,            help="Drive root（CADHLLM_DRIVE_ROOT）")
    parser.add_argument("--adapter", default=None,            help="LoRA adapter 路徑（CADHLLM_ADAPTER_PATH）")
    args = parser.parse_args()

    # 環境變數設定（優先於預設值）
    if args.db:
        os.environ["CADHLLM_DB"] = os.path.abspath(args.db)
    if args.drive:
        os.environ["CADHLLM_DRIVE_ROOT"] = os.path.abspath(args.drive)
    if args.adapter:
        os.environ["CADHLLM_ADAPTER_PATH"] = os.path.abspath(args.adapter)

    try:
        import uvicorn
    except ImportError:
        print("[FAIL] uvicorn not installed: pip install uvicorn[standard]", file=sys.stderr)
        sys.exit(1)

    _logger = logging.getLogger(__name__)
    _db = os.environ.get("CADHLLM_DB", "/tmp/cadhllm_jobs.db")
    if _db == "/tmp/cadhllm_jobs.db":
        _logger.info("CADHLLM_DB not set, using default: %s", _db)
    _drive = os.environ.get("CADHLLM_DRIVE_ROOT", "/content/drive/MyDrive/CADHLLM")
    if _drive == "/content/drive/MyDrive/CADHLLM":
        _logger.info("CADHLLM_DRIVE_ROOT not set, using default: %s", _drive)
    _adapter = os.environ.get("CADHLLM_ADAPTER_PATH", "/data/cadhllm/saved_model")
    if _adapter == "/data/cadhllm/saved_model":
        _logger.info("CADHLLM_ADAPTER_PATH not set, using default: %s", _adapter)

    print(f"[START] CADHLLM Gateway http://{args.host}:{args.port}")
    print(f"   DB:      {_db}")
    print(f"   Drive:   {_drive}")
    print(f"   Adapter: {_adapter}")
    print(f"   UI:      http://localhost:{args.port}/")
    print(f"   Docs:    http://localhost:{args.port}/docs")

    uvicorn.run(
        "services.gateway.main:app",
        host    = args.host,
        port    = args.port,
        reload  = args.reload,
        log_level = "info",
    )


if __name__ == "__main__":
    main()
