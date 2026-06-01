"""tests/test_complement_engine.py — complement_engine 確定性單元測試。

monkeypatch lib.rag.search_cases（注入 fake），不依賴 live DB。
所有斷言均為數學可計算的確定性條件，符合專案「反假成功」規則。
"""
from __future__ import annotations

import sys
import os
import types
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ════════════════════════════════════════════════════════════════
# Fake cases（5 筆造假資料）
# ════════════════════════════════════════════════════════════════

FAKE_CASES = [
    {
        "case_id": "case_001",
        "project_name": "智慧植栽監測A",
        "project_category": "IoT",
        "components": [
            {"role": "Brain",   "type": "Brain-Arduino-class"},
            {"role": "Power",   "type": "Power-Battery-class"},
            {"role": "Control", "type": "Control-Button-class"},
            {"role": "Output",  "type": "Buzzer-Active-class"},
            {"role": "Output",  "type": "Lighting-NeoPixel-class"},  # 預期被建議
            {"role": "Output",  "type": "Display-OLED-class"},       # 預期被建議
        ],
        "score": 0.1,
    },
    {
        "case_id": "case_002",
        "project_name": "智慧植栽監測B",
        "project_category": "IoT",
        "components": [
            {"role": "Brain",   "type": "Brain-Arduino-class"},
            {"role": "Power",   "type": "Power-Battery-class"},
            {"role": "Control", "type": "Control-Button-class"},
            {"role": "Output",  "type": "Lighting-NeoPixel-class"},  # 預期被建議
            {"role": "Output",  "type": "Display-OLED-class"},       # 預期被建議
        ],
        "score": 0.12,
    },
    {
        "case_id": "case_003",
        "project_name": "智慧植栽監測C",
        "project_category": "IoT",
        "components": [
            {"role": "Brain",   "type": "Brain-Arduino-class"},
            {"role": "Power",   "type": "Power-Battery-class"},
            {"role": "Control", "type": "Control-Button-class"},
            {"role": "Output",  "type": "Lighting-NeoPixel-class"},  # 預期被建議
            {"role": "Sensor",  "type": "Sensor-Soil-class"},        # 偶爾出現
        ],
        "score": 0.15,
    },
    {
        "case_id": "case_004",
        "project_name": "智慧植栽監測D",
        "project_category": "IoT",
        "components": [
            {"role": "Brain",   "type": "Brain-Arduino-class"},
            {"role": "Power",   "type": "Power-Battery-class"},
            {"role": "Control", "type": "Control-Button-class"},
            {"role": "Output",  "type": "Display-OLED-class"},       # 預期被建議
        ],
        "score": 0.2,
    },
    {
        "case_id": "case_005",
        "project_name": "智慧植栽監測E",
        "project_category": "IoT",
        "components": [
            {"role": "Brain",   "type": "Brain-Arduino-class"},
            {"role": "Power",   "type": "Power-Battery-class"},
            {"role": "Control", "type": "Control-Button-class"},
            {"role": "Output",  "type": "Lighting-NeoPixel-class"},  # 預期被建議
        ],
        "score": 0.22,
    },
]

# 預期頻率（5 筆）：
# Lighting-NeoPixel-class: 4/5 = 0.8
# Display-OLED-class:      3/5 = 0.6
# Sensor-Soil-class:       1/5 = 0.2
# Brain / Power / Control type → 應排除


# ════════════════════════════════════════════════════════════════
# 測試 bridge（目前已有：Brain + Power + Control + Buzzer-Active）
# ════════════════════════════════════════════════════════════════

CURRENT_BRIDGE = {
    "project_name": "我的植栽機",
    "project_category": "IoT",
    "components": [
        {"role": "Brain",   "type": "Brain-Arduino-class"},
        {"role": "Power",   "type": "Power-Battery-class"},
        {"role": "Control", "type": "Control-Button-class"},
        {"role": "Output",  "type": "Buzzer-Active-class"},
    ],
}

CURRENT_TYPES = {c["type"] for c in CURRENT_BRIDGE["components"]}


# ════════════════════════════════════════════════════════════════
# Fixture：注入 fake lib.rag，強制 complement_engine 重新載入
# ════════════════════════════════════════════════════════════════

