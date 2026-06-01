"""
test_firmware_reactions.py — INF2：REACTION_RULES 與韌體生成邏輯測試

涵蓋：REACTION_RULES 結構、Buzzer 別名、match_reactions、OUTPUT_FALLBACK、
generate_firmware（Arduino/ESP32/RPi/Microbit）、TEST_TEMPLATES、_wrap_text。
"""
from __future__ import annotations
import pytest
from lib.firmware.templates import (
    REACTION_RULES, OUTPUT_FALLBACK, TEST_TEMPLATES,
    match_reactions, _wrap_text,
)
from lib.firmware import generate_firmware, generate_test_code


# ── REACTION_RULES 結構驗證 ──────────────────────────────────

class TestReactionRulesStructure:
    def test_is_dict(self):
        assert isinstance(REACTION_RULES, dict)

    def test_all_keys_are_two_tuples(self):
        for k in REACTION_RULES:
            assert isinstance(k, tuple) and len(k) == 2, f"Bad key: {k}"

    def test_all_values_have_required_fields(self):
        required = {"condition", "action", "else", "label"}
        for k, v in REACTION_RULES.items():
            assert not (required - v.keys()), f"Rule {k} missing fields"

    def test_all_fields_are_nonempty_strings(self):
        for k, v in REACTION_RULES.items():
            for field in ("condition", "action", "else", "label"):
                assert isinstance(v[field], str) and v[field].strip(), f"{k}.{field}"

    def test_minimum_rule_count(self):
        assert len(REACTION_RULES) >= 15

    def test_known_sensor_types_present(self):
        sensors = {k[0] for k in REACTION_RULES}
        assert {"SoilMoisture", "PIR", "Ultrasonic", "Light", "TempHumid"}.issubset(sensors)


# ── Buzzer 別名自動擴展 ──────────────────────────────────────

class TestBuzzerAliasExpansion:
    @pytest.mark.parametrize("sensor,variant", [
        ("PIR", "Buzzer_Active"), ("PIR", "Buzzer_Passive"),
        ("Ultrasonic", "Buzzer_Active"), ("Ultrasonic", "Buzzer_Passive"),
        ("TempHumid", "Buzzer_Active"), ("TempHumid", "Buzzer_Passive"),
    ])
    def test_alias_exists(self, sensor, variant):
        assert (sensor, variant) in REACTION_RULES

    def test_active_alias_same_content_as_original(self):
        orig = REACTION_RULES.get(("PIR", "Buzzer"))
        active = REACTION_RULES.get(("PIR", "Buzzer_Active"))
        if orig and active:
            assert orig == active

    def test_at_least_three_active_aliases(self):
        assert sum(1 for k in REACTION_RULES if k[1] == "Buzzer_Active") >= 3


# ── 特定規則內容驗證 ─────────────────────────────────────────

@pytest.mark.parametrize("sensor,output,field,expected", [
    ("SoilMoisture", "Relay",     "condition", "soilPct < 40"),
    ("PIR",          "Buzzer",    "condition", "motion == 1"),
    ("PIR",          "LED_Single","action",    "HIGH"),
    ("PIR",          "Relay",     "action",    "LOW"),
    ("Ultrasonic",   "Buzzer",    "condition", "20"),
    ("Ultrasonic",   "Servo",     "condition", "30"),
    ("Ultrasonic",   "Servo",     "action",    "myServo.write"),
    ("Light",        "NeoPixel",  "action",    "255"),
    ("TempHumid",    "Buzzer",    "condition", "35"),
    ("TempHumid",    "Relay",     "condition", "30"),
    ("PIR",          "NeoPixel",  "action",    "255"),
])
def test_specific_rule_content(sensor, output, field, expected):
    rule = REACTION_RULES.get((sensor, output))
    if rule is None:
        pytest.skip(f"Rule ({sensor}, {output}) not in REACTION_RULES")
    assert expected in rule[field], f"({sensor},{output}).{field} missing '{expected}'"


