"""tests/test_read_through_invariant.py — 讀穿不變量 gate(使用者常駐紀律,2026-06-10)。

原則(memory: read-through-not-extra-construct):凡可從單一真值源 verified.json **讀穿**的
load-bearing 數據,不得在別處**額外建制**(手寫副本)。最大異常 = `COMPONENT_REGISTRY`
(`lib/registry/_reg_*.py`)的 ComponentSpec 自帶 `length/width/height/current_ma/voltage_v/
weight_g/thermal_mw` 副本,與 verified.json physical/electrical 重疊;43 class 靠對帳維持同步。

本 gate 把該異常**固化、防漂移、防擴散**(在重構成真正讀穿之前):
  ① 凡 verified.json 有的欄位 → registry 值不得獨立漂移(沿用 specs._derive_specs_from_verified
     即「讀穿源本身」做比對,不在測試重寫衍生)。
  ② registry 有值但 verified.json **缺**該欄(= 額外建制的唯一棲身處)→ 必須在下方**凍結清單**
     內並附理由;**新增未列的額外建制即 FAIL**(逼人補 verified.json 或顯式justify)。

與既有 gate 互補:`test_power_ma_coverage` 只對 current_ma 做值對帳 + 計數;此 gate 統一涵蓋
geometry/voltage/weight/thermal 的讀穿一致性 + 全欄位的額外建制清單。
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.registry import COMPONENT_REGISTRY
from lib.specs import _derive_specs_from_verified

_VJ = json.loads((Path(__file__).resolve().parent.parent / "data"
                  / "component_datasheet_verified.json").read_text(encoding="utf-8"))

# registry ComponentSpec attr → (verified.json 衍生取值, 容差)。
# voltage/weight/thermal/current 取自 specs._derive_specs_from_verified()（讀穿源本身）；
# geometry 直接讀 verified.json physical（含 pcb_ 前綴 fallback，與 ssot_completeness 一致）。
_DERIVED = _derive_specs_from_verified()  # {section: {class: value}}，僅含 verified.json 有該欄者


def _verified_value(cls: str, field: str):
    """回 verified.json 對該 (class, field) 的讀穿值；verified.json 缺該欄 → None。"""
    if field == "current_ma":
        return _DERIVED["power_ma"].get(cls)
    if field == "voltage_v":
        return _DERIVED["voltage_v"].get(cls)
    if field == "weight_g":
        return _DERIVED["weight_g"].get(cls)
    if field == "thermal_mw":
        return _DERIVED["thermal_mw"].get(cls)
    phys = _VJ.get(cls, {}).get("physical", {})
    if field == "length_mm":
        return phys.get("length_mm") or phys.get("pcb_length_mm")
    if field == "width_mm":
        return phys.get("width_mm") or phys.get("pcb_width_mm")
    if field == "height_mm":
        return phys.get("height_mm")
    raise AssertionError(f"unknown field {field}")


_FIELDS = {
    "length_mm": 0.6, "width_mm": 0.6, "height_mm": 0.6,
    "current_ma": 0.5, "voltage_v": 0.05, "weight_g": 0.6, "thermal_mw": 1.0,
}

# ── 凍結額外建制清單:registry/specs 供值但 verified.json 缺該欄 ─────────────────
# 每筆都是「讀穿缺口」:或 verified.json 應補該欄(→ 變讀穿),或合理非 datasheet
# (電源輸出容量 / 被動零 / 量測待補)。新增未列項 = 新額外建制,gate 會擋。
_REGISTRY_ONLY_ALLOWED: dict[tuple[str, str], str] = {
    # 電源 source:registry current_ma = 輸出容量,非 datasheet 消耗;verified.json 無 current_typ_ma
    ("AC-Adapter-class", "current_ma"): "power source output capacity, not consumption",
    ("USB-Adapter-class", "current_ma"): "power source output capacity, not consumption",
    ("Battery-AA-class", "current_ma"): "power source: consumption 0",
    ("Battery-4AA-class", "current_ma"): "power source: consumption 0",
    ("Battery-LiPo-class", "current_ma"): "power source: consumption 0",
    # 被動 / 結構:無消耗 / 無工作電壓(registry 用預設)
    ("Chassis-Car-class", "current_ma"): "passive structural: 0",
    ("Chassis-Car-class", "voltage_v"): "passive structural: no operating voltage (registry default 5.0)",
    ("Speaker-class", "voltage_v"): "passive transducer: no operating voltage (registry default 5.0)",
    ("Switch-class", "current_ma"): "passive mechanical: 0",
    ("Switch-Generic-class", "current_ma"): "passive mechanical: 0",
    # verified.json 欄位缺口(specs _fallback 暫補,應最終補進 verified.json electrical.current_typ_ma)
    ("Joystick-class", "current_ma"): "verified.json gap: no current_typ_ma (specs _fallback)",
    ("Sensor-IR-class", "current_ma"): "verified.json gap: no current_typ_ma (specs _fallback)",
    ("Display-EInk-class", "current_ma"): "verified.json gap: no current_typ_ma (specs _fallback)",
    ("Lighting-LED-Strip-class", "current_ma"): "verified.json gap: no current_typ_ma (specs _fallback)",
    ("Arduino-Nano-class", "current_ma"): "verified.json gap: ATmega328≈Uno, datasheet power=TBC; _fallback community-consensus 19mA",
    ("Arduino-Nano-class", "thermal_mw"): "verified.json gap: datasheet thermal=TBC; _fallback community-consensus 150mW (~ATmega328 Uno-class)",
    # Motor-Stepper 物理尺寸待量測(已在 ssot_completeness.WIP_WHITELIST)
    ("Motor-Stepper-class", "length_mm"): "verified.json gap: physical L/W/H pending measurement (WIP)",
    ("Motor-Stepper-class", "width_mm"): "verified.json gap: physical L/W/H pending measurement (WIP)",
    ("Motor-Stepper-class", "height_mm"): "verified.json gap: physical L/W/H pending measurement (WIP)",
}


def _registry_only_actual() -> set[tuple[str, str]]:
    """實算:registry 有值但 verified.json 缺該欄的 (class, field) 集合。"""
    out: set[tuple[str, str]] = set()
    for cls, spec in COMPONENT_REGISTRY.items():
        if cls not in _VJ:
            continue  # 不在 SSOT 的 class 屬另一條 gate(referential integrity)
        for field in _FIELDS:
            reg = getattr(spec, field, None)
            if reg is None:
                continue
            if _verified_value(cls, field) is None:
                out.add((cls, field))
    return out


def test_no_drift_on_overlapping_fields():
    """讀穿不變量:凡 verified.json 有的 load-bearing 欄位,registry 副本不得漂移。
    抓到漂移 = 額外建制副本與單一真值不一致(應讀穿,不該各持一份)。"""
    drift = []
    for cls, spec in COMPONENT_REGISTRY.items():
        if cls not in _VJ:
            continue
        for field, tol in _FIELDS.items():
            v = _verified_value(cls, field)
            if v is None:
                continue
            reg = getattr(spec, field, None)
            if reg is None or abs(float(reg) - float(v)) > tol:
                drift.append(f"{cls}.{field}: registry={reg} != verified.json={v}")
    assert not drift, (
        "registry 副本與 verified.json 漂移(讀穿不變量破壞,應讀穿而非自帶副本):\n  "
        + "\n  ".join(drift))


def test_registry_only_fields_match_frozen_inventory():
    """額外建制清單凍結:registry 供值而 verified.json 缺該欄者,須恰等於 _REGISTRY_ONLY_ALLOWED。
    - 新增未列項 → 新的額外建制(該補 verified.json 或顯式 justify)。
    - 清單有但實際已無 → verified.json 已補上,請從清單移除(避免死項)。"""
    actual = _registry_only_actual()
    allowed = set(_REGISTRY_ONLY_ALLOWED)
    new = actual - allowed
    gone = allowed - actual
    assert not new, (
        "新增的額外建制(registry 供值、verified.json 缺、且未列入凍結清單):\n  "
        + "\n  ".join(f"{c}.{f}" for c, f in sorted(new))
        + "\n→ 補進 verified.json 使其可讀穿,或附理由加入 _REGISTRY_ONLY_ALLOWED。")
    assert not gone, (
        "凍結清單有但實際已不再額外建制(verified.json 已補?)請移除死項:\n  "
        + "\n  ".join(f"{c}.{f}" for c, f in sorted(gone)))


def test_inventory_entries_have_reasons():
    """每筆額外建制都須附非空理由(禁止無依據掛白名單)。"""
    blank = [k for k, v in _REGISTRY_ONLY_ALLOWED.items() if not (v and v.strip())]
    assert not blank, f"額外建制清單缺理由: {blank}"


def test_reg_files_carry_no_geometry_literals_except_wip():
    """B5-geo meta-gate:`_reg_*.py` 不得帶 L/W/H 字面值(除 Motor-Stepper WIP gap)——geometry
    一律由 `registry_data` Tier 1.5 從 verified.json physical 讀穿。防回歸到字面副本:#17 漂移
    gate 抓不到「重加但與 verified.json 同值」的死 literal,此 gate 直接禁源碼出現該額外建制。"""
    import re
    reg_dir = Path(__file__).resolve().parent.parent / "lib" / "registry"
    _lwh = re.compile(r'^\s*length_mm=.*width_mm=.*height_mm=.*,\s*$')
    _cls = re.compile(r"'([A-Za-z0-9\-]+-class)':\s*ComponentSpec\(")
    offenders = []
    for f in sorted(reg_dir.glob("_reg_*.py")):
        cur = None
        for ln in f.read_text(encoding="utf-8").splitlines():
            m = _cls.search(ln)
            if m:
                cur = m.group(1)
            if _lwh.match(ln) and cur != "Motor-Stepper-class":
                offenders.append(f"{f.name}:{cur}")
    assert not offenders, (
        "_reg_*.py 重新出現 geometry 字面副本(應讀穿 verified.json,非自帶 — B5-geo):\n  "
        + "\n  ".join(offenders))
