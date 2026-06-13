#!/usr/bin/env python3
"""no_silent_fallback_lint — 禁「必填資料的靜默頂替」。

動機（見 .ai/_fallback_retrospective.md 根因）：CLAUDE.md 的「禁容錯/用真實資料」一直停在
散文，沒有任何自動化在 commit/編輯時強制。本 lint 把該鐵則編譯成 gate：偵測必填欄位被
`.get(key, <literal>)` / `?? <literal>` / `|| <literal>` 頂替——缺值應 raise 或從 SSOT 衍生，
不可塞魔術預設讓使用者看到假內容。

偵測：
  Python（AST，高精度）：`X.get("<required_field>", <非 None 字面>)`。
  JS/JSX（regex，針對本次確認的頂替形）：色 hex `|| '#rgb'`、RGB 陣列 `|| [n,n,..`、
    nullish 數字 `?? <num>`、nullish 字面 `?? '...'`、物件頂替 `|| {`、幾何三元 `? x : <2+位數>`。

豁免：同行加註 `# nofallback-ok: <理由>`（py）或 `// nofallback-ok: <理由>`（js）。無理由的裸豁免本身視為缺漏。

三模式：
  (default)  掃 scan_globs，列出所有未豁免頂替（informational, exit 0）
  --hook     PostToolUse hook：只查剛寫入的單檔，fail-open，印 systemMessage 提示
  --strict   CI 模式：任何未豁免頂替 → exit 1

設定：config/fallback_required_fields.json（required_fields / scan_globs / exempt_marker）。
stdin（--hook）：{ "tool_name": "Edit"|"Write"|"MultiEdit", "tool_input": {"file_path": "..."} }
Log：.ai/no_silent_fallback_lint.log（hook 模式 append）
"""
from __future__ import annotations

import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / ".ai" / "no_silent_fallback_lint.log"
CONFIG = REPO / "config" / "fallback_required_fields.json"
RELEVANT_TOOLS = {"Edit", "Write", "MultiEdit"}
EXCLUDE_DIRS = {".venv", ".claude", ".git", "node_modules", "__pycache__",
                "saved_model", "output", "shells", ".swarm", ".claude-flow",
                ".pytest_cache", "dist", "build"}

_DEFAULTS = {
    "required_fields": [
        "inner_length", "inner_width", "inner_height",
        "length_mm", "width_mm", "height_mm",
        "pitch_mm", "x_mm", "y_mm", "cx", "cy",
    ],
    "scan_globs": ["services/**/*.py", "scripts/**/*.py", "v6/**/*.js", "v6/**/*.jsx"],
    "exempt_marker": "nofallback-ok",
}

# JS 頂替形：(kind, compiled regex)。僅針對本次確認的形，避免裸 `||` 噪音。
_JS_PATTERNS = [
    ("color-hex", re.compile(r"\|\|\s*['\"]#[0-9a-fA-F]{3,8}['\"]")),
    ("rgb-array", re.compile(r"\|\|\s*\[\s*-?[\d.]+\s*,\s*-?[\d.]+")),
    ("nullish-num", re.compile(r"\?\?\s*-?\d+(?:\.\d+)?\b")),
    ("nullish-str", re.compile(r"\?\?\s*['\"][^'\"]+['\"]")),
    ("object-fallback", re.compile(r"\|\|\s*\{")),
    ("ternary-geom", re.compile(r"\?\s*[\w.\[\]]{1,30}\s*:\s*-?\d{2,}\b")),
]


class ConfigError(Exception):
    """設定檔存在但無法解析——strict 模式不可靜默退回 _DEFAULTS。"""


def _load_config(strict: bool = False) -> dict:
    cfg = dict(_DEFAULTS)
    if not CONFIG.exists():
        # 刻意缺檔 → 用內建 _DEFAULTS（合法情境)。
        return cfg
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # 檔存在卻讀不到/壞掉:strict 必須失敗(否則靜默縮小保護集);
        # 非 strict 仍退回 defaults 但留下 log。
        if strict:
            raise ConfigError(f"{CONFIG} 無法解析: {type(e).__name__}: {e}") from e
        _log(f"CONFIG-FALLBACK {CONFIG} unreadable ({type(e).__name__}: {e}); using _DEFAULTS")
        return cfg
    for k in ("required_fields", "scan_globs", "exempt_marker"):
        if k in data:
            cfg[k] = data[k]
    return cfg


def _log(msg: str) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")
    except OSError:
        pass


def _is_literal_nonnull(node: ast.AST) -> bool:
    """字面預設且非 None（None 是合法的『缺值回 None 待檢查』，不算頂替）。"""
    if isinstance(node, ast.Constant):
        return node.value is not None
    if isinstance(node, (ast.List, ast.Tuple, ast.Dict)):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return isinstance(node.operand, ast.Constant)
    return False


def _default_repr(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<literal>"


def _check_py(path: Path, required: set[str], marker: str) -> list[tuple[int, str]]:
    """回傳 [(lineno, detail)]。"""
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        # 無法讀取必須分析的檔 → 不可當作「乾淨通過」（fail-closed）。
        return [(0, f"unreadable ({type(e).__name__}): {e}")]
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        # 無法解析 → 無法保證沒有頂替，視為缺漏而非靜默放行。
        return [(e.lineno or 0, f"unparseable (SyntaxError): {e.msg}")]
    lines = src.splitlines()
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "get" and len(node.args) == 2):
            continue
        key, default = node.args
        if not (isinstance(key, ast.Constant) and isinstance(key.value, str)):
            continue
        if key.value not in required:
            continue
        if not _is_literal_nonnull(default):
            continue
        ln = node.lineno
        line_txt = lines[ln - 1] if 0 < ln <= len(lines) else ""
        if _exempt_re(marker).search(line_txt):
            continue
        hits.append((ln, f".get(\"{key.value}\", {_default_repr(default)})"))
    return hits


