"""test_l1_netlist.py — VS-L1 schematic netlist 語義驗證。"""
from lib.verification.l1_netlist import (
    check_netlist, check_wiring_netlist,
    _build_non_data_from_ssot, _build_bus_dirs_from_ssot,
    _NON_DATA_FALLBACK, _is_bus_pin,
    passive_refdes_unique, passive_net_endpoints, passive_zero_power,
)
from lib.verification import Verdict


def _wire(comp_pin_mcu: dict, *, directions: dict | None = None) -> dict:
    """建合成 wiring dict：{comp: [(comp_pin, mcu), ...]}。

    directions: optional {(comp, comp_pin): direction} 讓 pin 帶 direction 欄位。
    """
    directions = directions or {}
    result = {}
    for c, pins in comp_pin_mcu.items():
        result[c] = {
            "label": c,
            "pins": [{"comp": cp, "mcu": m, "color": "#fff", "note": "",
                       "direction": directions.get((c, cp), "")}
                     for cp, m in pins],
        }
    return result


class TestCheckNetlist:
    def test_clean_netlist_passes(self):
        w = _wire({"PIR": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D2")],
                   "LED": [("VCC", "5V"), ("GND", "GND"), ("SIG", "D3")]})
        assert check_netlist(w).verdict == Verdict.PASS

    def test_dangling_pin_fails(self):
        # mcu 含 "?" = 未分配 = 角位未接線
        w = _wire({"PIR": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D?")]})
        rpt = check_netlist(w)
        assert rpt.verdict == Verdict.FAIL

    def test_isolated_component_fails(self):
        w = {"PIR": {"label": "PIR", "pins": []}}
        assert check_netlist(w).verdict == Verdict.FAIL

    def test_gpio_conflict_fails(self):
        # 兩元件搶同一 D3
        w = _wire({"A": [("SIG", "D3")], "B": [("SIG", "D3")]})
        rpt = check_netlist(w)
        assert rpt.verdict == Verdict.FAIL

    def test_i2c_bus_shared_ok(self):
        # I2C bus（A4/A5/SDA/SCL）多元件共用是合法的，不算衝突
        w = _wire({"OLED": [("SDA", "A4"), ("SCL", "A5")],
                   "RTC": [("SDA", "A4"), ("SCL", "A5")]})
        assert check_netlist(w).verdict == Verdict.PASS

    def test_power_ground_shared_ok(self):
        # 5V/GND 多元件並接是合法的
        w = _wire({"A": [("VCC", "5V"), ("GND", "GND"), ("S", "D2")],
                   "B": [("VCC", "5V"), ("GND", "GND"), ("S", "D3")]})
        assert check_netlist(w).verdict == Verdict.PASS

    def test_direction_error_fails(self):
        class _Iss:
            severity = "error"; comp = "A"; comp_pin = "OUT"
            mcu_pin = "D2"; reason = "兩端皆 digital_out"
        w = _wire({"A": [("OUT", "D2")]})
        rpt = check_netlist(w, validate_issues=[_Iss()])
        assert rpt.verdict == Verdict.FAIL

    def test_direction_warning_does_not_block(self):
        class _Warn:
            severity = "warning"; comp = "A"; comp_pin = "SIG"
            mcu_pin = "D2"; reason = "需 level shifter"
        w = _wire({"A": [("SIG", "D2")]})
        rpt = check_netlist(w, validate_issues=[_Warn()])
        assert rpt.verdict == Verdict.PASS  # L2 warn 不擋
        assert rpt.has_nonblocking_fail is False


class TestOutputShort:
    """Check 5: OUTPUT-OUTPUT short circuit detection."""

    def test_output_output_short_detected(self):
        """Two components both outputting to same GPIO -> FAIL."""
        w = _wire(
            {"SensorA": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D3")],
             "SensorB": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D3")]},
            directions={("SensorA", "OUT"): "digital_out",
                        ("SensorB", "OUT"): "digital_out"},
        )
        rpt = check_netlist(w)
        assert rpt.verdict == Verdict.FAIL
        checks = {c.name: c for c in rpt.checks}
        assert checks["no_output_short"].verdict == Verdict.FAIL
        assert "D3" in checks["no_output_short"].metric

    def test_output_output_on_power_ok(self):
        """Two components sharing a power pin -> no false positive."""
        w = _wire(
            {"A": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D2")],
             "B": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D3")]},
            directions={("A", "OUT"): "digital_out",
                        ("B", "OUT"): "digital_out"},
        )
        rpt = check_netlist(w)
        checks = {c.name: c for c in rpt.checks}
        assert checks["no_output_short"].verdict == Verdict.PASS

    def test_output_input_same_pin_ok(self):
        """One output + one input on same pin is normal wiring, not a short."""
        w = _wire(
            {"Driver": [("OUT", "D5")],
             "Sensor": [("IN", "D5")]},
            directions={("Driver", "OUT"): "digital_out",
                        ("Sensor", "IN"): "digital_in"},
        )
        rpt = check_netlist(w)
        checks = {c.name: c for c in rpt.checks}
        # pin conflict will fire (two comps, same data pin), but not output short
        assert checks["no_output_short"].verdict == Verdict.PASS


class TestPowerCompleteness:
    """Check 6: Unconnected power pin validation."""

    def test_unconnected_power_warns(self):
        """Component with VCC but no GND -> WARN."""
        w = _wire({"Sensor": [("VCC", "5V"), ("OUT", "D2")]})
        rpt = check_netlist(w)
        checks = {c.name: c for c in rpt.checks}
        assert checks["power_completeness"].verdict == Verdict.WARN
        # WARN does not block overall verdict (L1 WARN != FAIL)
        # But other checks may independently fail; check power specifically
        assert "Sensor" in checks["power_completeness"].metric["incomplete"][0]

    def test_complete_power_passes(self):
        """Component with both VCC and GND -> PASS."""
        w = _wire({"Sensor": [("VCC", "5V"), ("GND", "GND"), ("OUT", "D2")]})
        rpt = check_netlist(w)
        checks = {c.name: c for c in rpt.checks}
        assert checks["power_completeness"].verdict == Verdict.PASS

    def test_no_power_pins_passes(self):
        """Component with no power pins at all -> PASS (not incomplete)."""
        w = _wire({"Logic": [("SIG", "D4")]})
        rpt = check_netlist(w)
        checks = {c.name: c for c in rpt.checks}
        assert checks["power_completeness"].verdict == Verdict.PASS


class TestSsotDerivation:
    """Verify SSOT-derived whitelists."""

    def test_ssot_non_data_matches_fallback(self):
        """SSOT-derived set is superset of fallback (if SSOT available)."""
        derived = _build_non_data_from_ssot()
        # derived always includes fallback by design (union)
        assert _NON_DATA_FALLBACK.issubset(derived)
        # Should also have SSOT-only entries (VDD, V+, etc.)
        assert len(derived) >= len(_NON_DATA_FALLBACK)

    def test_ssot_bus_detection(self):
        """Bus pin detection from SSOT direction field."""
        bus_dirs = _build_bus_dirs_from_ssot()
        # SSOT should contain i2c_bidir, uart_tx, uart_rx at minimum
        assert any("i2c" in d for d in bus_dirs), f"no i2c in {bus_dirs}"
        assert any("uart" in d for d in bus_dirs), f"no uart in {bus_dirs}"

    def test_bus_pin_by_direction(self):
        """_is_bus_pin detects bus from direction even with unknown pin name."""
        assert _is_bus_pin("X99", direction="i2c_bidir") is True
        assert _is_bus_pin("X99", direction="uart_tx") is True
        assert _is_bus_pin("X99", direction="digital_out") is False

    def test_bus_pin_fallback_keywords(self):
        """Fallback keyword matching still works for SDA/SCL/A4/A5."""
        assert _is_bus_pin("SDA") is True
        assert _is_bus_pin("A4") is True
        assert _is_bus_pin("D7") is False


class TestPassiveRefdesUnique:
    """DRC-P1: passive refdes 唯一性驗證。"""

    def _wire_with_passives(self, passives_by_comp: dict) -> dict:
        """建含 passive 的合成 wiring。

        passives_by_comp: {comp_short: [{"refdes": ..., "nets": [...], ...}, ...]}
        passive 放在 pins[0]["passive"] 或 decoupling 清單。
        """
        result = {}
        for comp, pas_list in passives_by_comp.items():
            pins = []
            for i, pas in enumerate(pas_list):
                pins.append({
                    "comp": f"PIN{i}",
                    "mcu": f"D{i}",
                    "color": "#fff",
                    "note": "",
                    "direction": "",
                    "passive": pas,
                })
            result[comp] = {"label": comp, "pins": pins}
        return result

    def test_unique_refdes_passes(self):
        w = self._wire_with_passives({
            "LED": [{"kind": "R", "refdes": "R1", "nets": ["MCU.D9", "LED.A"]}],
            "DHT": [{"kind": "R", "refdes": "R2", "nets": ["DHT.DATA", "VCC"]}],
        })
        result = passive_refdes_unique(w)
        assert result.verdict == Verdict.PASS
        assert result.metric["n_passives"] == 2

    def test_duplicate_refdes_fails(self):
        w = self._wire_with_passives({
            "LED": [{"kind": "R", "refdes": "R1", "nets": ["MCU.D9", "LED.A"]}],
            "DHT": [{"kind": "R", "refdes": "R1", "nets": ["DHT.DATA", "VCC"]}],
        })
        result = passive_refdes_unique(w)
        assert result.verdict == Verdict.FAIL
        assert "R1" in result.metric["duplicates"]
        assert result.metric["duplicates"]["R1"] == 2

    def test_multiple_duplicates_fail(self):
        """多組重複 refdes 均應列入 metric。"""
        w = self._wire_with_passives({
            "A": [
                {"kind": "R", "refdes": "R1", "nets": ["A.SIG", "GND"]},
                {"kind": "C", "refdes": "C1", "nets": ["A.VCC", "GND"]},
            ],
            "B": [
                {"kind": "R", "refdes": "R1", "nets": ["B.SIG", "GND"]},
                {"kind": "C", "refdes": "C1", "nets": ["B.VCC", "GND"]},
            ],
        })
        result = passive_refdes_unique(w)
        assert result.verdict == Verdict.FAIL
        assert "R1" in result.metric["duplicates"]
        assert "C1" in result.metric["duplicates"]

    def test_empty_wiring_passes(self):
        result = passive_refdes_unique({})
        assert result.verdict == Verdict.PASS

    def test_decoupling_passives_also_checked(self):
        """decoupling 清單的 passive 也計入 refdes 唯一性。"""
        wiring = {
            "MCU": {
                "label": "MCU",
                "pins": [{"comp": "VCC", "mcu": "5V", "color": "#fff",
                           "note": "", "direction": "",
                           "passive": {"kind": "R", "refdes": "R1",
                                       "nets": ["MCU.VCC", "GND"]}}],
                "decoupling": [{"kind": "C", "refdes": "R1",
                                "nets": ["MCU.VCC", "GND"]}],
            }
        }
        result = passive_refdes_unique(wiring)
        assert result.verdict == Verdict.FAIL
        assert result.metric["duplicates"]["R1"] == 2


class TestPassiveNetEndpoints:
    """DRC-P2: passive nets 恰 2 端且非空字串。"""

    def _make_wiring(self, nets_list: list) -> dict:
        """建含單一 passive 的 wiring，nets = nets_list。"""
        return {
            "LED": {
                "label": "LED",
                "pins": [{
                    "comp": "A",
                    "mcu": "D9",
                    "color": "#fff",
                    "note": "",
                    "direction": "",
                    "passive": {"kind": "R", "refdes": "R1", "nets": nets_list},
                }],
            }
        }

    def test_valid_two_endpoints_passes(self):
        w = self._make_wiring(["MCU.D9", "LED.A"])
        assert passive_net_endpoints(w).verdict == Verdict.PASS

    def test_valid_power_net_passes(self):
        w = self._make_wiring(["VCC", "GND"])
        assert passive_net_endpoints(w).verdict == Verdict.PASS

    def test_only_one_endpoint_fails(self):
        w = self._make_wiring(["MCU.D9"])
        result = passive_net_endpoints(w)
        assert result.verdict == Verdict.FAIL
        assert result.metric["bad"]

    def test_three_endpoints_fails(self):
        w = self._make_wiring(["MCU.D9", "LED.A", "GND"])
        result = passive_net_endpoints(w)
        assert result.verdict == Verdict.FAIL

    def test_empty_string_endpoint_fails(self):
        w = self._make_wiring(["MCU.D9", ""])
        result = passive_net_endpoints(w)
        assert result.verdict == Verdict.FAIL

    def test_whitespace_only_endpoint_fails(self):
        w = self._make_wiring(["MCU.D9", "   "])
        result = passive_net_endpoints(w)
        assert result.verdict == Verdict.FAIL

    def test_empty_nets_fails(self):
        w = self._make_wiring([])
        result = passive_net_endpoints(w)
        assert result.verdict == Verdict.FAIL

    def test_empty_wiring_passes(self):
        result = passive_net_endpoints({})
        assert result.verdict == Verdict.PASS


class TestPassiveZeroPower:
    """DRC-P3: 被動 R/C/D 不應有非零 current_ma。"""

    def _make_wiring(self, kind: str, current_ma=None) -> dict:
        pas: dict = {"kind": kind, "refdes": "R1", "nets": ["A", "B"]}
        if current_ma is not None:
            pas["current_ma"] = current_ma
        return {
            "LED": {
                "label": "LED",
                "pins": [{
                    "comp": "A", "mcu": "D9", "color": "#fff", "note": "",
                    "direction": "",
                    "passive": pas,
                }],
            }
        }

    def test_no_current_ma_passes(self):
        w = self._make_wiring("R")
        assert passive_zero_power(w).verdict == Verdict.PASS

    def test_zero_current_ma_passes(self):
        w = self._make_wiring("R", current_ma=0)
        assert passive_zero_power(w).verdict == Verdict.PASS

    def test_nonzero_r_warns(self):
        w = self._make_wiring("R", current_ma=10)
        result = passive_zero_power(w)
        assert result.verdict == Verdict.WARN
        assert result.metric["nonzero"]

    def test_nonzero_c_warns(self):
        w = self._make_wiring("C", current_ma=5)
        result = passive_zero_power(w)
        assert result.verdict == Verdict.WARN

    def test_nonzero_d_warns(self):
        w = self._make_wiring("D", current_ma=20)
        result = passive_zero_power(w)
        assert result.verdict == Verdict.WARN

    def test_warn_is_non_blocking(self):
        """WARN 在 L2 層，不應造成整體 FAIL。"""
        w = self._make_wiring("R", current_ma=10)
        # 加入一個完整 wiring 以確保其他 L1 check 通過
        full_wiring = {
            "Sensor": {
                "label": "Sensor",
                "pins": [
                    {"comp": "VCC", "mcu": "5V", "color": "#fff",
                     "note": "", "direction": "", "passive": None},
                    {"comp": "GND", "mcu": "GND", "color": "#fff",
                     "note": "", "direction": "", "passive": None},
                    {"comp": "OUT", "mcu": "D2", "color": "#fff",
                     "note": "", "direction": "", "passive": None},
                ],
            }
        }
        from lib.verification.report import VerificationReport
        rpt = VerificationReport(artifact="test", artifact_type="netlist")
        rpt.add(passive_zero_power(w))
        # WARN 不影響 verdict（L2 非 blocking）
        assert rpt.verdict == Verdict.PASS

    def test_empty_wiring_passes(self):
        result = passive_zero_power({})
        assert result.verdict == Verdict.PASS


class TestCheckWiringNetlist:
    def test_real_auto_waterer_combo(self):
        # auto_waterer 元件組合應產出乾淨 netlist
        rpt = check_wiring_netlist("Arduino", ["SoilMoisture", "Relay", "Pump", "Button"])
        assert rpt.verdict == Verdict.PASS, rpt.render_text()

    def test_real_nightlight_combo(self):
        rpt = check_wiring_netlist("Arduino", ["NeoPixel", "PIR", "Light"])
        assert rpt.verdict == Verdict.PASS, rpt.render_text()
