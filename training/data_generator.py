"""data_generator.py — Phase I 訓練資料生成（inference + annotation 框架）。

產出格式：HuggingFace Dataset（prompt / completion）。
Scope：室內 / 桌面 / 純電子或單軸簡單機構（M1）。
"""
import json
import random
from typing import Dict, Any, List, Tuple
from collections import Counter

from config import TAXONOMY_CONFIG, MODEL_CONFIG, EDUCATIONAL_RATIONALE
try:
    from datasets import Dataset
except ImportError:
    Dataset = None  # type: ignore[assignment,misc]

# ── Scope filter（M1）────────────────────────────────────
_SCOPE_BLOCKLIST_KEYWORDS = (
    "戶外", "室外", "防水", "IP6", "IP54", "IP65", "IP67",
    "機械臂", "多軸", "六軸", "三軸", "雙軸",
    "LoRa 戶外", "太陽能板", "戶外監測",
)

_MULTIAXIS_TYPES = {"Motor-Servo-class", "Motor-Stepper-class"}


def _is_in_scope(description: str, aux_components: List[Dict]) -> bool:
    """判定是否在當前 scope 內（M1：無黑名單詞 + 多軸元件 <= 1）。"""
    desc_lower = description.lower() if description else ""
    for kw in _SCOPE_BLOCKLIST_KEYWORDS:
        if kw.lower() in desc_lower:
            return False
    multiaxis_count = sum(1 for c in aux_components
                          if c.get("type") in _MULTIAXIS_TYPES)
    return multiaxis_count <= 1

_LEGAL_CATS: List[str]       = TAXONOMY_CONFIG["project_categories"]
_tax = TAXONOMY_CONFIG["component_taxonomy"]
_CORE_ROLES: Dict[str, list] = {r: _tax[r] for r in ("Brain", "Power", "Control")}
_AUX_ROLES: Dict[str, list] = {r: _tax[r] for r in _tax if r not in ("Brain", "Power", "Control")}

# ── Prompt 模板 ──────────────────────────────────────────
PROMPT_TEMPLATES_ZH = [
    "我想做一個{project_name}。{description}。",
    "請幫我設計{project_name}，類型是{category}。{description}。"
    "需要用{brain}控制，{power}供電。有{sensors}感測，{actuators}輸出。{enclosure_style}外殼。",
    "幫我規劃一個 STEM 專題：{project_name}（{category}）。{description}。"
    "硬體：{brain}、{power}、{sensors}、{actuators}。機構：{enclosure_style}。",
    "設計一個{category}作品「{project_name}」。{description}。",
    "用{brain}當主控，{power}供電。感測器：{sensors}。致動器：{actuators}。{enclosure_style}尺寸。",
]

PROMPT_TEMPLATES_EN = [
    "Design a {project_name}. Category: {category}. Description: {description}. "
    "Brain: {brain}. Power: {power}. Sensors: {sensors}. Actuators: {actuators}. "
    "Enclosure: {enclosure_style}.",
    "Build a {category} project: {project_name}. {description}. Use {brain} as MCU, "
    "powered by {power}. Include {sensors}. Output via {actuators}. {enclosure_style} form factor.",
    "I want to make a {project_name}. It's a {category} project. {description}. "
    "Should use {brain} with {power}. Has {sensors} for sensing and {actuators} for action. "
    "Make it {enclosure_style}.",
]

# ── 模糊 prompt 模板（學生只描述想法，不指定元件）───────────
PROMPT_TEMPLATES_VAGUE_ZH = [
    "我想做一個{project_name}。{description}。",
    "幫我設計「{project_name}」。{description}。",
    "做一個{description}的裝置。",
]
PROMPT_TEMPLATES_VAGUE_EN = [
    "I want to build a {project_name}. {description}.",
    "Help me design a device that {description}.",
]