def test_temphum_dcmotor_action_keywords():
    rule = REACTION_RULES[("TempHumid", "DCMotor")]
    assert "MOTOR_IN1" in rule["action"] or "MOTOR_EN" in rule["action"]


# ── match_reactions ──────────────────────────────────────────

class TestMatchReactions:
    def test_returns_list_and_set(self):
        matched, handled = match_reactions(["PIR"], ["LED_Single"])
        assert isinstance(matched, list) and isinstance(handled, set)

    def test_single_match(self):
        matched, handled = match_reactions(["PIR"], ["LED_Single"])
        assert len(matched) == 1
        assert matched[0]["sensor"] == "PIR" and matched[0]["output"] == "LED_Single"
        assert "LED_Single" in handled

    def test_no_match_returns_empty(self):
        matched, handled = match_reactions(["PIR"], ["Speaker"])
        assert matched == [] and "Speaker" not in handled

    def test_empty_sensors(self):
        matched, handled = match_reactions([], ["LED_Single"])
        assert matched == [] and handled == set()

    def test_empty_outputs(self):
        matched, handled = match_reactions(["PIR"], [])
        assert matched == [] and handled == set()

    def test_multiple_sensors_outputs(self):
        matched, _ = match_reactions(["PIR", "Ultrasonic"], ["LED_Single", "Buzzer_Active"])
        assert len(matched) >= 2

    def test_matched_dict_keys(self):
        matched, _ = match_reactions(["SoilMoisture"], ["Relay"])
        rule = matched[0]
        for key in ("sensor", "output", "condition", "action", "else", "label"):
            assert key in rule

    def test_soil_relay_match(self):
        matched, _ = match_reactions(["SoilMoisture"], ["Relay"])
        assert any(m["sensor"] == "SoilMoisture" and m["output"] == "Relay" for m in matched)

    def test_temphum_dcmotor_match(self):
        matched, _ = match_reactions(["TempHumid"], ["DCMotor"])
        assert len(matched) == 1 and matched[0]["sensor"] == "TempHumid"


# ── OUTPUT_FALLBACK ──────────────────────────────────────────

class TestOutputFallback:
    def test_is_dict(self):
        assert isinstance(OUTPUT_FALLBACK, dict)

    def test_known_outputs_present(self):
        expected = {"LED_Single", "LED_RGB", "NeoPixel", "Buzzer_Active",
                    "Buzzer_Passive", "Servo", "DCMotor", "Stepper", "Relay"}
        assert expected.issubset(OUTPUT_FALLBACK.keys())

    def test_all_values_nonempty_strings(self):
        for k, v in OUTPUT_FALLBACK.items():
            assert isinstance(v, str) and v.strip(), f"Empty fallback: {k}"

    def test_led_fallback_digital(self):
        fb = OUTPUT_FALLBACK["LED_Single"]
        assert "digitalRead" in fb or "digitalWrite" in fb

    def test_neopixel_fallback_show(self):
        assert "show()" in OUTPUT_FALLBACK["NeoPixel"]


# ── generate_firmware：Arduino / ESP32 ───────────────────────

