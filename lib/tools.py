"""tools.py — Phase I 工具集。

Public API（module-level functions）：
  generate_aux_logic, validate_category, format_prompt, extract_output, extract_json

TAXONOMY_CONFIG 的唯一事實來源是 lib/config.py。
AdvancedValidator 的唯一事實來源是 lib/validator.py。
本模組 re-export 兩者，所有呼叫方只需 from tools import ...。
"""
import json
import re
from typing import Dict, Any, List, Tuple, Optional

try:
    import json_repair as _json_repair
except ImportError:
    _json_repair = None

# ── Single Source of Truth：從 config.py import ────────────
from .config import TAXONOMY_CONFIG, _COMPLEX_EFFECT_TEMPLATES, EDUCATIONAL_RATIONALE_TEMPLATES

# ── AdvancedValidator 唯一來源：validator.py ────────────
from .validator import AdvancedValidator  # noqa: F401 (re-exported)

# ── tools.py 內部使用的視圖：對映到 config.py 的鍵名 ────────
_LEGAL_CATS: List[str]         = TAXONOMY_CONFIG["project_categories"]
_CORE_ROLES: Dict[str, list]   = {
    r: TAXONOMY_CONFIG["component_taxonomy"][r]
    for r in ("Brain", "Power", "Control")
    if r in TAXONOMY_CONFIG["component_taxonomy"]
}
_AUX_ROLES: Dict[str, list]    = {
    r: TAXONOMY_CONFIG["component_taxonomy"][r]
    for r in TAXONOMY_CONFIG["component_taxonomy"]
    if r not in ("Brain", "Power", "Control")
}


# ── Module-level functions（原 LogicHelpers / PromptManager / OutputParser）──


def generate_aux_logic(proj_name: str, instruction: str) -> Tuple[list, bool]:
    """Rule-based auxiliary role 推斷。涵蓋 Sound/Display + Sensor/Actuator。"""
    aux = []
    has_sound = False
    text = (proj_name + " " + instruction).lower()

    if any(k in text for k in ["語音", "說話", "speak", "speaker", "voice", "音樂",
                                "music", "mp3", "song", "播放", "audio", "melody"]):
        has_sound = True
        aux.append({"role": "Sound", "tags": ["output", "audio"], "recommended_types": ["Speaker-class"]})
    elif any(k in text for k in ["警報", "鈴", "alarm", "sound", "發聲", "發出聲音", "蜂鳴", "buzzer"]):
        has_sound = True
        aux.append({"role": "Sound", "tags": ["output", "audio"], "recommended_types": ["Buzzer-Active-class"]})

    if any(k in text for k in ["顯示", "螢幕", "monitor", "oled", "lcd", "畫面"]):
        aux.append({"role": "Display", "tags": ["visual"], "recommended_types": ["Display-OLED-class"]})

    if any(k in text for k in ["澆水", "澆花", "灌溉", "soil", "水分", "植物", "盆栽"]):
        aux.append({"role": "Sensor", "tags": ["input", "environment"],
                    "recommended_types": ["Sensor-SoilMoisture-class"]})

    if any(k in text for k in ["澆水", "澆花", "灌溉", "水泵", "pump", "抽水"]):
        aux.append({"role": "Actuator", "tags": ["output", "liquid"],
                    "recommended_types": ["Pump-Water-class"]})

    if any(k in text for k in ["避障", "距離", "測距", "ultrasonic", "超音波",
                                "obstacle avoidance", "obstacle", "collision", "distance sensor"]):
        aux.append({"role": "Sensor", "tags": ["input", "distance"],
                    "recommended_types": ["Sensor-Ultrasonic-class"]})

    if any(k in text for k in ["機器人", "車", "移動", "馬達", "motor", "輪子", "避障",
                                "robot car", "rc car", "remote control car", "drive", "wheels"]):
        aux.append({"role": "Actuator", "tags": ["output", "motion"],
                    "recommended_types": ["Motor-DC-class"]})

    if any(k in text for k in ["溫度", "濕度", "天氣", "temp", "humid", "氣象"]):
        aux.append({"role": "Sensor", "tags": ["input", "environment"],
                    "recommended_types": ["Sensor-TempHumid-class"]})

    _LIGHT_SENSOR_KW = [
        "光感", "亮度偵測", "照度", "光敏", "ambient light",
        "light sensor", "測光", "日夜偵測", "bh1750", "ldr", "photoresist",
        "adjusts brightness", "based on light",
    ]
    _LIGHTING_KW     = ["燈光", "led", "燈條", "neopixel", "rgb", "彩燈",
                        "light effect", "燈效", "照明", "燈珠", "lighting"]
    _text_lower = text
    if any(k in _text_lower for k in _LIGHT_SENSOR_KW) and not any(k in _text_lower for k in _LIGHTING_KW):
        aux.append({"role": "Sensor", "tags": ["input", "environment"],
                    "recommended_types": ["Sensor-Light-class"]})

    _SIMPLE_LIGHT_KW  = ["night light", "夜燈", "小夜燈", "night lamp", "glow",
                          "adjusts brightness", "dim", "調光", "亮度調節"]
    _STRIP_KW         = ["led strip", "neopixel", "燈條", "rgb strip"]
    if any(k in _text_lower for k in _SIMPLE_LIGHT_KW) and not any(k in _text_lower for k in _STRIP_KW):
        if not any(c.get("role") == "Lighting" for c in aux):
            aux.append({"role": "Lighting", "tags": ["output", "light"],
                        "recommended_types": ["Lighting-LED-PWM-class"]})

    _WEARABLE_LIGHT_KW = ["bowtie", "bow tie", "wearable led", "glowing", "reactive light",
                           "clap light", "clap activated", "clap-reactive"]
    if any(k in _text_lower for k in _WEARABLE_LIGHT_KW):
        if not any(c.get("role") == "Lighting" for c in aux):
            aux.append({"role": "Lighting", "tags": ["output", "light"],
                        "recommended_types": ["Lighting-LED-RGB-class"]})

    if any(k in text for k in ["人體", "移動偵測", "pir", "防盜", "入侵", "感應",
                                "motion", "detect", "someone", "presence", "nearby",
                                "intruder", "burglar", "security alert", "motion sensor"]):
        aux.append({"role": "Sensor", "tags": ["input", "motion"],
                    "recommended_types": ["Sensor-PIR-class"]})

    if any(k in text for k in ["伺服", "servo", "機械臂", "轉向", "舎機"]):
        aux.append({"role": "Actuator", "tags": ["output", "motion"],
                    "recommended_types": ["Motor-Servo-class"]})

    if any(k in text for k in ["繼電器", "relay", "高壓", "交流"]):
        aux.append({"role": "Actuator", "tags": ["output", "switch"],
                    "recommended_types": ["Relay-Module-class"]})

    return aux, has_sound


