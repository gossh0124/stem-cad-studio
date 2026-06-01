"""data_generator_b_helpers.py — LoRA-B C 案資料生成器的常數/工具。

從 data_generator_b.py 分出（保持主檔 < 500 行，CLAUDE.md 規則）。
此模組僅含：scope filter、SSOT 元件物理屬性、enum、_CATEGORY_TEMPLATES、
helpers（role / face_out / placement_reason / enclosure_relation / template vary）。
"""
from __future__ import annotations
import functools
import random
from typing import Dict, Any, List

try:
    from lib.config import TAXONOMY_CONFIG
except ImportError:
    # Colab fallback（cwd=training/）
    from config import TAXONOMY_CONFIG

# ── Scope filter（M2: 與 data_generator.py M1 同步）────────
_MULTIAXIS_TYPES_B = {
    "Motor-Servo-class", "Motor-Stepper-class",
}


def _template_in_scope(template: Dict[str, Any]) -> bool:
    """LoRA-B template scope filter（M2）：env 不可為 outdoor_*；aux 多軸 ≤ 1。"""
    env = template.get("env", "")
    if env.startswith("outdoor"):
        return False
    aux = template.get("aux", [])
    multiaxis_count = sum(1 for c in aux if c in _MULTIAXIS_TYPES_B)
    return multiaxis_count <= 1


# ── SSOT 元件物理屬性 — 從 lib.specs 讀穿（SSOT20，不再硬編）──
# 唯一真值：data/component_datasheet_verified.json -> lib.specs 合併 cache。
# CURRENT_MA 即 specs.POWER_MA（消耗電流）；WEIGHT_G / THERMAL_MW 同源。
# 不再各自硬編（消除 Battery-LiPo 25 vs 22、TempHumid current 2.5 vs 1.5 等漂移）。
try:
    from lib.specs import WEIGHT_G, THERMAL_MW, POWER_MA as CURRENT_MA
except ImportError:
    try:
        from specs import WEIGHT_G, THERMAL_MW, POWER_MA as CURRENT_MA  # Colab: repo root on path
    except ImportError:
        import sys as _sys
        print(
            "[data_generator_b_helpers] WARNING: lib.specs 不可用 — WEIGHT_G/"
            "THERMAL_MW/CURRENT_MA 降級為空 dict，placement_reason 改用預設值。"
            "Colab 請確認 repo root + data/ 在 sys.path（非靜默：本訊息即告警）。",
            file=_sys.stderr,
        )
        WEIGHT_G = {}
        THERMAL_MW = {}
        CURRENT_MA = {}

# ── Enum（與 CH3_HIERARCHICAL_SPEC §3.1 對齊）──────────────
ZONES = [
    "top-center", "top-left", "top-right",
    "mid-center", "mid-left", "mid-right",
    "bottom-center", "bottom-left", "bottom-right",
    "bottom-probe",
]
FACE_OUTS = ["side-front", "side-back", "side-left", "side-right",
             "top", "bottom", "face"]
ENVIRONMENTS: List[Dict[str, Any]] = [
    {"name": "indoor_desktop", "waterproof": False, "ip": "IP20",
     "sealed": [], "exposed": []},
    {"name": "indoor_humid", "waterproof": False, "ip": "IP20",
     "sealed": [], "exposed": ["sensor_zone"]},
    {"name": "soil_contact", "waterproof": False, "ip": "IP20",
     "sealed": [], "exposed": ["soil_probe"]},
]
LID_METHODS = ["snap_fit_4x", "snap_fit_2x", "screw_4x_M3", "screw_4x_M2.5",
               "friction_fit", "magnetic_4x"]
BASE_METHODS = ["screw_boss_4x_M3", "screw_boss_4x_M2.5",
                "adhesive_pad", "belt_clip"]
CABLE_PATHS = ["channel_bottom", "channel_side", "channel_isolated",
               "direct", "flex_cable"]
VENT_PLACEMENTS = ["side_lower", "side_upper", "top_grid",
                   "bottom_holes", "perimeter"]

# vent strategy → 主要朝外面（params.vent_placements[].face）
VENT_FACE_FOR_STRATEGY: Dict[str, str] = {
    "side_vent_passive": "side-front",
    "top_vent_passive":  "top",
    "bottom_vent_passive": "bottom",
    "active_fan": "side-back",
    "no_vent": "",
}

