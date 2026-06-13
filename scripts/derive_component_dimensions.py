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

# Arduino-Uno-class 的 dims.js 區塊由 lib/pcb/layout_export.py 從 EAGLE .brd 真實本體中心
# 權威衍生（SSOT-AUTO-GENERATED marker 段），label/座標來源與 verified.json on_board 慣例
# 不同（如 'NCP1117-5V' vs 'V-Reg-5V'、.brd 中心 vs bbox）。此 deriver 不擁有該 class，
# 否則 --write 會覆蓋 layout_export 段、--check 會誤報雙權威衝突。見 layout_export 模組註解。
_LAYOUT_EXPORT_OWNED = frozenset({"Arduino-Uno-class"})


# 受測元件清單：自動從 verified.json 抓所有有 _ui_hints 的元件
def _all_classes_with_hints() -> list[str]:
    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    return sorted(c for c, v in ssot.items()
                  if "_ui_hints" in v and c not in _LAYOUT_EXPORT_OWNED)


_SOLID_BODY_SHAPES = frozenset({
    "ic-soic", "ic-qfp", "ic-dip", "ic-module",
    "box", "heatsink", "vreg-to220", "display-panel",
    "toggle-switch", "slide-switch",
    "crystal-hc49", "res-smd", "cap-electrolytic",
})


def _is_solid_shape(shape: str) -> bool:
    """True if shape is a single-instance solid body (not a header/hole/region/wire).
    Two solid bodies sharing one coordinate ⇒ same physical part drawn twice."""
    return shape in _SOLID_BODY_SHAPES


def _norm_label(s) -> str:
    """正規化 sub-component label 以比對 stale extra_ports：底線/連字號→空白、小寫、
    壓縮空白。截斷比對（前綴）在呼叫端另加座標重合確認。"""
    s = str(s).strip().lower().replace("_", " ").replace("-", " ").replace("/", " ")
    return re.sub(r"\s+", " ", s).strip()


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
    # VS-DEDUP（2026-06-06）：extra_ports label 若與 on_board_components label 撞名 → 跳過。
    # datasheet on_board_components 永遠勝;防 stale extra_ports 以舊手設座標蓋過 datasheet
    # bbox 位置造成 render drift（曾致 34 個子元件最大 40mm 偏移）。預防測試見
    # tests/test_no_stale_extra_ports.py。
    #
    # VS-DEDUP-2（2026-06-07，ic-subcomponent-overlap）：舊 guard 只比 label 精確相等，
    # 漏掉「同一實體子元件被 extra_ports 用 mangled label 再定義一次」的 stale entry——
    # mangling = 底線→空白、大小寫變動、12 字截斷（如 'ASIC_IC'→'ASIC IC'、
    # 'WS2812B_LED_2'→'WS2812B LED '、'Crystal-16MHz'→'Crystal-16MH'），或同義改名+座標漂移
    # （如 'L298N'→'L298N-IC'、'SPDT Toggle'→'SLIDE-SW'、'HLK-PM01'→'TRANSFORMER'）。這些
    # 重複 port 造成兩個本體疊在一起（IC port overlap 紅）。
    #
    # 判 stale（datasheet on_board 永遠勝）採三訊號，任一成立即跳過：
    #   (1) 正規化 label 相等；
    #   (2) 正規化 label 一方為另一方前綴（≥8 字）；
    #   (3) 正規化 token 一方為另一方子集（如 'sensitivity' ⊂ 'sensitivity trimpot'）；
    #   (4) 同槽位重合：兩者皆 solid（非 header / 非 mounting-hole）shape 且座標 ≤1.5mm 重疊
    #       —— 兩個實體本體不可能合法佔同一座標，必為同一零件重畫。
    # 不採「跨命名 + 漂移座標」的模糊匹配（避免誤刪合法相異零件如 4 個 Wheel、Sensing Grid）。
    _obc_rendered = [p for p in ports]  # 已含 on_board_components 衍生 port（帶 cx/cy）

    def _is_stale_extra(extra: dict) -> bool:
        ne = _norm_label(extra.get("label"))
        te = {t for t in ne.split() if len(t) >= 2}
        ex, ey = extra.get("cx"), extra.get("cy")
        e_solid = _is_solid_shape(extra.get("shape", ""))
        for p in _obc_rendered:
            npp = _norm_label(p["label"])
            if ne == npp:
                return True
            if len(ne) >= 8 and len(npp) >= 8 and (ne.startswith(npp) or npp.startswith(ne)):
                return True
            tp = {t for t in npp.split() if len(t) >= 2}
            if te and tp and (te <= tp or tp <= te):
                return True
            if (e_solid and _is_solid_shape(p.get("shape", ""))
                    and ex is not None and ey is not None
                    and abs(ex - p["cx"]) <= 1.5 and abs(ey - p["cy"]) <= 1.5):
                return True
        return False

    for extra in ui.get("extra_ports", []):
        if _is_stale_extra(extra):
            continue  # datasheet on_board_components 已涵蓋此實體子元件，extra_ports 為 stale
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
            # P6.3/no-silent-fallback(a):pin 座標是 SSOT 真值,缺值不得以 0 頂替
            # (會把質心拉向原點,假幾何流進 Gate-1 衍生)→ 直接索引,缺鍵 KeyError fail-loud。
            cx = sum(p["x_mm"] for p in pins) / len(pins)
            cy = sum(p["y_mm"] for p in pins) / len(pins)
            info = shape_map.get(name, {})
            # pitch：明示 pitch_mm 優先；否則從真實 pin 座標推導（SSOT，不漂移）；
            # 皆不可得才 raise（VS-PCB：禁以 2.54 頂替非標準連接器）。
            pitch = hg.get("pitch_mm")
            if pitch is None:
                # 同上:pitch 推導餵假 0 會放大 span → 推錯 pitch;缺鍵 fail-loud。
                _pxs = [p["x_mm"] for p in pins]
                _pys = [p["y_mm"] for p in pins]
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
    ap.add_argument("--write", action="store_true",
                    help="in-place rewrite each hinted class block in dims.js from SSOT")
    ap.add_argument("--class", dest="cls", help="only process one class")
    ap.add_argument("--tol", type=float, default=0.1)
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    classes = [args.cls] if args.cls else _all_classes_with_hints()

    if args.write:
        # newline="" 保留檔案原生行尾（dims.js 為 LF）；避免 Windows 預設把 LF→CRLF 造成全檔 churn。
        with open(DIMS_JS, "r", encoding="utf-8", newline="") as _f:
            dims_text = _f.read()
        changed = 0
        missing: list[str] = []
        for c in classes:
            spec = ssot.get(c)
            if not spec:
                continue
            old_block = _extract_dims_entry(dims_text, c)
            if old_block is None:
                missing.append(c)
                continue
            new_block = fmt_entry_js(c, derive_entry(c, spec))
            if "\r\n" in dims_text:
                new_block = new_block.replace("\n", "\r\n")  # 對齊原生 CRLF（若有）
            if old_block != new_block:
                dims_text = dims_text.replace(old_block, new_block, 1)
                changed += 1
        with open(DIMS_JS, "w", encoding="utf-8", newline="") as _f:
            _f.write(dims_text)
        if missing:
            print(f"[WARN] {len(missing)} hinted classes not found in dims.js: {missing}")
        print(f"[OK] dims.js rewritten: {changed} class block(s) updated from SSOT")
        return 0

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
