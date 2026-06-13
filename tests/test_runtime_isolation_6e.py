"""tests/test_runtime_isolation_6e.py — #28 A+B:galvanic isolation L1 gate 接進
runtime 自由輸入路徑 + 機器 verdict 化為 6E「Evaluate」教材。

緣由(#28,workflow wp67jngwi + 對抗式 verify confirmed):lib/verification/l1_isolation
的 galvanic isolation 契約**原僅在 CI 對 canned 跑**,runtime 自由輸入(LLM 生成)設計不
受其把關;且自由輸入的 6E 教育 payload 薄(engineering_decisions 無 stem_concept,前端期待
卻收 null)。本批把該契約接進 Phase 3 runtime,**同時**(A)摺入 phase3_constraint_check →
經既有 P3 gate 攔截不合物理設計,(B)把 verdict 化為 6E engineering_decisions 教材 —— 教育
內容**溯回機器 gate verdict**,而非 LLM 自我宣稱(計畫書核心原則:computable contracts,
never self-declaration)。

兩層鎖:
  ① 真實資料路徑(無 mock):runtime generate_wiring 往外傳 nets + 真 check_isolation +
     真 _emit_isolation_education(證資料是真 netlist,非造出來的)。
  ② fold/block 端到端:execute 把 isolation 摺入 overall_ok + results,FAIL → P3 gate 觸發
     (列「電氣隔離」),教材標 VIOLATED。
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch

from services.phase_handlers.phase3_handler import Phase3Handler
from services.phase_handlers._phase3_wiring import generate_wiring
from services.shared.models import Job
from services.pipeline import gate_logic
from lib.verification.l1_isolation import check_isolation
from lib.verification.report import CheckResult, Verdict
from lib.bom_calculator import BomSummary
from lib.canned_template_defs import TEMPLATE_DEFS

from tests.test_phase3_handler import _basic_bridge


# ── helpers ──────────────────────────────────────────────────────
def _runtime_nets(components):
    """跑 runtime wiring 路徑(generate_wiring)→ 回 netlist(build_netlist 模型)。"""
    brain = next((c["type"] for c in components if c.get("role") == "Brain"), "")
    wd = generate_wiring(components, brain, None)
    return (wd or {}).get("nets", [])


def _basic_bom(total_ma=50.0, budget_ma=500.0):
    return BomSummary(
        rows=[{"role": "Brain", "type": "Arduino-Uno-class", "label": "Uno",
               "qty": 1, "unit_ma": total_ma, "total_ma": total_ma,
               "unit_ntd": 250, "total_ntd": 250}],
        total_ma=total_ma, total_ntd=250, supply_v=5.0,
        power_type="USB-5V-class", current_budget_ma=budget_ma,
    )


_ISO_NA = [CheckResult("L1", "galvanic_isolation", Verdict.PASS,
                       metric={"applicable": False}, message="N/A")]


# ═══ 層 ① 真實資料路徑(無 mock) ═══════════════════════════════════

def test_generate_wiring_propagates_nets_with_ext_gnd():
    """回歸鎖(Edit 1):generate_wiring 往外傳 nets,且隔離負載設計(auto_waterer)
    產出含 EXT-GND 的 netlist。原本 nets 在 generate_wiring 被丟棄 → runtime 拿不到。"""
    comps = TEMPLATE_DEFS["auto_waterer"]["components"]
    nets = _runtime_nets(comps)
    assert nets, "generate_wiring 未往外傳 nets(或 build_netlist 失敗)"
    names = {n.get("name") for n in nets}
    assert "EXT-GND" in names, f"隔離負載設計應產出 EXT-GND 負載地域,實得 {names}"
    assert "GND" in names


def test_runtime_isolated_design_passes_and_emits_pass_education():
    """真實 netlist + 真 check_isolation:auto_waterer 兩地不相交 → galvanic PASS-applicable;
    _emit_isolation_education 產一則 6E『evaluate』教材,內容反映 PASS(教育溯回 verdict)。"""
    comps = TEMPLATE_DEFS["auto_waterer"]["components"]
    results = check_isolation(_runtime_nets(comps))
    gi = next(r for r in results if r.name == "galvanic_isolation")
    assert gi.verdict == Verdict.PASS and gi.metric.get("applicable", True) is True

    bridge: dict = {}
    Phase3Handler()._emit_isolation_education(bridge, results)
    iso = [d for d in bridge.get("engineering_decisions", [])
           if d.get("category") == "galvanic_isolation"]
    assert len(iso) == 1, "應產生恰一則 galvanic_isolation 6E 教材"
    d = iso[0]
    assert d["6e_stage"] == "evaluate"
    assert d["stem_concept"], "6E 教材須帶 stem_concept(補前端 null)"
    assert "通過" in d["description"]                 # PASS 內容
    assert "L·di/dt" in d["description"]               # 物理原理溯回


def test_runtime_bonded_ground_mutation_fails_and_education_says_violated():
    """mutation:把 EXT-GND 的一隻接腳併入 GND(綁地)→ 真 check_isolation FAIL;
    6E 教材標 VIOLATED 並含被綁定的接腳(內容溯回 gate 的 shared 集合,非自由文字)。"""
    comps = TEMPLATE_DEFS["auto_waterer"]["components"]
    nets = _runtime_nets(comps)
    gnd = next(n for n in nets if n.get("name") == "GND")
    extg = next(n for n in nets if n.get("name") == "EXT-GND")
    bonded_node = dict(extg["nodes"][0])           # 同一 (ref,pin) 落兩地 = 綁地
    gnd["nodes"].append(bonded_node)

    results = check_isolation(nets)
    gi = next(r for r in results if r.name == "galvanic_isolation")
    assert gi.verdict == Verdict.FAIL

    bridge: dict = {}
    Phase3Handler()._emit_isolation_education(bridge, results)
    d = next(x for x in bridge["engineering_decisions"]
             if x["category"] == "galvanic_isolation")
    assert "違反" in d["description"]
    assert bonded_node["ref"] in d["description"]   # 溯回實際綁定的接腳


def test_non_isolated_design_emits_no_isolation_education():
    """無隔離負載域(Brain+Sensor)→ galvanic N/A → 不產生隔離教學點(避免噪音,
    且不誤把 N/A 當『通過』教材)。"""
    comps = [{"role": "Brain", "type": "Arduino-Uno-class"},
             {"role": "Sensor", "type": "Sensor-TempHumid-class"}]
    results = check_isolation(_runtime_nets(comps))
    gi = next(r for r in results if r.name == "galvanic_isolation")
    assert gi.metric.get("applicable", True) is False
    bridge: dict = {}
    Phase3Handler()._emit_isolation_education(bridge, results)
    assert not [d for d in bridge.get("engineering_decisions", [])
                if d.get("category") == "galvanic_isolation"]


# ═══ 層 ② fold / block 端到端(execute) ═══════════════════════════

@patch("services.phase_handlers.base._raw_save_bridge", return_value=None)
@patch("services.phase_handlers.phase3_handler._calculate_bom")
@patch("services.phase_handlers.phase3_handler._check_isolation")
def test_execute_folds_isolation_into_constraint_check_pass(mock_iso, mock_bom, _save):
    """execute 把 isolation 摺入 phase3_constraint_check.results['isolation'] + overall_ok;
    PASS-applicable → overall_ok 不受影響 + 產 6E 教材。"""
    mock_bom.return_value = _basic_bom()
    mock_iso.return_value = [CheckResult(
        "L1", "galvanic_isolation", Verdict.PASS,
        metric={"n_logic": 3, "n_load": 2}, message="GND 與 EXT-GND 兩地不相交")]
    job = Job(job_id="iso-pass", project_name="IsoPass")
    rb, art = Phase3Handler().execute(job, _basic_bridge(), None)

    chk = rb["phase3_constraint_check"]
    assert "isolation" in chk["results"]
    assert chk["results"]["isolation"]["ok"] is True
    assert art["overall_ok"] is True
    assert any(d.get("category") == "galvanic_isolation"
               for d in rb.get("engineering_decisions", []))


@patch("services.phase_handlers.base._raw_save_bridge", return_value=None)
@patch("services.phase_handlers.phase3_handler._calculate_bom")
@patch("services.phase_handlers.phase3_handler._check_isolation")
def test_execute_isolation_fail_blocks_via_gate(mock_iso, mock_bom, _save):
    """isolation FAIL → overall_ok=False + results['isolation'].ok=False;P3 gate 觸發
    (列『電氣隔離』失敗類別)→ 經既有 HITL 攔截,非靜默放行;6E 教材標 VIOLATED。"""
    mock_bom.return_value = _basic_bom()           # 功率合格,唯一失敗來自隔離
    mock_iso.return_value = [CheckResult(
        "L1", "galvanic_isolation", Verdict.FAIL,
        metric={"shared": ["BT1.GND"]},
        message="GALVANIC ISOLATION VIOLATED：BT1.GND 同時在 GND 與 EXT-GND")]
    job = Job(job_id="iso-fail", project_name="IsoFail")
    rb, art = Phase3Handler().execute(job, _basic_bridge(), None)

    assert art["overall_ok"] is False
    assert rb["phase3_constraint_check"]["results"]["isolation"]["ok"] is False

    # block 證明:P3 gate payload 觸發且列出「電氣隔離」
    payload, _suggestions = gate_logic.p3_gate_payload(job, rb)
    assert payload is not None, "isolation FAIL 應觸發 P3 gate(非靜默放行)"
    assert "電氣隔離" in payload["overbudget_detail"]["failed_categories"]

    # 6E 教材溯回 verdict
    d = next(x for x in rb["engineering_decisions"]
             if x["category"] == "galvanic_isolation")
    assert "違反" in d["description"] and "BT1.GND" in d["description"]


# ═══ 層 ② 推廣:電源功率預算 6E 教材(DEC-H8 推廣,#28 B10) ═══════════

@patch("services.phase_handlers.base._raw_save_bridge", return_value=None)
@patch("services.phase_handlers.phase3_handler._calculate_bom")
@patch("services.phase_handlers.phase3_handler._check_isolation", return_value=_ISO_NA)
def test_execute_emits_power_budget_education_pass(_iso, mock_bom, _save):
    """power_ok → 6E『evaluate』電源功率預算教材,數值溯回 BOM(50mA/500mA)+ stem_concept。"""
    mock_bom.return_value = _basic_bom(total_ma=50.0, budget_ma=500.0)
    job = Job(job_id="pwr-pass", project_name="PwrPass")
    rb, _art = Phase3Handler().execute(job, _basic_bridge(), None)

    pb = [d for d in rb.get("engineering_decisions", [])
          if d.get("category") == "power_budget"]
    assert len(pb) == 1
    d = pb[0]
    assert d["6e_stage"] == "evaluate" and d["stem_concept"]
    assert "通過" in d["description"]
    assert "50" in d["description"] and "500" in d["description"]   # 溯回真實數值
    assert "brown-out" in d["description"]                          # 物理原理


@patch("services.phase_handlers.base._raw_save_bridge", return_value=None)
@patch("services.phase_handlers.phase3_handler._calculate_bom")
@patch("services.phase_handlers.phase3_handler._check_isolation", return_value=_ISO_NA)
def test_execute_emits_power_budget_education_fail(_iso, mock_bom, _save):
    """power 超標 → 6E 教材標超標 + 超出百分比(600/500 = +20%),數值溯回 BOM。"""
    mock_bom.return_value = _basic_bom(total_ma=600.0, budget_ma=500.0)
    job = Job(job_id="pwr-fail", project_name="PwrFail")
    rb, _art = Phase3Handler().execute(job, _basic_bridge(), None)

    d = next(x for x in rb["engineering_decisions"]
             if x["category"] == "power_budget")
    assert "超標" in d["description"]
    assert "600" in d["description"] and "20%" in d["description"]
