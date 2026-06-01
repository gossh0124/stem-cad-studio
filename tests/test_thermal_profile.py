"""Z1.5 thermal profile self-test — 跨 4 MCU + 6 modules + 5 mounts 驗證熱源資料完整性。"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3
from lib.pcb.esp32_devkit_v1 import ESP32_DEVKIT_V1
from lib.pcb.microbit_v2 import MICROBIT_V2
from lib.pcb.raspberry_pi_4b import RASPBERRY_PI_4B
from lib.pcb.modules import ALL_MODULES
from lib.cad.mounts import ALL_MOUNTS


PCB_BOARDS = (
    ('Tier-1', ARDUINO_UNO_R3),
    ('Tier-1', ESP32_DEVKIT_V1),
    ('Tier-1', MICROBIT_V2),
    ('Tier-1', RASPBERRY_PI_4B),
)


def assert_thermal_present(spec, label: str) -> int:
    """檢查 PCBSpec 至少一個 sub_component 有 thermal_typical_mw > 0。"""
    typ_total = spec.total_thermal_mw('typical')
    if typ_total <= 0:
        print(f'  ❌ {label} 無熱源資料')
        return 1
    print(f'  ✅ {spec.name:35s} typ={typ_total:7.0f}mW '
          f'idle={spec.total_thermal_mw("idle"):7.0f}mW '
          f'peak={spec.total_thermal_mw("peak"):7.0f}mW')
    return 0


def assert_mount_thermal(class_name: str, builder_kind: str, spec_obj) -> int:
    """檢查 mount spec 有 thermal_typical_mw 欄位且 > 0。"""
    typ = getattr(spec_obj, 'thermal_typical_mw', 0)
    if typ <= 0:
        print(f'  ❌ {class_name} ({builder_kind}) 無熱源資料')
        return 1
    print(f'  ✅ {class_name:25s} ({builder_kind:18s}) typ={typ:6.0f}mW '
          f'idle={spec_obj.thermal_idle_mw:5.0f}mW '
          f'peak={spec_obj.thermal_peak_mw:6.0f}mW')
    return 0


def main() -> int:
    failures = 0

    print('=== Tier 1：MCU 主板 ===')
    for tier, spec in PCB_BOARDS:
        failures += assert_thermal_present(spec, tier)

    print('\n=== Tier 2：感測 / 顯示 / 致動模組 ===')
    for class_name, mod in ALL_MODULES.items():
        failures += assert_thermal_present(mod, class_name)

    print('\n=== Tier 4：機械接合件（內嵌設備熱源） ===')
    from lib.cad.mounts import DEFAULT_MOUNT_SPECS
    for class_name, (kind, label, builder) in ALL_MOUNTS.items():
        failures += assert_mount_thermal(class_name, kind, DEFAULT_MOUNT_SPECS[kind])

    print('\n=== 總結 ===')
    if failures:
        print(f'❌ {failures} 個元件缺熱源資料')
        return 1
    print('✅ 全部 4 MCU + 6 模組 + 5 mounts 熱源資料齊全')
    return 0


if __name__ == '__main__':
    sys.exit(main())


# --- ADR-6 / ADR-4 unit tests (pytest) ---
import math
import pytest
from lib.assembly_solver._types import (
    _Comp, _Decision,
    THERMAL_TIER_LOW, THERMAL_TIER_MID,
    _H_CONV_W_M2K, _AMBIENT_C, _INFLUENCE_RADIUS_CAP_MM,
    _ACTIVE_FAN_CFM, _COLOR_LUT_DEFAULT,
)
from lib.assembly_solver.thermal import _validate_thermal


def _make_comp(type_: str, thermal_mw: float, L=20, W=15, H=10,
               x=10.0, y=20.0) -> _Comp:
    return _Comp(
        type=type_, role="sensor", L=L, W=W, H=H,
        weight_g=5.0, thermal_mw=thermal_mw, ports=[],
        x=x, y=y,
    )


class TestThermalOverlayADR6:
    """ADR-6: V3 thermal overlay schema population."""

    def test_thermal_overlay_present_in_result(self):
        comps = [_make_comp("DCMotor", 800)]
        decisions: list = []
        result = _validate_thermal(comps, None, decisions)
        assert "thermal_overlay" in result

    def test_thermal_overlay_heat_sources_structure(self):
        comps = [_make_comp("DCMotor", 1000, x=5.0, y=10.0)]
        decisions: list = []
        result = _validate_thermal(comps, None, decisions)
        overlay = result["thermal_overlay"]
        assert len(overlay["heat_sources"]) == 1
        src = overlay["heat_sources"][0]
        assert src["type"] == "DCMotor"
        assert src["position"] == [5.0, 10.0, 0.0]
        assert src["thermal_mw"] == 1000.0
        assert "surface_temp_c" in src
        assert "influence_radius_mm" in src

    def test_surface_temp_calculation(self):
        comp = _make_comp("Heater", 2000, L=20, W=15, H=10)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        src = result["thermal_overlay"]["heat_sources"][0]
        # Manual: A = 2*(20*15 + 20*10 + 15*10) = 2*(300+200+150) = 1300 mm^2 = 0.0013 m^2
        # dT = (2000/1000) / (7.0 * 0.0013) = 2 / 0.0091 = 219.78
        # surface_temp = 25 + 219.78 = 244.78
        expected_a = 2 * (20*15 + 20*10 + 15*10) / 1e6
        expected_temp = _AMBIENT_C + (2000/1000.0) / (_H_CONV_W_M2K * expected_a)
        assert abs(src["surface_temp_c"] - round(expected_temp, 1)) < 0.1

    def test_influence_radius_formula(self):
        comp = _make_comp("LED", 200)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        src = result["thermal_overlay"]["heat_sources"][0]
        expected_r = math.sqrt(200 / 50.0) * 10.0
        assert abs(src["influence_radius_mm"] - round(expected_r, 1)) < 0.1

    def test_influence_radius_capped(self):
        comp = _make_comp("BigMotor", 5000)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        src = result["thermal_overlay"]["heat_sources"][0]
        assert src["influence_radius_mm"] == _INFLUENCE_RADIUS_CAP_MM

    def test_color_lut_present(self):
        comps = [_make_comp("Sensor", 100)]
        decisions: list = []
        result = _validate_thermal(comps, None, decisions)
        overlay = result["thermal_overlay"]
        assert overlay["color_lut"] == _COLOR_LUT_DEFAULT
        assert overlay["ambient_c"] == _AMBIENT_C

    def test_estimated_dt_matches_shell(self):
        comp = _make_comp("MCU", 600)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions,
                                   inner_l=80, inner_w=60, inner_h=40)
        overlay = result["thermal_overlay"]
        a_shell = 2 * (80*60 + 80*40 + 60*40) / 1e6
        expected_dt = (600/1000.0) / (_H_CONV_W_M2K * a_shell)
        assert abs(overlay["estimated_dt_c"] - round(expected_dt, 1)) < 0.1


class TestAirflowOverlayADR4:
    """ADR-4: Airflow overlay data based on thermal tier."""

    def test_low_tier_no_airflow(self):
        comp = _make_comp("LED", 100)  # < 500 mW → LOW
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        assert "airflow_overlay" not in result

    def test_mid_tier_passive_airflow(self):
        comp = _make_comp("Motor", 800)  # 500-1500 → MID
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        assert "airflow_overlay" in result
        af = result["airflow_overlay"]
        assert af["mode"] == "passive"
        assert "vent_count" in af
        assert af["vent_count"] >= 1
        assert "vent_positions" in af

    def test_high_tier_active_airflow(self):
        comp = _make_comp("BigMotor", 2000)  # > 1500 → HIGH
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        assert "airflow_overlay" in result
        af = result["airflow_overlay"]
        assert af["mode"] == "active"
        assert af["cfm"] == _ACTIVE_FAN_CFM
        assert len(af["fan_position"]) == 3

    def test_high_tier_fan_position_centered(self):
        comp = _make_comp("BigMotor", 2000)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions,
                                   inner_l=100, inner_w=80, inner_h=50)
        af = result["airflow_overlay"]
        assert af["fan_position"] == [50.0, 40.0, 45.0]

    def test_existing_keys_preserved(self):
        comp = _make_comp("Motor", 800)
        decisions: list = []
        result = _validate_thermal([comp], None, decisions)
        # Original keys still present
        assert "heat_sources" in result
        assert "total_power_mw" in result
        assert "thermal_tier" in result
        assert "needs_venting" in result
        assert "passive_venting" in result
        assert "vent_placements" in result
