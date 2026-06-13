"""build_rag_index.py — 建構 RAG 向量索引。

用法：
  .venv/Scripts/python.exe tools/build_rag_index.py             # 建元件索引
  .venv/Scripts/python.exe tools/build_rag_index.py --all        # 建全部索引（含合成案例 + canned）
  .venv/Scripts/python.exe tools/build_rag_index.py --force      # 強制重建
  .venv/Scripts/python.exe tools/build_rag_index.py --synthetic N # 灌入 N 筆合成案例
  .venv/Scripts/python.exe tools/build_rag_index.py --canned      # 灌入 v6/canned/ 精校案例
  .venv/Scripts/python.exe tools/build_rag_index.py --from-state # 從 state/ 目錄灌入歷史案例
  .venv/Scripts/python.exe tools/build_rag_index.py --status     # 顯示索引狀態
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/builders/ → repo root (3 levels)
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PROJECT_ROOT / "lib"))
sys.path.insert(0, str(_PROJECT_ROOT / "training"))


def _build_components(force: bool):
    from lib.rag import build_component_index
    print("[1/3] 建構元件索引...")
    t0 = time.time()
    build_component_index(force=force)
    print(f"      完成 ({time.time() - t0:.1f}s)")


class RagIngestError(RuntimeError):
    """灌入過程中有記錄失敗時拋出，避免「部分/空索引」被當成成功建置。"""


# 累計各灌入階段的失敗筆數；main() 在結尾檢查，任一筆失敗即以非零退出，
# 避免「部分/空索引」被自動化/CI 誤判為成功建置。
_INGEST_FAILURES: list[tuple[str, int]] = []


def _record_failures(stage: str, failures: int) -> None:
    if failures:
        _INGEST_FAILURES.append((stage, failures))


def _build_canned_cases() -> int:
    """遍歷 v6/canned/*.json，將精校 bridge dict 灌入 cases collection。

    - 跳過 _index.json
    - 每個 canned 檔案已是完整 bridge dict（含 project_name, _instruction,
      cot_plan.high_level_plan, components[{role,type,...}]）
    - case_id 格式：canned_{stem}（例如 canned_auto_waterer）
    - 回傳灌入筆數

    注意：此函式不執行實際 DB 寫入時，請在環境無 LanceDB 時用 --dry-run 模式。
    """
    from lib.rag import add_case

    canned_dir = _PROJECT_ROOT / "v6" / "canned"
    if not canned_dir.exists():
        print("[canned] v6/canned/ 目錄不存在，跳過")
        return 0

    print("[canned] 掃描 v6/canned/ 精校案例...")
    count = 0
    failures = 0
    for fp in sorted(canned_dir.glob("*.json")):
        if fp.name == "_index.json":
            continue
        try:
            bridge = json.loads(fp.read_text(encoding="utf-8"))
            pname = bridge.get("project_name", fp.stem)
            comps = bridge.get("components", [])
            add_case(bridge, case_id=f"canned_{fp.stem}")
            print(f"  [canned] {pname} ({len(comps)} comps)")
            count += 1
        except Exception as e:
            failures += 1
            print(f"  [WARN] {fp.name}: {e}")

    print(f"[canned] 完成 {count} 筆")
    _record_failures("canned", failures)
    return count


def _build_synthetic_cases(n: int):
    """從訓練資料生成器產出合成案例並灌入 RAG。"""
    from lib.rag import add_case
    from data_generator import DataGenerator

    print(f"[2/3] 灌入 {n} 筆合成案例...")
    gen = DataGenerator()
    t0 = time.time()
    count = 0
    failures = 0
    for i in range(n):
        try:
            sample = gen._build_sample(i)
            completion_text = sample["completion"]
            if completion_text.endswith("<|eot_id|>"):
                completion_text = completion_text[: -len("<|eot_id|>")]
            bridge = json.loads(completion_text)
            bridge["_instruction"] = sample["prompt"]
            add_case(bridge, case_id=f"synthetic_{i:04d}")
            count += 1
        except Exception as e:
            failures += 1
            print(f"      [WARN] case {i} failed: {e}")
    print(f"      完成 {count}/{n} 筆 ({time.time() - t0:.1f}s)")
    _record_failures("synthetic", failures)


def _build_synthetic_assembly(n: int):
    """從 LoRA-B 資料生成器產出合成組裝決策並灌入 RAG。"""
    from lib.rag import add_assembly
    from data_generator_b import DataGeneratorB, WEIGHT_G, THERMAL_MW

    print(f"[3/3] Seeding {n} synthetic assembly decisions...")
    gen = DataGeneratorB()
    t0 = time.time()
    samples = gen.generate_synthetic_data(n)
    count = 0
    failures = 0
    for i, sample in enumerate(samples):
        try:
            completion_text = sample["completion"]
            if completion_text.endswith("<|eot_id|>"):
                completion_text = completion_text[: -len("<|eot_id|>")]
            plan = json.loads(completion_text)
            fake_bridge = {
                "project_name": f"synthetic_asm_{i:04d}",
                "project_category": sample.get("_category", "Education"),
                "components": [
                    {
                        "type": c.get("component", ""),
                        "spec": {
                            "weight_g": WEIGHT_G.get(c.get("component", ""), 10.0),
                            "thermal_mw": THERMAL_MW.get(c.get("component", ""), 0.0),
                        },
                    }
                    for c in plan.get("layout", [])
                ],
            }
            add_assembly(plan, fake_bridge, assembly_id=f"synthetic_asm_{i:04d}")
            count += 1
        except Exception as e:
            failures += 1
            print(f"      [WARN] assembly {i} failed: {e}")
    print(f"      Done {count}/{n} ({time.time() - t0:.1f}s)")
    _record_failures("synthetic_asm", failures)


def _ingest_from_state():
    """從 state/ 目錄灌入歷史成功案例。"""
    from lib.rag import add_case, add_assembly

    state_dir = Path(_PROJECT_ROOT / "data" / "state")
    if not state_dir.exists():
        drive_root = Path(
            os.environ.get("CADHLLM_DRIVE_ROOT", "")
        )
        state_dir = drive_root / "state" if drive_root.exists() else None

    if not state_dir or not state_dir.exists():
        print("[state] state/ 目錄不存在，跳過")
        return

    print(f"[state] 從 {state_dir} 灌入歷史案例...")
    count = 0
    failures = 0
    for fp in state_dir.glob("*.json"):
        try:
            bridge = json.loads(fp.read_text(encoding="utf-8"))
            if not bridge.get("components"):
                continue
            add_case(bridge, case_id=fp.stem)
            if bridge.get("cad_output", {}).get("assembly_rationale"):
                plan = {
                    "placement_rationale": bridge["cad_output"].get(
                        "assembly_rationale", ""
                    ),
                    "layout": [],
                    "thermal": bridge["cad_output"].get("thermal_field", {}),
                    "joints": bridge["cad_output"].get("joints", {}),
                }
                add_assembly(plan, bridge, assembly_id=f"hist_{fp.stem}")
            count += 1
        except Exception as e:
            failures += 1
            print(f"  [WARN] {fp.name}: {e}")
    print(f"      灌入 {count} 筆歷史案例")
    _record_failures("state", failures)


def _show_status():
    from lib.rag import get_status
    status = get_status()
    print("=== RAG 系統狀態 ===")
    print(f"DB 路徑:      {status['db_path']}")
    print(f"Embed model:  {status['embed_model']}")
    print(f"Embed loaded: {status['embed_loaded']}")
    for name, count in status.get("collections", {}).items():
        print(f"  {name}: {count} 筆")
    if status.get("error"):
        print(f"  [ERROR] {status['error']}")


def main():
    parser = argparse.ArgumentParser(description="建構 CADHLLM RAG 向量索引")
    parser.add_argument("--force", action="store_true", help="強制重建索引")
    parser.add_argument("--all", action="store_true", help="建全部索引（含合成案例）")
    parser.add_argument(
        "--synthetic", type=int, default=0,
        help="灌入 N 筆合成 Phase I 案例"
    )
    parser.add_argument(
        "--synthetic-asm", type=int, default=0,
        help="灌入 N 筆合成 Phase IV 組裝決策"
    )
    parser.add_argument(
        "--canned", action="store_true",
        help="灌入 v6/canned/ 精校案例（16 筆）"
    )
    parser.add_argument(
        "--from-state", action="store_true",
        help="從 state/ 目錄灌入歷史案例"
    )
    parser.add_argument("--status", action="store_true", help="顯示索引狀態")
    args = parser.parse_args()

    if args.status:
        _show_status()
        return

    # Ensure DB dimension compatibility before any writes
    from lib.rag.rag_embedding import check_db_dimension_compat
    check_db_dimension_compat()

    _build_components(force=args.force)

    if args.all:
        _build_synthetic_cases(200)
        _build_synthetic_assembly(50)
        _build_canned_cases()

    if args.synthetic > 0:
        _build_synthetic_cases(args.synthetic)

    if args.synthetic_asm > 0:
        _build_synthetic_assembly(args.synthetic_asm)

    if args.canned:
        _build_canned_cases()

    if args.from_state:
        _ingest_from_state()

    _show_status()

    # 任一筆灌入失敗即視為建置失敗：避免部分/空索引被自動化誤判為成功。
    if _INGEST_FAILURES:
        detail = ", ".join(f"{stage}={n}" for stage, n in _INGEST_FAILURES)
        total = sum(n for _, n in _INGEST_FAILURES)
        raise RagIngestError(
            f"RAG 灌入有 {total} 筆失敗 ({detail})；索引可能不完整，"
            f"請檢視上方 [WARN] 訊息後重建。"
        )


if __name__ == "__main__":
    main()
