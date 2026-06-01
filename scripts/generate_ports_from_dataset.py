"""Generate component-dimensions.js ports[] from component_datasheet_verified.json.

Reads the SSOT dataset and produces a JS file with accurate port overlays
derived from on_board_components positions, pin_layout XY, and physical features.

Usage:
    python scripts/generate_ports_from_dataset.py [--dry-run]
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(ROOT, "data", "component_datasheet_verified.json")
TARGET = os.path.join(ROOT, "v6", "data", "component-dimensions.js")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _port_shapes import infer_shape as _infer_shape, infer_color as _infer_color


def _port_from_obc(obc, comp_l, comp_w):
    """Convert an on_board_component entry to a port dict for the JS renderer."""
    name = obc.get("name", "?")
    ctype = obc.get("type", "ic")
    if "x_mm" not in obc or "y_mm" not in obc:
        raise ValueError(f"on_board_component missing required geometry 'x_mm'/'y_mm': {obc!r}")
    x = obc["x_mm"]
    y_mm = obc["y_mm"]
    w = obc.get("w_mm", 4)
    h = obc.get("h_mm", w)
    d = obc.get("d_mm")

    # Dataset coords: origin bottom-left, Y up
    # JS ports coords: origin top-left, Y down (matching CSS convention)
    y_js = comp_w - y_mm - h

    shape = _infer_shape(name, ctype, obc.get("shape"))
    color = _infer_color(ctype, obc.get("color"))

    port = {
        "side": "face",
        "x": round(x, 1),
        "y": round(max(0, y_js), 1),
        "w": round(w, 1),
        "h": round(h, 1),
        "label": _short_label(name),
        "color": color,
        "shape": shape,
    }
    if d:
        port["d"] = round(d, 1)
    if obc.get("pins"):
        port["pins"] = obc["pins"]
    if obc.get("pitch_mm"):
        port["pitch"] = obc["pitch_mm"]
    if obc.get("rows"):
        port["rows"] = obc["rows"]

    # Determine side from position (if at edge)
    if x <= 0:
        port["side"] = "left"
    elif x + w >= comp_l - 0.5:
        port["side"] = "right"
    if y_mm <= 0:
        port["side"] = "bottom"
    elif y_mm + h >= comp_w - 0.5:
        port["side"] = "top"

    return port


def _short_label(name):
    """Shorten OBC name to a display label."""
    name = re.sub(r'_+', ' ', name)
    name = re.sub(r'\b(class|module|body|active|area)\b', '', name, flags=re.I)
    return name.strip()[:12]


def _ports_from_pin_layout(pl, comp_l, comp_w):
    """Generate header-group ports from pin_layout."""
    ports = []
    for g in pl.get("header_groups", []):
        pins = g.get("pins", [])
        if not pins:
            continue

        # Find bounding box of all pins with XY
        xs = [p["x_mm"] for p in pins if "x_mm" in p]
        ys = [p["y_mm"] for p in pins if "y_mm" in p]
        if not xs or not ys:
            continue

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        pitch = g.get("pitch_mm", 2.54)
        pad_w = pitch * 0.6

        # Header bounding box
        hdr_x = x_min - pad_w / 2
        hdr_w = (x_max - x_min) + pad_w
        hdr_y_mm = y_min - pad_w / 2
        hdr_h = (y_max - y_min) + pad_w

        if hdr_w < 1:
            hdr_w = pad_w
        if hdr_h < 1:
            hdr_h = pad_w

        # Convert to JS top-left-origin
        y_js = comp_w - hdr_y_mm - hdr_h

        port = {
            "side": "face",
            "x": round(max(0, hdr_x), 1),
            "y": round(max(0, y_js), 1),
            "w": round(hdr_w, 1),
            "h": round(hdr_h, 1),
            "label": g.get("name", "Header")[:12],
            "color": "#c9b037",
            "shape": "conn-header-male",
            "pins": len(pins),
            "pitch": g.get("pitch_mm", 2.54),
        }

        # Determine side
        side = g.get("side")
        if side == "left" or hdr_x <= 0:
            port["side"] = "left"
        elif side == "right" or hdr_x + hdr_w >= comp_l - 0.5:
            port["side"] = "right"
        elif side == "bottom" or hdr_y_mm <= 1:
            port["side"] = "bottom"
        elif side == "top" or hdr_y_mm + hdr_h >= comp_w - 1:
            port["side"] = "top"

        ports.append(port)

    return ports


def _fallback_ports_for_simple(comp_key, phys, ident):
    """Generate minimal ports for components without on_board_components."""
    ports = []
    l = phys.get("length_mm", 30)
    w = phys.get("width_mm", 20)

    # LED-type: single dome element
    if "LED" in comp_key or "Lighting" in comp_key:
        diam = phys.get("diameter_mm", min(l, w) * 0.6)
        ports.append({
            "side": "face",
            "x": round((l - diam) / 2, 1),
            "y": round((w - diam) / 2, 1),
            "w": round(diam, 1),
            "h": round(diam, 1),
            "label": "LED",
            "color": "#ef4444",
            "shape": "led-tht",
        })

    # Battery: cells
    elif "Battery" in comp_key:
        ports.append({
            "side": "face",
            "x": round(l * 0.1, 1),
            "y": round(w * 0.15, 1),
            "w": round(l * 0.8, 1),
            "h": round(w * 0.7, 1),
            "label": "Cell",
            "color": "#3b82f6",
            "shape": "box",
        })

    # Button: cap
    elif "Button" in comp_key:
        cap = min(l, w) * 0.5
        ports.append({
            "side": "face",
            "x": round((l - cap) / 2, 1),
            "y": round((w - cap) / 2, 1),
            "w": round(cap, 1),
            "h": round(cap, 1),
            "label": "Cap",
            "color": "#444",
            "shape": "button-tactile",
        })

    # Potentiometer: knob
    elif "Potentiometer" in comp_key:
        shaft_d = phys.get("shaft_diameter_mm", 6)
        ports.append({
            "side": "face",
            "x": round((l - shaft_d) / 2, 1),
            "y": round((w - shaft_d) / 2, 1),
            "w": round(shaft_d, 1),
            "h": round(shaft_d, 1),
            "label": "Shaft",
            "color": "#888",
            "shape": "pot-shaft",
        })

    # Joystick: stick
    elif "Joystick" in comp_key:
        sh = phys.get("stick_height_mm", 15)
        ports.append({
            "side": "face",
            "x": round(l * 0.3, 1),
            "y": round(w * 0.3, 1),
            "w": round(min(l, w) * 0.35, 1),
            "h": round(min(l, w) * 0.35, 1),
            "label": "Stick",
            "color": "#555",
            "shape": "cylinder",
        })

    # Remote: IR window
    elif "Remote" in comp_key:
        ports.append({
            "side": "face",
            "x": round(l * 0.3, 1),
            "y": round(w * 0.15, 1),
            "w": round(l * 0.4, 1),
            "h": round(w * 0.3, 1),
            "label": "IR Window",
            "color": "#1a1a2e",
            "shape": "box",
        })

    # Chassis: wheels
    elif "Chassis" in comp_key:
        wd = phys.get("wheel_diameter_mm", 40)
        for ox, oy in [(0.1, 0.15), (0.7, 0.15), (0.1, 0.65), (0.7, 0.65)]:
            ports.append({
                "side": "face",
                "x": round(l * ox, 1),
                "y": round(w * oy, 1),
                "w": round(wd, 1),
                "h": round(wd, 1),
                "label": "Wheel",
                "color": "#333",
                "shape": "cylinder",
            })

    # Generic fallback
    elif not ports:
        ports.append({
            "side": "face",
            "x": round(l * 0.2, 1),
            "y": round(w * 0.2, 1),
            "w": round(l * 0.6, 1),
            "h": round(w * 0.6, 1),
            "label": comp_key.split("-")[0],
            "color": "#888",
            "shape": "box",
        })

    return ports


def generate_all():
    with open(DATASET, "r", encoding="utf-8") as f:
        ds = json.load(f)

    with open(TARGET, "r", encoding="utf-8") as f:
        existing_js = f.read()

    results = {}
    for comp_key in sorted(ds.keys()):
        if comp_key.startswith("_"):
            continue  # _meta / _ssot20_research_provenance 等 metadata 鍵，非元件
        entry = ds[comp_key]
        phys = entry.get("physical", {})
        ident = entry.get("identity", {})
        pl = entry.get("pin_layout", {})
        obc = entry.get("on_board_components", [])

        # 必填外框尺寸：標準件用 length/width/height_mm；複合件（如 Motor-Stepper 馬達+驅動板）
        # 用 combined_* 權威外框。兩者皆無才 raise（禁靜默套魔術預設 30/20/10）。
        l = phys.get("length_mm", phys.get("combined_length_mm"))
        w = phys.get("width_mm", phys.get("combined_width_mm"))
        h = phys.get("height_mm", phys.get("combined_height_mm"))
        if l is None or w is None or h is None:
            raise ValueError(f"{comp_key}: physical length/width/height_mm (or combined_*) missing from SSOT")

        ports = []

        # 1. From on_board_components (primary source)
        if obc:
            for item in obc:
                ports.append(_port_from_obc(item, l, w))

        # 2. From pin_layout header groups
        pin_ports = _ports_from_pin_layout(pl, l, w)
        # Avoid duplicate headers if OBC already has them
        obc_labels = {p["label"].lower() for p in ports}
        for pp in pin_ports:
            if pp["label"].lower() not in obc_labels:
                ports.append(pp)

        # 3. Fallback for simple components
        if not ports:
            ports = _fallback_ports_for_simple(comp_key, phys, ident)

        results[comp_key] = {"l": l, "w": w, "h": h, "ports": ports}

    return results


def _fmt_port(p):
    """Format a single port dict as compact JS."""
    parts = [f"side: '{p['side']}'", f"x: {p['x']}", f"y: {p['y']}",
             f"w: {p['w']}", f"h: {p['h']}"]
    if "d" in p:
        parts.append(f"d: {p['d']}")
    parts.append(f"label: '{p['label']}'")
    parts.append(f"color: '{p['color']}'")
    parts.append(f"shape: '{p['shape']}'")  # required; no silent fallback (set at construction)
    if "pins" in p:
        parts.append(f"pins: {p['pins']}")
    if "pitch" in p:
        parts.append(f"pitch: {p['pitch']}")
    if "rows" in p:
        parts.append(f"rows: {p['rows']}")
    return "{ " + ", ".join(parts) + " }"


def write_js(results, dry_run=False):
    """Rewrite component-dimensions.js with generated ports."""
    with open(TARGET, "r", encoding="utf-8") as f:
        js = f.read()

    # Parse existing JS to find each component entry and replace its ports
    changed = 0
    for comp_key, data in results.items():
        # Match the entry in JS: 'CompKey-class': { l: N, w: N, h: N, ports: [...] }
        # Use regex to find and replace the entire entry
        pat = re.compile(
            r"('" + re.escape(comp_key) + r"'\s*:\s*\{[^}]*?ports:\s*)\[.*?\]",
            re.DOTALL
        )
        if not pat.search(js):
            continue

        port_strs = ["\n    " + _fmt_port(p) + "," for p in data["ports"]]
        ports_block = "[" + "".join(port_strs) + "\n  ]"

        js = pat.sub(lambda m: m.group(1) + ports_block, js)
        changed += 1

    if dry_run:
        print(f"Would update {changed} entries in component-dimensions.js")
        # Show a sample
        sample_key = "Sensor-PIR-class"
        if sample_key in results:
            print(f"\nSample ({sample_key}):")
            for p in results[sample_key]["ports"]:
                print(f"  {_fmt_port(p)}")
        return

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"Updated {changed} entries in component-dimensions.js")


def main():
    dry_run = "--dry-run" in sys.argv
    results = generate_all()
    print(f"Generated ports for {len(results)} components")

    # Stats
    total_ports = sum(len(d["ports"]) for d in results.values())
    print(f"Total port entries: {total_ports}")

    write_js(results, dry_run=dry_run)


if __name__ == "__main__":
    main()
