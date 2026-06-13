"""lib/pcb/layout_export.py — 後端 PCB SSOT → 前端 component-dimensions 視覺佈局 exporter。

VS-PCB 根治：前端 `v6/data/component-dimensions.js` 的 PCB 元件佈局過去手填，與後端
三來源交叉驗證的 `lib/pcb` 大幅不符。本模組把後端權威 SSOT 自動轉成前端格式：

  位置（cx/cy）= EAGLE .brd 解析出的元件**真實本體中心**（anchor→中心，見 eagle_parse）。
                 PCB 左下角原點、不翻轉、不加偏移（與後端同座標系）。
  尺寸（params）= 後端 datasheet 本體尺寸（三來源驗證，非 .brd 銀漆）。
  shape/color  = 沿用前端既有慣例（per-component 映射表）。

座標系：cx/cy 為元件中心 mm，PCB 左下角原點。前端 renderer（scene-3d.js）對所有 port
套同一公式 cz3 = -(cy - W/2)，故與後端同源即視覺一致。

目前涵蓋 Arduino-Uno-class（唯一有 EAGLE board placement 的板）。其他板無 .brd
placement，待後續以 datasheet anchor 近似擴充（見 problem.md VS-PCB）。
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from .eagle_parse import parse_brd, BrdElement
from .arduino_uno_r3 import ARDUINO_UNO_R3

_ARDUINO_BRD = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "data", "pcb_sources", "arduino_uno_r3", "eagle_official", "UNO-TH_Rev3e.brd")


# ── 本體中心來源策略（SSOT19 仲裁）──────────────────────────────────────
# 多數 package 取 eagle_parse 的「絲印/文件層 bbox 中心」即為本體中心；但少數
# package 的 layer-21 絲印只是不對稱極性標記（非本體輪廓），其 bbox 中心會偏離
# 真實質心，改用 EAGLE element anchor（= package 原點 = pad 質心）。
#   CHIP-LED0805：.brd 內 pad A=(0,-1.05)/C=(0,+1.05) 對稱於原點 → 原點即質心；
#     layer-21 三個小標記 bbox 中心在 local(0,+0.15)，經 R90/R270 旋轉後造成
#     ±0.15mm 假性 X 偏移（RX/TX→27.79、L→28.09，本應同為一列 27.94）。
#     改用 anchor → 收斂至真值 27.94，與 verified.json on_board 同值（解 SSOT19 gate 互斥）。
_ANCHOR_AS_CENTER_PACKAGES = {"CHIP-LED0805"}


def _body_center(be: BrdElement) -> Tuple[float, float]:
    """元件本體中心：CHIP-LED0805 等用 anchor（pad 質心），其餘用絲印 bbox 中心。"""
    if be.package in _ANCHOR_AS_CENTER_PACKAGES:
        return be.anchor_x, be.anchor_y
    return be.center_x, be.center_y


# ── 後端 SubComponent.name → .brd <element> name ────────────────────────
ARDUINO_ELEMENT_MAP: Dict[str, str] = {
    "USB-B": "X2",
    "DC-Jack": "X1",
    "ATmega328P": "ZU4",
    "ATmega16U2": "U3",
    "V-Reg-5V": "U1",
    "LP2985-3V3": "U2",
    "Crystal-16MHz": "Y1",
    "Resonator-ATmega": "Y2",
    "ICSP-16U2": "ICSP1",
    "ICSP-Main": "ICSP",
    "Reset-Switch": "RESET",
    "LED-ON": "ON",
    "LED-RX": "RX",
    "LED-TX": "TX",
    "LED-L": "L",
    "Cap-PC1": "PC1",
    "Cap-PC2": "PC2",
}


# ── 前端視覺映射：後端 name → (label, shape, color, params) ───────────────
# label/shape/color/params 沿用 component-dimensions.js 既有慣例；
# params 採後端 datasheet 本體尺寸（三來源驗證）。位置 cx/cy 由 .brd 中心填入。
ARDUINO_RENDER: Dict[str, dict] = {
    "ATmega328P":       dict(label="ATmega328P",   shape="ic-dip",          color="#222222",
                             params=dict(pins=28, pitch=2.54, rows=2, bodyW=7.62, rowSpacing=7.62)),
    "ATmega16U2":       dict(label="ATmega16U2",   shape="ic-qfp",          color="#333333",
                             params=dict(pins=32, bodyW=5.0, bodyD=5.0)),
    "V-Reg-5V":         dict(label="NCP1117-5V",   shape="ic-soic",         color="#444444",
                             params=dict(pins=4, bodyW=6.5, bodyD=3.5)),
    "LP2985-3V3":       dict(label="LP2985-3V3",   shape="ic-soic",         color="#3a3a3a",
                             params=dict(pins=5, bodyW=2.9, bodyD=1.6)),
    "Crystal-16MHz":    dict(label="Crystal-16MH", shape="crystal-hc49",    color="#d4d4d4",
                             params=dict(bodyW=11.4, bodyD=4.7)),
    "Resonator-ATmega": dict(label="Resonator",    shape="res-smd",         color="#a16207",
                             params=dict(bodyW=8.0, bodyD=2.5)),
    "ICSP-16U2":        dict(label="ICSP-16U2",    shape="conn-header-male", color="#fbbf24",
                             params=dict(pins=6, pitch=2.54, rows=2)),
    "ICSP-Main":        dict(label="ICSP",         shape="conn-header-male", color="#fbbf24",
                             params=dict(pins=6, pitch=2.54, rows=2)),
    "Reset-Switch":     dict(label="Reset-Button", shape="button-tactile",  color="#ef4444",
                             params=dict(bodyW=6.0, bodyD=6.0)),
    "LED-ON":           dict(label="LED-PWR",      shape="led-smd",         color="#22c55e",
                             params=dict(bodyW=2.0, bodyD=1.25)),
    "LED-RX":           dict(label="LED-RX",       shape="led-smd",         color="#eab308",
                             params=dict(bodyW=2.0, bodyD=1.25)),
    "LED-TX":           dict(label="LED-TX",       shape="led-smd",         color="#eab308",
                             params=dict(bodyW=2.0, bodyD=1.25)),
    "LED-L":            dict(label="LED-L",        shape="led-smd",         color="#eab308",
                             params=dict(bodyW=2.0, bodyD=1.25)),
    "Cap-PC1":          dict(label="Cap-PC1",      shape="cap-electrolytic", color="#1f2937",
                             params=dict(diameter=6.3, bodyH=5.4)),
    "Cap-PC2":          dict(label="Cap-PC2",      shape="cap-electrolytic", color="#1f2937",
                             params=dict(diameter=6.3, bodyH=5.4)),
    "USB-B":            dict(label="USB-B",        shape="conn-usb-b",      color="#c0c0c0",
                             params=dict(bodyW=12.0, bodyD=16.0, bodyH=11.0)),
    "DC-Jack":          dict(label="DC-Barrel",    shape="conn-barrel-jack", color="#1a1a1a",
                             params=dict(bodyW=9.0, bodyD=14.0, bodyH=11.0)),
}

# 重生順序（與既有 JS 一致，利於 diff 比對）
ARDUINO_ORDER: List[str] = [
    "ATmega328P", "ATmega16U2", "V-Reg-5V", "LP2985-3V3",
    "USB-B", "DC-Jack", "ICSP-16U2", "ICSP-Main",
    "Crystal-16MHz", "Resonator-ATmega", "Cap-PC1", "Cap-PC2",
    "Reset-Switch", "LED-ON", "LED-TX", "LED-RX", "LED-L",
]

# mounting hole 視覺參數（pad 直徑沿用既有）
_MH_COLOR = "#c9b037"
_MH_PARAMS = dict(diameter=3.2, padDia=6.4)


def arduino_brd_centers(brd_path: Optional[str] = None) -> Dict[str, BrdElement]:
    """回 {後端 SubComponent.name: BrdElement}（已對映 .brd element）。"""
    path = brd_path or _ARDUINO_BRD
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "EAGLE .brd SSOT 來源缺失，layout_export 無法衍生佈局。\n"
            f"  預期路徑：{os.path.abspath(path)}\n"
            "  此資料檔（data/pcb_sources/arduino_uno_r3/eagle_official/UNO-TH_Rev3e.brd）"
            "未隨 repo 提供，請還原後再執行（V2 archive 內存有此檔）。")
    elems = parse_brd(path)
    out: Dict[str, BrdElement] = {}
    for be_name, el_name in ARDUINO_ELEMENT_MAP.items():
        if el_name in elems:
            out[be_name] = elems[el_name]
    return out


def export_arduino_ports(pcb_spec, brd_path: Optional[str] = None) -> List[dict]:
    """後端 ARDUINO_UNO_R3 → 前端 component-dimensions ports（SSOT 衍生段）。

    回傳 21 個條目：17 個 sub_component 本體（中心由 .brd 衍生）+ 4 個 mounting holes。
    不含前端自有方向慣例的邊緣 header（POWER/ANALOG/DIGITAL），那些屬 VS-AXIS。

    嚴格無容錯：任何 ARDUINO_RENDER 元件若缺後端 sub_component、缺 .brd 中心、或
    本體幾何來源為 'none'（package 找不到），一律 raise ValueError——不靜默退用 anchor，
    避免「降級資料當成功」掩蓋映射/解析錯誤（見 problem.md / false-success-gating 經驗）。
    """
    centers = arduino_brd_centers(brd_path)
    sub_by_name = {sc.name: sc for sc in pcb_spec.sub_components}

    problems: List[str] = []
    for be_name in ARDUINO_RENDER:
        if be_name not in sub_by_name:
            problems.append(f"{be_name}: 後端無此 sub_component")
            continue
        be = centers.get(be_name)
        if be is None:
            problems.append(f"{be_name}: 無 .brd 中心（element 映射 {ARDUINO_ELEMENT_MAP.get(be_name)!r} 缺失）")
        elif be.body_source == "none":
            problems.append(f"{be_name}: package {be.package!r} 幾何缺失（body_source=none）")
    if problems:
        raise ValueError("export_arduino_ports 無法衍生（嚴格模式，禁容錯）:\n  - "
                         + "\n  - ".join(problems))

    ports: List[dict] = []
    for be_name in ARDUINO_ORDER:
        render = ARDUINO_RENDER[be_name]
        be = centers[be_name]
        cx, cy = _body_center(be)
        ports.append(dict(
            side="face", cx=round(cx, 2), cy=round(cy, 2),
            shape=render["shape"], label=render["label"], color=render["color"],
            params=dict(render["params"]),
        ))

    # mounting holes（後端權威座標，精確）
    for i, mh in enumerate(pcb_spec.mounting_holes, start=1):
        ports.append(dict(
            side="face", cx=round(mh.x, 2), cy=round(mh.y, 2),
            shape="mounting-hole", label=f"MH{i}", color=_MH_COLOR,
            params=dict(_MH_PARAMS),
        ))

    return ports


# ── JS 文字輸出（重生 component-dimensions.js 段落用）────────────────────
def _fmt_num(v) -> str:
    """1.0 -> '1'，2.54 -> '2.54'（去尾零，與既有 JS 風格一致）。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(v)


