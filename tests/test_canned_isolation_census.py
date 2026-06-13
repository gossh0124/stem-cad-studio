"""tests/test_canned_isolation_census.py — P1: galvanic isolation 全 canned demo 拓樸 census
(Axis-A,純 stdlib,CI-blocking,firewall-safe 不 import skidl)。

verify-first 探勘(workflow wbg1jyqdj)+ 逐 demo 拓樸 dig 的最終結論(已修正初版 census 的 over-claim):
旗艦 galvanic isolation 契約(NET_GND_LOGIC 'GND' 與 NET_GND_LOAD 'EXT-GND' pin 集不相交)對 16 個
canned demo **全部正確**——其中 15 個回 PASS-N/A 是**拓樸誠實**,非缺陷、非漂綠:

- **唯一真實隔離 = auto_waterer**:Relay + 板上負載 `Pump.VCC→Relay.NO`(Pump 在 BOM 消費繼電器輸出)
  → post-pass 把 Pump.GND 搬 EXT-GND → 兩地不相交、applicable=True。
- **繼電器 demo 但負載外接(N/A 忠實)**:access_control(電磁鎖)/ rc_car / auto_curtain —— Relay 乾接點
  隔離機制**存在且正確**(coil 側與 COM/NO 接點側分離,見 relay_domain_wiring),但 `Relay.NO→LOAD+`
  是**外接螺端、無板上元件消費**(STEM 套件中學生自接負載)→ 無建模負載地可查 → galvanic_isolation
  正確回 N/A。**這不是缺陷**:無法檢查一個未建模的負載地;強制產 EXT-GND 會**捏造不存在的隔離**
  (反向 no-silent-fallback 違規)。
- **直驅致動器、無繼電器(N/A by topology)**:biped_robot(servo×4)等 —— 致動器邏輯地本就與 MCU
  共地(設計如此),galvanic-isolation-via-relay 契約**不適用**。

本 census 把上述拓樸事實鎖成 regression guard:① 16/16 build + 無綁地 FAIL;② applicable=True 恰當且
**iff** demo 有板上繼電器負載消費者(目前唯 auto_waterer);③ 繼電器 demo 集 = BOM 有 Relay 者,且其
coil/contact 分離全 PASS。任一 demo 改為「板上消費繼電器負載」(→真隔離)或退化,census 不符即 FAIL。

殘留可選增強(非缺陷,需 demo 設計決策):把 access_control/rc_car/auto_curtain 的外接負載比照
auto_waterer 改為板上建模(需各繼電器所控負載身分 + 該元件在 SSOT),即可使其成為真實 in-model 隔離。
"""
import pytest

from lib.canned_template_defs import TEMPLATE_DEFS
from lib.wiring import to_json
from lib.wiring.engine import resolve_wiring, normalize_brain, normalize_comps
from lib.verification.l1_isolation import check_galvanic_isolation, check_relay_domain_wiring
from lib.verification.report import Verdict

# production bake 投影一致(scripts/builders/bake_canned_bridges.py:267-268)。
_EXCLUDED_ROLES = ("Power", "Housing", "Brain")

# committed census witness ——————————————————————————————————————————————
# 唯一達成真實 in-model galvanic isolation 的 demo(Relay + 板上負載消費 Relay.NO → 產出 EXT-GND)。
_GENUINE_ISOLATION = {"auto_waterer"}
# 有繼電器(乾接點隔離機制)但所控負載外接、未在板上建模 → galvanic_isolation N/A 忠實。
_RELAY_LOAD_OFFBOARD = {"access_control", "rc_car", "auto_curtain"}


def _projection(demo: str):
    comps = TEMPLATE_DEFS[demo]["components"]
    brain = next((c["type"] for c in comps if c.get("role") == "Brain"), "Arduino-Uno-class")
    comp_names = [c["type"] for c in comps if c.get("role") not in _EXCLUDED_ROLES]
    return brain, comp_names


def _demo_nets(demo: str) -> list[dict]:
    brain, comp_names = _projection(demo)
    return to_json(brain, comp_names)["nets"]


def _applicable(cr) -> bool:
    """三值:metric.applicable 缺鍵 → 真實隔離(applicable);=False → N/A(無 EXT-GND 負載域)。"""
    return cr.metric.get("applicable", True)


def _has_relay(demo: str) -> bool:
    return any("Relay" in c["type"] for c in TEMPLATE_DEFS[demo]["components"])