class TestGenerateFirmwareArduino:
    def _gen(self, brain, outputs, sensors, power="5V"):
        return generate_firmware(brain, power, outputs, sensors)

    def test_returns_correct_keys(self):
        fw = self._gen("Arduino", ["LED_Single"], ["PIR"])
        assert {"code", "lang", "ext"} == fw.keys()

    def test_lang_ext_cpp(self):
        fw = self._gen("Arduino", ["LED_Single"], [])
        assert fw["lang"] == "cpp" and fw["ext"] == ".ino"

    def test_has_setup_and_loop(self):
        fw = self._gen("Arduino", ["LED_Single"], ["PIR"])
        assert "void setup()" in fw["code"] and "void loop()" in fw["code"]

    def test_serial_begin_present(self):
        assert "Serial.begin" in self._gen("Arduino", [], [])["code"]

    def test_pir_led_reaction_rule_in_code(self):
        assert "motion == 1" in self._gen("Arduino", ["LED_Single"], ["PIR"])["code"]

    @pytest.mark.parametrize("brain,include", [
        ("Arduino",  "#include <DHT.h>"),
        ("Arduino",  "#include <Servo.h>"),
        ("Arduino",  "#include <Adafruit_NeoPixel.h>"),
        ("Arduino",  "#include <Stepper.h>"),
        ("ESP32",    "#include <WiFi.h>"),
    ])
    def test_library_includes(self, brain, include):
        comp_map = {
            "#include <DHT.h>": (["LED_Single"], ["TempHumid"]),
            "#include <Servo.h>": (["Servo"], ["Ultrasonic"]),
            "#include <Adafruit_NeoPixel.h>": (["NeoPixel"], []),
            "#include <Stepper.h>": (["Stepper"], []),
            "#include <WiFi.h>": (["LED_Single"], []),
        }
        outs, sens = comp_map[include]
        assert include in self._gen(brain, outs, sens)["code"]

    @pytest.mark.parametrize("outputs,sensors,keyword", [
        (["LED_Single"], [],           "LED_PIN"),
        (["Relay"],      [],           "RELAY_PIN"),
        ([],             ["PIR"],      "PIR_PIN"),
        ([],             ["Ultrasonic"],"TRIG_PIN"),
        ([],             ["SoilMoisture"],"SOIL_PIN"),
    ])
    def test_pin_defines_present(self, outputs, sensors, keyword):
        assert keyword in self._gen("Arduino", outputs, sensors)["code"]

    def test_auto_brain_same_as_arduino(self):
        fw_auto = generate_firmware("auto", "5V", ["LED_Single"], [])
        fw_ard  = generate_firmware("Arduino", "5V", ["LED_Single"], [])
        assert fw_auto["lang"] == fw_ard["lang"]

    def test_project_name_in_header(self):
        fw = generate_firmware("Arduino", "5V", ["LED_Single"], [], project_name="自動澆水")
        assert "自動澆水" in fw["code"]

    def test_empty_comps_still_generates(self):
        assert "void setup()" in self._gen("Arduino", [], [])["code"]


# ── generate_firmware：RPi ────────────────────────────────────

class TestGenerateFirmwareRPi:
    def _gen(self, outputs, sensors):
        return generate_firmware("RPi", "5V", outputs, sensors)

    def test_lang_python(self):
        fw = self._gen(["LED_Single"], [])
        assert fw["lang"] == "python" and fw["ext"] == ".py"

    def test_gpiozero_import(self):
        assert "gpiozero" in self._gen(["LED_Single"], [])["code"]

    def test_while_true(self):
        assert "while True:" in self._gen(["LED_Single"], [])["code"]

    @pytest.mark.parametrize("sensors,keyword", [
        (["TempHumid"],  "Adafruit_DHT"),
        (["Ultrasonic"], "DistanceSensor"),
        (["PIR"],        "MotionSensor"),
    ])
    def test_sensor_imports(self, sensors, keyword):
        assert keyword in self._gen(["LED_Single"], sensors)["code"]

    def test_relay_output_device(self):
        assert "OutputDevice" in self._gen(["Relay"], [])["code"]

    def test_header_brain_label(self):
        assert "Raspberry Pi" in self._gen(["LED_Single"], [])["code"]


# ── generate_firmware：Microbit ───────────────────────────────

