"""PB4 (Path B / D4): power injection derived from SSOT by voltage matching.

Fixes the frontend _injectPower bug where every ESP32 source was routed to a '5V' MCU
pin that ESP32 does not have (only VIN/3V3) → the power wire was silently dropped. Here
the MCU power pin is chosen from the MCU's real PWR pins and the source pin name comes
from the source SSOT (not hardcoded 'V+'/'BAT+').
"""
import pytest

from lib.wiring.power_inject import (
    derive_power_injection,
    derive_load_power_injection,
    derive_power_source_wiring,
    PowerInjectError,
    UnknownPowerSourceError,
)


class TestPowerInject:
    def test_esp32_5v_routes_to_vin_not_missing_5v_pin(self):
        # THE bug fix: ESP32 has VIN + 3V3, no '5V' pin → 5V source must route to VIN.
        assert derive_power_injection("ESP32", "USB5V")["plus"]["mcu_pin"] == "VIN"

    def test_arduino_5v_routes_to_5v_pin(self):
        assert derive_power_injection("Arduino", "USB5V")["plus"]["mcu_pin"] == "5V"

    def test_lipo_routes_to_3v3_on_esp32(self):
        assert derive_power_injection("ESP32", "BatteryLiPo")["plus"]["mcu_pin"] == "3V3"

    def test_source_pin_name_derived_from_ssot(self):
        # USB source PWR pin = VCC; battery PWR pin = V+ — derived, not hardcoded.
        assert derive_power_injection("Arduino", "USB5V")["plus"]["source_pin"] == "VCC"
        assert derive_power_injection("ESP32", "BatteryLiPo")["plus"]["source_pin"] == "V+"

    def test_minus_is_gnd(self):
        r = derive_power_injection("Arduino", "USB5V")
        assert r["minus"]["source_pin"] == "GND" and r["minus"]["mcu_pin"] == "GND"

    def test_unknown_power_raises(self):
        with pytest.raises(PowerInjectError):
            derive_power_injection("ESP32", "No-Such-Power-Class")


class TestPowerInjectFeasibility:
    """PB4 0-anomaly: incompatible source→MCU combos RAISE (not silently pick a pin).
    2xAA=3.0V / 1S LiPo=3.7V cannot power Arduino (VIN 6-12V, 5V pin ~5V; 3V3 is output)."""

    def test_arduino_2xAA_infeasible_raises(self):
        with pytest.raises(PowerInjectError):
            derive_power_injection("Arduino", "BatteryAA")

    def test_arduino_lipo_infeasible_raises(self):
        with pytest.raises(PowerInjectError):
            derive_power_injection("Arduino", "BatteryLiPo")

    def test_microbit_2xAA_feasible_3v3(self):
        assert derive_power_injection("Microbit", "BatteryAA")["plus"]["mcu_pin"] == "3V3"

    def test_arduino_4xAA_6v_or_9v_uses_vin(self):
        # 4xAA(6V)/9V are the feasible Arduino battery options → VIN
        r = derive_power_injection("Arduino", "USB5V")  # 5V → 5V pin (sanity, feasible)
        assert r["plus"]["mcu_pin"] == "5V"


class TestLoadPowerInject:
    """derive_load_power_injection: load-domain V+ -> EXT-PWR rail, GND common.

    Distinct from derive_power_injection: this is the LOAD domain (external power
    feeds a driver/relay load input, e.g. garden battery -> pump), so there is
    NO MCU feasibility check. Source pin + voltage are derived from SSOT, not hardcoded.
    """

    def test_load_rail_and_common_gnd(self):
        r = derive_load_power_injection("BatteryLiPo")
        assert r["plus"]["load_rail"] == "EXT-PWR"
        assert r["minus"]["load_rail"] == "GND"
        assert r["minus"]["source_pin"] == "GND"

    def test_source_pin_derived_from_ssot(self):
        # battery PWR pin = V+ ; USB PWR pin = VCC — read from pin_layout, not hardcoded.
        assert derive_load_power_injection("BatteryLiPo")["plus"]["source_pin"] == "V+"
        assert derive_load_power_injection("USB5V")["plus"]["source_pin"] == "VCC"

    def test_voltage_and_source_from_ssot(self):
        r = derive_load_power_injection("BatteryLiPo")
        assert r["source"] == "BatteryLiPo"
        assert r["voltage_v"] == 3.7

    def test_no_mcu_feasibility_check_in_load_domain(self):
        # 2xAA (3.0V, infeasible for an Arduino MCU supply) is perfectly valid as a
        # LOAD power source — load domain must NOT apply MCU feasibility and must NOT raise.
        r = derive_load_power_injection("BatteryAA")
        assert r["plus"]["load_rail"] == "EXT-PWR"
        assert r["voltage_v"] == 3.0

    def test_unknown_power_raises(self):
        with pytest.raises(PowerInjectError):
            derive_load_power_injection("No-Such-Power-Class")


