"""scripts/_verify_inference_schema.py — v2 LoRA-B Plan schema 驗證。

對 LoRA-B Plan 階段輸出（PlanJSON）抽樣檢查每元件 layout entry 是否帶
v2 enclosure_relation 欄位，且值在 5 enum 內（internal / breadboard / panel /
external / embedded）。

來源優先順序（CLI 旗標互斥）：
  --jsonl PATH      讀 OpenAI messages 訓練格式（plan 階段 assistant content）
  --plan-file PATH  讀單一 plan JSON
  --plan-dir DIR    讀目錄下所有 *.json 當 plan
預設：讀 training/data/cadhllm_lora_b_ch3_dryrun.jsonl（最近一份 dry-run 資料）

訓練完 LoRA-B 後實機驗收，把推理輸出寫成 plan JSON 或加進 jsonl，跑：
  .venv/Scripts/python.exe scripts/_verify_inference_schema.py --jsonl PATH --samples 10
exit code：全 PASS 回 0，有 FAIL 回 1。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JSONL = ROOT / "training" / "data" / "cadhllm_lora_b_ch3_dryrun.jsonl"
ENCLOSURE_ENUM = {"internal", "breadboard", "panel", "external", "embedded"}


def _iter_plan_jsonl(path: Path) -> Iterator[tuple[str, dict]]:
    """從 OpenAI messages JSONL 抽 plan 階段 assistant content。"""
    for ln, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msgs = obj.get("messages") or []
        user = next((m for m in msgs if m.get("role") == "user"), {})
        if "<|im_start|>plan" not in (user.get("content") or ""):
            continue
        asst = next((m for m in msgs if m.get("role") == "assistant"), None)
        if not asst:
            continue
        try:
            plan = json.loads(asst["content"])
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        yield (f"{path.name}:L{ln}", plan)


def _iter_plan_files(paths: Iterable[Path]) -> Iterator[tuple[str, dict]]:
    for p in paths:
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # 容錯：plan 物件本身 / 包了 bridge.plan / phase4.plan
        plan = obj if isinstance(obj.get("elements"), list) else (
            obj.get("plan") or obj.get("phase4", {}).get("plan") or {}
        )
        if isinstance(plan, dict) and plan.get("elements"):
            yield (str(p.relative_to(ROOT)), plan)


def _check_plan(src: str, plan: dict) -> tuple[int, int, list[str]]:
    """回傳 (pass_count, fail_count, fail_lines)。"""
    elements = plan.get("elements") or []
    if not isinstance(elements, list):
        return (0, 0, [f"  - {src}: elements 不是 list（{type(elements).__name__}）"])
    passes = fails = 0
    fail_lines: list[str] = []
    for el in elements:
        cid = el.get("id") or el.get("component_type") or "?"
        rel = el.get("enclosure_relation")
        if rel is None:
            fails += 1
            fail_lines.append(f"  - {src}: {cid} 缺 enclosure_relation")
        elif rel not in ENCLOSURE_ENUM:
            fails += 1
            fail_lines.append(f"  - {src}: {cid} enclosure_relation={rel!r} 不在 5 enum")
        else:
            passes += 1
    return (passes, fails, fail_lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--jsonl", type=Path, help="OpenAI messages 訓練格式")
    g.add_argument("--plan-file", type=Path, help="單一 plan JSON")
    g.add_argument("--plan-dir", type=Path, help="目錄下所有 *.json")
    ap.add_argument("--samples", type=int, default=0,
                    help="只取前 N 個 plan（0 = 全部）")
    args = ap.parse_args()

    if args.jsonl:
        plans = _iter_plan_jsonl(args.jsonl)
    elif args.plan_file:
        plans = _iter_plan_files([args.plan_file])
    elif args.plan_dir:
        plans = _iter_plan_files(sorted(args.plan_dir.glob("*.json")))
    else:
        if not DEFAULT_JSONL.exists():
            print(f"[verify_schema] 預設來源不存在：{DEFAULT_JSONL}", file=sys.stderr)
            print(f"[verify_schema] 用 --jsonl / --plan-file / --plan-dir 指定", file=sys.stderr)
            return 2
        plans = _iter_plan_jsonl(DEFAULT_JSONL)

    total_pass = total_fail = plan_count = 0
    all_fail_lines: list[str] = []
    for src, plan in plans:
        plan_count += 1
        if args.samples and plan_count > args.samples:
            plan_count -= 1
            break
        p, f, lines = _check_plan(src, plan)
        total_pass += p
        total_fail += f
        all_fail_lines.extend(lines)

    print(f"[VERIFY SCHEMA] checked {plan_count} plans, "
          f"{total_pass + total_fail} total components")
    print(f"PASS: {total_pass} components valid")
    print(f"FAIL: {total_fail} components missing/invalid")
    for line in all_fail_lines[:50]:
        print(line)
    if len(all_fail_lines) > 50:
        print(f"  ... 還有 {len(all_fail_lines) - 50} 行未顯示")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
