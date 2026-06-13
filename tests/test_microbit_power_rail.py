"""tests/test_microbit_power_rail.py — Microbit(無 5V rail)電源域回歸鎖。

緣由:plant_monitor 換 Microbit-class(2026-06-13,使用者「demo 換 MCU」)後,其 3.3V
感測器(電容式土壤 SEN0193 / DHT22 / SSD1306 OLED,SSOT voltage_operating_v=3.3)透過
`wiring_hints.vcc=3.3V`(比照 Display-OLED-class 既有 pattern)落 Microbit 的 3V rail =
物理正確且可行。但 Microbit **無 5V 供電腳**,故「真 5V-only 負載」(如 5V 繼電器線圈)在
Microbit 上仍須 loud 報 power-feasibility error,不得靜默(no-silent-fallback)。

本檔把兩向都鎖死,防回歸:
  ① plant_monitor on Microbit → 0 wiring error(3.3V 件落 3V rail 可行;若有人移除 vcc hint
     會立刻退回 2 個 5V error,本測試擋之)。
  ② 合成真 5V-only 件(Relay)on Microbit → 仍 surface power-feasibility error(守 no-silent)。

對應 [[Key Decisions]] 「demo 換 MCU」+ Tier1 物理硬約束(無 5V rail 不可掛真 5V 件)。
"""
from lib.canned_template_defs import TEMPLATE_DEFS
from lib.wiring.validate import validate_wiring


def _errors(brain: str, names: list[str]) -> list:
    return [i for i in validate_wiring(brain, names) if getattr(i, "severity", "") == "error"]


def test_plant_monitor_brain_is_microbit():
    """plant_monitor 主控已換 Microbit-class(demo 換 MCU);換回應觸發本鎖重新評估。"""
    brain = next(c["type"] for c in TEMPLATE_DEFS["plant_monitor"]["components"]
                 if c["role"] == "Brain")
    assert brain == "Microbit-class", f"plant_monitor Brain 應為 Microbit-class,實得 {brain}"


def test_plant_monitor_microbit_is_power_feasible():
    """3.3V 感測器(soil/DHT/OLED)經 wiring_hints.vcc=3.3V 落 Microbit 3V rail → 0 error。"""
    comps = TEMPLATE_DEFS["plant_monitor"]["components"]
    names = [c["type"] for c in comps if c["role"] not in ("Power", "Housing", "Brain")]
    errs = _errors("Microbit", names)
    assert not errs, (
        "plant_monitor on Microbit 應 0 wiring error(3.3V 件落 3V rail);"
        f"實得: {[(getattr(e, 'comp', ''), getattr(e, 'reason', '')) for e in errs]} —— "
        "soil/DHT 的 wiring_hints.vcc=3.3V 被移除?")


def test_true_5v_load_on_microbit_still_errors():
    """no-silent-fallback 守:Microbit 無 5V rail → 真 5V-only 件(Relay 線圈)仍須 loud 報 error。
    防有人把 mcu_power_pin / power_feasibility 改成靜默把 5V 降 3V 而藏掉不相容。"""
    errs = _errors("Microbit", ["Relay-Module-class"])
    assert errs, "真 5V 件在 Microbit 上未 surface power-feasibility error(no-silent-fallback 破)"
    assert any("5" in getattr(e, "reason", "") for e in errs), \
        f"error 理由未指出 5V 不相容: {[getattr(e, 'reason', '') for e in errs]}"
