#!/usr/bin/env python
"""derive_schematic_tables.py — 從 verified.json physical 衍生 schematic REGISTRY_MM。

SCHEM-DEMO-1 Wave A：取代 v6/data/component-dimensions.js 手填 window.REGISTRY_MM
（schematic 節點 mm 尺寸）為 SSOT-AUTO 衍生。

compKey→class 對應為 schematic 專用（含 user 決策特例）：
  - DCMotor → Motor-DC-class（裸馬達 70x22，非 wiring 層的 L298N-Driver-class）
  - Buzzer  → Buzzer-Active-class（Active/Passive 同尺寸 12x12）
  - Stepper → Motor-Stepper-class（用 combined_length/width_mm）

用法：
  --check  drift gate：derived vs 前端 REGISTRY_MM，漂移則 exit 1
  --write  將衍生表寫回 component-dimensions.js（marker，勿手改）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
JS = ROOT / "v6" / "data" / "component-dimensions.js"

# schematic compKey → verified.json class（schematic 專用；見 module docstring 特例）
SCHEM_MAP: dict[str, str] = {
    "SoilMoisture": "Sensor-SoilMoisture-class", "Relay": "Relay-Module-class",
    "Pump": "Pump-Water-class", "Ultrasonic": "Sensor-Ultrasonic-class",
    "PIR": "Sensor-PIR-class", "Servo": "Motor-Servo-class",
    "OLED": "Display-OLED-class", "LCD": "Display-LCD-class",
    "NeoPixel": "Lighting-NeoPixel-class", "Buzzer": "Buzzer-Active-class",
    "LED_Single": "Lighting-LED-PWM-class", "LED_RGB": "Lighting-LED-RGB-class",
    "DCMotor": "Motor-DC-class", "TempHumid": "Sensor-TempHumid-class",
    "Speaker": "MP3-Module-class", "Light": "Sensor-Light-class",
    "MSGEQ7": "Sensor-MSGEQ7-class", "Button": "Button-class",
    "Switch": "Switch-class", "BatteryAA": "Battery-AA-class",
    "BatteryLiPo": "Battery-LiPo-class", "USB5V": "USB-5V-class",
    "Stepper": "Motor-Stepper-class",
}

VERIFIED_PATH = ROOT / "data" / "component_datasheet_verified.json"


def _phys_lw(spec: dict) -> tuple[float | None, float | None]:
    p = spec.get("physical", {}) or {}
    length = p.get("length_mm", p.get("combined_length_mm"))
    width = p.get("width_mm", p.get("combined_width_mm"))
    return length, width


def derive() -> dict[str, list[float]]:
    """從 verified.json 衍生 {compKey: [L_mm, W_mm]}；缺值即 raise（禁臆造）。"""
    import json
    vj = json.loads(VERIFIED_PATH.read_text("utf-8"))
    out: dict[str, list[float]] = {}
    for key, cls in SCHEM_MAP.items():
        spec = vj.get(cls)
        if not spec:
            raise SystemExit(f"[FAIL] {key}: verified.json 無 class {cls}")
        length, width = _phys_lw(spec)
        if length is None or width is None:
            raise SystemExit(f"[FAIL] {key}({cls}): physical 缺 length/width_mm")
        out[key] = [float(length), float(width)]
    return out


def parse_current() -> dict[str, list[float]]:
    txt = JS.read_text(encoding="utf-8")
    m = re.search(r"window\.REGISTRY_MM\s*=\s*\{([\s\S]*?)\};", txt)
    if not m:
        raise SystemExit("[FAIL] component-dimensions.js 找不到 window.REGISTRY_MM")
    cur: dict[str, list[float]] = {}
    for key, length, width in re.findall(r"(\w+):\s*\[([\d.]+),\s*([\d.]+)\]", m.group(1)):
        cur[key] = [float(length), float(width)]
    return cur


def _fmt(v: float) -> str:
    return f"{int(v)}.0" if float(v).is_integer() else f"{v:g}"


def render(table: dict[str, list[float]]) -> str:
    keys, lines, row = list(SCHEM_MAP.keys()), [], []
    for i, key in enumerate(keys):
        length, width = table[key]
        row.append(f"{key}: [{_fmt(length)}, {_fmt(width)}]")
        if len(row) == 3 or i == len(keys) - 1:
            lines.append("  " + ",  ".join(row) + ",")
            row = []
    return ("// -- Schematic dimension table — SSOT-AUTO from verified.json physical --\n"
            "// 勿手改；重跑：.venv/Scripts/python.exe scripts/derive_schematic_tables.py --write\n"
            "window.REGISTRY_MM = {\n" + "\n".join(lines) + "\n};")


def derive_role_palette() -> dict[str, str]:
    """role → hex 色，取自 lib/config.py ROLE_PALETTE（11 role 單一 SSOT）。"""
    from lib.config import ROLE_PALETTE
    return dict(ROLE_PALETTE)


def parse_current_role() -> dict[str, str]:
    txt = JS.read_text(encoding="utf-8")
    m = re.search(r"window\.ROLE_PALETTE\s*=\s*\{([\s\S]*?)\};", txt)
    if not m:
        return {}
    return dict(re.findall(r"(\w+):\s*'(#[0-9a-fA-F]{3,6})'", m.group(1)))


def render_role(table: dict[str, str]) -> str:
    body = ", ".join(f"{k}: '{v}'" for k, v in table.items())
    return ("// -- Role → UI 顏色 — SSOT-AUTO from lib/config.py ROLE_PALETTE --\n"
            "// 勿手改；重跑：.venv/Scripts/python.exe scripts/derive_schematic_tables.py --write\n"
            "window.ROLE_PALETTE = {" + body + "};")


def cmd_check() -> int:
    derived, current = derive(), parse_current()
    drift = []
    for key in SCHEM_MAP:
        if key not in current:
            drift.append(f"REGISTRY_MM.{key}: 前端缺")
        elif (abs(derived[key][0] - current[key][0]) > 1e-6
              or abs(derived[key][1] - current[key][1]) > 1e-6):
            drift.append(f"REGISTRY_MM.{key}: derived={derived[key]} vs js={current[key]}")
    role_d, role_c = derive_role_palette(), parse_current_role()
    for role, color in role_d.items():
        if role_c.get(role) != color:
            drift.append(f"ROLE_PALETTE.{role}: config={color} vs js={role_c.get(role)}")
    if drift:
        print("[DRIFT] schematic 衍生表與 SSOT 漂移:")
        for d in drift:
            print("  -", d)
        return 1
    print(f"[OK] REGISTRY_MM {len(derived)} + ROLE_PALETTE {len(role_d)} 與 SSOT 零漂移")
    return 0


def cmd_write() -> int:
    derived = derive()
    txt = JS.read_text(encoding="utf-8")
    # marker 允許任意 dash 樣式(ASCII `--` 或 box-drawing `──`/U+2500),避免
    # 因 marker 編碼不符而替換 0 處(2026-06-12 修:檔案用 `──`、舊 regex 只認 `--`)。
    reg_pat = (r"//[^\n]*Schematic dimension table[^\n]*\n(?://[^\n]*\n)?"
               r"window\.REGISTRY_MM\s*=\s*\{[\s\S]*?\};")
    reg_block = render(derived)
    txt, n = re.subn(reg_pat, lambda _m: reg_block, txt)
    if n != 1:
        raise SystemExit(f"[FAIL] REGISTRY_MM 區塊替換 {n} 處（預期 1）")
    # ROLE_PALETTE：首次插在 REGISTRY_MM 區塊後;之後 idempotent 替換
    role_block = render_role(derive_role_palette())
    role_pat = (r"//[^\n]*Role[^\n]*\n(?://[^\n]*\n)?"
                r"window\.ROLE_PALETTE\s*=\s*\{[\s\S]*?\};")
    if re.search(role_pat, txt):
        txt = re.sub(role_pat, lambda _m: role_block, txt)
    else:
        txt = re.sub(r"(window\.REGISTRY_MM\s*=\s*\{[\s\S]*?\};)",
                     lambda m: m.group(1) + "\n\n" + role_block, txt, count=1)
    JS.write_text(txt, encoding="utf-8")
    print(f"[WRITE] REGISTRY_MM {len(derived)} + ROLE_PALETTE 已 SSOT-AUTO 寫回 {JS.name}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="寫回 component-dimensions.js")
    ap.add_argument("--check", action="store_true", help="drift gate（預設）")
    args = ap.parse_args()
    sys.exit(cmd_write() if args.write else cmd_check())
