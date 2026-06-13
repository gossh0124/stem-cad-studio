"""config.py — Global configuration and taxonomy for STEM_AI_LLM."""
import os
from pathlib import Path
from typing import Dict, Any

def _resolve_lora_path() -> str:
    """回傳 LoRA adapter 儲存路徑，優先序：環境變數 → Colab Drive → 本地 saved_model/。"""
    if os.environ.get("CADHLLM_LORA_PATH"):
        return os.environ["CADHLLM_LORA_PATH"]
    colab_path = "/content/drive/MyDrive/CADHLLM/saved_model/cadhllm_lora"
    if Path("/content/drive").exists():
        return colab_path
    # 本地端：相對於此檔案的上層目錄
    local_path = Path(__file__).parent.parent / "saved_model" / "cadhllm_lora"
    return str(local_path)

MODEL_CONFIG: Dict[str, Any] = {
    "base_model_4bit": "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    "base_model_full": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "max_seq_len": 2048,
    "load_in_4bit": True,
    "random_state": 3407,
    "lora_r": 16,
    "lora_alpha": 32,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    "lora_save_path": _resolve_lora_path(),
}

ENCLOSURE_DEFAULTS: Dict[str, Any] = {
    "wall_thickness_mm": 2.0,
    "max_dimension_mm": 150,
    "material": "PLA",
}

ENCLOSURE_SIZE_CAPS: Dict[str, int] = {
    "compact": 120,
    "medium": 160,
    "large": 220,
}

ENCLOSURE_SIZE_THRESHOLDS = {
    "large_component_count": 5,
    "medium_component_count": 3,
}

# 面積閾值 (mm²) — 決定 compact/medium/large 外殼
AREA_COMPACT_MAX_MM2 = 8000
AREA_MEDIUM_MAX_MM2 = 20000

# ROLE_PALETTE — role → UI 顏色 單一 SSOT（11 role 對齊 TAXONOMY_CONFIG core+aux）。
# Wave B：取代散落各檔的平行手填色表（UI_ROLE_COLOR / ROLE_COLOR / scene-3d ROLE_RGB
# / assembly-v3 ROLE_COLORS / _phase5 _ROLE_COLORS）。缺角色降級走 ROLE_COLOR_UNKNOWN
# （顯式 Unknown 灰，非靜默沿用相鄰色；VS-FALLBACK(b)）。
ROLE_PALETTE: Dict[str, str] = {
    "Brain": "#4da6ff", "Power": "#ffcc00", "Control": "#b070ff",
    "Sensor": "#ff88cc", "Actuator": "#00ff88", "Display": "#00d0d0",
    "Sound": "#ff7733", "Lighting": "#ffe14d", "Mist": "#66ccff",
    "Chassis": "#8d6e63", "Enclosure": "#a1887f",
}
ROLE_COLOR_UNKNOWN = "#888"

