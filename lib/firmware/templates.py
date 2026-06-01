"""
templates.py — Shared constants, reaction rules, and per-component test code templates.

Per-component test code generators (_tc_* functions + TEST_TEMPLATES dict) are in
test_code_templates.py; imported here for backward compatibility.
"""
from __future__ import annotations

from .test_code_templates import TEST_TEMPLATES  # re-export


# ===================================================================
# SHARED UTILITIES
# ===================================================================

def _wrap_text(text: str, width: int = 58) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    cur = ""
    cur_w = 0
    for ch in text:
        w = 2 if ord(ch) > 127 else 1
        if cur_w + w > width and cur:
            out.append(cur)
            cur = ""
            cur_w = 0
        cur += ch
        cur_w += w
    if cur:
        out.append(cur)
    return out


def stem_header_lines(
    outputs: list[str], sensors: list[str],
    project_name: str = "", plan: str = "",
    comment_prefix: str = "//",
) -> list[str]:
    try:
        from ..config import EDUCATIONAL_RATIONALE_TEMPLATES
    except ImportError:
        try:
            from config import EDUCATIONAL_RATIONALE_TEMPLATES
        except ImportError:
            EDUCATIONAL_RATIONALE_TEMPLATES = {}

    p = comment_prefix
    lines: list[str] = []

    if project_name or plan:
        lines.append(f"{p} --- 專案背景 -------------------------------------------")
        if project_name:
            lines.append(f"{p} 專題：{project_name}")
        if plan:
            for chunk in _wrap_text(plan, width=58):
                lines.append(f"{p} {chunk}")
        lines.append("")

    all_comps = list(dict.fromkeys(outputs + sensors))
    rationale_pairs: list[tuple[str, str]] = []
    for c in all_comps:
        for key in (c, f"{c}-class"):
            if key in EDUCATIONAL_RATIONALE_TEMPLATES:
                rationale_pairs.append((c, EDUCATIONAL_RATIONALE_TEMPLATES[key]))
                break

    if rationale_pairs:
        lines.append(f"{p} --- STEM 學習點 ----------------------------------------")
        for comp, text in rationale_pairs:
            lines.append(f"{p} • {comp}：{text}")
        lines.append("")

    return lines


# ===================================================================
# REACTION RULES
# ===================================================================