# ── 專案描述 → 隱含能力映射 (role, type, inferred_reason) ───
_I = "inferred: "  # DRY prefix
_IMPLICIT_CAPABILITY_MAP: Dict[str, List[Tuple[str, str, str]]] = {
    "smart_night_light":   [("Sensor", "Sensor-Light-class", _I+"需光感測"),
                            ("Lighting", "Lighting-LED-PWM-class", _I+"需 PWM LED")],
    "auto_curtain":        [("Sensor", "Sensor-Light-class", _I+"需偵測光線"),
                            ("Actuator", "Motor-Stepper-class", _I+"滑軌需步進馬達")],
    "voice_doorbell":      [("Sensor", "Sensor-PIR-class", _I+"需 PIR"),
                            ("Sound", "MP3-Module-class", _I+"需 MP3")],
    "air_quality_monitor": [("Sensor", "Sensor-TempHumid-class", _I+"需溫濕度"),
                            ("Display", "Display-OLED-class", _I+"需顯示數值")],
    "auto_pet_feeder":     [("Actuator", "Motor-Servo-class", _I+"閘門需伺服馬達")],
    "smart_trash_can":     [("Sensor", "Sensor-Ultrasonic-class", _I+"需測距開蓋"),
                            ("Actuator", "Motor-Servo-class", _I+"開蓋需伺服馬達")],
    "obstacle_avoiding_bot": [("Sensor", "Sensor-Ultrasonic-class", _I+"避障需超音波"),
                              ("Actuator", "Motor-DC-class", _I+"驅動需 DC 馬達")],
    "remote_car":          [("Actuator", "Motor-DC-class", _I+"需直流馬達")],
    "line_follower":  [("Sensor", "Sensor-IR-class", _I+"循線需 IR"),
                       ("Actuator", "Motor-DC-class", _I+"驅動需 DC 馬達")],
    "wobble_bot":     [("Actuator", "Motor-Servo-class", _I+"搖擺需伺服馬達")],
    "drink_dispenser": [("Actuator", "Pump-Water-class", _I+"需水泵"),
                        ("Display", "Display-OLED-class", _I+"顯示菜單")],
    "fan_controller": [("Sensor", "Sensor-TempHumid-class", _I+"感測溫度"),
                       ("Actuator", "Motor-Servo-class", _I+"擺頭需伺服馬達")],
    "floor_sweeper":  [("Sensor", "Sensor-Ultrasonic-class", _I+"避障需超音波"),
                       ("Actuator", "Motor-DC-class", _I+"清掃需 DC 馬達")],
    "ball_launcher":  [("Actuator", "Motor-Servo-class", _I+"發射角度需伺服馬達")],
    "music_box":      [("Sound", "MP3-Module-class", _I+"需 MP3 播放旋律")],
    "light_saber":    [("Lighting", "Lighting-NeoPixel-class", _I+"需 NeoPixel"),
                       ("Sound", "Buzzer-Passive-class", _I+"需音效")],
    "burglar_alarm":  [("Sensor", "Sensor-PIR-class", _I+"需 PIR"),
                       ("Sound", "Buzzer-Active-class", _I+"需蜂鳴器")],
    "perimeter_alarm": [("Sensor", "Sensor-PIR-class", _I+"需 PIR"),
                        ("Sound", "Buzzer-Active-class", _I+"需蜂鳴器"),
                        ("Lighting", "Lighting-LED-RGB-class", _I+"需 LED 警示")],
    "safe_box":       [("Actuator", "Motor-Servo-class", _I+"解鎖需伺服馬達"),
                       ("Sound", "Buzzer-Active-class", _I+"需蜂鳴器")],
    "distance_alarm": [("Sensor", "Sensor-Ultrasonic-class", _I+"需超音波"),
                       ("Sound", "Buzzer-Active-class", _I+"需蜂鳴器"),
                       ("Lighting", "Lighting-LED-RGB-class", _I+"需 RGB 指示")],
    "beam_break":     [("Sensor", "Sensor-IR-class", _I+"光柵需 IR"),
                       ("Sound", "Buzzer-Active-class", _I+"需蜂鳴器")],
    "warning_flasher": [("Sensor", "Sensor-PIR-class", _I+"需 PIR"),
                        ("Lighting", "Lighting-NeoPixel-class", _I+"需 NeoPixel")],
    "auto_plant_waterer":    [("Sensor", "Sensor-SoilMoisture-class", _I+"需土壤感測"),
                              ("Actuator", "Pump-Water-class", _I+"需水泵")],
    "greenhouse_controller": [("Sensor", "Sensor-TempHumid-class", _I+"需溫濕度"),
                              ("Display", "Display-OLED-class", _I+"需顯示數據")],
    "plant_monitor":   [("Sensor", "Sensor-Light-class", _I+"需光照感測"),
                        ("Sensor", "Sensor-SoilMoisture-class", _I+"需土壤感測")],
    "germination_box": [("Sensor", "Sensor-TempHumid-class", _I+"需溫濕度"),
                        ("Lighting", "Lighting-LED-PWM-class", _I+"補光需 PWM LED")],
    "auto_fertilizer": [("Sensor", "Sensor-SoilMoisture-class", _I+"需土壤感測"),
                        ("Actuator", "Pump-Water-class", _I+"施肥需水泵")],
    "hydro_pump":      [("Sensor", "Sensor-TempHumid-class", _I+"需溫度監測"),
                        ("Actuator", "Pump-Water-class", _I+"循環需水泵")],
    "morse_code":      [("Sound", "Buzzer-Passive-class", _I+"需蜂鳴器"),
                        ("Lighting", "Lighting-LED-RGB-class", _I+"需 LED 閃爍")],
    "distance_meter":  [("Sensor", "Sensor-Ultrasonic-class", _I+"需超音波"),
                        ("Display", "Display-OLED-class", _I+"需顯示數值")],
    "color_mixer":     [("Lighting", "Lighting-LED-RGB-class", _I+"混色需 RGB LED")],
}