TAXONOMY_CONFIG: Dict[str, Any] = {
    "core_roles": ["Brain", "Power", "Control"],
    "aux_roles": ["Sensor", "Actuator", "Display", "Sound", "Lighting", "Mist", "Chassis", "Enclosure"],
    # 2026-05-08 6 category SSOT（與 training/config.py 一致；Wearables 移至 Layer 4 進階未來）
    "project_categories": ["Smart_Home", "Robotics", "Interactive_Art", "Gardening", "Security", "Education"],
    "intent_types": ["have", "prefer", "avoid", "budget_constraint"],

    "component_taxonomy": {
        # RaspberryPi-class 已於 2026-06-13 從使用者可選 Brain 詞彙退役（退役方案 B）：
        # 小型 STEM demo 目標下不需 Linux SBC（過於複雜、價格/功耗高、消費級可印無益）。
        # infra 休眠保留（registry ComponentSpec / SSOT / lib/pcb / firmware / MCU_COMPONENTS=5
        # 皆不動），僅從 taxonomy / alias / phase1 詞彙 / role_alternatives / 訓練詞彙移除。
        "Brain": ["Arduino-Uno-class", "Arduino-Nano-class", "ESP32-class", "Microbit-class"],
        "Power": ["USB-5V-class", "Battery-LiPo-class", "Battery-AA-class", "Battery-4AA-class", "AC-Adapter-class", "USB-Adapter-class"],
        "Control": ["Button-class", "Switch-class", "Switch-Generic-class", "Potentiometer-class", "Remote-class", "Joystick-class"],
        "Sensor": ["Sensor-PIR-class", "Sensor-Ultrasonic-class", "Sensor-TempHumid-class", "Sensor-Light-class", "Sensor-SoilMoisture-class", "Sensor-IR-class", "Sensor-MSGEQ7-class"],
        "Actuator": ["Motor-Servo-class", "Motor-DC-class", "Motor-Stepper-class", "Pump-Water-class", "Relay-Module-class", "L298N-Driver-class"],
        "Display": ["Display-OLED-class", "Display-LCD-class", "Display-EInk-class", "LED-Matrix-class"],
        "Sound": ["Buzzer-Active-class", "Buzzer-Passive-class", "MP3-Module-class", "Speaker-class"],
        "Lighting": ["Lighting-LED-RGB-class", "Lighting-LED-Strip-class", "Lighting-NeoPixel-class", "Lighting-LED-PWM-class"],
        "Mist": ["Mist-Atomizer-class", "Mist-Ultrasonic-class"],
        "Chassis": ["Chassis-Car-class"],
        # Enclosure 不是型錄元件：由程序化外殼生成子系統 (lib/cad/shell/, enclosure_fit.py)
        # 產生幾何，無對應 *-class 元件。原本誤別名為 Chassis-Car-class 會讓車型底盤
        # 靜默滿足外殼角色 — 改為空清單，避免錯誤元件選擇 (SSOT-integrity)。
        "Enclosure": []
    },

    "alias_mapping": {
        "Microbit": "Microbit-class", "MicroBit": "Microbit-class", "Micro-Bit": "Microbit-class",
        "MicroBit-class": "Microbit-class", "Arduino": "Arduino-Uno-class",
        "Nano": "Arduino-Nano-class", "Arduino-Nano": "Arduino-Nano-class",
        "Speaker": "Speaker-class", "Speaker-Unit": "Speaker-class", "Speaker-Unit-class": "Speaker-class",
        "USB-Power-Adapter-class": "USB-Adapter-class", "Battery-AA": "Battery-AA-class",
        "Switch-generic": "Switch-Generic-class", "Sensor-PIR": "Sensor-PIR-class",
        "Display-OLED": "Display-OLED-class", "Servo": "Motor-Servo-class"
    },

    "gen_mapping": {
        # 2026-05-08 移除 Wearables（計步器/發光領結/導盲手環 → Layer 4 進階未來）
        "Smart_Home": [("智慧小夜燈", "smart_night_light"), ("自動窗簾", "auto_curtain"), ("語音門鈴", "voice_doorbell")],
        "Robotics": [("遙控車", "remote_car"), ("避障車", "obstacle_avoiding_bot"), ("說話機器人", "talking_robot")],
        "Interactive_Art": [("音樂盒", "music_box"), ("光劍", "light_saber"), ("電子琴", "electronic_piano")],
        "Gardening": [("自動澆花器", "auto_plant_waterer"), ("植物監測儀", "plant_monitor")],
        "Security": [("防盜鈴", "burglar_alarm"), ("門禁系統", "access_control"), ("警報器", "security_siren")],
        "Education": [("倒數計時器", "countdown_timer"), ("語音導覽機", "voice_guide")]
    }
}
TAXONOMY_CONFIG["all_valid_types"] = set(sum(TAXONOMY_CONFIG["component_taxonomy"].values(), []))

