"""tests/test_feasibility.py — lib/feasibility.py 驗收測試。

四項確定性測試（不依賴 LLM、不碰 live pipeline）：
  (a) servo-輪子 bridge → ≥1 Motor-Servo error
  (b) RaspberryPi + Battery-AA + 省電一個月 → ≥1 能量 error，印 runtime_hours
  (c) MP3 意圖但只有蜂鳴器 → ≥1 buzzer warning
  (d) 正常合理 bridge → 零 error（無誤報）

解析錨點 assert：
  Battery-AA  capacity_mah == 2500
  Battery-LiPo capacity_mah == 1000

執行：
  .venv/Scripts/python.exe tests/test_feasibility.py
  或 pytest tests/test_feasibility.py -v
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# 讓測試從專案根目錄找到 lib/
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.feasibility import check_feasibility, _ds_capacity_mah, check_missing_capabilities  # noqa: E402


# ---------------------------------------------------------------------------
# 解析正確性錨點
# ---------------------------------------------------------------------------

def test_datasheet_anchor_aa():
    assert _ds_capacity_mah("Battery-AA-class") == 2500


def test_datasheet_anchor_lipo():
    assert _ds_capacity_mah("Battery-LiPo-class") == 1000


# ---------------------------------------------------------------------------
# (a) Servo + 輪子 → ≥1 Motor-Servo error
# ---------------------------------------------------------------------------

_BRIDGE_A = {
    "project_name": "遙控車",
    "project_category": "robot",
    "_instruction": "用伺服馬達讓輪子連續轉動行走",
    "components": [
        {"role": "mcu", "type": "Arduino-Uno-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 50.0}},
        {"role": "actuator", "type": "Motor-Servo-class", "qty": 2,
         "spec": {"voltage_v": 5.0, "current_ma": 150.0}},
        {"role": "power", "type": "Battery-AA-class", "qty": 1,
         "spec": {"voltage_v": 3.0, "current_ma": None}},
    ],
}


def test_servo_wheel_error():
    issues = check_feasibility(_BRIDGE_A)
    servo_errors = [i for i in issues
                    if i["severity"] == "error" and "Motor-Servo" in i["component"]]
    assert len(servo_errors) >= 1, f"期望 ≥1 Motor-Servo error，實際：{issues}"


# ---------------------------------------------------------------------------
# (a2) Servo + 雙足步行 → CAP-001 negative-guard，不誤判 error
# 伺服做「關節角度控制」是正確用途（非驅動輪）；exclude_patterns 排除足式步行。
# ---------------------------------------------------------------------------

_BRIDGE_BIPED = {
    "project_name": "雙足機器人",
    "project_category": "robot",
    "_instruction": "用四個伺服馬達做會走路的雙足機器人，前進後退",
    "components": [
        {"role": "mcu", "type": "Arduino-Uno-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 50.0}},
        {"role": "actuator", "type": "Motor-Servo-class", "qty": 4,
         "spec": {"voltage_v": 5.0, "current_ma": 150.0}},
        {"role": "power", "type": "Battery-AA-class", "qty": 1,
         "spec": {"voltage_v": 3.0, "current_ma": None}},
    ],
}


def test_servo_biped_no_false_positive():
    """CAP-001 exclude_patterns：雙足步行用伺服做關節控制，不應誤判為 servo error。"""
    issues = check_feasibility(_BRIDGE_BIPED)
    servo_errors = [i for i in issues
                    if i["severity"] == "error" and "Motor-Servo" in i.get("component", "")]
    assert len(servo_errors) == 0, f"雙足步行不應觸發 CAP-001 servo error，實際：{servo_errors}"


# ---------------------------------------------------------------------------
# (b) RaspberryPi + Battery-AA + 省電一個月 → ≥1 能量 error + runtime_hours
# ---------------------------------------------------------------------------

_BRIDGE_B = {
    "project_name": "智慧農場",
    "project_category": "iot",
    "_instruction": "用樹莓派控制，省電跑一個月不關機",
    "components": [
        {"role": "mcu", "type": "RaspberryPi-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 600.0}},
        {"role": "power", "type": "Battery-AA-class", "qty": 1,
         "spec": {"voltage_v": 3.0, "current_ma": None}},
        {"role": "sensor", "type": "Sensor-TempHumid-class", "qty": 1,
         "spec": {"voltage_v": 3.3, "current_ma": 1.5}},
    ],
}


def test_rpi_battery_energy_error():
    issues = check_feasibility(_BRIDGE_B)
    energy_errors = [i for i in issues
                     if i["severity"] == "error" and "電池續航" in i["issue"]]
    assert len(energy_errors) >= 1, f"期望 ≥1 能量 error，實際：{issues}"

    # 確認 issue 文字中含有算出的 runtime_hours
    match = re.search(r"約 ([\d.]+) 小時", energy_errors[0]["issue"])
    assert match is not None, "energy error 中應包含『約 N.N 小時』字串"
    runtime_h = float(match.group(1))
    # 理論值：2500mAh / (600 + 1.5)mA ≈ 4.15h，應遠低於 720h
    assert runtime_h < 50, f"runtime_hours 應 <50h，實際 {runtime_h}"


# ---------------------------------------------------------------------------
# (c) MP3 意圖 + 只有蜂鳴器 → ≥1 buzzer warning
# ---------------------------------------------------------------------------

_BRIDGE_C = {
    "project_name": "音樂盒",
    "project_category": "music",
    "_instruction": "播放音樂，想要放 mp3 歌曲",
    "components": [
        {"role": "mcu", "type": "Arduino-Uno-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 50.0}},
        {"role": "output", "type": "Buzzer-Active-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 30.0}},
        {"role": "power", "type": "Battery-AA-class", "qty": 1,
         "spec": {"voltage_v": 3.0, "current_ma": None}},
    ],
}


def test_buzzer_mp3_warning():
    issues = check_feasibility(_BRIDGE_C)
    buzzer_warnings = [i for i in issues
                       if i["severity"] == "warning" and "Buzzer" in i["component"]]
    assert len(buzzer_warnings) >= 1, f"期望 ≥1 buzzer warning，實際：{issues}"


# ---------------------------------------------------------------------------
# (d) 正常合理 bridge → 零 error（無誤報）
# ---------------------------------------------------------------------------

_BRIDGE_D = {
    "project_name": "自動澆水系統",
    "project_category": "agriculture",
    "_instruction": "偵測土壤濕度，太乾就自動開水泵澆水，OLED 顯示狀態",
    "components": [
        {"role": "mcu", "type": "Arduino-Uno-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 50.0}},
        {"role": "sensor", "type": "Sensor-SoilMoisture-class", "qty": 1,
         "spec": {"voltage_v": 3.3, "current_ma": 5.0}},
        {"role": "actuator", "type": "Pump-Water-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 220.0}},
        {"role": "driver", "type": "Relay-Module-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": 80.0}},
        {"role": "display", "type": "Display-OLED-class", "qty": 1,
         "spec": {"voltage_v": 3.3, "current_ma": 20.0}},
        {"role": "power", "type": "AC-Adapter-class", "qty": 1,
         "spec": {"voltage_v": 5.0, "current_ma": None}},
    ],
}


def test_normal_bridge_zero_errors():
    issues = check_feasibility(_BRIDGE_D)
    errors = [i for i in issues if i["severity"] == "error"]
    assert len(errors) == 0, f"正常 bridge 不應有 error，實際：{errors}"


# ---------------------------------------------------------------------------
# (e) 缺少能力偵測測試（MISSING_CAPABILITY_RULES）
# ---------------------------------------------------------------------------

# 共用元件基底（MCU + 電源，不含感測器）
_BASE_COMPONENTS = [
    {"role": "mcu",   "type": "Arduino-Uno-class", "qty": 1,
     "spec": {"voltage_v": 5.0, "current_ma": 50.0}},
    {"role": "power", "type": "AC-Adapter-class",   "qty": 1,
     "spec": {"voltage_v": 5.0, "current_ma": None}},
]


def test_missing_light_sensor_flagged():
    """意圖含 'night'，元件無光感測器 → 應回報 Sensor-Light warning。"""
    issues = check_missing_capabilities(
        "晚上自動亮的燈，天黑就打開",
        _BASE_COMPONENTS,
    )
    missing = [i for i in issues if i["missing_component"] == "Sensor-Light"]
    assert len(missing) >= 1, f"期望 Sensor-Light warning，實際：{issues}"


def test_light_sensor_present_ok():
    """意圖含 'night'，且元件清單已有 Sensor-Light → 不應回報。"""
    components = _BASE_COMPONENTS + [
        {"role": "sensor", "type": "Sensor-Light-class", "qty": 1,
         "spec": {"voltage_v": 3.3, "current_ma": 1.0}},
    ]
    issues = check_missing_capabilities(
        "night light automatic — 自動感光夜燈",
        components,
    )
    missing = [i for i in issues if i["missing_component"] == "Sensor-Light"]
    assert len(missing) == 0, f"Sensor-Light 已存在，不應回報，實際：{issues}"


def test_missing_temp_sensor_flagged():
    """意圖含 'temperature'，元件無溫度感測器 → 應回報 Sensor-TempHumid warning。"""
    issues = check_missing_capabilities(
        "monitor temperature and alert when hot",
        _BASE_COMPONENTS,
    )
    missing = [i for i in issues if i["missing_component"] == "Sensor-TempHumid"]
    assert len(missing) >= 1, f"期望 Sensor-TempHumid warning，實際：{issues}"


def test_no_relevant_keywords_ok():
    """意圖不含任何規則關鍵字 → 零 warning。"""
    issues = check_missing_capabilities(
        "讓 LED 閃爍，按鈕控制開關",
        _BASE_COMPONENTS,
    )
    assert len(issues) == 0, f"無關鍵字不應有 warning，實際：{issues}"


def test_chinese_keywords_work():
    """中文關鍵字觸發 → 回報對應 warning（光感測器）。"""
    issues = check_missing_capabilities(
        "晚上自動亮的燈，偵測照度控制亮暗",
        _BASE_COMPONENTS,
    )
    missing = [i for i in issues if i["missing_component"] == "Sensor-Light"]
    assert len(missing) >= 1, f"中文關鍵字應觸發 Sensor-Light warning，實際：{issues}"


def test_multiple_missing():
    """意圖同時觸發 2 條規則（light + temperature），兩者皆缺 → 皆應回報。"""
    issues = check_missing_capabilities(
        "night temperature monitor — 夜間溫度監控自動燈",
        _BASE_COMPONENTS,
    )
    cats = {i["missing_component"] for i in issues}
    assert "Sensor-Light" in cats, f"Sensor-Light 應被回報，實際 cats：{cats}"
    assert "Sensor-TempHumid" in cats, f"Sensor-TempHumid 應被回報，實際 cats：{cats}"


# 整合測試：check_feasibility 也應包含缺少能力警告
def test_feasibility_integrates_missing_capability():
    """check_feasibility 對 '晚上亮燈' bridge 應回傳 Sensor-Light warning。"""
    bridge = {
        "project_name": "夜燈",
        "project_category": "automation",
        "_instruction": "晚上自動亮的燈，天黑就打開，天亮就關閉",
        "components": _BASE_COMPONENTS,
    }
    issues = check_feasibility(bridge)
    missing = [i for i in issues if i.get("missing_component") == "Sensor-Light"]
    assert len(missing) >= 1, f"check_feasibility 應整合 Sensor-Light warning，實際：{issues}"


# ---------------------------------------------------------------------------
# 直接執行時：印出詳細驗收報告
# ---------------------------------------------------------------------------

def _run_report() -> None:
    print("=" * 70)
    print("lib/feasibility.py 驗收測試")
    print("=" * 70)

    aa_cap = _ds_capacity_mah("Battery-AA-class")
    lipo_cap = _ds_capacity_mah("Battery-LiPo-class")
    assert aa_cap == 2500
    assert lipo_cap == 1000
    print(f"[ANCHOR] Battery-AA  capacity_mah = {aa_cap} mAh  OK")
    print(f"[ANCHOR] Battery-LiPo capacity_mah = {lipo_cap} mAh  OK")
    print()

    all_pass = True

    def _check(label: str, fn):
        nonlocal all_pass
        try:
            fn()
            print(f"  PASS  {label}")
            return True
        except AssertionError as exc:
            print(f"  FAIL  {label} - {exc}")
            all_pass = False
            return False

    # (a)
    print("--- (a) Servo 輪子 bridge ---")
    issues_a = check_feasibility(_BRIDGE_A)
    servo_errors = [i for i in issues_a if i["severity"] == "error" and "Motor-Servo" in i["component"]]
    if _check(">=1 Motor-Servo error", test_servo_wheel_error):
        for e in servo_errors:
            print(f"         {e['issue'][:80]}")
    print()

    # (b)
    print("--- (b) RaspberryPi + Battery-AA + 省電一個月 ---")
    issues_b = check_feasibility(_BRIDGE_B)
    energy_errors = [i for i in issues_b if i["severity"] == "error" and "電池續航" in i["issue"]]
    if _check(">=1 能量 error + runtime_hours", test_rpi_battery_energy_error):
        match = re.search(r"約 ([\d.]+) 小時", energy_errors[0]["issue"])
        runtime_h = float(match.group(1)) if match else None
        print(f"         {energy_errors[0]['issue'][:100]}")
        if runtime_h is not None:
            print(f"         算出 runtime_hours = {runtime_h:.1f} h（理論值約 4.1h）")
    print()

    # (c)
    print("--- (c) MP3 意圖 + 只有蜂鳴器 ---")
    issues_c = check_feasibility(_BRIDGE_C)
    buzzer_warnings = [i for i in issues_c if i["severity"] == "warning" and "Buzzer" in i["component"]]
    if _check(">=1 buzzer warning", test_buzzer_mp3_warning):
        for w in buzzer_warnings:
            print(f"         {w['issue'][:80]}")
    print()

    # (d)
    print("--- (d) 正常合理 bridge（Arduino + 土壤 + 水泵 + 繼電器 + OLED）---")
    issues_d = check_feasibility(_BRIDGE_D)
    errors_d = [i for i in issues_d if i["severity"] == "error"]
    warnings_d = [i for i in issues_d if i["severity"] == "warning"]
    if _check("零 error（無誤報）", test_normal_bridge_zero_errors):
        print(f"         零 error，warnings: {len(warnings_d)}（非阻斷性）")
    print()

    print("=" * 70)
    print("所有驗收測試 PASS" if all_pass else "部分驗收測試 FAIL — 請檢查上方輸出")
    print("=" * 70)


if __name__ == "__main__":
    _run_report()