# ── 每個 category 的合理輔助元件池 ────────────────────────
_CATEGORY_AUX_POOL: Dict[str, List[Tuple[str, List[str]]]] = {
    "Smart_Home": [
        ("Sensor",   ["Sensor-PIR-class", "Sensor-TempHumid-class", "Sensor-Light-class", "Sensor-Ultrasonic-class", "Sensor-IR-class"]),
        ("Display",  ["Display-OLED-class", "Display-LCD-class", "Display-EInk-class"]),
        ("Actuator", ["Relay-Module-class", "Motor-Servo-class", "Motor-Stepper-class"]),
        ("Sound",    ["Buzzer-Active-class", "Buzzer-Passive-class", "Speaker-class", "MP3-Module-class"]),
        ("Lighting", ["Lighting-NeoPixel-class", "Lighting-LED-Strip-class", "Lighting-LED-PWM-class"]),
        ("Mist",     ["Mist-Ultrasonic-class", "Mist-Atomizer-class"]),
    ],
    "Robotics": [
        ("Sensor",   ["Sensor-Ultrasonic-class", "Sensor-PIR-class", "Sensor-IR-class", "Sensor-Light-class"]),
        ("Actuator", ["Motor-DC-class", "Motor-Servo-class", "Motor-Stepper-class"]),
        ("Display",  ["Display-OLED-class", "Display-LCD-class"]),
        ("Sound",    ["Buzzer-Active-class", "MP3-Module-class", "Speaker-class"]),
        ("Lighting", ["Lighting-LED-RGB-class"]),
        ("Chassis",  ["Chassis-Car-class"]),
    ],
    "Interactive_Art": [
        ("Sound",    ["Speaker-class", "Buzzer-Passive-class", "Buzzer-Active-class", "MP3-Module-class"]),
        ("Actuator", ["Motor-Servo-class", "Motor-Stepper-class"]),
        ("Lighting", ["Lighting-NeoPixel-class", "Lighting-LED-RGB-class", "Lighting-LED-Strip-class", "Lighting-LED-PWM-class"]),
        ("Display",  ["Display-OLED-class", "LED-Matrix-class"]),
        ("Sensor",   ["Sensor-MSGEQ7-class", "Sensor-PIR-class", "Sensor-Ultrasonic-class"]),
        ("Mist",     ["Mist-Ultrasonic-class", "Mist-Atomizer-class"]),
    ],
    "Gardening": [
        ("Sensor",   ["Sensor-SoilMoisture-class", "Sensor-TempHumid-class", "Sensor-Light-class"]),
        ("Actuator", ["Pump-Water-class", "Relay-Module-class"]),
        ("Display",  ["Display-OLED-class", "Display-LCD-class", "Display-EInk-class"]),
        ("Sound",    ["Buzzer-Active-class"]),
        ("Lighting", ["Lighting-LED-RGB-class"]),
    ],
    "Security": [
        ("Sensor",   ["Sensor-PIR-class", "Sensor-Ultrasonic-class", "Sensor-IR-class"]),
        ("Actuator", ["Relay-Module-class", "Motor-Servo-class"]),
        ("Sound",    ["Buzzer-Active-class", "Buzzer-Passive-class", "Speaker-class"]),
        ("Lighting", ["Lighting-LED-RGB-class", "Lighting-NeoPixel-class"]),
        ("Display",  ["Display-OLED-class", "Display-LCD-class"]),
    ],
    "Education": [
        ("Sensor",   ["Sensor-Ultrasonic-class", "Sensor-TempHumid-class", "Sensor-Light-class", "Sensor-PIR-class", "Sensor-SoilMoisture-class", "Sensor-IR-class"]),
        ("Display",  ["Display-OLED-class", "Display-LCD-class", "LED-Matrix-class"]),
        ("Sound",    ["Buzzer-Passive-class", "Buzzer-Active-class", "Speaker-class", "MP3-Module-class"]),
        ("Actuator", ["Motor-Servo-class", "Motor-DC-class", "Motor-Stepper-class"]),
        ("Lighting", ["Lighting-NeoPixel-class", "Lighting-LED-RGB-class"]),
        ("Mist",     ["Mist-Atomizer-class"]),
    ],
}

