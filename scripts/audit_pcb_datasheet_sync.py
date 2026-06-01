"""scripts/audit_pcb_datasheet_sync.py — lib/pcb vs datasheet JSON diff.

Compares lib/pcb SubComponents (SSOT) against
data/component_datasheet_verified.json on_board_components.
Reports: missing, extra, name mismatch, position/size drift.

Usage:
  .venv/Scripts/python.exe scripts/audit_pcb_datasheet_sync.py
  .venv/Scripts/python.exe scripts/audit_pcb_datasheet_sync.py --fix  # auto-patch JSON
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.pcb import (
    ARDUINO_UNO_R3,
    ESP32_DEVKIT_V1,
    MICROBIT_V2,
    RASPBERRY_PI_4B,
    PCBSpec,
    SubComponent,
)

DATASHEET_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "component_datasheet_verified.json",
)

BOARD_MAP = {
    "Arduino-Uno-class": ARDUINO_UNO_R3,
    "ESP32-class": ESP32_DEVKIT_V1,
    "Microbit-class": MICROBIT_V2,
    "RaspberryPi-class": RASPBERRY_PI_4B,
}

BOARD_ALIASES = {
    "Arduino-Uno-class": {
        "DC-Barrel": "DC-Jack",
        "NCP1117-5V": "V-Reg-5V",
        "Reset-Button": "Reset-Switch",
        "LED-PWR": "LED-ON",
    },
    "ESP32-class": {
        "CP2102": "USB-UART",
        "AMS1117-3V3": "LDO-AMS1117",
        "Micro-USB": "USB-Micro",
    },
    "Microbit-class": {
        "nRF52833-QDAA": "nRF52833",
        "Micro-USB": "USB-Micro",
        "Reset-Button": "Reset-Button",
    },
    "RaspberryPi-class": {
        "BCM2711-SoC": "BCM2711",
        "LPDDR4-RAM": "LPDDR4",
        "USB-C-Power": "USB-C-PWR",
        "microHDMI-0": "HDMI-0",
        "microHDMI-1": "HDMI-1",
        "3.5mm-Audio": "Audio-Jack",
        "USB-3.0-x2": "USB-A-Top",
        "USB-2.0-x2": "USB-A-Bottom",
        "CSI-Camera": "CSI-Camera",
        "DSI-Display": "DSI-Display",
    },
}


def _normalize_name(name: str, board: str = "") -> str:
    aliases = BOARD_ALIASES.get(board, {})
    return aliases.get(name, name)


def _load_datasheet():
    with open(DATASHEET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _sub_to_dict(sc: SubComponent) -> dict:
    return {
        "name": sc.name,
        "anchor_x": sc.anchor_x,
        "anchor_y": sc.anchor_y,
        "body_l": sc.body_l,
        "body_w": sc.body_w,
        "body_h": sc.body_h,
        "package": sc.package,
        "description": sc.description,
    }


def audit_board(class_name: str, pcb_spec: PCBSpec, ds_entry: dict) -> list:
    issues = []
    ds_comps = ds_entry.get("on_board_components", [])
    ds_by_name = {}
    for c in ds_comps:
        n = c.get("name", c.get("id", ""))
        ds_by_name[_normalize_name(n, class_name)] = c

    pcb_names = set()
    for sc in pcb_spec.sub_components:
        pcb_names.add(sc.name)
        ds_match = ds_by_name.get(sc.name)
        if not ds_match:
            issues.append({
                "board": class_name,
                "type": "missing_in_json",
                "component": sc.name,
                "detail": f"lib/pcb has {sc.name} but JSON datasheet does not",
            })
            continue

        dl = ds_match.get("w_mm", 0)
        dw = ds_match.get("h_mm", 0)
        if abs(dl - sc.body_l) > 1.0 or abs(dw - sc.body_w) > 1.0:
            issues.append({
                "board": class_name,
                "type": "size_drift",
                "component": sc.name,
                "detail": (
                    f"JSON w={dl},h={dw} vs "
                    f"SSOT body_l={sc.body_l},body_w={sc.body_w}"
                ),
            })

    for ds_name in ds_by_name:
        if ds_name not in pcb_names:
            issues.append({
                "board": class_name,
                "type": "extra_in_json",
                "component": ds_name,
                "detail": f"JSON has {ds_name} but lib/pcb does not",
            })

    return issues


def generate_json_from_pcb(pcb_spec: PCBSpec) -> list:
    """Generate on_board_components JSON from lib/pcb SSOT."""
    TYPE_MAP = {
        "SMD-WROOM": "module", "QFN": "ic", "TQFP": "ic",
        "QFN-73": "ic", "QFN-68": "ic", "QFN-48": "ic", "QFN-24": "ic",
        "BGA": "ic", "LGA-12": "ic", "MEMS": "ic",
        "SOIC-8": "ic", "SOT-223": "ic", "SOT-23-5": "ic",
        "USB-MICRO-B": "connector", "USB-B": "connector",
        "USB-C": "connector", "DC-BARREL": "connector",
        "Micro-HDMI": "connector", "3.5mm-TRRS": "connector",
        "RJ45": "connector", "USB-A-Stack-3.0": "connector",
        "USB-A-Stack-2.0": "connector", "2x20-header": "connector",
        "microSD-slot": "connector", "FPC-15": "connector",
        "edge-connector-80": "connector",
        "TACT": "button",
        "SW-SMD-4P": "button", "SW-THT": "button",
        "LED-0805": "led", "LED-0603": "led", "SMD-0402": "led",
        "PCB-TRACE": "feature", "XTAL-HC49": "passive",
        "5x5": "feature", "speaker": "feature",
        "capacitive-pad": "feature",
    }
    COLOR_MAP = {
        "module": "#374151", "ic": "#1e3a5f", "connector": "#7dd3fc",
        "button": "#ef4444", "led": "#22c55e", "feature": "#78350f",
        "passive": "#6b7280",
    }
    result = []
    for sc in pcb_spec.sub_components:
        comp_type = TYPE_MAP.get(sc.package, "ic")
        if "LED" in sc.name:
            comp_type = "led"
        if "BTN" in sc.name:
            comp_type = "button"
        result.append({
            "name": sc.name,
            "type": comp_type,
            "desc": sc.description,
            "x_mm": round(sc.anchor_x - sc.body_l / 2, 1),
            "y_mm": round(sc.anchor_y - sc.body_w / 2, 1),
            "w_mm": sc.body_l,
            "h_mm": sc.body_w,
            "shape": "box",
            "color": COLOR_MAP.get(comp_type, "#6b7280"),
        })
    return result


def main():
    fix_mode = "--fix" in sys.argv
    ds = _load_datasheet()
    total_issues = 0

    for class_name, pcb_spec in BOARD_MAP.items():
        if class_name not in ds:
            print(f"[SKIP] {class_name} not in datasheet JSON")
            continue

        issues = audit_board(class_name, pcb_spec, ds[class_name])
        n_pcb = len(pcb_spec.sub_components)
        n_ds = len(ds[class_name].get("on_board_components", []))

        print(f"\n{'='*60}")
        print(f"{class_name}: lib/pcb={n_pcb} vs JSON={n_ds}")
        print(f"{'='*60}")

        if not issues:
            print("  OK (no discrepancies)")
        else:
            for iss in issues:
                tag = iss["type"].upper()
                print(f"  [{tag}] {iss['component']}: {iss['detail']}")
            total_issues += len(issues)

        if fix_mode:
            generated = generate_json_from_pcb(pcb_spec)
            ds[class_name]["on_board_components"] = generated
            print(f"  [FIX] Regenerated {len(generated)} components from SSOT")

    print(f"\n{'='*60}")
    print(f"Total issues: {total_issues}")

    if fix_mode and total_issues > 0:
        with open(DATASHEET_PATH, "w", encoding="utf-8") as f:
            json.dump(ds, f, indent=2, ensure_ascii=False)
        print(f"[FIX] Wrote updated {DATASHEET_PATH}")

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
