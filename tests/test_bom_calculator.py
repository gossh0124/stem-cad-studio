"""Tests for lib/bom_calculator.py."""
import pytest

from lib.bom_calculator import calculate_bom, BomSummary


class TestCalculateBom:
    def test_empty_components(self):
        result = calculate_bom([])
        assert result.total_ma == 0.0
        assert result.total_ntd == 0
        assert result.rows == []
        assert result.supply_v == 5.0

    def test_single_component_uses_lookup(self):
        comps = [{"type": "Motor-Servo-class", "role": "Actuator", "qty": 1}]
        result = calculate_bom(comps)
        assert result.total_ma > 0
        assert result.total_ntd > 0
        assert len(result.rows) == 1

    def test_qty_multiplies(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 3}]
        result = calculate_bom(comps)
        row = result.rows[0]
        assert row["total_ma"] == row["unit_ma"] * 3
        assert row["total_ntd"] == row["unit_ntd"] * 3

    def test_power_component_sets_supply(self):
        comps = [
            {"type": "Battery-AA-class", "role": "Power", "qty": 1},
            {"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1},
        ]
        result = calculate_bom(comps)
        assert result.power_type == "Battery-AA-class"

    def test_default_power_type_usb(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps)
        assert result.power_type == "USB-5V-class"

    def test_result_is_named_tuple(self):
        result = calculate_bom([])
        assert isinstance(result, BomSummary)
        assert hasattr(result, 'rows')
        assert hasattr(result, 'total_ma')
        assert hasattr(result, 'current_budget_ma')

    def test_multiple_components_sum(self):
        comps = [
            {"type": "Motor-Servo-class", "role": "Actuator", "qty": 1},
            {"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 2},
        ]
        result = calculate_bom(comps)
        expected = sum(r["total_ma"] for r in result.rows)
        assert abs(result.total_ma - expected) < 0.01

    def test_unknown_type_raises(self):
        comps = [{"type": "NonExistentSensor-XYZ", "role": "Sensor", "qty": 1}]
        with pytest.raises(ValueError):
            calculate_bom(comps)

    def test_label_falls_back_to_type(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps)
        assert result.rows[0]["label"] == "Lighting-LED-RGB-class"

    def test_label_uses_provided(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1, "label": "Red LED"}]
        result = calculate_bom(comps)
        assert result.rows[0]["label"] == "Red LED"


class TestCalculateBomPassives:
    """被動元件 BOM 追加行為（step3）。"""

    # ── 共用 wiring fixtures ─────────────────────────────────────
    _wiring_external = {
        "LED1": {
            "pins": [
                {
                    "comp": "A",
                    "mcu": "D3",
                    "passive": {
                        "kind": "R",
                        "value": "220R",
                        "topo": "series",
                        "location": "external",
                        "purchasable": True,
                        "refdes": "R1",
                    },
                }
            ],
            "decoupling": [],
        }
    }

    _wiring_onboard = {
        "MCU1": {
            "pins": [],
            "decoupling": [
                {
                    "kind": "C",
                    "value": "100nF",
                    "topo": "decoupling",
                    "location": "onboard",
                    "purchasable": False,
                    "refdes": "C1",
                }
            ],
        }
    }

    _wiring_mixed = {
        "LED1": {
            "pins": [
                {
                    "comp": "A",
                    "mcu": "D3",
                    "passive": {
                        "kind": "R",
                        "value": "220R",
                        "topo": "series",
                        "location": "external",
                        "purchasable": True,
                        "refdes": "R1",
                    },
                }
            ],
            "decoupling": [],
        },
        "MCU1": {
            "pins": [],
            "decoupling": [
                {
                    "kind": "C",
                    "value": "100nF",
                    "topo": "decoupling",
                    "location": "onboard",
                    "purchasable": False,
                    "refdes": "C1",
                }
            ],
        },
    }

    # ── 測試：無 wiring 時行為不變（向後相容）──────────────────
    def test_no_wiring_no_passive_rows(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert passive_rows == []

    # ── 測試：被動行存在 ────────────────────────────────────────
    def test_passive_row_appended(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps, wiring=self._wiring_external)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert len(passive_rows) == 1
        assert passive_rows[0]["type"] == "R"

    # ── 測試：被動零功耗 ────────────────────────────────────────
    def test_passive_zero_power(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps, wiring=self._wiring_external)
        for row in result.rows:
            if row.get("role") == "Passive":
                assert row["unit_ma"] == 0.0
                assert row["total_ma"] == 0.0

    # ── 測試：total_ma 不因被動改變（回歸保護）──────────────────
    def test_total_ma_unchanged_by_passives(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result_no_wiring = calculate_bom(comps)
        result_with_wiring = calculate_bom(comps, wiring=self._wiring_external)
        assert result_no_wiring.total_ma == result_with_wiring.total_ma

    # ── 測試：onboard 不計成本（qty=0, total_ntd=0, note='已含於模組'）
    def test_onboard_passive_not_purchasable(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result = calculate_bom(comps, wiring=self._wiring_onboard)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert len(passive_rows) == 1
        row = passive_rows[0]
        assert row["purchasable"] is False
        assert row["qty"] == 0
        assert row["total_ntd"] == 0
        assert row["note"] == "已含於模組"

    # ── 測試：onboard 不計入 total_ntd ──────────────────────────
    def test_onboard_not_counted_in_total_ntd(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result_no_wiring = calculate_bom(comps)
        result_with_onboard = calculate_bom(comps, wiring=self._wiring_onboard)
        assert result_no_wiring.total_ntd == result_with_onboard.total_ntd

    # ── 測試：external 計入 total_ntd ───────────────────────────
    def test_external_passive_counted_in_total_ntd(self):
        comps = [{"type": "Lighting-LED-RGB-class", "role": "Display", "qty": 1}]
        result_no_wiring = calculate_bom(comps)
        result_with_ext = calculate_bom(comps, wiring=self._wiring_external)
        assert result_with_ext.total_ntd > result_no_wiring.total_ntd

    # ── 測試：external R unit_ntd=1（查 PASSIVE_CATALOG）────────
    def test_external_r_unit_ntd_from_catalog(self):
        comps = []
        result = calculate_bom(comps, wiring=self._wiring_external)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert passive_rows[0]["unit_ntd"] == 1
        assert passive_rows[0]["total_ntd"] == 1

    # ── 測試：混合 wiring（一 external + 一 onboard）──────────────
    def test_mixed_wiring_only_external_counts(self):
        comps = []
        result = calculate_bom(comps, wiring=self._wiring_mixed)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert len(passive_rows) == 2
        purchasable = [r for r in passive_rows if r["purchasable"]]
        not_purchasable = [r for r in passive_rows if not r["purchasable"]]
        assert len(purchasable) == 1
        assert len(not_purchasable) == 1
        assert result.total_ntd == purchasable[0]["unit_ntd"]

    # ── 測試：to_json 包裝格式（含頂層 "wiring" key）────────────
    def test_to_json_wrapper_format(self):
        wrapped = {"wiring": self._wiring_external, "other": "data"}
        comps = []
        result = calculate_bom(comps, wiring=wrapped)
        passive_rows = [r for r in result.rows if r.get("role") == "Passive"]
        assert len(passive_rows) == 1
