"""derive_component_dimensions.py — 從 verified.json 衍生 v6/data/component-dimensions.js entries

Phase 3B: SSOT migration step 1。讀 data/component_datasheet_verified.json，
按 _ui_hints + on_board_components + extra_ports 衍生前端 ports 陣列。

用法：
  # 衍生並輸出到 stdout（不寫檔）
  .venv/Scripts/python.exe scripts/derive_component_dimensions.py

  # 衍生並對比現有 dims.js（drift gate，退出碼 0 = 對齊）
  .venv/Scripts/python.exe scripts/derive_component_dimensions.py --check

  # 只處理特定 class
  .venv/Scripts/python.exe scripts/derive_component_dimensions.py --class Relay-Module-class
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"
DIMS_JS = ROOT / "v6" / "data" / "component-dimensions.js"

# 受測元件清單：自動從 verified.json 抓所有有 _ui_hints 的元件
def _all_classes_with_hints() -> list[str]:
    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    return sorted(c for c, v in ssot.items() if "_ui_hints" in v)


def derive_ports(class_name: str, spec: dict) -> list[dict]:
    """從 verified.json 條目衍生前端 ports 陣列。"""
    ui = spec.get("_ui_hints", {})
    shape_map = ui.get("frontend_shape", {})
    ports: list[dict] = []

    for sub in spec.get("on_board_components", []):
        label = sub.get("label") or sub.get("name")
        if not label:
            continue
        shape_info = shape_map.get(label)
        if not shape_info:
            continue  # 無 frontend_shape 對應 → 跳過（不渲染）
        cx = sub["x_mm"] + sub["w_mm"] / 2
        cy = sub["y_mm"] + sub["h_mm"] / 2
        params = {"bodyW": sub["w_mm"], "bodyD": sub["h_mm"]}
        params.update(shape_info.get("extra_params", {}))
        ports.append({
            "side": shape_info.get("side", "face"),
            "cx": round(cx, 3),
            "cy": round(cy, 3),
            "shape": shape_info["shape"],
            "label": label,
            "color": shape_info["color"],
            "params": params,
        })

    # extra_ports（無 on_board_components 對應的純邏輯 port，如 WIRES）
    for extra in ui.get("extra_ports", []):
        ports.append({
            "side": extra.get("side", "face"),
            "cx": extra["cx"],
            "cy": extra["cy"],
            "shape": extra["shape"],
            "label": extra["label"],
            "color": extra.get("color", "#888"),
            "params": extra.get("extra_params", {}),
            **({"rot": extra["rot"]} if "rot" in extra else {}),
        })

    # P5.8: 從 pin_layout.header_groups 衍生 ports（opt-in，避免 verified.json 雙寫）
    # 需 _ui_hints.derive_from_pin_layout = true 才啟用，避免影響其他 27 個 class（命名慣例不一）。
    if ui.get("derive_from_pin_layout"):
        existing_labels = {p["label"] for p in ports}
        for hg in spec.get("pin_layout", {}).get("header_groups", []):
            name = hg.get("name", "")
            if not name or name in existing_labels:
                continue
            pins = hg.get("pins", [])
            if not pins:
                continue
            cx = sum(p.get("x_mm", 0) for p in pins) / len(pins)
            cy = sum(p.get("y_mm", 0) for p in pins) / len(pins)
            info = shape_map.get(name, {})
            # pitch：明示 pitch_mm 優先；否則從真實 pin 座標推導（SSOT，不漂移）；
            # 皆不可得才 raise（VS-PCB：禁以 2.54 頂替非標準連接器）。
            pitch = hg.get("pitch_mm")
            if pitch is None:
                _pxs = [p.get("x_mm", 0) for p in pins]
                _pys = [p.get("y_mm", 0) for p in pins]
                _span = (max(max(_pxs) - min(_pxs), max(_pys) - min(_pys))
                         if len(pins) >= 2 else 0)
                if len(pins) < 2 or _span <= 0:
                    raise ValueError(
                        f"{class_name}/{name}: header 缺 pitch_mm 且 pin 座標不足以推導 pitch，"
                        "拒絕以 2.54 頂替"
                    )
                pitch = round(_span / (len(pins) - 1), 3)
            params = {
                "pins": hg.get("pin_count", len(pins)),
                "pitch": pitch,
                "rows": hg.get("rows", 1),
            }
            params.update(info.get("extra_params", {}))
            ports.append({
                "side": info.get("side", hg.get("side", "face")),
                "cx": round(cx, 3),
                "cy": round(cy, 3),
                "shape": info.get("shape", "conn-header-male"),
                "label": name,
                "color": info.get("color", "#c9b037"),
                "params": params,
            })
    return ports


def _phys_dim(phys: dict, *keys) -> float | None:
    for k in keys:
        if k in phys and isinstance(phys[k], (int, float)):
            return float(phys[k])
    return None


def derive_entry(class_name: str, spec: dict) -> dict:
    phys = spec.get("physical", {})
    return {
        "l": _phys_dim(phys, "length_mm", "combined_length_mm"),
        "w": _phys_dim(phys, "width_mm", "combined_width_mm"),
        "h": _phys_dim(phys, "height_mm", "combined_height_mm"),
        "ports": derive_ports(class_name, spec),
    }


def _fmt_param_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return f"'{v}'"


def _fmt_params(params: dict) -> str:
    parts = [f"{k}: {_fmt_param_value(v)}" for k, v in params.items()]
    return "{ " + ", ".join(parts) + " }"


def fmt_port_js(p: dict) -> str:
    parts = [f"side: '{p['side']}'", f"cx: {p['cx']}", f"cy: {p['cy']}",
             f"shape: '{p['shape']}'", f"label: '{p['label']}'", f"color: '{p['color']}'"]
    if p.get("params"):
        parts.append(f"params: {_fmt_params(p['params'])}")
    return "{ " + ", ".join(parts) + " }"


def fmt_entry_js(class_name: str, entry: dict) -> str:
    lines = [f'  "{class_name}":' + " { " + f"l: {entry['l']}, w: {entry['w']}, h: {entry['h']}, ports: ["]
    for i, p in enumerate(entry["ports"]):
        suffix = "," if i < len(entry["ports"]) - 1 else ""
        lines.append(f"    {fmt_port_js(p)}{suffix}")
    lines.append("  ] }")
    return "\n".join(lines)


def _extract_dims_entry(js_text: str, class_name: str) -> str | None:
    """從 dims.js 抽出 class_name 的 entry 文字（粗略）。"""
    m = re.search(
        rf'"{re.escape(class_name)}"\s*:\s*\{{[^}}]*ports\s*:\s*\[(.*?)\]\s*\}}',
        js_text, flags=re.DOTALL,
    )
    if not m:
        return None
    return m.group(0)


def _parse_dims_entry(js_text: str, class_name: str) -> dict | None:
    """從 dims.js 抽 entry，回傳 {l, w, h, ports: [...]} 結構。"""
    m = re.search(
        rf'"{re.escape(class_name)}"\s*:\s*\{{(.*?)ports\s*:\s*\[(.*?)\]\s*\}}',
        js_text, flags=re.DOTALL,
    )
    if not m:
        return None
    head, body = m.group(1), m.group(2)
    out = {"ports": []}
    for key in ("l", "w", "h"):
        mm = re.search(rf"\b{key}\s*:\s*(-?[\d.]+)", head)
        if mm:
            out[key] = float(mm.group(1))
    for line in body.split("\n"):
        s = line.strip().rstrip(",")
        if not s.startswith("{"):
            continue
        port = {"params": {}}
        for key in ("cx", "cy"):
            mm = re.search(rf"\b{key}\s*:\s*(-?[\d.]+)", s)
            if mm:
                port[key] = float(mm.group(1))
        for key in ("side", "shape", "label", "color"):
            mm = re.search(rf"\b{key}\s*:\s*'([^']+)'", s)
            if mm:
                port[key] = mm.group(1)
        # params block
        pm = re.search(r"params\s*:\s*\{([^}]*)\}", s)
        if pm:
            for kv in pm.group(1).split(","):
                kv = kv.strip()
                if not kv or ":" not in kv:
                    continue
                k, v = [x.strip() for x in kv.split(":", 1)]
                v = v.strip("'\"")
                try:
                    port["params"][k] = float(v) if "." in v else int(v)
                except ValueError:
                    port["params"][k] = v
        if "label" in port:
            out["ports"].append(port)
    return out


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_/]+", "", str(s)).lower()


def check_drift(class_name: str, ssot: dict, dims_text: str, tol: float = 0.1,
                warnings: list[str] | None = None) -> list[str]:
    """對比 derive 結果 vs 現有 dims.js entry。

    嚴格檢查（issues）：每個 port 的 cx/cy/shape/side 對齊
    寬鬆檢查（warnings）：整體 l/w/h、label 命名差異、color 差異
    Label 對齊使用 normalize（忽略大小寫/連字符/底線/空格）。
    """
    spec = ssot.get(class_name)
    if not spec:
        return [f"[{class_name}] SSOT missing"]
    derived = derive_entry(class_name, spec)
    actual = _parse_dims_entry(dims_text, class_name)
    if not actual:
        return [f"[{class_name}] dims.js entry missing"]

    issues: list[str] = []
    warn = warnings if warnings is not None else []

    # l/w/h 整體尺寸（warning only：physical 是 bbox 估算，允許與 dims.js 微差）
    for key in ("l", "w", "h"):
        dv, av = derived.get(key), actual.get(key)
        if dv is None or av is None:
            continue
        if abs(dv - av) > tol:
            warn.append(f"[{class_name}] {key}: SSOT.physical={dv} vs dims={av} (physical bbox may need review)")

    # P5.6: 重複 label 處理 — 把 derived/actual 各自分組（按 normalized label），
    # 同組多筆時用 greedy 最近鄰（按 (cx,cy) 距離）配對，避免字典覆寫盲點。
    # 例：NeoPixel 8 顆 'WS2812B LED ' 同名子件，舊邏輯只比對 1 筆，新邏輯全 8 筆都比。
    def _group(ports):
        g: dict[str, list[dict]] = {}
        for p in ports:
            g.setdefault(_norm(p["label"]), []).append(p)
        return g

    derived_g = _group(derived["ports"])
    actual_g = _group(actual["ports"])

    def _dist(a, b):
        return ((a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2) ** 0.5

    for norm_lbl, dps in derived_g.items():
        aps = list(actual_g.get(norm_lbl, []))
        if not aps:
            for dp in dps:
                issues.append(f"[{class_name}/{dp['label']}] derived label has no match in dims.js")
            continue
        # Greedy 最近鄰配對：每個 derived 找最近的未配對 actual
        unpaired = list(aps)
        for dp in dps:
            if not unpaired:
                issues.append(f"[{class_name}/{dp['label']}] more derived than actual instances")
                continue
            best = min(unpaired, key=lambda ap: _dist(dp, ap))
            unpaired.remove(best)
            ap = best
            if dp["label"] != ap["label"]:
                warn.append(f"[{class_name}] label rename: SSOT '{dp['label']}' vs dims '{ap['label']}'")
            for key in ("cx", "cy"):
                if abs(dp[key] - ap.get(key, -999)) > tol:
                    issues.append(f"[{class_name}/{dp['label']}] {key}: derive={dp[key]} vs dims={ap.get(key)}")
            if dp.get("shape") != ap.get("shape"):
                issues.append(f"[{class_name}/{dp['label']}] shape: derive={dp.get('shape')!r} vs dims={ap.get('shape')!r}")
            if dp.get("side") != ap.get("side"):
                warn.append(f"[{class_name}/{dp['label']}] side: derive={dp.get('side')!r} vs dims={ap.get('side')!r}")
            if dp.get("color") != ap.get("color"):
                warn.append(f"[{class_name}/{dp['label']}] color: derive={dp.get('color')!r} vs dims={ap.get('color')!r}")

    for norm_lbl, aps in actual_g.items():
        derived_count = len(derived_g.get(norm_lbl, []))
        extra = len(aps) - derived_count
        if derived_count == 0:
            for ap in aps:
                issues.append(f"[{class_name}/{ap['label']}] in dims.js but not derived (missing SSOT entry?)")
        elif extra > 0:
            issues.append(f"[{class_name}/{aps[0]['label']}] dims.js has {len(aps)} instances but SSOT has {derived_count}")

    return issues


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="drift gate mode: exit 1 on mismatch")
    ap.add_argument("--class", dest="cls", help="only process one class")
    ap.add_argument("--tol", type=float, default=0.1)
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    classes = [args.cls] if args.cls else _all_classes_with_hints()

    if args.check:
        dims_text = DIMS_JS.read_text(encoding="utf-8")
        all_issues: list[str] = []
        all_warns: list[str] = []
        for c in classes:
            all_issues.extend(check_drift(c, ssot, dims_text, args.tol, warnings=all_warns))
        if all_warns:
            print(f"[WARN] {len(all_warns)} non-blocking issues (review later):")
            for line in all_warns[:30]:
                print(f"  {line}")
            if len(all_warns) > 30:
                print(f"  ... +{len(all_warns)-30} more")
        if all_issues:
            print(f"[FAIL] derive vs dims.js drift ({len(all_issues)} blocking issues):")
            for line in all_issues:
                print(f"  {line}")
            return 1
        print(f"[OK] derive aligned to dims.js for {len(classes)} classes (tol={args.tol}mm, position-strict)")
        return 0

    # default: emit derived JS to stdout
    for c in classes:
        spec = ssot.get(c)
        if not spec:
            print(f"// SKIP {c} (no SSOT)", file=sys.stderr)
            continue
        entry = derive_entry(c, spec)
        print(fmt_entry_js(c, entry))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
