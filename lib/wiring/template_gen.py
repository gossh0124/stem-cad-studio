"""lib/wiring/template_gen.py — 從 datasheet JSON 自動衍生 WiringTemplate。

CAG Layer 1: 已驗證 datasheet → WiringTemplate（零 hallucination）。

流程：
  1. 讀取 data/component_datasheet_verified.json
  2. 對每個已知元件，根據 pin_layout + wiring_hints 衍生 WiringTemplate
  3. engine.py 優先使用本模組產出，舊 WIRING_TEMPLATES 作為 fallback
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .engine import WireExtra, WiringTemplate

_log = logging.getLogger(__name__)

# ── Datasheet key → WIRING_TEMPLATES short name ────────────────
_DS_TO_SHORT: dict[str, str] = {
    "Sensor-TempHumid-class": "TempHumid",
    "Sensor-Ultrasonic-class": "Ultrasonic",
    "Sensor-PIR-class": "PIR",
    "Sensor-IR-class": "IR",
    "Sensor-SoilMoisture-class": "SoilMoisture",
    "Sensor-Light-class": "Light",
    "Sensor-MSGEQ7-class": "MSGEQ7",
    "Lighting-NeoPixel-class": "NeoPixel",
    "Lighting-LED-PWM-class": "LED_Single",
    "Lighting-LED-RGB-class": "LED_RGB",
    "Motor-Servo-class": "Servo",
    "Motor-DC-class": "DCMotor",
    "Motor-Stepper-class": "Stepper",
    "Relay-Module-class": "Relay",
    "Pump-Water-class": "Pump",
    "Display-OLED-class": "OLED",
    "Display-LCD-class": "LCD",
    "Buzzer-Active-class": "Buzzer_Active",
    "Buzzer-Passive-class": "Buzzer_Passive",
    "MP3-Module-class": "Speaker",
    "Button-class": "Button",
    "Switch-class": "Switch",
}

# 反向映射：short name → datasheet key
_SHORT_TO_DS: dict[str, str] = {v: k for k, v in _DS_TO_SHORT.items()}

# A4-A: 供電件不是「接線耗電端」。它們的 PWR pin(voltage_domain=3V/5V)描述的是
# *輸出*電壓,若誤走 template_from_datasheet 會被當成 vcc 而生成耗電 template
# (把電源當被供電元件)。前端 _injectPower 才是電源接入的正確路徑。此處 fail-loud,
# 不靜默回傳錯誤 consumer template。
_POWER_SOURCE_CLASSES: frozenset[str] = frozenset({
    "Battery-AA-class", "Battery-LiPo-class", "USB-5V-class",
    "AC-Adapter-class", "USB-Adapter-class",
})

# Pin type → PinNeed type 映射
_PIN_TYPE_MAP: dict[str, str] = {
    "PWM": "pwm",
    "ANALOG": "analog",
    "I2C": "i2c",
    "SPI": "spi",
    "UART": "uart",
    "GPIO": "digital",
}

# Pin direction → 中文描述
_DIRECTION_NOTES: dict[str, str] = {
    "digital_in": "數位輸入",
    "digital_out": "數位輸出",
    "analog_in": "類比輸入",
    "analog_out": "類比輸出",
    "power": "電源",
    "gnd": "接地",
    "i2c_data": "I2C Data",
    "i2c_clock": "I2C Clock",
    "spi_mosi": "SPI MOSI",
    "spi_miso": "SPI MISO",
    "spi_sck": "SPI Clock",
    "spi_ss": "SPI Slave Select",
    "uart_tx": "UART TX",
    "uart_rx": "UART RX",
    "other": "",
}

# （CROSS_WIRING_RULES 已移除：dead-code，無呼叫點；跨元件接線邏輯實作於 WireExtra）

# ── Datasheet 快取 ──────────────────────────────────────────────
_datasheet_cache: dict | None = None

_DEFAULT_DS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "component_datasheet_verified.json"
)


def load_datasheet(path: str | Path | None = None) -> dict:
    """載入並快取 component_datasheet_verified.json。"""
    global _datasheet_cache  # noqa: PLW0603
    if _datasheet_cache is not None and path is None:
        return _datasheet_cache

    ds_path = Path(path) if path else _DEFAULT_DS_PATH
    if not ds_path.exists():
        _log.warning("Datasheet 不存在: %s", ds_path)
        return {}

    with open(ds_path, encoding="utf-8") as f:
        data = json.load(f)

    if path is None:
        _datasheet_cache = data
    return data


def _collect_pins(comp_data: dict) -> list[dict]:
    """從元件 datasheet 收集所有 pin（跨 header_groups 攤平）。"""
    pins: list[dict] = []
    layout = comp_data.get("pin_layout", {})
    for group in layout.get("header_groups", []):
        for pin in group.get("pins", []):
            pins.append(pin)
    return pins


def _find_passive(pin_name: str, hints: dict) -> dict | None:
    """從 wiring_hints.passives 中查找匹配 pin 的被動元件資訊。"""
    for p in hints.get("passives", []):
        if p.get("pin") == pin_name:
            return {"kind": p["kind"], "value": p["value"], "topo": p["topo"]}
    return None


def _resolve_vcc(pins: list[dict], hints: dict) -> str | None:
    """決定 VCC 電壓：wiring_hints.vcc 優先，否則從 PWR pin 推斷。"""
    # Rule 1a: hints override
    hint_vcc = hints.get("vcc")
    if hint_vcc:
        return hint_vcc

    # Rule 1b: 從 PWR pin 的 voltage_domain 推斷
    for pin in pins:
        if pin.get("type") == "PWR":
            vd = pin.get("voltage_domain", "")
            if vd in ("5V", "3V3", "3.3V"):
                return vd.replace("3V3", "3.3V")
    return None


def _note_from_direction(direction: str) -> str:
    """從 pin direction 生成描述文字。"""
    return _DIRECTION_NOTES.get(direction, "")


def template_from_datasheet(comp_key: str) -> WiringTemplate | None:
    """從 datasheet 自動衍生 WiringTemplate。

    Args:
        comp_key: 元件 short name（如 "TempHumid"）或 datasheet key
                  （如 "Sensor-TempHumid-class"）

    Returns:
        WiringTemplate 或 None（若 datasheet 中找不到該元件）

    轉換規則：
    1. pin.type == "PWR" + voltage_domain → vcc 欄位
       - 若 wiring_hints.vcc 存在 → 優先使用（override）
    2. pin.type == "GND" → 自動加（engine.py 處理）
    3. pin.type == "NC" → 跳過
    4. 其他 pin → WireExtra
    5. wiring_hints.decoupling → decoupling 欄位
    6. wiring_hints.cross_component → WireExtra with fixed 欄位
    """
    ds = load_datasheet()
    if not ds:
        return None

    # 解析 datasheet key
    ds_key = _SHORT_TO_DS.get(comp_key, comp_key)
    if ds_key not in ds:
        # 嘗試帶 -class 後綴
        if not ds_key.endswith("-class"):
            ds_key = f"{ds_key}-class"
        if ds_key not in ds:
            return None

    comp_data = ds[ds_key]
    # A4-A: power sources cannot be wired as consumers (their PWR pin is an OUTPUT).
    if ds_key in _POWER_SOURCE_CLASSES:
        raise ValueError(
            f"{ds_key} is a power source, not a wiring consumer — its PWR pin is an "
            "output; power must be injected via the frontend _injectPower path, not "
            "derived as a vcc consumer template")
    short_name = _DS_TO_SHORT.get(ds_key, comp_key)
    pins = _collect_pins(comp_data)

    if not pins:
        return None

    # wiring_hints 可能尚不存在（另一個 agent 正在並行添加）
    hints: dict = comp_data.get("wiring_hints", {})

    # 決定 VCC
    vcc = _resolve_vcc(pins, hints)

    # 決定 label
    identity = comp_data.get("identity", {})
    label = identity.get("full_name", short_name)

    # 決定 decoupling
    decoupling = hints.get("decoupling")

    # 建構 WireExtra 列表。PB3：套用與 pin_needs_from_datasheet 相同的 wiring_hints 欄位
    # (mcu_pins 白名單 / pin_aliases 改名),讓 wiring-template 與 pin-needs 兩條 derive
    # 路徑一致 → 多數 _COMP_OVERRIDES 不再需要(可退役)。
    extras: list[WireExtra] = []
    mcu_pins = hints.get("mcu_pins")
    aliases = hints.get("pin_aliases") or {}
    _SKIP_TYPES = {"GND", "PWR", "NC", "RELAY_CONTACT", "MOTOR", "USB", "AUDIO"}

    for pin in pins:
        pin_type = pin.get("type", "")
        pin_name = pin.get("name", "")
        direction = pin.get("direction", "")

        if mcu_pins is not None:
            if pin_name not in mcu_pins:
                continue
        elif pin_type in _SKIP_TYPES:
            continue

        note = _note_from_direction(direction)
        passive = _find_passive(pin_name, hints)   # passive keyed on the SSOT pin name
        tag = aliases.get(pin_name, pin_name)
        extras.append(WireExtra(
            comp=tag,
            tag=tag,
            note=note,
            passive=passive,
        ))

    # Rule 6: cross_component → 額外 WireExtra with fixed。
    # target_pin（如 Relay 的 "NO"）必須併入 fixed，否則只落在普通 "Relay" 網而非
    # "Relay.NO" contact net（netlist.py 以 "." 判定接點），galvanic-isolation post-pass
    # 不會觸發。SSOT 既已宣告 target_pin，這裡不得靜默丟棄（DEC-H7）。無 target_pin 者
    # （L298N→ExternalPower、Relay→EXT-PWR/LOAD+、MP3→Speaker）行為不變。
    for cross in hints.get("cross_component", []):
        _target = cross.get("target_comp", "EXT")
        _tpin = cross.get("target_pin")
        _fixed = f"{_target}.{_tpin}" if _tpin else _target
        for cpin in cross.get("pins", []):
            extras.append(WireExtra(
                comp=cpin,
                tag=None,
                note=cross.get("note", ""),
                color=cross.get("color", "#ff88cc"),
                fixed=_fixed,
            ))

    return WiringTemplate(
        label=label,
        vcc=vcc,
        extra=extras,
        decoupling=decoupling,
    )


# ── 元件專屬覆寫 ────────────────────────────────────────────────
# 某些元件的 datasheet pin_layout 描述的是「裸元件」而非驅動板，
# 需要用驅動板的腳位覆寫（如 DCMotor 實際接 L298N 驅動板）。
# 這些覆寫的語義：「datasheet 描述馬達本體，但接線是透過驅動板」。

_COMP_OVERRIDES: dict[str, dict[str, Any]] = {
    "DCMotor": {
        "label": "L298N 馬達驅動",
        "vcc": "5V",
        "extras": [
            WireExtra("ENA", "ENA", "PWM 速度控制"),
            WireExtra("IN1", "IN1", "方向控制 A1"),
            WireExtra("IN2", "IN2", "方向控制 A2"),
            WireExtra("+12V", None, "外部 12V 電源", "#ff2200", "EXT"),
            # C(#8): L298N 馬達輸出 → 馬達端子 M1/M2（負載側，比照 Relay COM/NO 用 fixed；
            # 用 M1/M2 避開 netlist _GROUND_RAILS 含 'M-' 的接地誤分類）
            WireExtra("OUT1", None, "馬達輸出 → 馬達端子 M1", "#ff6600", "M1"),
            WireExtra("OUT2", None, "馬達輸出 → 馬達端子 M2", "#ff6600", "M2"),
        ],
    },
    "Stepper": {
        "label": "28BYJ-48 步進馬達 + ULN2003 驅動板",
        "vcc": "5V",
        "extras": [
            WireExtra("IN1", "IN1", "線圈 A1"),
            WireExtra("IN2", "IN2", "線圈 A2"),
            WireExtra("IN3", "IN3", "線圈 B1"),
            WireExtra("IN4", "IN4", "線圈 B2"),
        ],
    },
    "Pump": {
        "label": "微型水泵（透過繼電器控制）",
        "vcc": None,
        "extras": [
            WireExtra("VCC", None, "由 Relay NO 切換供電（外接電源接 COM）", "#ff8800", "Relay.NO"),
        ],
    },
    "Speaker": {
        "label": "DFPlayer Mini 音樂模組",
        "vcc": "5V",
        "extras": [
            WireExtra("TX", "TX", "SoftwareSerial TX（1kΩ 串聯）",
                      passive={"kind": "R", "value": "1kΩ", "topo": "series"}),
            WireExtra("RX", "RX", "SoftwareSerial RX"),
            WireExtra("SPK+", None, "接 8Ω 喇叭正極", "#ff88cc", "SPK"),
            WireExtra("SPK-", None, "接 8Ω 喇叭負極", "#888888", "SPK-"),
        ],
        "decoupling": "100nF",
    },
    "LED_Single": {
        "label": "單色 LED 指示燈",
        "vcc": None,
        # LED 的 datasheet pin 名是 Anode，但 COMP_PIN_NEEDS 用 "+"
        "extras": [
            WireExtra("+", "+", "長腳，串聯 220Ω 電阻",
                      passive={"kind": "R", "value": "220Ω", "topo": "series"}),
        ],
    },
    "Button": {
        "label": "微動按鈕（含上拉）",
        "vcc": None,
        # datasheet 有 A1/A2/B1/B2 物理 pin，實際只用一對做開關 → 邏輯 SIG
        "extras": [
            WireExtra("SIG", "SIG", "INPUT_PULLUP（按下=LOW）"),
        ],
    },
    "Switch": {
        "label": "撥動開關",
        "vcc": None,
        "extras": [
            WireExtra("SIG", "SIG", "INPUT_PULLUP（ON=LOW）"),
        ],
    },
    "LED_RGB": {
        "label": "RGB LED (4-pin)",
        "vcc": None,
        "extras": [
            WireExtra("R", "R", "PWM，串聯 220Ω",
                      passive={"kind": "R", "value": "220Ω", "topo": "series"}),
            WireExtra("G", "G", "PWM，串聯 220Ω",
                      passive={"kind": "R", "value": "220Ω", "topo": "series"}),
            WireExtra("B", "B", "PWM，串聯 220Ω",
                      passive={"kind": "R", "value": "220Ω", "topo": "series"}),
        ],
    },
    "Light": {
        "label": "LDR 光敏電阻",
        "vcc": "5V",
        # datasheet 模組有 AOUT/DOUT，但接線只用一個類比 → 邏輯 pin "LDR"
        "extras": [
            WireExtra("LDR", "LDR", "10kΩ 分壓",
                      passive={"kind": "R", "value": "10kΩ", "topo": "divider"}),
        ],
    },
    "Servo": {
        "label": "SG90 伺服馬達",
        "vcc": "5V",
        # datasheet pin name "SIGNAL" → COMP_PIN_NEEDS 用 "SIG"
        "extras": [
            WireExtra("SIG", "SIG", "PWM 控制腳（50Hz）"),
        ],
    },
    "SoilMoisture": {
        "label": "土壤濕度感測器",
        "vcc": "5V",
        # datasheet pin name "AOUT" → COMP_PIN_NEEDS 用 "AO"
        "extras": [
            WireExtra("AO", "AO", "類比輸出（0–1023）"),
        ],
        "decoupling": "100nF",
    },
    "MSGEQ7": {
        "label": "MSGEQ7 音頻頻譜分析器",
        "vcc": "5V",
        # datasheet 有完整 IC pin (IN/CKIN/CKOUT/...)，實際只接 3 控制線
        "extras": [
            WireExtra("OUT", "OUT", "類比輸出（7 頻段）"),
            WireExtra("STROBE", "STROBE", "頻段選擇觸發"),
            WireExtra("RESET", "RESET", "重置序列"),
        ],
        "decoupling": "100nF",
    },
    "Relay": {
        "label": "5V 單路繼電器",
        "vcc": "5V",
        # A4-B: 觸點負載側必須完整呈現切換迴路。控制側 IN(LOW 觸發)+ 線圈電源(VCC/GND
        # engine 自動加);觸點側 COM(公共,接外部電源)+ NO(常開,接負載) → 外部供電
        # 經 COM→NO→負載 形成迴路。NC(常閉)此模組預設不接。flyback D1 已板載(on_board
        # D1=1N4007),勿外加。
        "extras": [
            WireExtra("IN", "IN", "LOW 觸發"),
            WireExtra("COM", None, "公共接點 ← 外部電源", "#ff8800", "EXT-PWR"),
            WireExtra("NO", None, "常開接點 → 負載", "#ff6600", "LOAD+"),
        ],
        "decoupling": "100nF",
    },
}

# PB3: these 8 overrides are now FULLY derived from verified.json (template_from_datasheet
# honours mcu_pins + pin_aliases, and the fabricated LDR divider was removed from SSOT) —
# proven equivalent and retired. The literals above are kept as documented reference but
# are inactive at runtime (popped here). tests/test_wiring_overrides_retired.py guards that
# get_template output is unchanged for these. Genuine remaining exceptions: DCMotor (L298N
# driver indirection), Pump (Relay.NO switched-output target), Speaker (SoftwareSerial + SPK),
# Button/Switch (mechanical contacts → logical SIG), Relay (COM/NO load side semantics).
for _retired in ("Stepper", "LED_Single", "LED_RGB", "Light", "Servo", "SoilMoisture",
                 "MSGEQ7", "Relay"):  # Relay: COM/NO load side moved to SSOT cross_component (PB3)
    _COMP_OVERRIDES.pop(_retired, None)
del _retired


def _apply_override(short_name: str, tmpl: WiringTemplate | None) -> WiringTemplate | None:
    """若元件有專屬覆寫，套用之；否則返回原始 template。"""
    override = _COMP_OVERRIDES.get(short_name)
    if not override:
        return tmpl

    return WiringTemplate(
        label=override.get("label", tmpl.label if tmpl else short_name),
        vcc=override.get("vcc", tmpl.vcc if tmpl else None),
        extra=override.get("extras", tmpl.extra if tmpl else []),
        decoupling=override.get("decoupling", tmpl.decoupling if tmpl else None),
    )


def generate_all_templates() -> dict[str, WiringTemplate]:
    """批次生成所有已知元件的 WiringTemplate。

    Returns:
        short_name → WiringTemplate 的映射 dict
    """
    ds = load_datasheet()
    if not ds:
        _log.warning("無法載入 datasheet，generate_all_templates 回傳空 dict")
        return {}

    result: dict[str, WiringTemplate] = {}
    for ds_key, short_name in _DS_TO_SHORT.items():
        if ds_key not in ds:
            _log.debug("Datasheet 中找不到 %s，跳過", ds_key)
            continue

        tmpl = template_from_datasheet(short_name)
        tmpl = _apply_override(short_name, tmpl)
        if tmpl:
            result[short_name] = tmpl

    return result


def get_template(comp_key: str) -> WiringTemplate | None:
    """取得單一元件的 WiringTemplate（含 override）。

    這是 engine.py 整合用的主要入口。
    三層架構：Layer 1 (CAG) → Layer 2 (RAG) → None (待 Layer 3)。

    Args:
        comp_key: 元件 short name（如 "TempHumid"）

    Returns:
        WiringTemplate 或 None
    """
    # Layer 1: CAG — datasheet 直接衍生
    tmpl = template_from_datasheet(comp_key)
    tmpl = _apply_override(comp_key, tmpl)
    if tmpl:
        return tmpl

    # Layer 2: RAG — 語義搜尋最相似元件的 pin pattern。
    # RAG 是選用層：模組本身或其選用依賴(lancedb 等向量後端)缺席時屬「預期降級」，
    # 應靜默 fall-through 回 None(unknown→None 契約)。RAG 的延遲 import 發生在 call 時,
    # 故 ImportError/ModuleNotFoundError 需涵蓋 import 與 infer_template() 執行兩階段。
    # 注意:此處只吞 (Module)ImportError——其餘真實邏輯錯誤仍向上拋,不靜默掩蓋。
    try:
        from ..rag.rag_wiring import infer_template
        tmpl = infer_template(comp_key)
    except ImportError as exc:
        _log.debug("RAG wiring unavailable for %s (optional dep missing): %s", comp_key, exc)
    else:
        if tmpl:
            _log.info("template[%s] source=rag_inferred", comp_key)
            return tmpl

    return None
