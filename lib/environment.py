"""environment.py — 共用環境安裝函式，供 TRAIN 和 PIPELINE 共用。"""
import importlib
import importlib.metadata
import logging
import os
import subprocess
import sys

_log = logging.getLogger(__name__)


def _print_core_versions(pkgs: list) -> None:
    print("\n[info] 核心套件版本：")
    for pkg in pkgs:
        try:
            print(f"  {pkg}: {importlib.metadata.version(pkg)}")
        except importlib.metadata.PackageNotFoundError:
            print(f"  {pkg}: 未安裝")


def setup_environment(mode: str = "pipeline") -> None:
    """安裝環境套件。

    Args:
        mode: "train"（完整訓練棧）或 "pipeline"（推論棧）
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError) as exc:
        print(f"[environment] reconfigure failed: {exc}", file=sys.stderr, flush=True)

    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

    print("[1/3] 清理衝突套件...")
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y",
         "torchao", "unsloth", "trl", "transformers", "bitsandbytes", "xformers"],
        capture_output=True, encoding="utf-8", errors="replace",
    )

    print("[2/3] 安裝 bitsandbytes==0.45.5...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps",
         "--no-cache-dir", "bitsandbytes==0.45.5"],
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    )

    if mode == "train":
        _install_train()
    else:
        _install_pipeline()

    _reload_modules()
    print("\n[ok] 環境安裝完成。")


def _install_train() -> None:
    print("[3/3] 安裝完整訓練棧...")
    core = [
        "unsloth==2026.2.1", "transformers==4.57.6",
        "trl==0.24.0", "peft==0.18.1",
    ]
    other = [
        "datasets", "accelerate", "psutil", "jsonschema",
        "json-repair", "rich", "pillow<12", "torchvision",
        "hf-transfer", "build123d", "unsloth_zoo",
    ]
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir",
             "--no-deps"] + core,
            check=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + other,
            check=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        print("[ok] 訓練棧安裝完成。")
    except subprocess.CalledProcessError as e:
        print(f"[error] 安裝失敗：{e.stderr[-500:]}")
        raise

    _print_core_versions(["unsloth", "transformers", "trl", "peft", "bitsandbytes"])


def _install_pipeline() -> None:
    print("[3/3] 安裝推論棧（無訓練套件）...")
    pkgs = [
        "unsloth==2026.2.1", "transformers==4.57.6",
        "peft==0.18.1", "jsonschema", "json-repair",
        "rich", "pillow<12", "build123d",
    ]
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + pkgs,
            check=True, capture_output=True, encoding="utf-8", errors="replace",
        )
        print("[ok] 推論棧安裝完成。")
    except subprocess.CalledProcessError as e:
        print(f"[error] 安裝失敗：{e.stderr[-500:]}")
        raise

    _print_core_versions(["unsloth", "transformers", "peft", "bitsandbytes"])


def _reload_modules() -> None:
    print("\n[...] 強制重新載入模組...")
    try:
        importlib.invalidate_caches()
        targets = ["unsloth", "trl", "peft", "transformers", "bitsandbytes"]
        for mod in list(sys.modules.keys()):
            if any(mod.startswith(t) for t in targets):
                sys.modules.pop(mod, None)
        import unsloth  # noqa: F401
        print("[ok] 模組重新載入成功。")
    except (ImportError, ModuleNotFoundError) as e:
        _log.warning("模組重新載入失敗: %s", e)
        print(f"[warn] 重新載入失敗（{e}），若遇 ImportError 請手動 Restart Runtime。")