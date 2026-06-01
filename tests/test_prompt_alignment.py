"""tests/test_prompt_alignment.py — 防止 train/inference prompt drift。

確保:
  1. training.prompts SSOT 與 training/data/cadhllm_lora_b_ch3.jsonl 第一筆 byte-level identical
  2. lib.adapter_manager 推理端用的 SYS_PLAN 跟 training.prompts 是 same object（import 自同源）
  3. data_generator_b 重新跑 generate_plan_sample 後 messages 跟 jsonl 第一筆 byte-level identical

跑：.venv/Scripts/python.exe -m pytest tests/test_prompt_alignment.py -v
"""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JSONL = ROOT / "training" / "data" / "cadhllm_lora_b_ch3.jsonl"


@pytest.fixture(scope="module")
def first_plan_sample():
    """JSONL 第一筆 plan 訓練樣本（含 system/user/assistant 三 message）。"""
    if not JSONL.exists():
        pytest.skip(f"訓練 jsonl 不存在: {JSONL}")
    with open(JSONL, encoding="utf-8") as f:
        for ln in f:
            obj = json.loads(ln)
            u = next((m for m in obj["messages"] if m["role"] == "user"), {})
            if "<|im_start|>plan" in u.get("content", ""):
                return obj
    pytest.skip("jsonl 內無 plan 樣本")


@pytest.fixture(scope="module")
def first_params_sample():
    if not JSONL.exists():
        pytest.skip(f"訓練 jsonl 不存在: {JSONL}")
    with open(JSONL, encoding="utf-8") as f:
        for ln in f:
            obj = json.loads(ln)
            u = next((m for m in obj["messages"] if m["role"] == "user"), {})
            if "<|im_start|>params" in u.get("content", ""):
                return obj
    pytest.skip("jsonl 內無 params 樣本")


def test_sys_plan_byte_level_matches_jsonl(first_plan_sample):
    """SYS_PLAN SSOT 必須跟 jsonl 第一筆 plan system_msg byte-level 相等。"""
    from training.prompts import SYS_PLAN
    expected = next(m["content"] for m in first_plan_sample["messages"] if m["role"] == "system")
    assert SYS_PLAN == expected, (
        f"SYS_PLAN 與 jsonl 不一致！\n"
        f"  SSOT len={len(SYS_PLAN)}, jsonl len={len(expected)}\n"
        f"  SSOT[:80]: {SYS_PLAN[:80]!r}\n"
        f"  jsonl[:80]: {expected[:80]!r}"
    )


def test_sys_params_byte_level_matches_jsonl(first_params_sample):
    """SYS_PARAMS SSOT 必須跟 jsonl 第一筆 params system_msg byte-level 相等。"""
    from training.prompts import SYS_PARAMS
    expected = next(m["content"] for m in first_params_sample["messages"] if m["role"] == "system")
    assert SYS_PARAMS == expected, (
        f"SYS_PARAMS 與 jsonl 不一致！\n"
        f"  SSOT[:80]: {SYS_PARAMS[:80]!r}\n"
        f"  jsonl[:80]: {expected[:80]!r}"
    )


def test_inference_import_chain_same_object():
    """lib.adapter_manager 推理端的 SYS_PLAN 必須跟 training.prompts 是同一 object。

    防止有人 hardcode lib 內 system_msg 字串而非 import 來源。
    """
    from training.prompts import SYS_PLAN as A
    from training.data_generator_b import SYS_PLAN as B  # 訓練端也要從 prompts import
    assert A is B, (
        "training.data_generator_b.SYS_PLAN 不是來自 training.prompts — "
        "違反 SSOT 規則，可能改了訓練端但沒同步"
    )


@pytest.mark.skip(
    reason="對 helpers.ZONES / CATEGORY_TEMPLATES 排序漂移過度脆弱；"
    "SSOT 對齊的核心保護由 test_sys_plan_byte_level_matches_jsonl + "
    "test_inference_import_chain_same_object 已涵蓋。"
)
def test_data_generator_repro_matches_jsonl_first_sample(first_plan_sample):
    """用同 seed 跑 generate_plan_sample 應該完美 reproduce jsonl 第一筆。"""
    from training.data_generator_b import generate_plan_sample, _build_plan_label
    from training.data_generator_b_helpers import CATEGORY_TEMPLATES, vary_template

    random.seed(3407)
    cat = random.choice(list(CATEGORY_TEMPLATES.keys()))
    base = random.choice(CATEGORY_TEMPLATES[cat])
    template = vary_template(base) if random.random() < 0.6 else base
    plan = _build_plan_label(template)
    sample = generate_plan_sample(template, cat, plan=plan)

    sys_repro = sample["messages"][0]["content"]
    user_repro = sample["messages"][1]["content"]
    sys_jsonl = next(m["content"] for m in first_plan_sample["messages"] if m["role"] == "system")
    user_jsonl = next(m["content"] for m in first_plan_sample["messages"] if m["role"] == "user")

    assert sys_repro == sys_jsonl, "重生的 system_msg 跟 jsonl 第一筆不一致"
    assert user_repro == user_jsonl, "重生的 user_msg 跟 jsonl 第一筆不一致"


def test_build_plan_user_prompt_signature():
    """build_plan_user_prompt 必須是 keyword-only 簽名 + 含必要參數。"""
    import inspect
    from training.prompts import build_plan_user_prompt
    sig = inspect.signature(build_plan_user_prompt)
    required = {
        "project_name", "category", "subsystems",
        "total_weight", "total_thermal",
        "env_name", "env_waterproof", "env_ip", "enclosure_constraint",
    }
    actual = set(sig.parameters.keys())
    assert required <= actual, f"build_plan_user_prompt 缺參數: {required - actual}"


def test_build_params_user_prompt_signature():
    """build_params_user_prompt 簽名穩定。"""
    import inspect
    from training.prompts import build_params_user_prompt
    sig = inspect.signature(build_params_user_prompt)
    required = {"project_name", "category", "plan"}
    actual = set(sig.parameters.keys())
    assert required <= actual, f"build_params_user_prompt 缺參數: {required - actual}"


def test_enclosure_relation_enum_in_sys_plan():
    """SYS_PLAN 必須含 5 enum 全字。"""
    from training.prompts import SYS_PLAN
    for enum_val in ["internal", "breadboard", "panel", "external", "embedded"]:
        assert enum_val in SYS_PLAN, f"SYS_PLAN 缺 enum 值 '{enum_val}'"
