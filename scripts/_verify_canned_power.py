"""scripts/_verify_canned_power.py — 三方交叉驗證 16 範本功率。

來源：
  A. SSOT   = data/component_datasheet_verified.json (electrical.current_typ_ma)
  B. INDEX  = v6/canned/_index.json (total_ma / budget_ma)
  C. PROBLEM = problem.md 內表格（硬編對照）

對每範本：
  1. 讀 v6/canned/<id>.json 取 components 列表
  2. 取每 comp 的 class_name → 查 SSOT current_typ_ma
  3. 加總得 SSOT_total
  4. 與 INDEX_total、PROBLEM_total 比對

用法：.venv\\Scripts\\python.exe scripts\\_verify_canned_power.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT = ROOT / "data" / "component_datasheet_verified.json"
CANNED = ROOT / "v6" / "canned"

# problem.md 表（手抄）
PROBLEM_TABLE: dict[str, tuple[float, int]] = {
    "auto_waterer":        (355,    800),
    "plant_monitor":       (76.5,   800),
    "smart_nightlight":    (71,    1000),
    "auto_curtain":        (561,   1000),
    "voice_doorbell":      (200.5, 1000),
    "rc_car":              (735,   1000),
    "obstacle_car":        (665,   1000),
    "talking_robot":       (285,   1000),
    "music_box":           (200,   1000),
    "lightsaber":          (750.5, 1000),
    "electronic_keyboard": (79,    1000),
    "burglar_alarm":       (145,    800),
    "access_control":      (342,   1000),
    "alarm_siren":         (100,   1000),
    "countdown_timer":     (101,   1000),
    "voice_guide":         (202,    800),
}


def _load_ssot() -> dict[str, float]:
    """class_name → current_typ_ma (mA)"""
    data = json.loads(SSOT.read_text(encoding="utf-8"))
    out: dict[str, float] = {}
    for cls, body in data.items():
        if cls == "_meta":
            continue
        elec = body.get("electrical") or {}
        cur = elec.get("current_typ_ma")
        if cur is None:
            cur = elec.get("current_idle_ma", 0)
        out[cls] = float(cur)
    return out


def _load_index() -> dict[str, dict]:
    """tpl_id → entry (total_ma / budget_ma)"""
    arr = json.loads((CANNED / "_index.json").read_text(encoding="utf-8"))
    return {e["id"]: e for e in arr}


def _load_canned(tpl_id: str) -> dict:
    """v6/canned/<id>.json → parsed bridge dict (cached call-side)."""
    return json.loads((CANNED / f"{tpl_id}.json").read_text(encoding="utf-8"))


def _bridge_components(bridge: dict) -> list[dict]:
    """Parsed bridge dict → components list."""
    return bridge.get("components") or []


def _class_of(comp: dict) -> str:
    """bridge component schema: comp['type'] == SSOT class_name (e.g. 'Arduino-Uno-class')."""
    return comp.get("type") or "?"


def _qty(comp: dict) -> int:
    try:
        return int(comp.get("qty", 1))
    except (TypeError, ValueError):
        return 1


def _spec_current(comp: dict) -> float:
    """bridge 內快取的 spec.current_ma（用於檢查 bridge 是否跟 SSOT 對齊）"""
    spec = comp.get("spec") or {}
    try:
        return float(spec.get("current_ma", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _bridge_power_budget(bridge: dict) -> dict:
    """Parsed bridge dict → power_budget (phase3 calculated authoritative value)."""
    return bridge.get("power_budget") or {}


def _all_match(ssot_t: float, spec_t: float, idx_t: float,
               pb_t: float | None, pm_t: float | None) -> bool:
    """Five-column concordance: SSOT, SPEC, INDEX, BRIDGE, PROBLEM all within 1 mA."""
    if abs(spec_t - idx_t) >= 1:
        return False
    if abs(ssot_t - idx_t) >= 1:
        return False
    if pb_t is not None and abs(ssot_t - pb_t) >= 1:
        return False
    if pm_t is not None and abs(ssot_t - pm_t) >= 1:
        return False
    return True


def main() -> int:
    ssot = _load_ssot()
    idx = _load_index()
    print(f"SSOT classes: {len(ssot)}")
    print(f"INDEX templates: {len(idx)}")
    print()

    missing_classes: set[str] = set()
    rows: list[tuple] = []

    for tpl_id, idx_entry in idx.items():
        bridge = _load_canned(tpl_id)
        comps = _bridge_components(bridge)
        ssot_total = 0.0
        spec_total = 0.0
        unresolved: list[str] = []
        for c in comps:
            cls = _class_of(c)
            q = _qty(c)
            cur_ssot = ssot.get(cls)
            cur_spec = _spec_current(c)
            spec_total += cur_spec * q
            if cur_ssot is None:
                unresolved.append(cls)
                missing_classes.add(cls)
            else:
                ssot_total += cur_ssot * q
        idx_total = idx_entry["total_ma"]
        idx_budget = idx_entry["budget_ma"]
        pb = _bridge_power_budget(bridge)
        pb_total = pb.get("total_ma")
        pb_budget = pb.get("budget_ma")
        pm = PROBLEM_TABLE.get(tpl_id)
        pm_total = pm[0] if pm else None
        pm_budget = pm[1] if pm else None
        rows.append((tpl_id, ssot_total, spec_total, idx_total, pb_total, pm_total,
                     idx_budget, pb_budget, pm_budget, unresolved))

    print(f"{'tpl_id':<22} {'SSOT':>7} {'SPEC':>7} {'INDEX':>7} {'BRIDGE':>7} {'PM':>7}  "
          f"{'budget(I/B/P)':<14} status")
    print("-" * 110)
    for (tpl_id, ssot_t, spec_t, idx_t, pb_t, pm_t,
         idx_b, pb_b, pm_b, unres) in rows:
        budget = f"{idx_b}/{pb_b if pb_b else '-'}/{pm_b if pm_b else '-'}"
        unr = ",".join(unres) if unres else ""
        pm_disp = f"{pm_t:.1f}" if pm_t is not None else "-"
        pb_disp = f"{pb_t:.1f}" if pb_t is not None else "-"
        d_idx_spec = abs(spec_t - idx_t) < 1
        d_idx_ssot = abs(ssot_t - idx_t) < 1
        d_pb = pb_t is not None and abs(ssot_t - pb_t) < 1
        d_pm = pm_t is not None and abs(ssot_t - pm_t) < 1
        all_ok = d_idx_spec and d_idx_ssot and d_pb and d_pm
        flag = "OK" if all_ok else "MISMATCH!"
        print(f"{tpl_id:<22} {ssot_t:>7.1f} {spec_t:>7.1f} {idx_t:>7.1f} "
              f"{pb_disp:>7} {pm_disp:>7}  {budget:<14} {flag} {unr}")

    mismatch_count = sum(1 for r in rows
                         if not (_all_match(r[1], r[2], r[3], r[4], r[5])))

    if missing_classes:
        print()
        print(f"[WARN] {len(missing_classes)} class_name not in SSOT:")
        for c in sorted(missing_classes):
            print(f"  - {c}")

    if mismatch_count:
        print(f"\nFAIL: {mismatch_count} template(s) have power MISMATCH")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
