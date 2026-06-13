"""lib/verification/l1_passives.py — P5.1 Axis-A 被動/驅動級完整性規則(純 stdlib,閉式,免 SPICE)。

第一片 driver-stage(B1 family):高電流/感性 actuator 的「裸高電流端子」(馬達/線圈/喇叭輸出
M+/M-/M1/M2…)絕不可直連 MCU brain pin —— 必須經驅動板(L298N/ULN2003)輸出或外部/負載軌。
資料源:lib.wiring.wiring_data.WIRING_TEMPLATES(每元件 → MCU 的接線 SSOT)。

緣由(問題 #10):計劃書 B1「obstacle_car DCMotor 直掛 Arduino 無驅動級」premise 經查為 stale ——
Motor-DC-class 透過 DCMotor/L298N 模板以 ENA/IN1/IN2 邏輯腳接 MCU,馬達端子在驅動輸出側。repo 已
正確驅動間接;本檔把該不變量鎖成可計算 gate,防回歸(未來若把裸 M+/M- tag 到 GPIO 即 FAIL)。
"""
from __future__ import annotations

from .report import CheckResult, Verdict

# 裸高電流端子(馬達/線圈/喇叭輸出)= 負載側,絕不該以 tag(= MCU brain pin)直連。
# 正當接法:driver 板輸出,或 WireExtra.fixed 標外部/負載軌(此時 tag=None)。
_BARE_HIGH_CURRENT_TERMINALS = frozenset({
    "M+", "M-", "M1", "M2", "MOTOR+", "MOTOR-",
    "OUT1", "OUT2", "OUT+", "OUT-", "COIL+", "COIL-",
})


def check_driver_stage(templates) -> list[CheckResult]:
    """裸高電流端子不得直連 MCU(WireExtra.tag 非 None)。

    templates: dict[str, WiringTemplate](WIRING_TEMPLATES)。
    回 [CheckResult];任一違規 → L1 FAIL(blocking:GPIO 直驅裸高電流負載是真 bug,
    stall 電流遠超 GPIO 額定 + 無 flyback 路徑)。
    """
    bare = {t.upper() for t in _BARE_HIGH_CURRENT_TERMINALS}
    offenders: list[str] = []
    for key, tmpl in templates.items():
        for w in getattr(tmpl, "extra", []):
            if w.tag is not None and str(w.comp).upper() in bare:
                offenders.append(f"{key}.{w.comp}->MCU:{w.tag}")
    verdict = Verdict.FAIL if offenders else Verdict.PASS
    return [CheckResult(
        "L1", "no_gpio_drives_bare_high_current_terminal", verdict,
        metric={"offenders": offenders, "n_templates": len(templates)},
        message=("裸高電流端子直連 MCU(缺驅動級): " + ", ".join(offenders)) if offenders
                else "所有高電流端子經驅動級/外部軌,未直掛 MCU GPIO",
    )]


# ── LED 串聯/限流電阻 presence(P5.1 第二片) ────────────────────────────────
# LED-class 模板的每個 MCU-driven 腳(WireExtra.tag 非 None)必須帶串聯電阻 passive
# (topo=="series", kind=="R")—— 離散 LED 為限流 R,定址燈條(NeoPixel)為資料線串聯 R。
# 資料源:lib.wiring.wiring_data.WIRING_TEMPLATES 的 passive 欄(SWL3)。
# _LED_TEMPLATE_KEYS 對應 wiring_data._TAXONOMY_TO_SHORT 的 "Lighting-*" classes
# (Lighting-NeoPixel/LED-PWM/LED-RGB/LED-Strip → NeoPixel/LED_Single/LED_RGB);
# tests/test_l1_passives.py 以 taxonomy 漂移守衛鎖死 —— 新增 Lighting-* class 卻未納入
# 即 test FAIL(DEC-H7 scope guard:抓到,不靜默放行讓裸 LED 過)。
_LED_TEMPLATE_KEYS = frozenset({"NeoPixel", "LED_Single", "LED_RGB"})


