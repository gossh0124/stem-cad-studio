"""migrate_dims_to_ui_hints.py — 把 v6/data/component-dimensions.js entries 遷移成 verified.json _ui_hints

Phase 3D 批次遷移工具：對於 verified.json 已有的元件，從 dims.js 抽取
shape/color/params/side，產生 `_3d_hints` + `_ui_hints` JSON 片段。

匹配邏輯：
  - dims.js port 的 label 若能匹配 SSOT on_board_components.label（normalize 後）
    且 (cx, cy) 與 SSOT (x_mm+w/2, y_mm+h/2) 差 <= tol → 用 frontend_shape
  - 否則 → extra_ports（保留 dims.js 現狀，drift=0）

用法：
  # 為單一 class 產生 hints 片段
  .venv/Scripts/python.exe scripts/migrate_dims_to_ui_hints.py --class ESP32-class

  # 為所有 pending 元件產生（stdout 全部）
  .venv/Scripts/python.exe scripts/migrate_dims_to_ui_hints.py --all

  # 直接寫入 verified.json（in-place merge）
  .venv/Scripts/python.exe scripts/migrate_dims_to_ui_hints.py --all --apply
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
TOL_MM = 0.5  # 匹配容忍度（migrate 階段較寬鬆，後續 phase 可再收緊）


def _norm_label(s: str) -> str:
    return re.sub(r"[\s\-_/]+", "", s).lower()


def _parse_dims_entry(js_text: str, class_name: str) -> dict | None:
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
    # parse each line that looks like a port literal
    for raw_line in body.split("\n"):
        s = raw_line.strip().rstrip(",")
        if not s.startswith("{"):
            continue
        port = {}
        for key in ("cx", "cy"):
            mm = re.search(rf"\b{key}\s*:\s*(-?[\d.]+)", s)
            if mm:
                port[key] = float(mm.group(1))
        for key in ("side", "shape", "label", "color"):
            mm = re.search(rf"\b{key}\s*:\s*'([^']+)'", s)
            if mm:
                port[key] = mm.group(1)
        # rot (optional)
        rm = re.search(r"\brot\s*:\s*(-?[\d.]+)", s)
        if rm:
            port["rot"] = float(rm.group(1))
        # params block
        pm = re.search(r"params\s*:\s*\{([^}]*)\}", s)
        params = {}
        if pm:
            for kv in pm.group(1).split(","):
                kv = kv.strip()
                if not kv or ":" not in kv:
                    continue
                k, v = [x.strip() for x in kv.split(":", 1)]
                v = v.strip("'\"")
                try:
                    params[k] = float(v) if "." in v else int(v)
                except ValueError:
                    params[k] = v
        port["params"] = params
        if "label" in port:
            out["ports"].append(port)
    return out


def derive_ui_hints(class_name: str, ssot_spec: dict, dims_entry: dict) -> dict:
    """產生 _ui_hints 片段（frontend_shape + extra_ports）。"""
    sub_by_norm = {}
    for s in ssot_spec.get("on_board_components", []):
        lbl = s.get("label") or s.get("name") or ""
        if lbl:
            sub_by_norm[_norm_label(lbl)] = s
            s.setdefault("label", lbl)  # 統一接口
    frontend_shape: dict[str, dict] = {}
    extra_ports: list[dict] = []
    used_sub_labels: set[str] = set()

    for port in dims_entry["ports"]:
        label = port["label"]
        norm = _norm_label(label)
        sub = sub_by_norm.get(norm)
        # 對齊條件：SSOT 有同名 sub + cx/cy 在容忍範圍內
        if sub:
            ssot_cx = sub["x_mm"] + sub["w_mm"] / 2
            ssot_cy = sub["y_mm"] + sub["h_mm"] / 2
            if abs(port.get("cx", 0) - ssot_cx) <= TOL_MM and abs(port.get("cy", 0) - ssot_cy) <= TOL_MM:
                # 用 frontend_shape 路徑（label 需用 SSOT 真值，dims.js 之後可同步改）
                extra_params = {k: v for k, v in port.get("params", {}).items()
                                if k not in ("bodyW", "bodyD")}  # bodyW/D 由 SSOT 衍生
                entry = {"shape": port["shape"], "color": port["color"], "side": port.get("side", "face")}
                if extra_params:
                    entry["extra_params"] = extra_params
                frontend_shape[sub["label"]] = entry
                used_sub_labels.add(sub["label"])
                continue
        # 否則：當 extra_port 保留
        extra = {
            "label": label,
            "side": port.get("side", "face"),
            "cx": port["cx"],
            "cy": port["cy"],
            "shape": port["shape"],
            "color": port["color"],
        }
        if port.get("params"):
            extra["extra_params"] = port["params"]
        if "rot" in port:
            extra["rot"] = port["rot"]
        extra_ports.append(extra)

    # tags / enclosure_relation 留待手動或從 registry 補（本工具不假設）
    ui: dict = {}
    if frontend_shape:
        ui["frontend_shape"] = frontend_shape
    if extra_ports:
        ui["extra_ports"] = extra_ports
    return ui


def derive_3d_hints(ssot_spec: dict) -> dict:
    """產生最小 _3d_hints — 每個 sub 補 body_h_mm 預設 5（後續可由 modules.py 自訂值上拉）。"""
    subs = []
    for sub in ssot_spec.get("on_board_components", []):
        lbl = sub.get("label") or sub.get("name")
        if not lbl:
            continue
        subs.append({"label": lbl, "body_h_mm": 5.0})
    return {"sub_components_3d": subs} if subs else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--class", dest="cls")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true", help="write back to verified.json")
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    dims_text = DIMS_JS.read_text(encoding="utf-8")

    if args.cls:
        classes = [args.cls]
    elif args.all:
        # 找出 SSOT ∩ dims.js 且尚未有 _ui_hints 的元件
        in_dims = set(re.findall(r'"([A-Z][A-Za-z0-9-]+-class)":\s*\{', dims_text))
        classes = sorted(c for c in ssot if c in in_dims and "_ui_hints" not in ssot[c])
    else:
        print("Use --class <name> or --all", file=sys.stderr)
        return 2

    changes = {}
    for cls in classes:
        if cls not in ssot:
            print(f"// SKIP {cls} (no SSOT)", file=sys.stderr)
            continue
        entry = _parse_dims_entry(dims_text, cls)
        if not entry:
            print(f"// SKIP {cls} (no dims.js entry)", file=sys.stderr)
            continue
        ui = derive_ui_hints(cls, ssot[cls], entry)
        hints3d = derive_3d_hints(ssot[cls])
        snippet = {}
        if hints3d:
            snippet["_3d_hints"] = hints3d
        if ui:
            snippet["_ui_hints"] = ui
        changes[cls] = snippet
        if not args.apply:
            print(f"// === {cls} ===")
            print(json.dumps(snippet, indent=2, ensure_ascii=False))
            print()

    if args.apply:
        for cls, snippet in changes.items():
            ssot[cls].setdefault("_3d_hints", snippet.get("_3d_hints", {"sub_components_3d": []}))
            if "_3d_hints" in snippet and not ssot[cls]["_3d_hints"].get("sub_components_3d"):
                ssot[cls]["_3d_hints"] = snippet["_3d_hints"]
            if "_ui_hints" in snippet:
                ssot[cls]["_ui_hints"] = snippet["_ui_hints"]
        SSOT_JSON.write_text(json.dumps(ssot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"[OK] wrote _3d_hints/_ui_hints for {len(changes)} classes to {SSOT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