EDUCATIONAL_RATIONALE_TEMPLATES = {
    "Arduino-Uno-class": "採用 ATmega328P 微控制器，透過數位/類比 GPIO 腳位控制外部元件。",
    "Arduino-Nano-class": "Arduino Nano（ATmega328），與 Uno 同核心同腳位但體積僅 1/3，適合機器人等空間受限專題。",
    "ESP32-class": "雙核心 CPU 內建 Wi-Fi/Bluetooth，適合 IoT 無線控制應用。",
    "Microbit-class": "內建加速度計與 LED 矩陣，專為 STEM 教育設計的微控制板。",
    "USB-5V-class": "透過 USB 介面提供穩定 5V 直流電源，適合低功耗模組供電。",
    "Battery-LiPo-class": "鋰聚合物電池，能量密度高，適合需要可攜式電源的專題。",
    "Battery-AA-class": "標準 AA 乾電池，取得方便，適合低功耗感測器節點。",
    "Battery-4AA-class": "4 顆 AA 串聯 6V 電池盒，可攜且電壓落在伺服 4.8-6V 範圍，適合多伺服機器人等需獨立電源軌的負載。",
    "AC-Adapter-class": "將交流電轉換為穩定直流輸出，適合固定式高功耗設備供電。",
    "Button-class": "機械式按鍵，按下時電路導通，是最基礎的數位輸入元件。",
    "Potentiometer-class": "可變電阻器，輸出 0~5V 類比電壓，用於調節音量或速度。",
    "Switch-class": "撥動式開關，可維持開/關狀態，適合電源控制或模式切換。",
    "Joystick-class": "雙軸類比搖桿，輸出 XY 方向電壓值，適合遙控移動方向。",
    "Remote-class": "紅外線遙控器，發送 IR 編碼訊號，配合接收模組實現無線控制。",
    "Sensor-Ultrasonic-class": "利用超音波回波測量距離，偵測範圍約 2cm 至 4m。",
    "Sensor-TempHumid-class": "量測環境溫度與相對濕度，常用於智慧農業或氣候監控。",
    "Sensor-Light-class": "光敏電阻感測環境亮度，可根據光線自動調整設備行為。",
    "Sensor-PIR-class": "被動式紅外線感測器，偵測人體熱輻射以判斷是否有人移動。",
    "Sensor-SoilMoisture-class": "量測土壤導電率以判斷含水量，適合自動澆水系統。",
    "Sensor-IR-class": "紅外線接收模組（如 VS1838B），解碼 38kHz IR 遙控訊號，廣泛用於家電與裝置遙控。",
    "Motor-Servo-class": "伺服馬達，可精確控制轉角 0 至 180 度，適合機械臂關節。",
    "Motor-DC-class": "直流馬達，透過 PWM 調速，適合輪式機器人驅動。",
    "Motor-Stepper-class": "步進馬達，每步精確旋轉固定角度，適合精密定位應用。",
    "Relay-Module-class": "電磁繼電器，以低電壓控制高電壓迴路的通斷開關。",
    "Pump-Water-class": "小型水泵，透過繼電器控制開關，用於自動澆水或水循環。",
    "Display-OLED-class": "有機發光二極體螢幕，對比高耗電低，顯示文字與圖形。",
    "Display-LCD-class": "液晶顯示器，透過 I2C 介面顯示多行文字，成本低廉。",
    "Display-EInk-class": "電子墨水顯示器，無需持續供電即可保持畫面，適合低功耗。",
    "LED-Matrix-class": "LED 點陣模組，可顯示捲動文字或簡單動畫圖案。",
    "Buzzer-Active-class": "內建振盪電路，通電即發聲，適合簡單的嗶嗶提示音。",
    "Buzzer-Passive-class": "需外部 PWM 驅動，可發出不同頻率音調，適合旋律播放。",
    "MP3-Module-class": "SD 卡 MP3 播放模組，可播放預錄音頻，適合語音提示應用。",
    "Speaker-class": "揚聲器將電訊號轉換為聲波，搭配功放模組輸出高品質音效。",
    "Lighting-LED-RGB-class": "三色 RGB LED，混合紅綠藍光產生全彩效果，可獨立控制。",
    "Lighting-LED-Strip-class": "可彎折的 LED 燈條，適合環境氛圍照明或裝飾性佈線。",
    "Lighting-NeoPixel-class": "WS2812B 可定址 LED，每顆獨立控制色彩，用單線串接。",
    "Lighting-LED-PWM-class": "單顆或少量 LED 搭配 PWM 調光，功耗低（~20mA），適合夜燈、指示燈等簡單照明。",
    "Mist-Atomizer-class": "霧化器透過振動將水霧化，常用於加濕器或舞台效果。",
    "Mist-Ultrasonic-class": "超音波霧化片，振動頻率將液體表面霧化，功耗低效率高。",
    "Chassis-Car-class": "車型底盤，整合馬達與輪組，是輪式機器人的移動平台。",
}

ASSEMBLY_V3 = {
    "GRID_RES": 3,
    "CLEARANCE": 3.0,
    "TURN_PENALTY": 2.0,
    "WIRE_MARGIN": 1,
    # 對齊 v2 / thermal.py 政策：THERMAL_TIER_MID=1500mW 為「必須主動通風」門檻
    # （原 2000 與 thermal 建議文字「>1500mW 必須通風」自相矛盾，1500-2000mW 區間會建議卻不加通風）
    "VENT_THRESHOLD_MW": 1500,
    "H_CONV": 7.0,
    "DT_MAX": 40.0,
}

CAD_VALIDATION = {
    "BBOX_LIMIT_MM": 300.0,
    "MIN_WALL_MM": 1.5,
}

_COMPLEX_EFFECT_TEMPLATES = [
    {
        "suffix": "，並加上 RGB 燈光效果",
        "aux_roles": [{"role": "Lighting", "tags": ["output", "visual"],
                       "recommended_types": ["Lighting-LED-RGB-class"]}],
    },
    {
        "suffix": "，搭配 LED 燈條裝飾",
        "aux_roles": [{"role": "Lighting", "tags": ["output", "visual"],
                       "recommended_types": ["Lighting-LED-Strip-class"]}],
    },
    {
        "suffix": "，使用 NeoPixel 燈環顯示狀態",
        "aux_roles": [{"role": "Lighting", "tags": ["output", "visual"],
                       "recommended_types": ["Lighting-NeoPixel-class"]}],
    },
    {
        "suffix": "，並噴出水霧製造氛圍",
        "aux_roles": [{"role": "Mist", "tags": ["output", "effect"],
                       "recommended_types": ["Mist-Atomizer-class"]}],
    },
    {
        "suffix": "，搭配超音波霧化效果",
        "aux_roles": [{"role": "Mist", "tags": ["output", "effect"],
                       "recommended_types": ["Mist-Ultrasonic-class"]}],
    },
    {
        "suffix": "，結合燈光與水霧的舞台效果",
        "aux_roles": [
            {"role": "Lighting", "tags": ["output", "visual"],
             "recommended_types": ["Lighting-NeoPixel-class"]},
            {"role": "Mist", "tags": ["output", "effect"],
             "recommended_types": ["Mist-Ultrasonic-class"]},
        ],
    },
]
