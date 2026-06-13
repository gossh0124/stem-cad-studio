"""scripts/crosscheck/axis_b_isolation.py — Axis-B:SKiDL 獨立重建 auto_waterer + galvanic isolation。

防火牆外(DEC-H4):此檔 **import skidl**,必須以 venv313 的 python 執行(SKiDL 不支援 3.14)。
in-repo 測試(tests/test_crosscheck_results.py)**不** import 此檔,只讀其產出的 JSON。

獨立性:電路由**設計意圖**重建(控制域共 GND_LOGIC、負載域共 GND_LOAD,relay 乾接點 COM/NO
物理隔離兩地),**非**從 Axis-A 的 build_netlist 複製。两軸對同一 demo 各自獨立導出,若一致即交叉驗證。

用法(orchestrator 會自動以 venv313 呼叫):
  <venv313>/python.exe scripts/crosscheck/axis_b_isolation.py <axis_a.json> <out.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _pinset(net):
    """SKiDL Net → {(ref, pin_name)}(用 SKiDL 自身 net 物件,非 Axis-A 資料)。"""
    return {(p.ref, p.name) for p in net.pins}


def _build(bond_grounds: bool):
    """由設計意圖獨立重建 auto_waterer;回 (gnd_logic_set, gnd_load_set, erc_errors)。

    bond_grounds=True 為 mutant:把負載地接回控制地(模擬隔離被破壞)。
    """
    from skidl import Part, Pin, Net, ERC, SKIDL, TEMPLATE, reset
    import skidl

    reset()
    PASSIVE = Pin.types.PASSIVE

    def mod(ref_name, prefix, pin_names):
        tmpl = Part(tool=SKIDL, name=ref_name, ref_prefix=prefix,
                    pins=[Pin(num=str(i + 1), name=nm, func=PASSIVE)
                          for i, nm in enumerate(pin_names)],
                    dest=TEMPLATE)
        part = tmpl()
        part.ref = ref_name  # 顯式命名以對齊 Axis-A 的元件短名(供 node-set 比對)
        return part

    arduino = mod("Arduino", "U", ["5V", "GND", "D2", "A0"])
    soil = mod("SoilMoisture", "U", ["VCC", "GND", "AO"])
    relay = mod("Relay", "K", ["VCC", "GND", "IN", "COM", "NO"])
    pump = mod("Pump", "M", ["VCC", "GND"])
    battery = mod("BatteryAA", "BT", ["V+", "GND"])

    gnd_logic = Net("GND_LOGIC")
    gnd_load = Net("GND_LOAD")
    v5 = Net("5V")
    a0 = Net("A0")
    d2 = Net("D2")
    ext_pwr = Net("EXT_PWR")
    load_plus = Net("LOAD")

    # 控制域(共 GND_LOGIC)
    gnd_logic += arduino["GND"], soil["GND"], relay["GND"]
    v5 += arduino["5V"], soil["VCC"], relay["VCC"]
    a0 += arduino["A0"], soil["AO"]
    d2 += arduino["D2"], relay["IN"]
    # 負載域(共 GND_LOAD)—— relay 乾接點(COM/NO)為唯一跨域連接,物理隔離兩地
    gnd_load += battery["GND"], pump["GND"]
    ext_pwr += battery["V+"], relay["COM"]
    load_plus += relay["NO"], pump["VCC"]

    if bond_grounds:
        gnd_logic += pump["GND"]  # MUTANT:負載地接回控制地 → 隔離破壞,两地共用 Pump.GND

    # 原生 SKiDL ERC(unconnected / drive-conflict);隔離契約以 SKiDL net 物件直接集合判定。
    erc_errors = -1
    try:
        ERC()
        erc_errors = int(skidl.erc_logger.error.count)
    except Exception:
        erc_errors = -1  # ERC 執行失敗不阻斷隔離判定(隔離以下方 set 代數為準)

    return _pinset(gnd_logic), _pinset(gnd_load), erc_errors


def main() -> int:
    axis_a_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    axis_a = json.loads(axis_a_path.read_text(encoding="utf-8"))

    import skidl

    # 正常電路
    logic, load, erc_ok = _build(bond_grounds=False)
    shared = sorted(logic & load)
    iso_pass = len(shared) == 0

    # 綁地 mutant —— 隔離必須被抓到(shared 非空)
    m_logic, m_load, _erc_mut = _build(bond_grounds=True)
    m_shared = sorted(m_logic & m_load)
    mutant_caught = len(m_shared) > 0

    # 與 Axis-A 比對兩地 node-set(元件短名 + pin;Axis-B 已對齊 ref 命名)
    a_logic = {tuple(x) for x in axis_a["logic_gnd_pins"]}
    a_load = {tuple(x) for x in axis_a["load_gnd_pins"]}
    node_sets_equal = (a_logic == logic) and (a_load == load)

    result = {
        "demo": "auto_waterer",
        "skidl_version": skidl.__version__,
        "input_hash": axis_a.get("input_hash"),
        "axis_a": {
            "isolation_pass": axis_a["isolation_pass"],
            "logic_gnd_pins": sorted(map(tuple, a_logic)),
            "load_gnd_pins": sorted(map(tuple, a_load)),
        },
        "axis_b": {
            "isolation_pass": iso_pass,
            "erc_errors": erc_ok,
            "logic_gnd_pins": sorted(logic),
            "load_gnd_pins": sorted(load),
            "shared": shared,
        },
        "agree": bool(axis_a["isolation_pass"] == iso_pass),
        "node_sets_equal": bool(node_sets_equal),
        "mutant": {
            # Axis-A 的綁地 mutant 由 in-repo 測試另行驗(power_inject/build_netlist 層);
            # 此處證 Axis-B 對綁地 mutant 會抓到(隔離 set 非空)。
            "axis_b_caught": bool(mutant_caught),
            "axis_b_shared_example": m_shared[:3],
        },
    }
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    ok = result["agree"] and result["node_sets_equal"] and iso_pass and mutant_caught
    print(f"[AXIS-B] isolation_pass={iso_pass} agree={result['agree']} "
          f"node_sets_equal={node_sets_equal} mutant_caught={mutant_caught} erc_errors={erc_ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
