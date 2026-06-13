"""tests/test_power_budget_single_source.py — #20 電源供電上限「單一官方源(讀穿)」防禦。

problem #20:電源供電上限(supply_ma)曾為三源額外建制且漂移——
  - `lib/specs.POWER_BUDGET_MA`(手刻 5 class:USB-5V=500/USB-Adapter=500/LiPo=1500/AA=800/AC=2000)
  - `phase2_handler._SUPPLY_MA`(手刻 8 class:USB-5V=1000/USB-Adapter=1000/LiPo=1000/…)
  - `bake_canned_bridges._SUPPLY`(與 phase2 逐字相同)
三份不一致(USB-5V 500↔1000、USB-Adapter 500↔1000、LiPo 1500↔1000),導致 **Phase 2 早期警示
比 Phase 3 最終 BOM 預算寬鬆 = 假性放行**(USB 700mA:Phase2「<1000 OK」放行 → Phase3「>500」擋下)。

修正(使用者「一律用現實/官方真實值」+ 讀穿):全部讀穿 verified.json 官方供電容量
(`_SUPPLY_CURRENT_KEYS`,經 `_section("supply_ma")`);verified.json 缺項的 alias variant
(USB-Buck/LiPo-Charger/BatteryHolder-AA)走 cache `_fallback.supply_ma`(附 provenance)。

本 gate:① POWER_BUDGET_MA 對 in-SSOT 電源 class == verified.json 供電容量欄(讀穿,零漂移);
② 5 個 in-SSOT 電源 class 都有供電上限(防欄名/deriver 漂移使其靜默掉出);
③ Phase 2 早期警示上限 == POWER_BUDGET_MA(early==final,鎖死假性放行修復);
④ bake._supply_ma == POWER_BUDGET_MA(第三源亦同源);
⑤ 不變量:無電源 class 的 early 上限寬鬆於 final;
⑥ _fallback.supply_ma 只補 verified.json 缺項(variant),不得遮蔽 in-SSOT class。
"""
import json
from pathlib import Path

from lib.specs import POWER_BUDGET_MA, USB_BUDGET_MA, _SUPPLY_CURRENT_KEYS

_ROOT = Path(__file__).resolve().parent.parent
_VERIFIED = _ROOT / "data" / "component_datasheet_verified.json"
_CACHE = _ROOT / "data" / "_component_specs_cache.json"

_IN_SSOT_POWER = (
    "USB-5V-class", "USB-Adapter-class", "AC-Adapter-class",
    "Battery-AA-class", "Battery-LiPo-class",
)


def _verified_supply(cls: str, vj: dict):
    elec = vj.get(cls, {}).get("electrical", {})
    for k in _SUPPLY_CURRENT_KEYS:
        if k in elec:
            return float(elec[k])
    return None


def _phase2_supply(power_class: str) -> float:
    from services.phase_handlers.phase2_handler import Phase2Handler
    h = Phase2Handler()
    res = h._check_power_early([{"type": power_class, "role": "Power", "qty": 1}], None)
    return float(res["supply_ma"])


def test_power_budget_reads_through_verified():
    """POWER_BUDGET_MA 對每個有供電容量欄的 verified.json class，值須等於 SSOT(讀穿、零漂移)。"""
    vj = json.loads(_VERIFIED.read_text(encoding="utf-8"))
    drift = {}
    for cls in vj:
        if cls.startswith("_"):
            continue
        s = _verified_supply(cls, vj)
        if s is not None and POWER_BUDGET_MA.get(cls) != s:
            drift[cls] = (POWER_BUDGET_MA.get(cls), s)
    assert not drift, (
        "POWER_BUDGET_MA 與 verified.json 供電容量漂移(應讀穿;改值改 verified.json 後 rebuild):\n"
        + "\n".join(f"  {c}: budget={b} vs ssot={s}" for c, (b, s) in sorted(drift.items())))


def test_in_ssot_power_sources_covered():
    """5 個 in-SSOT 電源 class 都有供電上限(防欄名/deriver 漂移使其靜默掉出)。"""
    vj = json.loads(_VERIFIED.read_text(encoding="utf-8"))
    for cls in _IN_SSOT_POWER:
        assert _verified_supply(cls, vj) is not None, f"{cls} verified.json 缺供電容量欄(_SUPPLY_CURRENT_KEYS)"
        assert cls in POWER_BUDGET_MA, f"{cls} 未讀穿進 POWER_BUDGET_MA"


def test_phase2_early_warning_equals_final_budget():
    """Phase 2 早期警示上限 == Phase 3 最終預算(POWER_BUDGET_MA),鎖死 #20 假性放行修復。"""
    mismatch = {}
    for cls, budget in POWER_BUDGET_MA.items():
        got = _phase2_supply(cls)
        if got != budget:
            mismatch[cls] = (got, budget)
    assert not mismatch, (
        "Phase 2 早期警示上限 ≠ 最終預算(假性放行風險再現):\n"
        + "\n".join(f"  {c}: phase2={g} vs budget={b}" for c, (g, b) in sorted(mismatch.items())))