def _fmt_params(params: dict) -> str:
    items = ", ".join(f"{k}: {_fmt_num(v)}" for k, v in params.items())
    return "{ " + items + " }"


def port_to_js(p: dict) -> str:
    """單一 port dict → 一行 JS object literal（無尾逗號）。"""
    parts = [f"side: '{p['side']}'", f"cx: {_fmt_num(p['cx'])}", f"cy: {_fmt_num(p['cy'])}"]
    if p.get("rot"):
        parts.append(f"rot: {_fmt_num(p['rot'])}")
    parts.append(f"shape: '{p['shape']}'")
    parts.append(f"label: '{p['label']}'")
    parts.append(f"color: '{p['color']}'")
    parts.append(f"params: {_fmt_params(p['params'])}")
    return "{ " + ", ".join(parts) + " }"


def render_ports_js(ports: List[dict], indent: str = "    ") -> str:
    """ports → 多行 JS（每行一個 port，逗號分隔，無結尾逗號）。"""
    return ",\n".join(indent + port_to_js(p) for p in ports)


# ── 自動寫入 component-dimensions.js（取代人工搬運）────────────────────
# SSOT 段以 sentinel marker 框出，writer 只替換兩 marker 之間，legacy 段不受影響。
SECTION_BEGIN = "// >>> SSOT-AUTO-GENERATED by lib/pcb/layout_export.py"
SECTION_END = "// <<< SSOT-AUTO-GENERATED"

