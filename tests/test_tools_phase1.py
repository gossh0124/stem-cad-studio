"""test_tools_phase1.py -- Phase I tool functions tests."""
import json
import pytest

from lib.tools import (
    generate_aux_logic,
    validate_category,
    extract_output,
    extract_json,
    build_llama31_chat_prompt,
    format_prompt,
)
from lib.config import TAXONOMY_CONFIG


# ── generate_aux_logic ──────────────────────────────────────


class TestGenerateAuxLogic:
    def test_watering_project(self):
        aux, has_sound = generate_aux_logic("auto_waterer", "build a soil moisture auto watering pump system")
        roles = [a["role"] for a in aux]
        assert "Sensor" in roles
        assert "Actuator" in roles
        assert has_sound is False

    def test_music_project_has_sound(self):
        aux, has_sound = generate_aux_logic("music_box", "build a music box that plays songs")
        assert has_sound is True
        roles = [a["role"] for a in aux]
        assert "Sound" in roles

    def test_alarm_has_sound(self):
        aux, has_sound = generate_aux_logic("alarm", "build a burglar alarm")
        assert has_sound is True

    def test_robot_car_has_motor(self):
        aux, _ = generate_aux_logic("rc_car", "build a remote control car")
        roles = [a["role"] for a in aux]
        assert "Actuator" in roles

    def test_obstacle_avoidance_has_ultrasonic(self):
        aux, _ = generate_aux_logic("obstacle_car", "build an obstacle avoidance robot")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Sensor-Ultrasonic-class" in types

    def test_display_project(self):
        aux, _ = generate_aux_logic("monitor", "build a temperature monitor with OLED display")
        roles = [a["role"] for a in aux]
        assert "Display" in roles

    def test_servo_project(self):
        aux, _ = generate_aux_logic("curtain", "build an automatic curtain with servo")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Motor-Servo-class" in types

    def test_temperature_sensor(self):
        aux, _ = generate_aux_logic("weather", "build a temperature and humidity station")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Sensor-TempHumid-class" in types

    def test_pir_motion_detection(self):
        aux, _ = generate_aux_logic("security", "build a motion detection security system")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Sensor-PIR-class" in types

    def test_relay_project(self):
        aux, _ = generate_aux_logic("relay_ctrl", "build a relay controller for AC appliances")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Relay-Module-class" in types

    def test_night_light_led_pwm(self):
        aux, _ = generate_aux_logic("nightlight", "build a smart night light")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Lighting-LED-PWM-class" in types

    def test_wearable_light_rgb(self):
        aux, _ = generate_aux_logic("bowtie", "build a clap-reactive wearable led bowtie")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Lighting-LED-RGB-class" in types

    def test_light_sensor_detected(self):
        aux, _ = generate_aux_logic("light_meter", "build a light sensor for ambient light detection")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Sensor-Light-class" in types

    def test_soil_moisture_sensor(self):
        aux, _ = generate_aux_logic("planter", "build a soil moisture monitor for plants")
        types = []
        for a in aux:
            types.extend(a.get("recommended_types", []))
        assert "Sensor-SoilMoisture-class" in types

    def test_empty_input_no_aux(self):
        aux, has_sound = generate_aux_logic("", "")
        assert len(aux) == 0
        assert has_sound is False

    def test_chinese_keywords(self):
        aux, has_sound = generate_aux_logic("", "make an automatic watering system for 澆花 plants")
        roles = [a["role"] for a in aux]
        assert "Sensor" in roles or "Actuator" in roles

    def test_speaker_vs_buzzer(self):
        aux_speaker, _ = generate_aux_logic("", "build a speaker music player")
        speaker_types = []
        for a in aux_speaker:
            speaker_types.extend(a.get("recommended_types", []))

        aux_buzzer, _ = generate_aux_logic("", "build an alarm buzzer")
        buzzer_types = []
        for a in aux_buzzer:
            buzzer_types.extend(a.get("recommended_types", []))

        assert "Speaker-class" in speaker_types
        assert "Buzzer-Active-class" in buzzer_types

    def test_aux_items_have_tags(self):
        aux, _ = generate_aux_logic("bot", "build a robot car with speakers")
        for item in aux:
            assert "tags" in item
            assert isinstance(item["tags"], list)

    def test_aux_items_have_recommended_types(self):
        aux, _ = generate_aux_logic("bot", "build a robot car with speakers")
        for item in aux:
            assert "recommended_types" in item
            assert len(item["recommended_types"]) > 0


# ── validate_category ───────────────────────────────────────


