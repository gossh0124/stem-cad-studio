"""tests/test_l1_passives.py — P5.1 driver-stage 規則 + B1 family 回歸鎖。

問題 #10:計劃書 B1「obstacle_car DCMotor 無驅動級」premise stale —— Motor-DC 經 DCMotor/L298N
模板以邏輯腳(ENA/IN1/IN2)接 MCU,裸馬達端子在驅動輸出側。本測試:① 真實模板皆無違規(live
gate);② 故意把裸 M+ 端子 tag 到 GPIO → 必 FAIL(證 gate 會 fire);③ DCMotor MCU 腳皆為驅動邏輯。
"""
from lib.verification.l1_passives import (
    check_driver_stage, check_led_current_limit, check_rail_current_budget,
    _BARE_HIGH_CURRENT_TERMINALS, _LED_TEMPLATE_KEYS,
)
from lib.verification.report import Verdict
from lib.wiring.wiring_data import (
    WIRING_TEMPLATES, WiringTemplate, WireExtra, _TAXONOMY_TO_SHORT,
)
from lib.wiring.template_gen import generate_all_templates


def test_real_templates_pass():
    """live gate:真實 WIRING_TEMPLATES 無裸高電流端子掛 MCU → PASS(在 CI 對真資料執行)。"""
    res = check_driver_stage(WIRING_TEMPLATES)
    fails = [r for r in res if r.verdict == Verdict.FAIL]
    assert not fails, f"真實模板出現裸高電流端子直連 MCU: {[r.metric for r in fails]}"
    assert any(r.verdict == Verdict.PASS for r in res)


def test_bare_motor_terminal_on_mcu_fails():
    """mutation:把裸 M+ 端子 tag 到 MCU(D5)→ 必 FAIL(防 gate 退化成永遠綠)。"""
    mutant = {"BadMotor": WiringTemplate("裸馬達直掛 GPIO(故意)", "5V", [
        WireExtra("M+", "D5", "BUG:裸馬達端子直連 GPIO"),
        WireExtra("M-", None, "GND 側", fixed="GND"),
    ])}
    res = check_driver_stage(mutant)
    assert any(r.verdict == Verdict.FAIL for r in res), "裸馬達端子直連 MCU 未被抓"
    offenders = res[0].metric["offenders"]
    assert any("BadMotor.M+" in o for o in offenders), offenders


def test_dcmotor_mcu_pins_are_driver_logic():
    """DCMotor(= Motor-DC 經 L298N)接 MCU 的腳皆為驅動邏輯(ENA/IN1/IN2),無裸高電流端子;
    +12V 高電流供電在外部軌(tag=None),不接 MCU —— 鎖住 B1 的驅動間接正確行為。"""
    tmpl = WIRING_TEMPLATES["DCMotor"]
    bare = {t.upper() for t in _BARE_HIGH_CURRENT_TERMINALS}
    mcu_pins = {w.comp for w in tmpl.extra if w.tag is not None}
    assert mcu_pins, "DCMotor 應有 MCU 邏輯腳"
    assert not {p for p in mcu_pins if p.upper() in bare}, \
        f"DCMotor 不應有裸高電流端子接 MCU: {mcu_pins}"
    pwr = [w for w in tmpl.extra if w.comp == "+12V"]
    assert pwr and pwr[0].tag is None, "DCMotor +12V 應為外部軌(tag=None),不接 MCU"


# ── P5.1 第二片:LED 串聯/限流電阻 presence ────────────────────────────────

def test_real_templates_have_led_series_resistor():
    """live gate:真實 LED-class 模板每個 MCU-driven 腳皆帶串聯 R → PASS;
    且 checked 非空並涵蓋三個 LED 模板(防規則漂移成空 → 假綠)。"""
    res = check_led_current_limit(WIRING_TEMPLATES)
    fails = [r for r in res if r.verdict == Verdict.FAIL]
    assert not fails, f"真實 LED 模板出現缺串聯電阻的驅動腳: {[r.metric for r in fails]}"
    checked = set(res[0].metric["checked"])
    assert checked == {"LED_Single", "LED_RGB", "NeoPixel"}, \
        f"LED live-gate 涵蓋面漂移: {checked}"


def test_bare_led_without_series_resistor_fails():
    """mutation:把 LED_Single 的陽極腳改成無 passive(裸 LED 直掛 GPIO)→ 必 FAIL
    (防 gate 退化成永遠綠)。用真實 key LED_Single,確保被規則認列為 LED-class。"""
    mutant = dict(WIRING_TEMPLATES)
    mutant["LED_Single"] = WiringTemplate("裸 LED 無限流(故意)", None, [
        WireExtra("+", "+", "BUG:裸 LED 直掛 GPIO 無 220Ω"),  # passive=None
    ])
    res = check_led_current_limit(mutant)
    assert any(r.verdict == Verdict.FAIL for r in res), "裸 LED 無串聯電阻未被抓"
    offenders = res[0].metric["offenders"]
    assert any("LED_Single.+" in o for o in offenders), offenders