# ── 專案描述模板 ─────────────────────────────────────────
_PROJECT_DESCRIPTIONS: Dict[str, List[Tuple[str, str, str]]] = {
    "Smart_Home": [
        ("智慧小夜燈",     "smart_night_light",    "設計一個根據環境光線自動調節亮度的小夜燈"),
        ("自動窗簾控制器", "auto_curtain",          "設計一個根據光線和時間自動開關的電動窗簾"),
        ("語音門鈴",       "voice_doorbell",        "製作一個偵測訪客並播放自訂音樂的智慧門鈴"),
        ("室內空氣品質站", "air_quality_monitor",   "打造一個顯示溫濕度的壁掛式環境監測站"),
        ("自動寵物餵食器", "auto_pet_feeder",       "設計一個伺服馬達控制閘門定時釋放飼料的餵食裝置"),
        ("智慧垃圾桶",     "smart_trash_can",       "打造一個偵測人靠近就自動開蓋的垃圾桶"),
        ("電動窗簾馬達",   "motorized_curtain",     "設計一個步進馬達驅動滑軌精準開合窗簾的控制器"),
    ],
    "Robotics": [
        ("避障小車",       "obstacle_avoiding_bot", "設計一個用超音波偵測障礙物並自動迴避的雙輪機器人"),
        ("遙控車",         "remote_car",            "打造一個無線遙控的雙輪驅動小車"),
        ("循線機器人",     "line_follower",         "設計一個沿黑線行走的教學機器人"),
        ("搖擺機器人",     "wobble_bot",            "設計一個伺服馬達驅動的左右搖擺機器人"),
        ("自動飲料機",     "drink_dispenser",       "製作一個按鈕選擇並用泵浦出飲料的桌上型裝置"),
        ("搖頭風扇控制器", "fan_controller",        "設計一個感測溫度自動擺頭的桌上風扇控制器"),
        ("掃地機器人",     "floor_sweeper",         "打造一個超音波避障的單軸清掃機器人"),
        ("投球機",         "ball_launcher",         "設計一個伺服馬達控制發射角度的桌上投球裝置"),
    ],  # 2026-05-08 移除「機械臂控制器」「雲台攝影機座」（多軸 scope 外）
    "Interactive_Art": [
        ("互動音樂盒",     "music_box",             "製作一個打開蓋子就播放旋律的互動音樂盒"),
        ("光劍",           "light_saber",           "設計一個帶有音效和 RGB 燈效的光劍道具"),
        ("電子琴",         "electronic_piano",      "打造一個觸控輸入的簡易電子琴"),
        ("距離感應樂器",   "theremin",              "設計一個用超音波距離控制音高的電子樂器"),
        ("揮手招財貓",     "lucky_cat",             "設計一個伺服馬達驅動手臂週期擺動的招財貓裝飾"),
        ("旋轉展示台",     "turntable",             "打造一個步進馬達精準控制旋轉角度的展示平台"),
    ],
    "Gardening": [
        ("室內自動澆花器", "auto_plant_waterer",    "製作一個偵測土壤濕度並自動澆水的室內智慧花盆"),
        ("溫室控制器",     "greenhouse_controller", "設計一個監測室內溫室溫濕度的環境控制器"),
        ("植物監測儀",     "plant_monitor",         "打造一個追蹤室內光照和土壤狀態的植物照護裝置"),
        ("自動遮陽板",     "auto_sunshade",         "設計一個光感測器驅動伺服馬達控制室內遮陽角度的裝置"),
        ("種子發芽箱",     "germination_box",       "設計一個監測溫濕度並控制補光的種子發芽培育箱"),
        ("自動施肥器",     "auto_fertilizer",       "製作一個土壤感測器驅動泵浦定量施肥的裝置"),
        ("水耕循環泵",     "hydro_pump",            "打造一個溫度感測控制水泵循環營養液的水耕裝置"),
    ],  # 2026-05-08 移除「自動灑水旋轉器」（戶外 scope 外）；其餘 description 加「室內」明確化
    "Security": [
        ("防盜警報器",     "burglar_alarm",         "設計一個偵測人體移動就發出警報的防盜裝置"),
        ("門禁系統",       "access_control",        "製作一個結合 PIR 感測和繼電器的門禁控制器"),
        ("周界警報",       "perimeter_alarm",       "打造一個偵測入侵並發出聲光警報的防護系統"),
        ("保險箱",         "safe_box",              "製作一個按鈕密碼解鎖伺服馬達開門的桌上保險箱"),
        ("距離警報器",     "distance_alarm",        "設計一個超音波偵測入侵距離並分級警報的裝置"),
        ("光柵感應器",     "beam_break",            "打造一個紅外線中斷觸發警報的通道感應器"),
        ("警示閃燈",       "warning_flasher",       "設計一個 PIR 偵測到人體就閃爍 LED 警示的裝置"),
    ],
    "Education": [
        ("反應力遊戲機",   "reaction_game",         "製作一個測試反應速度的 OLED 遊戲裝置"),
        ("程式教學車",     "coding_car",            "設計一個用來教授程式概念的雙輪機器人小車"),
        ("多感測器教學套件","sensor_kit",            "打造一個整合多種感測器的 STEM 教學裝置"),
        ("步進馬達教學台", "stepper_demo",          "製作一個按鈕控制單顆步進馬達正反轉並顯示步數的教學台"),
        ("摩斯密碼機",     "morse_code",            "製作一個按鈕輸入摩斯密碼並用蜂鳴器和 LED 輸出的教學裝置"),
        ("距離量測器",     "distance_meter",        "設計一個超音波量測距離並顯示在 OLED 的教學工具"),
        ("光混色實驗台",   "color_mixer",           "打造一個旋鈕控制 RGB LED 混色的光學教學裝置"),
    ],  # 2026-05-08 移除「旗號信號機」（雙 servo scope 外）
}


