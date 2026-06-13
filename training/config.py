"""config.py — Training package 的 TAXONOMY_CONFIG 與 MODEL_CONFIG 快照。

此檔案是 training package 的獨立副本，與主專案 lib/config.py 同源。
修改元件清單或分類時，需同步更新兩邊。
"""
from typing import Dict, Any, List

# ── 模型配置 ─────────────────────────────────────────────
MODEL_CONFIG: Dict[str, Any] = {
    "base_model_4bit": "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    "max_seq_len": 2048,
    "lora_r": 16,
    "lora_alpha": 32,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj",
                       "gate_proj", "up_proj", "down_proj"],
}

# ── 分類與元件清單（SSOT 快照）────────────────────────────
TAXONOMY_CONFIG: Dict[str, Any] = {
    "core_roles": ["Brain", "Power", "Control"],
    "aux_roles": ["Sensor", "Actuator", "Display", "Sound", "Lighting", "Mist", "Chassis", "Enclosure"],
    "project_categories": [
        "Smart_Home", "Robotics",
        "Interactive_Art", "Gardening", "Security", "Education",
    ],

    "component_taxonomy": {
        # RaspberryPi-class 已退役（2026-06-13，方案 B；見 lib/config.py 同註解）：infra 休眠保留，僅退出訓練詞彙。
        "Brain":    ["Arduino-Uno-class", "ESP32-class", "Microbit-class"],
        "Power":    ["USB-5V-class", "Battery-LiPo-class", "Battery-AA-class", "AC-Adapter-class", "USB-Adapter-class"],
        "Control":  ["Button-class", "Switch-class", "Switch-Generic-class", "Potentiometer-class", "Remote-class", "Joystick-class"],
        "Sensor":   ["Sensor-PIR-class", "Sensor-Ultrasonic-class", "Sensor-TempHumid-class", "Sensor-Light-class", "Sensor-SoilMoisture-class", "Sensor-IR-class", "Sensor-MSGEQ7-class"],
        "Actuator": ["Motor-Servo-class", "Motor-DC-class", "Motor-Stepper-class", "Pump-Water-class", "Relay-Module-class", "L298N-Driver-class"],
        "Display":  ["Display-OLED-class", "Display-LCD-class", "Display-EInk-class", "LED-Matrix-class"],
        "Sound":    ["Buzzer-Active-class", "Buzzer-Passive-class", "MP3-Module-class", "Speaker-class"],
        "Lighting": ["Lighting-LED-RGB-class", "Lighting-LED-Strip-class", "Lighting-NeoPixel-class", "Lighting-LED-PWM-class"],
        "Mist":     ["Mist-Atomizer-class", "Mist-Ultrasonic-class"],
        "Chassis":  ["Chassis-Car-class"],
    },

    "alias_mapping": {
        "Microbit": "Microbit-class", "MicroBit": "Microbit-class",
        "Micro-Bit": "Microbit-class", "MicroBit-class": "Microbit-class",
        "Arduino": "Arduino-Uno-class",
        "Speaker": "Speaker-class", "Speaker-Unit": "Speaker-class", "Speaker-Unit-class": "Speaker-class",
        "USB-Power-Adapter-class": "USB-Adapter-class",
        "Battery-AA": "Battery-AA-class", "Servo": "Motor-Servo-class",
        "Switch-generic": "Switch-Generic-class",
        "Sensor-PIR": "Sensor-PIR-class", "Display-OLED": "Display-OLED-class",
    },
}
TAXONOMY_CONFIG["all_valid_types"] = set(
    sum(TAXONOMY_CONFIG["component_taxonomy"].values(), [])
)

# U9: 訓練資料永不含 user_components — 用戶自填元件只走推論路徑
_USER_PREFIX = "User-"
assert not any(
    t.startswith(_USER_PREFIX)
    for t in TAXONOMY_CONFIG["all_valid_types"]
), f"TAXONOMY_CONFIG 含 '{_USER_PREFIX}*' 元件，違反 U9 訓練隔離規則"

