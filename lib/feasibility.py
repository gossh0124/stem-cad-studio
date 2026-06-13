"""feasibility.py — Phase I bridge 事後可行性檢查。

對 Phase I 產出的 bridge dict 執行純規則（不呼叫 LLM）的可行性審查，
回傳帶有教育語氣的問題清單，協助 STEM 學生理解「為何不可行」並提供改善建議。

符合 6E 框架的 Explain（解釋原理）與 Evaluate（評估方案）階段。

API 契約：
    check_feasibility(bridge: dict) -> list[dict]
    每筆結果包含：
        component    (str)  — 出問題的元件類型或 "system"
        severity     (str)  — "error" | "warning"
        issue        (str)  — 簡短問題描述
        why          (str)  — 教育性說明（原理解釋）
        suggested_fix (str) — 可操作的解決方案

資料來源：
    - bridge spec（來自 COMPONENT_REGISTRY，由 Phase I 填入）
    - data/component_datasheet_verified.json（SSOT，三來源交叉驗證）
    禁止在此檔案 hardcode 任何元件數值。

規則資料表：lib/feasibility_rules.py（CAPABILITY_RULES、LONG_RUN_PATTERNS、MISSING_CAPABILITY_RULES）
驗收測試：tests/test_feasibility.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .feasibility_rules import CAPABILITY_RULES, LONG_RUN_PATTERNS, MISSING_CAPABILITY_RULES

# ---------------------------------------------------------------------------
# 1. SSOT 載入：data/component_datasheet_verified.json
# ---------------------------------------------------------------------------

_DATASHEET_PATH = Path(__file__).parent.parent / "data" / "component_datasheet_verified.json"


def _load_datasheet() -> dict[str, Any]:
    """載入 datasheet JSON（UTF-8）。讀取失敗時 raise，不靜默退降級。"""
    if not _DATASHEET_PATH.exists():
        raise FileNotFoundError(
            f"SSOT datasheet 找不到：{_DATASHEET_PATH}。"
            "請確認 data/component_datasheet_verified.json 存在。"
        )
    with open(_DATASHEET_PATH, encoding="utf-8") as f:
        return json.load(f)


_DATASHEET: dict[str, Any] = _load_datasheet()


def _ds_electrical(class_name: str) -> dict[str, Any]:
    """取得 datasheet 中特定元件的 electrical 欄位；找不到回傳空 dict。"""
    return _DATASHEET.get(class_name, {}).get("electrical", {})


def _ds_capacity_mah(class_name: str) -> float | None:
    """從 datasheet 取電池 capacity_mah；欄位不存在回傳 None（不捏造）。"""
    return _ds_electrical(class_name).get("capacity_mah")


def _ds_output_voltage(class_name: str) -> float | None:
    """從 datasheet 取電源元件輸出電壓（output_voltage_v 或 voltage_nominal_v）。"""
    elec = _ds_electrical(class_name)
    return elec.get("output_voltage_v") or elec.get("voltage_nominal_v")


def _ds_min_voltage(class_name: str) -> float | None:
    """從 datasheet 取元件最小工作電壓（多欄位 fallback）。"""
    elec = _ds_electrical(class_name)
    return (
        elec.get("voltage_min_v")
        or elec.get("voltage_operating_v")
        or elec.get("voltage_input_v")
    )


# ---------------------------------------------------------------------------
# 電源兩域常數
# ---------------------------------------------------------------------------

# 負載電源偵測（複用後端兩域模型 reference_power_topology_wiring_standard）：
# 電流 ≥ 此值或 datasheet notes 明示須 driver → 需外接電源經 driver/relay，不可 MCU 腳直驅。
_LOAD_POWER_CURRENT_MA = 200.0
_LOAD_POWER_NOTE_KEYS = (
    "cannot drive", "requires relay", "requires h-bridge",
    "requires driver", "h-bridge driver", "mosfet for mcu",
)
_DRIVER_TYPE_KEYS = ("relay", "l298n", "l293", "driver", "uln2003", "tb6612", "mosfet")
# bridge role 命名雙慣例（測試 fixture 用 'mcu'/'power'、canned state 用 'Brain'/'Power'）→
# role 不可靠時用 type 關鍵字 fallback，避免漏判（曾因只認 'Brain' 而生產 no-op）。
_BRAIN_TYPE_KEYS = ("arduino", "esp32", "esp8266", "microbit", "micro:bit", "raspberry", "rpi")
_POWER_TYPE_KEYS = ("battery", "usb-5v", "usb5v", "usb-adapter", "ac-adapter")


# ---------------------------------------------------------------------------
# 2. 意圖偵測輔助函式
# ---------------------------------------------------------------------------

def _detect_intent(instruction: str, patterns: list[str]) -> bool:
    """檢查 instruction 是否符合任一意圖 pattern（大小寫不分）。"""
    if not instruction:
        return False
    for pat in patterns:
        if re.search(pat, instruction, re.IGNORECASE):
            return True
    return False


def _detect_long_run(instruction: str) -> tuple[bool, float]:
    """
    偵測 _instruction 是否暗示長時運轉需求。
    回傳 (detected, expected_hours)；未偵測到時回傳 (False, 0.0)。
    """
    if not instruction:
        return False, 0.0
    for pattern, expected_h in LONG_RUN_PATTERNS:
        if re.search(pattern, instruction, re.IGNORECASE):
            return True, expected_h
    return False, 0.0


# ---------------------------------------------------------------------------
# 3. 核心檢查函式
# ---------------------------------------------------------------------------

def _check_capability(bridge: dict) -> list[dict]:
    """
    檢查 1：能力誤用（CAPABILITY_RULES 表驅動）。
    intent_patterns 與 component_match 同時命中 → 產生問題。
    """
    issues: list[dict] = []
    instruction = bridge.get("_instruction", "")
    components = bridge.get("components", [])

    for rule in CAPABILITY_RULES:
        if not _detect_intent(instruction, rule["intent_patterns"]):
            continue
        # exclude_patterns(negative-guard):意圖命中排除樣式 → 跳過此規則。
        # 例:CAP-001 的 行走/前進/走路 會掃到足式步行,但雙足/四足用伺服做「關節角度控制」
        # (伺服正確用途,非驅動輪)→ 以 雙足/walker/腿 等排除,避免偽陽性 error。
        if rule.get("exclude_patterns") and _detect_intent(instruction, rule["exclude_patterns"]):
            continue
        for comp in components:
            comp_type = comp.get("type", comp.get("selected_type", ""))
            if re.match(rule["component_match"], comp_type, re.IGNORECASE):
                issues.append({
                    "component": comp_type,
                    "severity": rule["severity"],
                    "issue": rule["issue"],
                    "why": rule["why"],
                    "suggested_fix": rule["suggested_fix"],
                })
                break  # 同一規則每次只報告一次
    return issues


def _check_energy_runtime(bridge: dict) -> list[dict]:
    """
    檢查 2：能量續航（量化計算）。

    runtime_hours = capacity_mah（SSOT datasheet）÷ total_current_ma（bridge spec）
    若 _instruction 暗示長時運轉且 runtime < expected * 0.5 → error。
    資料缺失時產生 warning，禁靜默跳過。
    """
    issues: list[dict] = []
    instruction = bridge.get("_instruction", "")
    components = bridge.get("components", [])

    is_long_run, expected_hours = _detect_long_run(instruction)
    if not is_long_run:
        return issues

    # 找有 capacity_mah 的電池元件
    battery_components: list[dict] = []
    for comp in components:
        comp_type = comp.get("type", comp.get("selected_type", ""))
        cap = _ds_capacity_mah(comp_type)
        if cap is not None:
            battery_components.append({"comp_type": comp_type, "capacity_mah": cap})

    if not battery_components:
        issues.append({
            "component": "system",
            "severity": "warning",
            "issue": "偵測到長時運轉意圖，但未找到電池元件或電池資料缺失",
            "why": (
                "系統在 bridge 中找不到有 capacity_mah 資料的電池元件。"
                "若此專案依賴電池供電，必須明確指定電池型號以進行續航評估。"
            ),
            "suggested_fix": (
                "請在 bridge components 中加入電池元件"
                "（如 Battery-AA-class 或 Battery-LiPo-class），"
                "或改用 AC-Adapter-class（市電）以避免電量限制。"
            ),
        })
        return issues

    battery_type_set = {bc["comp_type"] for bc in battery_components}
    consumer_currents: list[tuple[str, float]] = []
    missing_current: list[str] = []

    for comp in components:
        comp_type = comp.get("type", comp.get("selected_type", ""))
        if comp_type in battery_type_set:
            continue
        spec = comp.get("spec", {})
        current_ma = spec.get("current_ma")
        if current_ma is None:
            ds_cur = _ds_electrical(comp_type).get("current_typ_ma")
            if ds_cur is not None:
                current_ma = ds_cur
            else:
                missing_current.append(comp_type)
                continue
        consumer_currents.append((comp_type, float(current_ma)))

    if missing_current:
        missing_str = ", ".join(set(missing_current))
        issues.append({
            "component": missing_str,
            "severity": "warning",
            "issue": f"下列元件缺少電流消耗資料，無法精確計算續航：{missing_str}",
            "why": (
                "精確的續航計算需要所有元件的電流消耗值。"
                "缺少資料的元件可能導致低估實際用電，計算結果僅為下限估算。"
            ),
            "suggested_fix": (
                "請確認這些元件在 COMPONENT_REGISTRY 中有 current_ma 欄位，"
                "或在 data/component_datasheet_verified.json 中補充 current_typ_ma。"
            ),
        })

    if not consumer_currents:
        return issues

    total_current_ma = sum(cur for _, cur in consumer_currents)
    if total_current_ma <= 0:
        return issues

    primary_battery = max(battery_components, key=lambda bc: bc["capacity_mah"])
    capacity_mah = primary_battery["capacity_mah"]
    battery_type = primary_battery["comp_type"]
    runtime_hours = capacity_mah / total_current_ma

    if runtime_hours < expected_hours * 0.5:
        consumer_detail = ", ".join(f"{ct}({ma:.0f}mA)" for ct, ma in consumer_currents)
        issues.append({
            "component": battery_type,
            "severity": "error",
            "issue": (
                f"電池續航不足：以 {battery_type}（{capacity_mah:.0f}mAh）驅動此配置，"
                f"估算續航約 {runtime_hours:.1f} 小時，"
                f"遠低於學生目標的 {expected_hours:.0f} 小時"
            ),
            "why": (
                f"電池續航公式：runtime = capacity_mah ÷ total_current_ma。\n"
                f"  電池容量：{capacity_mah:.0f} mAh（來源：SSOT datasheet）\n"
                f"  各元件電流：{consumer_detail}\n"
                f"  總電流：{total_current_ma:.0f} mA\n"
                f"  估算續航：{capacity_mah:.0f} ÷ {total_current_ma:.0f}"
                f" = {runtime_hours:.1f} 小時\n"
                f"  學生期望：≥ {expected_hours:.0f} 小時\n\n"
                "注意：實際電池在大電流下因內阻壓降，容量會進一步縮減（Peukert 效應）。"
                "以上為理想值，實際續航可能更短。"
            ),
            "suggested_fix": (
                "解決方案（依可行性排序）：\n"
                "  1. 改用 AC-Adapter-class（市電接頭）— 不受電量限制，適合固定場所\n"
                "  2. 換大容量電池（Battery-LiPo-class 可達 10000mAh 以上的行動電源）\n"
                "  3. 降低系統功耗：換低功耗 MCU"
                "（如 Microbit-class 30mA vs RaspberryPi-class 600mA）、"
                "關閉不必要的週邊（WiFi、螢幕）\n"
                "  4. 加入電源管理：讓 MCU 進入睡眠模式，僅在需要時喚醒"
            ),
        })
    return issues


def _comp_type(comp: dict) -> str:
    return comp.get("type", comp.get("selected_type", "")) or ""


def _is_brain(comp: dict) -> bool:
    if (comp.get("role") or "").lower() in ("brain", "mcu"):
        return True
    t = _comp_type(comp).lower()
    return any(k in t for k in _BRAIN_TYPE_KEYS)


def _is_power(comp: dict) -> bool:
    if (comp.get("role") or "").lower() == "power":
        return True
    t = _comp_type(comp).lower()
    return any(k in t for k in _POWER_TYPE_KEYS)


def _ds_needs_load_power(class_name: str) -> bool:
    """SSOT 判斷：元件是否需負載電源（高電流 → 不可由 MCU 腳直驅，須外接電源經 driver/relay）。

    優先看 datasheet electrical.notes（權威：「cannot drive from GPIO」「requires driver」），
    再回退電流門檻（≥200mA;排除 PIR 65mA / 小 LED 等由 VCC 軌供電的邏輯件）。
    """
    elec = _ds_electrical(class_name)
    notes = (elec.get("notes") or "").lower()
    if any(k in notes for k in _LOAD_POWER_NOTE_KEYS):
        return True
    cur = elec.get("current_typ_ma") or elec.get("current_max_ma")
    return cur is not None and cur >= _LOAD_POWER_CURRENT_MA


def _check_power_domain(bridge: dict) -> list[dict]:
    """
    檢查 4：電源兩域可行性（複用後端 power_inject SSOT，把後端可行性結論以教學語言呈現給學生）。

    (1) MCU 電源相容（邏輯域）：電源能否供 MCU。不可行＋無 driver → error（電壓不符）;
        不可行＋有 driver → warning（此電源實為負載電源，MCU 另需 USB）。
    (2) 負載電源需求（負載域）：高電流元件（B 類）需外接電源經 driver/relay，缺則 warning。
    """
    issues: list[dict] = []
    components = bridge.get("components", [])
    brain = next((c for c in components if _is_brain(c)), None)
    power = next((c for c in components if _is_power(c)), None)
    if brain is None:
        return issues
    brain_type = _comp_type(brain)
    types = [_comp_type(c) for c in components]
    has_driver = any(any(k in t.lower() for k in _DRIVER_TYPE_KEYS) for t in types)

    # (1) MCU 電源相容（邏輯域）— 複用後端 derive_power_injection（同 SSOT）
    if power is not None:
        power_type = power.get("type", power.get("selected_type", ""))
        try:
            from .wiring.power_inject import derive_power_injection
            derive_power_injection(brain_type, power_type)
        except Exception:  # noqa: BLE001 — 不可行（電壓不符 / 查無）
            if has_driver:
                issues.append({
                    "component": power_type,
                    "severity": "warning",
                    "issue": f"{power_type} 電壓不足以供 {brain_type}（邏輯電源）",
                    "why": (
                        f"{power_type} 的輸出電壓無法供 {brain_type} 本體運作。本專案有繼電器/驅動板，"
                        f"此電源應作為「負載電源」——經繼電器/驅動板供高電流元件（如馬達、泵），"
                        f"而 {brain_type} 本身需另接 USB 邏輯電源。這是電路的兩種電源域（邏輯 vs 負載）。"
                    ),
                    "suggested_fix": (
                        f"確認 {brain_type} 由 USB 供電;此電源接繼電器 COM / 驅動板電源端（負載側），與 MCU 共地。"
                    ),
                })
            else:
                issues.append({
                    "component": power_type,
                    "severity": "error",
                    "issue": f"{power_type} 無法供 {brain_type}（電壓不符）",
                    "why": (
                        f"{power_type} 的輸出電壓不在 {brain_type} 的電源輸入範圍內，"
                        f"直接供電會無法開機或損壞。"
                    ),
                    "suggested_fix": (
                        f"改用 USB-5V-class（{brain_type} 最佳供電）;"
                        f"或換用相容的 MCU（如 2×AA 3V 適合 micro:bit）。"
                    ),
                })

    # (2) 負載電源需求（負載域）— 高電流元件須外接電源經 driver/relay
    for comp in components:
        if _is_brain(comp) or _is_power(comp):
            continue
        ctype = _comp_type(comp)
        if not ctype or has_driver or not _ds_needs_load_power(ctype):
            continue
        cur = _ds_electrical(ctype).get("current_typ_ma") or _ds_electrical(ctype).get("current_max_ma")
        issues.append({
            "component": ctype,
            "severity": "warning",
            "issue": f"{ctype} 電流過高（約 {cur}mA），需外接電源經驅動板/繼電器",
            "why": (
                f"{ctype} 約需 {cur}mA，超過 MCU GPIO 每腳上限（約 40mA），"
                f"不可由 MCU 腳直接供電，否則會燒壞 I/O。"
            ),
            "suggested_fix": (
                "加入 Relay-Module-class（開關控制）或 L298N-Driver-class（馬達調速），"
                "並用外接電源（電池/變壓器）供其負載側，與 MCU 共地。"
            ),
        })
    return issues


# ---------------------------------------------------------------------------
# 3. 缺少能力檢查函式
# ---------------------------------------------------------------------------

def check_missing_capabilities(user_intent: str, components: list[dict]) -> list[dict]:
    """
    檢查 3：缺少能力（MISSING_CAPABILITY_RULES 表驅動）。

    對每條規則：
      1. 若使用者意圖文字中包含任一 intent_keyword（大小寫不分）→ 觸發
      2. 若觸發後元件清單中沒有 type 以 required_category 開頭的元件 → 回傳警告
      3. 若元件已存在 → 不回報（正常）

    參數：
        user_intent  — 使用者輸入的自然語言意圖字串（bridge["_instruction"]）
        components   — bridge["components"] list，每筆含 type 欄位

    回傳 list[dict]，每筆格式：
        {
            "rule_id":            str,
            "missing_component":  str,   # required_category
            "reason":             str,   # reason_zh
            "component":          str,   # = missing_component（符合現有 issue 格式）
            "severity":           str,   # "warning"
            "issue":              str,
            "why":                str,
            "suggested_fix":      str,
        }
    """
    if not user_intent:
        return []

    intent_lower = user_intent.lower()
    issues: list[dict] = []

    for rule in MISSING_CAPABILITY_RULES:
        # 步驟 1：意圖關鍵字比對（任一命中即觸發）
        keyword_hit = any(kw.lower() in intent_lower for kw in rule["intent_keywords"])
        if not keyword_hit:
            continue

        # 步驟 2：元件清單中是否已有所需類別
        required = rule["required_category"]
        has_required = any(
            comp.get("type", comp.get("selected_type", "")).startswith(required)
            for comp in components
        )
        if has_required:
            continue

        # 步驟 3：缺少 → 產生警告
        issues.append({
            "rule_id": rule["rule_id"],
            "missing_component": required,
            "reason": rule["reason_zh"],
            "component": required,
            "severity": "warning",
            "issue": f"意圖暗示需要 {required}，但元件清單中找不到此類感測器",
            "why": (
                f"{rule['reason_zh']}。\n"
                f"您的說明中包含「{rule['intent_keywords'][0]}」等關鍵詞，"
                f"這通常表示專案需要偵測此類環境訊號。"
                f"若沒有對應感測器，MCU 將無法取得這項資料。"
            ),
            "suggested_fix": (
                f"請在元件清單中加入 {required}-class 感測器，"
                f"並將其連接至 MCU 的類比或數位輸入腳位。"
                f"若此功能並非必要，請調整專案說明以避免誤判。"
            ),
        })

    return issues


# ---------------------------------------------------------------------------
# 4. 主入口
# ---------------------------------------------------------------------------

def check_feasibility(bridge: dict) -> list[dict]:
    """
    對 Phase I 產出的 bridge 做事後可行性檢查。

    bridge 結構：
        project_name (str), project_category (str), _instruction (str),
        components (list): 每筆含 role, type, qty, spec{voltage_v, current_ma, ...}

    回傳 list[dict]，每筆含：
        component, severity ("error"|"warning"), issue, why, suggested_fix

    設計原則：
        - 所有數值來自 bridge spec 或 SSOT datasheet，禁止 hardcode
        - 資料缺失時產生 warning，禁靜默跳過
        - 純 Python 規則，不呼叫 LLM

    """
    if not isinstance(bridge, dict):
        raise TypeError(f"bridge 必須是 dict，收到 {type(bridge).__name__}")

    issues: list[dict] = []
    issues.extend(_check_capability(bridge))
    issues.extend(_check_energy_runtime(bridge))
    issues.extend(_check_power_domain(bridge))
    issues.extend(
        check_missing_capabilities(
            bridge.get("_instruction", ""),
            bridge.get("components", []),
        )
    )
    return issues
