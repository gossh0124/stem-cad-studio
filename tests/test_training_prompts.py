"""Tests for training/prompts.py — LoRA prompt SSOT."""
from __future__ import annotations

import json
import pytest

from training.prompts import (
    SYS_PHASE1,
    SYS_PLAN,
    SYS_PARAMS,
    build_plan_user_prompt,
    build_params_user_prompt,
)


class TestSysConstants:
    """System prompt constants are non-empty and contain required keywords."""

    def test_sys_phase1_non_empty(self):
        assert len(SYS_PHASE1) > 100

    def test_sys_phase1_contains_json_rule(self):
        assert "JSON" in SYS_PHASE1

    def test_sys_phase1_contains_components(self):
        assert "components" in SYS_PHASE1

    def test_sys_phase1_contains_cot_plan(self):
        assert "cot_plan" in SYS_PHASE1

    def test_sys_phase1_contains_brain_power_control(self):
        assert "Brain" in SYS_PHASE1
        assert "Power" in SYS_PHASE1
        assert "Control" in SYS_PHASE1

    def test_sys_phase1_no_markdown(self):
        assert "Markdown" in SYS_PHASE1  # rule says "no Markdown"

    def test_sys_plan_non_empty(self):
        assert len(SYS_PLAN) > 50

    def test_sys_plan_contains_enclosure_relation(self):
        assert "enclosure_relation" in SYS_PLAN

    def test_sys_plan_mentions_five_buckets(self):
        for bucket in ("internal", "breadboard", "panel", "external", "embedded"):
            assert bucket in SYS_PLAN

    def test_sys_params_non_empty(self):
        assert len(SYS_PARAMS) > 50

    def test_sys_params_mentions_geometry(self):
        assert "enclosure_spec" in SYS_PARAMS
        assert "placements" in SYS_PARAMS

    def test_sys_params_mentions_units(self):
        assert "mm" in SYS_PARAMS

    def test_constants_are_strings(self):
        assert isinstance(SYS_PHASE1, str)
        assert isinstance(SYS_PLAN, str)
        assert isinstance(SYS_PARAMS, str)


class TestBuildPlanUserPrompt:
    """build_plan_user_prompt returns correctly formatted strings."""

    def test_basic_output(self):
        result = build_plan_user_prompt(
            project_name="auto_waterer",
            category="Gardening",
            subsystems=["Arduino-Uno-class(weight=25.0g, thermal=250.0mW)"],
            total_weight=70.0,
            total_thermal=500.0,
        )
        assert "<|im_start|>plan" in result
        assert "auto_waterer" in result
        assert "Gardening" in result

    def test_contains_subsystems(self):
        subs = ["Arduino-Uno-class(weight=25.0g, thermal=250.0mW)",
                "Sensor-SoilMoisture-class(weight=5.0g, thermal=25.0mW)"]
        result = build_plan_user_prompt(
            project_name="test",
            category="Gardening",
            subsystems=subs,
            total_weight=30.0,
            total_thermal=275.0,
        )
        for s in subs:
            assert s in result

    def test_contains_weight_and_thermal(self):
        result = build_plan_user_prompt(
            project_name="x",
            category="y",
            subsystems=["a"],
            total_weight=123.0,
            total_thermal=456.0,
        )
        assert "123" in result
        assert "456" in result

    def test_default_env(self):
        result = build_plan_user_prompt(
            project_name="x",
            category="y",
            subsystems=["a"],
            total_weight=10.0,
            total_thermal=10.0,
        )
        assert "indoor" in result
        assert "IP20" in result

    def test_custom_env(self):
        result = build_plan_user_prompt(
            project_name="x",
            category="y",
            subsystems=["a"],
            total_weight=10.0,
            total_thermal=10.0,
            env_name="outdoor",
            env_waterproof=True,
            env_ip="IP65",
        )
        assert "outdoor" in result
        assert "IP65" in result

    def test_custom_enclosure_constraint(self):
        result = build_plan_user_prompt(
            project_name="x",
            category="y",
            subsystems=["a"],
            total_weight=10.0,
            total_thermal=10.0,
            enclosure_constraint="large (300mm)",
        )
        assert "large (300mm)" in result


class TestBuildParamsUserPrompt:
    """build_params_user_prompt returns correctly formatted strings."""

    def test_basic_output(self):
        plan = {"placement_strategy": "gravity_bottom", "zones": []}
        result = build_params_user_prompt(
            project_name="test_project",
            category="Art",
            plan=plan,
        )
        assert "<|im_start|>params" in result
        assert "test_project" in result
        assert "Art" in result

    def test_contains_plan_json(self):
        plan = {"key": "value", "nested": {"a": 1}}
        result = build_params_user_prompt(
            project_name="x",
            category="y",
            plan=plan,
        )
        assert '"key"' in result
        assert '"value"' in result
        assert '"nested"' in result

    def test_plan_json_is_valid_json_substring(self):
        plan = {"placement_strategy": "gravity_bottom"}
        result = build_params_user_prompt(
            project_name="x",
            category="y",
            plan=plan,
        )
        json_start = result.index("{")
        json_end = result.rindex("}") + 1
        parsed = json.loads(result[json_start:json_end])
        assert parsed == plan

    def test_output_ends_with_instruction(self):
        result = build_params_user_prompt(
            project_name="x",
            category="y",
            plan={},
        )
        assert "ParamsJSON" in result
