"""tests/test_provenance_lint.py — P0.0：DEC-H7 provenance 凍結 gate + mutant 防回歸。

證明:① 當前樹 strict PASS(手填已凍結);② growth(新增手填)/spread(擴散到新檔)→ FAIL。
"""
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "tools"))
import provenance_lint as pl  # noqa: E402


def test_current_tree_frozen_passes():
    """當前樹:已知手填皆在宣告檔、未擴大 → 無違規。"""
    baseline = pl._load_baseline()
    assert pl.check(baseline) == [], "當前樹不該有 provenance 違規(手填已凍結於 baseline)"


def _synthetic(tmp_path: Path, comp_pins_entries: int, spread: bool):
    """在 tmp 建合成 v6 樹,回傳 (baseline, monkeypatch REPO)。"""
    (tmp_path / "v6" / "s").mkdir(parents=True)
    entries = "\n".join(f"    C{i}: {{ X:[0,.5] }}," for i in range(comp_pins_entries))
    (tmp_path / "v6" / "s" / "comp.js").write_text(
        f"const COMP_PINS = {{\n{entries}\n}};\n", encoding="utf-8")
    other = "const COMP_PINS = 1;\n" if spread else "// nothing\n"
    (tmp_path / "v6" / "s" / "other.js").write_text(other, encoding="utf-8")
    baseline = {
        "scan_globs": ["v6/**/*.js"],
        "handfill_loci": [{
            "id": "COMP_PINS", "file": "v6/s/comp.js", "symbol": "COMP_PINS",
            "detect": "const COMP_PINS = {", "block_open": "const COMP_PINS = {",
            "max_entries": 3, "entry_regex": r"^\s*[\w'\"+-]+:\s*\{",
            "allowed_files": ["v6/s/comp.js"], "purge_plan": "x",
        }],
    }
    return baseline


def test_growth_mutant_fails(tmp_path, monkeypatch):
    """COMP_PINS 區塊 entry 數超過上限(新增手填)→ growth 違規。"""
    monkeypatch.setattr(pl, "REPO", tmp_path)
    baseline = _synthetic(tmp_path, comp_pins_entries=5, spread=False)  # 5 > 上限 3
    viols = pl.check(baseline)
    assert any("growth" in v for v in viols), f"未抓到 growth:{viols}"


def test_spread_mutant_fails(tmp_path, monkeypatch):
    """COMP_PINS 擴散到未宣告檔 → spread 違規。"""
    monkeypatch.setattr(pl, "REPO", tmp_path)
    baseline = _synthetic(tmp_path, comp_pins_entries=2, spread=True)
    viols = pl.check(baseline)
    assert any("spread" in v for v in viols), f"未抓到 spread:{viols}"


def test_frozen_synthetic_passes(tmp_path, monkeypatch):
    """合成樹在上限內、未擴散 → PASS。"""
    monkeypatch.setattr(pl, "REPO", tmp_path)
    baseline = _synthetic(tmp_path, comp_pins_entries=3, spread=False)
    assert pl.check(baseline) == []
