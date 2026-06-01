"""pipeline/swap_engine.py — 元件替換建議引擎。

負責分析超標元件、生成替換建議、套用使用者選擇。
從 pipeline_runner.py 的 PipelineRunner 類別中抽取。
"""
from __future__ import annotations
from typing import Dict, List

from lib.specs import POWER_MA as _POWER_MA, lookup_constant as _lookup_constant

CURATED_ALT: Dict[str, Dict[str, str]] = {
    "Speaker-class":              {"type": "Buzzer-Active-class",     "label": "主動蜂鳴器"},
    "Lighting-NeoPixel-class":    {"type": "Lighting-LED-RGB-class",  "label": "RGB LED"},
    "Motor-DC-class":             {"type": "Motor-Servo-class",       "label": "伺服馬達"},
    "Pump-Water-class":           {"type": "Relay-Module-class",      "label": "繼電器模組"},
    "Display-LCD-class":          {"type": "Display-OLED-class",      "label": "OLED 螢幕"},
    "Lighting-LED-Strip-class":   {"type": "Lighting-LED-PWM-class",  "label": "單顆 PWM LED"},
    "LED-Matrix-class":           {"type": "Display-OLED-class",      "label": "OLED 螢幕"},
    "Motor-Stepper-class":        {"type": "Motor-Servo-class",       "label": "伺服馬達"},
    "Mist-Ultrasonic-class":      {"type": "Mist-Atomizer-class",     "label": "壓電霧化片"},
    "MP3-Module-class":           {"type": "Buzzer-Passive-class",    "label": "被動蜂鳴器"},
    "Lighting-LED-RGB-class":     {"type": "Lighting-LED-PWM-class",  "label": "單顆 PWM LED"},
}

TRADEOFF: Dict[tuple, str] = {
    ("Speaker-class",            "Buzzer-Active-class"):    "喇叭→蜂鳴器：無法播放 MP3，僅能發出單音提示",
    ("Lighting-NeoPixel-class",  "Lighting-LED-RGB-class"): "NeoPixel→RGB LED：可定址燈條變為單顆 RGB，無法做流水燈效",
    ("Motor-DC-class",           "Motor-Servo-class"):      "DC 馬達→伺服馬達：連續旋轉變為 0~180° 角度控制",
    ("Pump-Water-class",         "Relay-Module-class"):     "水泵→繼電器：直接驅動變為開關控制，需搭配外部水閥",
    ("Display-LCD-class",        "Display-OLED-class"):     "LCD 1602→OLED：字符屏變為 128×64 點陣（螢幕較小但省電）",
    ("Lighting-LED-Strip-class", "Lighting-LED-PWM-class"): "LED 燈條→單顆 LED：多燈變為單燈，適合指示用途",
    ("LED-Matrix-class",         "Display-OLED-class"):     "LED 矩陣→OLED：8×8 點陣變為小螢幕",
    ("Motor-Stepper-class",      "Motor-Servo-class"):      "步進馬達→伺服馬達：精密定位變為角度控制",
    ("Mist-Ultrasonic-class",    "Mist-Atomizer-class"):    "超音波霧化器→壓電霧化片：霧量減少但功耗降低",
    ("MP3-Module-class",         "Buzzer-Passive-class"):   "MP3 模組→被動蜂鳴器：無法播放音檔，僅能產生不同頻率音調",
    ("Lighting-LED-RGB-class",   "Lighting-LED-PWM-class"): "RGB LED→單顆 LED：三色變為單色調光",
}


def _rag_find_alternative(ctype: str, role: str) -> Dict[str, str] | None:
    """RAG 語義搜尋：找功能相近的替代元件（CURATED_ALT 未覆蓋時 fallback）。"""
    try:
        from lib.rag.rag_components import search_components
    except ImportError:
        return None

    try:
        results = search_components(
            query=f"{role} component similar to {ctype}",
            top_k=5,
            role_filter=role if role not in ("Brain", "Power") else None,
        )
    except Exception:
        return None

    current_ma = _lookup_constant(_POWER_MA, ctype, None)
    for r in results:
        alt_type = r.get("class_name", "")
        if alt_type == ctype:
            continue
        alt_ma = _lookup_constant(_POWER_MA, alt_type, None)
        if alt_ma is None:
            continue
        if current_ma is not None and alt_ma >= current_ma:
            continue
        return {"type": alt_type, "label": r.get("name", alt_type)}

    return None


def build_swap_suggestions(bridge: dict) -> list:
    """分析超標元件，生成按省電量排序的替換建議。"""
    components = bridge.get("components", [])
    suggestions = []

    for i, comp in enumerate(components):
        ctype = comp.get("type")
        if not ctype:
            raise ValueError(f'Component at index {i} missing required key "type": {comp!r}')
        role = comp.get("role", "")
        if role in ("Brain", "Power"):
            continue

        alt_info = CURATED_ALT.get(ctype)
        if not alt_info:
            rag_alt = _rag_find_alternative(ctype, role)
            if not rag_alt:
                continue
            alt_info = rag_alt

        alt_type = alt_info["type"]
        current_ma = _lookup_constant(_POWER_MA, ctype, None)
        alt_ma = _lookup_constant(_POWER_MA, alt_type, None)
        if current_ma is None or alt_ma is None:
            continue
        saving = current_ma - alt_ma
        if saving <= 0:
            continue

        tradeoff = TRADEOFF.get(
            (ctype, alt_type), f"{ctype} → {alt_type}")

        suggestions.append({
            "id": f"swap_{i}",
            "comp_index": i,
            "current": {"type": ctype, "role": role, "ma": round(current_ma, 1)},
            "alternative": {
                "type": alt_type,
                "label": alt_info["label"],
                "ma": round(alt_ma, 1),
            },
            "saving_ma": round(saving, 1),
            "trade_off": tradeoff,
            "stem_concept": "比較同功能元件的功耗差異，學習設計取捨",
        })

    suggestions.sort(key=lambda s: s["saving_ma"], reverse=True)
    return suggestions


def apply_swaps(bridge: dict, suggestions: list, selected_ids: List[str]):
    """將使用者勾選的替換方案套用到 bridge.components。"""
    if not selected_ids:
        return
    swap_map = {s["id"]: s for s in suggestions}
    components = bridge.get("components", [])
    for swap_id in selected_ids:
        swap = swap_map.get(swap_id)
        if not swap:
            continue
        idx = swap["comp_index"]
        if idx < len(components):
            components[idx]["type"] = swap["alternative"]["type"]
            components[idx].pop("spec", None)
    bridge["components"] = components
