"""tests/test_wiring_netlist.py — A-1 net 模型完整性 gate。

驗證 build_netlist 滿足 A-1 gate：
  - 每 pin 入 net（comp-side 節點數 == wiring pin 數）
  - 0 棄繪（無 UNASSIGNED net）
  - 電源軌單一 net（每電壓域至多一條）/ 接地單一 net
  - I2C bus 共用（多裝置共用同一 SDA/SCL → 單一 bus net）
"""
import pytest

from lib.wiring import build_netlist, resolve_wiring, to_json, PinAllocationError
from lib.wiring.wiring_data import COMP_PIN_NEEDS


def _pin_count(wiring: dict) -> int:
    return sum(len((info or {}).get("pins", [])) for info in wiring.values())


def _comp_node_count(nets: list) -> int:
    return sum(1 for n in nets for nd in n["nodes"] if nd["side"] == "comp")


# ── 每個元件：pin 全入 net、0 棄繪、電源軌單一 ──────────────────

@pytest.mark.parametrize("comp", sorted(COMP_PIN_NEEDS.keys()))
def test_every_component_pins_all_in_nets(comp):
    bk = "Arduino"
    try:
        wiring = resolve_wiring(bk, [comp])
    except PinAllocationError:
        pytest.skip(f"{comp} 無法在 Arduino 分配 pin")
    if not wiring:
        pytest.skip(f"{comp} 無 wiring 模板")

    nets = build_netlist(bk, wiring)
    # 每 pin 恰一個 comp-side 節點 → 0 棄繪
    assert _comp_node_count(nets) == _pin_count(wiring), f"{comp}: 有 pin 未入 net"
    assert not any(n["name"] == "UNASSIGNED" for n in nets), f"{comp}: 出現 UNASSIGNED net（pin 未分配）"
    # 每電壓域電源軌單一
    power = [n for n in nets if n["kind"] == "power"]
    assert len({n["voltage_domain"] for n in power}) == len(power), f"{comp}: 電源軌分裂為多 net"
    # 接地單一
    assert len([n for n in nets if n["kind"] == "ground"]) <= 1, f"{comp}: 接地分裂"
    # 每 net 至少一節點
    assert all(n["nodes"] for n in nets)


# ── 合成多元件：電源軌 / 接地 / I2C bus 共用 ────────────────────

_I2C_TWO_DEVICES = {
    "OLED": {"label": "OLED 顯示", "pins": [
        {"comp": "VCC", "mcu": "5V", "color": "#ff4444"},
        {"comp": "GND", "mcu": "GND", "color": "#333333"},
        {"comp": "SDA", "mcu": "A4", "color": "#00897b"},
        {"comp": "SCL", "mcu": "A5", "color": "#00897b"},
    ]},
    "RTC": {"label": "RTC 時鐘", "pins": [
        {"comp": "VCC", "mcu": "5V", "color": "#ff4444"},
        {"comp": "GND", "mcu": "GND", "color": "#333333"},
        {"comp": "SDA", "mcu": "A4", "color": "#00897b"},
        {"comp": "SCL", "mcu": "A5", "color": "#00897b"},
    ]},
}


def test_power_rail_single_net_two_devices():
    nets = build_netlist("Arduino", _I2C_TWO_DEVICES)
    by_name = {n["name"]: n for n in nets}
    # 兩裝置 VCC 共用單一 5V 電源軌 net（含 2 comp + 1 MCU 節點）
    assert by_name["5V"]["kind"] == "power"
    assert by_name["5V"]["voltage_domain"] == "5V"
    assert len([nd for nd in by_name["5V"]["nodes"] if nd["side"] == "comp"]) == 2
    assert len([nd for nd in by_name["5V"]["nodes"] if nd["side"] == "mcu"]) == 1


def test_ground_single_net_two_devices():
    nets = build_netlist("Arduino", _I2C_TWO_DEVICES)
    ground = [n for n in nets if n["kind"] == "ground"]
    assert len(ground) == 1
    assert len([nd for nd in ground[0]["nodes"] if nd["side"] == "comp"]) == 2


def test_i2c_bus_shared_single_net():
    """兩 I2C 裝置共用 A4(SDA)/A5(SCL) → 各群成單一 bus net（非每裝置一條）。"""
    nets = build_netlist("Arduino", _I2C_TWO_DEVICES)
    by_name = {n["name"]: n for n in nets}
    for bus_pin in ("A4", "A5"):
        net = by_name[bus_pin]
        assert net["kind"] == "bus", f"{bus_pin} 應為 bus net"
        assert len([nd for nd in net["nodes"] if nd["side"] == "comp"]) == 2, \
            f"{bus_pin} bus 未被兩裝置共用"
        assert len([nd for nd in net["nodes"] if nd["side"] == "mcu"]) == 1


def test_net_count_not_per_pin():
    """net 數應遠少於 pin 數（共軌/共 bus 已合併）。"""
    nets = build_netlist("Arduino", _I2C_TWO_DEVICES)
    n_pins = _pin_count(_I2C_TWO_DEVICES)  # 8
    # 5V / GND / A4 / A5 = 4 nets < 8 pins
    assert len(nets) == 4
    assert len(nets) < n_pins


# ── to_json 整合 ────────────────────────────────────────────────

def _resolvable_comps(n: int = 2) -> list:
    """取 n 個 resolve_wiring 可產出非空 wiring 的 canonical 元件名。"""
    out = []
    for c in sorted(COMP_PIN_NEEDS.keys()):
        try:
            w = resolve_wiring("Arduino", [c])
        except PinAllocationError:
            continue
        if w:
            out.append(c)
        if len(out) >= n:
            break
    return out


