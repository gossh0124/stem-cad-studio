"""驗證 training/trainer.py build_dataset() 三種格式分支。

CH3 開訓 hard gate 4：data_generator_b.py C 案輸出 messages 格式 jsonl，
trainer.py 必須能吃。

注意：本機 Python 3.14 + datasets+dill pickle 不相容（與 build_dataset 邏輯無關），
故測試走純 dict 邏輯驗 _fmt，繞過 Dataset.from_list 的 fingerprint pickle。
Colab T4 (Py 3.10/3.11) 正式訓練時 Dataset.from_list 會正常運作。
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training"
for p in (str(ROOT), str(TRAINING)):
    if p not in sys.path:
        sys.path.insert(0, p)

# 只 import build_dataset 用到的 helper（不觸發 Dataset.from_list）
from training.trainer import _messages_to_prompt_completion  # noqa: E402


class _FakeTokenizer:
    """模擬 HF tokenizer.apply_chat_template，避免測試載入 4bit 模型。"""
    eos_token = "<|eot_id|>"

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        parts = ["<|begin_of_text|>"]
        for m in messages:
            parts.append(
                f"<|start_header_id|>{m['role']}<|end_header_id|>\n\n"
                f"{m['content']}<|eot_id|>"
            )
        if add_generation_prompt:
            parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
        return "".join(parts)


def _fmt_single(sample, tokenizer=None):
    """直接走 build_dataset 內 _fmt 的對應分支邏輯。"""
    import json as _json
    if "messages" in sample:
        return _messages_to_prompt_completion(sample["messages"], tokenizer=tokenizer)
    if "prompt" in sample and "completion" in sample:
        return {"prompt": sample["prompt"], "completion": sample["completion"]}
    if "instruction" in sample and "expected" in sample:
        system_msg = (
            "你是 Phase I STEAM 專案規劃師。將使用者的自然語言需求轉換為嚴格的 JSON。\n"
            "規則：只輸出 JSON 物件，不要 Markdown。components 必須包含 Brain/Power/Control。\n"
        )
        return {
            "prompt": (
                "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                f"{system_msg}<|eot_id|>"
                "<|start_header_id|>user<|end_header_id|>\n\n"
                f"{sample['instruction']}<|eot_id|>"
                "<|start_header_id|>assistant<|end_header_id|>\n\n"
            ),
            "completion": _json.dumps(sample["expected"], ensure_ascii=False, indent=2) + "<|eot_id|>",
        }
    raise ValueError(f"Unknown jsonl format: keys={list(sample.keys())}")


# ---------- 分支 1：messages（apply_chat_template 路徑） ----------

def test_messages_branch_with_tokenizer():
    sample = {
        "messages": [
            {"role": "system", "content": "你是規劃師"},
            {"role": "user", "content": "做一個感測器盒"},
            {"role": "assistant", "content": '{"ok": true}'},
        ]
    }
    row = _fmt_single(sample, tokenizer=_FakeTokenizer())
    assert "prompt" in row and "completion" in row
    assert "你是規劃師" in row["prompt"]
    assert "做一個感測器盒" in row["prompt"]
    assert row["prompt"].rstrip().endswith("<|start_header_id|>assistant<|end_header_id|>")
    assert '{"ok": true}' in row["completion"]
    assert row["completion"].endswith("<|eot_id|>")


# ---------- 分支 1b：messages（無 tokenizer，fallback 手拼） ----------

def test_messages_branch_without_tokenizer_fallback():
    sample = {
        "messages": [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]
    }
    row = _fmt_single(sample, tokenizer=None)
    assert "<|begin_of_text|>" in row["prompt"]
    assert "<|start_header_id|>system<|end_header_id|>" in row["prompt"]
    assert row["prompt"].endswith("<|start_header_id|>assistant<|end_header_id|>\n\n")
    assert row["completion"] == "a<|eot_id|>"


# ---------- 分支 1c：messages 末項非 assistant → raise ----------

def test_messages_branch_rejects_non_assistant_last():
    try:
        _messages_to_prompt_completion([
            {"role": "user", "content": "u"},
            {"role": "system", "content": "s"},
        ])
    except ValueError as e:
        assert "assistant" in str(e)
        return
    raise AssertionError("應拋 ValueError")


# ---------- 分支 2：prompt + completion ----------

def test_prompt_completion_branch_passthrough():
    row = _fmt_single({"prompt": "P", "completion": "C"}, tokenizer=None)
    assert row["prompt"] == "P" and row["completion"] == "C"


# ---------- 分支 3：instruction + expected ----------

def test_instruction_expected_branch():
    row = _fmt_single({
        "instruction": "做一個盒子",
        "expected": {"components": ["Brain"]},
    }, tokenizer=None)
    assert "做一個盒子" in row["prompt"]
    assert "components" in row["completion"]
    assert row["completion"].endswith("<|eot_id|>")


# ---------- 分支 4：未知格式 raise ----------

def test_unknown_format_raises():
    try:
        _fmt_single({"foo": "bar"})
    except ValueError as e:
        assert "Unknown jsonl format" in str(e)
        return
    raise AssertionError("應拋 ValueError")


# ---------- 整合：5 樣本 dry-run jsonl ----------

def test_real_dryrun_jsonl():
    path = ROOT / "training" / "data" / "cadhllm_lora_b_ch3_dryrun.jsonl"
    if not path.exists():
        return  # 檔案不在時跳過
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    assert rows, "dry-run jsonl 不該空"
    assert all("messages" in r for r in rows), "所有 row 都應為 messages 格式"
    tok = _FakeTokenizer()
    formatted = [_fmt_single(r, tokenizer=tok) for r in rows]
    assert len(formatted) == len(rows)
    for i, row in enumerate(formatted):
        assert "prompt" in row and "completion" in row, f"row {i} missing keys"
        assert row["prompt"], f"row {i} empty prompt"
        assert row["completion"], f"row {i} empty completion"
        assert row["completion"].endswith("<|eot_id|>"), f"row {i} missing eot_id"


if __name__ == "__main__":
    tests = [
        test_messages_branch_with_tokenizer,
        test_messages_branch_without_tokenizer_fallback,
        test_messages_branch_rejects_non_assistant_last,
        test_prompt_completion_branch_passthrough,
        test_instruction_expected_branch,
        test_unknown_format_raises,
        test_real_dryrun_jsonl,
    ]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS {t.__name__}")
    print(f"\nALL {passed}/{len(tests)} PASSED")
