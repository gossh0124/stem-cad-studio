"""scripts/builders/prompt_alignment_check.py — 防止 train/inference prompt drift。

兩種檢查：
  1. **HARDCODE scan**: lib/ + services/ 內若出現 system_msg literal
     字串(如「你是 Phase X」「Plan 階段」)且非從 training.prompts 來，
     視為 drift 風險 → warn / fail。

  2. **byte-level**: 跑 training.prompts.SYS_PLAN / build_*_user_prompt
     對比 training/data/cadhllm_lora_b_ch3.jsonl 第一筆 → 必須完全相等。

用法：
  .venv/Scripts/python.exe scripts/builders/prompt_alignment_check.py            # 報 issues
  .venv/Scripts/python.exe scripts/builders/prompt_alignment_check.py --strict   # CI 用,有 issues 即 exit 1

Hook 整合：建議掛 PostToolUse on Edit/Write 編 lib/adapter_manager.py
或 training/prompts.py 時自動跑(advisory)。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# scan 目錄與排除
SCAN_DIRS = [ROOT / "lib", ROOT / "services"]
EXCLUDE_FILES = {
    ROOT / "lib" / "adapter_manager.py",   # 已用 SSOT
    ROOT / "lib" / "registry.py",           # enum 定義註解，不是 prompt
    ROOT / "lib" / "assembly_solver.py",    # 程式邏輯註解
}
EXCLUDE_PATTERNS = ["test_", "/tests/", "/__pycache__/"]

# 視為 system_msg literal 的 fingerprint 關鍵字
SUSPECT_PATTERNS = [
    r"你是\s*Phase\s+IV.*階段",  # 「你是 Phase IV ... 階段」
    r"PlanJSON.*高層決策",
    r"ParamsJSON.*低層幾何",
    r"你是\s*Phase\s+I\s+STEAM\s*專案規劃師",  # 舊 Phase I prompt（已遷至 SSOT）
]


def scan_hardcoded_prompts() -> list[tuple[Path, int, str]]:
    """Scan lib/ + services/ 內疑似 hardcoded system_msg literal。"""
    issues: list[tuple[Path, int, str]] = []
    pattern_re = re.compile("|".join(SUSPECT_PATTERNS))
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.py"):
            if p in EXCLUDE_FILES:
                continue
            if any(ex in str(p) for ex in EXCLUDE_PATTERNS):
                continue
            try:
                lines = p.read_text(encoding="utf-8").splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines, 1):
                if pattern_re.search(ln):
                    issues.append((p.relative_to(ROOT), i, ln.strip()[:120]))
    return issues


def check_byte_level_alignment() -> list[str]:
    """跑 builders 對比 jsonl 第一筆 byte-level。"""
    errors: list[str] = []
    try:
        from training.prompts import SYS_PLAN, SYS_PARAMS
    except ImportError as e:
        errors.append(f"training.prompts import fail: {e}")
        return errors

    jsonl_path = ROOT / "training" / "data" / "cadhllm_lora_b_ch3.jsonl"
    if not jsonl_path.exists():
        errors.append(f"訓練 jsonl 不存在: {jsonl_path} — 跳過 byte-level check")
        return errors

    with open(jsonl_path, encoding="utf-8") as f:
        first_plan = None
        first_params = None
        for ln in f:
            obj = json.loads(ln)
            u = next((m for m in obj["messages"] if m["role"] == "user"), {})
            s = next((m for m in obj["messages"] if m["role"] == "system"), {})
            if "<|im_start|>plan" in u.get("content", "") and first_plan is None:
                first_plan = s.get("content", "")
            elif "<|im_start|>params" in u.get("content", "") and first_params is None:
                first_params = s.get("content", "")
            if first_plan and first_params:
                break

    # 若掃完整份 jsonl 仍找不到 plan / params 樣本（marker rename、格式漂移、
    # 內容被改名/重構），代表這個 gate 想攔的 drift 已發生 → 必須 hard fail，
    # 不可因為「沒比對到東西」而靜默回傳空 errors（always-green-gate）。
    if first_plan is None:
        errors.append(
            f"jsonl 中找不到任何 plan 樣本（marker '<|im_start|>plan' 未命中）: {jsonl_path}"
            " — 可能 marker rename / 格式漂移，byte-level check 無法執行"
        )
    if first_params is None:
        errors.append(
            f"jsonl 中找不到任何 params 樣本（marker '<|im_start|>params' 未命中）: {jsonl_path}"
            " — 可能 marker rename / 格式漂移，byte-level check 無法執行"
        )

    if first_plan and SYS_PLAN != first_plan:
        # 找出差異位置
        diff = next((i for i, (a, b) in enumerate(zip(SYS_PLAN, first_plan)) if a != b), -1)
        errors.append(
            f"SYS_PLAN != jsonl plan system_msg (first diff at char {diff})\n"
            f"  SSOT[{max(0,diff-20)}:{diff+20}]: {SYS_PLAN[max(0,diff-20):diff+20]!r}\n"
            f"  jsonl[{max(0,diff-20)}:{diff+20}]: {first_plan[max(0,diff-20):diff+20]!r}"
        )
    if first_params and SYS_PARAMS != first_params:
        diff = next((i for i, (a, b) in enumerate(zip(SYS_PARAMS, first_params)) if a != b), -1)
        errors.append(
            f"SYS_PARAMS != jsonl params system_msg (first diff at char {diff})\n"
            f"  SSOT[{max(0,diff-20)}:{diff+20}]: {SYS_PARAMS[max(0,diff-20):diff+20]!r}\n"
            f"  jsonl[{max(0,diff-20)}:{diff+20}]: {first_params[max(0,diff-20):diff+20]!r}"
        )

    return errors


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError) as exc:
        print(f"[prompt_alignment_check] reconfigure failed: {exc}", file=sys.stderr, flush=True)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="任一 issue 即 exit 1（CI 用）")
    args = ap.parse_args()

    print("[prompt_alignment] 1/2 scan hardcoded prompts in lib/ + services/...")
    scan_issues = scan_hardcoded_prompts()
    if scan_issues:
        print(f"  WARN: {len(scan_issues)} 處疑似 hardcoded prompt:")
        for path, ln, content in scan_issues:
            print(f"    {path}:{ln} {content}")
    else:
        print("  OK: 沒找到 hardcoded system_msg literal")

    print("\n[prompt_alignment] 2/2 byte-level: training.prompts vs jsonl 第一筆...")
    align_errors = check_byte_level_alignment()
    if align_errors:
        print(f"  FAIL: {len(align_errors)} 處不對齊:")
        for err in align_errors:
            print(f"    {err}")
    else:
        print("  OK: SYS_PLAN / SYS_PARAMS 與 jsonl byte-level identical")

    n_issues = len(scan_issues) + len(align_errors)
    print(f"\n[prompt_alignment] Total {n_issues} issues "
          f"({len(scan_issues)} scan warn + {len(align_errors)} byte-level fail)")
    if args.strict and n_issues > 0:
        return 1
    if len(align_errors) > 0:
        # byte-level 不對齊永遠是 hard fail（不管 strict）
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
