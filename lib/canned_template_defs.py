"""tools/_canned_template_defs.py — 16 canned demo template definitions.

Extracted from bake_canned_bridges.py to keep files under 500 lines.
Each entry aligns with v6/data.jsx CHALLENGE_CATALOG.
"""
from __future__ import annotations

TEMPLATE_DEFS: dict = {
    # === Gardening ===
    "auto_waterer": {
        "name": "自動澆花器", "category": "Gardening",
        "prompt": "智慧花盆 自動澆水系統",
        "high_level_plan": "土壤含水量低於閾值時，繼電器啟動水泵供水至植物根部，定時偵測並避免過度澆水。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",        "qty": 1},
            {"role": "Power",   "type": "Battery-AA-class",         "qty": 1},
            {"role": "Sensor",  "type": "Sensor-SoilMoisture-class","qty": 1},
            {"role": "Output",  "type": "Pump-Water-class",         "qty": 1},
            {"role": "Control", "type": "Relay-Module-class",       "qty": 1},
        ],
        "challenges_focus": ["thermal", "high_current", "waterproof"],
    },
    "plant_monitor": {
        "name": "植物監測儀", "category": "Gardening",
        "prompt": "植物監測儀",
        "high_level_plan": "持續偵測土壤濕度與環境溫度，OLED 顯示即時讀值，協助使用者判斷澆水時機。",
        "components": [
            {"role": "Brain",   "type": "Microbit-class",            "qty": 1},
            {"role": "Power",   "type": "Battery-AA-class",          "qty": 1},
            {"role": "Sensor",  "type": "Sensor-SoilMoisture-class", "qty": 1},
            {"role": "Sensor",  "type": "Sensor-TempHumid-class",    "qty": 1},
            {"role": "Output",  "type": "Display-OLED-class",        "qty": 1},
        ],
        "challenges_focus": ["low_power", "i2c"],
    },

    # === Smart_Home ===
    "smart_nightlight": {
        "name": "智慧小夜燈", "category": "Smart_Home",
        "prompt": "智慧小夜燈",
        "high_level_plan": "光敏電阻偵測環境亮度，低於閾值時自動點亮 LED，模擬日落自動照明。",
        "components": [
            {"role": "Brain",  "type": "Arduino-Uno-class",       "qty": 1},
            {"role": "Power",  "type": "USB-5V-class",            "qty": 1},
            {"role": "Sensor", "type": "Sensor-Light-class",      "qty": 1},
            {"role": "Output", "type": "Lighting-LED-PWM-class",  "qty": 1},
        ],
        "challenges_focus": ["low_power", "port_orient"],
    },
    "auto_curtain": {
        "name": "自動窗簾", "category": "Smart_Home", "scope": "layer4",
        "prompt": "自動窗簾",
        "high_level_plan": "（Layer 4 進階）步進馬達拉動繩索開關窗簾，光感測或定時觸發。",
        "components": [
            {"role": "Brain",   "type": "ESP32-class",          "qty": 1},
            # 電源 USB-5V→AC-Adapter(#27):ESP32(240)+Stepper(240)+Relay(80)+Light(1)=561mA
            # 超出 USB 2.0 SDP 官方 500mA 上限(原被 stale 1000mA budget 掩蓋,#20 假性放行)。
            # 馬達負載 + 固定家電 → 5V/2A 壁插 AC 變壓器(HLK-PM01,verified.json 2000mA)為適配現實電源(#19)。
            {"role": "Power",   "type": "AC-Adapter-class",     "qty": 1},
            {"role": "Sensor",  "type": "Sensor-Light-class",   "qty": 1},
            {"role": "Output",  "type": "Motor-Stepper-class",  "qty": 1},
            {"role": "Control", "type": "Relay-Module-class",   "qty": 1},
        ],
        "challenges_focus": ["high_current", "structural", "cable_routing"],
    },
    "voice_doorbell": {
        "name": "語音門鈴", "category": "Smart_Home",
        "prompt": "語音門鈴",
        "high_level_plan": "按鈕觸發 MP3 模組播放預錄問候語，揚聲器朝外輸出。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",    "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",         "qty": 1},
            {"role": "Control", "type": "Button-class",         "qty": 1},
            {"role": "Output",  "type": "MP3-Module-class",     "qty": 1},
        ],
        "challenges_focus": ["port_orient", "thermal"],
    },

    # === Robotics ===
    "rc_car": {
        "name": "遙控車", "category": "Robotics",
        "prompt": "遙控車",
        "high_level_plan": "IR 遙控器發送指令，主控解碼後分別控制兩顆 DC 馬達實現前後左右。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",  "qty": 1},
            {"role": "Power",   "type": "Battery-LiPo-class", "qty": 1},
            {"role": "Sensor",  "type": "Remote-class",       "qty": 1},
            {"role": "Output",  "type": "Motor-DC-class",     "qty": 2},
            {"role": "Control", "type": "Relay-Module-class", "qty": 1},
            {"role": "Housing", "type": "Chassis-Car-class",  "qty": 1},
        ],
        "challenges_focus": ["high_current", "gravity_sort", "cable_routing"],
    },
    # obstacle_car（避障車）已於 2026-06-13 由 biped_robot（簡易雙足機器人）取代並移除：
    # 不可印（與 rc_car 致動器域重複 + Chassis 大底盤）+ 避障邏輯由 biped 原樣涵蓋並超越。
    # 知識保存於 vault『簡易雙足機器人 demo 規格』取代理由節。
    "biped_robot": {
        "name": "簡易雙足機器人", "category": "Robotics",
        "prompt": "簡易雙足機器人",
        "high_level_plan": "四顆伺服馬達（髖×2 + 踝×2）以正弦步態驅動雙足行走，HC-SR04 偵測前方障礙時停步/轉向，主動蜂鳴器回饋；伺服軌與主控軌分離供電以避免同動堵轉壓降。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Nano-class",       "qty": 1},
            {"role": "Power",   "type": "Battery-4AA-class",        "qty": 1},
            {"role": "Output",  "type": "Motor-Servo-class",        "qty": 4},
            {"role": "Sensor",  "type": "Sensor-Ultrasonic-class",  "qty": 1},
            {"role": "Output",  "type": "Buzzer-Active-class",      "qty": 1},
        ],
        "challenges_focus": ["high_current", "gravity_sort", "port_orient"],
    },
    "talking_robot": {
        "name": "說話機器人", "category": "Robotics",
        "prompt": "說話機器人",
        "high_level_plan": "PIR 偵測有人接近，OLED 顯示表情、MP3 模組播放問候語。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",   "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",        "qty": 1},
            {"role": "Sensor",  "type": "Sensor-PIR-class",    "qty": 1},
            {"role": "Output",  "type": "Display-OLED-class",  "qty": 1},
            {"role": "Output",  "type": "MP3-Module-class",    "qty": 1},
        ],
        "challenges_focus": ["port_orient", "i2c"],
    },

    # === Interactive_Art ===
    "music_box": {
        "name": "音樂盒", "category": "Interactive_Art",
        "prompt": "音樂盒",
        "high_level_plan": "翻蓋觸發微動開關，MP3 模組播放預錄樂曲，搭配揚聲器外放。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",      "qty": 1},
            {"role": "Control", "type": "Switch-class",      "qty": 1},
            {"role": "Output",  "type": "MP3-Module-class",  "qty": 1},
        ],
        "challenges_focus": ["port_orient", "structural"],
    },
    "lightsaber": {
        "name": "光劍", "category": "Interactive_Art", "scope": "layer4",
        "prompt": "光劍",
        "high_level_plan": "（Layer 4 進階）按鈕啟動 NeoPixel 燈條全亮，加速度計偵測揮動觸發音效。",
        "components": [
            {"role": "Brain",   "type": "ESP32-class",            "qty": 1},
            {"role": "Power",   "type": "Battery-LiPo-class",     "qty": 1},
            {"role": "Control", "type": "Button-class",           "qty": 1},
            {"role": "Output",  "type": "Lighting-NeoPixel-class","qty": 1},
            {"role": "Output",  "type": "Buzzer-Active-class",    "qty": 1},
        ],
        "challenges_focus": ["high_current", "structural", "thermal"],
    },
    "electronic_keyboard": {
        "name": "電子琴", "category": "Interactive_Art",
        "prompt": "電子琴",
        "high_level_plan": "按鍵矩陣偵測按下，被動蜂鳴器以 PWM 產生對應音調。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",   "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",        "qty": 1},
            {"role": "Control", "type": "Button-class",        "qty": 8},
            {"role": "Output",  "type": "Buzzer-Passive-class","qty": 1},
        ],
        "challenges_focus": ["cable_routing", "port_orient"],
    },

    # === Security ===
    "burglar_alarm": {
        "name": "防盜鈴", "category": "Security",
        "prompt": "防盜鈴",
        "high_level_plan": "PIR 偵測人體紅外線，觸發時主動蜂鳴器發出高分貝警報音。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",   "qty": 1},
            {"role": "Power",   "type": "Battery-AA-class",    "qty": 1},
            {"role": "Sensor",  "type": "Sensor-PIR-class",    "qty": 1},
            {"role": "Output",  "type": "Buzzer-Active-class", "qty": 1},
        ],
        "challenges_focus": ["port_orient", "low_power"],
    },
    "access_control": {
        "name": "門禁系統", "category": "Security",
        "prompt": "門禁系統",
        "high_level_plan": "按鍵密碼或刷卡輸入，OLED 顯示狀態，繼電器控制電磁鎖開關。",
        "components": [
            {"role": "Brain",   "type": "ESP32-class",         "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",        "qty": 1},
            {"role": "Control", "type": "Button-class",        "qty": 4},
            {"role": "Output",  "type": "Display-OLED-class",  "qty": 1},
            {"role": "Output",  "type": "Relay-Module-class",  "qty": 1},
        ],
        "challenges_focus": ["high_current", "i2c", "structural"],
    },
    "alarm_siren": {
        "name": "警報器", "category": "Security",
        "prompt": "警報器",
        "high_level_plan": "震動感測或按鍵觸發，蜂鳴器持續鳴叫並 LED 閃爍警示。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",     "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",          "qty": 1},
            {"role": "Control", "type": "Switch-class",          "qty": 1},
            {"role": "Output",  "type": "Buzzer-Active-class",   "qty": 1},
            {"role": "Output",  "type": "Lighting-LED-RGB-class","qty": 1},
        ],
        "challenges_focus": ["port_orient", "thermal"],
    },

    # === Education ===
    "countdown_timer": {
        "name": "倒數計時器", "category": "Education",
        "prompt": "倒數計時器",
        "high_level_plan": "按鈕設定倒數秒數，OLED 顯示剩餘時間，倒數結束時蜂鳴器響鈴。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",     "qty": 1},
            {"role": "Power",   "type": "USB-5V-class",          "qty": 1},
            {"role": "Control", "type": "Button-class",          "qty": 2},
            {"role": "Output",  "type": "Display-OLED-class",    "qty": 1},
            {"role": "Output",  "type": "Buzzer-Active-class",   "qty": 1},
        ],
        "challenges_focus": ["port_orient", "low_power"],
    },
    "voice_guide": {
        "name": "語音導覽機", "category": "Education",
        "prompt": "語音導覽機",
        "high_level_plan": "多選按鍵切換主題，MP3 模組播放對應的錄音講解。",
        "components": [
            {"role": "Brain",   "type": "Arduino-Uno-class",  "qty": 1},
            {"role": "Power",   "type": "Battery-AA-class",   "qty": 1},
            {"role": "Control", "type": "Button-class",       "qty": 4},
            {"role": "Output",  "type": "MP3-Module-class",   "qty": 1},
        ],
        "challenges_focus": ["port_orient", "cable_routing"],
    },
}
