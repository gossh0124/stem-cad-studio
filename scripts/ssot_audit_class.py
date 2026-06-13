"""ssot_audit_class.py — SSOT3/4 人工審計 CLI（resumable，逐 class 走查）

設計目標：上次 Wave 1 agent 因無 WebFetch、退化為文字推測（違背架構性區分原則）
被擋。本工具不替使用者仲裁，只負責：
  (1) 列出待審 class + 當前狀態 + datasheet URL
  (2) 顯示單一 class 的 pin_layout / extra_ports / on_board / 已記錄 verdict
  (3) 接受使用者基於 datasheet 機械圖判定後輸入 verdict / 修正值
  (4) 自動 backup + patch verified.json + 跑 drift gate + append audit log

不引入 WebFetch / 不自動推測。

用法：
  .venv/Scripts/python.exe scripts/ssot_audit_class.py --list
  .venv/Scripts/python.exe scripts/ssot_audit_class.py --show Arduino-Uno-class
  .venv/Scripts/python.exe scripts/ssot_audit_class.py --record Sensor-Light-class --verdict both_ok --notes "panel-mount offset 合理"
  .venv/Scripts/python.exe scripts/ssot_audit_class.py --patch-extra Mist-Atomizer-class INPUT --cx 2.75 --cy 0.5 --notes "datasheet p.3 pin 在底邊"

verdict 值：
  both_ok          — pin/extra 兩者都對，為架構性區分（pad vs housing 合理偏移），無需修
  pin_fixed        — 已透過 --patch-pin 修 pin_layout
  extra_fixed      — 已透過 --patch-extra 修 extra_ports
  needs_datasheet  — 仍找不到可信機械圖，待後續

audit log: data/ssot_audit_log.jsonl
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"
AUDIT_LOG = ROOT / "data" / "ssot_audit_log.jsonl"
DRIFT_GATE = ROOT / "scripts" / "derive_component_dimensions.py"

VALID_VERDICTS = {"both_ok", "pin_fixed", "extra_fixed", "physical_fixed", "needs_datasheet"}

# patch-physical 寫入的欄位級 provenance block（頂層 _-key；lib/specs.py 與 drift gate
# 皆跳過 _-prefixed top-level key，故與既有 reader 隔離，不影響 specs cache / drift）。
PHYS_AUDIT_KEY = "_ssot_physical_audit"

# patch-physical 安全子集白名單：只准動純量 physical 尺寸 + 連接器 pitch。
# 結構性欄位（pin 數、pin/孔座標、header 重排）一律拒絕——見 work/active/
# 「StemAiAgentV3 session 收尾 2026-06-12」鐵則：不手填座標、pin/pitch 結構性改動留結構批次。
_ALLOWED_PHYS_LEAVES = {"length_mm", "width_mm", "height_mm", "pcb_thickness_mm", "weight_g"}
_PITCH_PATH_RE = re.compile(r"^pin_layout\.header_groups\[\d+\]\.pitch_mm$")
_SEG_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?$")

# 來源：docs/ssot_pin_layout_vs_extra_ports.md §B（24 DRIFT class）+ §G（22 frontend_shape 空 class，部分重疊）
PENDING_CLASSES = [
    # Batch 1: MCU 主板 + 顯示
    "Arduino-Uno-class", "ESP32-class", "Microbit-class", "RaspberryPi-class",
    "Display-OLED-class", "Display-LCD-class",
    # Batch 2: 感測器
    "Sensor-TempHumid-class", "Sensor-Ultrasonic-class", "Sensor-PIR-class",
    "Sensor-Light-class", "Sensor-IR-class", "Sensor-MSGEQ7-class",
    # Batch 3: 顯示 + 致動器
    "Display-EInk-class", "LED-Matrix-class", "Speaker-class",
    "Motor-DC-class", "L298N-Driver-class", "USB-5V-class",
    # Batch 4: 照明 + 控制
    "Lighting-LED-RGB-class", "Lighting-LED-PWM-class", "Lighting-LED-Strip-class",
    "Lighting-NeoPixel-class", "Mist-Atomizer-class", "Mist-Ultrasonic-class",
    "Potentiometer-class", "Joystick-class", "Buzzer-Passive-class",
]


def _load_ssot() -> dict:
    return json.loads(SSOT_JSON.read_text(encoding="utf-8"))


def _load_audit_log() -> list[dict]:
    if not AUDIT_LOG.exists():
        return []
    return [json.loads(line) for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def _current_verdict(cls: str, log: list[dict]) -> dict | None:
    """回傳該 class 最新一筆 log entry（若有）。"""
    for entry in reversed(log):
        if entry.get("class") == cls:
            return entry
    return None


def _append_log(entry: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry.setdefault("ts", _dt.datetime.now().isoformat(timespec="seconds"))
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _backup_ssot() -> Path:
    bak = SSOT_JSON.with_suffix(".json.bak")
    shutil.copy2(SSOT_JSON, bak)
    return bak


def _write_ssot(data: dict) -> None:
    SSOT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run_drift_gate() -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(DRIFT_GATE), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def _datasheet_urls(spec: dict) -> list[str]:
    urls = []
    for s in spec.get("sources", []) or []:
        u = s.get("url")
        if u:
            urls.append(u)
    return urls


def cmd_list(log: list[dict]) -> int:
    print(f"=== SSOT3/4 審計進度（共 {len(PENDING_CLASSES)} class）===\n")
    counts = {v: 0 for v in VALID_VERDICTS}
    counts["unaudited"] = 0
    for cls in PENDING_CLASSES:
        entry = _current_verdict(cls, log)
        if entry is None:
            v = "unaudited"
        else:
            v = entry.get("verdict", "unaudited")
        counts[v] = counts.get(v, 0) + 1
        marker = {
            "both_ok": "[OK]      ",
            "pin_fixed": "[PIN-FIX] ",
            "extra_fixed": "[EXT-FIX] ",
            "physical_fixed": "[PHY-FIX] ",
            "needs_datasheet": "[NEED-DS] ",
            "unaudited": "[ . ]     ",
        }.get(v, "[ ? ]     ")
        note = f"  — {entry.get('notes','')}" if entry and entry.get("notes") else ""
        print(f"  {marker}{cls}{note}")
    print("\n統計：")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\n下一個 unaudited → `--show <class>` 開始審計")
    return 0


def cmd_show(cls: str, ssot: dict, log: list[dict]) -> int:
    spec = ssot.get(cls)
    if not spec:
        print(f"[ERROR] class '{cls}' 不存在於 verified.json")
        return 2
    print(f"=== {cls} ===\n")
    phys = spec.get("physical", {})
    print(f"PCB 尺寸: l={phys.get('length_mm')}, w={phys.get('width_mm')}, h={phys.get('height_mm')}")
    urls = _datasheet_urls(spec)
    if urls:
        print(f"\nDatasheet 來源：")
        for u in urls:
            print(f"  - {u}")
    else:
        print(f"\nDatasheet 來源：（無 sources.url，需另尋）")

    print("\n--- pin_layout.header_groups ---")
    for hg in spec.get("pin_layout", {}).get("header_groups", []) or []:
        name = hg.get("name", "?")
        side = hg.get("side", "?")
        pin_count = hg.get("pin_count", "?")
        pitch = hg.get("pitch_mm", "?")  # nofallback-ok: 審計 CLI 顯示用佔位，不進入計算或寫回
        pins = hg.get("pins", [])
        if pins:
            cx = sum(p.get("x_mm", 0) for p in pins) / len(pins)  # nofallback-ok: 審計 CLI 顯示用質心,不進入計算或寫回
            cy = sum(p.get("y_mm", 0) for p in pins) / len(pins)  # nofallback-ok: 審計 CLI 顯示用質心,不進入計算或寫回
            print(f"  [{name}] side={side} pins={pin_count} pitch={pitch} center=({cx:.2f}, {cy:.2f})")
        else:
            print(f"  [{name}] side={side} pins={pin_count} (pins 未列)")

    print("\n--- _ui_hints.extra_ports ---")
    for ep in spec.get("_ui_hints", {}).get("extra_ports", []) or []:
        print(f"  [{ep.get('label','?')}] side={ep.get('side','?')} cx={ep.get('cx')} cy={ep.get('cy')} shape={ep.get('shape')}")

    print("\n--- on_board_components（前 5 筆）---")
    for sub in (spec.get("on_board_components", []) or [])[:5]:
        cx = sub.get("x_mm", 0) + sub.get("w_mm", 0) / 2  # nofallback-ok: 審計 CLI 顯示用,不進入計算或寫回
        cy = sub.get("y_mm", 0) + sub.get("h_mm", 0) / 2  # nofallback-ok: 審計 CLI 顯示用,不進入計算或寫回
        print(f"  [{sub.get('label','?')}] center=({cx:.2f}, {cy:.2f}) shape={sub.get('shape')}")

    entry = _current_verdict(cls, log)
    if entry:
        print(f"\n--- 已有 audit log ---")
        print(json.dumps(entry, ensure_ascii=False, indent=2))
    else:
        print("\n（尚未審計）")
    print("\n下一步：")
    print(f"  --record {cls} --verdict both_ok|needs_datasheet --notes '...'")
    print(f"  --patch-extra {cls} <LABEL> --cx N --cy M --notes '...'")
    print(f"  --patch-pin   {cls} <GROUP_NAME> <PIN_NUM> --x N --y M --notes '...'")
    return 0


def cmd_record(cls: str, verdict: str, notes: str, ssot: dict) -> int:
    if cls not in ssot:
        print(f"[ERROR] class '{cls}' 不存在")
        return 2
    if verdict not in VALID_VERDICTS:
        print(f"[ERROR] verdict 必須為 {sorted(VALID_VERDICTS)}")
        return 2
    _append_log({"class": cls, "verdict": verdict, "notes": notes, "action": "record"})
    print(f"[OK] recorded: {cls} verdict={verdict}")
    return 0


def cmd_patch_extra(cls: str, label: str, cx: float | None, cy: float | None,
                    notes: str, ssot: dict) -> int:
    spec = ssot.get(cls)
    if not spec:
        print(f"[ERROR] class '{cls}' 不存在")
        return 2
    extras = spec.setdefault("_ui_hints", {}).setdefault("extra_ports", [])
    target = next((ep for ep in extras if ep.get("label") == label), None)
    if not target:
        print(f"[ERROR] class '{cls}' 沒有 extra_ports.label='{label}'")
        return 2
    before = {"cx": target.get("cx"), "cy": target.get("cy")}
    if cx is not None:
        target["cx"] = cx
    if cy is not None:
        target["cy"] = cy
    after = {"cx": target.get("cx"), "cy": target.get("cy")}
    bak = _backup_ssot()
    _write_ssot(ssot)
    rc, out = _run_drift_gate()
    _append_log({
        "class": cls, "verdict": "extra_fixed", "action": "patch-extra",
        "label": label, "before": before, "after": after,
        "notes": notes, "drift_gate_rc": rc,
    })
    print(f"[patch] {cls} extra_ports['{label}']: {before} → {after}")
    print(f"[backup] {bak}")
    print(f"[drift gate] rc={rc}\n{out}")
    if rc != 0:
        # drift gate FAIL → 已寫入的 SSOT 違反 drift，回滾至 patch 前的 .bak，
        # 絕不把 gate-failing 的 SSOT 留在磁碟上（No-Silent-Fallback）
        shutil.copy2(bak, SSOT_JSON)
        print(f"[rollback] drift gate 失敗，已從備份還原 SSOT：{bak} → {SSOT_JSON}")
        return 1
    return 0


def cmd_patch_pin(cls: str, group: str, pin_num: int, x: float | None, y: float | None,
                  notes: str, ssot: dict) -> int:
    spec = ssot.get(cls)
    if not spec:
        print(f"[ERROR] class '{cls}' 不存在")
        return 2
    hg = next((g for g in spec.get("pin_layout", {}).get("header_groups", []) if g.get("name") == group), None)
    if not hg:
        print(f"[ERROR] class '{cls}' 沒有 pin_layout.header_groups.name='{group}'")
        return 2
    pin = next((p for p in hg.get("pins", []) if p.get("num") == pin_num), None)
    if not pin:
        print(f"[ERROR] group '{group}' 沒有 pin num={pin_num}")
        return 2
    before = {"x_mm": pin.get("x_mm"), "y_mm": pin.get("y_mm")}
    if x is not None:
        pin["x_mm"] = x
    if y is not None:
        pin["y_mm"] = y
    after = {"x_mm": pin.get("x_mm"), "y_mm": pin.get("y_mm")}
    bak = _backup_ssot()
    _write_ssot(ssot)
    rc, out = _run_drift_gate()
    _append_log({
        "class": cls, "verdict": "pin_fixed", "action": "patch-pin",
        "group": group, "pin": pin_num, "before": before, "after": after,
        "notes": notes, "drift_gate_rc": rc,
    })
    print(f"[patch] {cls} pin_layout['{group}'].pin#{pin_num}: {before} → {after}")
    print(f"[backup] {bak}")
    print(f"[drift gate] rc={rc}\n{out}")
    print("[REMINDER] pin_layout 改動會影響 wiring/drill；建議跑：")
    print("  .venv/Scripts/python.exe -m pytest tests/test_eagle_parse.py tests/test_layout_export.py -v")
    if rc != 0:
        # drift gate FAIL → 回滾至 patch 前的 .bak，絕不留下 gate-failing 的 SSOT
        shutil.copy2(bak, SSOT_JSON)
        print(f"[rollback] drift gate 失敗，已從備份還原 SSOT：{bak} → {SSOT_JSON}")
        return 1
    return 0


def _path_allowed(dotpath: str) -> bool:
    """白名單守門：只准 physical 純量尺寸與連接器 pitch；其餘（座標、pin 數、結構）拒絕。"""
    if dotpath.startswith("physical."):
        return dotpath.split(".", 1)[1] in _ALLOWED_PHYS_LEAVES
    return bool(_PITCH_PATH_RE.match(dotpath))


def _resolve_container(spec: dict, dotpath: str) -> tuple[dict, str]:
    """把 dotted path 解析成 (container_dict, leaf_key)，供純量 get/set。
    支援 'physical.height_mm' 與 'pin_layout.header_groups[0].pitch_mm'。
    中間節點須已存在（不自動建結構，fail-loud）；leaf 可不存在（null→value 填值合法）。"""
    segs = dotpath.split(".")
    cur = spec
    for seg in segs[:-1]:
        m = _SEG_RE.match(seg)
        if not m:
            raise KeyError(f"非法路徑片段: {seg!r}")
        cur = cur[m.group(1)]
        if m.group(2) is not None:
            cur = cur[int(m.group(2))]
    m = _SEG_RE.match(segs[-1])
    if not m or m.group(2) is not None:
        raise KeyError(f"leaf 必須是純量欄位名（不可帶索引）: {segs[-1]!r}")
    return cur, m.group(1)


def cmd_patch_physical(cls: str, sets: list[str], tier: str, sources: list[str],
                       confidence: str, basis: str, notes: str, ssot: dict) -> int:
    """套用安全子集純量修正（physical 尺寸 / 連接器 pitch）+ 欄位級 provenance。
    管線同 patch-extra/pin：備份 → 改 → drift gate → 失敗回滾 → append audit log。"""
    spec = ssot.get(cls)
    if not spec:
        print(f"[ERROR] class '{cls}' 不存在")
        return 2
    if not sets:
        print("[ERROR] 需至少一個 --set path=value")
        return 2

    # 先全部解析 + 驗證（任一非法即中止，不留半套寫入）
    planned: list[tuple[str, dict, str, object, float]] = []
    for raw in sets:
        if "=" not in raw:
            print(f"[ERROR] --set 格式須為 path=value: {raw!r}")
            return 2
        path, val_s = raw.split("=", 1)
        path = path.strip()
        if not _path_allowed(path):
            print(f"[ERROR] 路徑不在安全子集白名單: {path!r}\n"
                  f"        只准 physical.{{length_mm,width_mm,height_mm,pcb_thickness_mm,weight_g}} "
                  f"與 pin_layout.header_groups[N].pitch_mm；\n"
                  f"        結構性 pin/座標改動請走結構批次，非此指令。")
            return 2
        try:
            value = float(val_s.strip())
        except ValueError:
            print(f"[ERROR] value 非數值: {val_s!r}")
            return 2
        try:
            container, leaf = _resolve_container(spec, path)
        except (KeyError, IndexError, TypeError) as e:
            print(f"[ERROR] 路徑無法解析（中間結構不存在？）: {path!r} — {e}")
            return 2
        before = container.get(leaf)  # leaf 可能不存在 → None（null→value 合法）
        planned.append((path, container, leaf, before, value))

    bak = _backup_ssot()
    changes = []
    for path, container, leaf, before, value in planned:
        container[leaf] = value
        changes.append({"field": path, "before": before, "after": value})

    # 欄位級 provenance（獨立 block，攜帶 tier，不污染 _ssot20_research_provenance）
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    prov_cls = ssot.setdefault(PHYS_AUDIT_KEY, {}).setdefault(cls, {})
    for path, container, leaf, before, value in planned:
        prov_cls[path] = {
            "value": value, "previous": before, "tier": tier,
            "confidence": confidence, "basis": basis, "sources": sources, "ts": ts,
        }

    _write_ssot(ssot)
    rc, out = _run_drift_gate()
    _append_log({
        "class": cls, "verdict": "physical_fixed", "action": "patch-physical",
        "changes": changes, "tier": tier, "confidence": confidence,
        "basis": basis, "sources": sources, "notes": notes, "drift_gate_rc": rc,
    })
    for c in changes:
        print(f"[patch] {cls} {c['field']}: {c['before']} → {c['after']}")
    print(f"[prov]  {PHYS_AUDIT_KEY}['{cls}'] += {len(changes)} 欄位 (tier={tier}, {len(sources)} sources)")
    print(f"[backup] {bak}")
    print(f"[drift gate] rc={rc}")
    if out:
        print(out)
    if rc != 0:
        # drift gate FAIL → 回滾至 patch 前的 .bak，絕不留 gate-failing 的 SSOT（No-Silent-Fallback）
        shutil.copy2(bak, SSOT_JSON)
        print(f"[rollback] drift gate 失敗，已從備份還原 SSOT：{bak} → {SSOT_JSON}")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="SSOT3/4 人工審計 CLI")
    sub = ap.add_subparsers(dest="cmd", required=False)

    sub.add_parser("list", help="列出 28 待審 class 狀態")
    p_show = sub.add_parser("show", help="顯示單一 class 詳細狀態")
    p_show.add_argument("cls")
    p_rec = sub.add_parser("record", help="記錄 verdict（不改 verified.json）")
    p_rec.add_argument("cls")
    p_rec.add_argument("--verdict", required=True, choices=sorted(VALID_VERDICTS))
    p_rec.add_argument("--notes", default="")
    p_pe = sub.add_parser("patch-extra", help="修 extra_ports 座標")
    p_pe.add_argument("cls"); p_pe.add_argument("label")
    p_pe.add_argument("--cx", type=float); p_pe.add_argument("--cy", type=float)
    p_pe.add_argument("--notes", default="")
    p_pp = sub.add_parser("patch-pin", help="修 pin_layout 座標")
    p_pp.add_argument("cls"); p_pp.add_argument("group"); p_pp.add_argument("pin_num", type=int)
    p_pp.add_argument("--x", type=float); p_pp.add_argument("--y", type=float)
    p_pp.add_argument("--notes", default="")
    p_ph = sub.add_parser("patch-physical", help="修 physical 純量尺寸 / 連接器 pitch（安全子集）")
    p_ph.add_argument("cls")
    p_ph.add_argument("--set", dest="sets", action="append", default=[], metavar="PATH=VALUE",
                      help="如 physical.height_mm=29 或 pin_layout.header_groups[0].pitch_mm=2.0；可重複")
    p_ph.add_argument("--tier", required=True, help="來源 tier（A/B/community/empirical）")
    p_ph.add_argument("--source", dest="sources", action="append", default=[],
                      metavar="'name | url'", help="provenance 來源；可重複")
    p_ph.add_argument("--confidence", default="")
    p_ph.add_argument("--basis", default="")
    p_ph.add_argument("--notes", default="")

    # 也支援頂層 --list / --show CLS 的捷徑寫法
    ap.add_argument("--list", action="store_true", dest="top_list")
    ap.add_argument("--show", dest="top_show", metavar="CLS")

    args = ap.parse_args()
    log = _load_audit_log()
    ssot = _load_ssot()

    if args.top_list or args.cmd == "list":
        return cmd_list(log)
    if args.top_show:
        return cmd_show(args.top_show, ssot, log)
    if args.cmd == "show":
        return cmd_show(args.cls, ssot, log)
    if args.cmd == "record":
        return cmd_record(args.cls, args.verdict, args.notes, ssot)
    if args.cmd == "patch-extra":
        return cmd_patch_extra(args.cls, args.label, args.cx, args.cy, args.notes, ssot)
    if args.cmd == "patch-pin":
        return cmd_patch_pin(args.cls, args.group, args.pin_num, args.x, args.y, args.notes, ssot)
    if args.cmd == "patch-physical":
        return cmd_patch_physical(args.cls, args.sets, args.tier, args.sources,
                                  args.confidence, args.basis, args.notes, ssot)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