class TestPowerSourceWiring:
    """derive_power_source_wiring 的 no-silent-fallback 契約(缺陷 C 回歸,DEC-H7)。

    缺陷史:不可解析的 power source 會被內部兩個 `except PowerInjectError: pass` 吞掉,
    `not mcu_ok` 仍成立 → 照樣捏造 V_USB,使用者指定源消失、EXT-PWR 負載軌無源,API 仍回 200。
    """

    def test_unresolvable_source_raises_not_fabricates_vusb(self):
        # 不可解析(typo / 未支援)→ raise,兩種 has_ext_pwr 皆然;絕不回含 V_USB 的清單。
        for ext in (True, False):
            with pytest.raises(UnknownPowerSourceError):
                derive_power_source_wiring("Arduino", "SolarPanel", has_ext_pwr=ext)

    def test_registered_mcu_source_supplies_mcu(self):
        # 已註冊且可供 MCU 的源(USB5V/Arduino)→ 正常單一 MCU 源,不 raise。
        devs = derive_power_source_wiring("Arduino", "USB5V", has_ext_pwr=False)
        assert devs is not None
        assert devs[0]["plus"]["net_name"] in ("5V", "VIN")
        assert devs[0]["minus"]["net_name"] == "GND"

    def test_resolvable_mcu_infeasible_still_isolates(self):
        # 可解析但電壓對 MCU 不可行(LiPo 3.7V/Arduino)+ ext_pwr:合法情形,**不 raise** ——
        # 負載源走隔離 EXT-PWR(minus=EXT-GND),MCU 另由獨立 V_USB(5V/GND)供電。
        devs = derive_power_source_wiring("Arduino", "BatteryLiPo", has_ext_pwr=True)
        assert devs is not None
        rails = {d["plus"]["net_name"]: d["minus"]["net_name"] for d in devs}
        assert rails.get("EXT-PWR") == "EXT-GND", f"負載源應在隔離 EXT-PWR/EXT-GND: {rails}"
        assert any(d["refdes"] == "V_USB" and d["plus"]["net_name"] == "5V" for d in devs), \
            "MCU 應有獨立 V_USB(5V)"

    def test_to_json_propagates_unresolvable_power_not_swallowed(self):
        # engine 傳播:不可解析 power 必須上拋(到 API → 422),不得被 engine 的 except 吞成 None。
        from lib.wiring import to_json
        with pytest.raises(UnknownPowerSourceError):
            to_json("Arduino", ["Relay"], power="SolarPanel")

    def test_api_wiring_returns_422_for_unresolvable_power(self, monkeypatch):
        # route 層:/api/v1/wiring 對不可解析 power 回 HTTP 422(設計問題),非 200 + 幽靈電源。
        # import routes_design 會觸發 auth.py fail-loud(防 hardcoded JWT)→ 測試環境顯式 opt-in。
        pytest.importorskip("build123d")  # API route boots full pipeline (lib.cad/build123d)
        monkeypatch.setenv("CADHLLM_ALLOW_DEV_SECRET", "1")
        import asyncio
        from fastapi import HTTPException
        from services.gateway.routes_design import api_wiring, DesignRequest
        req = DesignRequest(brain="Arduino", outputs=["Relay-Module-class"],
                            sensors=[], power="SolarPanel")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(api_wiring(req))
        assert ei.value.status_code == 422