def test_led_keys_match_lighting_taxonomy():
    """DEC-H7 scope guard:_LED_TEMPLATE_KEYS 必等於 _TAXONOMY_TO_SHORT 的全部 Lighting-*
    模板集合 —— 新增 Lighting-* class 卻未納入規則 → FAIL(抓到,不靜默放行裸 LED);
    且每個 LED key 都有對應真實模板(無懸空引用)。"""
    lighting = {short for taxo, short in _TAXONOMY_TO_SHORT.items()
                if taxo.startswith("Lighting-")}
    assert lighting == set(_LED_TEMPLATE_KEYS), \
        f"Lighting taxonomy 與 LED 規則集合漂移: taxonomy={lighting} vs rule={set(_LED_TEMPLATE_KEYS)}"
    missing = set(_LED_TEMPLATE_KEYS) - set(WIRING_TEMPLATES)
    assert not missing, f"LED 規則指向不存在的模板: {missing}"


# ── production artifact 覆蓋(收掉「gate 只審 static fallback dict」觀察,見問題 #14) ──
# 既有 live-gate 審 static WIRING_TEMPLATES;production wiring 實走 template_gen.generate_all_templates
# (datasheet 衍生,與 static dict 可能分歧,如 DCMotor 多 OUT1→M1/OUT2→M2)。下列鎖死 production
# artifact 也滿足兩條規則 —— 分歧出的裸端子皆 tag=None 經 fixed 走負載軌,故 driver-stage 仍綠。

def test_production_templates_pass_driver_stage():
    """production-derived 模板(generate_all_templates)無裸高電流端子直連 MCU。"""
    res = check_driver_stage(generate_all_templates())
    fails = [r for r in res if r.verdict == Verdict.FAIL]
    assert not fails, f"production 模板出現裸高電流端子直連 MCU: {[r.metric for r in fails]}"
    assert any(r.verdict == Verdict.PASS for r in res)


def test_production_templates_pass_led_current_limit():
    """production-derived LED 模板每個驅動腳皆帶串聯 R,且涵蓋三個 LED 模板(非空)。"""
    res = check_led_current_limit(generate_all_templates())
    fails = [r for r in res if r.verdict == Verdict.FAIL]
    assert not fails, f"production LED 模板缺串聯電阻: {[r.metric for r in fails]}"
    assert set(res[0].metric["checked"]) == {"LED_Single", "LED_RGB", "NeoPixel"}


# ── P5.1 第三片:軌電流預算 ≤ 電源供電容量(符合物理,#26/#27) ────────────────────

def test_real_demos_within_supply_budget():
    """live gate:全 canned demo 定義(TEMPLATE_DEFS)總耗電 ≤ 電源官方供電容量 → PASS。
    auto_curtain(#27 修為 AC-Adapter)等皆在預算內;n_designs 非空(防空集假綠)。"""
    from lib.canned_template_defs import TEMPLATE_DEFS
    designs = [(k, v["components"]) for k, v in TEMPLATE_DEFS.items()]
    res = check_rail_current_budget(designs)
    fails = [r for r in res if r.verdict == Verdict.FAIL]
    assert not fails, f"有設計總耗電超過電源官方容量: {[r.metric['offenders'] for r in fails]}"
    assert res[0].metric["n_designs"] >= 16


def test_over_budget_design_fails():
    """mutation:561mA 負載(ESP32+Stepper+Relay)配 USB-5V(官方 500mA)→ 必 FAIL
    (防 gate 退化成永遠綠;即 #26 auto_curtain 修正前的真實超載狀態)。"""
    over = [("over_budget_mutant", [
        {"role": "Power", "type": "USB-5V-class", "qty": 1},
        {"role": "Brain", "type": "ESP32-class", "qty": 1},
        {"role": "Output", "type": "Motor-Stepper-class", "qty": 1},
        {"role": "Control", "type": "Relay-Module-class", "qty": 1},
    ])]
    res = check_rail_current_budget(over)
    assert any(r.verdict == Verdict.FAIL for r in res), "超載設計未被抓"
    assert any("over_budget_mutant" in o for o in res[0].metric["offenders"])


def test_auto_curtain_now_has_fitting_power():
    """#27 回歸鎖:auto_curtain 電源為適配(官方供電容量 ≥ 其總負載),非供不起的 USB-5V。"""
    from lib.canned_template_defs import TEMPLATE_DEFS
    from lib.specs import POWER_MA, POWER_BUDGET_MA, lookup_constant
    comps = TEMPLATE_DEFS["auto_curtain"]["components"]
    power = next(c["type"] for c in comps if c["role"] == "Power")
    total = sum(lookup_constant(POWER_MA, c["type"], 20) * c.get("qty", 1) for c in comps)
    assert power != "USB-5V-class", "auto_curtain 不應再用供不起的 USB-5V"
    assert POWER_BUDGET_MA[power] >= total, f"auto_curtain 電源 {power} 仍供不起 {total}mA"
