"""test_snap_fit_defaults.py — VS-PV5 回歸保護：build_pcb_two_piece 預設參數
必須通過 PV5 snap-fit 應力 gate（否則所有 MCU 殼體生成失敗）。

用 inspect 讀實際預設值——預設若再被改壞，此測試自動抓到。
"""
import inspect

from lib.cad.shell import build_pcb_two_piece
from lib.cad.shell.shell_spec import validate_snap_fit_stress


def _defaults() -> dict:
    p = inspect.signature(build_pcb_two_piece).parameters
    return {
        "t": p["snap_arm_t"].default,
        "h": p["snap_arm_h"].default,
        "lip": p["snap_lip_d"].default,
        "mat": p["material"].default,
    }


def test_default_snap_params_pass_pv5():
    d = _defaults()
    r = validate_snap_fit_stress(d["t"], d["h"], d["lip"], d["mat"])
    assert r["ok"], (
        f"預設 snap-fit 參數過不了 PV5：t={d['t']} h={d['h']} lip_d={d['lip']} "
        f"{d['mat']} → util={r['utilization_pct']}% > 70%。{r.get('suggestions')}"
    )


def test_default_has_safety_margin():
    # 預設應留合理邊際（util < 60%），不該剛好卡在 70% 邊緣
    d = _defaults()
    r = validate_snap_fit_stress(d["t"], d["h"], d["lip"], d["mat"])
    assert r["utilization_pct"] < 60, f"預設邊際過小: util={r['utilization_pct']}%"


def test_petg_also_passes_with_defaults():
    # PETG（韌性更好）用預設幾何也必須通過
    d = _defaults()
    r = validate_snap_fit_stress(d["t"], d["h"], d["lip"], "PETG")
    assert r["ok"]
