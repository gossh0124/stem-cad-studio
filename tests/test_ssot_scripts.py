"""test_ssot_scripts.py — SSOT migration script 單元測試（SSOT5）

覆蓋：
- upgrade_3d_hints_body_h.infer_body_h: HEIGHT_RULES 各 rule 匹配 + LED-SMD shape guard（SSOT2 修）
- connect_frontend_shape._norm: label normalization tolerance

source script 純函式以 fixture dict 餵入，無檔案 I/O 依賴。
"""
from __future__ import annotations
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.upgrade_3d_hints_body_h import infer_body_h  # noqa: E402
from scripts.connect_frontend_shape import _norm  # noqa: E402


# ── HEIGHT_RULES：rule matching ───────────────────────────────────────────────

@pytest.mark.parametrize("sub,on_board,expected_h,rule_kw", [
    # (sub, on_board_entry, expected body_h_mm, rule_id substring)
    ({"label": "Power LED", "shape": "led-smd"}, None, 1.0, "led-smd"),
    ({"label": "Power LED"}, {"shape": "led-tht", "type": "indicator", "w_mm": 5.0}, 5.0, "led-tht"),
    ({"label": "5mm Red LED"}, {"shape": "led-tht", "type": "indicator", "w_mm": 5.0}, 5.0, "led-tht"),
    ({"label": "GND Resistor"}, None, 0.5, "res-smd"),
    ({"label": "0.1uF Ceramic"}, None, 1.0, "cap-ceramic"),
    ({"label": "10uF Electrolytic"}, None, 12.0, "electrolytic"),
    ({"label": "MAIN Header"}, None, 2.54, "header-male"),
    ({"label": "Mount Hole"}, None, 0.1, "mounting"),
    ({"label": "Copper Trace"}, None, 0.05, "copper"),
    ({"label": "Antenna"}, None, 0.05, "copper"),
    ({"label": "Buzzer 12mm"}, None, 9.0, "buzzer"),
    ({"label": "SG90 Servo"}, None, 22.7, "motor-servo"),
    ({"label": "ATMEGA328P"}, None, 4.0, "ic-dip"),
    ({"label": "LM393 IC"}, None, 1.75, "ic-soic"),
    ({"label": "USB-C Socket"}, None, 3.5, "usb-c"),
    ({"label": "Reset Btn"}, None, 4.3, "button-tact"),
    ({"label": "Sensitivity Trimpot"}, None, 4.5, "pot-trim"),
])
def test_height_rule_matches(sub, on_board, expected_h, rule_kw):
    result = infer_body_h(sub, on_board)
    assert result is not None, f"no rule matched for {sub}"
    h, reason = result
    assert h == expected_h, f"expected {expected_h}, got {h} ({reason})"
    assert rule_kw in reason, f"expected rule '{rule_kw}' in reason '{reason}'"


def test_led_smd_guard_rejects_led_tht_shape():
    """SSOT2 修復：shape='led-tht' 的子件不可掉到 SMD rule（即使缺 w_mm）。"""
    sub = {"label": "Status LED", "shape": "led-tht"}
    on_board = {"shape": "led-tht", "type": "indicator"}  # 缺 w_mm
    result = infer_body_h(sub, on_board)
    assert result is not None
    h, reason = result
    # 在新 guard 下，led-smd rule 的 lambda 因 shape=='led-tht' 被否決；
    # led-tht rule 要 w_mm>=4 也不滿足；應走到後續 rule 或 None。
    # 關鍵斷言：不可被誤判為 1.0mm SMD。
    assert h != 1.0 or "led-smd" not in reason, f"shape=led-tht 被誤判為 SMD: h={h}, reason={reason}"


def test_no_rule_returns_none():
    """無 label 也無匹配 keyword 時回 None。"""
    result = infer_body_h({"label": "Mystery Component XYZ"}, None)
    assert result is None


def test_on_board_label_merged():
    """on_board_components 的 type/shape 應被合併到推斷（sub 的 label 為主）。"""
    sub = {"label": "U1"}  # label 本身無線索
    on_board = {"label": "U1", "shape": "ic-soic"}
    result = infer_body_h(sub, on_board)
    assert result is not None
    h, _ = result
    assert h == 1.75  # 走 ic-soic rule


# ── connect_frontend_shape._norm: normalization tolerance ─────────────────────

@pytest.mark.parametrize("a,b", [
    ("MAIN Header", "main-header"),
    ("Power_LED", "powerled"),
    ("USB-C Socket", "usbcsocket"),
    ("Copper  Trace", "coppertrace"),  # multiple spaces
    ("A/B/C", "abc"),
])
def test_norm_tolerates_separators_and_case(a, b):
    assert _norm(a) == _norm(b)


def test_norm_keeps_alphanumeric():
    assert _norm("LM393") == "lm393"
    assert _norm("ATMEGA328P-PU") == "atmega328ppu"


def test_norm_distinguishes_different_strings():
    assert _norm("Power") != _norm("Ground")