def validate_category(raw: str) -> str:
    """將非法 category 字串映射至最接近的合法值（模糊比對）。"""
    raw_lower = raw.lower().replace(" ", "_")
    for cat in _LEGAL_CATS:
        if cat.lower() in raw_lower or raw_lower in cat.lower():
            return cat
    return "Education"


# Phase I system prompt: lazy-loaded from training/prompts.py to avoid
# cross-layer import at module level (lib/ should not import training/).
_PHASE1_SYSTEM_MSG: str | None = None


def _get_phase1_system_msg() -> str:
    """Lazy-load SYS_PHASE1 from training.prompts on first use."""
    global _PHASE1_SYSTEM_MSG
    if _PHASE1_SYSTEM_MSG is None:
        try:
            from training.prompts import SYS_PHASE1
            _PHASE1_SYSTEM_MSG = SYS_PHASE1
        except ImportError:
            raise ImportError(
                "Cannot import training.prompts.SYS_PHASE1. "
                "Ensure the training/ package is on sys.path or "
                "run from the project root."
            )
    return _PHASE1_SYSTEM_MSG


def build_llama31_chat_prompt(system: str, user: str) -> str:
    """Llama 3.1 Instruct chat template — runtime inference 端 SSOT。

    訓練端 (training/trainer.py / data_generator.py) **不** import 此函式；
    訓練用同樣字串建 jsonl 後 byte-level 鎖在 prompt_alignment_check 內，
    runtime 推理端則統一從這裡取，避免日後 template 微調出現多源 drift。
    """
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{system}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{user}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def format_prompt(instruction: str, rag_context: str = "") -> str:
    """將使用者輸入轉為 Phase I LLM 的 Llama 3.1 chat template prompt。

    Parameters
    ----------
    instruction : str
        使用者自然語言需求
    rag_context : str
        RAG 檢索結果（注入 system prompt 尾部，不改變訓練格式核心）
    """
    system_msg = _get_phase1_system_msg()
    if rag_context:
        system_msg = system_msg + "\n" + rag_context + "\n"
    return build_llama31_chat_prompt(system_msg, instruction)


def extract_output(text: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
    """從 LLM 原始輸出提取 JSON（strict → json_repair fallback）。"""
    if not text:
        return None, "failed", "Empty text"
    clean_text = re.sub(r'```json\s*', '', text)
    clean_text = re.sub(r'```', '', clean_text).strip()
    match = re.search(r'\{.*\}', clean_text, re.DOTALL)
    if match:
        clean_text = match.group(0)
    try:
        return json.loads(clean_text), "strict", None
    except json.JSONDecodeError:
        pass
    if _json_repair is not None:
        try:
            obj = _json_repair.repair_json(clean_text, return_objects=True)
            if isinstance(obj, list):
                obj = obj[0]
            return obj, "repaired", "Used json_repair"
        except Exception as e:
            return None, "failed", str(e)
    return None, "failed", "json_repair not available"


def extract_json(text: str) -> Optional[dict]:
    """括號平衡演算法提取第一個完整 JSON 物件。"""
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
    obj, _, _ = extract_output(text)
    return obj