REACTION_RULES: dict[tuple[str, str], dict[str, str]] = {
    ("SoilMoisture", "Relay"):      {"condition": "soilPct < 40",
                                     "action":    "digitalWrite(RELAY_PIN, LOW);  // Active-LOW ON",
                                     "else":      "digitalWrite(RELAY_PIN, HIGH);",
                                     "label":     "土壤濕度 < 40% → 繼電器導通"},
    ("PIR", "Buzzer"):              {"condition": "motion == 1",
                                     "action":    "tone(BUZZER_PIN, 1000, 200);",
                                     "else":      "noTone(BUZZER_PIN);",
                                     "label":     "偵測到人體 → 蜂鳴器警報"},
    ("PIR", "LED_Single"):          {"condition": "motion == 1",
                                     "action":    "digitalWrite(LED_PIN, HIGH);",
                                     "else":      "digitalWrite(LED_PIN, LOW);",
                                     "label":     "偵測到人體 → LED 亮起"},
    ("PIR", "Relay"):               {"condition": "motion == 1",
                                     "action":    "digitalWrite(RELAY_PIN, LOW);",
                                     "else":      "digitalWrite(RELAY_PIN, HIGH);",
                                     "label":     "偵測到人體 → 繼電器導通"},
    ("PIR", "NeoPixel"):            {"condition": "motion == 1",
                                     "action":    "strip.fill(strip.Color(255,0,0)); strip.show();",
                                     "else":      "strip.fill(strip.Color(0,0,0)); strip.show();",
                                     "label":     "偵測到人體 → NeoPixel 紅色警示"},
    ("Ultrasonic", "Buzzer"):       {"condition": "dist_cm < 20",
                                     "action":    "tone(BUZZER_PIN, 1500, 100);",
                                     "else":      "noTone(BUZZER_PIN);",
                                     "label":     "距離 < 20cm → 蜂鳴器提示"},
    ("Ultrasonic", "LED_Single"):   {"condition": "dist_cm < 20",
                                     "action":    "digitalWrite(LED_PIN, HIGH);",
                                     "else":      "digitalWrite(LED_PIN, LOW);",
                                     "label":     "距離 < 20cm → LED 亮起"},
    ("Ultrasonic", "Servo"):        {"condition": "dist_cm < 30",
                                     "action":    "myServo.write(90);",
                                     "else":      "myServo.write(0);",
                                     "label":     "距離 < 30cm → 伺服馬達 90°"},
    ("Light", "LED_Single"):        {"condition": "lightPct < 30",
                                     "action":    "digitalWrite(LED_PIN, HIGH);",
                                     "else":      "digitalWrite(LED_PIN, LOW);",
                                     "label":     "光線 < 30% → LED 自動亮燈"},
    ("Light", "NeoPixel"):          {"condition": "lightPct < 30",
                                     "action":    "strip.fill(strip.Color(255,180,50)); strip.show();",
                                     "else":      "strip.fill(strip.Color(0,0,0)); strip.show();",
                                     "label":     "光線 < 30% → NeoPixel 暖光"},
    ("Light", "Relay"):             {"condition": "lightPct < 30",
                                     "action":    "digitalWrite(RELAY_PIN, LOW);",
                                     "else":      "digitalWrite(RELAY_PIN, HIGH);",
                                     "label":     "光線 < 30% → 繼電器導通（開燈）"},
    ("TempHumid", "Buzzer"):        {"condition": "temp > 35.0",
                                     "action":    "tone(BUZZER_PIN, 2000, 300);",
                                     "else":      "noTone(BUZZER_PIN);",
                                     "label":     "溫度 > 35°C → 蜂鳴器高溫警報"},
    ("TempHumid", "Relay"):         {"condition": "temp > 30.0",
                                     "action":    "digitalWrite(RELAY_PIN, LOW);  // 啟動風扇",
                                     "else":      "digitalWrite(RELAY_PIN, HIGH);",
                                     "label":     "溫度 > 30°C → 繼電器導通（風扇）"},
    ("TempHumid", "DCMotor"):       {"condition": "temp > 30.0",
                                     "action":    "digitalWrite(MOTOR_IN1,HIGH); digitalWrite(MOTOR_IN2,LOW); analogWrite(MOTOR_EN,200);",
                                     "else":      "analogWrite(MOTOR_EN, 0);",
                                     "label":     "溫度 > 30°C → 直流馬達啟動（風扇）"},
    ("Ultrasonic", "Stepper"):      {"condition": "dist_cm < 30",
                                     "action":    "myStepper.step(stepPerRev / 4);  // 正轉 90°",
                                     "else":      "// 步進馬達：等待觸發",
                                     "label":     "距離 < 30cm → 步進馬達正轉 90°"},
    ("PIR", "Stepper"):             {"condition": "motion == 1",
                                     "action":    "myStepper.step(stepPerRev / 2);  // 正轉 180°",
                                     "else":      "// 步進馬達：等待觸發",
                                     "label":     "偵測到人體 → 步進馬達正轉 180°"},
    ("Light", "Stepper"):           {"condition": "lightPct < 30",
                                     "action":    "myStepper.step(stepPerRev / 4);  // 調整角度",
                                     "else":      "myStepper.step(-stepPerRev / 4);",
                                     "label":     "光線 < 30% → 步進馬達調整角度"},
}

for _rk, _rv in list(REACTION_RULES.items()):
    if _rk[1] == "Buzzer":
        REACTION_RULES[(_rk[0], "Buzzer_Active")] = _rv
        REACTION_RULES[(_rk[0], "Buzzer_Passive")] = _rv

OUTPUT_FALLBACK: dict[str, str] = {
    "LED_Single": "digitalWrite(LED_PIN, !digitalRead(LED_PIN));  // LED 翻轉",
    "LED_RGB":    "analogWrite(LED_R, 0); analogWrite(LED_G, 150); analogWrite(LED_B, 255);",
    "NeoPixel":   "strip.fill(strip.Color(0,150,255)); strip.show();",
    "Buzzer_Active":  "digitalWrite(BUZZER_PIN, HIGH); delay(200); digitalWrite(BUZZER_PIN, LOW);",
    "Buzzer_Passive": "tone(BUZZER_PIN, 440, 200);",
    "Servo":      "myServo.write(90);",
    "DCMotor":    "digitalWrite(MOTOR_IN1,HIGH); digitalWrite(MOTOR_IN2,LOW); analogWrite(MOTOR_EN,200);",
    "Stepper":    "myStepper.step(stepPerRev / 4);  // 正轉 90°",
    "Relay":      "// Relay: 等待感測器觸發",
    "Pump":       "// Pump: 等待感測器觸發",
    "Speaker":    "// DFPlayer: 等待觸發指令",
}


def match_reactions(sensors: list[str], outputs: list[str]) -> tuple[list[dict], set[str]]:
    matched = []
    handled: set[str] = set()
    for s in sensors:
        for o in outputs:
            rule = REACTION_RULES.get((s, o))
            if rule:
                matched.append({"sensor": s, "output": o, **rule})
                handled.add(o)
    return matched, handled
