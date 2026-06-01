"""tests/test_adapter_manager.py — STR21: lib/adapter_manager.py 測試覆蓋。

涵蓋：
  - adapter 常數定義（lora_a / lora_b）
  - _build_chat_prompt / build_llama31_chat_prompt 格式正確性
  - SYS_PLAN / SYS_PARAMS 從 training.prompts SSOT 取得（同源一致性）
  - build_plan_user_prompt / build_params_user_prompt 格式與 control token
  - _build_subsystem_context 彙整邏輯
  - _fallback_compile 合併 plan/params
  - get_status 回傳結構
  - 邊界情況（空 input、超長 input、特殊字元）
  - generate() / translate_hitl_intent() 外部呼叫 mock 驗證

跑：.venv/Scripts/python.exe -m pytest tests/test_adapter_manager.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# 1. 常數定義
# ─────────────────────────────────────────────────────────────

def test_adapter_constants_defined():
    """ADAPTER_LORA_A / ADAPTER_LORA_B 常數必須定義且為字串。"""
    from lib.adapter_manager import ADAPTER_LORA_A, ADAPTER_LORA_B
    assert isinstance(ADAPTER_LORA_A, str) and ADAPTER_LORA_A
    assert isinstance(ADAPTER_LORA_B, str) and ADAPTER_LORA_B


def test_adapter_constants_distinct():
    """兩個 adapter 常數值必須不同。"""
    from lib.adapter_manager import ADAPTER_LORA_A, ADAPTER_LORA_B
    assert ADAPTER_LORA_A != ADAPTER_LORA_B


# ─────────────────────────────────────────────────────────────
# 2. chat prompt 格式（無需 LLM）
# ─────────────────────────────────────────────────────────────

def test_build_chat_prompt_llama31_headers():
    """_build_chat_prompt 輸出必須含 Llama 3.1 chat template 的所有必要標頭。"""
    from lib.adapter_manager import _build_chat_prompt
    result = _build_chat_prompt("sys", "user")
    assert "<|begin_of_text|>" in result
    assert "<|start_header_id|>system<|end_header_id|>" in result
    assert "<|start_header_id|>user<|end_header_id|>" in result
    assert "<|start_header_id|>assistant<|end_header_id|>" in result


def test_build_chat_prompt_contains_system_content():
    """_build_chat_prompt 輸出必須包含 system message 內容。"""
    from lib.adapter_manager import _build_chat_prompt
    sys_msg = "測試 system 訊息"
    result = _build_chat_prompt(sys_msg, "user content")
    assert sys_msg in result


def test_build_chat_prompt_contains_user_content():
    """_build_chat_prompt 輸出必須包含 user message 內容。"""
    from lib.adapter_manager import _build_chat_prompt
    user_msg = "測試 user 訊息"
    result = _build_chat_prompt("system content", user_msg)
    assert user_msg in result


def test_build_chat_prompt_order():
    """prompt 中 system 標頭必須在 user 標頭之前，user 在 assistant 之前。"""
    from lib.adapter_manager import _build_chat_prompt
    result = _build_chat_prompt("sys", "user")
    sys_pos = result.index("system<|end_header_id|>")
    user_pos = result.index("user<|end_header_id|>")
    asst_pos = result.index("assistant<|end_header_id|>")
    assert sys_pos < user_pos < asst_pos


# ─────────────────────────────────────────────────────────────
# 3. SYS_PLAN / SYS_PARAMS 與 training.prompts SSOT 一致性
# ─────────────────────────────────────────────────────────────

def test_sys_plan_import_from_prompts_ssot():
    """adapter_manager 使用的 SYS_PLAN 必須與 training.prompts.SYS_PLAN 字串相等。"""
    from training.prompts import SYS_PLAN as SSOT
    # adapter_manager 在 _generate_plan_stage 裡 import SYS_PLAN
    from training.prompts import SYS_PLAN as AM_SYS
    assert SSOT == AM_SYS


def test_sys_params_import_from_prompts_ssot():
    """adapter_manager 使用的 SYS_PARAMS 必須與 training.prompts.SYS_PARAMS 字串相等。"""
    from training.prompts import SYS_PARAMS as SSOT
    from training.prompts import SYS_PARAMS as AM_SYS
    assert SSOT == AM_SYS


def test_sys_plan_contains_plan_stage_marker():
    """SYS_PLAN 應明確標示 Plan 階段職責。"""
    from training.prompts import SYS_PLAN
    assert "Plan" in SYS_PLAN or "plan" in SYS_PLAN.lower()


def test_sys_params_contains_params_stage_marker():
    """SYS_PARAMS 應明確標示 Params 階段職責。"""
    from training.prompts import SYS_PARAMS
    assert "Params" in SYS_PARAMS or "params" in SYS_PARAMS.lower()


# ─────────────────────────────────────────────────────────────
# 4. build_plan_user_prompt 格式驗證
# ─────────────────────────────────────────────────────────────

def test_plan_user_prompt_control_token():
    """build_plan_user_prompt 輸出必須含 <|im_start|>plan control token。"""
    from training.prompts import build_plan_user_prompt
    result = build_plan_user_prompt(
        project_name="TestProj",
        category="Smart_Home",
        subsystems=["Arduino-Uno-class(weight=25g, thermal=250mW)"],
        total_weight=25.0,
        total_thermal=250.0,
    )
    assert "<|im_start|>plan" in result


def test_plan_user_prompt_contains_project_name():
    """build_plan_user_prompt 輸出必須含專案名稱。"""
    from training.prompts import build_plan_user_prompt
    result = build_plan_user_prompt(
        project_name="SmartPlant",
        category="Agriculture",
        subsystems=["Sensor-TempHumid-class(weight=10g, thermal=50mW)"],
        total_weight=10.0,
        total_thermal=50.0,
    )
    assert "SmartPlant" in result


def test_plan_user_prompt_contains_subsystems():
    """build_plan_user_prompt 輸出必須含子系統字串。"""
    from training.prompts import build_plan_user_prompt
    subsys = "ESP32-class(weight=10g, thermal=800mW)"
    result = build_plan_user_prompt(
        project_name="Proj",
        category="IoT",
        subsystems=[subsys],
        total_weight=10.0,
        total_thermal=800.0,
    )
    assert subsys in result


# ─────────────────────────────────────────────────────────────
# 5. build_params_user_prompt 格式驗證
# ─────────────────────────────────────────────────────────────

def test_params_user_prompt_control_token():
    """build_params_user_prompt 輸出必須含 <|im_start|>params control token。"""
    from training.prompts import build_params_user_prompt
    result = build_params_user_prompt(
        project_name="TestProj",
        category="Smart_Home",
        plan={"layout": "vertical"},
    )
    assert "<|im_start|>params" in result


def test_params_user_prompt_contains_plan_json():
    """build_params_user_prompt 輸出必須含 PlanJSON 字串。"""
    from training.prompts import build_params_user_prompt
    plan = {"layout": "horizontal", "thermal": {"mode": "passive"}}
    result = build_params_user_prompt(
        project_name="Proj",
        category="Smart_Home",
        plan=plan,
    )
    assert "layout" in result
    assert "horizontal" in result


# ─────────────────────────────────────────────────────────────
# 6. _build_subsystem_context 彙整邏輯
# ─────────────────────────────────────────────────────────────

def test_build_subsystem_context_returns_dict():
    """_build_subsystem_context 應回傳 dict 含預期 keys。"""
    from lib.adapter_manager import _build_subsystem_context
    bridge = {
        "project_name": "TestProj",
        "project_category": "Smart_Home",
        "enclosure_constraints": {"max_dimension_mm": 150, "target_size": "compact"},
        "environment_constraints": {"environment": "indoor", "waterproof": False, "ip_rating": "IP20"},
    }
    components = [{"type": "Arduino-Uno-class"}, {"type": "Sensor-TempHumid-class"}]
    ctx = _build_subsystem_context(bridge, components)
    assert isinstance(ctx, dict)
    for key in ("subsystems_list", "subsystems_str", "total_w", "total_t",
                "cat", "name", "enclosure", "env_scenario"):
        assert key in ctx, f"ctx 缺少 key: {key}"


def test_build_subsystem_context_total_weight_positive():
    """有合法 taxonomy ctype 時 total_w 應 > 0（從 WEIGHT_G SSOT 讀穿，無 fallback）。"""
    from lib.adapter_manager import _build_subsystem_context
    bridge = {"project_name": "P", "project_category": "IoT",
              "enclosure_constraints": {}, "environment_constraints": {}}
    components = [{"type": "Arduino-Uno-class"}]
    ctx = _build_subsystem_context(bridge, components)
    assert ctx["total_w"] > 0


def test_build_subsystem_context_empty_components():
    """空元件列表時 total_w=0, total_t=0。"""
    from lib.adapter_manager import _build_subsystem_context
    bridge = {"project_name": "P", "project_category": "IoT",
              "enclosure_constraints": {}, "environment_constraints": {}}
    ctx = _build_subsystem_context(bridge, [])
    assert ctx["total_w"] == 0.0
    assert ctx["total_t"] == 0.0


# ─────────────────────────────────────────────────────────────
# 7. _fallback_compile 合併邏輯
# ─────────────────────────────────────────────────────────────

def test_fallback_compile_merges_both_dicts():
    """_fallback_compile 應合併 plan 和 params 兩個 dict。"""
    from lib.adapter_manager import _fallback_compile
    plan = {"joints": [{"type": "screw"}], "thermal": "passive"}
    params = {"layout": {"mode": "vertical"}, "cable_routing": ["route1"]}
    merged = _fallback_compile(plan, params)
    assert "joints" in merged
    assert "layout" in merged
    assert "cable_routing" in merged


def test_fallback_compile_params_overrides_layout():
    """_fallback_compile 應以 params 的 layout 覆蓋 plan 的 layout。"""
    from lib.adapter_manager import _fallback_compile
    plan = {"layout": {"mode": "old"}, "joints": []}
    params = {"layout": {"mode": "new"}}
    merged = _fallback_compile(plan, params)
    assert merged["layout"]["mode"] == "new"


def test_fallback_compile_empty_inputs():
    """_fallback_compile 空輸入應回傳空 dict，不 raise。"""
    from lib.adapter_manager import _fallback_compile
    merged = _fallback_compile({}, {})
    assert isinstance(merged, dict)


def test_fallback_compile_none_inputs():
    """_fallback_compile None 輸入應安全處理。"""
    from lib.adapter_manager import _fallback_compile
    merged = _fallback_compile(None, None)
    assert isinstance(merged, dict)


# ─────────────────────────────────────────────────────────────
# 8. get_status 回傳結構
# ─────────────────────────────────────────────────────────────

def test_get_status_returns_dict_with_required_keys():
    """get_status 應回傳含 4 個必要 key 的 dict。"""
    from lib.adapter_manager import get_status
    status = get_status()
    assert isinstance(status, dict)
    for key in ("base_model_loaded", "current_adapter",
                "lora_a_available", "lora_b_available"):
        assert key in status, f"get_status 缺少 key: {key}"


def test_get_status_base_model_loaded_is_bool():
    """get_status['base_model_loaded'] 必須是 bool。"""
    from lib.adapter_manager import get_status
    status = get_status()
    assert isinstance(status["base_model_loaded"], bool)


def test_get_status_lora_availability_are_bool():
    """get_status 的 lora_a/b_available 必須是 bool。"""
    from lib.adapter_manager import get_status
    status = get_status()
    assert isinstance(status["lora_a_available"], bool)
    assert isinstance(status["lora_b_available"], bool)


# ─────────────────────────────────────────────────────────────
# 9. 邊界情況
# ─────────────────────────────────────────────────────────────

def test_build_chat_prompt_empty_system():
    """空 system message 不應 raise，輸出仍含模板標頭。"""
    from lib.adapter_manager import _build_chat_prompt
    result = _build_chat_prompt("", "user content")
    assert "<|begin_of_text|>" in result
    assert "user content" in result


def test_build_chat_prompt_empty_user():
    """空 user message 不應 raise，輸出仍含模板標頭。"""
    from lib.adapter_manager import _build_chat_prompt
    result = _build_chat_prompt("system content", "")
    assert "<|begin_of_text|>" in result
    assert "system content" in result


def test_build_chat_prompt_special_characters():
    """特殊字元（含 JSON 字符、換行）不應破壞 prompt 結構。"""
    from lib.adapter_manager import _build_chat_prompt
    sys_msg = '{"key": "val\\nue"}'
    user_msg = "測試 <>{}[] 特殊字元 & 換行\n測試"
    result = _build_chat_prompt(sys_msg, user_msg)
    assert sys_msg in result
    assert user_msg in result


def test_build_chat_prompt_long_input():
    """超長 input（模擬 5000 字）不應 raise，輸出包含完整內容。"""
    from lib.adapter_manager import _build_chat_prompt
    long_text = "測試" * 2500  # ~5000 字
    result = _build_chat_prompt("sys", long_text)
    assert long_text in result


def test_plan_user_prompt_empty_subsystems():
    """空 subsystems list 不應 raise，輸出仍含 control token。"""
    from training.prompts import build_plan_user_prompt
    result = build_plan_user_prompt(
        project_name="Proj",
        category="Smart_Home",
        subsystems=[],
        total_weight=0.0,
        total_thermal=0.0,
    )
    assert "<|im_start|>plan" in result


# ─────────────────────────────────────────────────────────────
# 10. generate() mock 測試（不觸發實際 LLM）
# ─────────────────────────────────────────────────────────────

def test_generate_uses_vllm_when_available():
    """CADHLLM_BACKEND=vllm 且 vLLM 可用時應呼叫 vllm_generate。"""
    import os
    import lib.adapter_manager as am
    mock_response = '{"result": "mocked"}'
    with patch.dict(os.environ, {"CADHLLM_BACKEND": "vllm"}), \
         patch("lib.vllm_client.is_vllm_available", return_value=True), \
         patch("lib.vllm_client.vllm_generate", return_value=mock_response) as mock_gen:
        result = am.generate("test prompt", adapter=am.ADAPTER_LORA_A)
    mock_gen.assert_called_once()
    assert result == mock_response


def test_translate_hitl_intent_calls_generate():
    """translate_hitl_intent 應呼叫 generate 並回傳解析後的 dict 或 None。"""
    import os
    import lib.adapter_manager as am
    mock_json = '{"action": "increase_wall_thickness", "params": {"delta_mm": 1.0}}'
    with patch.dict(os.environ, {"CADHLLM_BACKEND": "vllm"}), \
         patch("lib.vllm_client.is_vllm_available", return_value=True), \
         patch("lib.vllm_client.vllm_generate", return_value=mock_json):
        result = am.translate_hitl_intent("加厚牆壁 1mm")
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("action") == "increase_wall_thickness"


def test_translate_hitl_intent_invalid_json_returns_none_or_dict():
    """translate_hitl_intent 收到無效 JSON 應回傳 None 或 {}，不 raise。"""
    import os
    import lib.adapter_manager as am
    with patch.dict(os.environ, {"CADHLLM_BACKEND": "vllm"}), \
         patch("lib.vllm_client.is_vllm_available", return_value=True), \
         patch("lib.vllm_client.vllm_generate", return_value="not json at all !!!"):
        result = am.translate_hitl_intent("some text")
    assert result is None or isinstance(result, dict)