class TestGenerateFirmwareMicrobit:
    def _gen(self, outputs, sensors):
        return generate_firmware("Microbit", "3.3V", outputs, sensors)

    def test_lang_python(self):
        fw = self._gen(["LED_Single"], [])
        assert fw["lang"] == "python" and fw["ext"] == ".py"

    def test_microbit_import(self):
        assert "from microbit import" in self._gen(["LED_Single"], [])["code"]

    def test_while_true(self):
        assert "while True:" in self._gen(["LED_Single"], [])["code"]

    @pytest.mark.parametrize("outputs,sensors,keyword", [
        (["Buzzer_Active"], ["PIR"],       "music"),
        ([],                ["Ultrasonic"],"import machine"),
        (["NeoPixel"],      [],            "neopixel"),
    ])
    def test_keyword_present(self, outputs, sensors, keyword):
        assert keyword in self._gen(outputs, sensors)["code"]


# ── TEST_TEMPLATES ────────────────────────────────────────────

class TestTestTemplates:
    def test_all_keys_strings(self):
        for k in TEST_TEMPLATES:
            assert isinstance(k, str)

    def test_returns_code_and_lang(self):
        result = TEST_TEMPLATES["LED_Single"]({"+": 13})
        assert "code" in result and "lang" in result

    @pytest.mark.parametrize("comp,pin_map", [
        ("LED_Single",    {"+": 13}),
        ("Buzzer_Active", {"SIG": 8}),
        ("Relay",         {"IN": 7}),
        ("Servo",         {"SIG": 9}),
        ("NeoPixel",      {"DIN": 6}),
        ("TempHumid",     {"DATA": 2}),
        ("Ultrasonic",    {"TRIG": 4, "ECHO": 5}),
        ("PIR",           {"OUT": 3}),
        ("SoilMoisture",  {"AO": "A0"}),
        ("Light",         {"LDR": "A1"}),
        ("LED_RGB",       {"R": 9, "G": 10, "B": 11}),
        ("Stepper",       {"IN1": 8, "IN2": 9, "IN3": 10, "IN4": 11}),
        ("DCMotor",       {"ENA": 5, "IN1": 6, "IN2": 7}),
        ("Pump",          {"IN": 7}),
    ])
    def test_template_code_nonempty(self, comp, pin_map):
        result = TEST_TEMPLATES[comp](pin_map)
        assert isinstance(result["code"], str) and len(result["code"]) > 20

    def test_neopixel_uses_pin_number(self):
        assert "6" in TEST_TEMPLATES["NeoPixel"]({"DIN": 6})["code"]

    def test_dht_include_and_pin(self):
        code = TEST_TEMPLATES["TempHumid"]({"DATA": 2})["code"]
        assert "DHT" in code and "2" in code

    def test_stepper_include(self):
        code = TEST_TEMPLATES["Stepper"]({"IN1": 8, "IN2": 9, "IN3": 10, "IN4": 11})["code"]
        assert "#include <Stepper.h>" in code


# ── _wrap_text ────────────────────────────────────────────────

class TestWrapText:
    def test_empty_returns_empty(self):
        assert _wrap_text("") == []

    def test_short_not_split(self):
        assert _wrap_text("hello", width=20) == ["hello"]

    def test_long_split_within_width(self):
        result = _wrap_text("a" * 120, width=58)
        assert len(result) > 1 and all(len(l) <= 58 for l in result)

    def test_cjk_double_width(self):
        assert len(_wrap_text("中" * 30, width=58)) >= 2


# ── generate_test_code ────────────────────────────────────────

class TestGenerateTestCode:
    def test_returns_dict(self):
        assert isinstance(generate_test_code("Arduino", ["LED_Single"]), dict)

    def test_led_code_present(self):
        result = generate_test_code("Arduino", ["LED_Single"])
        assert "LED_Single" in result and "code" in result["LED_Single"]

    def test_unknown_comp_excluded(self):
        assert "UnknownWidget" not in generate_test_code("Arduino", ["UnknownWidget"])

    def test_multiple_comps_all_returned(self):
        result = generate_test_code("Arduino", ["LED_Single", "TempHumid", "PIR"])
        assert len(result) == 3

    def test_auto_brain_works(self):
        assert "LED_Single" in generate_test_code("auto", ["LED_Single"])
