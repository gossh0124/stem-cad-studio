"""test_eagle_parse.py — EAGLE .brd 解析器（anchor→中心）測試。

驗證 VS-PCB exporter 的座標來源：parse_brd 必須正確算出元件本體中心，
特別是對稱封裝 center==anchor、連接器封裝 center≠anchor 的 anchor→中心換算。
"""
import math
import os

import pytest

from lib.pcb.eagle_parse import (
    parse_brd, _parse_rot, _apply_transform, BrdElement,
)

_BRD = os.path.join(
    os.path.dirname(__file__), "..",
    "data", "pcb_sources", "arduino_uno_r3", "eagle_official", "UNO-TH_Rev3e.brd")


@pytest.fixture(scope="module")
def elems():
    return parse_brd(_BRD)


# ── 旋轉字串解析 ─────────────────────────────────────────────
class TestParseRot:
    def test_none_empty(self):
        assert _parse_rot(None) == (0, False)
        assert _parse_rot("") == (0, False)

    def test_plain_angles(self):
        assert _parse_rot("R0") == (0, False)
        assert _parse_rot("R90") == (90, False)
        assert _parse_rot("R180") == (180, False)
        assert _parse_rot("R270") == (270, False)

    def test_mirror(self):
        assert _parse_rot("MR0") == (0, True)
        assert _parse_rot("MR90") == (90, True)


# ── 局部點變換 ───────────────────────────────────────────────
class TestApplyTransform:
    def test_identity(self):
        x, y = _apply_transform(3.0, 4.0, 0, False)
        assert x == pytest.approx(3.0)
        assert y == pytest.approx(4.0)

    def test_rot90(self):
        x, y = _apply_transform(1.0, 0.0, 90, False)
        assert x == pytest.approx(0.0, abs=1e-9)
        assert y == pytest.approx(1.0)

    def test_rot180(self):
        x, y = _apply_transform(2.0, 3.0, 180, False)
        assert x == pytest.approx(-2.0)
        assert y == pytest.approx(-3.0)

    def test_mirror_negates_x(self):
        x, y = _apply_transform(2.0, 3.0, 0, True)
        assert x == pytest.approx(-2.0)
        assert y == pytest.approx(3.0)


# ── 整檔解析 ─────────────────────────────────────────────────
class TestParseBrd:
    def test_returns_many_elements(self, elems):
        assert len(elems) > 100  # UNO-TH 有上百個 element

    def test_all_are_brd_element(self, elems):
        assert all(isinstance(e, BrdElement) for e in elems.values())

    def test_atmega328p_center_equals_anchor(self, elems):
        """DIL28-3 銀漆對稱於原點 → 中心 == anchor（CLAUDE.md 已驗證錨點）。"""
        zu4 = elems["ZU4"]
        assert zu4.package == "DIL28-3"
        assert zu4.rotation == "R180"
        assert zu4.anchor_x == pytest.approx(46.355)
        assert zu4.anchor_y == pytest.approx(16.383)
        assert zu4.center_x == pytest.approx(46.355, abs=0.01)
        assert zu4.center_y == pytest.approx(16.383, abs=0.01)

    def test_symmetric_caps_center_equals_anchor(self, elems):
        for name, ax, ay in [("PC1", 25.527, 9.144), ("PC2", 18.415, 9.144)]:
            e = elems[name]
            assert e.package == "PANASONIC_D"
            assert e.center_x == pytest.approx(ax, abs=0.01)
            assert e.center_y == pytest.approx(ay, abs=0.01)

    def test_usb_b_center_offset_from_anchor(self, elems):
        """USB-B(PN61729) 連接器本體中心 ≠ element 原點（anchor→中心換算非平凡）。"""
        x2 = elems["X2"]
        assert x2.package == "PN61729"
        # 本體中心明顯偏離 anchor（連接器突出板緣方向）
        assert abs(x2.center_x - x2.anchor_x) > 1.0

    def test_body_dims_from_silkscreen(self, elems):
        """本體尺寸由 package 輪廓量得且為正。"""
        zu4 = elems["ZU4"]
        assert zu4.body_l > 0 and zu4.body_w > 0
        assert zu4.body_source in ("layer21", "layer51", "pads")

    def test_missing_element_returns_none(self, elems):
        assert elems.get("DOES_NOT_EXIST") is None
