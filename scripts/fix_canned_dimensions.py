"""Fix baked canned template placement dimensions to match SSOT.

Reads component-dimensions.js, then patches each canned-*.json in output/state/.
"""
import json, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CANNED_DIR = ROOT / "output" / "state"
COMP_DIM_JS = ROOT / "v6" / "data" / "component-dimensions.js"

def parse_component_dimensions(js_path):
    text = js_path.read_text(encoding="utf-8")
    dims = {}
    pattern = re.compile(r'"([^"]+)":\s*\{\s*l:\s*([\d.]+),\s*w:\s*([\d.]+),\s*h:\s*([\d.]+)')
    for m in pattern.finditer(text):
        dims[m.group(1)] = {"l": float(m.group(2)), "w": float(m.group(3)), "h": float(m.group(4))}
    return dims


def main():
    ssot = parse_component_dimensions(COMP_DIM_JS)
    print(f"SSOT: {len(ssot)} component types")

    total_fixed = 0
    for cf in sorted(CANNED_DIR.glob("canned-*.json")):
        name = cf.stem.replace("canned-", "")
        data = json.loads(cf.read_text(encoding="utf-8"))
        cad = data.get("cad_output", {})
        placements = cad.get("component_placements", [])
        if not placements:
            continue

        fixes = []
        for comp in placements:
            ctype = comp.get("type", "")
            if ctype not in ssot:
                continue
            ref = ssot[ctype]
            dl = abs(comp.get("L", 0) - ref["l"])
            dw = abs(comp.get("W", 0) - ref["w"])
            dh = abs(comp.get("H", 0) - ref["h"])
            if dl > 0.5 or dw > 0.5 or dh > 0.5:
                old = f"{comp.get('L',0)}x{comp.get('W',0)}x{comp.get('H',0)}"
                comp["L"] = ref["l"]
                comp["W"] = ref["w"]
                comp["H"] = ref["h"]
                fixes.append(f"{ctype}: {old} -> {ref['l']}x{ref['w']}x{ref['h']}")

        if fixes:
            cf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"[{name}] fixed {len(fixes)} placements:")
            for f in fixes:
                print(f"  {f}")
            total_fixed += len(fixes)
        else:
            print(f"[{name}] ok")

    print(f"\nTotal: {total_fixed} placements fixed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