_DIMS_JS = os.path.join(
    os.path.dirname(__file__), "..", "..", "v6", "data", "component-dimensions.js")


def render_arduino_section(indent: str = "    ") -> str:
    """回 SSOT marker 之間應有的精確內容：19 行，每行結尾逗號（legacy 段緊接其後）。"""
    ports = export_arduino_ports(ARDUINO_UNO_R3)
    return "\n".join(indent + port_to_js(p) + "," for p in ports)


def extract_arduino_section(js_text: str) -> str:
    """從 JS 文字抓出兩 marker 之間的內容（不含 marker 行），未找到則 raise。"""
    if SECTION_BEGIN not in js_text or SECTION_END not in js_text:
        raise ValueError("component-dimensions.js 缺 SSOT-AUTO-GENERATED marker")
    pre, rest = js_text.split(SECTION_BEGIN, 1)
    begin_line_end = rest.index("\n") + 1          # 跳過 begin marker 那行
    body_and_after = rest[begin_line_end:]
    body, _after = body_and_after.split(SECTION_END, 1)
    return body.rstrip("\n").rstrip()


_BEGIN_MARKER_LINE = (
    "    " + SECTION_BEGIN
    + " — 勿手改，重跑：.venv/Scripts/python.exe -m lib.pcb.layout_export --write")
