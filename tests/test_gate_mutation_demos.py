"""tests/test_gate_mutation_demos.py — 五個 golden gate 的恆綠稽核(mutation test)。

目的(碩論 Ch5 判分基準效度前置):研究設計用「既有可計算契約 gate」當學習成效
評量的客觀 golden。本檔對 4 個固定 demo(smart_nightlight / plant_monitor /
auto_waterer / obstacle_car)逐 gate 跑 mutation,證明每個 gate:
  (a) VALID 設計 → PASS(非空洞),且
  (b) 違反契約的 MUTATED 設計 → 真的 FAIL(catch),
      若 MUTATED 仍 PASS = 恆綠陷阱(false-PASS),該 gate 不可單獨當研究 golden。

實測裁定(2026-06-12,純 stdlib,不需 build123d/shells):
  power_budget : SOUND         — 算術真 catch
  isolation    : EVERGREEN-TRAP— 窄別名集 → 負載電源腳用集合外別名(PWR/VDD)假 PASS-N/A
  bbox guard   : EVERGREEN-TRAP— schema 上限(inner<=280,wall<=4)使 outer<=288,>295 結構不可達
  PV1 wall     : PARTIAL       — 函式 sound,但 Phase IV 預夾 [1.5,3.5] 使使用者薄壁永不到 gate
  role / H21   : EVERGREEN-TRAP— 非法 per-component role → AdvancedValidator.validate ok=True

標 "EVERGREEN WITNESS" 的測試現在會 PASS(它斷言的是「gate 沒擋」這個事實);
當對應的 gate 被修好(契約收緊),該 witness 會轉紅,提醒回來反轉斷言。
"""
from __future__ import annotations

import copy
import json
import pathlib

import pytest

pytest.importorskip("build123d")  # transitive isolation/role gate imports pull lib.cad (build123d)

REPO = pathlib.Path(__file__).resolve().parents[1]


def _canned(demo: str) -> dict:
    return json.loads((REPO / "v6" / "canned" / f"{demo}.json").read_text(encoding="utf-8"))


# ======================================================================
# Gate 1 — power_budget : VERIFIED SOUND
# ======================================================================
from lib.canned_template_defs import TEMPLATE_DEFS
from lib.bom_calculator import calculate_bom
from lib.verification.l1_passives import check_rail_current_budget
from lib.verification.report import Verdict


def _power(comps):
    b = calculate_bom(comps)
    return (b.total_ma <= b.current_budget_ma), b.total_ma, b.current_budget_ma, b.power_type


def _l1_power_pass(name, comps):
    return check_rail_current_budget([(name, comps)])[0].verdict == Verdict.PASS


def test_power_valid_auto_waterer_passes():
    comps = copy.deepcopy(TEMPLATE_DEFS["auto_waterer"]["components"])
    ok, total, budget, ptype = _power(comps)
    assert ptype == "Battery-AA-class"
    assert total <= budget, f"valid 應 PASS:{total} <= {budget}"
    assert ok is True
    assert _l1_power_pass("auto_waterer", comps) is True


def test_power_mutated_overcurrent_FAILS():
    """SOUND witness:pump qty 1->5 (1235mA) > Battery-AA 800mA → gate 真 catch。"""
    comps = copy.deepcopy(TEMPLATE_DEFS["auto_waterer"]["components"])
    for c in comps:
        if c.get("type") == "Pump-Water-class":
            c["qty"] = 5  # 220*5=1100; +Arduino50+Soil5+Relay80 = 1235
    ok, total, budget, _ = _power(comps)
    assert total > budget, f"mutated 應違反契約:{total} > {budget}"
    assert ok is False, "power gate 未 catch 超預算 = 恆綠(但實測非恆綠)"
    assert _l1_power_pass("auto_waterer_mut", comps) is False


def test_power_biped_robot_on_usb5v_FAILS():
    """SOUND witness:biped_robot(4×servo 走路 ~664mA)換 USB-5V(500mA)→ FAIL。
    (取代已移除的 obstacle_car;2026-06-13,biped 取代 obstacle_car)"""
    comps = copy.deepcopy(TEMPLATE_DEFS["biped_robot"]["components"])
    for c in comps:
        if c.get("role") == "Power":
            c["type"] = "USB-5V-class"
    ok, total, budget, ptype = _power(comps)
    assert ptype == "USB-5V-class" and budget == 500.0
    assert total > budget and ok is False


