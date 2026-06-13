"""Tests for lib/specs.py — component specs data consistency."""
from __future__ import annotations

import pytest

from lib.specs import (
    POWER_MA,
    PRICE_NTD,
    VOLTAGE_V,
    SUPPLY_V,
    POWER_BUDGET_MA,
    STALL_MA,
    WEIGHT_G,
    THERMAL_MW,
    COMPONENT_NAME_ALIASES,
    COMPONENT_SHORTHAND_ALIASES,
    BOM_URLS,
    lookup_constant,
    resolve_component_alias,
)


class TestPowerMa:
    """POWER_MA loaded from cache has correct structure."""

    def test_non_empty(self):
        assert len(POWER_MA) > 10

    def test_all_values_positive(self):
        for k, v in POWER_MA.items():
            assert v >= 0, f"{k} has negative power: {v}"

    def test_known_components_present(self):
        for comp in ("Arduino-Uno-class", "ESP32-class", "Sensor-PIR-class"):
            assert comp in POWER_MA, f"{comp} missing from POWER_MA"


class TestPriceNtd:
    """PRICE_NTD has reasonable values."""

    def test_non_empty(self):
        assert len(PRICE_NTD) > 20

    def test_all_positive(self):
        for k, v in PRICE_NTD.items():
            assert v > 0, f"{k} has non-positive price: {v}"

    def test_known_component(self):
        assert PRICE_NTD["Arduino-Uno-class"] == 250


class TestVoltageV:
    """VOLTAGE_V has valid voltage ranges."""

    def test_non_empty(self):
        assert len(VOLTAGE_V) > 20

    def test_reasonable_range(self):
        for k, v in VOLTAGE_V.items():
            assert 1.0 <= v <= 24.0, f"{k} voltage {v}V out of range"

    def test_arduino_5v(self):
        assert VOLTAGE_V["Arduino-Uno-class"] == 5.0

    def test_esp32_3v3(self):
        assert VOLTAGE_V["ESP32-class"] == 3.3


class TestSupplyV:
    """SUPPLY_V for power sources."""

    def test_non_empty(self):
        assert len(SUPPLY_V) >= 3

    def test_usb_5v(self):
        assert SUPPLY_V["USB-5V-class"] == 5.0

    def test_lipo_3v7(self):
        assert SUPPLY_V["Battery-LiPo-class"] == 3.7

    def test_reads_through_same_as_voltage_v(self):
        """B1:SUPPLY_V 對 in-SSOT 電源 class == VOLTAGE_V(同讀穿源 verified.json,零漂移)。
        先前 SUPPLY_V 為手刻字典(與 verified.json 電壓重複);改 _section("supply_v") 後不得漂移。"""
        from lib.specs import VOLTAGE_V
        for cls in ("USB-5V-class", "USB-Adapter-class", "AC-Adapter-class",
                    "Battery-AA-class", "Battery-LiPo-class"):
            assert cls in SUPPLY_V, f"{cls} 未讀穿進 SUPPLY_V"
            assert SUPPLY_V[cls] == VOLTAGE_V[cls], (
                f"{cls}: SUPPLY_V={SUPPLY_V[cls]} != VOLTAGE_V={VOLTAGE_V[cls]}(漂移)")

    def test_fallback_supply_v_only_for_absent_classes(self):
        """B1:_fallback.supply_v 只補 verified.json 缺項的 alias variant,不得遮蔽 in-SSOT class。"""
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent
        vj = json.loads((root / "data" / "component_datasheet_verified.json").read_text(encoding="utf-8"))
        cache = json.loads((root / "data" / "_component_specs_cache.json").read_text(encoding="utf-8"))
        for cls in cache.get("_fallback", {}).get("supply_v", {}):
            if cls.startswith("_"):
                continue
            assert cls not in vj, f"{cls} 在 verified.json 卻被 _fallback.supply_v 遮蔽"
            assert cls in SUPPLY_V, f"{cls} 在 _fallback 卻未進 SUPPLY_V"


class TestPowerBudget:
    """POWER_BUDGET_MA has reasonable current budgets."""

    def test_usb_500ma(self):
        assert POWER_BUDGET_MA["USB-5V-class"] == 500.0

    def test_lipo_higher_than_usb(self):
        assert POWER_BUDGET_MA["Battery-LiPo-class"] > POWER_BUDGET_MA["USB-5V-class"]


