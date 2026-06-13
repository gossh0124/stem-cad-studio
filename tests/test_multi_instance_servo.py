"""tests/test_multi_instance_servo.py — 直驅多實例件(servo)配腳回歸鎖。

緣由:biped『簡易雙足機器人』(2026-06-13,取代 obstacle_car)是 16+ 範本中**首個用 4×SG90**
的 demo。wiring 引擎原以 class short name 去重(`normalize_comps` 的 seen set)→ qty:4 servo
會收斂成單一 {'Servo':{'SIG':D3}},4 顆撞同一腳 = 物理壞 demo。

修法 = **多元件 instance suffix**(Servo / Servo~2 / Servo~3 / Servo~4):bake 對直驅多實例白名單
(`_MULTI_INSTANCE_DIRECT`)展開 qty→帶 ~N 尾綴的獨立 wiring 實例,各配獨立 PWM 腳、共用 VCC/GND;
所有 class-level 查詢(SHORT_TO_CLASS / COMP_PIN_NEEDS / template / SSOT pin)以 `instance_base()` 去尾綴。
**注意**:既有 demo 測試走 TEMPLATE_DEFS 原始 type(qty 不展開),**不**觸發多實例路徑 → 本檔是
多實例能力的唯一 spec/回歸鎖(否則有人改壞 suffix 邏輯,全庫仍綠卻出 4-servo-撞-1-腳 的壞 demo)。

對應 [[StemAiAgentV3 簡易雙足機器人 demo 規格]] §6 多實例方案裁定、[[No-Silent-Fallback 設計哲學]]。
"""
from lib.canned_template_defs import TEMPLATE_DEFS
from lib.wiring import to_json
from lib.wiring.validate import validate_wiring
from lib.wiring.comp_class_map import instance_base


def test_instance_base_strips_suffix():
    assert instance_base("Servo~2") == "Servo"
    assert instance_base("Motor-Servo-class~4") == "Motor-Servo-class"
    assert instance_base("Servo") == "Servo"          # no suffix → unchanged
    assert instance_base("Sensor-Ultrasonic-class") == "Sensor-Ultrasonic-class"


def test_biped_demo_shape():
    """biped_robot 存在且為 Nano + 4×Servo + Ultrasonic + Buzzer + 6V Battery-4AA。"""
    d = TEMPLATE_DEFS["biped_robot"]
    by_role = {}
    for c in d["components"]:
        by_role.setdefault(c["role"], []).append((c["type"], c.get("qty", 1)))
    assert ("Arduino-Nano-class", 1) in by_role["Brain"]
    assert ("Battery-4AA-class", 1) in by_role["Power"]
    servos = [q for t, q in by_role["Output"] if t == "Motor-Servo-class"]
    assert servos == [4], f"biped 應有 4×Motor-Servo,實得 {servos}"
    assert ("Sensor-Ultrasonic-class", 1) in by_role["Sensor"]
    # 雙足關鍵字必在 prompt → 觸發 CAP-001 exclude_patterns(servo 非驅輪,免假陽)
    assert "雙足" in d["prompt"]


def _expand_servo(brain, base_comps, servo_qty):
    """模擬 bake 對直驅多實例件的 qty 展開(Servo, Servo~2, …)。"""
    names = ["Motor-Servo-class"] + [f"Motor-Servo-class~{i}" for i in range(2, servo_qty + 1)]
    return to_json(brain, names + base_comps)


def test_four_servos_get_four_distinct_pwm_pins():
    """4 servo 實例 → 4 個獨立 wiring entry,各 VCC/GND/SIG、SIG 為 4 個互異 PWM 腳,0 error。"""
    j = _expand_servo("Arduino-Nano-class", ["Sensor-Ultrasonic-class", "Buzzer-Active-class"], 4)
    alloc = j["allocation"]
    servo_keys = [k for k in alloc if instance_base(k) == "Servo"]
    assert len(servo_keys) == 4, f"應 4 個 servo 實例,實得 {servo_keys}"
    sig_pins = [alloc[k]["SIG"] for k in servo_keys]
    assert len(set(sig_pins)) == 4, f"4 servo SIG 應互異,實得 {sig_pins}"
    # 每實例都有完整 VCC/GND/SIG(共用電源軌、獨立訊號)
    wiring = j["wiring"]
    for k in servo_keys:
        tags = {p["comp"] for p in wiring[k]["pins"]}
        assert {"VCC", "GND", "SIG"} <= tags, f"{k} 缺腳: {tags}"
    errs = [i for i in validate_wiring("Arduino-Nano-class",
            ["Motor-Servo-class", "Motor-Servo-class~2", "Motor-Servo-class~3",
             "Motor-Servo-class~4", "Sensor-Ultrasonic-class", "Buzzer-Active-class"])
            if getattr(i, "severity", "") == "error"]
    assert not errs, f"biped 多實例接線應 0 error,實得 {[(e.comp, e.reason) for e in errs]}"


def test_driver_mediated_not_in_multi_instance_whitelist():
    """DC 馬達經 L298N 共驅動板,qty>1 **不**展開(避免弄壞 rc_car);白名單只含直驅 servo。"""
    from scripts.builders.bake_canned_bridges import _MULTI_INSTANCE_DIRECT
    assert "Motor-Servo-class" in _MULTI_INSTANCE_DIRECT
    assert "Motor-DC-class" not in _MULTI_INSTANCE_DIRECT
    assert "L298N-Driver-class" not in _MULTI_INSTANCE_DIRECT