_MARKER_RE_CACHE: dict[str, re.Pattern] = {}


def _exempt_re(marker: str) -> re.Pattern:
    """豁免必須是帶理由的真實註解：`# nofallback-ok: <理由>`（py）/
    `// nofallback-ok: <理由>` 或 `/* nofallback-ok: <理由> */`（js/jsx；JSX 行內
    只能用 `{/* … */}` 區塊形，不認此形會把善意註記靜默忽略 — 本 lint 的 meta 違例）。
    裸出現在字串/URL/變數名中的 marker 不算豁免（無理由的裸豁免本身視為缺漏）。"""
    rx = _MARKER_RE_CACHE.get(marker)
    if rx is None:
        rx = re.compile(r"(?:#|//|\{?/\*)\s*" + re.escape(marker) + r"\s*:\s*\S+")
        _MARKER_RE_CACHE[marker] = rx
    return rx


def _check_js(path: Path, marker: str) -> list[tuple[int, str]]:
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        # 無法讀取必須分析的檔 → fail-closed,視為缺漏。
        return [(0, f"unreadable ({type(e).__name__}): {e}")]
    exempt = _exempt_re(marker)
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(src.splitlines(), start=1):
        if exempt.search(line):
            continue
        for kind, rx in _JS_PATTERNS:
            m = rx.search(line)
            if m:
                hits.append((i, f"{kind}: {m.group(0).strip()}"))
    return hits


def _check_file(path: Path, required: set[str], marker: str) -> list[tuple[int, str]]:
    if path.suffix == ".py":
        return _check_py(path, required, marker)
    if path.suffix in (".js", ".jsx"):
        return _check_js(path, marker)
    return []


def _scan(cfg: dict) -> list[tuple[Path, int, str]]:
    required = set(cfg["required_fields"])
    marker = cfg["exempt_marker"]
    out: list[tuple[Path, int, str]] = []
    seen: set[Path] = set()
    for pattern in cfg["scan_globs"]:
        for p in REPO.glob(pattern):
            if p in seen or any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            seen.add(p)
            for ln, detail in _check_file(p, required, marker):
                out.append((p, ln, detail))
    out.sort(key=lambda t: (t[0].as_posix(), t[1]))
    return out


def _mode_default() -> int:
    cfg = _load_config()
    hits = _scan(cfg)
    if not hits:
        print("[no_silent_fallback] PASS — 掃描範圍內無未豁免的必填欄位頂替")
        return 0
    print(f"[no_silent_fallback] {len(hits)} 個未豁免頂替（缺值應 raise/derive，非塞預設）：")
    for p, ln, detail in hits:
        print(f"  {p.relative_to(REPO).as_posix()}:{ln}  {detail}")
    print("  → 修法：缺必填即 raise / 從 SSOT 衍生；合法 optional 請加註 `nofallback-ok: <理由>`")
    return 0


def _mode_strict() -> int:
    try:
        cfg = _load_config(strict=True)
    except ConfigError as e:
        print(f"[no_silent_fallback][strict] FAIL — 設定載入失敗: {e}")
        return 1
    hits = _scan(cfg)
    if not hits:
        print("[no_silent_fallback][strict] PASS")
        return 0
    print(f"[no_silent_fallback][strict] FAIL — {len(hits)} 個未豁免頂替：")
    for p, ln, detail in hits:
        print(f"  {p.relative_to(REPO).as_posix()}:{ln}  {detail}")
    return 1


def _mode_hook() -> int:
    for stream_name, enc in (("stdin", "utf-8-sig"), ("stdout", "utf-8")):
        try:
            getattr(sys, stream_name).reconfigure(encoding=enc, errors="replace")
        except (AttributeError, OSError):
            pass
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") not in RELEVANT_TOOLS:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    p = Path(file_path)
    if not p.is_absolute():
        p = REPO / p
    try:
        p = p.resolve()
    except OSError:
        return 0
    if not p.exists() or p.suffix not in (".py", ".js", ".jsx"):
        return 0
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return 0
    cfg = _load_config()
    hits = _check_file(p, set(cfg["required_fields"]), cfg["exempt_marker"])
    if not hits:
        return 0
    try:
        rel = p.relative_to(REPO).as_posix()
    except ValueError:
        rel = p.as_posix()
    detail = "; ".join(f"L{ln} {d}" for ln, d in hits[:5])
    _log(f"HIT {rel}: {detail}")
    msg = (f"[no_silent_fallback] {rel} 有 {len(hits)} 處必填欄位頂替（{detail}）。"
           "缺值應 raise 或從 SSOT 衍生，勿塞魔術預設；合法 optional 請加註 `nofallback-ok: <理由>`。")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg,
        }
    }, ensure_ascii=False))
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--hook" in args:
        return _mode_hook()
    if "--strict" in args:
        return _mode_strict()
    return _mode_default()


if __name__ == "__main__":
    sys.exit(main())
