"""feasibility_rules.py — 可行性規則資料表（純資料，無邏輯）。

由 lib/feasibility.py 匯入，單獨放置以利擴充而不超過 500 行限制。

新增規則：在 CAPABILITY_RULES 加一筆 dict 即可，欄位說明：
    rule_id         str   — 唯一識別碼（CAP-NNN）
    description     str   — 人類可讀說明
    intent_patterns list  — 比對 _instruction 的 regex list（任一命中即觸發）
    exclude_patterns list — （選填）regex list；任一命中 _instruction → 跳過此規則（negative-guard）
    component_match str   — 比對元件 type 的 regex（命中 → 觸發）
    severity        str   — "error" | "warning"
    issue           str   — 簡短問題（顯示給學生）
    why             str   — 教育性說明（6E Explain/Evaluate）
    suggested_fix   str   — 可操作的解決方案
"""
from __future__ import annotations
from typing import Any

# ---------------------------------------------------------------------------
# A. 能力誤用規則表
# ---------------------------------------------------------------------------

CAPABILITY_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "CAP-001",
        "description": "伺服馬達無法連續旋轉驅動輪子",
        "intent_patterns": [
            r"輪", r"wheel", r"drive", r"連續轉", r"一直轉",
            r"行走", r"move", r"前進", r"後退", r"走路", r"locomotion",
        ],
        # negative-guard(2026-06-13):伺服做「關節角度控制」的足式步行(雙足/四足/人形)
        # 是伺服正確用途,非驅動輪;排除以免 CAP-001 對 servo-walker 偽陽性 error。見 feasibility.py _check_capability。
        "exclude_patterns": [
            r"雙足", r"biped", r"步行", r"walker", r"otto", r"腿", r"leg",
            r"關節", r"joint", r"humanoid", r"人形", r"四足", r"quadruped",
        ],
        "component_match": r"^Motor-Servo",
        "severity": "error",
        "issue": "伺服馬達（Motor-Servo-class）無法連續旋轉，不適合驅動輪子",
        "why": (
            "標準伺服馬達（如 SG90）是「角度控制」元件，旋轉範圍僅限 0°–180°。"
            "它的控制訊號（PWM 脈衝寬度）對應到特定角度，而非轉速。"
            "即使強行送出超出範圍的訊號，也無法實現連續 360° 旋轉。"
            "用它驅動車輪只會讓輪子在兩個極端位置之間抖動，無法前進。"
        ),
        "suggested_fix": (
            "連續旋轉驅動輪子請改用：\n"
            "  • Motor-DC-class（直流馬達）+ L298N-Driver-class 驅動板"
            " → 簡單、便宜、適合差速轉向\n"
            "  • Motor-Stepper-class（步進馬達）→ 需要精確位置控制時使用\n"
            "  • 若手邊只有伺服馬達，可購買「連續旋轉伺服」（Continuous Rotation Servo），"
            "它的控制訊號代表轉速與方向，而非角度。"
        ),
    },
    {
        "rule_id": "CAP-002",
        "description": "蜂鳴器無法播放 MP3 音訊檔案",
        "intent_patterns": [
            r"播放", r"音樂", r"music", r"song", r"melody",
            r"語音", r"mp3", r"audio", r"sound file", r"wav", r"錄音",
        ],
        "component_match": r"^Buzzer",
        "severity": "warning",
        "issue": "蜂鳴器（Buzzer-*-class）只能發出單音，無法播放音訊檔案（MP3/WAV）",
        "why": (
            "主動蜂鳴器（Buzzer-Active-class）內建振盪電路，只能發出固定頻率的嗶嗶聲；"
            "被動蜂鳴器（Buzzer-Passive-class）雖可透過 PWM 改變音高，"
            "但受限於單一音調輸出，仍無法播放複雜的音訊資料"
            "（MP3 是壓縮的多聲道數位音訊格式）。"
            "播放 MP3 需要解碼 IC 和能夠重現頻率範圍的揚聲器。"
        ),
        "suggested_fix": (
            "若需要播放 MP3/WAV 音訊：\n"
            "  • 加入 MP3-Module-class（如 DFPlayer Mini）— 內建 MP3 解碼，"
            "搭配 Speaker-class 即可播放 SD 卡中的音訊檔案\n"
            "  • 若只需要簡單旋律（非音訊檔案），Buzzer-Passive-class + tone() 函式"
            "可演奏音符序列（如生日快樂歌），但不如真實音訊自然\n"
            "  • 語音播放建議：MP3-Module-class + Speaker-class + 預錄音訊檔案"
        ),
    },
]

