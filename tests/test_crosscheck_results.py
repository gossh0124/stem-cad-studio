"""tests/test_crosscheck_results.py — Axis-B 交叉驗證 in-repo gate(DEC-H3/H4)。

防火牆(DEC-H4):本檔**不** import skidl/kicad;只讀 `scripts/crosscheck/crosscheck-results.json`
+ 用 repo 純碼重算 Axis-A hash 驗 freshness。results 由 `python scripts/crosscheck/run.py`
(需 venv313)產生;無 / Axis-B=null → skip(lean CI 無 SKiDL)。
"""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "scripts" / "crosscheck" / "crosscheck-results.json"


def _load_compute_axis_a():
    """以路徑載入 run.py 的 compute_axis_a(單一來源,避免複製 hash 規範化邏輯)。"""
    spec = importlib.util.spec_from_file_location(
        "xcheck_run", ROOT / "scripts" / "crosscheck" / "run.py")
    assert spec and spec.loader, "scripts/crosscheck/run.py 載入失敗"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compute_axis_a


@pytest.fixture(scope="module")
def results():
    if not RESULTS.exists():
        pytest.skip("crosscheck-results.json 不存在(先跑 scripts/crosscheck/run.py + venv313)")
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    if data.get("axis_b") is None:
        pytest.skip("Axis-B 未執行(venv313 缺;Axis-A-only 產出)")
    return data


_FORBIDDEN_PKGS = {"skidl", "kicad", "pyspice", "inspice"}  # top-level package(小寫;涵蓋 PySpice/InSpice — P5.3 實裝模擬器為 InSpice fork,漏列即 DEC-H4 破洞)


def _forbidden_imports_in(source: str) -> set:
    """source 中 import 到的 forbidden top-level package(**AST**,非 line-regex)。

    涵蓋舊 line-regex 漏掉的形式:逗號式 `import os, skidl`、`import skidl as s`、
    submodule `from kicad.pcbnew import X`。註解/字串內提及 .kicad_mod 不算 import → 合法。
    """
    found: set = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0].lower() for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:  # 絕對 import 才有 module 名
            found.add((node.module or "").split(".")[0].lower())
    return found & _FORBIDDEN_PKGS


def test_firewall_no_forbidden_import_in_lib():
    """DEC-H4:lib/ 不得 import skidl/kicad/pyspice(**import 級**,非文字級;註解引 .kicad_mod 合法)。"""
    offenders = []
    for p in (ROOT / "lib").rglob("*.py"):
        try:
            hit = _forbidden_imports_in(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            offenders.append(f"{p.relative_to(ROOT)}: 無法解析({e})")
            continue
        if hit:
            offenders.append(f"{p.relative_to(ROOT)}: import {sorted(hit)}")
    assert not offenders, "lib/ 出現防火牆外 import(應在 scripts/crosscheck/ 等防火牆外):\n" + "\n".join(offenders)


def test_firewall_detects_comma_and_submodule_forms():
    """回歸(重驗確認 REAL):AST 防火牆須抓到舊 line-regex 漏掉的形式 ——
    逗號式 `import os, skidl`、`import pyspice as ps`、submodule `from kicad.x import Y`。"""
    src = "import os, skidl\nimport pyspice as ps\nfrom kicad.pcbnew import Board\nfrom InSpice.Unit import u_V\n"
    assert _forbidden_imports_in(src) == {"skidl", "pyspice", "kicad", "inspice"}
    # 合法:註解/字串提及不算 import;相對 import 與非 forbidden 套件不誤報。
    assert _forbidden_imports_in("# uses skidl elsewhere\nx = 'kicad_mod'\nimport os\n") == set()


def test_axis_b_agrees_with_axis_a(results):
    """两軸對 auto_waterer 隔離判定 + 兩地 node-set 各自獨立導出且一致。"""
    assert results["agree"] is True, "两軸隔離判定不一致"
    assert results["node_sets_equal"] is True, "两軸兩地 node-set 不相等(獨立重建有歧異)"
    assert results["axis_a"]["isolation_pass"] is True
    assert results["axis_b"]["isolation_pass"] is True


def test_axis_b_catches_bonded_ground_mutant(results):
    """Axis-B 對綁地 mutant(負載地接回控制地)必抓到 → 證 gate 非恆綠。"""
    assert results["mutant"]["axis_b_caught"] is True, "Axis-B 未抓到綁地 mutant"


def test_freshness_hash_matches_current_netlist(results):
    """freshness(N2):results 的 input_hash 須等於當前 build_netlist 重算值,防吃舊資料矇混。"""
    compute_axis_a = _load_compute_axis_a()
    current = compute_axis_a()["input_hash"]
    assert results.get("input_hash") == current, (
        f"crosscheck-results 過時:results={results.get('input_hash')} vs 當前={current}"
        "(netlist 已變,請重跑 scripts/crosscheck/run.py 更新交叉驗證)")


def _load_run_module():
    spec = importlib.util.spec_from_file_location(
        "xcheck_run_full", ROOT / "scripts" / "crosscheck" / "run.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_no_venv_preserves_populated_witness(tmp_path, monkeypatch):
    """回歸守衛:無 venv313 時 main() 不得以 axis_b=null 覆寫已含 Axis-B 的 committed witness。

    缺陷史:原 no-venv 分支無條件 write_text 覆寫 committed witness 成 null + return 0,乾淨環境
    一跑即毀掉已驗 witness,gate 退化成 skip-by-default,且 repo 非 git 不可復原。"""
    mod = _load_run_module()
    witness = tmp_path / "crosscheck-results.json"
    good = {"demo": "auto_waterer", "axis_a": {"x": 1}, "axis_b": {"isolation_pass": True},
            "agree": True, "node_sets_equal": True, "mutant": {"axis_b_caught": True},
            "input_hash": "deadbeef"}
    witness.write_text(json.dumps(good), encoding="utf-8")
    monkeypatch.setattr(mod, "RESULTS", witness)
    monkeypatch.setattr(mod, "ART", tmp_path / "_artifacts")
    monkeypatch.setenv("CDV_VENV313", str(tmp_path / "nonexistent" / "python.exe"))
    assert mod.main() == 0
    preserved = json.loads(witness.read_text(encoding="utf-8"))
    assert preserved["axis_b"] == {"isolation_pass": True}, "已驗 witness 被覆寫(回歸!)"
    assert preserved["agree"] is True


def test_no_venv_no_witness_writes_artifacts_not_committed(tmp_path, monkeypatch):
    """無 venv313 且無既有 witness:降級輸出只寫 _artifacts/,不得寫 committed 路徑
    (否則 committed witness 假性存在,in-repo gate 不再 skip 而吃到 null)。"""
    mod = _load_run_module()
    witness = tmp_path / "crosscheck-results.json"  # 不存在
    art = tmp_path / "_artifacts"
    monkeypatch.setattr(mod, "RESULTS", witness)
    monkeypatch.setattr(mod, "ART", art)
    monkeypatch.setenv("CDV_VENV313", str(tmp_path / "nope" / "python.exe"))
    assert mod.main() == 0
    assert not witness.exists(), "無 venv + 無既有 witness 時不得寫 committed 路徑"
    assert (art / "crosscheck-results.axis-a-only.json").exists(), "降級輸出應寫 _artifacts/"