# SSOT: Phase I system prompt 唯一來源 → training/prompts.py
from prompts import SYS_PHASE1 as _SYSTEM_MSG_A


def _synth_rag_context_a(category: str, exclude_name: str = "") -> str:
    """生成模擬 RAG context（Phase I 格式），讓模型學會有 RAG 時的推論。"""
    descs = _PROJECT_DESCRIPTIONS.get(category, _PROJECT_DESCRIPTIONS["Education"])
    candidates = [d for d in descs if d[1] != exclude_name]
    if not candidates:
        return ""
    n = random.randint(1, min(2, len(candidates)))
    picked = random.sample(candidates, n)
    lines = ["[參考案例]"]
    for i, (zh, slug, desc) in enumerate(picked, 1):
        pool = _CATEGORY_AUX_POOL.get(category, _CATEGORY_AUX_POOL["Education"])
        aux_types = [random.choice(types) for _, types in random.sample(pool, min(2, len(pool)))]
        brain = random.choice(TAXONOMY_CONFIG["component_taxonomy"]["Brain"])
        comps = [brain] + aux_types
        lines.append(f"案例 {i}：{slug}（{category}）")
        lines.append(f"元件：{', '.join(comps)}")
        lines.append("---")
    return "\n".join(lines)


def _format_prompt(instruction: str, rag_context: str = "") -> str:
    """Llama 3.1 Instruct chat template。"""
    system_msg = _SYSTEM_MSG_A
    if rag_context:
        system_msg = system_msg + "\n" + rag_context + "\n"
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        f"{system_msg}<|eot_id|>"
        "<|start_header_id|>user<|end_header_id|>\n\n"
        f"{instruction}<|eot_id|>"
        "<|start_header_id|>assistant<|end_header_id|>\n\n"
    )