def _make_fake_rag(fake_cases):
    """建立 fake lib.rag module 並注入 sys.modules，以 importlib 直接載入模組檔案
    （繞過 services/__init__.py 的完整 import 鏈）。"""
    import importlib.util

    def _fake_search_cases(
        query: str,
        top_k: int = 3,
        category_filter: Optional[str] = None,
    ):
        return fake_cases[:top_k]

    lib_mod = types.ModuleType("lib")
    rag_mod = types.ModuleType("lib.rag")
    rag_mod.search_cases = _fake_search_cases
    lib_mod.rag = rag_mod

    sys.modules["lib"] = lib_mod
    sys.modules["lib.rag"] = rag_mod

    # 清除舊的快取（確保重載時使用新的 lib.rag）
    for key in list(sys.modules.keys()):
        if "complement_engine" in key:
            del sys.modules[key]

    # 直接以檔案路徑載入，不觸發 services/__init__.py
    module_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "services", "pipeline", "complement_engine.py",
    )
    spec = importlib.util.spec_from_file_location(
        "services.pipeline.complement_engine", module_path
    )
    ce_mod = importlib.util.module_from_spec(spec)
    sys.modules["services.pipeline.complement_engine"] = ce_mod
    spec.loader.exec_module(ce_mod)
    return ce_mod


@pytest.fixture()
def ce_full():
    """注入 5 筆 fake cases 的引擎實例。"""
    return _make_fake_rag(FAKE_CASES)


@pytest.fixture()
def ce_empty():
    """注入 0 筆 fake cases 的引擎實例。"""
    return _make_fake_rag([])


# ════════════════════════════════════════════════════════════════
# 共用：執行主查詢，供多個 test 複用
# ════════════════════════════════════════════════════════════════

@pytest.fixture()
def results_full(ce_full):
    return ce_full.suggest_complements(CURRENT_BRIDGE, top_k_cases=5, max_suggestions=3)


# ════════════════════════════════════════════════════════════════
# 測試案例
# ════════════════════════════════════════════════════════════════

def test_T1_no_overlap_with_current_types(results_full):
    """T1: 回傳不含 current_types（差集正確）。"""
    returned_types = {r["type"] for r in results_full}
    overlap = returned_types & CURRENT_TYPES
    assert len(overlap) == 0, f"FAIL T1: overlap={overlap}"
    print(f"PASS T1: 不含 current_types，overlap={overlap}")


def test_T2_no_brain_power_control_roles(results_full):
    """T2: 回傳不含 Brain/Power/Control 角色元件。"""
    excluded_roles = {"Brain", "Power", "Control"}
    bad = [r for r in results_full if r["role"] in excluded_roles]
    assert len(bad) == 0, f"FAIL T2: bad={bad}"
    print(f"PASS T2: 不含 Brain/Power/Control 角色")


def test_T3_frequency_in_range(results_full):
    """T3: 所有 frequency 在 [0, 1]。"""
    bad = [r for r in results_full if not (0.0 <= r["frequency"] <= 1.0)]
    assert len(bad) == 0, f"FAIL T3: bad={bad}"
    print(f"PASS T3: 所有 frequency 在 [0, 1]")


def test_T4_sorted_desc_by_frequency(results_full):
    """T4: frequency 由高到低排序。"""
    freqs = [r["frequency"] for r in results_full]
    assert freqs == sorted(freqs, reverse=True), f"FAIL T4: freqs={freqs}"
    print(f"PASS T4: 已由高到低排序 freqs={freqs}")


def test_T5a_neopixel_in_results(results_full):
    """T5a: Lighting-NeoPixel-class 在建議中。"""
    returned_types = [r["type"] for r in results_full]
    assert "Lighting-NeoPixel-class" in returned_types, (
        f"FAIL T5a: returned_types={returned_types}"
    )
    print("PASS T5a: Lighting-NeoPixel-class 在建議中")


def test_T5b_oled_in_results(results_full):
    """T5b: Display-OLED-class 在建議中。"""
    returned_types = [r["type"] for r in results_full]
    assert "Display-OLED-class" in returned_types, (
        f"FAIL T5b: returned_types={returned_types}"
    )
    print("PASS T5b: Display-OLED-class 在建議中")


def test_T6_buzzer_excluded(results_full):
    """T6: Buzzer-Active-class（已在 bridge）不被建議。"""
    returned_types = [r["type"] for r in results_full]
    assert "Buzzer-Active-class" not in returned_types, (
        f"FAIL T6: returned_types={returned_types}"
    )
    print("PASS T6: Buzzer-Active-class 已被差集排除")


def test_T7_neopixel_frequency(results_full):
    """T7: NeoPixel frequency == 0.8（4/5）。"""
    hits = [r for r in results_full if r["type"] == "Lighting-NeoPixel-class"]
    assert hits, "FAIL T7: NeoPixel 不在結果中"
    expected = round(4 / 5, 4)
    assert hits[0]["frequency"] == expected, (
        f"FAIL T7: actual={hits[0]['frequency']}, expected={expected}"
    )
    print(f"PASS T7: NeoPixel frequency={hits[0]['frequency']}")


