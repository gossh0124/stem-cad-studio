"""Phase 2 step 1：被動元件(R/C/D)升 netlist 一等公民的標註層。

為每個 passive 物件補：
  - refdes：確定性編號（全方案一命名空間，R1/C1/D1...；同輸入必得同 refdes）
  - location："onboard"（模組/開發板已焊）或 "external"（學生需自備外接）
  - purchasable：external→True 進 BOM；onboard→False（避免重複採購/電氣雙重）
  - onboard_ref：若 onboard，指回 verified.json on_board_components 的來源

location 判定 = 拓撲預設 + on_board_components 覆寫（權威，符合「權威來源優先」）。
被動仍維持「繪製層標註/徽章」（不切 ELK 走線）；本層只加資料欄位。
設計見 .ai/_phase2_design.md（B-1：不建 R/C/D class，用 on_board_components 當板載真相）。
"""
from __future__ import annotations

import json
from pathlib import Path

# 拓撲 → 預設 location（被 on_board_components 覆寫前的起點）
_TOPO_DEFAULT_LOCATION: dict[str, str] = {
    "series": "external",      # 限流/串聯，學生外接（如 LED 220Ω）
    "pullup": "external",      # 上拉（如 bare DHT22 4.7kΩ）
    "divider": "external",     # 分壓（如 LDR 10kΩ）
    "decoupling": "onboard",   # IC 去耦，模組板已焊
    "bulk": "onboard",         # MCU 電源軌大電容，開發板已焊
    "flyback": "onboard",      # 繼電器飛輪二極體，模組板已有（如 Relay D1）
}

_DATASHEET_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "component_datasheet_verified.json"
_datasheet_cache: dict | None = None


def _load_datasheet() -> dict:
    """Lazy + cached 載入 verified.json 的 components 區（fail-open 回空 dict）。"""
    global _datasheet_cache
    if _datasheet_cache is None:
        try:
            d = json.loads(_DATASHEET_PATH.read_text(encoding="utf-8"))
            _datasheet_cache = d.get("components", d) if isinstance(d, dict) else {}
        except (OSError, json.JSONDecodeError):
            _datasheet_cache = {}
    return _datasheet_cache


def _onboard_passive_kinds(class_name: str) -> set[str]:
    """該 class 的 on_board_components 中已板載的被動 kind（R/C/D）。"""
    ds = _load_datasheet()
    obc = ds.get(class_name, {}).get("on_board_components", []) or []
    kinds: set[str] = set()
    for o in obc:
        rid = str(o.get("id") or "").upper()
        if rid[:1] in ("R", "C", "D"):
            kinds.add(rid[:1])
    return kinds


def annotate_passives(
    wiring: dict,
    power_passives: list[dict],
    comp_classes: dict[str, str] | None = None,
) -> None:
    """In-place 為 wiring 與 power_passives 內所有 passive 補 refdes/location/purchasable。

    Args:
        wiring: resolve_wiring 輸出 {comp_short: {"pins":[{...,"passive":{}}], "decoupling":[{}]}}
        power_passives: MCU_POWER_PASSIVES list（電源軌被動，topo=bulk/decoupling→onboard）
        comp_classes: {comp_short: class_name}，供 on_board_components 覆寫查詢；None 則僅用拓撲預設
    """
    comp_classes = comp_classes or {}
    counters = {"R": 0, "C": 0, "D": 0}

    def _refdes(kind: str) -> str:
        k = kind if kind in counters else "R"
        counters[k] += 1
        return f"{k}{counters[k]}"

    def _nets(p: dict, comp_short: str | None, pin: dict | None, power_net: str | None) -> list[str]:
        """被動的雙端 net。topo 決定第二端（VCC/GND/元件腳）。"""
        topo = p.get("topo", "series")
        if power_net:  # MCU 電源軌 bulk/decoupling：net ↔ GND
            return [power_net, "GND"]
        if topo == "decoupling" and comp_short:  # IC 去耦：VCC ↔ GND（元件電源腳）
            return [f"{comp_short}.VCC", "GND"]
        if pin is not None and comp_short:
            sig = f"{comp_short}.{pin.get('comp', '')}"
            mcu = f"MCU.{pin.get('mcu', '')}"
            if topo == "pullup":   # 訊號腳 ↔ VCC
                return [sig, "VCC"]
            if topo == "divider":  # 訊號腳 ↔ GND
                return [sig, "GND"]
            return [mcu, sig]      # series：MCU 腳 ↔ 元件腳（串聯於訊號線）
        return []

    def _annotate(p: dict, comp_short: str | None, pin: dict | None = None,
                  power_net: str | None = None) -> None:
        kind = p.get("kind", "R")
        topo = p.get("topo", "series")
        loc = _TOPO_DEFAULT_LOCATION.get(topo, "external")
        # on_board_components 覆寫（權威）：模組板已有同 kind 被動 → 強制 onboard
        if comp_short and comp_short in comp_classes:
            cls = comp_classes[comp_short]
            if kind in _onboard_passive_kinds(cls):
                loc = "onboard"
                p["onboard_ref"] = f"{cls}:on_board"
        p["location"] = loc
        p["purchasable"] = loc == "external"
        p["refdes"] = _refdes(kind)
        p["nets"] = _nets(p, comp_short, pin, power_net)

    # 確定性順序：wiring dict 插入序（= 正規化 comps 序）→ 每 comp 先 pins 後 decoupling → 最後 power
    for comp_short, info in wiring.items():
        for pin in info.get("pins", []):
            pas = pin.get("passive")
            if pas:
                _annotate(pas, comp_short, pin=pin)
        for cap in info.get("decoupling", []):
            _annotate(cap, comp_short)
    for pp in power_passives:
        _annotate(pp, None, power_net=pp.get("net"))
