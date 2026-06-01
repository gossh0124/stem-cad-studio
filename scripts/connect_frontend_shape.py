"""connect_frontend_shape.py — 把 verified.json 內 extra_ports 條目搬到 frontend_shape

P1.1 SSOT 接通：22 個 class 的 _ui_hints.frontend_shape 是空的，所有 ports 走 extra_ports。
本腳本對 on_board_components 與 extra_ports label 比對（normalize 容忍），位置對齊
(tol=0.5mm) 時把該 extra_port 搬到 frontend_shape，並刪掉 extra_ports 該條目。

用法：
  .venv/Scripts/python.exe scripts/connect_frontend_shape.py [--apply] [--class X]
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"
TOL_MM = 0.5


def _norm(s: str) -> str:
    return re.sub(r"[\s\-_/]+", "", str(s)).lower()


def migrate_class(cls_name: str, spec: dict) -> tuple[list[tuple], list[tuple]]:
    """回傳 (migrated, mismatched) 列表."""
    on_board = spec.get("on_board_components", [])
    ui = spec.get("_ui_hints", {})
    extras = ui.get("extra_ports", [])
    if not on_board or not extras:
        return [], []

    # on_board normalize lookup
    on_board_idx = {}
    for sub in on_board:
        lbl = sub.get("label") or sub.get("name")
        if lbl:
            on_board_idx[_norm(lbl)] = sub

    migrated: list[tuple] = []
    mismatched: list[tuple] = []
    remaining: list[dict] = []
    new_fs: dict = {}

    for ep in extras:
        ep_label = ep.get("label", "")
        ep_norm = _norm(ep_label)
        sub = on_board_idx.get(ep_norm)
        if not sub:
            remaining.append(ep)
            continue
        # 計算 on_board center
        sub_cx = sub["x_mm"] + sub["w_mm"] / 2
        sub_cy = sub["y_mm"] + sub["h_mm"] / 2
        if abs(ep.get("cx", 0) - sub_cx) <= TOL_MM and abs(ep.get("cy", 0) - sub_cy) <= TOL_MM:
            # 可遷：用 SSOT label（on_board 的 label/name）為 frontend_shape key
            ssot_label = sub.get("label") or sub.get("name")
            entry: dict = {
                "shape": ep.get("shape"),
                "color": ep.get("color", "#888"),
                "side": ep.get("side", "face"),
            }
            extra_params = {k: v for k, v in (ep.get("extra_params", {}) or {}).items()
                            if k not in ("bodyW", "bodyD")}  # bodyW/D 由 on_board 衍生
            if extra_params:
                entry["extra_params"] = extra_params
            new_fs[ssot_label] = entry
            migrated.append((cls_name, ssot_label, ep_label, sub_cx, sub_cy))
        else:
            mismatched.append((cls_name, ep_label, ssot_label := (sub.get("label") or sub.get("name")),
                               ep.get("cx"), ep.get("cy"), sub_cx, sub_cy))
            remaining.append(ep)

    if not new_fs:
        return migrated, mismatched

    # 套用：合併到 frontend_shape；ui.extra_ports 替換成 remaining
    fs = ui.setdefault("frontend_shape", {})
    fs.update(new_fs)
    ui["extra_ports"] = remaining
    return migrated, mismatched


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--class", dest="cls")
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    classes = [args.cls] if args.cls else list(ssot.keys())

    all_migrated: list[tuple] = []
    all_mismatched: list[tuple] = []

    for cls in classes:
        spec = ssot.get(cls)
        if not spec:
            continue
        ui = spec.get("_ui_hints", {})
        # 只處理 frontend_shape 空 + 有 on_board 的
        if not ui or ui.get("frontend_shape"):
            continue
        m, mm = migrate_class(cls, spec)
        all_migrated.extend(m)
        all_mismatched.extend(mm)

    print(f"[propose] migrate {len(all_migrated)} extra_ports → frontend_shape")
    print(f"[skip] {len(all_mismatched)} mismatched (label matches but position drift)")
    if not args.apply:
        for cls, ssot_lbl, ep_lbl, cx, cy in all_migrated[:25]:
            print(f"  + {cls}: '{ep_lbl}' → frontend_shape['{ssot_lbl}'] @ ({cx:.2f}, {cy:.2f})")
        if len(all_migrated) > 25:
            print(f"  ... +{len(all_migrated)-25} more")
        for cls, ep, ssot_lbl, cx, cy, scx, scy in all_mismatched[:10]:
            print(f"  - {cls}: '{ep}' vs SSOT '{ssot_lbl}': extra ({cx},{cy}) vs on_board ({scx:.2f},{scy:.2f})")
        if len(all_mismatched) > 10:
            print(f"  ... +{len(all_mismatched)-10} mismatched")
        print("\nrun with --apply to write back")
        return 0

    SSOT_JSON.write_text(json.dumps(ssot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] migrated {len(all_migrated)} entries to frontend_shape in {SSOT_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
