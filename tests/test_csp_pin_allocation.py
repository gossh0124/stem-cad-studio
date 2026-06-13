"""tests/test_csp_pin_allocation.py — ADR-5 CSP pin allocator tests.

Covers:
  1. Basic allocation (same result as FIFO for simple cases)
  2. ESP32 input-only constraint (GPIO 34-39 never assigned to output components)
  3. I2C grouping (2+ I2C devices share same SDA/SCL)
  4. Conflict detection (more PWM needs than available pins)
  5. MRV ordering (most constrained vars allocated first)
  6. Backward compatibility (16 canned project profiles produce valid allocations)
"""
from __future__ import annotations
import pytest

from lib.wiring import PIN_POOLS, COMP_PIN_NEEDS, allocate_pins
from lib.wiring.csp import csp_allocate, _INPUT_ONLY_PINS, _I2C_HW_PINS


# ── helpers ────────────────────────────────────────────────────────────────

def _pool(brain_key: str) -> dict:
    raw = PIN_POOLS[brain_key]
    return {
        "pwm":     list(raw["pwm"]),
        "digital": list(raw["digital"]),
        "analog":  list(raw["analog"]),
        "i2c":     dict(raw["i2c"]),
    }


def _run_csp(brain_key: str, comps: list[str]):
    """Run CSP and assert no conflicts."""
    pool = _pool(brain_key)
    alloc, labels, conflicts = csp_allocate(brain_key, comps, pool, COMP_PIN_NEEDS)
    return alloc, labels, conflicts


# ── 1. Basic allocation ────────────────────────────────────────────────────

class TestBasicAllocation:
    def test_single_analog_sensor(self):
        alloc, labels, conflicts = _run_csp("Arduino", ["SoilMoisture"])
        assert not conflicts
        assert "SoilMoisture" in alloc
        # AO must map to an analog pin (A0–A3)
        ao = alloc["SoilMoisture"]["AO"]
        assert ao in PIN_POOLS["Arduino"]["analog"], f"Expected analog pin, got {ao}"

    def test_single_digital_output(self):
        alloc, labels, conflicts = _run_csp("Arduino", ["NeoPixel"])
        assert not conflicts
        din = alloc["NeoPixel"]["DIN"]
        digital_pool = PIN_POOLS["Arduino"]["digital"] + PIN_POOLS["Arduino"]["pwm"]
        assert din in digital_pool, f"DIN {din} not in digital pool"

    def test_single_pwm_component(self):
        alloc, labels, conflicts = _run_csp("Arduino", ["Servo"])
        assert not conflicts
        sig = alloc["Servo"]["SIG"]
        assert sig in PIN_POOLS["Arduino"]["pwm"], f"Servo SIG {sig} not in PWM pool"

    def test_pin_labels_format(self):
        _, labels, conflicts = _run_csp("Arduino", ["SoilMoisture"])
        assert not conflicts
        assert "AO=" in labels["SoilMoisture"]

    def test_no_pin_collision_multi_components(self):
        comps = ["NeoPixel", "Button", "SoilMoisture"]
        alloc, _, conflicts = _run_csp("Arduino", comps)
        assert not conflicts
        all_pins = []
        for comp_pins in alloc.values():
            for p in comp_pins.values():
                # analog pins (strings like "A0") and digital (ints) can overlap intentionally
                # only check non-i2c pins for uniqueness
                all_pins.append(str(p))
        # all_pins should be unique (no two comps share a pin)
        # I2C pins are shared deliberately — filter them out
        assert len(all_pins) == len(set(all_pins)), f"Pin collision detected: {all_pins}"

    def test_matches_fifo_for_simple_case(self):
        """For a single analog sensor, CSP and FIFO must agree."""
        fifo_result = allocate_pins("Arduino", ["SoilMoisture"])
        csp_alloc, _, conflicts = _run_csp("Arduino", ["SoilMoisture"])
        assert not conflicts
        fifo_pin = fifo_result["allocation"]["SoilMoisture"]["AO"]
        csp_pin  = csp_alloc["SoilMoisture"]["AO"]
        assert str(fifo_pin) == str(csp_pin), (
            f"FIFO={fifo_pin} vs CSP={csp_pin} differ for SoilMoisture.AO")


# ── 2. ESP32 input-only constraint ────────────────────────────────────────

