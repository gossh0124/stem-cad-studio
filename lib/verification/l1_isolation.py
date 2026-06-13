"""lib/verification/l1_isolation.py — VS-L1 galvanic isolation 契約（Axis A，純 stdlib）。

規劃書 DEC-H3 / P0.2：把核心賣點「galvanic isolation」從「程式碼存在、無測試觸發」升級為
**可計算、blocking、mutation-tested** 的契約，純 set 代數 over `build_netlist()` 輸出，
**不 embed SKiDL/PySpice/KiCad**（那是防火牆外的 Axis B 獨立 oracle）。

契約（本層 = 可由 netlist 拓樸計算者）：
  - galvanic_isolation     控制地(GND) ∩ 負載地(EXT-GND) 的 pin 集合 = ∅（三值：
                           PASS 隔離 / FAIL 綁地 / PASS-N/A 無隔離負載域）。
  - relay_domain_wiring    繼電器線圈側 pin(VCC/IN/GND) 與接點側 pin(COM/NO/NC) 不共 net
                           （device-level 隔離；線圈與乾接點物理分離的拓樸對應）。

不在本層（誠實標注，避免 stub 契約）：
  - no_infeasible_mcu_source  由 `lib/wiring/power_inject.derive_power_injection` 在上游 raise
                              `PowerInjectError` 強制（infeasible 來源根本到不了 netlist）。
  - kickback_containment      屬 value/類比域（flyback 二極體是否齊備 + 箝位電壓），
                              歸 `lib/verification/l1_passives`（P5.1）+ ngspice witness（P5.2）。

聚合：`check_isolation(nets)` 回傳 list[CheckResult]，供 l1_netlist 的 report.extend() 併入。
"""
from __future__ import annotations

from .report import CheckResult, Verdict

# 接點側 pin（繼電器乾接點 / 負載迴路）
_CONTACT_PINS = frozenset({"COM", "NO", "NC"})
# 視為「VCC/V+ 類」的負載供電 pin（與 netlist.py 隔離 post-pass 同義）
_LOGIC_GND_NAME = "GND"
_LOAD_GND_NAME = "EXT-GND"


def _net_by_name(nets: list[dict], name: str) -> dict | None:
    for n in nets:
        if n.get("name") == name:
            return n
    return None


def _pinset(net: dict | None) -> set[tuple[str, str]]:
    """net 的 (ref, pin) 集合（None → 空集）。"""
    if not net:
        return set()
    return {(nd.get("ref", ""), nd.get("pin", "")) for nd in net.get("nodes", [])}


def check_galvanic_isolation(
    nets: list[dict], *, logic_gnd: str = _LOGIC_GND_NAME, load_gnd: str = _LOAD_GND_NAME
) -> CheckResult:
    """控制地與負載地 pin 集合不相交。三值：無 EXT-GND（無隔離負載域）→ PASS-N/A。"""
    load_net = _net_by_name(nets, load_gnd)
    if load_net is None:
        return CheckResult(
            "L1", "galvanic_isolation", Verdict.PASS,
            message=f"N/A：無繼電器隔離負載域（無 {load_gnd} net）",
            metric={"applicable": False},
        )
    logic_pins = _pinset(_net_by_name(nets, logic_gnd))
    load_pins = _pinset(load_net)
    shared = logic_pins & load_pins
    if shared:
        return CheckResult(
            "L1", "galvanic_isolation", Verdict.FAIL,
            message=f"GALVANIC ISOLATION VIOLATED：{sorted(shared)} 同時在 {logic_gnd} 與 {load_gnd}（綁地，kickback 可達 MCU）",
            metric={"shared": sorted(f"{r}.{p}" for r, p in shared)},
            threshold=f"{logic_gnd} ∩ {load_gnd} == ∅",
        )
    return CheckResult(
        "L1", "galvanic_isolation", Verdict.PASS,
        message=f"{logic_gnd} 與 {load_gnd} 兩地不相交",
        metric={"n_logic": len(logic_pins), "n_load": len(load_pins)},
        threshold=f"{logic_gnd} ∩ {load_gnd} == ∅",
    )


def check_relay_domain_wiring(nets: list[dict]) -> CheckResult:
    """繼電器線圈側 pin(VCC/IN/GND…) 與接點側 pin(COM/NO/NC) 不可落在同一 net。

    偵測 relay refs = 在 contact net 以 side='contact' 出現者；對每個 relay ref，
    若任一 net 同時含其接點 pin 與線圈 pin → 線圈與乾接點被橋接 → FAIL。
    """
    relay_refs: set[str] = set()
    for n in nets:
        if n.get("kind") == "contact":
            for nd in n.get("nodes", []):
                if nd.get("side") == "contact":
                    relay_refs.add(nd.get("ref", ""))
    relay_refs.discard("")
    if not relay_refs:
        return CheckResult(
            "L1", "relay_domain_wiring", Verdict.PASS,
            message="N/A：無繼電器接點 net", metric={"applicable": False},
        )

    violations: list[str] = []
    for r in sorted(relay_refs):
        for n in nets:
            pins_of_r = {str(nd.get("pin", "")).upper()
                         for nd in n.get("nodes", []) if nd.get("ref") == r}
            has_contact = bool(pins_of_r & _CONTACT_PINS)
            has_coil = bool(pins_of_r - _CONTACT_PINS)
            if has_contact and has_coil:
                violations.append(f"{r}@{n.get('name')}:{sorted(pins_of_r)}")
    if violations:
        return CheckResult(
            "L1", "relay_domain_wiring", Verdict.FAIL,
            message="繼電器線圈側與接點側共 net（線圈未與乾接點隔離）",
            metric={"violations": violations},
            threshold="per-relay: coil-pins net ∩ contact-pins net == ∅",
        )
    return CheckResult(
        "L1", "relay_domain_wiring", Verdict.PASS,
        message="繼電器線圈側與接點側分離", metric={"n_relays": len(relay_refs)},
    )


def check_isolation(nets: list[dict]) -> list[CheckResult]:
    """聚合本層所有隔離契約 → list[CheckResult]（供 l1_netlist report.extend 併入）。"""
    return [
        check_galvanic_isolation(nets),
        check_relay_domain_wiring(nets),
    ]
