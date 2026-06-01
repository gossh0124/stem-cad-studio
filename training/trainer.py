"""trainer.py — Phase I LoRA 訓練器（Colab 4bit 專用）。

使用 unsloth + trl SFTTrainer，適用 Colab T4/A100 環境。
產出標準 PEFT LoRA adapter。
"""
from __future__ import annotations
import json
import time
from typing import Any, Dict, List

from config import MODEL_CONFIG


def report_environment() -> Dict[str, Any]:
    info = {"cuda_available": False, "device_name": None,
            "vram_gb": None, "compute_capability": None}
    try:
        import torch
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            props = torch.cuda.get_device_properties(0)
            info["device_name"] = torch.cuda.get_device_name(0)
            info["vram_gb"] = round(props.total_memory / (1024 ** 3), 1)
            info["compute_capability"] = props.major + props.minor / 10
    except Exception as e:
        info["error"] = str(e)
    return info


def _messages_to_prompt_completion(messages: List[Dict[str, str]], tokenizer=None) -> Dict[str, str]:
    """將 HuggingFace 標準 chat 格式 [system,user,assistant] 轉為 prompt/completion。

    優先用 tokenizer.apply_chat_template；無 tokenizer 時 fallback Llama3 風格拼接，
    與既有 instruction/expected 分支對齊。
    """
    if not messages or messages[-1].get("role") != "assistant":
        raise ValueError(
            f"messages 最後一筆必須是 assistant；got roles={[m.get('role') for m in messages]}"
        )
    prefix_msgs = messages[:-1]
    completion_text = messages[-1].get("content", "")

    if tokenizer is not None and hasattr(tokenizer, "apply_chat_template"):
        try:
            prompt_text = tokenizer.apply_chat_template(
                prefix_msgs, tokenize=False, add_generation_prompt=True,
            )
            return {
                "prompt": prompt_text,
                "completion": completion_text + (tokenizer.eos_token or "<|eot_id|>"),
            }
        except (AttributeError, KeyError, TypeError) as _e:
            import warnings
            warnings.warn(f"apply_chat_template failed ({_e}), falling back to manual format")
            # fallback 到手拼

    # Fallback：Llama3 風格手拼，與既有 instruction/expected 分支格式對齊
    parts = ["<|begin_of_text|>"]
    for m in prefix_msgs:
        role = m.get("role", "user")
        content = m.get("content", "")
        parts.append(
            f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
        )
    parts.append("<|start_header_id|>assistant<|end_header_id|>\n\n")
    return {
        "prompt": "".join(parts),
        "completion": completion_text + "<|eot_id|>",
    }


def build_dataset(samples: List[Dict[str, Any]], tokenizer=None):
    """從多種格式（messages / prompt+completion / instruction+expected）轉為 Dataset。

    支援三種輸入：
    - {"messages": [{"role":"system"/"user"/"assistant","content":...}, ...]} — HF 標準
    - {"prompt": ..., "completion": ...} — 原樣
    - {"instruction": ..., "expected": ...} — Phase I 既有格式
    """
    from datasets import Dataset

    def _fmt(s):
        if "messages" in s:
            return _messages_to_prompt_completion(s["messages"], tokenizer=tokenizer)
        if "prompt" in s and "completion" in s:
            return {"prompt": s["prompt"], "completion": s["completion"]}
        if "instruction" in s and "expected" in s:
            system_msg = (
                "你是 Phase I STEAM 專案規劃師。將使用者的自然語言需求轉換為嚴格的 JSON。\n"
                "規則：只輸出 JSON 物件，不要 Markdown。components 必須包含 Brain/Power/Control。\n"
            )
            return {
                "prompt": (
                    "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
                    f"{system_msg}<|eot_id|>"
                    "<|start_header_id|>user<|end_header_id|>\n\n"
                    f"{s['instruction']}<|eot_id|>"
                    "<|start_header_id|>assistant<|end_header_id|>\n\n"
                ),
                "completion": json.dumps(s["expected"], ensure_ascii=False, indent=2) + "<|eot_id|>",
            }
        raise ValueError(f"Unknown jsonl format: keys={list(s.keys())}")

    return Dataset.from_list([_fmt(s) for s in samples])