def test_bake_supply_matches_budget():
    """bake._supply_ma(canned 烤製用)亦讀穿同源,== POWER_BUDGET_MA。"""
    from scripts.builders.bake_canned_bridges import _supply_ma
    mismatch = {}
    for cls, budget in POWER_BUDGET_MA.items():
        got = _supply_ma([{"type": cls, "role": "Power"}])
        if got != int(budget):
            mismatch[cls] = (got, int(budget))
    assert not mismatch, f"bake._supply_ma 與 POWER_BUDGET_MA 漂移:{mismatch}"


def test_bake_and_phase2_default_to_usb_budget():
    """無 Power 元件 / 未知電源 → 兩消費端都收尾於 USB_BUDGET_MA(單一預設源)。"""
    from scripts.builders.bake_canned_bridges import _supply_ma
    assert _supply_ma([{"type": "Arduino-Uno-class", "role": "Brain"}]) == int(USB_BUDGET_MA)
    assert _phase2_supply("Arduino-Uno-class") == float(USB_BUDGET_MA)


def test_no_early_looser_than_final():
    """不變量:無電源 class 的 early 上限 > final(寬鬆=假性放行)。現為相等。"""
    for cls, budget in POWER_BUDGET_MA.items():
        assert _phase2_supply(cls) <= budget, f"{cls} early 上限寬鬆於 final"


def test_fallback_supply_only_for_absent_classes():
    """_fallback.supply_ma 只能補 verified.json 缺項(alias variant),不得遮蔽 in-SSOT class。"""
    vj = json.loads(_VERIFIED.read_text(encoding="utf-8"))
    cache = json.loads(_CACHE.read_text(encoding="utf-8"))
    fb = cache.get("_fallback", {}).get("supply_ma", {})
    shadowed = [cls for cls in fb
                if not cls.startswith("_") and _verified_supply(cls, vj) is not None]
    assert not shadowed, f"_fallback.supply_ma 遮蔽了 verified.json 已有供電容量的 class:{shadowed}"
    # 且 variant 確實被 read-through 涵蓋(in POWER_BUDGET_MA)
    for cls in fb:
        if not cls.startswith("_"):
            assert cls in POWER_BUDGET_MA, f"{cls} 在 _fallback 卻未進 POWER_BUDGET_MA"


def test_phase2_consumption_reads_through_power_ma():
    """B2:phase2 早期耗電總和 == 以 POWER_MA(lookup_constant，alias-aware)算的總和——讀穿
    單一官方源,無 _MA_FALLBACK 手刻副本漂移。先前 phase2 對 alias 名(Servo-SG90)用手值 250,
    與官方 Motor-Servo=150 漂移;讀穿後一律取官方值。未知元件仍軟預設 20mA(早期警示非 raise)。"""
    from lib.specs import POWER_MA, lookup_constant
    from services.phase_handlers.phase2_handler import Phase2Handler
    h = Phase2Handler()
    comps = [
        {"type": "ESP32-class", "role": "Brain", "qty": 1},
        {"type": "Motor-Servo-class", "role": "Output", "qty": 2},
        {"type": "Servo-SG90-class", "role": "Output", "qty": 1},     # alias → 官方 Motor-Servo
        {"type": "Totally-Unknown-XYZ", "role": "Output", "qty": 1},  # 未知 → 軟預設 20
    ]
    res = h._check_power_early(comps, None)
    expected = sum(lookup_constant(POWER_MA, c["type"], 20) * c["qty"] for c in comps)
    assert res["total_ma"] == expected
    # alias 解析實證:Servo-SG90 取官方 Motor-Servo 值,非舊手刻 250
    assert lookup_constant(POWER_MA, "Servo-SG90-class", 20) == POWER_MA["Motor-Servo-class"]


def test_phase3_bom_power_ok_agrees_with_l1_rail_budget_gate():
    """B8(#29):兩套驗證家族(runtime `_phase3_validators` vs CI `lib/verification/l1_*`)經
    verify-first 判定**多數互補**(component-list 啟發式 vs netlist/template 拓樸,不同物理);
    唯一「同算」重疊 = Phase 3 runtime `power_ok`(bom_calculator:total typical ≤ supply)
    ≡ l1 CI gate `check_rail_current_budget`(同算)。兩者讀同一 SSOT(POWER_MA/POWER_BUDGET_MA)
    → 須對所有 canned demo 同意。此 gate 鎖兩實作不因單邊改公式而漂移(B4 模式:正當分層、
    補一致性 gate 而非強行合併)。"""
    from lib.canned_template_defs import TEMPLATE_DEFS
    from lib.bom_calculator import calculate_bom
    from lib.verification.l1_passives import check_rail_current_budget
    from lib.verification.report import Verdict
    disagree = []
    for name, d in TEMPLATE_DEFS.items():
        comps = d["components"]
        bom = calculate_bom(comps)
        bom_ok = bom.total_ma <= bom.current_budget_ma
        l1_ok = check_rail_current_budget([(name, comps)])[0].verdict == Verdict.PASS
        if bom_ok != l1_ok:
            disagree.append((name, bom_ok, l1_ok))
    assert not disagree, (
        "Phase3 runtime power_ok 與 l1 check_rail_current_budget 對 canned demo 不一致"
        "(同算重疊漂移,單邊改了公式?):\n"
        + "\n".join(f"  {n}: bom_ok={b} vs l1_ok={l}" for n, b, l in disagree))
    assert len(TEMPLATE_DEFS) >= 16, "canned demo 數異常(防空集假綠)"
