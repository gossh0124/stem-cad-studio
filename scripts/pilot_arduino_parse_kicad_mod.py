"""scripts/pilot_arduino_parse_kicad_mod.py — Pilot-1.2

從 Arduino_UNO_R3.kicad_mod 抽出每 pad 的本地座標（footprint 內），
並以「對齊 EAGLE BRD 同方向 / 同原點」的方式輸出，供 Pilot-2 cross-verify。

注意：KiCad footprint 內座標是「相對 footprint 原點」，需要在 audit 時
與 EAGLE BRD 對齊（兩者本來就應使用相同 PCB 左下原點，若 KiCad mod 採
footprint-local origin，需 audit script 補 offset 才能比較）。

本腳本先輸出 raw KiCad 座標，audit step (Pilot-2.1) 再做對齊。
"""
from __future__ import annotations
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KICAD_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "data", "pcb_sources", "arduino_uno_r3", "Arduino_UNO_R3.kicad_mod"
)


@dataclass(frozen=True)
class KicadPad:
    number: str           # pad number / name as written
    pad_type: str         # 'thru_hole', 'smd', etc.
    shape: str            # 'circle', 'oval', 'rect', ...
    x_mm: float           # local coords within footprint (KiCad: footprint-local)
    y_mm: float
    drill_mm: float       # 0 if SMD


# KiCad mod uses S-expression; we do a lightweight regex-based parse adequate for pad blocks
_PAD_PATTERN = re.compile(
    r'\(pad\s+"?([^"\s)]+)"?\s+(\w+)\s+(\w+)\s+\(at\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)(?:\s+(-?\d+\.?\d*))?\)',
    re.DOTALL,
)
_DRILL_RE = re.compile(r'\(drill\s+(-?\d+\.?\d*)')


def parse_pads(path: str) -> List[KicadPad]:
    text = open(path, "r", encoding="utf-8").read()
    out: List[KicadPad] = []
    # iterate by pad block to also capture drill within same block
    # find pad blocks manually (parens balanced) for drill association
    pos = 0
    while True:
        idx = text.find("(pad ", pos)
        if idx < 0:
            break
        # find matching closing paren
        depth = 0
        end = idx
        for i, ch in enumerate(text[idx:], start=idx):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        block = text[idx:end]
        m = _PAD_PATTERN.search(block)
        if m:
            number, pad_type, shape, x, y = m.group(1), m.group(2), m.group(3), float(m.group(4)), float(m.group(5))
            dm = _DRILL_RE.search(block)
            drill = float(dm.group(1)) if dm else 0.0
            out.append(KicadPad(
                number=number, pad_type=pad_type, shape=shape,
                x_mm=round(x, 4), y_mm=round(y, 4), drill_mm=drill,
            ))
        pos = end
    return out


def detect_footprint_origin_hint(path: str) -> Optional[str]:
    """KiCad footprint 沒有 PCB-absolute 原點；若有 (at ...) 在 footprint 根層級，
    那是「footprint 在 PCB 上放置時的預設位置」，不適用單檔。

    回傳簡短說明字串，audit step 用來判斷對齊策略。
    """
    text = open(path, "r", encoding="utf-8").read()[:500]
    has_at = "(at " in text.split("\n", 5)[1] if len(text.split("\n")) > 1 else False
    return f"footprint-root has_at={has_at}; KiCad mod 座標 = footprint local，需 Pilot-2.1 audit script 對齊 EAGLE BRD 原點"


def main():
    pads = parse_pads(KICAD_PATH)
    print(f"# KiCad footprint pad extraction — {KICAD_PATH}")
    print(f"# total pads parsed: {len(pads)}")
    print(f"# {detect_footprint_origin_hint(KICAD_PATH)}\n")
    # sort by pad number (numeric where possible)
    def sortkey(p: KicadPad):
        try:
            return (0, int(p.number))
        except ValueError:
            return (1, p.number)
    for p in sorted(pads, key=sortkey):
        print(f"  pad {p.number:>6s}  {p.pad_type:10s} {p.shape:8s}  "
              f"x={p.x_mm:8.3f}  y={p.y_mm:8.3f}  drill={p.drill_mm:.2f}")
    print(f"\n# SUMMARY: expected ≥32 header pads, got {len(pads)} total (含 mounting holes / SMD)")


if __name__ == "__main__":
    main()