# ======================================================================
# Gate 2 — galvanic isolation : EVERGREEN TRAP
# ======================================================================
from lib.wiring import build_netlist
from lib.verification.l1_isolation import check_galvanic_isolation


def test_isolation_valid_auto_waterer_real_extgnd_PASS():
    """VALID:relay 乾接點 → Pump.GND 搬 EXT-GND,兩地不相交,applicable=True。"""
    wiring = copy.deepcopy(_canned("auto_waterer")["wiring"])
    nets = build_netlist("Arduino", wiring)
    cr = check_galvanic_isolation(nets)
    assert cr.verdict == Verdict.PASS
    # genuine PASS 路徑的 metric={'n_logic':N,'n_load':M}(無 applicable 鍵,N/A 路徑才回 applicable=False)
    assert cr.metric.get("n_load", 0) >= 1, "valid demo 必須有真實隔離負載域(n_load>=1),非 N/A"
    assert any(n["name"] == "EXT-GND" for n in nets)


def test_isolation_EVERGREEN_outofset_alias_false_pass():
    """EVERGREEN WITNESS:把 relay-fed 電源腳 comp 'VCC'->'PWR'(netlist 別名集外)。
    build_netlist 不再搬 Pump.GND → EXT-GND 不生成 → 負載共用 logic GND(違反契約),
    但 check_galvanic_isolation 回 PASS 且 applicable=False(假 PASS-N/A)。
    此測 PASS == 恆綠陷阱確認。修好(別名集對齊 _POWER_RAILS)後此測轉紅。"""
    wiring = copy.deepcopy(_canned("auto_waterer")["wiring"])
    pin = next(p for p in wiring["Pump"]["pins"] if p["mcu"] == "Relay.NO")
    pin["comp"] = "PWR"  # 集合外合法電源別名
    nets = build_netlist("Arduino", wiring)
    cr = check_galvanic_isolation(nets)
    assert not any(n["name"] == "EXT-GND" for n in nets), "別名外 → migration 未發生(EXT-GND 不生成)"
    assert cr.verdict == Verdict.PASS, "negative-by-construction:無 EXT-GND → gate 退化成 N/A"
    assert cr.metric.get("applicable", True) is False, "假 PASS-N/A:該擋的共地負載被報成『無隔離負載域』"


# ======================================================================
# Gate 3 — bbox guard (hl_dsl.validate_params) : EVERGREEN TRAP
# ======================================================================
from lib.cad.hl_dsl import validate_params

_PLAN = {
    "elements": [{"id": "e1", "component_type": "Arduino-Uno-class",
                  "role": "Brain", "logical_zone": "mid-center"}],
    "assembly_order": ["e1"],
    "joints": {"lid_method": "snap_fit_4x", "base_method": "screw_boss_4x_M3", "reason": "x"},
    "thermal_strategy": {"strategy": "no_vent"},
}
_PARAMS_VALID = {
    "enclosure_spec": {"inner_length": 220, "inner_width": 120, "inner_height": 80, "wall": 2.0, "tol": 0.3},
    "placements": [{"element_id": "e1", "x": 0, "y": 0, "rot_deg": 0}],
    "wire_routes": [], "vent_placements": [],
}


def _has_guard(errs):
    return any("bbox_guard" in e for e in errs)


def test_bbox_valid_demo_passes():
    ok, errs = validate_params(copy.deepcopy(_PARAMS_VALID), _PLAN)
    assert ok, f"valid(outer=224<=295)應 PASS:{errs}"
    assert not _has_guard(errs)


def test_bbox_EVERGREEN_schema_max_box_guard_silent():
    """EVERGREEN WITNESS:schema 上限盒 inner=280/wall=4 → outer=288<=295,guard 永不觸發。
    任何 schema-valid 輸入 outer<=288,故 guard 的 >295 結構不可達。"""
    bad = copy.deepcopy(_PARAMS_VALID)
    bad["enclosure_spec"]["inner_length"] = 280  # schema max
    bad["enclosure_spec"]["wall"] = 4.0          # schema max → outer 288
    ok, errs = validate_params(bad, _PLAN)
    assert ok, f"288<=295 必 PASS:{errs}"
    assert not _has_guard(errs), "guard 在 schema-valid 輸入觸發 = 它其實可達(與裁定矛盾)"


