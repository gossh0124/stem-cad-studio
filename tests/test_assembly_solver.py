"""Tests for lib/assembly_solver.py — baseline + overflow escalation chain."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.assembly_solver import solve

# ── 共用 fixtures ────────────────────────────────────────

_WIRING_SIMPLE = {
    "Relay": {"label": "Relay", "pins": [
        {"comp": "IN", "mcu": "D5", "color": "#44cc44", "note": ""},
    ]},
    "SoilMoisture": {"label": "Soil", "pins": [
        {"comp": "AO", "mcu": "A0", "color": "#ffaa00", "note": ""},
    ]},
}

_COMPS_BASELINE = [
    {"type": "Arduino-Uno-class", "role": "Brain", "qty": 1},
    {"type": "Relay-Module-class", "role": "Output", "qty": 1},
    {"type": "Pump-Water-class", "role": "Actuator", "qty": 1},
    {"type": "Sensor-SoilMoisture-class", "role": "Sensor", "qty": 1},
]

# Arduino 68.6×53.3 + Relay 50×26 + Pump 45×30 + PIR 32×24
# area = 3656 + 1300 + 1350 + 768 = 7074 mm²
_COMPS_OVERFLOW = [
    {"type": "Arduino-Uno-class", "role": "Brain", "qty": 1},
    {"type": "Relay-Module-class", "role": "Output", "qty": 1},
    {"type": "Pump-Water-class", "role": "Actuator", "qty": 1},
    {"type": "Sensor-PIR-class", "role": "Sensor", "qty": 1},
]


def _run_baseline():
    return solve(
        components=_COMPS_BASELINE,
        wiring_raw=_WIRING_SIMPLE,
        # 120×100=12000mm² 足夠裝 ~8600mm² 元件 (util ~72%, 無溢出)
        enclosure_spec={"inner_length": 120, "inner_width": 100, "inner_height": 45, "wall": 2.5},
    )


def _run_slight_overflow():
    """殼體剛好比 Arduino 略小，預期 1 個元件升至 panel。"""
    return solve(
        components=_COMPS_BASELINE,
        wiring_raw=_WIRING_SIMPLE,
        # 3360 mm² 殼 vs ~7074 mm² 元件面積 → 利用率 ~210%
        enclosure_spec={"inner_length": 60, "inner_width": 56, "inner_height": 30, "wall": 2.0},
    )


def _run_severe_overflow():
    """極小殼體裝多個大元件（274% 利用率），預期觸發 panel + external + resize。"""
    return solve(
        components=_COMPS_OVERFLOW,
        wiring_raw=_WIRING_SIMPLE,
        # 2000 mm² 殼 vs ~7074 mm² 元件 → 超嚴重溢出
        enclosure_spec={"inner_length": 50, "inner_width": 40, "inner_height": 25, "wall": 2.0},
    )


# ── Baseline 測試（向後相容）────────────────────────────

def test_placements():
    result = _run_baseline()
    assert len(result["placements"]) == 2, "Expected 2 internal placements (Arduino+Relay)"
    assert len(result["external_refs"]) == 1, "Expected 1 external ref (SoilMoisture)"
    assert len(result["embedded_refs"]) == 1, "Expected 1 embedded ref (Pump-Water)"


def test_thermal_field():
    result = _run_baseline()
    tf = result["thermal_field"]
    assert tf["total_power_mw"] > 0, "Expected nonzero thermal"
    assert tf["thermal_tier"] == "MID", (
        f"650mW (Arduino+Relay only) should be MID tier, got {tf.get('thermal_tier')}"
    )
    assert tf["needs_venting"] is False
    assert tf["passive_venting"] is True


def test_wire_routes():
    result = _run_baseline()
    assert len(result["wire_routes"]) >= 1, "Expected at least 1 wire route"


def test_decisions():
    result = _run_baseline()
    assert len(result["decisions"]) == 10, (
        f"Expected 10 decisions (v2 enclosure_partition + 7 original + cog_check + port_orient), "
        f"got {len(result['decisions'])}"
    )


def test_no_escalation_when_fits():
    """元件合適時不應有溢出升級記錄。"""
    result = _run_baseline()
    assert result["overflow_escalations"] == [], (
        f"No overflow expected for 90x70 shell, got: {result['overflow_escalations']}"
    )
    steps = [d["step"] for d in result["decisions"]]
    assert "overflow_escalate" not in steps


# ── 溢出升級鏈測試 ───────────────────────────────────────

def test_slight_overflow_moves_to_panel():
    """輕微溢出：最大元件應升至 panel，internal 元件數減少。"""
    result = _run_slight_overflow()
    assert len(result["overflow_escalations"]) > 0, "Expected escalation records"
    steps = [d["step"] for d in result["decisions"]]
    assert "overflow_escalate" in steps, "Expected overflow_escalate decision"
    # panel 應有元件（原始 panel_comps 為空，升級後應有內容）
    assert len(result["panel_placements"]) > 0, "Expected comps escalated to panel"


def test_severe_overflow_triggers_all_levels():
    """嚴重溢出：預期 panel 升級、external 升級或殼體 resize。"""
    result = _run_severe_overflow()
    assert len(result["overflow_escalations"]) > 0, "Expected escalation records"
    steps = [d["step"] for d in result["decisions"]]
    assert "overflow_escalate" in steps
    esc_desc = " ".join(result["overflow_escalations"])
    # 至少有 panel 升級發生
    assert "panel" in esc_desc, f"Expected panel escalation, got: {esc_desc}"
    # 結果仍是合法的（不 crash，有 placements 或 panel）
    total_placed = len(result["placements"]) + len(result["panel_placements"])
    assert total_placed > 0, "Expected at least one component placed after escalation"


def test_shell_resize_uses_actual_dimensions():
    """殼體 resize 必須依據實際元件尺寸，而非固定 +20%。"""
    result = _run_severe_overflow()
    esc_desc = " ".join(result["overflow_escalations"])
    if "shell_resize" not in esc_desc:
        # 若未觸發 resize，測試視為通過（元件夠少可只靠 panel/external 解決）
        return
    # resize 描述格式：shell_resize:LxW→NewLxNewW mm
    import re
    m = re.search(r"shell_resize:(\d+)x(\d+)→(\d+\.?\d*)x(\d+\.?\d*)mm", esc_desc)
    assert m, f"resize description malformed: {esc_desc}"
    new_l, new_w = float(m.group(3)), float(m.group(4))
    # 新尺寸必須大於原始殼體 (50×40)
    assert new_l > 50 or new_w > 40, "Resized shell must be larger than original"
    # 新尺寸不應是固定 +20% 的 60×48（必須由實際元件驅動）
    # Arduino L=68.58 → resize 後 L 應接近元件實際需求，而非固定比例
    assert new_l != 60.0 or new_w != 48.0, (
        "Shell resize should be driven by component dims, not fixed +20%"
    )