def test_T8_oled_frequency(results_full):
    """T8: OLED frequency == 0.6（3/5）。"""
    hits = [r for r in results_full if r["type"] == "Display-OLED-class"]
    assert hits, "FAIL T8: OLED 不在結果中"
    expected = round(3 / 5, 4)
    assert hits[0]["frequency"] == expected, (
        f"FAIL T8: actual={hits[0]['frequency']}, expected={expected}"
    )
    print(f"PASS T8: OLED frequency={hits[0]['frequency']}")


def test_T9_neopixel_before_oled(results_full):
    """T9: NeoPixel 排在 OLED 之前（頻率 0.8 > 0.6）。"""
    returned_types = [r["type"] for r in results_full]
    assert "Lighting-NeoPixel-class" in returned_types, "FAIL T9: NeoPixel 不在結果中"
    assert "Display-OLED-class" in returned_types, "FAIL T9: OLED 不在結果中"
    np_idx = returned_types.index("Lighting-NeoPixel-class")
    oled_idx = returned_types.index("Display-OLED-class")
    assert np_idx < oled_idx, (
        f"FAIL T9: np_idx={np_idx} oled_idx={oled_idx}"
    )
    print(f"PASS T9: NeoPixel(idx={np_idx}) < OLED(idx={oled_idx})")


def test_T10_seen_in_is_list(results_full):
    """T10: 所有 seen_in 是 list。"""
    bad = [r for r in results_full if not isinstance(r.get("seen_in"), list)]
    assert len(bad) == 0, f"FAIL T10: bad={bad}"
    print("PASS T10: 所有 seen_in 是 list")


def test_T11_empty_cases_returns_empty(ce_empty):
    """T11: 0 筆 cases 時回傳 []。"""
    result = ce_empty.suggest_complements(CURRENT_BRIDGE, top_k_cases=5)
    assert result == [], f"FAIL T11: actual={result}"
    print("PASS T11: 0 筆 cases → []")


def test_T12_max_suggestions_limit(ce_full):
    """T12: max_suggestions=1 時最多回傳 1 筆。"""
    result = ce_full.suggest_complements(CURRENT_BRIDGE, top_k_cases=5, max_suggestions=1)
    assert len(result) <= 1, f"FAIL T12: len={len(result)}"
    print(f"PASS T12: max_suggestions=1 回傳 {len(result)} 筆")


# ════════════════════════════════════════════════════════════════
# 直接執行模式（保留給命令列驗收）
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    all_pass = True
    ce = _make_fake_rag(FAKE_CASES)
    results = ce.suggest_complements(CURRENT_BRIDGE, top_k_cases=5, max_suggestions=3)

    print("\n" + "=" * 60)
    print("complement_engine 單元測試")
    print("=" * 60)
    print(f"\n[回傳結果] {len(results)} 筆：")
    for i, r in enumerate(results, 1):
        print(f"  [{i}] type={r['type']}  role={r['role']}  "
              f"frequency={r['frequency']}  seen_in={r['seen_in']}")
    print()

    tests = [
        (test_T1_no_overlap_with_current_types, results),
        (test_T2_no_brain_power_control_roles, results),
        (test_T3_frequency_in_range, results),
        (test_T4_sorted_desc_by_frequency, results),
        (test_T5a_neopixel_in_results, results),
        (test_T5b_oled_in_results, results),
        (test_T6_buzzer_excluded, results),
        (test_T7_neopixel_frequency, results),
        (test_T8_oled_frequency, results),
        (test_T9_neopixel_before_oled, results),
        (test_T10_seen_in_is_list, results),
    ]
    for fn, arg in tests:
        try:
            fn(arg)
        except AssertionError as e:
            print(str(e))
            all_pass = False
        except Exception:
            traceback.print_exc()
            all_pass = False

    # T11 / T12 需要不同 fixture
    ce_e = _make_fake_rag([])
    try:
        test_T11_empty_cases_returns_empty(ce_e)
    except AssertionError as e:
        print(str(e)); all_pass = False

    try:
        test_T12_max_suggestions_limit(ce)
    except AssertionError as e:
        print(str(e)); all_pass = False

    print("\n" + "=" * 60)
    print("全部 PASS" if all_pass else "有 FAIL，請檢查上方輸出")
    print("=" * 60)
    sys.exit(0 if all_pass else 1)
