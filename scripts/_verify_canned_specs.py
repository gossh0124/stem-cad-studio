"""scripts/_verify_canned_specs.py — canned voltage/weight/thermal 對賬 gate。

比照 scripts/_verify_canned_power.py（功率 5 欄對賬），但對的是「靜態 spec」:
  voltage_v / weight_g / thermal_mw。

基準（唯一真相）：lib.registry.COMPONENT_REGISTRY 的
  .voltage_v / .weight_g / .thermal_mw
（SSOT20 後已讀穿 data/_component_specs_cache.json ← data/component_datasheet_verified.json）。

對每個 v6/canned/<id>.json 掃描三種 baked 面，與基準比對：
  1. voltage : components[].spec.voltage_v          （key=components[].type）
  2. thermal : 任一 dict 內 thermal_mw              （key=type/comp_type）
               或 thermal_field/heat_source 的 power_mw（帶 spatial_kind/
               estimation_source 簽名 → 是熱耗，非 cot_plan 的電氣 power_mw）
  3. weight  : 任一 dict 內 weight_g（資料值，非 decisions 公式字串）

電氣 current_ma 不在此檢（已由 _verify_canned_power.py 五欄對賬涵蓋）。
此 gate 為 demo 顯示一致性，不擋既有 pytest / canned power gate。

用法：.venv\\Scripts\\python.exe scripts\\_verify_canned_specs.py
回傳：0 = 全對齊；1 = 有漂移（列出每筆 baked != registry）。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

try:  # Windows CP950 終端：強制 UTF-8 輸出避免中文 mojibake
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "lib"))

from lib.registry import COMPONENT_REGISTRY  # noqa: E402
from lib.specs import resolve_component_alias  # noqa: E402

CANNED = ROOT / "v6" / "canned"

# 容差：voltage 0.01V、thermal 0.5mW、weight 0.5g
_TOL = {"voltage_v": 0.01, "thermal_mw": 0.5, "weight_g": 0.5}


def _baseline(cls: str, field: str) -> float | None:
    """registry 基準值；class 不在表時走 alias 解析。"""
    spec = COMPONENT_REGISTRY.get(cls) or COMPONENT_REGISTRY.get(
        resolve_component_alias(cls)
    )
    return float(getattr(spec, field)) if spec else None


def _type_of(d: dict) -> str | None:
    """dict 內的元件型別鍵（canned 各處命名不一）。"""
    return d.get("type") or d.get("comp_type") or d.get("class") or d.get("selected_type")


def _walk(node, path: str = ""):
    """深走整棵樹，yield (path, dict)。"""
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def collect_voltage(bridge: dict) -> list[tuple[str, str, float]]:
    """components[].spec.voltage_v → (path, type, baked)。"""
    out: list[tuple[str, str, float]] = []
    for i, c in enumerate(bridge.get("components") or []):
        spec = c.get("spec") or {}
        if _is_num(spec.get("voltage_v")):
            out.append((f"components[{i}].spec.voltage_v",
                        c.get("type") or "?", float(spec["voltage_v"])))
    return out


def collect_thermal(bridge: dict) -> list[tuple[str, str, float]]:
    """所有 thermal 面 → (path, type, baked_mw)。

    - dict 內 thermal_mw（無條件視為熱耗）
    - dict 內 power_mw 且帶 heat_source 簽名（spatial_kind / estimation_source）
      → 此處 power_mw 是熱耗，非 cot_plan.subsystems 的電氣 power_mw
    """
    out: list[tuple[str, str, float]] = []
    for path, d in _walk(bridge):
        t = _type_of(d)
        if t is None:
            continue
        if _is_num(d.get("thermal_mw")):
            out.append((f"{path}.thermal_mw", t, float(d["thermal_mw"])))
        elif _is_num(d.get("power_mw")) and (
            "spatial_kind" in d or "estimation_source" in d
        ):
            out.append((f"{path}.power_mw", t, float(d["power_mw"])))
    return out


def collect_weight(bridge: dict) -> list[tuple[str, str, float]]:
    """任一 dict 內 weight_g 資料值 → (path, type, baked_g)。"""
    out: list[tuple[str, str, float]] = []
    for path, d in _walk(bridge):
        t = _type_of(d)
        if t is not None and _is_num(d.get("weight_g")):
            out.append((f"{path}.weight_g", t, float(d["weight_g"])))
    return out


_COLLECTORS = {
    "voltage_v": collect_voltage,
    "thermal_mw": collect_thermal,
    "weight_g": collect_weight,
}


def main() -> int:
    files = sorted(CANNED.glob("*.json"))
    files = [f for f in files if f.name != "_index.json"]
    print(f"registry classes: {len(COMPONENT_REGISTRY)}")
    print(f"canned templates: {len(files)}")
    print()

    drift_rows: list[tuple] = []   # (tpl, field, path, type, baked, base)
    missing: set[str] = set()
    surfaces = 0

    for f in files:
        bridge = json.loads(f.read_text(encoding="utf-8"))
        tpl = f.stem
        for field, collector in _COLLECTORS.items():
            for path, ctype, baked in collector(bridge):
                surfaces += 1
                base = _baseline(ctype, field)
                if base is None:
                    missing.add(f"{ctype}.{field}")
                    continue
                if abs(baked - base) >= _TOL[field]:
                    drift_rows.append((tpl, field, path, ctype, baked, base))

    print(f"scanned {surfaces} baked spec surfaces across {len(files)} templates")
    print()

    if drift_rows:
        print(f"{'template':<20} {'field':<11} {'type':<26} "
              f"{'baked':>8} {'registry':>9}  path")
        print("-" * 110)
        for tpl, field, path, ctype, baked, base in sorted(drift_rows):
            print(f"{tpl:<20} {field:<11} {ctype:<26} "
                  f"{baked:>8.2f} {base:>9.2f}  {path}")
        # 依 (field, type) 聚合，方便看「同一錯值散佈幾檔」
        agg: dict[tuple[str, str, float, float], int] = {}
        for tpl, field, path, ctype, baked, base in drift_rows:
            agg[(field, ctype, baked, base)] = agg.get((field, ctype, baked, base), 0) + 1
        print()
        print("漂移聚合（field / type / baked→registry / 出現次數）：")
        for (field, ctype, baked, base), n in sorted(agg.items()):
            print(f"  {field:<11} {ctype:<26} {baked:>8.2f} -> {base:<8.2f} x{n}")

    if missing:
        print()
        print(f"[WARN] {len(missing)} (class.field) 無 registry 基準（已略過比對）：")
        for m in sorted(missing):
            print(f"  - {m}")

    print()
    if drift_rows:
        print(f"FAIL: {len(drift_rows)} 筆 baked spec 與 registry 漂移")
        return 1
    print("OK: 所有 canned voltage/weight/thermal 與 registry 對齊")
    return 0


if __name__ == "__main__":
    sys.exit(main())
