"""tests/test_schematic_power_label.py — 原理圖電源標籤 no-silent-fallback 防禦。

problem #19:`generate_svg` 的 `_POWER_LABELS.get(power, "USB 5V")` 把**未知電源靜默標成
「USB 5V」**(與真正 USB-5V 標籤無法區分)。且因 schematic 與 wiring power 詞彙不一致
(finding 2),phase3(真實 pipeline)的 `power_key = normalize_comp(power_class)` 產出
class-衍生短名(Battery-AA/AC-Adapter/…),8 個電源 source class 中 **7 個**不在 _POWER_LABELS
→ 在生產原理圖被誤標「USB 5V」(電池/AC 專案標成 USB)。

本 gate:① 每個電源 source class(SUPPLY_V，lib 級單源)經 normalize_comp 都有**非-fallback**
標籤(釘住覆蓋、防詞彙漂移再生）；② 未知/不適配電源 = **無效設計輸入** → **raise**
(no-silent-fallback (a)；每個專案都應有適配電源)，不得靜默成「USB 5V」也不渲染未知標籤。
"""
import pytest

from lib.schematic import generate_svg, _POWER_LABELS
from lib.wiring.engine import normalize_comp
from lib.specs import SUPPLY_V


def test_every_power_source_class_has_nonfallback_label():
    """每個電源 source class（SUPPLY_V）經 phase3 的 normalize_comp 投影後，
    都須在 _POWER_LABELS 有標籤 —— 否則該電源專案的原理圖會 fallback 成「USB 5V」。"""
    missing = {}
    for cls in SUPPLY_V:
        short = normalize_comp(cls)
        if short not in _POWER_LABELS:
            missing[cls] = short
    assert not missing, (
        "電源 source class 經 normalize_comp 無對應標籤（會在 phase3 原理圖誤標 USB 5V）：\n  "
        + "\n  ".join(f"{c} -> {s!r}" for c, s in sorted(missing.items()))
        + "\n→ 在 lib/schematic._POWER_LABELS 補該短名標籤（或統一 power 詞彙，finding 2）。")


def test_battery_project_not_mislabeled_usb():
    """電池供電專案（phase3 傳 normalize_comp('Battery-AA-class')='Battery-AA'）的原理圖
    應標「AA 電池」，非靜默「USB 5V」。鎖住 #19 生產 bug 修復。"""
    svg = generate_svg("Arduino", normalize_comp("Battery-AA-class"), [], [])
    assert "AA 電池" in svg, "電池專案電源標籤遺失（誤標 USB 5V?）"


def test_unknown_power_raises_not_silent_usb():
    """未知/不適配電源 = 無效設計輸入 → raise（no-silent-fallback (a)）；
    不渲染、更不得偽裝成「USB 5V」。每個專案都應有適配電源。"""
    with pytest.raises(ValueError):
        generate_svg("Arduino", "SolarPanel", [], [])


def test_known_ui_short_still_labels():
    """既有 UI 短名（bake _POWER_KEY 值）標籤不回歸。"""
    assert "USB 5V" in generate_svg("Arduino", "USB-5V", [], [])
    assert "LiPo 3.7V" in generate_svg("Arduino", "LiPo", [], [])


def test_api_schematic_422_on_unfitting_power(monkeypatch):
    """API 邊界:未知/不適配電源 → /api/v1/schematic 回 422(與 /api/v1/wiring 一致),
    非靜默產出誤標原理圖。"""
    monkeypatch.setenv("CADHLLM_ALLOW_DEV_SECRET", "1")
    import asyncio
    from fastapi import HTTPException
    from services.gateway.routes_design import api_schematic, DesignRequest
    req = DesignRequest(brain="Arduino", outputs=["Relay-Module-class"], sensors=[],
                        power="SolarPanel")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(api_schematic(req))
    assert ei.value.status_code == 422


def test_bake_power_key_covers_classes_with_valid_labels():
    """B4:bake `_POWER_KEY`(電源 class→SVG 短名)須涵蓋每個電源 class(SUPPLY_V),且每個值皆為
    `_POWER_LABELS` 有效鍵 —— 補齊電源詞彙鏈一致性(與 #19 phase3 normalize_comp 路徑互補):
    防 bake canned 的 SVG 電源標籤因 class 漏映射或映射到無效短名而 fallback/誤標。"""
    from scripts.builders.bake_canned_bridges import _POWER_KEY
    missing_key = [c for c in SUPPLY_V if c not in _POWER_KEY]
    assert not missing_key, f"電源 class 無 bake._POWER_KEY(SVG 標籤會 fallback): {missing_key}"
    bad = {c: s for c, s in _POWER_KEY.items() if s not in _POWER_LABELS}
    assert not bad, f"_POWER_KEY 值非 _POWER_LABELS 有效鍵(標籤 fallback/誤標): {bad}"
