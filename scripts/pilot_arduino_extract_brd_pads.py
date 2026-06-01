"""scripts/pilot_arduino_extract_brd_pads.py — Pilot-1.1

從 Arduino UNO-TH_Rev3e.brd 抽出 JANALOG / JDIGITAL / ICSP header 的每 pad
絕對 PCB 座標（左下原點 mm）。用於 Pilot-2 audit 的 EAGLE primary source。

對每 <element>：找到對應 <package> 中所有 <pad> 的 local 座標 →
套 element 的 anchor + rotation + mirror → 得 PCB 絕對座標。

座標慣例與 lib/pcb 一致：左下原點、X 右 / Y 上、mm。
"""
from __future__ import annotations
import math
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BRD_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "data", "pcb_sources", "arduino_uno_r3", "eagle_official", "UNO-TH_Rev3e.brd"
)

# Header element names in the BRD that hold pads we care about
HEADER_ELEMENTS = ("POWER", "AD", "IOL", "IOH", "ICSP")


@dataclass(frozen=True)
class PadAbs:
    element: str       # 'POWER', 'AD', ...
    pad_name: str      # '1', '2', ... (EAGLE pad name within package)
    x_mm: float        # PCB absolute
    y_mm: float
    drill_mm: float
    eagle_ref: str     # 'POWER.1', 'AD.5', ...


def _parse_rot(rot: str | None) -> Tuple[int, bool]:
    if not rot:
        return 0, False
    mirror = rot.startswith("M")
    digits = rot.lstrip("MR")
    try:
        angle = int(round(float(digits))) % 360 if digits else 0
    except ValueError:
        angle = 0
    return angle, mirror


def _xform(px: float, py: float, angle: int, mirror: bool) -> Tuple[float, float]:
    if mirror:
        px = -px
    rad = math.radians(angle)
    c, s = math.cos(rad), math.sin(rad)
    return px * c - py * s, px * s + py * c


def extract_header_pads(brd_path: str) -> List[PadAbs]:
    tree = ET.parse(brd_path)
    root = tree.getroot()

    # Index packages: {(lib_name, pkg_name): <package>}
    packages: Dict[Tuple[str, str], ET.Element] = {}
    for lib in root.iter("library"):
        lib_name = lib.get("name", "")
        for pkg in lib.iter("package"):
            packages[(lib_name, pkg.get("name", ""))] = pkg

    out: List[PadAbs] = []
    elements_node = root.find(".//elements")
    if elements_node is None:
        return out

    for el in elements_node.findall("element"):
        ename = el.get("name", "")
        if ename not in HEADER_ELEMENTS:
            continue
        lib_name = el.get("library", "")
        pkg_name = el.get("package", "")
        _ex, _ey = el.get("x"), el.get("y")
        if _ex is None or _ey is None:
            raise ValueError(f"<element name={ename!r}> missing required x/y attribute")
        ax, ay = float(_ex), float(_ey)
        angle, mirror = _parse_rot(el.get("rot"))
        pkg = packages.get((lib_name, pkg_name))
        if pkg is None:
            continue
        for pad in pkg.findall("pad"):
            pname = pad.get("name", "")
            px, py = float(pad.get("x", "0")), float(pad.get("y", "0"))
            drill = float(pad.get("drill", "0") or 0)
            off_x, off_y = _xform(px, py, angle, mirror)
            out.append(PadAbs(
                element=ename, pad_name=pname,
                x_mm=round(ax + off_x, 4),
                y_mm=round(ay + off_y, 4),
                drill_mm=drill,
                eagle_ref=f"{ename}.{pname}",
            ))
    return out


def main():
    pads = extract_header_pads(BRD_PATH)
    print(f"# EAGLE BRD pad extraction — {BRD_PATH}")
    print(f"# total header pads: {len(pads)}\n")
    by_element: Dict[str, List[PadAbs]] = {}
    for p in pads:
        by_element.setdefault(p.element, []).append(p)
    for ename in HEADER_ELEMENTS:
        ps = by_element.get(ename, [])
        print(f"## {ename}  ({len(ps)} pads)")
        ps_sorted = sorted(ps, key=lambda p: int(p.pad_name) if p.pad_name.isdigit() else 999)
        for p in ps_sorted:
            print(f"  {p.eagle_ref:10s}  x={p.x_mm:7.3f}  y={p.y_mm:7.3f}  drill={p.drill_mm:.2f}")
        print()
    print(f"# SUMMARY: expected 38 (8+6+8+10+6), got {len(pads)}")


if __name__ == "__main__":
    main()