class TestESP32InputOnlyConstraint:
    INPUT_ONLY = _INPUT_ONLY_PINS["ESP32"]

    def test_neopixel_din_not_on_input_only(self):
        alloc, _, conflicts = _run_csp("ESP32", ["NeoPixel"])
        assert not conflicts
        din = alloc["NeoPixel"]["DIN"]
        assert din not in self.INPUT_ONLY, (
            f"NeoPixel DIN={din} assigned to input-only GPIO (34/35/36/39)")

    def test_relay_in_not_on_input_only(self):
        alloc, _, conflicts = _run_csp("ESP32", ["Relay"])
        assert not conflicts
        pin = alloc["Relay"]["IN"]
        assert pin not in self.INPUT_ONLY, f"Relay IN={pin} on input-only GPIO"

    def test_servo_sig_not_on_input_only(self):
        alloc, _, conflicts = _run_csp("ESP32", ["Servo"])
        assert not conflicts
        sig = alloc["Servo"]["SIG"]
        assert sig not in self.INPUT_ONLY, f"Servo SIG={sig} on input-only GPIO"

    def test_analog_sensor_may_use_input_only(self):
        """Analog input sensors (SoilMoisture) CAN be assigned to input-only pins."""
        alloc, _, conflicts = _run_csp("ESP32", ["SoilMoisture"])
        assert not conflicts
        ao = alloc["SoilMoisture"]["AO"]
        # The analog pool for ESP32 is [34,35,36,39] — all input-only by hardware design
        assert ao in PIN_POOLS["ESP32"]["analog"], f"AO={ao} not in analog pool"

    def test_mixed_output_and_input_sensor(self):
        """Mixing an output comp and an analog sensor must not put output on input-only."""
        alloc, _, conflicts = _run_csp("ESP32", ["NeoPixel", "SoilMoisture"])
        assert not conflicts
        din = alloc["NeoPixel"]["DIN"]
        ao  = alloc["SoilMoisture"]["AO"]
        assert din not in self.INPUT_ONLY, f"NeoPixel DIN={din} on input-only"
        assert ao in PIN_POOLS["ESP32"]["analog"]


# ── 3. I2C grouping ───────────────────────────────────────────────────────

class TestI2CGrouping:
    def test_single_oled_gets_hw_i2c(self):
        alloc, _, conflicts = _run_csp("Arduino", ["OLED"])
        assert not conflicts
        sda, scl = _I2C_HW_PINS["Arduino"]
        assert alloc["OLED"]["SDA"] == sda, f"OLED SDA should be {sda}"
        assert alloc["OLED"]["SCL"] == scl, f"OLED SCL should be {scl}"

    def test_oled_and_lcd_share_i2c_bus(self):
        """Two I2C devices MUST share the same SDA/SCL pair."""
        alloc, _, conflicts = _run_csp("Arduino", ["OLED", "LCD"])
        assert not conflicts
        assert alloc["OLED"]["SDA"] == alloc["LCD"]["SDA"], "SDA mismatch"
        assert alloc["OLED"]["SCL"] == alloc["LCD"]["SCL"], "SCL mismatch"

    def test_esp32_i2c_pins(self):
        alloc, _, conflicts = _run_csp("ESP32", ["OLED"])
        assert not conflicts
        sda, scl = _I2C_HW_PINS["ESP32"]
        assert alloc["OLED"]["SDA"] == sda, f"ESP32 OLED SDA should be {sda}"
        assert alloc["OLED"]["SCL"] == scl

    def test_i2c_and_digital_no_collision(self):
        """I2C pins must not collide with digital pins of other components."""
        alloc, _, conflicts = _run_csp("Arduino", ["OLED", "NeoPixel"])
        assert not conflicts
        i2c_pins = {alloc["OLED"]["SDA"], alloc["OLED"]["SCL"]}
        din = alloc["NeoPixel"]["DIN"]
        assert din not in i2c_pins, f"NeoPixel DIN={din} collides with I2C bus"


# ── 4. Conflict detection ─────────────────────────────────────────────────

