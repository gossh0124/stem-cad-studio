"""tests/test_dims_frame_convention.py — P0.5：座標系(Y-handedness)慣例鎖。

緣由(問題 #8,經 3-lens 對抗式驗證確認):
  `derive_component_dimensions.py --check` 是**自參照** drift gate(只比 deriver 輸出 vs
  dims.js,兩者同源),對「系統性鏡像」結構性盲目——鏡像實際發生在**消費層**
  (scene-3d.js 翻 Y、port-resolver.js 通用元件不翻),自參照 gate 從不檢視該層。

本檔鎖住**與 #8 視覺修正無關**的 frame 慣例不變量(deriver / SSOT / 註解),讓座標系
從「隱含」變「明示且受測」,並擋掉孕育此問題的 stale 註解回歸。**刻意不**斷言 render
路徑的當前 handedness——「2D 通用不翻」是待修的 bug,鎖住它等於固化 bug(#8 修好後須反轉)。

已驗證事實(權威來源):
  - SSOT 原點 = PCB 左下角 / y-up：data/component_datasheet_verified.json _meta.coordinate_origin
    （並有 16 個 canned JSON 宣告 coordinate_system: y-up）。
  - deriver 保持不翻：cy = y_mm + h_mm/2（純位移，無 board_h - ... 反轉）。
  - component-dimensions.js 舊註解誤寫 "top-left corner" → 已更正為 bottom-left。
"""
import json
from pathlib import Path

import scripts.derive_component_dimensions as d

_REPO = Path(__file__).resolve().parent.parent
_SSOT = _REPO / "data" / "component_datasheet_verified.json"
_DIMS_JS = _REPO / "v6" / "data" / "component-dimensions.js"


def test_ssot_declares_bottom_left_origin():
    """SSOT _meta 必明文宣告 bottom-left 原點(消費層翻 Y 的依據)。"""
    meta = json.loads(_SSOT.read_text(encoding="utf-8")).get("_meta", {})
    origin = str(meta.get("coordinate_origin", "")).lower()
    assert "bottom-left" in origin, (
        f"SSOT _meta.coordinate_origin 未宣告 bottom-left: {origin!r}")


def test_deriver_preserves_bottom_left_no_flip():
    """deriver 須保持 bottom-left:cy = y_mm + h_mm/2,且**較大 y_mm → 較大 cy**。

    mutant 抵抗:Y-flip(cy = board_h - (y_mm + h_mm/2))會**反轉**此排序;
    此測試對該 mutant 必 fail,故座標系選擇是受測的 load-bearing 不變量,非隱含巧合。
    """
    spec = {
        "_ui_hints": {"frontend_shape": {
            "Low": {"shape": "box", "color": "#111111"},
            "High": {"shape": "box", "color": "#222222"},
        }},
        "on_board_components": [
            {"label": "Low", "x_mm": 0.0, "y_mm": 2.0, "w_mm": 4.0, "h_mm": 4.0},
            {"label": "High", "x_mm": 0.0, "y_mm": 30.0, "w_mm": 4.0, "h_mm": 4.0},
        ],
    }
    ports = {p["label"]: p for p in d.derive_ports("Synthetic", spec)}
    assert ports["Low"]["cy"] == 4.0    # 2 + 4/2，純位移無翻轉
    assert ports["High"]["cy"] == 32.0  # 30 + 4/2
    # 較大 y_mm → 較大 cy(bottom-left 保留);Y-flip mutant 會使此反轉 → fail。
    assert ports["High"]["cy"] > ports["Low"]["cy"]
    # cx 同樣為純位移(對稱保護,防有人只改一軸)。
    assert ports["Low"]["cx"] == 2.0    # 0 + 4/2


def test_dims_js_header_not_stale_topleft():
    """回歸鎖:component-dimensions.js 標頭不得再宣稱 'top-left'(孕育 #8 假設的 stale 源),
    且須宣告 bottom-left。防註解漂回誤導值。"""
    text = _DIMS_JS.read_text(encoding="utf-8")
    header = text[:600]  # 標頭區塊(cx/cy 慣例註解所在)
    assert "top-left corner" not in header, (
        "component-dimensions.js 標頭仍含 stale 'top-left corner'(與 SSOT bottom-left 矛盾)")
    assert "bottom-left" in header, (
        "component-dimensions.js 標頭未宣告 bottom-left 原點")