# ---------------------------------------------------------------------------
# B. 缺少能力規則表（intent keywords → required component category）
# ---------------------------------------------------------------------------

MISSING_CAPABILITY_RULES: list[dict[str, Any]] = [
    {
        "rule_id": "MISS-001",
        "intent_keywords": [
            "light", "dark", "night", "bright", "dim", "luminous", "photosensitive",
            "光", "亮", "暗", "夜", "照度", "光感",
        ],
        "required_category": "Sensor-Light",
        "reason_zh": "偵測環境光線需要光感測器",
        "reason_en": "Detecting ambient light requires a light sensor",
    },
    {
        "rule_id": "MISS-002",
        "intent_keywords": [
            "temperature", "hot", "cold", "warm", "heat", "thermal",
            "溫度", "熱", "冷", "暖",
        ],
        "required_category": "Sensor-TempHumid",
        "reason_zh": "偵測溫度需要溫濕度感測器",
        "reason_en": "Temperature detection requires a temp/humidity sensor",
    },
    {
        "rule_id": "MISS-003",
        "intent_keywords": [
            "distance", "obstacle", "avoid", "proximity", "range",
            "距離", "障礙", "避障", "接近",
        ],
        "required_category": "Sensor-Ultrasonic",
        "reason_zh": "偵測距離/障礙需要超音波感測器",
        "reason_en": "Distance/obstacle detection requires an ultrasonic sensor",
    },
    {
        "rule_id": "MISS-004",
        "intent_keywords": [
            "motion", "movement", "presence", "detect person", "human",
            "動作", "移動", "人體", "偵測",
        ],
        "required_category": "Sensor-PIR",
        "reason_zh": "偵測人體動作需要 PIR 感測器",
        "reason_en": "Motion/presence detection requires a PIR sensor",
    },
    {
        "rule_id": "MISS-005",
        "intent_keywords": [
            "sound", "noise", "voice", "speak", "hear", "listen", "music",
            "聲音", "噪音", "語音", "說話", "聽", "音樂",
        ],
        "required_category": "Sensor-Sound",
        "reason_zh": "偵測聲音需要聲音感測器",
        "reason_en": "Sound detection requires a sound sensor",
    },
    {
        "rule_id": "MISS-006",
        "intent_keywords": [
            "water", "moisture", "soil", "humidity", "wet", "dry",
            "水", "濕度", "土壤", "乾", "濕", "澆",
        ],
        "required_category": "Sensor-SoilMoisture",
        "reason_zh": "偵測水分/土壤濕度需要土壤感測器",
        "reason_en": "Moisture/soil detection requires a soil moisture sensor",
    },
    {
        "rule_id": "MISS-007",
        "intent_keywords": [
            "gas", "smoke", "air quality", "co2", "carbon", "pollution",
            "氣體", "煙", "空氣品質", "一氧化碳", "煙霧",
        ],
        "required_category": "Sensor-Gas",
        "reason_zh": "偵測氣體/煙霧需要氣體感測器",
        "reason_en": "Gas/smoke detection requires a gas sensor",
    },
    {
        "rule_id": "MISS-008",
        "intent_keywords": [
            "gps", "location", "position", "latitude", "longitude", "navigation",
            "定位", "位置", "經緯度", "導航", "座標",
        ],
        "required_category": "Module-GPS",
        "reason_zh": "定位/導航需要 GPS 模組",
        "reason_en": "Location/navigation requires a GPS module",
    },
]

# ---------------------------------------------------------------------------
# C. 長時運轉意圖模式表（pattern, 期望最低時數）
# ---------------------------------------------------------------------------

LONG_RUN_PATTERNS: list[tuple[str, float]] = [
    (r"一個月|1個月|thirty.?day|30.?day", 720.0),   # 30 天
    (r"整天|全天|24小時|24h|all.?day|whole.?day", 24.0),
    (r"省電|low.?power|energy.?saving|battery.?sav", 24.0),
    (r"long.?run|持久|連續運作|不斷電", 24.0),
    (r"一週|一周|7.?day|week.?long", 168.0),         # 7 天
    (r"兩天|48.?hour|two.?day", 48.0),
]
