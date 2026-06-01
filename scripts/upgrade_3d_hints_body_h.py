"""upgrade_3d_hints_body_h.py — 把 verified.json `_3d_hints.sub_components_3d` 內
default `body_h_mm=5.0` 升級成依 type/shape 推斷的標準高度。

用法：
  .venv/Scripts/python.exe scripts/upgrade_3d_hints_body_h.py [--apply]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"

# 標準封裝高度（mm）— 工業常見值
# 對應 on_board_components.type / .shape / label 關鍵字
HEIGHT_RULES = [
    # (priority, predicate(sub) -> bool, body_h_mm, comment)
    ("ic-module",   lambda s: (s.get("shape") == "ic-module") or "esp32" in s.get("label","").lower() and "wroom" in s.get("label","").lower(), 3.5, "ESP32-WROOM 模組（PCB+金屬罩）"),
    ("crystal",     lambda s: s.get("shape") in ("crystal-hc49",) or "crystal" in s.get("label","").lower(), 4.5, "HC-49 晶振"),
    ("relay",       lambda s: s.get("shape") == "relay" or "relay" in s.get("label","").lower() or "srd-" in s.get("label","").lower(), 15.5, "繼電器本體"),
    ("usb-b",       lambda s: s.get("shape") in ("conn-usb-b","conn-usb-a") or "usb-b" in s.get("label","").lower(), 13.0, "USB-B socket"),
    ("usb-c",       lambda s: s.get("shape") == "conn-usb-c" or "usb-c" in s.get("label","").lower(), 3.5, "USB-C socket"),
    ("usb-micro",   lambda s: s.get("shape") == "conn-usb-micro" or "micro-usb" in s.get("label","").lower() or "micro_usb" in s.get("label","").lower(), 2.9, "USB Micro-B socket"),
    ("barrel-jack", lambda s: s.get("shape") == "conn-barrel-jack" or "barrel" in s.get("label","").lower() or "dc-jack" in s.get("label","").lower(), 11.0, "DC barrel jack"),
    ("screw-term",  lambda s: s.get("shape") == "conn-screw-terminal" or "screw" in s.get("label","").lower(), 10.0, "screw terminal block"),
    ("button-tact", lambda s: s.get("shape") == "button-tactile" or "btn" in s.get("label","").lower() or "button" in s.get("label","").lower() or "reset" in s.get("label","").lower(), 4.3, "tactile push button"),
    ("pot-trim",    lambda s: s.get("shape") == "pot-trimmer" or "trimpot" in s.get("label","").lower() or "trimmer" in s.get("label","").lower() or "sensitivity" in s.get("label","").lower(), 4.5, "trim potentiometer"),
    ("pot-shaft",   lambda s: s.get("shape") == "pot-shaft" or "potentiometer" in s.get("label","").lower(), 15.0, "shaft potentiometer (含旋鈕)"),
    ("ic-dip",      lambda s: s.get("shape") == "ic-dip" or "dip" in s.get("label","").lower() or "atmega" in s.get("label","").lower() or "uln2003" in s.get("label","").lower(), 4.0, "DIP IC (DIP-8/16/28)"),
    ("ic-qfp",      lambda s: s.get("shape") == "ic-qfp" or "qfp" in s.get("label","").lower(), 1.6, "QFP IC"),
    ("ic-soic",     lambda s: s.get("shape") == "ic-soic" or s.get("type") == "ic" or "lm393" in s.get("label","").lower() or "tlc555" in s.get("label","").lower() or "cp210" in s.get("label","").lower() or "ams1117" in s.get("label","").lower() or "ne555" in s.get("label","").lower(), 1.75, "SOIC IC"),
    ("electrolytic",lambda s: s.get("shape") == "cap-electrolytic" or "electro" in s.get("label","").lower(), 12.0, "電解電容"),
    ("cap-ceramic", lambda s: s.get("shape") == "cap-ceramic" or "ceramic" in s.get("label","").lower(), 1.0, "陶瓷電容 0805"),
    ("res-smd",     lambda s: s.get("shape") == "res-smd" or "resistor" in s.get("label","").lower(), 0.5, "SMD 電阻 0805"),
    ("led-tht",     lambda s: s.get("shape") == "led-tht" or ("led" in s.get("label","").lower() and s.get("type") == "indicator" and s.get("w_mm",0) >= 4), 5.0, "5mm THT LED"),
    ("led-smd",     lambda s: s.get("shape") == "led-smd" or ("led" in s.get("label","").lower()), 1.0, "SMD LED 0805"),
    ("buzzer",      lambda s: s.get("shape") == "buzzer" or "buzzer" in s.get("label","").lower() or "speaker" in s.get("label","").lower(), 9.0, "buzzer 12mm"),
    ("motor-dc",    lambda s: s.get("shape") == "motor-dc" or "motor" in s.get("label","").lower(), 25.0, "DC 馬達"),
    ("motor-servo", lambda s: s.get("shape") == "motor-servo" or "servo" in s.get("label","").lower(), 22.7, "SG90 servo"),
    ("sensor-dome", lambda s: s.get("shape") == "sensor-dome" or "dome" in s.get("label","").lower() or "ir-receiver" in s.get("label","").lower(), 5.0, "圓頂感測（IR/PIR）"),
    ("header-male", lambda s: s.get("shape") in ("conn-header-male","conn-header-female") or s.get("type") == "connector" or "header" in s.get("label","").lower() or "hdr" in s.get("label","").lower() or "pin" in s.get("label","").lower(), 2.54, "排針/排母 housing"),
    ("mounting",    lambda s: s.get("shape") == "mounting-hole" or "mount" in s.get("label","").lower() or s.get("type") == "feature", 0.1, "安裝孔（平面 marker）"),
    ("copper",      lambda s: "copper" in s.get("label","").lower() or "trace" in s.get("label","").lower() or "antenna" in s.get("label","").lower(), 0.05, "PCB 銅箔/天線 trace"),
    ("battery",     lambda s: "battery" in s.get("label","").lower() or "holder" in s.get("label","").lower(), 14.0, "電池盒 / battery holder"),
    ("ldr",         lambda s: "ldr" in s.get("label","").lower() or "photo" in s.get("label","").lower() or "gl552" in s.get("label","").lower(), 2.0, "光敏電阻"),
]


def infer_body_h(sub: dict, on_board_entry: dict | None) -> tuple[float, str] | None:
    """合併 on_board_components 的 type/shape/label 與 _3d_hints 的 label 推斷高度。"""
    merged = {**(on_board_entry or {}), **sub}
    label = (merged.get("label") or merged.get("name") or "").lower()
    merged["label"] = label
    for rule_id, pred, h, comment in HEIGHT_RULES:
        if pred(merged):
            return h, f"{rule_id}: {comment}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    upgrades = []
    skipped = []

    for cls, spec in ssot.items():
        hints = spec.get("_3d_hints", {}).get("sub_components_3d", [])
        if not hints:
            continue
        # 建 on_board lookup
        on_board = {}
        for sub in spec.get("on_board_components", []):
            lbl = sub.get("label") or sub.get("name")
            if lbl:
                on_board[lbl] = sub
        for h_sub in hints:
            current = h_sub.get("body_h_mm")
            if current != 5.0:
                continue  # 已有自訂值，跳過
            lbl = h_sub.get("label")
            on_board_entry = on_board.get(lbl)
            inferred = infer_body_h(h_sub, on_board_entry)
            if inferred is None:
                skipped.append((cls, lbl, "no rule matched"))
                continue
            new_h, reason = inferred
            if abs(new_h - 5.0) < 0.01:
                continue  # default 巧合等於 5.0
            upgrades.append((cls, lbl, new_h, reason))
            if args.apply:
                h_sub["body_h_mm"] = new_h

    print(f"[propose] upgrades: {len(upgrades)} / skipped: {len(skipped)}")
    if not args.apply:
        for cls, lbl, h, r in upgrades[:30]:
            print(f"  {cls}/{lbl}: 5.0 -> {h} ({r})")
        if len(upgrades) > 30:
            print(f"  ... +{len(upgrades)-30} more")
        if skipped:
            print(f"\n[skipped] {len(skipped)} entries (no rule):")
            for cls, lbl, _ in skipped[:15]:
                print(f"  {cls}/{lbl}")
        print("\nrun with --apply to write back to verified.json")
        return 0

    SSOT_JSON.write_text(json.dumps(ssot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[OK] wrote {len(upgrades)} body_h_mm upgrades to {SSOT_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
