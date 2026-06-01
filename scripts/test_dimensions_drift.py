"""test_dimensions_drift.py — 鎖定前端 component-dimensions.js 與 verified.json SSOT 對齊

資料來源（SOURCE: official）：
  - data/component_datasheet_verified.json（_meta.methodology = "官方 datasheet + 官方 EDA 封裝圖 + 實測/社群驗證"）
  - on_board_components[].x_mm/y_mm 是子件 bounding box 左下角（PCB 原點在左下）
  - 前端 cx/cy 是子件中心 → 換算 cx = x_mm + w_mm/2, cy = y_mm + h_mm/2

tolerance = 0.1mm（零誤差語意；測量噪訊容忍範圍）

用法：
  # CI 紅線（核心 3 元件，必須綠）
  .venv/Scripts/python.exe scripts/test_dimensions_drift.py

  # 完整稽核（全 32 個含 on_board_components 的 class）
  .venv/Scripts/python.exe scripts/test_dimensions_drift.py --all

  # 指定元件
  .venv/Scripts/python.exe scripts/test_dimensions_drift.py --class ESP32-class

退出碼：0 = 對齊；1 = 漂移；2 = 元件清單缺失（SSOT 違反）。
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIMS_JS = ROOT / "v6" / "data" / "component-dimensions.js"
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"
TOL_MM = 0.1

# CI 紅線元件（歷史核心 3 元件，必須維持綠燈）
# SOURCE: official — 從 data/component_datasheet_verified.json on_board_components 衍生
CORE_COMPONENTS = ["Battery-AA-class", "Pump-Water-class", "Relay-Module-class"]


def _all_classes_with_subcomponents(ssot: dict) -> list[str]:
    """SOURCE: official — 從 verified.json 自動掃描有 on_board_components 的 class。"""
    return sorted(
        c for c, v in ssot.items()
        if isinstance(v, dict) and not c.startswith("_") and v.get("on_board_components")
    )


def _load_ssot_expected(class_name: str, ssot: dict) -> dict[str, dict]:
    """從 SSOT on_board_components 衍生期望的 cx/cy。

    Returns: {label: {cx, cy, bodyW, bodyD}}
    """
    spec = ssot.get(class_name)
    if not spec:
        raise RuntimeError(f"SSOT 無 {class_name} 條目")
    expected: dict[str, dict] = {}
    for sub in spec.get("on_board_components", []):
        label = sub["label"]
        expected[label] = {
            "cx": sub["x_mm"] + sub["w_mm"] / 2,
            "cy": sub["y_mm"] + sub["h_mm"] / 2,
            "bodyW": sub["w_mm"],
            "bodyD": sub["h_mm"],
        }
    return expected


def _extract_ports(js_text: str, class_name: str) -> list[dict]:
    """粗略解析 dimensions.js 抓出 class_name 的 ports。"""
    m = re.search(
        rf'"{re.escape(class_name)}"\s*:\s*\{{[^}}]*ports\s*:\s*\[(.*?)\]\s*\}}',
        js_text, flags=re.DOTALL,
    )
    if not m:
        raise RuntimeError(f"dims.js 無 {class_name} 條目")
    body = m.group(1)
    ports = []
    for line in body.split("\n"):
        s = line.strip().rstrip(",")
        if not s.startswith("{"):
            continue
        port = {}
        for key in ("cx", "cy"):
            mm = re.search(rf"\b{key}\s*:\s*(-?[\d.]+)", s)
            if mm:
                port[key] = float(mm.group(1))
        lm = re.search(r"label\s*:\s*'([^']+)'", s)
        if lm:
            port["label"] = lm.group(1)
        for key in ("bodyW", "bodyD", "bodyH"):
            mm = re.search(rf"\b{key}\s*:\s*(-?[\d.]+)", s)
            if mm:
                port[key] = float(mm.group(1))
        if "label" in port:
            ports.append(port)
    return ports


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true",
                    help="掃描全 32 個有 on_board_components 的 class（完整稽核，非 CI 紅線）")
    ap.add_argument("--class", dest="cls",
                    help="只測指定元件（會繞過 CI 核心清單）")
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    dims_text = DIMS_JS.read_text(encoding="utf-8")

    if args.cls:
        components = [args.cls]
        mode = f"single ({args.cls})"
    elif args.all:
        components = _all_classes_with_subcomponents(ssot)
        mode = f"all ({len(components)} classes with on_board_components)"
    else:
        components = CORE_COMPONENTS
        mode = f"core CI ({len(components)} classes)"

    failed: list[str] = []
    checked = 0

    for class_name in components:
        try:
            expected = _load_ssot_expected(class_name, ssot)
        except RuntimeError as e:
            failed.append(f"[{class_name}] {e}")
            continue
        try:
            ports = _extract_ports(dims_text, class_name)
        except RuntimeError as e:
            failed.append(f"[{class_name}] {e}")
            continue
        by_label = {p["label"]: p for p in ports}
        for label, exp in expected.items():
            checked += 1
            actual = by_label.get(label)
            if actual is None:
                failed.append(f"[{class_name}/{label}] missing in dims.js (SSOT expects cx={exp['cx']:.2f}, cy={exp['cy']:.2f})")
                continue
            for key in ("cx", "cy"):
                if key not in actual:
                    failed.append(f"[{class_name}/{label}] dims.js missing {key} (SSOT={exp[key]:.2f})")
                    continue
                diff = abs(actual[key] - exp[key])
                if diff > TOL_MM:
                    failed.append(
                        f"[{class_name}/{label}] {key}: dims.js={actual[key]:.2f} vs SSOT={exp[key]:.2f} "
                        f"(drift {diff:.2f}mm > {TOL_MM})"
                    )

    if failed:
        print(f"[FAIL] SSOT drift ({len(failed)}/{checked} items, mode={mode}):")
        for line in failed:
            print(f"  {line}")
        print("\nFix:")
        print("  - SSOT is data/component_datasheet_verified.json (single source of truth)")
        print("  - Update v6/data/component-dimensions.js to match: cx = x_mm + w_mm/2, cy = y_mm + h_mm/2")
        return 1

    print(f"[OK] SSOT aligned: {checked} sub-components across {len(components)} classes "
          f"(tolerance={TOL_MM}mm, mode={mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
