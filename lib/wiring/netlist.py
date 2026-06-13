"""lib/wiring/netlist.py — A-1 net 模型：comp→MCU-pin 配對升級為 net。

net = 共用同一電氣節點（以 MCU pin 標籤為節點識別）的所有 pin 群組：
  - VCC pins 全部映射到 MCU 電源 pin（5V/3V3）→ **單一電源軌 net**
  - GND pins → **單一接地 net**
  - I2C SDA/SCL（共用 bus）→ 每條 bus 單一 net（所有 I2C 裝置共用同一 MCU pin）
  - signal pins → 各自唯一 MCU GPIO 的 2-node net

每個 net 的 nodes 為 generic ref（comp 或 MCU），故 A-4 可在此模型加
comp↔comp 跨元件 net（不經 MCU pin）。to_json 以此為 schematic ELK 的
net-level 真相（取代逐 pin 配對渲染）。

設計原則（VS-FALLBACK / 絕對禁 fallback）：
  - 每個 wiring pin 必入某 net（0 棄繪）；未分配（含 "?"）的 pin 入
    名為 "UNASSIGNED" 的 net 並由 completeness gate 暴露，**不靜默丟棄**。
"""
from __future__ import annotations

import re

# 電源/地軌標籤（MCU pin 端）：同名歸為單一軌
_POWER_RAILS = {"5V", "3V3", "3.3V", "3V", "VIN", "VCC", "VDD", "V+", "DC+"}
# NET_GND_LOGIC = 'GND'(控制端);NET_GND_LOAD = 'EXT-GND'(動力端,galvanic isolation)。
_GROUND_RAILS = {"GND", "GND1", "GND2", "GND_D", "DC-", "M-", "AGND", "EXT-GND"}
# 外部供電軌(EXT-PWR/EXT)視為 power；負載端子(LOAD/SPK/PUMP/M…)視為 contact；
# EXT-GND 為動力端負載地(與 MCU GND 完全隔離)。共同點:皆非 MCU pin,其 net 不掛 brain 假節點。
_EXT_POWER_RAILS = {"EXT-PWR", "EXT"}
_LOAD_TERMINALS = {"LOAD", "LOAD+", "LOAD-", "SPK", "SPK-", "PUMP+", "PUMP-", "M1", "M2"}
_LOAD_GND = {"EXT-GND"}
_EXTERNAL_PINS = _EXT_POWER_RAILS | _LOAD_TERMINALS | _LOAD_GND
# bus pin 標籤（comp 端 tag 或 MCU 端含此關鍵字）
_BUS_TAGS = {"SDA", "SCL", "SCK", "MISO", "MOSI"}

_POWER_COLOR = "#ff4444"
_GROUND_COLOR = "#333333"
_BUS_COLOR = "#00897b"
_SIGNAL_COLOR = "#44cc44"
_CONTACT_COLOR = "#ff8800"   # 跨元件接點 net（relay→load 等 comp↔comp）

_UNASSIGNED = "UNASSIGNED"


def _sanitize(s: str) -> str:
    """net id 用：非英數轉底線（標籤如 '5V'/'A4'/'D2' 保持可讀）。"""
    return re.sub(r"[^A-Za-z0-9]", "_", s) or "X"


def _classify(mcu: str, comp_tag: str) -> str:
    """由 MCU pin 標籤 + comp 端 tag 判定 net 類別。"""
    u = (mcu or "").upper()
    if u in _POWER_RAILS or u in _EXT_POWER_RAILS:
        return "power"
    if u in _GROUND_RAILS:
        return "ground"
    if u in _LOAD_TERMINALS:
        return "contact"
    if comp_tag.upper() in _BUS_TAGS or any(b in u for b in _BUS_TAGS):
        return "bus"
    return "signal"


def _voltage_domain(mcu: str) -> str | None:
    u = (mcu or "").upper()
    if u in ("5V", "VIN"):
        return "5V"
    if u in ("3V3", "3.3V", "3V"):
        return "3V3"
    return None


def _color_for(kind: str) -> str:
    return {
        "power": _POWER_COLOR,
        "ground": _GROUND_COLOR,
        "bus": _BUS_COLOR,
    }.get(kind, _SIGNAL_COLOR)