# ── 每個 category 的典型專案模板 ──────────────────────────
CATEGORY_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "Gardening": [
        {"name": "auto_plant_waterer", "brain": "Arduino-Uno-class",
         "power": "USB-5V-class", "control": "Button-class",
         "aux": ["Sensor-SoilMoisture-class", "Pump-Water-class", "Relay-Module-class"],
         "env": "soil_contact"},
        {"name": "greenhouse_monitor", "brain": "ESP32-class",
         "power": "USB-5V-class", "control": "Button-class",
         "aux": ["Sensor-TempHumid-class", "Sensor-Light-class", "Display-OLED-class"],
         "env": "indoor_humid"},
        {"name": "plant_care_station", "brain": "Microbit-class",
         "power": "USB-Adapter-class", "control": "Switch-Generic-class",
         "aux": ["Sensor-SoilMoisture-class", "Pump-Water-class", "Display-OLED-class"],
         "env": "soil_contact"},
        {"name": "herb_garden_timer", "brain": "Arduino-Uno-class",
         "power": "USB-5V-class", "control": "Potentiometer-class",
         "aux": ["Pump-Water-class", "Relay-Module-class", "Display-LCD-class"],
         "env": "soil_contact"},
        {"name": "grow_light_station", "brain": "ESP32-class",
         "power": "USB-Adapter-class", "control": "Button-class",
         "aux": ["Sensor-Light-class", "Sensor-TempHumid-class",
                  "Lighting-LED-Strip-class", "Display-OLED-class"],
         "env": "indoor_humid"},
    ],
    "Smart_Home": [
        {"name": "smart_lamp", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Sensor-Light-class", "Lighting-NeoPixel-class"],
         "env": "indoor_desktop"},
        {"name": "motion_alarm", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Switch-class",
         "aux": ["Sensor-PIR-class", "Buzzer-Active-class", "Lighting-LED-RGB-class"],
         "env": "indoor_desktop"},
        {"name": "temp_display", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Sensor-TempHumid-class", "Display-OLED-class"],
         "env": "indoor_desktop"},
        {"name": "smart_humidifier", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Potentiometer-class",
         "aux": ["Sensor-TempHumid-class", "Mist-Atomizer-class", "Display-OLED-class"],
         "env": "indoor_humid"},
        {"name": "led_strip_controller", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Potentiometer-class",
         "aux": ["Lighting-LED-Strip-class", "Sensor-IR-class"],
         "env": "indoor_desktop"},
    ],
    "Robotics": [
        {"name": "obstacle_car", "brain": "Arduino-Uno-class", "power": "Battery-AA-class",
         "control": "Remote-class",
         "aux": ["Motor-DC-class", "Motor-DC-class", "Sensor-Ultrasonic-class",
                  "Chassis-Car-class"], "env": "indoor_desktop"},
        {"name": "servo_turret", "brain": "Arduino-Uno-class", "power": "Battery-AA-class",
         "control": "Joystick-class",
         "aux": ["Motor-Servo-class", "Sensor-Ultrasonic-class", "Buzzer-Passive-class"],
         "env": "indoor_desktop"},
        {"name": "line_follower", "brain": "Arduino-Uno-class", "power": "Battery-AA-class",
         "control": "Switch-class",
         "aux": ["Motor-DC-class", "Motor-DC-class", "Sensor-IR-class",
                  "Sensor-IR-class", "Chassis-Car-class"], "env": "indoor_desktop"},
        {"name": "pan_tracker", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Joystick-class",
         "aux": ["Motor-Servo-class", "Sensor-Ultrasonic-class", "Display-OLED-class"],
         "env": "indoor_desktop"},
        {"name": "sorting_pusher", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Motor-Servo-class", "Sensor-IR-class", "Sensor-Light-class",
                  "Buzzer-Passive-class"], "env": "indoor_desktop"},
    ],
    "Interactive_Art": [
        {"name": "music_box", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["MP3-Module-class", "Speaker-class", "Lighting-NeoPixel-class"],
         "env": "indoor_desktop"},
        {"name": "mist_lamp", "brain": "ESP32-class", "power": "AC-Adapter-class",
         "control": "Potentiometer-class",
         "aux": ["Mist-Ultrasonic-class", "Lighting-NeoPixel-class"],
         "env": "indoor_desktop"},
        {"name": "freq_visualizer", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Sensor-MSGEQ7-class", "LED-Matrix-class", "Lighting-LED-PWM-class"],
         "env": "indoor_desktop"},
        {"name": "rotating_display", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Motor-Stepper-class", "Lighting-NeoPixel-class"],
         "env": "indoor_desktop"},
    ],
    "Security": [
        {"name": "door_sensor", "brain": "ESP32-class", "power": "Battery-LiPo-class",
         "control": "Switch-class",
         "aux": ["Sensor-PIR-class", "Buzzer-Active-class"], "env": "indoor_desktop"},
        {"name": "perimeter_guard", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Switch-class",
         "aux": ["Sensor-IR-class", "Sensor-Ultrasonic-class", "Buzzer-Active-class",
                  "Lighting-LED-Strip-class"], "env": "indoor_desktop"},
        {"name": "access_keypad", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Motor-Servo-class", "Buzzer-Passive-class", "Display-OLED-class"],
         "env": "indoor_desktop"},
        {"name": "motion_alert_light", "brain": "ESP32-class", "power": "USB-5V-class",
         "control": "Switch-Generic-class",
         "aux": ["Sensor-PIR-class", "Lighting-NeoPixel-class", "Buzzer-Active-class",
                  "Display-OLED-class"], "env": "indoor_desktop"},
        {"name": "safe_box", "brain": "Arduino-Uno-class", "power": "Battery-AA-class",
         "control": "Button-class",
         "aux": ["Motor-Servo-class", "Buzzer-Active-class", "Lighting-LED-PWM-class"],
         "env": "indoor_desktop"},
        {"name": "distance_alarm", "brain": "Microbit-class", "power": "Battery-LiPo-class",
         "control": "Button-class",
         "aux": ["Sensor-Ultrasonic-class", "Buzzer-Passive-class",
                  "Lighting-LED-RGB-class"], "env": "indoor_desktop"},
    ],
    "Education": [
        {"name": "weather_station", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Sensor-TempHumid-class", "Display-LCD-class"], "env": "indoor_desktop"},
        {"name": "eink_weather", "brain": "ESP32-class", "power": "Battery-LiPo-class",
         "control": "Button-class",
         "aux": ["Sensor-TempHumid-class", "Display-EInk-class"], "env": "indoor_desktop"},
        {"name": "sensor_lab", "brain": "RaspberryPi-class", "power": "USB-Adapter-class",
         "control": "Switch-Generic-class",
         "aux": ["Sensor-Ultrasonic-class", "Sensor-Light-class", "Display-LCD-class"],
         "env": "indoor_desktop"},
        {"name": "sound_meter", "brain": "Arduino-Uno-class", "power": "USB-5V-class",
         "control": "Button-class",
         "aux": ["Sensor-MSGEQ7-class", "Display-OLED-class", "Lighting-LED-PWM-class"],
         "env": "indoor_desktop"},
        {"name": "reaction_timer", "brain": "Microbit-class", "power": "Battery-AA-class",
         "control": "Button-class",
         "aux": ["Lighting-LED-RGB-class", "Buzzer-Active-class", "Display-LCD-class"],
         "env": "indoor_desktop"},
    ],
}