def test_to_json_includes_nets():
    comps = _resolvable_comps(2)
    assert comps, "找不到可解析的元件（COMP_PIN_NEEDS 全無模板？）"
    out = to_json("Arduino", comps)
    assert "nets" in out
    assert isinstance(out["nets"], list) and out["nets"], \
        f"nets 為空（comps={comps}, wiring keys={list(out['wiring'])}）"
    n = out["nets"][0]
    assert {"id", "name", "kind", "nodes", "color"} <= set(n)
    # net id 前綴
    assert all(net["id"].startswith("N$") for net in out["nets"])


def test_comp_to_comp_contact_net():
    """G1 (Phase 1): comp↔comp 接點(Pump.VCC→Relay.COM)的另一端是來源元件 Relay,
    不是 brain;且不破壞 0-棄繪 gate(pump 端仍恰一 comp 節點)。"""
    wiring = {"Pump": {"label": "微型水泵", "pins": [
        {"comp": "VCC", "mcu": "Relay.COM", "color": "#ff8800"},
    ]}}
    nets = build_netlist("Arduino", wiring)
    contact = [n for n in nets if n["kind"] == "contact"]
    assert len(contact) == 1, "comp↔comp 應產生 contact net"
    net = contact[0]
    refs = {nd["ref"] for nd in net["nodes"]}
    assert "Relay" in refs, "contact net 另一端應為來源元件 Relay"
    assert "Arduino" not in refs, "contact net 不應把 brain 當假 MCU pin 掛上"
    # 0-棄繪 gate：pump 端恰一個 comp 節點（contact 端 side='contact' 不計）
    assert _comp_node_count(nets) == _pin_count(wiring) == 1


def test_unassigned_pin_surfaced_not_dropped():
    """未分配 pin（mcu='?'）必入 UNASSIGNED net（暴露非靜默棄繪）。"""
    wiring = {"X": {"label": "X", "pins": [
        {"comp": "SIG", "mcu": "?", "color": "#44cc44"},
    ]}}
    nets = build_netlist("Arduino", wiring)
    assert any(n["name"] == "UNASSIGNED" for n in nets)
    # pin 仍入 net（0 棄繪）
    assert _comp_node_count(nets) == 1


# ── Galvanic isolation post-pass（P0.3：真觸發 EXT-GND 隔離分支）──────────────
# 規劃書 P0.3：build_netlist 的隔離 post-pass(netlist.py:165-183)過去無任何測試觸發
# ——既有 test_comp_to_comp_contact_net 的 Pump 只有 VCC、無 GND，_to_move 恆空。
# 這裡讓負載元件「同時」有 contact-net VCC + logic-GND，才會真正走到搬移分支。

_AUTO_WATERER_ISO = {
    "Relay": {"label": "繼電器", "pins": [
        {"comp": "VCC", "mcu": "5V", "color": "#ff4444"},
        {"comp": "IN", "mcu": "D2", "color": "#44cc44"},
        {"comp": "GND", "mcu": "GND", "color": "#333333"},
    ]},
    "SoilMoisture": {"label": "土壤濕度", "pins": [
        {"comp": "VCC", "mcu": "5V", "color": "#ff4444"},
        {"comp": "AO", "mcu": "A0", "color": "#ffaa00"},
        {"comp": "GND", "mcu": "GND", "color": "#333333"},
    ]},
    "Pump": {"label": "水泵", "pins": [
        {"comp": "VCC", "mcu": "Relay.NO", "color": "#ff8800"},  # 負載經繼電器乾接點供電
        {"comp": "GND", "mcu": "GND", "color": "#333333"},        # 負載回流 → 應隔離至 EXT-GND
    ]},
}


def _comp_refs(net: dict) -> set:
    return {nd["ref"] for nd in net["nodes"] if nd["side"] == "comp"}


def test_galvanic_isolation_load_gnd_moves_to_ext_gnd():
    """繼電器供電的負載(Pump)其 GND 應被移到 EXT-GND，與 logic GND 完全不相交。
    這是核心 galvanic-isolation 契約;mutation-resistant:斷言搬移確實發生（非空洞通過）。"""
    nets = build_netlist("Arduino", _AUTO_WATERER_ISO)
    by_name = {n["name"]: n for n in nets}
    assert "EXT-GND" in by_name, "負載 GND 未被隔離出 EXT-GND（post-pass 未觸發）"
    logic_gnd = _comp_refs(by_name["GND"])
    load_gnd = _comp_refs(by_name["EXT-GND"])
    assert logic_gnd & load_gnd == set(), f"兩地相交（綁地）：{logic_gnd & load_gnd}"
    assert "Pump" in load_gnd, "Pump.GND 未移到 EXT-GND（post-pass 空洞通過）"
    assert "Pump" not in logic_gnd, "Pump.GND 仍殘留 logic GND"


def test_galvanic_isolation_control_stays_on_logic_gnd():
    """負向(M1):控制端(Relay/SoilMoisture)GND 必須留在 logic GND，
    不可被過度隔離誤搬 EXT-GND。"""
    nets = build_netlist("Arduino", _AUTO_WATERER_ISO)
    by_name = {n["name"]: n for n in nets}
    logic_gnd = _comp_refs(by_name["GND"])
    load_gnd = _comp_refs(by_name["EXT-GND"]) if "EXT-GND" in by_name else set()
    assert {"Relay", "SoilMoisture"} <= logic_gnd, "控制端 GND 不應離開 logic GND"
    assert not ({"Relay", "SoilMoisture"} & load_gnd), "控制端被過度隔離至 EXT-GND"