class TestStallMa:
    """STALL_MA for motors/pumps."""

    def test_motor_present(self):
        assert "Motor-Servo-class" in STALL_MA
        assert "Motor-DC-class" in STALL_MA

    def test_all_positive(self):
        for k, v in STALL_MA.items():
            assert v > 0, f"{k} stall current not positive"


class TestWeightG:
    """WEIGHT_G data integrity."""

    def test_non_empty(self):
        assert len(WEIGHT_G) > 20

    def test_all_non_negative(self):
        for k, v in WEIGHT_G.items():
            assert v >= 0, f"{k} has negative weight"

    def test_chassis_heaviest(self):
        assert WEIGHT_G["Chassis-Car-class"] == max(WEIGHT_G.values())


class TestThermalMw:
    """THERMAL_MW data integrity."""

    def test_non_empty(self):
        assert len(THERMAL_MW) > 20

    def test_all_non_negative(self):
        for k, v in THERMAL_MW.items():
            assert v >= 0, f"{k} has negative thermal"

    def test_rpi_highest(self):
        assert THERMAL_MW["RaspberryPi-class"] == max(THERMAL_MW.values())


class TestComponentNameAliases:
    """COMPONENT_NAME_ALIASES maps to valid canonical names."""

    def test_non_empty(self):
        assert len(COMPONENT_NAME_ALIASES) > 10

    def test_values_end_with_class(self):
        for alias, canonical in COMPONENT_NAME_ALIASES.items():
            assert canonical.endswith("-class"), (
                f"Alias {alias} -> {canonical} missing -class suffix"
            )

    def test_known_alias(self):
        assert COMPONENT_NAME_ALIASES["DHT22-Sensor-class"] == "Sensor-TempHumid-class"

    def test_no_self_reference(self):
        for alias, canonical in COMPONENT_NAME_ALIASES.items():
            assert alias != canonical, f"Self-referencing alias: {alias}"


class TestComponentShorthandAliases:
    """COMPONENT_SHORTHAND_ALIASES maps to valid canonical names."""

    def test_non_empty(self):
        assert len(COMPONENT_SHORTHAND_ALIASES) > 30

    def test_keys_lowercase(self):
        for key in COMPONENT_SHORTHAND_ALIASES:
            assert key == key.lower(), f"Key '{key}' not lowercase"

    def test_values_end_with_class(self):
        for key, val in COMPONENT_SHORTHAND_ALIASES.items():
            assert val.endswith("-class"), f"Shorthand {key} -> {val} missing -class"

    def test_common_lookups(self):
        assert COMPONENT_SHORTHAND_ALIASES["buzzer"] == "Buzzer-Active-class"
        assert COMPONENT_SHORTHAND_ALIASES["servo"] == "Motor-Servo-class"
        assert COMPONENT_SHORTHAND_ALIASES["pump"] == "Pump-Water-class"


class TestLookupConstant:
    """lookup_constant resolves via aliases."""

    def test_direct_hit(self):
        assert lookup_constant(PRICE_NTD, "Arduino-Uno-class", 0) == 250

    def test_via_alias(self):
        val = lookup_constant(PRICE_NTD, "DHT22-Sensor-class", 0)
        assert val == PRICE_NTD["Sensor-TempHumid-class"]

    def test_missing_returns_default(self):
        assert lookup_constant(PRICE_NTD, "NonExistent-class", -1) == -1


class TestResolveComponentAlias:
    """resolve_component_alias resolves or passes through."""

    def test_known_alias(self):
        assert resolve_component_alias("Servo-SG90-class") == "Motor-Servo-class"

    def test_canonical_passthrough(self):
        assert resolve_component_alias("Arduino-Uno-class") == "Arduino-Uno-class"

    def test_unknown_passthrough(self):
        assert resolve_component_alias("FooBar-class") == "FooBar-class"


class TestCrossConsistency:
    """Cross-table consistency checks."""

    def test_price_keys_subset_of_voltage(self):
        missing = set(PRICE_NTD.keys()) - set(VOLTAGE_V.keys())
        skip = {"Arduino-Nano-class", "ESP8266-class"}
        real_missing = missing - skip
        assert not real_missing, f"In PRICE_NTD but not VOLTAGE_V: {real_missing}"

    def test_weight_covers_thermal(self):
        missing = set(THERMAL_MW.keys()) - set(WEIGHT_G.keys())
        assert not missing, f"In THERMAL_MW but not WEIGHT_G: {missing}"

    def test_stall_components_in_power_ma(self):
        for comp in STALL_MA:
            assert comp in POWER_MA, f"{comp} in STALL_MA but not POWER_MA"