def _onboard_relay_load(demo: str) -> list[str]:
    """板上消費繼電器輸出的元件腳(某元件 pin 的 mcu 接到 '<Relay>.NO')——即在板上建模的隔離負載。"""
    brain, comp_names = _projection(demo)
    w = resolve_wiring(normalize_brain(brain), normalize_comps(comp_names))
    return [f"{comp}.{p.get('comp')}->{p.get('mcu')}"
            for comp, info in w.items()
            for p in info.get("pins", [])
            if comp != "Relay" and str(p.get("mcu", "")).endswith(".NO")]


@pytest.mark.parametrize("demo", sorted(TEMPLATE_DEFS))
def test_demo_builds_and_no_genuine_isolation_fail(demo):
    """16/16 demo 經真實 demo→netlist 路徑建出且無綁地 FAIL(兩地不相交或無負載地);
    有繼電器者其 coil 側與接點側分離(隔離機制正確)。"""
    nets = _demo_nets(demo)
    assert check_galvanic_isolation(nets).verdict == Verdict.PASS, \
        f"{demo} galvanic isolation FAIL(綁地?)"
    assert check_relay_domain_wiring(nets).verdict == Verdict.PASS, \
        f"{demo} relay 線圈側與接點側未分離"


@pytest.mark.parametrize("demo", sorted(TEMPLATE_DEFS))
def test_applicable_iff_onboard_relay_load(demo):
    """applicable(真實隔離)成立 **iff** demo 有板上繼電器負載消費者;且恰等於 committed
    _GENUINE_ISOLATION。任一 demo 由「外接負載」改為「板上建模」(→真隔離)即須更新此表。"""
    applicable = _applicable(check_galvanic_isolation(_demo_nets(demo)))
    onboard = bool(_onboard_relay_load(demo))
    assert applicable == onboard, (
        f"{demo}: applicable={applicable} 但板上繼電器負載={onboard} —— "
        "兩者應一致(applicable 來自板上負載消費 Relay.NO → 產 EXT-GND)")
    assert applicable == (demo in _GENUINE_ISOLATION), (
        f"{demo}: applicable={applicable} 與 census 期望 {demo in _GENUINE_ISOLATION} 不符;"
        "若 demo 已建模板上負載達成真隔離,請把它移入 _GENUINE_ISOLATION")


def test_relay_topology_census_is_honest():
    """拓樸 census(取代初版 over-claim 的『gap/缺陷』框架):
    - 繼電器 demo(BOM 有 Relay)恰為 真實隔離 ∪ 負載外接;
    - 其中唯 auto_waterer 有板上負載消費者(真隔離);其餘 3 個負載外接 → N/A 忠實;
    - biped_robot 等無繼電器 → galvanic-isolation 不適用(非繼電器 demo)。"""
    relay_demos = {d for d in TEMPLATE_DEFS if _has_relay(d)}
    assert relay_demos == _GENUINE_ISOLATION | _RELAY_LOAD_OFFBOARD, (
        f"繼電器 demo 集 {sorted(relay_demos)} 與 census "
        f"{sorted(_GENUINE_ISOLATION | _RELAY_LOAD_OFFBOARD)} 不符")
    # 唯一板上隔離負載 = auto_waterer
    onboard = {d for d in relay_demos if _onboard_relay_load(d)}
    assert onboard == _GENUINE_ISOLATION, f"板上繼電器負載 demo {sorted(onboard)} 應只有 auto_waterer"
    # 負載外接者:有繼電器、無板上消費者、且 galvanic_isolation N/A(忠實,非缺陷)
    for d in _RELAY_LOAD_OFFBOARD:
        assert _has_relay(d) and not _onboard_relay_load(d)
        assert not _applicable(check_galvanic_isolation(_demo_nets(d))), \
            f"{d} 應為 N/A(負載外接);若已板上建模請移入 _GENUINE_ISOLATION"
    # biped_robot:無繼電器(伺服直驅),不在繼電器 demo 集
    # (取代已移除的 obstacle_car;2026-06-13,biped 取代 obstacle_car)
    assert not _has_relay("biped_robot") and "biped_robot" not in relay_demos
    # 非退化:真隔離集非空、與外接集不重疊
    assert _GENUINE_ISOLATION and not (_GENUINE_ISOLATION & _RELAY_LOAD_OFFBOARD)