def test_bbox_EVERGREEN_over295_dominated_by_schema():
    """EVERGREEN WITNESS:能讓 guard 觸發的輸入(inner=292→outer=296)必同時觸發 schema maximum
    (inner>280)。移除 guard 後 verdict 不變 → guard 對 verdict 零獨立貢獻 = 恆綠。"""
    bad = copy.deepcopy(_PARAMS_VALID)
    bad["enclosure_spec"]["inner_length"] = 292  # outer 296 > 295
    ok, errs = validate_params(bad, _PLAN)
    assert not ok
    has_schema_max = any("280" in e for e in errs)
    assert has_schema_max, "outer>295 蘊含 inner>=288>280 → schema maximum 必同時 fire"
    errs_without_guard = [e for e in errs if "bbox_guard" not in e]
    assert len(errs_without_guard) > 0, "若移除 guard 後無 error,guard 才是 load-bearing(目前不是)"


# ======================================================================
# Gate 4 — PV1 wall thickness : PARTIAL (函式 sound / production 路徑 bypass)
# ======================================================================
from lib.cad.shell.shell_spec import _validate_wall_thickness, _MIN_WALL_MM


def test_pv1_min_wall_constant():
    assert _MIN_WALL_MM == 1.5


@pytest.mark.parametrize("bad", [1.49, 1.0, 0.0, -1.0])
def test_pv1_function_SOUND_rejects_thin(bad):
    """SOUND witness:gate 函式本身對 <1.5 真 raise(非 no-op tautology)。"""
    with pytest.raises(ValueError):
        _validate_wall_thickness(bad)


def test_pv1_function_accepts_valid():
    assert _validate_wall_thickness(2.0) == 2.0
    assert _validate_wall_thickness(1.5) == 1.5


def test_pv1_EVERGREEN_phase4_preclamp_bypasses_gate():
    """EVERGREEN WITNESS:複現 phase4_handler.py:294-296 預夾邏輯。
    使用者要 1.0mm(違反契約)→ 預夾成 2.0 → 永遠不會把 <1.5 餵給 gate → gate 永不 fire。
    此測 PASS == production 路徑 bypass 確認(口委指控屬實,機制=預夾)。"""
    _lb_wall = 1.0  # 使用者/LoRA-B 想要的薄壁(契約違反)
    _wall_arg = (_lb_wall if _lb_wall and 1.5 <= _lb_wall <= 3.5 else 2.0)
    assert _wall_arg == 2.0, "預夾把 1.0 靜默改寫成 2.0 → gate 拿不到違反值"
    # 被夾後的 2.0 餵 gate 不會 raise:使用者的 1.0mm 意圖被吞掉、gate 從未裁決
    assert _validate_wall_thickness(_wall_arg) == 2.0


# ======================================================================
# Gate 5 — component role / H21 : EVERGREEN TRAP
# ======================================================================
from lib.validator import AdvancedValidator


def test_role_EVERGREEN_illegal_bridge_role_false_pass():
    """EVERGREEN WITNESS:auto_waterer 的 Pump role 改成不存在的 'TOTALLY-BOGUS-ROLE'。
    契約理想=reject;當前 live code:AdvancedValidator.validate 回 ok=True 且連 warning 都沒有。
    此測 PASS == per-component role 未被任何 gate 強制 = 恆綠陷阱確認。"""
    inst = {
        "project_name": "auto_waterer", "project_category": "Gardening",
        "inventory_mentions": [],
        "enclosure_constraints": {"target_size": "medium", "wall_thickness_mm": 2.0, "material": "PLA"},
        "components": [
            {"role": "Brain", "type": "Arduino-Uno-class", "qty": 1},
            {"role": "Power", "type": "Battery-AA-class", "qty": 1},
            {"role": "Control", "type": "Relay-Module-class", "qty": 1},
            {"role": "TOTALLY-BOGUS-ROLE", "type": "Pump-Water-class", "qty": 1},  # mutated
        ],
    }
    result = AdvancedValidator.validate(inst)
    ok = result[0]
    warns = result[2] if len(result) > 2 else []
    assert ok is True, "若變 False 代表 role gate 收緊了 → 反轉此 witness"
    assert not any("BOGUS" in str(w) for w in warns), "非法 role 連 warning 都沒有 = 完全隱形"