class TestConflictDetection:
    def test_too_many_pwm_components(self):
        """Arduino only has 6 PWM pins. 3 × LED_RGB (3 PWM each) = 9 > 6."""
        # Construct a pool with very limited PWM to force conflict detection
        limited_pool = {
            "pwm":     [3],        # only 1 PWM pin
            "digital": [],
            "analog":  [],
            "i2c":     {"sda": "A4", "scl": "A5"},
        }
        # LED_RGB needs 3 PWM pins — should fail
        _, _, conflicts = csp_allocate("Arduino", ["LED_RGB"], limited_pool, COMP_PIN_NEEDS)
        assert conflicts, "Expected conflict when PWM pool is exhausted"

    def test_conflict_message_is_readable(self):
        """Conflict strings must be non-empty, human-readable text."""
        limited_pool = {
            "pwm":     [],
            "digital": [],
            "analog":  [],
            "i2c":     {"sda": "A4", "scl": "A5"},
        }
        _, _, conflicts = csp_allocate("Arduino", ["Servo"], limited_pool, COMP_PIN_NEEDS)
        assert conflicts
        for msg in conflicts:
            assert isinstance(msg, str) and len(msg) > 5, f"Bad conflict msg: {msg!r}"

    def test_empty_pool_all_fail(self):
        """Totally empty pool must produce conflicts for any non-I2C component."""
        empty_pool = {"pwm": [], "digital": [], "analog": [], "i2c": {"sda": "A4", "scl": "A5"}}
        _, _, conflicts = csp_allocate("Arduino", ["NeoPixel", "Button"], empty_pool, COMP_PIN_NEEDS)
        assert conflicts

    def test_no_conflict_normal_scenario(self):
        """Normal scenario must produce zero conflicts."""
        _, _, conflicts = _run_csp("Arduino", ["Servo", "NeoPixel", "Button"])
        assert conflicts == [], f"Unexpected conflicts: {conflicts}"


# ── 5. MRV ordering ──────────────────────────────────────────────────────

class TestMRVOrdering:
    def test_most_constrained_allocated_first(self):
        """When PWM pool is tiny, the component needing PWM (Servo) should still
        be allocated — MRV picks it before less-constrained ones."""
        tight_pool = {
            "pwm":     [3],          # exactly 1 PWM
            "digital": [2, 4, 7, 8, 12, 13],
            "analog":  ["A0", "A1"],
            "i2c":     {"sda": "A4", "scl": "A5"},
        }
        alloc, _, conflicts = csp_allocate(
            "Arduino", ["Button", "Servo", "SoilMoisture"], tight_pool, COMP_PIN_NEEDS
        )
        # With exactly 1 PWM pin and Servo needing exactly 1 PWM — must succeed.
        # Servo SIG must end up on pin 3 (the only PWM pin).
        assert not conflicts, f"Conflicts: {conflicts}"
        servo_sig = alloc["Servo"]["SIG"]
        assert servo_sig == 3, (
            f"Servo.SIG={servo_sig}: expected pin 3 (the only PWM pin); "
            f"MRV should prioritise Servo once Button/Soil take their pins"
        )

    def test_mrv_does_not_starve_later_components(self):
        """All components in a typical project must receive valid allocations."""
        comps = ["Servo", "Button", "SoilMoisture", "NeoPixel"]
        alloc, _, conflicts = _run_csp("Arduino", comps)
        assert not conflicts
        for c in comps:
            assert c in alloc, f"{c} missing from allocation"


# ── 6. Backward compatibility — 16 canned project profiles ───────────────

CANNED_PROFILES = [
    ("Arduino", ["SoilMoisture", "Relay", "Pump", "Button"]),          # auto_waterer
    ("Arduino", ["NeoPixel", "PIR", "Light"]),                         # smart_nightlight
    ("Arduino", ["Speaker", "Servo", "PIR", "Button"]),                 # talking_robot
    ("Arduino", ["LED_RGB", "Button"]),                                 # rgb_lamp
    ("Arduino", ["TempHumid", "OLED", "Button"]),                      # temp_display
    ("Arduino", ["Ultrasonic", "NeoPixel"]),                           # distance_light
    ("Arduino", ["DCMotor", "Ultrasonic", "Button"]),                  # motor+sensor+button mix
    ("Arduino", ["Stepper", "PIR"]),                                    # auto_curtain
    ("Arduino", ["Buzzer_Active", "PIR"]),                              # alarm
    ("Arduino", ["LCD", "TempHumid"]),                                  # lcd_weather
    ("ESP32",   ["OLED", "DCMotor", "Ultrasonic"]),                    # esp32_bot
    ("ESP32",   ["NeoPixel", "SoilMoisture", "Relay"]),                # esp32_plant
    ("ESP32",   ["Servo", "PIR", "Button"]),                           # esp32_door
    ("ESP32",   ["LED_RGB", "OLED", "Button"]),                        # esp32_rgb
    ("Arduino", ["SoilMoisture", "Relay", "OLED", "Button"]),         # smart_garden
    ("Arduino", ["NeoPixel", "TempHumid", "Light", "Button"]),        # weather_lamp
]


