"""tests/test_pcb_vs_verified_alignment.py — B5-coord Slice 1:雙座標源機器對齊 gate。

背景(2026-06-11 recon workflow `w5h1crhal`):lib/pcb(6 模組 PCBSpec)與
verified.json 之間**此前零機器 gate**(僅註解宣稱對齊),實測已實質漂移——
HC-SR04 header x 差 5.96mm 且異邊、OLED 上排孔差 2mm、Relay 孔位完全不同、
Relay 螺絲端子 lib=右牆 vs vj=上牆(實體矛盾)。使用者裁示(2026-06-10):
**座標 SSOT = verified.json**;但直接全面讀穿會在未裁決真值下移動外殼幾何
1~6mm(違 use-real-official-values)→ Slice 1 先上 gate:

  - 把「對齊」從註解宣稱變機器事實;
  - 今日已知漂移凍結為 FROZEN_DRIFT(棘輪):**新漂移 → 立即 FAIL**;
    已凍結漂移被修復 → 也 FAIL(提示縮減清單,防 stale 豁免);
  - 凍結清單即 Slice 2 的待裁決工作清單(逐筆回 datasheet 裁真值)。

座標慣例:兩源皆宣告 PCB 左下原點/y-up/mm;pin y 的 lib 內縮(1.27=半 pitch)
vs vj 邊線(0/W)為已知慣例差,收口於 pin_y 漂移碼,Slice 3 裁決。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.pcb import ALL_MODULES

ROOT = Path(__file__).resolve().parent.parent
_VERIFIED = ROOT / "data" / "component_datasheet_verified.json"
_TOL = 0.1  # mm,與既有 drift gate(test_dimensions_drift)同容差


def _vj_components() -> dict:
    d = json.loads(_VERIFIED.read_text(encoding="utf-8"))
    return d.get("components", d) if isinstance(d, dict) else {}


def _r1(v) -> float:
    return round(float(v), 1)


def drift_codes(pcb, entry: dict) -> list[str]:
    """機器算出該 class 的漂移碼(粗粒度、確定性;細節進斷言訊息)。"""
    phys = entry.get("physical", {}) or {}
    codes: list[str] = []
    if abs(pcb.length - phys.get("length_mm", -1)) > _TOL:
        codes.append("L")
    if abs(pcb.width - phys.get("width_mm", -1)) > _TOL:
        codes.append("W")
    t_vj = phys.get("pcb_thickness_mm")
    if t_vj is None:
        codes.append("thickness_missing_vj")
    elif abs(pcb.pcb_thickness - t_vj) > _TOL:
        codes.append("thickness")
    lib_holes = sorted((_r1(h.x), _r1(h.y), _r1(h.diameter)) for h in pcb.mounting_holes)
    vj_holes = sorted(
        (_r1(h.get("x_mm")), _r1(h.get("y_mm")), _r1(h.get("diameter_mm", h.get("d_mm", -1))))
        for h in (phys.get("mounting_holes") or entry.get("mounting_holes") or []))
    if lib_holes != vj_holes:
        codes.append("holes")
    vj_pins = [p for hg in (entry.get("pin_layout", {}).get("header_groups") or [])
               for p in hg.get("pins", [])]
    lib_px = sorted(_r1(p.x) for p in pcb.pins)
    vj_px = sorted(_r1(p["x_mm"]) for p in vj_pins)
    if len(lib_px) != len(vj_px):
        codes.append("pin_count")
    else:
        if lib_px != vj_px:
            codes.append("pin_x")
        if sorted(_r1(p.y) for p in pcb.pins) != sorted(_r1(p["y_mm"]) for p in vj_pins):
            codes.append("pin_y")
    return codes


# 2026-06-11 凍結現狀(probe 實測;棘輪:新增漂移 FAIL、修復未除名也 FAIL)。
# 待裁決重點:Relay holes 完全不同(lib 上緣 vs vj 下緣)+ pin_count(vj 多
# SCREW_TERMINAL 群組,lib 無對應);OLED 上排孔 y 22.5 vs 24.5(vj 對稱較可信);
# LCD 孔徑 3.0 vs 2.5;HC-SR04 厚度 1.6 vs 1.2;pin_x 各類偏移 0.7~5.96mm;
# pin_y 含內縮/邊線慣例差。5 類 vj 缺 pcb_thickness_mm(SSOT 補值項)。
FROZEN_DRIFT: dict[str, set[str]] = {
    "Display-LCD-class": {"thickness_missing_vj", "holes", "pin_x", "pin_y"},
    "Display-OLED-class": {"thickness_missing_vj", "holes", "pin_x", "pin_y"},
    "Relay-Module-class": {"thickness_missing_vj", "holes", "pin_count"},
    "Sensor-PIR-class": {"thickness_missing_vj", "pin_x", "pin_y"},
    "Sensor-TempHumid-class": {"thickness_missing_vj", "pin_x", "pin_y"},
    "Sensor-Ultrasonic-class": {"thickness", "pin_x", "pin_y"},
}


class TestPcbVsVerifiedAlignment:
    def test_all_modules_present_in_verified(self):
        """lib/pcb 每個模組 class 必在 verified.json(SSOT 覆蓋完整性)。"""
        comps = _vj_components()
        missing = [c for c in ALL_MODULES if c not in comps]
        assert missing == [], f"lib/pcb 模組不在 verified.json:{missing}"

    def test_lw_aligned_invariant(self):
        """L/W 不變量:六類整板尺寸兩源必相等(Tier 2 覆寫的無症狀前提,正式上鎖)。"""
        comps = _vj_components()
        for cls, pcb in ALL_MODULES.items():
            codes = drift_codes(pcb, comps[cls])
            assert "L" not in codes and "W" not in codes, (
                f"{cls} 整板 L/W 漂移 — Tier 2 覆寫不再無症狀,立即裁決")

    def test_drift_ratchet(self):
        """棘輪:漂移碼集合必須恰等於凍結清單 — 新漂移 FAIL(雙源失守),
        已修復未除名也 FAIL(防 stale 豁免;修復後請自清單移除該碼)。"""
        comps = _vj_components()
        problems: list[str] = []
        for cls, pcb in ALL_MODULES.items():
            actual = set(drift_codes(pcb, comps[cls])) - {"L", "W"}
            frozen = FROZEN_DRIFT.get(cls, set())
            new = actual - frozen
            fixed = frozen - actual
            if new:
                problems.append(f"{cls} 新漂移 {sorted(new)}(裁示 SSOT=verified.json,"
                                f"請回 datasheet 裁決後修正漂移側)")
            if fixed:
                problems.append(f"{cls} 漂移 {sorted(fixed)} 已修復,請自 FROZEN_DRIFT 除名(棘輪縮減)")
        assert problems == [], "\n".join(problems)

    def test_registry_tier2_consistency(self):
        """registry 最終 spec(經 Tier 1.5 讀穿 + Tier 2 lib/pcb 覆寫)L/W 仍等於
        verified.json physical — 守住「覆寫不改變 SSOT 值」的等價性。"""
        from lib.registry import COMPONENT_REGISTRY
        comps = _vj_components()
        for cls in ALL_MODULES:
            spec = COMPONENT_REGISTRY.get(cls)
            if spec is None:
                pytest.fail(f"{cls} 不在 COMPONENT_REGISTRY")
            phys = comps[cls]["physical"]
            assert abs(spec.length_mm - phys["length_mm"]) <= _TOL, cls
            assert abs(spec.width_mm - phys["width_mm"]) <= _TOL, cls


class TestGateNotFalseGreen:
    """meta-gate:合成漂移必被算出(防 drift_codes 永回空)。"""

    def test_synthetic_drift_detected(self):
        pcb = ALL_MODULES["Sensor-Ultrasonic-class"]
        entry = {"physical": {"length_mm": pcb.length + 5.0, "width_mm": pcb.width,
                              "pcb_thickness_mm": pcb.pcb_thickness},
                 "pin_layout": {"header_groups": [{"pins": [
                     {"name": p.name, "x_mm": p.x, "y_mm": p.y} for p in pcb.pins]}]}}
        codes = drift_codes(pcb, entry)
        assert "L" in codes and "pin_x" not in codes, codes

    def test_aligned_entry_yields_empty(self):
        pcb = ALL_MODULES["Sensor-Ultrasonic-class"]
        entry = {"physical": {"length_mm": pcb.length, "width_mm": pcb.width,
                              "pcb_thickness_mm": pcb.pcb_thickness},
                 "pin_layout": {"header_groups": [{"pins": [
                     {"name": p.name, "x_mm": p.x, "y_mm": p.y} for p in pcb.pins]}]}}
        assert drift_codes(pcb, entry) == []
