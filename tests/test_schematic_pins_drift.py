"""tests/test_schematic_pins_drift.py — P0.4：SCHEM_PINS drift gate + 假綠 meta-gate。

修復前 `derive_schematic_pins.py --check` 直接 return 0、從不 diff（false-green no-op）。
本測試證明修復後：乾淨樹 PASS；改壞輸出 / 元件意外掉出 → FAIL。
"""
import scripts.derive_schematic_pins as d


def test_check_passes_on_clean_tree():
    """乾淨樹:SSOT 衍生與磁碟一致、唯一缺漏在 WIP 白名單 → PASS。"""
    res = d.build()
    code, problems = d._check_problems(res)
    assert code == 0, problems


def test_check_detects_output_drift(tmp_path, monkeypatch):
    """meta-gate:改壞 schematic-pins.js → --check 必 FAIL（防假綠 no-op 回歸）。"""
    res = d.build()
    mutated = d._render_js(res["pins"]).replace('"nx"', '"nx_MUTANT"', 1)
    p = tmp_path / "schematic-pins.js"
    p.write_text(mutated, encoding="utf-8")
    monkeypatch.setattr(d, "_OUT", p)
    code, problems = d._check_problems(res)
    assert code == 1 and problems, "改壞的 schematic-pins.js 未被 --check 抓到"
    assert any("不符" in pr for pr in problems)


def test_check_fails_on_any_missing(tmp_path, monkeypatch):
    """DEC-T8(更正):任一元件無法衍生 → FAIL(無 WIP 容忍 fallback)。"""
    res = {"pins": {"Relay": [{"name": "VCC", "num": 1, "nx": 0.0, "ny": 0.0,
                               "side": "NORTH", "type": "PWR", "vd": None, "group": "H"}]},
           "missing": ["GhostComp(Some-class: 無 pin_layout)"]}
    p = tmp_path / "schematic-pins.js"
    p.write_text(d._render_js(res["pins"]), encoding="utf-8")  # drift=0,只留 missing 問題
    monkeypatch.setattr(d, "_OUT", p)
    code, problems = d._check_problems(res)
    assert code == 1
    assert any("無法衍生" in pr for pr in problems)


def test_no_components_missing_now():
    """移除 fallback + 修 deriver(driver dims)後,全 23 元件皆可衍生,0 missing。"""
    res = d.build()
    assert res["missing"] == [], f"仍有元件無法衍生(需補真實資料): {res['missing']}"
    assert len(res["pins"]) == 23