def train(data, *, output_dir: str, max_steps: int = 400,
          lora_r: int = 16, lora_alpha: int = 32, lora_dropout: float = 0.05,
          learning_rate: float = 1.5e-4, eval_ratio: float = 0.08,
          warmup_steps: int = 20, lr_scheduler_type: str = "cosine",
          num_train_epochs: float = 0.0,
          **_kw) -> Dict[str, Any]:
    from unsloth import FastLanguageModel
    from trl import SFTTrainer, SFTConfig
    from transformers import EarlyStoppingCallback
    from datasets import Dataset
    import torch

    # 先載 tokenizer（messages 格式需要 apply_chat_template）
    base = MODEL_CONFIG["base_model_4bit"]
    print(f"[4bit] 載入 {base}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base, max_seq_length=2048, dtype=None, load_in_4bit=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if isinstance(data, list) and data:
        sample = data[0]
        if "prompt" in sample and "completion" in sample and "messages" not in sample:
            dataset = Dataset.from_list(data)
        elif "messages" in sample or "instruction" in sample:
            dataset = build_dataset(data, tokenizer=tokenizer)
        else:
            raise ValueError(f"資料格式無法識別：keys = {list(sample.keys())}")
    elif isinstance(data, Dataset):
        dataset = data
    else:
        raise ValueError("data 必須是 Dataset 或非空 list")

    split = dataset.train_test_split(test_size=eval_ratio, seed=3407)
    train_ds, eval_ds = split["train"], split["test"]

    model = FastLanguageModel.get_peft_model(
        model, r=lora_r, lora_alpha=lora_alpha, lora_dropout=lora_dropout,
        target_modules=MODEL_CONFIG["target_modules"],
        bias="none", use_gradient_checkpointing="unsloth", random_state=3407,
    )

    eff_batch = 2 * 4  # per_device_batch * grad_accum
    steps_per_epoch = len(train_ds) // eff_batch
    eval_save_steps = max(steps_per_epoch // 4, 20)

    use_epochs = num_train_epochs > 0
    sft_kwargs: Dict[str, Any] = dict(
        output_dir=output_dir,
        per_device_train_batch_size=2, gradient_accumulation_steps=4,
        learning_rate=learning_rate, max_length=2048,
        logging_steps=10,
        save_strategy="steps", save_steps=eval_save_steps, save_total_limit=3,
        eval_strategy="steps", eval_steps=eval_save_steps,
        load_best_model_at_end=True, metric_for_best_model="eval_loss",
        warmup_steps=warmup_steps, optim="adamw_8bit", weight_decay=0.01,
        lr_scheduler_type=lr_scheduler_type, seed=3407, report_to="none",
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        packing=False, completion_only_loss=True,
    )
    if use_epochs:
        sft_kwargs["num_train_epochs"] = num_train_epochs
    else:
        sft_kwargs["max_steps"] = max_steps
    args = SFTConfig(**sft_kwargs)

    stop_disp = (f"epochs={num_train_epochs}" if use_epochs
                 else f"max_steps={max_steps}")
    print(f"[4bit] train={len(train_ds)} eval={len(eval_ds)} | "
          f"{stop_disp} eval_every={eval_save_steps} "
          f"lr={learning_rate} warmup={warmup_steps} sched={lr_scheduler_type}")
    trainer = SFTTrainer(
        model=model, train_dataset=train_ds, eval_dataset=eval_ds,
        processing_class=tokenizer, args=args,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=5)],
    )
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0

    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    best_step = trainer.state.best_global_step
    best_loss = trainer.state.best_metric
    print(f"[4bit] [OK] done {elapsed/60:.1f} min -> {output_dir}")
    print(f"[4bit] best_step={best_step}  best_eval_loss={best_loss:.6f}")

    return {
        "mode": "unsloth-4bit", "elapsed_s": elapsed,
        "output_dir": output_dir,
        "best_step": best_step, "best_eval_loss": best_loss,
        "train_size": len(train_ds), "eval_size": len(eval_ds),
    }