class TestBackwardCompatibility:
    @pytest.mark.parametrize("brain,comps", CANNED_PROFILES,
                             ids=[f"{b}-{'+'.join(c[:2])}" for b, c in CANNED_PROFILES])
    def test_canned_profile_no_conflicts(self, brain, comps):
        alloc, labels, conflicts = _run_csp(brain, comps)
        assert not conflicts, (
            f"[{brain}] {comps} produced conflicts: {conflicts}")
        for comp in comps:
            if comp in COMP_PIN_NEEDS:
                assert comp in alloc, f"{comp} missing from allocation"

    @pytest.mark.parametrize("brain,comps", CANNED_PROFILES,
                             ids=[f"{b}-{'+'.join(c[:2])}" for b, c in CANNED_PROFILES])
    def test_allocate_pins_api_shape(self, brain, comps):
        """allocate_pins() must return {allocation, pin_labels} for every canned profile."""
        result = allocate_pins(brain, comps)
        assert "allocation" in result
        assert "pin_labels" in result
        assert isinstance(result["allocation"], dict)
        assert isinstance(result["pin_labels"], dict)

    def test_esp32_output_comps_not_on_input_only_pins(self):
        """Cross-check all ESP32 canned profiles: output comps never on GPIO 34-39."""
        input_only = _INPUT_ONLY_PINS["ESP32"]
        output_types = {"pwm", "digital"}
        for brain, comps in CANNED_PROFILES:
            if brain != "ESP32":
                continue
            alloc, _, _ = _run_csp(brain, comps)
            for comp in comps:
                needs = COMP_PIN_NEEDS.get(comp, [])
                for need in needs:
                    if need.type in output_types:
                        pin = alloc.get(comp, {}).get(need.tag)
                        assert pin not in input_only, (
                            f"[ESP32] {comp}.{need.tag}={pin} on input-only GPIO")


# ── 9. Global pin-budget feasibility (anti-hang regression) ──────────────
# 2026-06-11: csp_allocate 缺全域腳位預算預檢時,過訂(鴿籠不可行)設計會讓
# _backtrack 窮舉指數樹「永不終止」(實測 >5,000,000 節點/47s 未返)。此組鎖:
# (a) 4b 匹配預檢秒拒鴿籠不可行集;(b) 任何輸入必有界終止(節點上限承重)。

class TestGlobalPinBudget:
    # 根因集:13 個 digital/pwm 唯一需求 > Arduino UNO 12 腳(鴿籠不可行)。
    _OVERBUDGET_ARDUINO = [
        "Relay", "Pump", "Servo", "Stepper", "OLED", "LED_Single",
        "Buzzer_Active", "Button", "Switch", "SoilMoisture", "DCMotor",
    ]

    def test_pigeonhole_overbudget_fast_conflict(self):
        """過訂集必在預檢層快速回 conflict(修前 = 無窮回溯 hang)。"""
        import time
        t0 = time.monotonic()
        _, _, conflicts = _run_csp("Arduino", self._OVERBUDGET_ARDUINO)
        elapsed = time.monotonic() - t0
        assert conflicts, "13 digital/pwm 需求 > 12 腳,必須回 conflict"
        assert elapsed < 10, f"預檢應毫秒級完成,實測 {elapsed:.1f}s(hang 回歸)"
        joined = " ".join(conflicts)
        assert "Not enough unique pins" in joined, conflicts
        # 訊息報「飽和群組」真值:13 needed / 12 available,不混入 analog 池
        assert "13 pins needed" in joined and "12 available" in joined, conflicts

    def test_overbudget_raises_pin_allocation_error(self):
        """allocate_pins 對過訂集必 raise(no-silent-fallback,不降級 FIFO)。"""
        from lib.wiring import PinAllocationError
        with pytest.raises(PinAllocationError):
            allocate_pins("Arduino", self._OVERBUDGET_ARDUINO)

    def test_matching_blind_spot_terminates(self):
        """匹配預檢盲區(I2C 共享腳逐出互動)仍須有界終止 — 節點上限承重。

        此 ESP32 集可穿過 4b 匹配(看不見 _forward_check 的 I2C 逐出)但實際
        不可行:無上限時 >2,000,000 節點/16.7s 不返。不斷言可行性結論(未來
        COMP_PIN_NEEDS 變動可能翻轉),只斷言「必須終止」這個反 hang 不變量。
        """
        import time
        comps = ["DCMotor", "PIR", "Buzzer_Passive", "LED_RGB",
                 "OLED", "SD_Card", "MSGEQ7", "Stepper"]
        t0 = time.monotonic()
        _run_csp("ESP32", comps)   # 可行→回 allocation;不可行→回 conflicts
        elapsed = time.monotonic() - t0
        assert elapsed < 30, f"csp_allocate 必須有界終止,實測 {elapsed:.1f}s"