class TestValidateCategory:
    @pytest.mark.parametrize("cat", TAXONOMY_CONFIG["project_categories"])
    def test_valid_categories_unchanged(self, cat):
        assert validate_category(cat) == cat

    def test_fuzzy_match_lowercase(self):
        assert validate_category("education") == "Education"

    def test_fuzzy_match_partial(self):
        result = validate_category("smart")
        assert result == "Smart_Home"

    def test_completely_unknown_defaults_education(self):
        assert validate_category("xyzzy_nonsense") == "Education"

    def test_empty_string_matches_first(self):
        result = validate_category("")
        assert result in TAXONOMY_CONFIG["project_categories"]

    def test_robotics_variant(self):
        assert validate_category("robot") in ("Robotics", "Education")

    def test_gardening_match(self):
        assert validate_category("gardening") == "Gardening"

    def test_security_match(self):
        assert validate_category("security") == "Security"


# ── extract_output ──────────────────────────────────────────


class TestExtractOutput:
    def test_valid_json(self):
        obj, method, err = extract_output('{"key": "value"}')
        assert obj == {"key": "value"}
        assert method == "strict"
        assert err is None

    def test_json_in_markdown_block(self):
        text = '```json\n{"key": "value"}\n```'
        obj, method, err = extract_output(text)
        assert obj == {"key": "value"}
        assert method == "strict"

    def test_json_with_surrounding_text(self):
        text = 'Here is the output: {"key": "value"} end'
        obj, method, err = extract_output(text)
        assert obj == {"key": "value"}

    def test_empty_text_fails(self):
        obj, method, err = extract_output("")
        assert obj is None
        assert method == "failed"
        assert err == "Empty text"

    def test_none_text_fails(self):
        obj, method, err = extract_output(None)
        assert obj is None
        assert method == "failed"

    def test_nested_json(self):
        data = {"project": {"name": "test", "components": [1, 2, 3]}}
        obj, method, _ = extract_output(json.dumps(data))
        assert obj == data

    def test_no_json_at_all(self):
        obj, method, _ = extract_output("This is plain text without JSON")
        assert obj is None
        assert method == "failed"


# ── extract_json ────────────────────────────────────────────


class TestExtractJson:
    def test_simple_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_with_prefix(self):
        result = extract_json('Some text {"a": 1} more text')
        assert result == {"a": 1}

    def test_nested_braces(self):
        text = '{"outer": {"inner": "value"}}'
        result = extract_json(text)
        assert result == {"outer": {"inner": "value"}}

    def test_empty_string(self):
        assert extract_json("") is None

    def test_none_input(self):
        assert extract_json(None) is None

    def test_no_json(self):
        assert extract_json("no json here") is None

    def test_no_object_braces(self):
        result = extract_json("just plain text no braces")
        assert result is None

    def test_whitespace_json(self):
        result = extract_json("  { \"key\": \"val\" }  ")
        assert result == {"key": "val"}


# ── build_llama31_chat_prompt ───────────────────────────────


class TestBuildLlama31ChatPrompt:
    def test_contains_begin_of_text(self):
        prompt = build_llama31_chat_prompt("sys", "usr")
        assert "<|begin_of_text|>" in prompt

    def test_contains_system_header(self):
        prompt = build_llama31_chat_prompt("sys", "usr")
        assert "<|start_header_id|>system<|end_header_id|>" in prompt

    def test_contains_user_header(self):
        prompt = build_llama31_chat_prompt("sys", "usr")
        assert "<|start_header_id|>user<|end_header_id|>" in prompt

    def test_contains_assistant_header(self):
        prompt = build_llama31_chat_prompt("sys", "usr")
        assert "<|start_header_id|>assistant<|end_header_id|>" in prompt

    def test_system_content_present(self):
        prompt = build_llama31_chat_prompt("My system message", "My user input")
        assert "My system message" in prompt

    def test_user_content_present(self):
        prompt = build_llama31_chat_prompt("sys", "My user input")
        assert "My user input" in prompt

    def test_eot_tokens(self):
        prompt = build_llama31_chat_prompt("sys", "usr")
        assert prompt.count("<|eot_id|>") == 2

    def test_order_system_before_user(self):
        prompt = build_llama31_chat_prompt("SYS_MSG", "USR_MSG")
        sys_pos = prompt.index("SYS_MSG")
        usr_pos = prompt.index("USR_MSG")
        assert sys_pos < usr_pos


# ── format_prompt ───────────────────────────────────────────


class TestFormatPrompt:
    def test_basic_prompt(self):
        prompt = format_prompt("Build a robot car")
        assert "Build a robot car" in prompt
        assert "<|begin_of_text|>" in prompt

    def test_with_rag_context(self):
        prompt = format_prompt("Build a robot", rag_context="RAG: similar project found")
        assert "RAG: similar project found" in prompt

    def test_without_rag_context(self):
        prompt = format_prompt("Test instruction")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
