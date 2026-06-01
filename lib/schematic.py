"""
schematic.py — Schematic SVG generation (Phase III fallback)

Front-end SSOT: v6/schematic-elk.jsx (ELK layout + registry.py standard sizes).
This module serves as the backend API /api/v1/schematic fallback;
component sizes come from registry.py.

Refactored to use xml.etree.ElementTree DOM builder for
structured SVG generation with proper XML escaping and tooltips.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from .wiring import resolve_wiring, normalize_brain, normalize_comps

# ── Layout Constants ─────────────────────────────────────────
_W, _H = 800, 480
_MCU_X, _MCU_W = 350, 100

_ROLE_COL = {
    "Brain": "#00aaff", "Output": "#00ff88",
    "Sensor": "#ff88cc", "Power": "#f0c060",
}
_BRAIN_LABELS = {
    "Arduino": "Arduino\nUno", "ESP32": "ESP32",
    "RPi": "RPi\n4B", "Microbit": "micro\n:bit",
}
_OUT_LABELS = {
    "NeoPixel": "NeoPixel\nWS2812B", "LED_Single": "Single\nLED",
    "LED_RGB": "RGB\nLED", "Speaker": "DFPlayer\nMini",
    "Buzzer_Active": "Buzzer\n(Active)", "Buzzer_Passive": "Buzzer\n(Passive)",
    "OLED": "OLED\nSSD1306",
    "LCD": "LCD 1602\n+I2C", "Servo": "SG90\nServo",
    "DCMotor": "L298N\nDriver", "Relay": "Relay\n5V", "Pump": "Water\nPump",
    "Stepper": "28BYJ-48\nStepper",
}
_SEN_LABELS = {
    "TempHumid": "DHT22\nTemp/Hum", "Ultrasonic": "HC-SR04\nUltrasonic",
    "PIR": "HC-SR501\nPIR", "SoilMoisture": "Soil\nSensor",
    "Light": "LDR\nPhoto",
}
_POWER_LABELS = {"LiPo": "LiPo 3.7V", "USB-5V": "USB 5V", "AA": "AA 電池",
                 "DC-5V": "DC 5V 2A", "auto": "USB 5V"}
_NON_DATA_MCUS = {"GND", "5V", "3.3V", "EXT", "SPK", "SPK-", "LOAD"}

_SVG_NS = "http://www.w3.org/2000/svg"


def generate_svg(brain: str, power: str,
                 outputs: list[str], sensors: list[str],
                 wiring_notes: dict | None = None) -> str:
    """
    Generate a complete Schematic SVG (with animation, legend, grid).

    Args:
        brain: "Arduino" | "ESP32" | "RPi" | "Microbit"
        power: "USB-5V" | "LiPo" | "AA" | "DC-5V"
        outputs: list of output component keys
        sensors: list of sensor component keys
        wiring_notes: optional dict of wire_id -> educational tooltip text

    Returns:
        SVG string
    """
    if wiring_notes is None:
        wiring_notes = {}

    brain_key = normalize_brain(brain) if brain != "auto" else "Arduino"
    outputs = normalize_comps(outputs)
    sensors = normalize_comps(sensors)
    all_comps = outputs + sensors
    wiring = resolve_wiring(brain_key, all_comps)

    mcu_h = max(120, len(all_comps) * 28 + 20)
    mcu_y = (_H - mcu_h) // 2

    # ── Build SVG DOM ──
    root = ET.Element("svg", {
        "xmlns": _SVG_NS,
        "width": str(_W),
        "height": str(_H),
        "viewBox": f"0 0 {_W} {_H}",
        "style": "background:#0a0a0f;font-family:'IBM Plex Mono','Courier New',monospace;",
    })

    # Animation CSS + markers
    style = ET.SubElement(root, "style")
    style.text = (
        "@keyframes sigflow { 0%{stroke-dashoffset:40;opacity:.9} "
        "100%{stroke-dashoffset:0;opacity:.2} }\n"
        ".sig-anim { stroke-dasharray:6 4; animation:sigflow .7s linear infinite; }"
    )
    defs = ET.SubElement(root, "defs")
    for mid, fill in [("arrowG", "#00cc66"), ("arrowP", "#cc4488")]:
        marker = ET.SubElement(defs, "marker", {
            "id": mid, "markerWidth": "6", "markerHeight": "5",
            "refX": "5", "refY": "2.5", "orient": "auto",
        })
        ET.SubElement(marker, "polygon", {
            "points": "0 0, 6 2.5, 0 5", "fill": fill, "opacity": "0.8",
        })

    # ── Grid background ──
    for y in range(0, _H + 1, 30):
        ET.SubElement(root, "line", {
            "x1": "0", "y1": str(y), "x2": str(_W), "y2": str(y),
            "stroke": "#1a1a28", "stroke-width": "1",
        })
    for x in range(0, _W + 1, 30):
        ET.SubElement(root, "line", {
            "x1": str(x), "y1": "0", "x2": str(x), "y2": str(_H),
            "stroke": "#1a1a28", "stroke-width": "1",
        })

    # ── MCU block ──
    mcu_rect = ET.SubElement(root, "rect", {
        "x": str(_MCU_X), "y": str(mcu_y),
        "width": str(_MCU_W), "height": str(mcu_h),
        "rx": "4", "fill": "#141420",
        "stroke": _ROLE_COL["Brain"], "stroke-width": "1.5",
    })
    mcu_title = ET.SubElement(mcu_rect, "title")
    mcu_title.text = f"{brain_key} MCU"

    for li, ln in enumerate(_BRAIN_LABELS.get(brain_key, brain_key).split("\n")):
        ty = mcu_y + mcu_h // 2 - 6 + li * 14
        txt = ET.SubElement(root, "text", {
            "x": str(_MCU_X + _MCU_W // 2), "y": str(ty),
            "text-anchor": "middle",
            "fill": _ROLE_COL["Brain"], "font-size": "11", "font-weight": "700",
        })
        txt.text = ln

    # ── Power rail ──
    pwr_label = _POWER_LABELS.get(power, "USB 5V")
    pwr_rect = ET.SubElement(root, "rect", {
        "x": str(_MCU_X + 10), "y": "14",
        "width": str(_MCU_W - 20), "height": "24", "rx": "4",
        "fill": "none", "stroke": _ROLE_COL["Power"],
        "stroke-width": "1.5", "stroke-dasharray": "4,2",
    })
    pwr_title = ET.SubElement(pwr_rect, "title")
    pwr_title.text = f"Power: {pwr_label}"

    pwr_txt = ET.SubElement(root, "text", {
        "x": str(_MCU_X + _MCU_W // 2), "y": "30",
        "text-anchor": "middle",
        "fill": _ROLE_COL["Power"], "font-size": "10",
    })
    pwr_txt.text = pwr_label

    ET.SubElement(root, "line", {
        "x1": str(_MCU_X + _MCU_W // 2), "y1": "38",
        "x2": str(_MCU_X + _MCU_W // 2), "y2": str(mcu_y),
        "stroke": _ROLE_COL["Power"], "stroke-width": "1.5",
        "stroke-dasharray": "3,2",
    })

    # ── Left: outputs ──
    _render_side(root, outputs, wiring, _OUT_LABELS,
                 side="left", role="Output", mcu_y=mcu_y, mcu_h=mcu_h,
                 wiring_notes=wiring_notes)

    # ── Right: sensors ──
    _render_side(root, sensors, wiring, _SEN_LABELS,
                 side="right", role="Sensor", mcu_y=mcu_y, mcu_h=mcu_h,
                 wiring_notes=wiring_notes)

    # ── GND rail ──
    ET.SubElement(root, "line", {
        "x1": "60", "y1": str(_H - 20),
        "x2": str(_W - 60), "y2": str(_H - 20),
        "stroke": "#555", "stroke-width": "1", "stroke-dasharray": "3,3",
    })
    gnd_txt = ET.SubElement(root, "text", {
        "x": str(_W // 2), "y": str(_H - 6),
        "text-anchor": "middle", "fill": "#555", "font-size": "9",
    })
    gnd_txt.text = "─── GND Rail ───"

    # ── Legend ──
    for i, (role, lbl) in enumerate([
        ("Brain", "MCU 主控"), ("Output", "輸出元件"),
        ("Sensor", "感測器"), ("Power", "電源"),
    ]):
        ly = 20 + i * 16
        ET.SubElement(root, "rect", {
            "x": "20", "y": str(ly), "width": "10", "height": "10",
            "rx": "2", "fill": _ROLE_COL[role],
        })
        leg_txt = ET.SubElement(root, "text", {
            "x": "34", "y": str(ly + 9), "fill": "#aaa", "font-size": "9",
        })
        leg_txt.text = lbl

    return ET.tostring(root, encoding="unicode")


def _render_side(parent: ET.Element, comps: list[str], wiring: dict,
                 label_map: dict, *, side: str, role: str,
                 mcu_y: int, mcu_h: int, wiring_notes: dict):
    if not comps:
        return
    col = _ROLE_COL[role]
    start_y = mcu_y + 20
    step = (mcu_h - 40) / (len(comps) - 1) if len(comps) > 1 else 0
    is_left = side == "left"
    cx = 130 if is_left else _W - 130

    for i, key in enumerate(comps):
        spec = wiring.get(key)
        cy = mcu_y + mcu_h // 2 if len(comps) == 1 else int(start_y + i * step)

        data_pins = []
        if spec:
            data_pins = [p for p in spec["pins"] if p["mcu"] not in _NON_DATA_MCUS]

        bw, bh = 90, 50

        # Component group
        g = ET.SubElement(parent, "g", {
            "data-xv-id": f"comp:{key}", "style": "cursor:pointer;",
        })

        # Component box with tooltip
        comp_rect = ET.SubElement(g, "rect", {
            "x": str(cx - bw // 2), "y": str(cy - bh // 2),
            "width": str(bw), "height": str(bh),
            "rx": "4", "fill": "#141420",
            "stroke": col, "stroke-width": "1.5",
        })
        comp_title = ET.SubElement(comp_rect, "title")
        if spec:
            pin_summary = ", ".join(f"{p['comp']}={p['mcu']}" for p in spec["pins"]
                                    if p["mcu"] not in _NON_DATA_MCUS)
            comp_title.text = f"{spec['label']} [{pin_summary}]"
        else:
            comp_title.text = label_map.get(key, key)

        # Component label text
        for li, ln in enumerate(label_map.get(key, key).split("\n")):
            txt = ET.SubElement(g, "text", {
                "x": str(cx), "y": str(cy - 6 + li * 13),
                "text-anchor": "middle", "fill": col, "font-size": "9",
            })
            txt.text = ln

        # Wires
        if is_left:
            comp_edge = cx + bw // 2
            mcu_edge = _MCU_X
        else:
            comp_edge = cx - bw // 2
            mcu_edge = _MCU_X + _MCU_W

        for pi, dp in enumerate(data_pins):
            wy = cy - (len(data_pins) - 1) * 4 + pi * 8
            mid_x = (comp_edge + mcu_edge) // 2 + (pi * 8 if is_left else -pi * 8)

            if is_left:
                d_path = f"M{comp_edge},{wy} C{mid_x},{wy} {mid_x},{wy} {mcu_edge},{wy}"
                anim_from, anim_to = "0", "-20"
                lbl_x = comp_edge + 4
            else:
                d_path = f"M{mcu_edge},{wy} C{mid_x},{wy} {mid_x},{wy} {comp_edge},{wy}"
                anim_from, anim_to = "0", "20"
                lbl_x = mcu_edge + 4

            path_el = ET.SubElement(g, "path", {
                "d": d_path, "fill": "none",
                "stroke": dp["color"], "stroke-width": "1.5",
                "stroke-dasharray": "6,4",
            })
            ET.SubElement(path_el, "animate", {
                "attributeName": "stroke-dashoffset",
                "from": anim_from, "to": anim_to,
                "dur": "1.2s", "repeatCount": "indefinite",
            })

            # Wire tooltip from wiring_notes
            wire_id = f"MCU_{dp['mcu']}_to_{key}_{dp['comp']}"
            note_text = wiring_notes.get(wire_id)
            if note_text:
                wire_title = ET.SubElement(path_el, "title")
                wire_title.text = note_text

            # Wire label text
            wire_lbl = ET.SubElement(g, "text", {
                "x": str(lbl_x), "y": str(wy - 3),
                "fill": dp["color"], "font-size": "7",
            })
            wire_lbl.text = f"{dp['comp']}→{dp['mcu']}"

        # VCC/GND dots
        if spec and any(p["mcu"] in ("5V", "3.3V") for p in spec["pins"]):
            dot_x = cx - bw // 2 - 6 if is_left else cx + bw // 2 + 6
            ET.SubElement(g, "circle", {
                "cx": str(dot_x), "cy": str(cy - 8), "r": "3", "fill": "#ff4444",
            })
            ET.SubElement(g, "circle", {
                "cx": str(dot_x), "cy": str(cy + 8), "r": "3", "fill": "#333",
            })


def to_json(brain: str, power: str,
            outputs: list[str], sensors: list[str]) -> dict:
    """API-ready: return SVG string + structured node/edge."""
    svg = generate_svg(brain, power, outputs, sensors)
    return {"raw_svg": svg}
