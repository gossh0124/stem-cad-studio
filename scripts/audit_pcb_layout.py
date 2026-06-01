"""scripts/audit_pcb_layout.py — VS-PCB：前端 PCB 佈局對照後端權威 SSOT 量化。

把前端 component-dimensions.js（手工硬編碼）與後端 lib/pcb（三來源交叉驗證）
的 PCB 元件佈局做量化對照，產出偏差清單。

執行：.venv/Scripts/python.exe scripts/audit_pcb_layout.py
依賴：node（dump 前端 JS）。

座標系：兩端皆 mm。後端 lib/pcb 為 PCB 左下角原點；前端 cx/cy 經 mounting-hole
校準確認與後端近似同系（偏 ~2mm）。後端 sub_component 用 EAGLE anchor（非元件
中心），故 IC/連接器位置偏差含 anchor 語義成分——mounting holes 為最精確對照。
"""
import os
import sys
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from lib.pcb import ARDUINO_UNO_R3
from lib.pcb.layout_export import arduino_brd_centers
from lib.verification.pcb_layout import audit_pcb_layout
from lib.verification import Verdict

# 前端 label → 後端 sub_component name（人工映射，Arduino-Uno）
ARDUINO_MAP = {
    "ATmega328P": "ATmega328P",
    "ATmega16U2": "ATmega16U2",
    "NCP1117-5V": "V-Reg-5V",
    "LP2985-3V3": "LP2985-3V3",
    "USB-B": "USB-B",
    "DC-Barrel": "DC-Jack",
    "ICSP-16U2": "ICSP-16U2",
    "ICSP": "ICSP-Main",
    "Crystal-16MH": "Crystal-16MHz",
    "Resonator": "Resonator-ATmega",
    "Cap-PC1": "Cap-PC1",
    "Cap-PC2": "Cap-PC2",
    "Reset-Button": "Reset-Switch",
    "LED-PWR": "LED-ON",
    "LED-TX": "LED-TX",
    "LED-RX": "LED-RX",
    "LED-L": "LED-L",
}
# 前端 mounting-hole label 依 cx/cy 與後端 MOUNTING_HOLES 最近鄰配對


def dump_frontend_ports(board_key: str) -> list:
    js = (
        "global.window={};"
        "eval(require('fs').readFileSync('v6/data/component-dimensions.js','utf8'));"
        f"const d=window.COMPONENT_DIMENSIONS['{board_key}'];"
        "process.stdout.write(JSON.stringify(d.ports));"
    )
    out = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise RuntimeError(f"node dump 失敗: {out.stderr}")
    return json.loads(out.stdout)


def fe_footprint(shape: str, params: dict):
    p = params or {}
    if shape == 'ic-dip':
        pins = p.get('pins', 0); rows = p.get('rows', 2) or 2; pitch = p.get('pitch', 2.54)
        length = (pins / rows) * pitch
        width = p.get('rowSpacing') or p.get('bodyW')
        return (length, width) if width else None
    if shape in ('conn-header-male', 'conn-header-female'):
        pins = p.get('pins', 0); rows = p.get('rows', 1) or 1; pitch = p.get('pitch', 2.54)
        return ((pins / rows) * pitch, 2.54 * rows)
    if shape == 'mounting-hole':
        d = p.get('padDia') or p.get('diameter')
        return (d, d) if d else None
    w = p.get('bodyW') or p.get('diameter')
    d = p.get('bodyD') or w
    return (w, d) if w else None


def be_footprint(sc) -> tuple:
    if sc.rotation in ('R90', 'R270'):
        return (sc.body_w, sc.body_l)
    return (sc.body_l, sc.body_w)


