"""test_layout_export.py — lib/pcb → component-dimensions exporter 測試。

驗證 VS-PCB 根治：後端權威 SSOT → 前端視覺佈局格式自動衍生，
含漏畫補齊（Resonator/Cap-PC1/Cap-PC2）、位置取 .brd 真實中心、JS 文字輸出格式。
"""
import os

import pytest

from lib.pcb import ARDUINO_UNO_R3
from lib.pcb.layout_export import (
    ARDUINO_ELEMENT_MAP, ARDUINO_RENDER, ARDUINO_ORDER,
    arduino_brd_centers, export_arduino_ports,
    port_to_js, render_ports_js, _fmt_num,
    render_arduino_section, extract_arduino_section, _DIMS_JS,
    _ARDUINO_BRD,
)

# .brd 為 machine-local（data/pcb_sources gitignored，決策 B 2026-06-07）。檔不在時
# （fresh clone / CI）依賴 .brd 衍生的測試「大聲」skip 而非 error。
_brd_required = pytest.mark.skipif(
    not os.path.exists(_ARDUINO_BRD),
    reason=("UNO-TH_Rev3e.brd 不在（data/pcb_sources gitignored）。VS-PCB SSOT-derive "
            "鏈需 .brd；還原見「開放問題待辦索引」。"),
)

# 前端 renderer（shapes-ic-conn.js / shapes-passive-mech.js）已實作的 shape 鍵
_KNOWN_SHAPES = {
    "ic-dip", "ic-soic", "ic-qfp", "ic-module",
    "conn-usb-micro", "conn-usb-c", "conn-usb-b",
    "conn-header-male", "conn-header-female", "conn-screw-terminal",
    "conn-barrel-jack", "mounting-hole",
    "cap-electrolytic", "cap-ceramic", "res-smd", "pot-trimmer",
    "crystal-hc49", "button-tactile", "buzzer", "led-tht", "led-smd",
}


@pytest.fixture(scope="module")
def ports():
    if not os.path.exists(_ARDUINO_BRD):
        pytest.skip("UNO-TH_Rev3e.brd 不在（data/pcb_sources gitignored）")
    return export_arduino_ports(ARDUINO_UNO_R3)


# ── 映射表自身一致性 ─────────────────────────────────────────
class TestMappings:
    def test_element_map_covers_render(self):
        # 每個有視覺映射的元件都要有對應 .brd element
        for name in ARDUINO_RENDER:
            assert name in ARDUINO_ELEMENT_MAP

    def test_order_subset_of_render(self):
        for name in ARDUINO_ORDER:
            assert name in ARDUINO_RENDER

    def test_render_names_are_backend_subcomponents(self):
        be_names = {sc.name for sc in ARDUINO_UNO_R3.sub_components}
        for name in ARDUINO_RENDER:
            assert name in be_names, f"{name} 不在後端 sub_components"


# ── .brd 中心對映 ────────────────────────────────────────────
@_brd_required
class TestBrdCenters:
    def test_maps_all_render_components(self):
        centers = arduino_brd_centers()
        for name in ARDUINO_RENDER:
            assert name in centers, f"{name} 無 .brd 中心"

    def test_atmega328p_center(self):
        centers = arduino_brd_centers()
        zu4 = centers["ATmega328P"]
        assert zu4.center_x == pytest.approx(46.355, abs=0.01)
        assert zu4.center_y == pytest.approx(16.383, abs=0.01)


# ── ports 輸出 ───────────────────────────────────────────────
@_brd_required
class TestExportPorts:
    def test_count(self, ports):
        # 17 sub_component + 4 mounting holes（VS-PCB①：+LP2985-3V3 +ICSP-Main）
        assert len(ports) == 21

    def test_previously_missing_now_present(self, ports):
        labels = {p["label"] for p in ports}
        for lbl in ("Resonator", "Cap-PC1", "Cap-PC2", "LP2985-3V3", "ICSP"):
            assert lbl in labels, f"漏畫補齊失敗：{lbl}"

    def test_atmega_position_is_brd_center(self, ports):
        atm = next(p for p in ports if p["label"] == "ATmega328P")
        assert atm["cx"] == pytest.approx(46.35, abs=0.05)
        assert atm["cy"] == pytest.approx(16.38, abs=0.05)
        assert atm["shape"] == "ic-dip"

    def test_all_shapes_known(self, ports):
        for p in ports:
            assert p["shape"] in _KNOWN_SHAPES, f"未知 shape: {p['shape']}"

    def test_mounting_holes_from_backend(self, ports):
        mh = [p for p in ports if p["shape"] == "mounting-hole"]
        assert len(mh) == 4
        be = {(round(m.x, 2), round(m.y, 2)) for m in ARDUINO_UNO_R3.mounting_holes}
        fe = {(p["cx"], p["cy"]) for p in mh}
        assert fe == be

    def test_every_port_has_required_fields(self, ports):
        for p in ports:
            assert {"side", "cx", "cy", "shape", "label", "color", "params"} <= set(p)
            assert isinstance(p["params"], dict)

    def test_no_duplicate_labels(self, ports):
        labels = [p["label"] for p in ports]
        assert len(labels) == len(set(labels))

    def test_strict_raises_on_missing_center(self, monkeypatch):
        """無容錯：映射到不存在的 .brd element 時必須 raise，不得靜默退 anchor。"""
        import lib.pcb.layout_export as lx
        bad = dict(lx.ARDUINO_ELEMENT_MAP)
        bad["ATmega328P"] = "NONEXISTENT_ELEM"
        monkeypatch.setattr(lx, "ARDUINO_ELEMENT_MAP", bad)
        with pytest.raises(ValueError, match="ATmega328P"):
            lx.export_arduino_ports(ARDUINO_UNO_R3)


# ── JS 文字輸出 ──────────────────────────────────────────────
class TestJsRender:
    def test_fmt_num_strips_trailing_zeros(self):
        assert _fmt_num(1.0) == "1"
        assert _fmt_num(2.54) == "2.54"
        assert _fmt_num(7.62) == "7.62"
        assert _fmt_num(28) == "28"

    def test_port_to_js_shape(self, ports):
        js = port_to_js(ports[0])
        assert js.startswith("{ side:")
        assert js.endswith("}")
        assert "shape:" in js and "params:" in js

    def test_render_block_lines_match_count(self, ports):
        block = render_ports_js(ports)
        assert block.count("\n") == len(ports) - 1  # 逗號分行，無結尾逗號
        assert not block.rstrip().endswith(",")


# ── 前端檔案 drift 偵測（前端必須等於後端 SSOT 衍生，無容錯）─────────────
@_brd_required
class TestFrontendNoDrift:
    """component-dimensions.js 的 SSOT 段必須與 exporter 輸出逐字相符。

    抓兩種錯：① 有人手改 SSOT 段未重跑 exporter；② 改後端未同步前端。
    這是「前端衍生自後端」的可計算 gate，取代肉眼比對。
    """

    def test_ssot_section_matches_exporter(self):
        with open(_DIMS_JS, "r", encoding="utf-8") as f:
            js = f.read()
        actual = extract_arduino_section(js).strip()
        expected = render_arduino_section().strip()
        assert actual == expected, (
            "component-dimensions.js SSOT 段與 exporter 輸出不符 — "
            "重跑：.venv/Scripts/python.exe -m lib.pcb.layout_export --write")

    def test_markers_present(self):
        with open(_DIMS_JS, "r", encoding="utf-8") as f:
            js = f.read()
        assert "// >>> SSOT-AUTO-GENERATED" in js
        assert "// <<< SSOT-AUTO-GENERATED" in js
