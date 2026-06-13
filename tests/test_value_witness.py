"""tests/test_value_witness.py — P5.2 flyback value witness in-repo gate(DEC-H2/T6/H4)。

防火牆(DEC-H4):本檔**不** import inspice/pyspice;只讀 `crossverify/value-witness.json`
+ 以 repo 純碼重算輸入 hash 驗 freshness。witness 由 `python crossverify/run_value_witness.py`
(需 venv313 + KiCad ngspice.dll)產生;缺檔 → skip(lean CI 無模擬器)。

witness 物理(全為真實官方值):SRD-05VDC 線圈 R=70Ω(Songle datasheet,與 verified.json
收斂)、1N4007 model(BV=1000V 官方)、ATmega328P abs-max=VCC+0.5=5.5V(Microchip)。
L 無公開值 → 10/25/70 mH 整量級掃描,verdict 須對全範圍成立(L-不敏感機器驗證)。
"""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "crossverify" / "value-witness.json"


def _load_compute_inputs():
    """路徑載入 run_value_witness.compute_inputs(單一 hash 來源,不複製規範化邏輯)。"""
    spec = importlib.util.spec_from_file_location(
        "value_witness_run", ROOT / "crossverify" / "run_value_witness.py")
    assert spec and spec.loader, "crossverify/run_value_witness.py 載入失敗"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.compute_inputs


@pytest.fixture(scope="module")
def witness():
    if not RESULTS.exists():
        pytest.skip("value-witness.json 不存在(先跑 crossverify/run_value_witness.py + venv313)")
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not data.get("sweep"):
        pytest.skip("witness 無模擬結果(venv313 缺;inputs-only 降級)")
    return data


def test_clamp_contract_all_sweep(witness):
    """箝位契約:全 L 掃描的箝位峰值 ≤ Vdd + Vf_max(二極體把 V=L·di/dt 含在一個壓降內)。"""
    assert witness["pass"] is True
    bound = witness["supply_v"] + witness["vf_max_v"]
    for row in witness["sweep"]:
        assert row["clamp_ok"], row
        assert row["clamped_peak_v"] <= bound, (
            f"L={row['l_mh']}mH 箝位峰值 {row['clamped_peak_v']}V > {bound}V")


def test_mutant_nonvacuous(witness):
    """非真空:拔掉二極體的 mutant 必須超 MCU abs-max(否則 gate 恆綠無意義)。
    這同時是教育 verdict 的物理依據:沒有 flyback 二極體,kickback 必然超標。"""
    assert witness["mutant_nonvacuous"] is True
    for row in witness["sweep"]:
        assert row["mutant_exceeds_abs_max"], row
        assert row["unclamped_peak_v"] > witness["abs_max_v"], row
        # 未箝位峰值須遠大於箝位(量級差,證明箝位真的在工作)
        assert row["unclamped_peak_v"] > 10 * row["clamped_peak_v"], row


def test_l_insensitivity(witness):
    """L-不敏感:箝位峰值跨 10→70 mH 整量級變動 < 0.1V —— 機器證明 verdict 不依賴
    Songle datasheet 未公開的線圈電感(use-real-official-values:不捏單值,掃描證不變)。"""
    assert witness["l_insensitivity_v"] < 0.1, (
        f"箝位峰值對 L 敏感({witness['l_insensitivity_v']}V),掃描宣告失效")
    l_values = [r["l_mh"] for r in witness["sweep"]]
    assert max(l_values) >= 7 * min(l_values), "掃描須跨量級(≥7×)才足以宣稱 L-不敏感"


def test_real_official_values_traceable(witness):
    """輸入溯源:witness 線圈電阻與 verified.json SSOT 收斂(70Ω,Songle datasheet)。"""
    assert abs(witness["coil_r_ohm"] - 70.0) <= 3.0
    assert witness["abs_max_v"] == 5.5  # Microchip ATmega328P: VCC+0.5 @ VCC=5.0
    assert witness["supply_v"] == 5.0


def test_freshness_hash_matches_current_inputs(witness):
    """freshness(N2):witness 的 input_hash 須等於當前輸入重算值,防吃舊資料矇混。"""
    compute_inputs = _load_compute_inputs()
    current = compute_inputs()["input_hash"]
    assert witness.get("input_hash") == current, (
        f"value-witness 過時:witness={witness.get('input_hash')} vs 當前={current}"
        "(輸入已變,請重跑 crossverify/run_value_witness.py)")
