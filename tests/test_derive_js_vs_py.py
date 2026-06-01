"""tests/test_derive_js_vs_py.py — datasheet-derive.js 與 derive_component_dimensions.py 跨語言一致性。

P5.7：兩個 derive 實作必須對同一份 verified.json 條目產出位置一致的 ports。
Skip 條件：Node 不可用（CI runner 缺 node）→ pytest.skip。
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"
JS_DERIVE = ROOT / "v6" / "data" / "datasheet-derive.js"

TOL_MM = 0.001  # JS Number 與 Python float 跨語言差，允許 µm 級舍入

# 抽樣涵蓋三種衍生路徑：frontend_shape(on_board)、extra_ports、pin_layout(opt-in)
SAMPLE_CLASSES = [
    "Battery-AA-class",      # on_board frontend_shape + extra_ports
    "Pump-Water-class",      # on_board frontend_shape + extra_ports
    "Relay-Module-class",    # 全 on_board frontend_shape，無 extra_ports
    "Remote-class",          # derive_from_pin_layout opt-in
    "ESP32-class",           # 全 extra_ports（無 frontend_shape 匹配）
]


@pytest.fixture(scope="module")
def node_available():
    if shutil.which("node") is None:
        pytest.skip("node not available — install Node.js to run JS/Python derive cross-check")
    return True


def _run_js_derive(class_name: str) -> dict | None:
    """用 Node 載 datasheet-derive.js 並對指定 class 跑衍生，回傳 JSON。"""
    js_code = f"""
const fs = require('fs');
const path = require('path');
// stub window 物件給 datasheet-derive.js
global.window = {{}};
const code = fs.readFileSync({json.dumps(str(JS_DERIVE))}, 'utf-8');
eval(code);
const ssot = JSON.parse(fs.readFileSync({json.dumps(str(SSOT_JSON))}, 'utf-8'));
const cls = {json.dumps(class_name)};
const ds = ssot[cls];
if (!ds) {{ console.error('NO_SSOT'); process.exit(1); }}
const result = window.deriveDimsFromDatasheet(ds);
process.stdout.write(JSON.stringify(result));
"""
    r = subprocess.run(["node", "-e", js_code], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        raise RuntimeError(f"node failed: {r.stderr}")
    return json.loads(r.stdout)


def _run_py_derive(class_name: str) -> dict:
    sys.path.insert(0, str(ROOT))
    from scripts.derive_component_dimensions import derive_entry  # noqa: E402
    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    return derive_entry(class_name, ssot[class_name])


@pytest.mark.parametrize("cls", SAMPLE_CLASSES)
def test_js_py_derive_consistency(node_available, cls):
    js_out = _run_js_derive(cls)
    py_out = _run_py_derive(cls)

    # 整體 l/w/h
    for key in ("l", "w", "h"):
        jv, pv = js_out.get(key), py_out.get(key)
        if jv is None or pv is None:
            continue
        assert abs(float(jv) - float(pv)) <= TOL_MM, f"{cls} {key} diverged: JS={jv} vs PY={pv}"

    # ports 數量
    assert len(js_out["ports"]) == len(py_out["ports"]), \
        f"{cls} port count diverged: JS={len(js_out['ports'])} vs PY={len(py_out['ports'])}"

    # 每個 port 對應比對（用 (label, side) 為 key，重複時用 (cx,cy) 最近鄰）
    js_ports = list(js_out["ports"])
    py_ports = list(py_out["ports"])
    for pp in py_ports:
        candidates = [j for j in js_ports if j["label"] == pp["label"] and j["side"] == pp["side"]]
        assert candidates, f"{cls}/{pp['label']} not found in JS output"
        best = min(candidates, key=lambda j: (j["cx"] - pp["cx"]) ** 2 + (j["cy"] - pp["cy"]) ** 2)
        js_ports.remove(best)
        for key in ("cx", "cy"):
            assert abs(best[key] - pp[key]) <= TOL_MM, \
                f"{cls}/{pp['label']} {key} diverged: JS={best[key]} vs PY={pp[key]}"
        assert best["shape"] == pp["shape"], \
            f"{cls}/{pp['label']} shape diverged: JS={best['shape']} vs PY={pp['shape']}"
