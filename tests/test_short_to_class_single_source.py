"""tests/test_short_to_class_single_source.py — P3.0：SHORT_TO_CLASS 單一真值 drift guard。

緣由:signal「short name → SSOT class」map 原有三份相同字面量副本
  (comp_class_map.SHORT_TO_CLASS / validate._SHORT_TO_CLASS / power_inject.SHORT_TO_CLASS),
  power_inject 程式內**自承 TODO**「If validate._SHORT_TO_CLASS gains new entries... this copy
  must be updated in sync」。單一源 comp_class_map 早已建立(其 docstring 言明供 wiring_data 與
  validate 共用),但 validate/power_inject 從未 migrate —— 重構做一半,留下漂移風險。

root cause:單一源已存在,但兩個消費端仍各自 inline 副本。修法:兩處改 `import ... from comp_class_map`。
本測試鎖「全部引用**同一物件**(identity)」,使三處副本再次漂移在結構上不可能(非僅值相等)。
"""
import json
from pathlib import Path

from lib.wiring import comp_class_map, validate, power_inject, wiring_data

_CANON = comp_class_map.SHORT_TO_CLASS


def test_validate_uses_single_source():
    assert validate._SHORT_TO_CLASS is _CANON, \
        "validate._SHORT_TO_CLASS 非 comp_class_map.SHORT_TO_CLASS(副本漂移風險)"


def test_power_inject_uses_single_source():
    assert power_inject.SHORT_TO_CLASS is _CANON, \
        "power_inject.SHORT_TO_CLASS 非 comp_class_map.SHORT_TO_CLASS(副本漂移風險)"


def test_wiring_data_uses_single_source():
    assert wiring_data._SHORT_TO_CLASS is _CANON, \
        "wiring_data._SHORT_TO_CLASS 非 comp_class_map.SHORT_TO_CLASS"


def test_map_nonempty_and_power_subset_disjoint():
    assert len(_CANON) >= 20, "SHORT_TO_CLASS 異常少(載入失準?)"
    # _POWER_SHORT_TO_CLASS 是刻意分離的電源域子集(BatteryAA/USB5V…),key 不應與 signal map 重疊。
    overlap = set(power_inject._POWER_SHORT_TO_CLASS) & set(_CANON)
    assert overlap == set(), f"電源子集與 signal map key 重疊(語意混淆): {overlap}"


def test_values_are_real_ssot_classes():
    """referential integrity:每個 class 值必在 SSOT(防單一源引用不存在的 class)。"""
    ssot = set(json.loads(
        (Path(__file__).resolve().parent.parent / "data"
         / "component_datasheet_verified.json").read_text(encoding="utf-8")).keys())
    missing = {k: v for k, v in _CANON.items() if v not in ssot}
    assert not missing, f"SHORT_TO_CLASS 值不在 SSOT: {missing}"


def test_power_short_to_class_values_are_real_ssot_classes():
    """B4 referential integrity:`_POWER_SHORT_TO_CLASS`(電源前端短名→class)每個值必在 SSOT。
    signal map 已有同等 gate(上),電源子集先前漏 —— 補,防電源短名映射 typo'd class 在
    `_resolve_power_class` 解析失敗 → runtime UnknownPowerSourceError(而非 commit 期被 gate 攔)。"""
    ssot = set(json.loads(
        (Path(__file__).resolve().parent.parent / "data"
         / "component_datasheet_verified.json").read_text(encoding="utf-8")).keys())
    missing = {k: v for k, v in power_inject._POWER_SHORT_TO_CLASS.items() if v not in ssot}
    assert not missing, f"_POWER_SHORT_TO_CLASS 值不在 SSOT: {missing}"
