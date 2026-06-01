"""tests/test_ssot_drift.py — pytest wrapper 把 SSOT drift gate 接進 CI。

對齊 data/component_datasheet_verified.json (SSOT) 與 v6/data/component-dimensions.js。
若 verified.json 變動 → 兩個 gate 之一爆掉即可 fail CI，阻擋 SSOT 漂移。
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SSOT_JSON = ROOT / "data" / "component_datasheet_verified.json"


def _run_script(rel_path: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / rel_path), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_core_three_components_aligned():
    """11 sub-components × 3 核心 classes 對齊 SSOT (tol=0.1mm)。

    對應 scripts/test_dimensions_drift.py 的 GATE 1。
    """
    r = _run_script("scripts/test_dimensions_drift.py")
    output = r.stdout + r.stderr
    assert r.returncode == 0, f"drift gate failed:\n{output}"
    assert "[OK]" in r.stdout, output


def test_derive_position_strict():
    """43 classes derive output 與 dims.js 位置一致 (tol=0.1mm)。

    對應 scripts/derive_component_dimensions.py --check 的 GATE 2。
    """
    r = _run_script("scripts/derive_component_dimensions.py", "--check")
    output = r.stdout + r.stderr
    assert r.returncode == 0, f"derive --check failed:\n{output}"
    assert "[FAIL]" not in r.stdout, output


def test_datasheet_derive_smoke():
    """三核心元件 derive_entry 衍生 ports 應非空，欄位齊全。"""
    sys.path.insert(0, str(ROOT))
    from scripts.derive_component_dimensions import derive_entry  # noqa: E402

    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    for cls in ["Battery-AA-class", "Pump-Water-class", "Relay-Module-class"]:
        entry = derive_entry(cls, ssot[cls])
        assert entry["ports"], f"{cls} derived ports should not be empty"
        assert entry["l"] and entry["w"] and entry["h"], f"{cls} l/w/h should be set"
        for p in entry["ports"]:
            for key in ("side", "cx", "cy", "shape", "label", "color"):
                assert key in p, f"{cls}/{p.get('label')} missing {key}"


@pytest.mark.parametrize("cls", ["Battery-AA-class", "Pump-Water-class", "Relay-Module-class"])
def test_ssot_has_3d_hints_and_ui_hints(cls):
    """核心三元件必須有 _3d_hints + _ui_hints（Phase 3A schema gate）。"""
    ssot = json.loads(SSOT_JSON.read_text(encoding="utf-8"))
    spec = ssot.get(cls)
    assert spec, f"SSOT 缺 {cls}"
    assert "_3d_hints" in spec, f"{cls} 缺 _3d_hints"
    assert "_ui_hints" in spec, f"{cls} 缺 _ui_hints"
    assert spec["_ui_hints"].get("frontend_shape"), f"{cls} _ui_hints.frontend_shape 應非空"
