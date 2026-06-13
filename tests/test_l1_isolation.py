"""tests/test_l1_isolation.py — P0.2 galvanic isolation 契約 + mutation test。

證明契約「非空洞」：真實 auto_waterer netlist → PASS；綁地 / 線圈-接點橋接 mutant → FAIL。
"""
from lib.verification.l1_isolation import (
    check_galvanic_isolation,
    check_relay_domain_wiring,
    check_isolation,
)
from lib.verification.report import Verdict
from lib.wiring import build_netlist


_AUTO_WATERER = {
    "Relay": {"label": "繼電器", "pins": [
        {"comp": "VCC", "mcu": "5V"}, {"comp": "IN", "mcu": "D2"}, {"comp": "GND", "mcu": "GND"},
    ]},
    "SoilMoisture": {"label": "土壤濕度", "pins": [
        {"comp": "VCC", "mcu": "5V"}, {"comp": "AO", "mcu": "A0"}, {"comp": "GND", "mcu": "GND"},
    ]},
    "Pump": {"label": "水泵", "pins": [
        {"comp": "VCC", "mcu": "Relay.NO"}, {"comp": "GND", "mcu": "GND"},
    ]},
}


# ── 真實 netlist：契約 PASS ──────────────────────────────────────
def test_real_auto_waterer_isolation_passes():
    nets = build_netlist("Arduino", _AUTO_WATERER)
    gi = check_galvanic_isolation(nets)
    assert gi.verdict is Verdict.PASS, gi.message
    # N/A 不算數：本案真的有 EXT-GND 負載域
    assert gi.metric.get("applicable") is not False
    rd = check_relay_domain_wiring(nets)
    assert rd.verdict is Verdict.PASS, rd.message
    assert all(c.verdict is Verdict.PASS for c in check_isolation(nets))


# ── Mutation 1：綁地 → galvanic FAIL（證明非空洞）──────────────────
def test_bonded_ground_mutant_fails():
    nets = build_netlist("Arduino", _AUTO_WATERER)
    # 把 Pump.GND 同時塞回 logic GND（綁地 mutant）
    gnd = next(n for n in nets if n["name"] == "GND")
    gnd["nodes"].append({"ref": "Pump", "pin": "GND", "side": "comp"})
    gi = check_galvanic_isolation(nets)
    assert gi.verdict is Verdict.FAIL, "綁地 mutant 未被抓到（契約空洞）"
    assert "Pump.GND" in gi.metric.get("shared", [])


# ── 三值：無隔離負載域 → PASS-N/A ────────────────────────────────
def test_no_load_domain_is_na_pass():
    nets = build_netlist("Arduino", {
        "OLED": {"label": "OLED", "pins": [
            {"comp": "VCC", "mcu": "5V"}, {"comp": "GND", "mcu": "GND"},
        ]},
    })
    gi = check_galvanic_isolation(nets)
    assert gi.verdict is Verdict.PASS
    assert gi.metric.get("applicable") is False


# ── Mutation 2：線圈側與接點側共 net → relay_domain FAIL ───────────
def test_relay_coil_contact_bonded_mutant_fails():
    # 手構 net：同一 net 同時含 Relay.COM(接點) 與 Relay.VCC(線圈) → 橋接
    nets = [
        {"name": "BAD", "kind": "signal", "nodes": [
            {"ref": "Relay", "pin": "COM", "side": "comp"},
            {"ref": "Relay", "pin": "VCC", "side": "comp"},
        ]},
        {"name": "Relay.NO", "kind": "contact", "nodes": [
            {"ref": "Pump", "pin": "VCC", "side": "comp"},
            {"ref": "Relay", "pin": "NO", "side": "contact"},
        ]},
    ]
    rd = check_relay_domain_wiring(nets)
    assert rd.verdict is Verdict.FAIL, "線圈-接點橋接 mutant 未被抓到"
