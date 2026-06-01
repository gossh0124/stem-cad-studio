"""test_rag_cases_dedup.py — search_cases 去重邏輯單元測試。

使用 MOCK 紀錄（不依賴 live DB），直接測試 _dedup_by_project_name。

驗收條件：
  1. 回傳結果中 project_name 無重複（set 大小 == list 長度）
  2. 同一 project_name 保留 _distance 最小者
  3. 回傳數量不超過 top_k
  4. 去重前後 score 欄位正確對應
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.rag.rag_cases import _dedup_by_project_name


# ───────────────────────────── helpers ──────────────────────────────

def _make_row(case_id: str, project_name: str, distance: float) -> dict:
    """建立模擬 LanceDB 搜尋結果列。"""
    return {
        "case_id": case_id,
        "project_name": project_name,
        "project_category": "Test",
        "components_json": "[]",
        "_distance": distance,
    }


# ───────────────────────────── tests ────────────────────────────────

def test_dedup_removes_duplicate_project_names():
    """同 project_name 出現兩次時，去重後只剩一筆，且保留最佳分數。

    模擬場景：auto_waterer 的 synthetic 與 canned 版本都出現在 top 結果中。
    """
    rows = [
        _make_row("synthetic_0001",  "auto_waterer_demo", 0.15),   # 第二佳
        _make_row("canned_auto_waterer", "auto_waterer_demo", 0.08),  # 最佳 ← 應保留
        _make_row("canned_plant_monitor", "plant_monitor_demo", 0.20),
        _make_row("canned_alarm_siren",   "alarm_siren_demo",   0.25),
    ]

    result = _dedup_by_project_name(rows, top_k=3)

    project_names = [r["project_name"] for r in result]
    print(f"\n去重後 project_names: {project_names}")
    print(f"保留的 case_ids: {[r['case_id'] for r in result]}")

    # 主驗收：無重複 project_name
    assert len(set(project_names)) == len(result), (
        f"回傳含重複 project_name: {project_names}"
    )

    # 保留最佳分數那筆（_distance 最小）
    auto_waterer_row = next(r for r in result if r["project_name"] == "auto_waterer_demo")
    assert auto_waterer_row["case_id"] == "canned_auto_waterer", (
        f"應保留 _distance=0.08 的 canned_auto_waterer，"
        f"實際保留: {auto_waterer_row['case_id']}"
    )

    # top_k 限制
    assert len(result) <= 3

    print("[OK] 去重正確，保留最佳分數，top_k 正確。")


def test_dedup_no_duplicate_in_all_unique():
    """所有 project_name 都不重複時，去重前後結果相同。"""
    rows = [
        _make_row("case_a", "proj_alpha",   0.10),
        _make_row("case_b", "proj_beta",    0.20),
        _make_row("case_c", "proj_gamma",   0.30),
        _make_row("case_d", "proj_delta",   0.40),
    ]

    result = _dedup_by_project_name(rows, top_k=3)
    project_names = [r["project_name"] for r in result]

    assert len(set(project_names)) == len(result)
    assert len(result) == 3  # top_k 裁截

    print(f"\n[OK] 無重複情況：回傳 {len(result)} 筆，project_names 唯一。")


def test_dedup_topk_respected():
    """即使去重後仍超過 top_k，仍正確裁截。"""
    rows = [
        _make_row(f"case_{i}", f"proj_{i}", float(i) * 0.05)
        for i in range(10)
    ]

    result = _dedup_by_project_name(rows, top_k=4)
    assert len(result) == 4

    project_names = [r["project_name"] for r in result]
    assert len(set(project_names)) == len(result)

    # 確認是分數最佳的前 4 筆（_distance 最小）
    scores = [r["_distance"] for r in result]
    assert scores == sorted(scores), f"結果未依 _distance 升冪排列: {scores}"

    print(f"\n[OK] top_k=4 裁截正確，_distance 升冪: {scores}")


def test_dedup_multiple_duplicates_same_project():
    """同一 project_name 出現 4 次，只保留 _distance 最小那筆。"""
    rows = [
        _make_row("v1", "duplicated_proj", 0.50),
        _make_row("v2", "duplicated_proj", 0.12),   # 最佳 ← 應保留
        _make_row("v3", "duplicated_proj", 0.30),
        _make_row("v4", "duplicated_proj", 0.45),
        _make_row("c1", "other_proj", 0.25),
    ]

    result = _dedup_by_project_name(rows, top_k=5)
    project_names = [r["project_name"] for r in result]

    assert len(set(project_names)) == len(result), (
        f"仍有重複: {project_names}"
    )

    dup_row = next(r for r in result if r["project_name"] == "duplicated_proj")
    assert dup_row["case_id"] == "v2", (
        f"應保留 _distance=0.12 的 v2，實際: {dup_row['case_id']}"
    )

    print(f"\n[OK] 4 次重複僅保留最佳: {dup_row['case_id']} (_distance={dup_row['_distance']})")


if __name__ == "__main__":
    test_dedup_removes_duplicate_project_names()
    test_dedup_no_duplicate_in_all_unique()
    test_dedup_topk_respected()
    test_dedup_multiple_duplicates_same_project()
    print("\n=== 全部去重單元測試通過 ===")