def main() -> int:
    print("=" * 64)
    print("VS-PCB：Arduino-Uno 前端佈局 vs 後端權威 SSOT 量化對照")
    print("=" * 64)

    fe_ports = dump_frontend_ports("Arduino-Uno-class")
    sub_by_name = {sc.name: sc for sc in ARDUINO_UNO_R3.sub_components}
    # 後端對照基準改用 EAGLE .brd 真實本體中心（anchor→中心換算），與 exporter 同源。
    # 消除舊版「以 anchor 比對」的語義雜訊，讓偏差下降為真實對齊（見 problem.md VS-PCB）。
    be_centers = arduino_brd_centers()

    matched, frontend_only, ssot_only = [], [], []
    matched_be_names = set()

    for fp in fe_ports:
        if "label" not in fp:
            raise ValueError(f"frontend port missing required 'label' field: {fp!r}")
        label = fp["label"]
        shape = fp.get("shape", "")
        if shape == 'mounting-hole':
            continue  # mounting holes 另以最近鄰配對
        be_name = ARDUINO_MAP.get(label)
        if not be_name or be_name not in sub_by_name:
            frontend_only.append(label)
            continue
        sc = sub_by_name[be_name]
        matched_be_names.add(be_name)
        be = be_centers.get(be_name)
        if be is None:  # 嚴格無容錯：映射到的後端元件缺 .brd 中心 = 設定錯誤，直接拋
            raise RuntimeError(
                f"audit：{label!r}→{be_name!r} 無 .brd 真實中心（element 映射缺失）。"
                f"修 lib/pcb/layout_export.ARDUINO_ELEMENT_MAP，勿靜默退 anchor。")
        sx, sy = be.center_x, be.center_y
        fw, fh = (fe_footprint(shape, fp.get("params")) or (None, None))
        sw, sh = be_footprint(sc)
        matched.append({
            "label": label,
            "fx": fp.get("cx"), "fy": fp.get("cy"),
            "sx": sx, "sy": sy,
            "fw": fw, "fh": fh, "sw": sw, "sh": sh,
        })

    # mounting holes 最近鄰配對
    fe_mh = [fp for fp in fe_ports if fp.get("shape") == 'mounting-hole']
    be_mh = list(ARDUINO_UNO_R3.mounting_holes)
    used_be = set()
    for fp in fe_mh:
        best, best_d = None, 1e9
        for i, mh in enumerate(be_mh):
            if i in used_be:
                continue
            d = abs(fp["cx"] - mh.x) + abs(fp["cy"] - mh.y)
            if d < best_d:
                best, best_d = i, d
        if best is not None:
            used_be.add(best)
            mh = be_mh[best]
            matched.append({
                "label": fp.get("label", "MH"),
                "fx": fp["cx"], "fy": fp["cy"], "sx": mh.x, "sy": mh.y,
                "fw": None, "fh": None, "sw": None, "sh": None,
            })

    # 後端有但前端未配對到的 sub_components = 漏畫
    for name in sub_by_name:
        if name not in matched_be_names:
            ssot_only.append(name)

    # 容差收緊：exporter 與 audit 同源（.brd 真實中心），實際偏差僅 rounding(~0.005mm)。
    # 0.5mm gate 仍能抓出任何真實回歸（手改 SSOT 段未重跑 exporter 等）。
    rpt = audit_pcb_layout(matched, frontend_only, ssot_only,
                           name="Arduino-Uno", pos_tol_mm=0.5, size_tol_mm=0.5)
    print(rpt.render_text())
    print(f"\n對照基準：後端 lib/pcb/arduino_uno_r3.py + UNO-TH_Rev3e.brd（EAGLE+KiCad+PDF 三來源驗證）")
    print(f"配對 {len(matched)}、前端多出 {len(frontend_only)}、後端漏畫 {len(ssot_only)}")
    print("註：sub_component 位置已用 EAGLE .brd 真實本體中心（anchor→中心換算）對照，與 exporter 同源；")
    print("    前端 SSOT 段由 lib/pcb/layout_export.py 自動生成。前端多出 4 者為邊緣 header")
    print("    方向慣例(POWER/ANALOG/DIGITAL，屬 VS-AXIS)，非 VS-PCB 範圍。")
    return 0 if rpt.verdict == Verdict.PASS else 1


if __name__ == "__main__":
    sys.exit(main())