def build_netlist(brain_key: str, wiring: dict, *, power_source: list | None = None) -> list[dict]:
    """將 wiring（comp→pins 配對）轉為 net 清單。

    Args:
        brain_key: 正規化後的 MCU key（如 "Arduino"），作為 MCU-side 節點 ref。
        wiring:    resolve_wiring 輸出 {comp: {"label", "pins": [{comp, mcu, ...}]}}。

    Returns:
        list[net]，每 net = {
            "id":   "N$<sanitized-mcu-label>",
            "name": <mcu-label>,            # 電氣節點名（"5V"/"GND"/"D2"/"A4"）
            "kind": "power"|"ground"|"bus"|"signal",
            "voltage_domain": "5V"|"3V3"|None,
            "nodes": [{"ref","pin","side":"comp"|"mcu","dir"?,"vd"?,"color"?}],
            "color": "#rrggbb",
        }
        排序：power → ground → bus → signal，同類依 name。
    """
    wiring = wiring or {}
    nets: dict[str, dict] = {}    # net key(=MCU pin label) → net dict（含暫存 _seen）

    def _ensure(key: str, comp_tag: str) -> dict:
        if key not in nets:
            kind = _classify(key, comp_tag)
            nets[key] = {
                "id": f"N${_sanitize(key)}",
                "name": key,
                "kind": kind,
                "voltage_domain": _voltage_domain(key) if kind == "power" else None,
                "nodes": [],
                "color": _color_for(kind),
                "_seen": set(),
            }
        return nets[key]

    def _add(net: dict, ref: str, pin: str, side: str, **meta) -> None:
        sig = (ref, pin, side)
        if sig in net["_seen"]:
            return
        net["_seen"].add(sig)
        node = {"ref": ref, "pin": pin, "side": side}
        for k, v in meta.items():
            if v not in (None, ""):
                node[k] = v
        net["nodes"].append(node)

    for comp, info in wiring.items():
        for p in (info or {}).get("pins", []):
            mcu = str(p.get("mcu", "")).strip()
            comp_tag = str(p.get("comp", "")).strip()
            # A-4 / G1 comp↔comp 接點 net：mcu 形如 "Relay.COM" 表示此 pin 接到「另一
            # 元件的接點」而非 MCU（如 Pump.VCC 由繼電器 COM/NO 供電）。net 另一端節點
            # 是「來源元件接點」(side="contact")，**不是 brain** —— 修正舊行為(把 brain
            # 當假 MCU pin 掛上)。side != "comp" 故 0-棄繪 gate 仍每 pin 恰一 comp 節點。
            if mcu and "." in mcu and "?" not in mcu:
                src_comp, _, src_pin = mcu.partition(".")
                net = _ensure(mcu, comp_tag)
                net["kind"] = "contact"
                net["color"] = _CONTACT_COLOR
                net["voltage_domain"] = None
                _add(net, comp, comp_tag, "comp",
                     dir=p.get("comp_dir"), vd=p.get("comp_vd"), color=p.get("color"))
                _add(net, src_comp, src_pin or "?", "contact", color=_CONTACT_COLOR)
                continue
            key = mcu if (mcu and "?" not in mcu) else _UNASSIGNED
            net = _ensure(key, comp_tag)
            # comp 端節點（每個 wiring pin → 恰一個 comp-side 節點：保證 0 棄繪）
            _add(net, comp, comp_tag, "comp",
                 dir=p.get("comp_dir"), vd=p.get("comp_vd"), color=p.get("color"))
            # MCU 端節點（共用電氣節點；以 net key 為 pin 名，去重後恰一個）。
            # G1/G2:外部供電/負載端子(EXT-PWR/LOAD/…)非 MCU pin,不掛 brain 假節點;
            # 其來源端由 power_source 注入(G2)或留作 comp↔comp 接點。
            if key != _UNASSIGNED and key.upper() not in _EXTERNAL_PINS:
                _add(net, brain_key, key, "mcu", vd=p.get("mcu_vd"))

    # G2:電源源(battery/USB)成真 net 節點 —— 掛到它供電的軌(5V/VIN)、GND 與外部
    # 負載軌(EXT-PWR)。side="source"(additive,不影響「每 pin 恰一 comp 節點」的 0-棄繪 gate)。
    # 共地架構:電源 source device 清單 —— 各 device 的 +/- 接其 net(負極皆 common GND)。
    if power_source:
        for _dev in (power_source or []):
            _ref = _dev.get("refdes") or "PS1"
            for _term, _col in ((_dev.get("plus"), _POWER_COLOR), (_dev.get("minus"), _GROUND_COLOR)):
                if _term and _term.get("net_name"):
                    _pin = _term.get("source_pin", "V+")
                    _add(_ensure(_term["net_name"], _pin), _ref, _pin, "source", color=_col)

    # Galvanic isolation:把「經繼電器乾接點供電的負載元件」(power pin 在 contact net)的 GND
    # 從 NET_GND_LOGIC('GND')移到 NET_GND_LOAD('EXT-GND'),使兩地網路完全不相交。
    # 偵測:某元件的 VCC/V+ 落在 contact net(= 被繼電器 NO 供電)→ 它是動力端負載。
    _load_comps = set()
    for _net in nets.values():
        if _net.get("kind") != "contact":
            continue
        for _nd in _net["nodes"]:
            if _nd.get("side") == "comp" and str(_nd.get("pin", "")).upper() in ("VCC", "V+", "VIN", "5V", "+"):
                _load_comps.add(_nd["ref"])
    if _load_comps and "GND" in nets:
        _logic_gnd = nets["GND"]
        _to_move = [_nd for _nd in list(_logic_gnd["nodes"])
                    if _nd.get("side") == "comp" and _nd["ref"] in _load_comps]
        if _to_move:
            _load_gnd = _ensure("EXT-GND", "GND")
            for _nd in _to_move:
                _logic_gnd["nodes"].remove(_nd)
                _load_gnd["nodes"].append(_nd)

    out: list[dict] = []
    for net in nets.values():
        net.pop("_seen", None)
        out.append(net)
    order = {"power": 0, "ground": 1, "bus": 2, "contact": 3, "signal": 4}
    out.sort(key=lambda n: (order.get(n["kind"], 9), str(n["name"])))
    return out
