"""lib/pcb/eagle_parse.py — EAGLE .brd 解析器（anchor → 元件真實中心）。

VS-PCB 根治用：lib/pcb 的 SubComponent 只存 EAGLE element 擺放原點（anchor），
不一定是元件本體中心。要把後端 SSOT 餵給前端視覺佈局（中心座標），需從 .brd 的
package 幾何（銀漆 layer 21 / 文件 layer 51）算出本體 bbox 中心相對 element 原點的
偏移，再依 element 旋轉換算回 PCB 絕對中心。

座標系：EAGLE .brd 與 lib/pcb 同為 PCB 左下角原點、X 向右、Y 向上、單位 mm。

唯一公開入口：
    parse_brd(path) -> dict[str, BrdElement]   # key = element name（ZU4 / X2 ...）

純解析、無副作用，可單測。
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 本體輪廓所在圖層（依優先序）：21 = tPlace 銀漆、51 = tDocu 文件層。
# 兩者皆描繪元件物理本體；pad/smd 會超出本體故不納入 bbox（僅在無輪廓時 fallback）。
_BODY_LAYERS = ("21", "51")


@dataclass(frozen=True)
class BrdElement:
    """單一 .brd <element> 解析結果。

    anchor_x/y = EAGLE element 擺放原點（PCB 絕對座標）。
    center_x/y = 元件本體 bbox 中心（PCB 絕對座標）= anchor + 旋轉後本體偏移。
    body_l/body_w = 旋轉後本體 bbox 尺寸（沿 X / 沿 Y），由 package 輪廓量得。
    rotation = 'R0'|'R90'|'R180'|'R270'，mirror = 是否鏡射（M 前綴）。
    body_source = 'layer21' | 'layer51' | 'pads' | 'none'（bbox 來源，供診斷）。
    """
    name: str
    package: str
    library: str
    anchor_x: float
    anchor_y: float
    rotation: str
    mirror: bool
    center_x: float
    center_y: float
    body_l: float
    body_w: float
    body_source: str


# ── 旋轉字串解析 ────────────────────────────────────────────────────────
def _parse_rot(rot: Optional[str]) -> Tuple[int, bool]:
    """'R90' -> (90, False)；'MR180' -> (180, True)；None/'' -> (0, False)。"""
    if not rot:
        return 0, False
    mirror = rot.startswith("M")
    digits = rot.lstrip("MR")
    if not digits:
        return 0, mirror
    try:
        angle = int(round(float(digits))) % 360
    except ValueError as exc:
        # 嚴格無容錯：garbled rot 不可降級成 R0（會產生看似合理卻錯誤的擺放）
        raise ValueError(f"無法解析 EAGLE rot 屬性 {rot!r}（digits={digits!r}）") from exc
    return angle, mirror


def _apply_transform(px: float, py: float, angle: int, mirror: bool) -> Tuple[float, float]:
    """把 package 局部點 (px,py) 套用 element 的 mirror + 旋轉，得相對 anchor 的偏移。

    EAGLE 慣例：先鏡射（沿 Y 軸，x→-x），再逆時針旋轉 angle 度。
    """
    if mirror:
        px = -px
    rad = math.radians(angle)
    c, s = math.cos(rad), math.sin(rad)
    return px * c - py * s, px * s + py * c


# ── package 本體 bbox ──────────────────────────────────────────────────
def _bbox_from_shapes(pkg: ET.Element, layers: Tuple[str, ...]) -> Optional[Tuple[float, float, float, float]]:
    """從指定圖層的 wire/rectangle/circle/polygon 計算 (xmin,ymin,xmax,ymax)。"""
    xs: List[float] = []
    ys: List[float] = []
    for shp in pkg:
        layer = shp.get("layer")
        if layer not in layers:
            continue
        tag = shp.tag
        if tag == "wire":
            if None in (shp.get("x1"), shp.get("x2"), shp.get("y1"), shp.get("y2")):
                continue
            xs += [float(shp.get("x1")), float(shp.get("x2"))]
            ys += [float(shp.get("y1")), float(shp.get("y2"))]
        elif tag == "rectangle":
            if None in (shp.get("x1"), shp.get("x2"), shp.get("y1"), shp.get("y2")):
                continue
            xs += [float(shp.get("x1")), float(shp.get("x2"))]
            ys += [float(shp.get("y1")), float(shp.get("y2"))]
        elif tag == "circle":
            if None in (shp.get("x"), shp.get("y"), shp.get("radius")):
                continue
            cx, cy = float(shp.get("x")), float(shp.get("y"))
            r = float(shp.get("radius"))
            xs += [cx - r, cx + r]
            ys += [cy - r, cy + r]
        elif tag == "polygon":
            for v in shp.findall("vertex"):
                if None in (v.get("x"), v.get("y")):
                    continue
                xs.append(float(v.get("x")))
                ys.append(float(v.get("y")))
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _bbox_from_pads(pkg: ET.Element) -> Optional[Tuple[float, float, float, float]]:
    """無本體輪廓時，退用 pad/smd 範圍估 bbox（會略大於本體）。"""
    xs: List[float] = []
    ys: List[float] = []
    for el in pkg:
        if el.tag == "pad":
            if None in (el.get("x"), el.get("y")):
                continue
            x, y = float(el.get("x")), float(el.get("y"))
            d = float(el.get("diameter", "0") or 0) / 2 or 0.6
            xs += [x - d, x + d]
            ys += [y - d, y + d]
        elif el.tag == "smd":
            if None in (el.get("x"), el.get("y")):
                continue
            x, y = float(el.get("x")), float(el.get("y"))
            dx = float(el.get("dx", "0")) / 2
            dy = float(el.get("dy", "0")) / 2
            xs += [x - dx, x + dx]
            ys += [y - dy, y + dy]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _package_body(pkg: ET.Element) -> Tuple[float, float, float, float, str]:
    """回 (local_cx, local_cy, local_l, local_w, source) — 未旋轉的本體 bbox。"""
    for layer in _BODY_LAYERS:
        bb = _bbox_from_shapes(pkg, (layer,))
        if bb:
            xmin, ymin, xmax, ymax = bb
            return ((xmin + xmax) / 2, (ymin + ymax) / 2,
                    xmax - xmin, ymax - ymin, f"layer{layer}")
    bb = _bbox_from_pads(pkg)
    if bb:
        xmin, ymin, xmax, ymax = bb
        return ((xmin + xmax) / 2, (ymin + ymax) / 2,
                xmax - xmin, ymax - ymin, "pads")
    return 0.0, 0.0, 0.0, 0.0, "none"


# ── 主解析 ─────────────────────────────────────────────────────────────
def _collect_packages(root: ET.Element) -> Dict[str, Dict[str, ET.Element]]:
    """{library_name: {package_name: <package>}}。涵蓋 board.libraries 下所有 library。"""
    libs: Dict[str, Dict[str, ET.Element]] = {}
    for lib in root.iter("library"):
        lib_name = lib.get("name", "")
        pkgs: Dict[str, ET.Element] = {}
        for pkg in lib.iter("package"):
            pkgs[pkg.get("name", "")] = pkg
        libs[lib_name] = pkgs
    return libs


def parse_brd(path: str) -> Dict[str, BrdElement]:
    """解析 EAGLE .brd，回 {element_name: BrdElement}。

    對每個 <element>：依 library+package 找輪廓 → 算本體 bbox 中心 →
    套 element 的 mirror+rot → 得 PCB 絕對中心。
    """
    tree = ET.parse(path)
    root = tree.getroot()
    libs = _collect_packages(root)

    out: Dict[str, BrdElement] = {}
    elements_node = root.find(".//elements")
    if elements_node is None:
        return out

    for el in elements_node.findall("element"):
        name = el.get("name", "")
        lib_name = el.get("library", "")
        pkg_name = el.get("package", "")
        ax, ay = float(el.get("x", "0")), float(el.get("y", "0"))
        angle, mirror = _parse_rot(el.get("rot"))

        pkg = libs.get(lib_name, {}).get(pkg_name)
        if pkg is None:
            # package 缺失：退化為以 anchor 為中心、尺寸 0
            out[name] = BrdElement(
                name=name, package=pkg_name, library=lib_name,
                anchor_x=ax, anchor_y=ay, rotation=f"R{angle}", mirror=mirror,
                center_x=ax, center_y=ay, body_l=0.0, body_w=0.0, body_source="none")
            continue

        lcx, lcy, l_l, l_w, source = _package_body(pkg)
        off_x, off_y = _apply_transform(lcx, lcy, angle, mirror)
        # 旋轉後本體尺寸：R90/R270 時 X/Y 軸交換
        if angle in (90, 270):
            body_l, body_w = l_w, l_l
        else:
            body_l, body_w = l_l, l_w

        out[name] = BrdElement(
            name=name, package=pkg_name, library=lib_name,
            anchor_x=ax, anchor_y=ay, rotation=f"R{angle}", mirror=mirror,
            center_x=round(ax + off_x, 4), center_y=round(ay + off_y, 4),
            body_l=round(body_l, 4), body_w=round(body_w, 4), body_source=source)

    return out


if __name__ == "__main__":
    import os
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    brd = os.path.join(os.path.dirname(__file__), "..", "..",
                       "data", "pcb_sources", "arduino_uno_r3",
                       "eagle_official", "UNO-TH_Rev3e.brd")
    elems = parse_brd(brd)
    print(f"解析 {len(elems)} 個 element\n")
    watch = ["ZU4", "U3", "U1", "Y1", "Y2", "ICSP", "X1", "X2",
             "S1", "ON", "RX", "TX", "L", "PC1", "PC2"]
    print(f"{'name':6} {'package':18} {'anchor':>18} {'center':>18} "
          f"{'body LxW':>14} {'rot':>5} src")
    for n in watch:
        e = elems.get(n)
        if not e:
            print(f"{n:6} <not found>")
            continue
        print(f"{e.name:6} {e.package:18} "
              f"({e.anchor_x:7.3f},{e.anchor_y:7.3f}) "
              f"({e.center_x:7.3f},{e.center_y:7.3f}) "
              f"{e.body_l:6.2f}x{e.body_w:5.2f} {e.rotation:>5} {e.body_source}")
