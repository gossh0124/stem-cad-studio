#!/usr/bin/env python3
"""provenance_lint — DEC-H7：凍結並漸縮 load-bearing 路徑上的『無依據手填』。

動機：CLAUDE.md「禁手填、全資料須有依據」一直停在散文;`no_silent_fallback_lint` 只擋
`.get(k,default)` / `?? literal` 頂替形,擋不住「整張手填表」(如 comp-specs.js 的 COMP_PINS
手猜 pin 分數、port-resolver.js 的 COMP_RENDERERS 手刻 glyph)。本 lint 把 DEC-H7 編成 gate。

策略(誠實版,非「偵測任意手填」的不可判定問題):
  以 config/provenance_baseline.json **凍結已知手填 loci**,強制三條可計算不變量——
    (1) no-spread  : 已知手填 symbol 不得出現在 baseline 未宣告的檔(防擴散到新檔)。
    (2) no-growth  : 帶 max_entries 的 symbol(如 COMP_PINS),其區塊 entry 數不得超過上限(防新增手填)。
    (3) inventory  : 列出目前所有手填 loci + purge_plan(漸縮進度可見);locus 消失→提示更新 baseline。
  forward「新 SSOT 值須帶 provenance」屬 P4.4(source_page),不在本 v1。

模式:
  (default) 列出 inventory + 任何違規(informational, exit 0)
  --strict  CI 模式:任何 spread / growth → exit 1

設定:config/provenance_baseline.json(scan_globs / handfill_loci / estimate_wip)。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "config" / "provenance_baseline.json"
EXCLUDE_DIRS = {".venv", ".claude", ".git", "node_modules", "__pycache__",
                "output", "shells", "dist", "build", ".pytest_cache"}


class ConfigError(Exception):
    """baseline 設定缺失/壞掉——strict 不可靜默放行(否則保護集歸零=假綠)。"""


def _load_baseline() -> dict:
    if not CONFIG.exists():
        raise ConfigError(f"{CONFIG} 不存在")
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ConfigError(f"{CONFIG} 無法解析: {type(e).__name__}: {e}") from e


def _scan_files(globs: list[str]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for pattern in globs:
        for p in REPO.glob(pattern):
            if p in seen or any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            seen.add(p)
            out.append(p)
    return sorted(out)


def _rel(p: Path) -> str:
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def _extract_block(text: str, open_marker: str) -> str | None:
    """從 open_marker 的 '{' 起,以括號配對抓出整個物件區塊文字(含外層 {})。"""
    i = text.find(open_marker)
    if i < 0:
        return None
    brace = text.find("{", i)
    if brace < 0:
        return None
    depth, j = 0, brace
    while j < len(text):
        c = text[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[brace:j + 1]
        j += 1
    return None  # 未配對(壞檔)→ 視為無法抓取


def check(baseline: dict) -> list[str]:
    """回傳違規清單(空=PASS)。"""
    globs = baseline.get("scan_globs", ["v6/**/*.js", "v6/**/*.jsx"])
    files = _scan_files(globs)
    # 預讀檔內容(fail-closed:讀不到必須分析的檔 → 視為違規)
    contents: dict[Path, str | None] = {}
    for p in files:
        try:
            contents[p] = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            contents[p] = None
            return [f"[unreadable] {_rel(p)} 無法讀取({type(e).__name__}: {e})— fail-closed"]

    violations: list[str] = []
    for locus in baseline.get("handfill_loci", []):
        sym = locus["symbol"]
        allowed = {a for a in locus.get("allowed_files", [locus["file"]])}
        host = REPO / locus["file"]
        host_text = contents.get(host)

        # (3) inventory：locus 是否仍在宣告檔
        if host_text is None or locus.get("detect", sym) not in host_text:
            violations.append(
                f"[purged?] {locus['id']}: 在 {locus['file']} 找不到 `{locus.get('detect', sym)}`"
                f" → 若已 purge 請從 baseline 移除(漸縮);若搬移請更新 file。")

        # (1) no-spread：symbol 出現在未宣告的檔
        for p, txt in contents.items():
            if txt is None:
                continue
            if _rel(p) in allowed:
                continue
            if re.search(r"\b" + re.escape(sym) + r"\b", txt):
                violations.append(
                    f"[spread] {locus['id']}: `{sym}` 擴散到未宣告檔 {_rel(p)}"
                    f"(DEC-H7:手填不得蔓延;允許檔={sorted(allowed)})")

        # (2) no-growth：帶 max_entries 者,區塊 entry 數不得超過上限
        if "max_entries" in locus and host_text is not None:
            block = _extract_block(host_text, locus.get("block_open", locus.get("detect", sym)))
            if block is None:
                violations.append(
                    f"[growth?] {locus['id']}: 無法抓取 `{sym}` 區塊(括號未配對?)— 無法驗 entry 數")
            else:
                rx = re.compile(locus["entry_regex"], re.MULTILINE)
                n = len(rx.findall(block))
                if n > locus["max_entries"]:
                    violations.append(
                        f"[growth] {locus['id']}: `{sym}` entry 數 {n} > 上限 {locus['max_entries']}"
                        f"(新增手填違反 DEC-H7;應改 SSOT derivation)")
    return violations


def _print_inventory(baseline: dict) -> None:
    print("[provenance] 已知手填 loci(凍結+漸縮 baseline):")
    for locus in baseline.get("handfill_loci", []):
        print(f"  - {locus['id']:18} {locus['file']}  → {locus['purge_plan']}")
    for est in baseline.get("estimate_wip", []):
        print(f"  - {est['id']:18} [estimate-wip] {est.get('class','')}  → {est['purge_plan']}")


def main() -> int:
    strict = "--strict" in sys.argv
    try:
        baseline = _load_baseline()
    except ConfigError as e:
        print(f"[provenance]{'[strict]' if strict else ''} FAIL — baseline 載入失敗: {e}")
        return 1
    _print_inventory(baseline)
    violations = check(baseline)
    if not violations:
        print(f"[provenance]{'[strict]' if strict else ''} PASS — 無擴散/增長(手填已凍結)")
        return 0
    print(f"[provenance]{'[strict]' if strict else ''} {len(violations)} 個違規:")
    for v in violations:
        print("  " + v)
    return 1 if strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
