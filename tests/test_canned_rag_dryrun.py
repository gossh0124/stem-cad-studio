"""test_canned_rag_dryrun.py — 驗證 v6/canned/ 精校案例可被 _build_canned_cases 解析。

dry-run 模式：只解析 JSON，不寫入 data/rag_db。

驗收條件：
  1. 解析到剛好 16 個 canned 檔案（跳過 _index.json）
  2. 每個 bridge 都含必要欄位：project_name, _instruction,
     cot_plan.high_level_plan, components（非空 list）
  3. 印出「將灌入」摘要
"""
from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANNED_DIR = PROJECT_ROOT / "v6" / "canned"

_REQUIRED_TOP = {"project_name", "_instruction", "cot_plan", "components"}


def _parse_canned_files():
    """解析全部 canned JSON，回傳 (橋接 dict 清單, 跳過檔案清單)。"""
    results = []
    skipped = []
    for fp in sorted(CANNED_DIR.glob("*.json")):
        if fp.name == "_index.json":
            skipped.append(fp.name)
            continue
        bridge = json.loads(fp.read_text(encoding="utf-8"))
        results.append((fp.stem, bridge))
    return results, skipped


def test_canned_count_and_fields():
    """assert 16 筆、每筆必要欄位齊全、components 非空。"""
    assert CANNED_DIR.exists(), f"v6/canned/ 目錄不存在: {CANNED_DIR}"

    parsed, skipped = _parse_canned_files()

    print(f"\n=== Canned RAG Dry-Run ===")
    print(f"跳過: {skipped}")
    print(f"解析到 {len(parsed)} 個 canned 檔案：")

    errors = []
    for stem, bridge in parsed:
        pname = bridge.get("project_name", "")
        comps = bridge.get("components", [])
        plan = bridge.get("cot_plan", {}).get("high_level_plan", "")
        instr = bridge.get("_instruction", "")

        missing = _REQUIRED_TOP - bridge.keys()

        line = (
            f"  將灌入: canned_{stem} | {pname} "
            f"({len(comps)} comps) | instr={instr[:30]!r}"
        )
        print(line)

        if missing:
            errors.append(f"{stem}: 缺少欄位 {missing}")
        if not comps:
            errors.append(f"{stem}: components 為空")
        if not plan:
            errors.append(f"{stem}: cot_plan.high_level_plan 為空")
        if not instr:
            errors.append(f"{stem}: _instruction 為空")

    print(f"\n合計將灌入: {len(parsed)} 筆")

    if errors:
        for e in errors:
            print(f"  [ERROR] {e}")

    assert len(parsed) == 16, (
        f"預期 16 個 canned 案例，實際解析到 {len(parsed)} 個。"
        f"（目錄內容: {[fp.name for fp in sorted(CANNED_DIR.glob('*.json'))]}）"
    )
    assert not errors, f"欄位驗證失敗：\n" + "\n".join(errors)

    print("\n[OK] 全部 16 筆 canned 案例欄位驗證通過，未寫入 data/rag_db。")


if __name__ == "__main__":
    test_canned_count_and_fields()