def check_led_current_limit(templates) -> list[CheckResult]:
    """LED-class 模板的每個 MCU-driven 腳須有串聯電阻(presence/topology,非數值)。

    templates: dict[str, WiringTemplate](WIRING_TEMPLATES)。
    回 [CheckResult];任一 LED 驅動腳缺串聯 R passive → L1 FAIL
    (裸 LED 直掛 GPIO 無限流 → 過電流燒 LED 或拉垮 GPIO)。

    僅 presence:串聯電阻數值在 verified.json 為 prose,無 R 欄位,(Vrail-Vf)/R 不可閉式導出;
    依 DEC-H7 此規則刻意只斷言「串聯 R 存在」,**不靜默預設 220Ω** —— 數值門檻留待 SSOT
    補 R 欄後另案(屆時缺值須 raise,非預設)。
    """
    offenders: list[str] = []
    checked: list[str] = []
    for key in sorted(_LED_TEMPLATE_KEYS):
        tmpl = templates.get(key)
        if tmpl is None:
            continue  # 該模板不在(可能為部分)集合中 —— 漂移由 test 層守衛
        checked.append(key)
        for w in getattr(tmpl, "extra", []):
            if w.tag is None:
                continue  # 非 MCU-driven 腳(GND/陰極等),不需限流 R
            p = w.passive
            if not (isinstance(p, dict) and p.get("kind") == "R" and p.get("topo") == "series"):
                offenders.append(f"{key}.{w.comp}")
    verdict = Verdict.FAIL if offenders else Verdict.PASS
    return [CheckResult(
        "L1", "led_pin_has_series_resistor", verdict,
        metric={"offenders": offenders, "checked": checked},
        message=("LED 驅動腳缺串聯限流電阻: " + ", ".join(offenders)) if offenders
                else f"所有 LED-class 驅動腳皆帶串聯 R(已查 {len(checked)} 模板)",
    )]


# ── 軌電流預算 ≤ 電源供電容量(P5.1 第三片,符合物理) ───────────────────────────
# 每個設計的總耗電(POWER_MA 加總,官方 verified.json current_typ_ma)不得超過其電源的
# 官方供電容量(POWER_BUDGET_MA,讀穿 verified.json 供電容量欄,#20/B1)。超過 = 電源供不起
# 負載 = 不符物理(且 #19「每個專案都應有適配的電源」)。閉式、純 stdlib、官方值,免 SPICE。
# 緣由(問題 #26/#27):重烤後 auto_curtain(ESP32+Stepper+Relay=561mA)on USB-5V(500mA)
# 被正確標 over-budget —— 先前被 stale 1000mA budget 掩蓋(#20 假性放行)。此 gate 把
# 「供電充足性」鎖成可計算不變量,防未來再出貨抽載超過電源官方容量的設計。

def check_rail_current_budget(designs) -> list[CheckResult]:
    """每個設計的總耗電 ≤ 其電源的官方供電容量。

    designs: iterable of (name, components);components = [{"type","role","qty"}]。
    耗電用 lib.specs.POWER_MA(alias-aware via lookup_constant);電源容量用 POWER_BUDGET_MA;
    無電源元件 → 預設 USB_BUDGET_MA(與 bom_calculator 一致)。電源元件本身耗 0(POWER_MA)。
    回 [CheckResult];任一設計超載 → L1 FAIL(供電不足,不符物理)。
    """
    from lib.specs import (POWER_MA, POWER_BUDGET_MA, USB_BUDGET_MA,
                           lookup_constant)
    offenders: list[str] = []
    checked = 0
    for name, comps in designs:
        checked += 1
        total = sum(lookup_constant(POWER_MA, c.get("type", ""), 20) * int(c.get("qty", 1))
                    for c in comps)
        supply = USB_BUDGET_MA
        for c in comps:
            if c.get("role") == "Power":
                supply = POWER_BUDGET_MA.get(c.get("type", ""), USB_BUDGET_MA)
                break
        if total > supply:
            offenders.append(f"{name}: {total:.0f}mA > 電源 {supply:.0f}mA")
    verdict = Verdict.FAIL if offenders else Verdict.PASS
    return [CheckResult(
        "L1", "rail_current_within_supply_budget", verdict,
        metric={"offenders": offenders, "n_designs": checked},
        message=("設計總耗電超過電源官方容量(供電不足/不適配電源): " + "; ".join(offenders))
                if offenders else f"所有 {checked} 設計總耗電 ≤ 電源官方供電容量",
    )]