# ── 元件屬性 helpers ───────────────────────────────────────
_ROLE_OF: Dict[str, str] = {
    t: r
    for r, types in TAXONOMY_CONFIG["component_taxonomy"].items()
    for t in types
}


def _load_registry_once() -> dict:
    """載入 COMPONENT_REGISTRY 一次，返回 mapping。

    載入順序（任一成功即用）：
      1. lib.registry.COMPONENT_REGISTRY（本地 repo root 可 import）
      2. training/_registry_enclosure_relation.json（Colab Drive 自包含 snapshot）
      3. 返回空 dict + stderr WARNING（兩條都掛才走，避免 silent）
    """
    try:
        from lib.registry import COMPONENT_REGISTRY
        return dict(COMPONENT_REGISTRY)
    except ImportError:
        pass
    # 路徑 2：fallback 讀 training/ 內 JSON snapshot（Colab Drive 環境）
    import json as _json
    from pathlib import Path as _Path
    snapshot = _Path(__file__).resolve().parent / "_registry_enclosure_relation.json"
    try:
        _mapping = _json.loads(snapshot.read_text(encoding="utf-8"))["mapping"]
        return {k: {"enclosure_relation": v} for k, v in _mapping.items()}
    except (FileNotFoundError, KeyError, _json.JSONDecodeError) as e:
        import sys as _sys
        print(
            f"[data_generator_b_helpers] WARNING: lib.registry import 失敗 "
            f"且 _registry_enclosure_relation.json 也讀不到 ({e}) — "
            f"enclosure_relation 全 fallback 為 'internal'，訓練資料將無 v2 schema 多樣性。"
            f"請確認 sys.path 含 repo root，或 training/_registry_enclosure_relation.json 在位。",
            file=_sys.stderr,
        )
        return {}