# ── 中文角色名映射 ───────────────────────────────────────
_ROLE_ZH = {
    "Brain": "主控板", "Power": "電源", "Control": "控制輸入",
    "Sensor": "感測器", "Actuator": "致動器", "Display": "顯示器",
    "Sound": "音效", "Lighting": "燈光", "Mist": "霧化",
}

# ── 元件參考值 (power_mw, pins) ──────────────────────────
_COMP_REF: Dict[str, Tuple[float, int]] = {
    "Arduino-Uno-class": (50, 0), "ESP32-class": (240, 0),
    "Microbit-class": (30, 0), "RaspberryPi-class": (600, 0),
    "USB-5V-class": (0, 0), "Battery-LiPo-class": (0, 0),
    "Battery-AA-class": (0, 0), "AC-Adapter-class": (0, 0), "USB-Adapter-class": (0, 0),
    "Button-class": (0, 1), "Switch-class": (0, 1), "Potentiometer-class": (1, 1),
    "Remote-class": (5, 1), "Joystick-class": (2, 2),
    "Sensor-PIR-class": (0.1, 1), "Sensor-Ultrasonic-class": (15, 2),
    "Sensor-TempHumid-class": (3, 1), "Sensor-Light-class": (1, 1),
    "Sensor-SoilMoisture-class": (5, 1), "Sensor-IR-class": (5, 1),
    "Motor-Servo-class": (200, 1), "Motor-DC-class": (300, 2),
    "Motor-Stepper-class": (240, 4), "Pump-Water-class": (220, 1),
    "Relay-Module-class": (80, 1),
    "Display-OLED-class": (20, 2), "Display-LCD-class": (25, 2),
    "Display-EInk-class": (15, 4), "LED-Matrix-class": (320, 2),
    "Buzzer-Active-class": (30, 1), "Buzzer-Passive-class": (25, 1),
    "MP3-Module-class": (200, 2), "Speaker-class": (200, 2),
    "Lighting-LED-RGB-class": (20, 1), "Lighting-LED-Strip-class": (200, 1),
    "Lighting-NeoPixel-class": (480, 1), "Lighting-LED-PWM-class": (20, 1),
    "Mist-Atomizer-class": (350, 1), "Mist-Ultrasonic-class": (500, 1),
    "Switch-Generic-class": (0, 1), "Chassis-Car-class": (0, 0),
    "Sensor-MSGEQ7-class": (3, 3),
}