_END_MARKER_LINE = "    " + SECTION_END
_LEGACY_COMMENT_LINE = (
    "    // ── Legacy（前端邊緣 header 方向慣例屬 VS-AXIS，暫保留手填）見 problem.md VS-PCB ──")


def _bootstrap_markers(text: str) -> str:
    """marker 不存在時，自動框出 Arduino-Uno-class 的 SSOT 段。

    EAGLE-derived 段（exporter 只輸出 side='face' port）一律進 marker；前端邊緣
    header（side 'left'/'right'）非 .brd placement 衍生，保留為 marker 後的 legacy。
    這不是手改 SSOT 內容，而是把 exporter 寫入點（marker）以程式還原。
    """
    import re

    m = re.search(r'("Arduino-Uno-class"\s*:\s*\{[^\[]*ports:\s*\[\n)(.*?)(\n\s*\]\s*\},)',
                  text, re.DOTALL)
    if not m:
        raise ValueError("找不到 Arduino-Uno-class ports 陣列，無法 bootstrap marker")
    head, body, tail = m.group(1), m.group(2), m.group(3)
    legacy_lines = [ln.rstrip().rstrip(",") for ln in body.split("\n")
                    if "side: 'left'" in ln or "side: 'right'" in ln]
    # legacy 之間以逗號分隔，最後一行不帶尾逗號（其前的 SSOT 段末行已帶逗號）。
    legacy_block = "\n".join(
        ln + ("," if i < len(legacy_lines) - 1 else "")
        for i, ln in enumerate(legacy_lines))
    new_array = (head
                 + _BEGIN_MARKER_LINE + "\n"
                 + _END_MARKER_LINE + "\n"
                 + _LEGACY_COMMENT_LINE + "\n"
                 + legacy_block
                 + tail)
    return text[:m.start()] + new_array + text[m.end():]


def write_arduino_section(js_path: Optional[str] = None) -> bool:
    """把 SSOT 段重寫進 component-dimensions.js（marker 之間）。回 True 若有變更。"""
    path = js_path or _DIMS_JS
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if SECTION_BEGIN not in text or SECTION_END not in text:
        text = _bootstrap_markers(text)

    pre, rest = text.split(SECTION_BEGIN, 1)
    begin_line = SECTION_BEGIN + rest[:rest.index("\n")]   # begin marker 整行（含尾註）
    after_begin = rest[rest.index("\n") + 1:]
    _body, after_end = after_begin.split(SECTION_END, 1)

    new_text = (pre + begin_line + "\n"
                + render_arduino_section() + "\n"
                + "    " + SECTION_END + after_end)
    if new_text == text:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return True


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--write" in sys.argv:
        changed = write_arduino_section()
        print("[OK] component-dimensions.js Arduino SSOT section rewritten"
              if changed else "[OK] component-dimensions.js already up-to-date")
    else:
        _ports = export_arduino_ports(ARDUINO_UNO_R3)
        print(f"=== Arduino-Uno-class SSOT 衍生 ports（{len(_ports)} 條）===")
        print("（加 --write 直接寫入 v6/data/component-dimensions.js）\n")
        print(render_arduino_section())