# ── 教育推理模板（中文）────────────────────────────────────
EDUCATIONAL_RATIONALE: Dict[str, str] = {
    "Arduino-Uno-class":          "採用 ATmega328P 微控制器，透過數位/類比 GPIO 腳位控制外部元件。",
    "ESP32-class":                "雙核心 CPU 內建 Wi-Fi/Bluetooth，適合 IoT 無線控制應用。",
    "Microbit-class":             "內建加速度計與 LED 矩陣，專為 STEM 教育設計的微控制板。",
    "USB-5V-class":               "透過 USB 介面提供穩定 5V 直流電源，適合低功耗模組供電。",
    "Battery-LiPo-class":         "鋰聚合物電池，能量密度高，適合需要可攜式電源的專題。",
    "Battery-AA-class":           "標準 AA 乾電池，取得方便，適合低功耗感測器節點。",
    "Sensor-SoilMoisture-class":  "量測土壤導電率以判斷含水量，適合自動澆水系統。",
    "Sensor-TempHumid-class":     "量測環境溫度與相對濕度，常用於智慧農業或氣候監控。",
    "Sensor-PIR-class":           "被動式紅外線感測器，偵測人體熱輻射以判斷是否有人移動。",
    "Sensor-Ultrasonic-class":    "利用超音波回波測量距離，偵測範圍約 2cm 至 4m。",
    "Sensor-Light-class":         "光敏電阻感測環境亮度，可根據光線自動調整設備行為。",
    "Motor-Servo-class":          "伺服馬達，可精確控制轉角 0 至 180 度，適合機械臂關節。",
    "Motor-DC-class":             "直流馬達，透過 PWM 調速，適合輪式機器人驅動。",
    "Pump-Water-class":           "小型水泵，透過繼電器控制開關，用於自動澆水或水循環。",
    "Relay-Module-class":         "電磁繼電器，以低電壓控制高電壓迴路的通斷開關。",
    "Display-OLED-class":         "有機發光二極體螢幕，對比高耗電低，顯示文字與圖形。",
    "Buzzer-Active-class":        "內建振盪電路，通電即發聲，適合簡單的嗶嗶提示音。",
    "Buzzer-Passive-class":       "需外部 PWM 驅動，可發出不同頻率音調，適合旋律播放。",
    "MP3-Module-class":           "SD 卡 MP3 播放模組，可播放預錄音頻，適合語音提示應用。",
    "Speaker-class":              "揚聲器搭配音訊放大器，播放高品質聲音效果。",
    "Lighting-NeoPixel-class":    "可程式化 RGB LED 燈帶，支援逐顆控制色彩與動畫。",
    "Lighting-LED-PWM-class":     "PWM 調光 LED，透過占空比控制亮度等級。",
    "Lighting-LED-RGB-class":     "RGB 三色 LED，混色產生多種色彩效果。",
    "Lighting-LED-Strip-class":   "LED 燈條，多顆 LED 串聯，提供均勻照明。",
    "AC-Adapter-class":           "交流轉直流電源供應器，輸出穩定 5V/2A，適合高功耗專題固定供電。",
    "USB-Adapter-class":          "USB 電源轉接器，提供穩定 5V 供電，適合桌面型專題使用。",
    "Button-class":               "觸覺按鈕開關，按下導通放開斷路，用於手動觸發事件。",
    "Switch-class":               "撥動開關 SPDT，手動切換電路通路，適合模式切換或電源開關。",
    "Switch-Generic-class":       "通用撥動開關，簡單開/關控制，適合電源或模式選擇。",
    "Potentiometer-class":        "旋轉電位器，轉動旋鈕調整類比電壓輸出，用於亮度或速度調節。",
    "Remote-class":               "紅外線遙控接收器，接收遙控器 IR 信號並解碼為按鍵值。",
    "Joystick-class":             "雙軸搖桿模組，兩個類比軸 + 按鈕，適合方向控制與遊戲互動。",
    "Sensor-IR-class":            "紅外線避障感測器，偵測前方障礙物反射 IR 光束，回傳數位信號。",
    "Sensor-MSGEQ7-class":        "七頻段音頻等化器 IC，分析聲音頻譜輸出各頻段強度，適合音樂視覺化。",
    "Motor-Stepper-class":        "步進馬達搭配 ULN2003 驅動板，精確角度定位，適合旋轉展示台。",
    "Display-LCD-class":          "1602 液晶顯示器，透過 I2C 介面顯示兩行文字，適合數據讀數。",
    "Display-EInk-class":         "電子墨水螢幕，斷電後仍保持畫面，超低功耗適合電池供電應用。",
    "LED-Matrix-class":           "MAX7219 驅動 8×8 LED 矩陣，透過 SPI 控制點陣圖案與動畫。",
    "Mist-Atomizer-class":        "壓電式霧化片，高頻振動將水霧化成微粒，適合加濕或視覺效果。",
    "Mist-Ultrasonic-class":      "超音波霧化模組，功率較高的霧化器，產生大量水霧效果。",
    "Chassis-Car-class":          "車體底盤結構件，提供馬達與輪軸安裝基座，適合移動式機器人專題。",
}