class DataGenerator:
    """從 TAXONOMY_CONFIG 動態生成 Phase I 訓練資料（含中文 subsystems）。"""

    def __init__(self):
        tax = TAXONOMY_CONFIG["component_taxonomy"]
        self._brain_types   = tax["Brain"]
        self._power_types   = tax["Power"]
        self._control_types = tax["Control"]

    def _pick_aux_components(self, category: str) -> List[Dict[str, Any]]:
        pool = _CATEGORY_AUX_POOL.get(category, _CATEGORY_AUX_POOL["Education"])
        n_aux = random.randint(1, min(3, len(pool)))
        chosen = random.sample(pool, n_aux)
        return [{"role": role, "type": random.choice(types), "qty": 1}
                for role, types in chosen]

    def _build_subsystems(self, components: List[Dict]) -> List[Dict]:
        """從 components 生成中文 subsystems（Plan 表格用）。

        若 component 含 inferred_reason 欄位，reason 前綴會改為 inferred 標注，
        讓模型學會區分顯式需求 vs 推理補全。
        """
        subs = []
        for c in components:
            t = c["type"]
            role_zh = _ROLE_ZH.get(c["role"], c["role"])
            part_name = t.replace("-class", "").replace("-", " ")
            inferred = c.get("inferred_reason")
            if inferred:
                reason = inferred
            else:
                reason = EDUCATIONAL_RATIONALE.get(t, f"提供 {role_zh} 功能")
            pw, pins = _COMP_REF.get(t, (0, 0))
            subs.append({
                "role": role_zh, "part": part_name, "type": t,
                "reason": reason, "power_mw": pw, "pins": pins,
            })
        return subs

    def _build_cot_plan(self, category, zh_name, description, brain, power,
                        components, enc_size, wall_t):
        subsystems = self._build_subsystems(components)
        total_ma = sum(s["power_mw"] for s in subsystems)
        total_pins = sum(s["pins"] for s in subsystems)
        return {
            "high_level_plan": f"設計{enc_size}尺寸的{category}作品「{zh_name}」：{description}",
            "subsystems": subsystems,
            "parameter_hints": {
                "enclosure_size": enc_size,
                "material": "PLA",
                "wall_thickness_mm": wall_t,
                "has_lid": True,
            },
            "power_summary": {
                "total_mw": total_ma,
                "budget_mw": 500 if "USB" in power else (1500 if "LiPo" in power else 800),
            },
            "total_pins": total_pins,
        }

    def _pick_aux_with_inferred(self, category: str, proj_slug: str,
                                ) -> List[Dict[str, Any]]:
        """隨機 aux + 隱含能力補全（帶 inferred_reason 標注）。"""
        aux = self._pick_aux_components(category)
        implicit = _IMPLICIT_CAPABILITY_MAP.get(proj_slug, [])
        if not implicit:
            return aux
        existing_types = {c["type"] for c in aux}
        for role, ctype, reason in implicit:
            if ctype not in existing_types:
                aux.append({"role": role, "type": ctype, "qty": 1,
                            "inferred_reason": reason})
                existing_types.add(ctype)
        return aux

    def _build_sample(self, idx: int) -> Dict[str, Any]:
        categories = list(_PROJECT_DESCRIPTIONS.keys())
        category = categories[idx % len(categories)]
        descs = _PROJECT_DESCRIPTIONS[category]
        zh_name, proj_slug, description = descs[idx % len(descs)]

        _bw = [0.05 if "RaspberryPi" in b else 0.317 for b in self._brain_types]
        brain   = random.choices(self._brain_types, weights=_bw, k=1)[0]
        power   = random.choice(self._power_types)
        control = random.choice(self._control_types)
        enc_size = random.choice(["compact", "compact", "medium", "large"])
        wall_t   = round(random.choice([1.6, 1.8, 2.0, 2.0, 2.0, 2.4, 2.8, 3.0]), 1)

        # 決定範例類型：40% 完整 / 40% 模糊(推理補全) / 20% 部分指定
        sample_kind = random.random()
        is_vague = sample_kind >= 0.4  # 60% 需要推理（含 vague + partial）

        # M1 scope filter
        for _ in range(5):
            if is_vague:
                aux_components = self._pick_aux_with_inferred(category, proj_slug)
            else:
                aux_components = self._pick_aux_components(category)
            if _is_in_scope(description, aux_components):
                break
        else:
            aux_components = [c for c in aux_components
                              if c.get("type") not in _MULTIAXIS_TYPES][:2]

        all_components = [
            {"role": "Brain",   "type": brain,   "qty": 1},
            {"role": "Power",   "type": power,   "qty": 1},
            {"role": "Control", "type": control,  "qty": 1},
        ] + aux_components

        cot_plan = self._build_cot_plan(
            category, zh_name, description, brain, power,
            all_components, enc_size, wall_t,
        )
        # completion 中移除 inferred_reason（訓練輸出 schema 不變）
        clean_comps = [{k: v for k, v in c.items() if k != "inferred_reason"}
                       for c in all_components]
        expected = {
            "project_name":      proj_slug,
            "project_category":  category,
            "cot_plan":          cot_plan,
            "components":        clean_comps,
            "enclosure_constraints": {
                "target_size":       enc_size,
                "max_dimension_mm":  150 if enc_size == "compact" else 220,
                "wall_thickness_mm": wall_t,
                "material":          "PLA",
            },
            "inventory_mentions": [],
        }

        # 選擇 prompt 模板
        sensor_names = [c["type"].replace("-class", "") for c in aux_components
                        if c["role"] == "Sensor"]
        actuator_names = [c["type"].replace("-class", "") for c in aux_components
                         if c["role"] in ("Actuator", "Sound", "Display", "Lighting", "Mist")]

        if sample_kind < 0.4:
            # 完整指定（原行為）
            tpls = PROMPT_TEMPLATES_ZH if random.random() < 0.6 else PROMPT_TEMPLATES_EN
            user_input = tpls[idx % len(tpls)].format(
                project_name=zh_name, category=category, description=description,
                brain=brain.replace("-class", ""), power=power.replace("-class", ""),
                sensors=", ".join(sensor_names) if sensor_names else "環境感測器",
                actuators=", ".join(actuator_names) if actuator_names else "輸出模組",
                enclosure_style=enc_size,
            )
        else:
            # 模糊/不完整（學生不指定元件，模型須推理）
            tpls = (PROMPT_TEMPLATES_VAGUE_ZH if random.random() < 0.6
                    else PROMPT_TEMPLATES_VAGUE_EN)
            user_input = tpls[idx % len(tpls)].format(
                project_name=zh_name, description=description,
            )

        rag_ctx = ""
        if random.random() < 0.35:  # 提高 RAG 注入率（原 25% → 35%）
            rag_ctx = _synth_rag_context_a(category, exclude_name=proj_slug)
        prompt = _format_prompt(user_input, rag_context=rag_ctx)
        return {
            "prompt":     prompt,
            "completion": json.dumps(expected, ensure_ascii=False, indent=2) + "<|eot_id|>",
            "user_input": user_input,
            "category":   category,
        }

    def generate_synthetic_data(self, n: int = 1200):
        """產生 n 筆訓練樣本，回傳 HuggingFace Dataset。"""
        assert n > 0
        samples = [self._build_sample(i) for i in range(n)]
        cat_dist = Counter(s["category"] for s in samples)
        print(f"[DataGen] 資料生成完成：{n} 筆")
        print(f"[DataGen] Category 分佈：{dict(cat_dist)}")
        if Dataset is None:
            raise ImportError('datasets 套件未安裝,請執行 pip install "datasets>=3.0.0"')
        return Dataset.from_list([
            {"prompt": s["prompt"], "completion": s["completion"]}
            for s in samples
        ])


def make_dataset(n: int = 1200):
    return DataGenerator().generate_synthetic_data(n)
