"""Wiring 涵蓋 drift gate.

根治 Sensor-IR/Remote 式漏接（元件存在於 verified.json SSOT 且被 canned demo 使用，
卻沒被加進 wiring 引擎的手維護映射表 COMP_PIN_NEEDS/_TAXONOMY_TO_SHORT → resolve_wiring
raise / 接線懸空 'D?'）。見 memory feedback_wiring_tables_need_ssot_derive。

判準：每個出現在 v6/canned/*.json `components` 的元件，normalize_comp 後必須
  (a) 對應到 COMP_PIN_NEEDS 條目（會接 MCU 信號腳的外設），或
  (b) 在 NON_WIRED_ALLOWLIST（brain/電源/結構/繼電器控制，刻意不接 MCU 信號腳）。
否則視為「verified.json/canned 有、wiring 映射漏」的涵蓋缺口 → FAIL。
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_CANNED = _ROOT / "v6" / "canned"

from lib.wiring.engine import COMP_PIN_NEEDS, normalize_comp  # noqa: E402

# 刻意不接 MCU 信號腳的 class（normalize_comp 後的 short name）。
# 新增此清單前請確認該元件「真的」不需 MCU 信號接線（否則應補進 COMP_PIN_NEEDS）。
NON_WIRED_ALLOWLIST = {
    # Brain / MCU 本體 —— 是接線的主體，非外設
    "Arduino-Uno", "Arduino-Nano", "ESP32", "ESP8266", "RPi", "RaspberryPi", "Microbit",
    # 電源 —— 供電非信號
    "Battery-AA", "Battery-LiPo", "USB-5V", "AC-Adapter",
    # 結構件 —— 無電氣腳
    "Chassis-Car",
    # 繼電器/驅動間接控制 —— 無直接 MCU 信號腳（Pump 由 Relay 控制供電）
    "Pump",
}


def _canned_component_types() -> set[str]:
    types: set[str] = set()
    for f in glob.glob(str(_CANNED / "*.json")):
        if os.path.basename(f).startswith("_"):  # 跳過 _index.json 等
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(d, dict):
            continue
        for c in d.get("components", []):
            t = c.get("type") if isinstance(c, dict) else c
            if t:
                types.add(t)
    return types


class TestWiringCoverage:
    def test_canned_components_all_mapped_or_allowlisted(self):
        types = _canned_component_types()
        assert types, "未從 v6/canned 收到任何元件型別（路徑/結構變動？）"
        gaps = []
        for t in sorted(types):
            short = normalize_comp(t)
            if short in COMP_PIN_NEEDS:
                continue
            if short in NON_WIRED_ALLOWLIST:
                continue
            gaps.append(f"{t} -> {short}")
        assert not gaps, (
            "wiring 涵蓋缺口：以下 canned 元件既不在 COMP_PIN_NEEDS 也不在 "
            "NON_WIRED_ALLOWLIST（需補 wiring 映射或確認不接線後加 allowlist）：\n  "
            + "\n  ".join(gaps)
        )

    def test_allowlist_and_comp_pin_needs_disjoint(self):
        # 防呆：一個 short name 不應同時在兩邊（語意矛盾）
        overlap = set(NON_WIRED_ALLOWLIST) & set(COMP_PIN_NEEDS)
        assert not overlap, f"short name 同時在 allowlist 與 COMP_PIN_NEEDS：{overlap}"