_REGISTRY_CACHE: dict = _load_registry_once()


@functools.lru_cache(maxsize=256)
def enclosure_relation_for(ctype: str) -> str:
    """v2 commit f915b7c：從 lib.registry SSOT 查 enclosure_relation（模組載入時一次性載入）。"""
    entry = _REGISTRY_CACHE.get(ctype)
    if entry is None:
        return "internal"
    # 兼容 ComponentSpec 物件 (有 .enclosure_relation 屬性) 或 dict (snapshot 模式)
    if isinstance(entry, dict):
        return entry.get("enclosure_relation", "internal")
    return getattr(entry, "enclosure_relation", "internal")


def role_of(ctype: str) -> str:
    return _ROLE_OF.get(ctype, "Structural")


def face_out_for(ctype: str) -> str:
    if "Display" in ctype or "LED" in ctype or "Matrix" in ctype:
        return "face"
    if "Sensor-PIR" in ctype or "Sensor-Ultrasonic" in ctype:
        return "side-front"
    if "Sensor-SoilMoisture" in ctype:
        return "bottom"
    if "USB" in ctype or "Battery" in ctype:
        return random.choice(["side-back", "bottom"])
    if "Pump" in ctype:
        return "bottom"
    if "Buzzer" in ctype or "Speaker" in ctype:
        return "top"
    return random.choice(["side-front", "side-back", "side-left", "side-right"])


def placement_reason(ctype: str, zone: str) -> str:
    w = WEIGHT_G.get(ctype, 10.0)
    t = THERMAL_MW.get(ctype, 0.0)
    reasons = []
    if w >= 30:
        reasons.append(f"重量 {w}g 較重，放底部穩定重心")
    if t >= 1500:
        reasons.append(f"發熱 {t}mW 較高，需靠近通風口")
    if "Sensor" in ctype:
        reasons.append("感測器朝外方便偵測")
    if "Display" in ctype or "LED" in ctype:
        reasons.append("顯示/燈光元件朝使用者面")
    if "USB" in ctype or "Battery" in ctype:
        reasons.append("電源/USB 朝可維護面")
    if "Pump" in ctype:
        reasons.append("水泵靠底部接近水源")
    if "Motor" in ctype:
        reasons.append("馬達軸心對齊運動方向")
    if not reasons:
        reasons.append(f"放置於 {zone} 平衡佈局")
    return "；".join(reasons[:2])


def vary_template(template: Dict[str, Any]) -> Dict[str, Any]:
    """對模板進行隨機變化以增加多樣性（M2 scope 縮限後）。"""
    t = dict(template)
    t["aux"] = list(template["aux"])
    if random.random() < 0.3:
        _brains = TAXONOMY_CONFIG["component_taxonomy"]["Brain"]
        _brain_w = [0.05 if "RaspberryPi" in b else (0.95 / (len(_brains) - 1)) for b in _brains]
        t["brain"] = random.choices(_brains, weights=_brain_w, k=1)[0]
    if random.random() < 0.2:
        t["power"] = random.choice(TAXONOMY_CONFIG["component_taxonomy"]["Power"])
    if random.random() < 0.3 and len(t["aux"]) > 1:
        t["aux"].pop(random.randint(0, len(t["aux"]) - 1))
    if random.random() < 0.3:
        pool = []
        for role, types in TAXONOMY_CONFIG["component_taxonomy"].items():
            if role not in ("Brain", "Power", "Control"):
                pool.extend(types)
        t["aux"].append(random.choice(pool))
    if random.random() < 0.2:
        t["env"] = random.choice([e["name"] for e in ENVIRONMENTS])

    if not _template_in_scope(t):
        kept, used = [], False
        for c in t["aux"]:
            if c in _MULTIAXIS_TYPES_B:
                if used:
                    continue
                used = True
            kept.append(c)
        t["aux"] = kept
        if t.get("env", "").startswith("outdoor"):
            t["env"] = "indoor_desktop"
    return t


def components_of(template: Dict[str, Any]) -> List[str]:
    return [template["brain"], template["power"], template["control"]] + list(template["aux"])


def env_cfg_of(template: Dict[str, Any]) -> Dict[str, Any]:
    return next(
        (e for e in ENVIRONMENTS if e["name"] == template.get("env", "indoor_desktop")),
        ENVIRONMENTS[0],
    )
