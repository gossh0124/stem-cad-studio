"""pipeline/clarify.py — Clarify Gate：用戶確認後的 bridge 映射邏輯。

從 pipeline_runner.py 抽取，負責將 Clarify UI 的回答映射到 bridge 元件替換。
"""
from __future__ import annotations
from typing import Callable, Dict, Optional

_ENV_MAP = {
    "室內":      {"environment": "indoor",  "waterproof": False, "ip_rating": "IP20"},
    "戶外":      {"environment": "outdoor", "waterproof": True,  "ip_rating": "IP67"},
    "陽台/半戶外": {"environment": "balcony", "waterproof": True,  "ip_rating": "IP54"},
    "其他":      {"environment": "indoor",  "waterproof": False, "ip_rating": "IP20"},
}

_POWER_SWAP_MAP: Dict[str, Dict[str, str]] = {
    "USB 插電":       {"type": "USB-5V-class",       "part": "USB 5V 電源模組"},
    "太陽能 + 鋰電池": {"type": "Battery-LiPo-class", "part": "鋰電池模組"},
    "AA 電池":        {"type": "Battery-AA-class",    "part": "AA 電池座"},
}

_CONN_BRAIN_MAP: Dict[str, str] = {
    "WiFi + 手機 App":  "ESP32-class",
    "Bluetooth 近距離": "ESP32-class",
    "LoRa 長距離":      "ESP32-class",
}


def apply_clarify_answers(
    bridge: dict,
    answers: dict,
    emit: Optional[Callable[[str], None]] = None,
) -> None:
    """將 clarify UI 的回答映射到 bridge，包括元件替換。"""
    if not answers:
        return

    bridge.setdefault("enclosure_constraints", {})
    components = bridge.get("components", [])

    # 元件確認回應（fuzzy_candidate / unknown / missing）
    comp_answers = answers.get("_component_confirms", {})
    for key, action in comp_answers.items():
        act = action.get("action", "")
        canonical = action.get("canonical", "")

        if act in ("accept_fuzzy", "use_equivalent"):
            for comp in components:
                if comp.get("_resolve", {}).get("original") == key:
                    comp["type"] = canonical
                    comp.pop("_resolve", None)
                    if emit:
                        emit(f"✅ 元件確認：{key} → {canonical}")
        elif act == "add_missing":
            role = action.get("role", "Sensor")
            if canonical:
                components.append({"role": role, "type": canonical, "qty": 1})
                if emit:
                    emit(f"➕ 補入遺漏元件：{key} → {canonical} ({role})")
        elif act == "skip":
            for comp in list(components):
                if comp.get("_resolve", {}).get("original") == key:
                    components.remove(comp)
                    if emit:
                        emit(f"⏭️ 跳過元件：{key}")

    # U6 Phase 2：近似值互證回應
    spec_answers = answers.get("_spec_confirms", {})
    if spec_answers:
        from ..shared.user_components_store import get_spec as _uc_get, add_component as _uc_add
        for compound_key, action in spec_answers.items():
            if action != "use_median":
                continue
            parts = compound_key.split("::", 1)
            if len(parts) != 2:
                continue
            comp_type, field_name = parts
            uc_spec = _uc_get(comp_type)
            if uc_spec is None:
                continue
            resolve_data = bridge.get("_component_resolve", {})
            for sw in resolve_data.get("spec_warnings", []):
                if sw["type"] != comp_type:
                    continue
                for w in sw["warnings"]:
                    if w["field"] == field_name:
                        setattr(uc_spec, field_name, w["median"])
                        _uc_add(uc_spec)
                        if emit:
                            emit(f"📊 近似值修正：{comp_type} {w['label']} → {w['median']} {w['unit']}")
                        break

    # S9：數量確認回應
    qty_answers = answers.get("_qty_confirms", {})
    for ctype, new_qty in qty_answers.items():
        try:
            new_qty = int(new_qty)
        except (ValueError, TypeError):
            if emit:
                emit(f"⚠️ 數量修正被忽略：{ctype} 的回答「{new_qty}」無法解析為整數，沿用原數量")
            continue
        if new_qty < 1:
            new_qty = 1
        for comp in components:
            if comp.get("type") == ctype:
                old_qty = comp.get("qty", 1)
                comp["qty"] = new_qty
                if emit:
                    emit(f"🔢 數量修正：{ctype} {old_qty} → {new_qty}")
                break

    # 清除剩餘 _resolve metadata
    for comp in components:
        comp.pop("_resolve", None)
    bridge.pop("_component_resolve", None)

    # Q1: 使用場景
    q_env = answers.get("q_env")
    if q_env and q_env in _ENV_MAP:
        bridge["environment_constraints"] = _ENV_MAP[q_env]
        if emit:
            emit(f"🌍 環境設定：{q_env} → {_ENV_MAP[q_env]}")

    # Q2: 電力來源
    q_power = answers.get("q_power")
    if q_power and q_power in _POWER_SWAP_MAP:
        swap = _POWER_SWAP_MAP[q_power]
        for comp in components:
            if comp.get("role") == "Power" and comp.get("type") != swap["type"]:
                old_type = comp.get("type", "?")
                comp["type"] = swap["type"]
                comp["part"] = swap["part"]
                comp.pop("spec", None)
                if emit:
                    emit(f"🔋 電力替換：{old_type} → {swap['type']}（用戶選擇「{q_power}」）")

    # Q4: 連線需求
    q_conn = answers.get("q_conn")
    if q_conn and q_conn in _CONN_BRAIN_MAP:
        required_brain = _CONN_BRAIN_MAP[q_conn]
        for comp in components:
            if comp.get("role") == "Brain":
                cur = comp.get("type", "")
                if "ESP32" not in cur and "ESP8266" not in cur:
                    comp["type"] = required_brain
                    comp.pop("spec", None)
                    if emit:
                        emit(f"📡 主控替換：{cur} → {required_brain}（需要 {q_conn}）")
                break
