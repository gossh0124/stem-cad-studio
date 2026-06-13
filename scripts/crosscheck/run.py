"""scripts/crosscheck/run.py — Axis-A≡Axis-B 交叉驗證 orchestrator(DEC-H3/H6)。

Axis-A(in-repo,系統 3.14):build_netlist → galvanic isolation 判定 + 兩地 node-set + 輸入 hash。
Axis-B(防火牆外,venv313 SKiDL):獨立重建電路 + 原生 ERC + 隔離 set 代數(見 axis_b_isolation.py)。
收口判準:两軸對同一 demo 同意(isolation + 兩地 node-set 相等)且 Axis-B 對綁地 mutant 會抓到。

產 scripts/crosscheck/crosscheck-results.json(committed witness,freshness hash 防 stale);
中間檔 axis_a.json 在 _artifacts/(gitignore)。
in-repo gate = tests/test_crosscheck_results.py(**不** import skidl,只讀 JSON + 重算 hash 驗 freshness)。

用法:python scripts/crosscheck/run.py
  venv313 路徑:環境變數 CDV_VENV313,或預設 ~/.claude/skills/circuit-design-verify/.venv313。
  無 venv313 → **不覆寫**已含 Axis-B 的 committed witness(否則乾淨環境一跑就把已驗 witness 毀成
  null + exit 0,gate 退化成 skip-by-default,且 repo 非 git 不可復原);降級 Axis-A-only 輸出改寫
  _artifacts/,committed witness 缺檔時 in-repo 測試自然 skip。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

ART = Path(__file__).resolve().parent / "_artifacts"
# results 為可提交的驗證 witness（freshness hash 防 stale);中間檔 axis_a.json 在 _artifacts/(gitignore)。
RESULTS = Path(__file__).resolve().parent / "crosscheck-results.json"
_DEFAULT_VENV = Path.home() / ".claude" / "skills" / "circuit-design-verify" / ".venv313" / "Scripts" / "python.exe"

# auto_waterer 標準接線:控制端(Arduino + Soil + Relay 線圈)+ 負載端(Battery + Pump 經 relay 接點)。
# 與 isolation 測試 fixture 同源;build_netlist 的隔離 post-pass 會把 Pump.GND 搬到 EXT-GND。
AUTO_WATERER = {
    "SoilMoisture": {"pins": [{"comp": "VCC", "mcu": "5V"}, {"comp": "GND", "mcu": "GND"},
                              {"comp": "AO", "mcu": "A0"}]},
    "Relay": {"pins": [{"comp": "VCC", "mcu": "5V"}, {"comp": "GND", "mcu": "GND"},
                       {"comp": "IN", "mcu": "D2"}, {"comp": "COM", "mcu": "EXT-PWR"},
                       {"comp": "NO", "mcu": "LOAD+"}]},
    "Pump": {"pins": [{"comp": "VCC", "mcu": "Relay.NO"}, {"comp": "GND", "mcu": "GND"}]},
    "BatteryAA": {"pins": [{"comp": "V+", "mcu": "EXT-PWR", "_netRole": "source"},
                           {"comp": "GND", "mcu": "EXT-GND", "_netRole": "source"}]},
}
LOGIC_GND, LOAD_GND = "GND", "EXT-GND"


def _gnd_set(nets, name):
    for n in nets:
        if n.get("name") == name:
            return sorted((nd["ref"], nd["pin"]) for nd in n["nodes"])
    return []


def compute_axis_a() -> dict:
    """build_netlist → 隔離判定 + 兩地 node-set + 規範化輸入 hash(freshness 用)。"""
    from lib.wiring import build_netlist
    nets = build_netlist("Arduino", AUTO_WATERER)
    logic = _gnd_set(nets, LOGIC_GND)
    load = _gnd_set(nets, LOAD_GND)
    shared = sorted(set(map(tuple, logic)) & set(map(tuple, load)))
    canon = json.dumps(
        [{"name": n["name"], "nodes": sorted((x["ref"], x["pin"]) for x in n["nodes"])}
         for n in sorted(nets, key=lambda n: n.get("name", ""))],
        sort_keys=True, ensure_ascii=False)
    input_hash = hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]
    return {"isolation_pass": len(shared) == 0, "logic_gnd_pins": logic,
            "load_gnd_pins": load, "shared": shared, "input_hash": input_hash}


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    axis_a = compute_axis_a()
    axis_a_path = ART / "axis_a.json"
    axis_a_path.write_text(json.dumps(axis_a, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[AXIS-A] isolation_pass={axis_a['isolation_pass']} "
          f"logic={len(axis_a['logic_gnd_pins'])} load={len(axis_a['load_gnd_pins'])} "
          f"hash={axis_a['input_hash']}")

    venv = Path(os.environ.get("CDV_VENV313", str(_DEFAULT_VENV)))
    if not venv.exists():
        print(f"[WARN] venv313 不存在({venv}) → Axis-B 跳過,不重新產生交叉驗證。")
        # 防呆:絕不以 axis_b=null 覆寫已含 Axis-B 的 committed witness(否則無 SKiDL 的機器一跑
        # 即毀掉已驗 witness + exit 0,gate 退化成 skip-by-default;repo 非 git 不可復原)。
        if RESULTS.exists() and json.loads(
                RESULTS.read_text(encoding="utf-8")).get("axis_b") is not None:
            print(f"[KEEP] 既有 committed witness 已含 Axis-B,保留不覆寫 → {RESULTS}")
            print("       裝 SKiDL venv313 後重跑以更新交叉驗證(見 README.md)。")
            return 0
        # 無已驗 witness:降級 Axis-A-only 寫 _artifacts/,**不**碰 committed 路徑;
        # committed witness 缺檔 → in-repo 測試自然 skip(乾淨環境正確行為)。
        degraded = ART / "crosscheck-results.axis-a-only.json"
        degraded.write_text(json.dumps(
            {"demo": "auto_waterer", "axis_a": axis_a, "axis_b": None,
             "agree": None, "node_sets_equal": None, "input_hash": axis_a["input_hash"]},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[WARN] 無已驗 witness;Axis-A-only 降級輸出 → {degraded}"
              "(committed witness 未動,in-repo 測試將 skip)。裝 SKiDL 後重跑(見 README.md)。")
        return 0

    axis_b_script = Path(__file__).resolve().parent / "axis_b_isolation.py"
    proc = subprocess.run(
        [str(venv), str(axis_b_script), str(axis_a_path), str(RESULTS)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    # 過濾 SKiDL 的 symbol-dir / fp-lib-table 雜訊,只留實質輸出
    for line in (proc.stdout + proc.stderr).splitlines():
        if line.strip() and "SYMBOL_DIR" not in line and "fp-lib-table" not in line:
            print(f"  {line}")
    if proc.returncode != 0 or not RESULTS.exists():
        print(f"[FAIL] Axis-B 執行失敗(rc={proc.returncode})")
        return 1

    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    ok = (res.get("agree") and res.get("node_sets_equal")
          and res.get("axis_b", {}).get("isolation_pass")
          and res.get("mutant", {}).get("axis_b_caught"))
    print(f"[CROSSCHECK] {'AGREE' if ok else 'MISMATCH'} → {RESULTS}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
