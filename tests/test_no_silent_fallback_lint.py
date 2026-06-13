"""no_silent_fallback_lint 測試：Python AST + JS regex 偵測 + 豁免機制。"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "no_silent_fallback_lint", REPO / "tools" / "no_silent_fallback_lint.py")
nsf = importlib.util.module_from_spec(_spec)
sys.modules["no_silent_fallback_lint"] = nsf
_spec.loader.exec_module(nsf)

REQUIRED = {"inner_height", "pitch_mm", "x_mm"}
MARKER = "nofallback-ok"


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_py_detects_required_field_literal_default(tmp_path):
    p = _write(tmp_path, "a.py", 'x = spec.get("inner_height", 40)\n')
    hits = nsf._check_py(p, REQUIRED, MARKER)
    assert len(hits) == 1 and hits[0][0] == 1
    assert "inner_height" in hits[0][1]


def test_py_ignores_none_default(tmp_path):
    # 缺值回 None 待檢查，非頂替
    p = _write(tmp_path, "b.py", 'x = spec.get("inner_height", None)\n')
    assert nsf._check_py(p, REQUIRED, MARKER) == []


def test_py_ignores_non_required_field(tmp_path):
    p = _write(tmp_path, "c.py", 'x = spec.get("subdir", "/tmp")\n')
    assert nsf._check_py(p, REQUIRED, MARKER) == []


def test_py_exemption_marker_silences(tmp_path):
    p = _write(tmp_path, "d.py",
               'x = spec.get("inner_height", 40)  # nofallback-ok: legacy demo bridge\n')
    assert nsf._check_py(p, REQUIRED, MARKER) == []


def test_py_detects_dict_and_negative_literal(tmp_path):
    p = _write(tmp_path, "e.py",
               'a = d.get("pitch_mm", {})\nb = d.get("x_mm", -1)\n')
    hits = nsf._check_py(p, REQUIRED, MARKER)
    assert {h[0] for h in hits} == {1, 2}


def test_js_detects_color_and_nullish_and_object(tmp_path):
    p = _write(tmp_path, "f.js",
               "const c = p.color || '#888';\n"
               "const pitch = hg.pitch_mm ?? 2.54;\n"
               "const spec = COMP_SPECS[k] || { label: k };\n"
               "const w = dims ? dims[0] : 130;\n")
    hits = nsf._check_js(p, MARKER)
    assert {h[0] for h in hits} == {1, 2, 3, 4}


def test_js_exemption_marker_silences(tmp_path):
    p = _write(tmp_path, "g.js",
               "const c = p.color || '#888'; // nofallback-ok: optional accent\n")
    assert nsf._check_js(p, MARKER) == []


def test_js_ignores_plain_logical_or(tmp_path):
    # `|| identifier` / `|| true` 非魔術字面頂替形，不報
    p = _write(tmp_path, "h.js", "const ok = a || b;\nconst flag = x || true;\n")
    assert nsf._check_js(p, MARKER) == []
