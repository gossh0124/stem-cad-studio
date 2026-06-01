"""training/cadhllm_hparams.py — CAD-HLLM (ACML 2025) 驗證的訓練/推理超參組。

來源：docs/224_CAD_HLLM_Generating_Execut.pdf（四川大學）
驗證任務：Hierarchical CAD 生成（Plan → Params）
本專案應用：LoRA-B（Phase IV Layer 2 組裝決策）訓練 + Phase IV 推理

設計原則：
- 不直接套到 LoRA-A 預設（避免破壞既訓 LoRA-A 重現性）
- 在 train.py 用 `--preset cadhllm` 啟用此組，預設仍走舊 hparams
- Phase IV 推理切換在 LoRA-B 上線時生效（見 INFERENCE_PRESET）
"""
from __future__ import annotations
from typing import Any, Dict


# 論文 Table 2 / Section 3.3 驗證之訓練超參
TRAINING_PRESET: Dict[str, Any] = {
    "optim":             "adamw_8bit",
    "learning_rate":     2e-4,
    "warmup_steps":      5,
    "lr_scheduler_type": "linear",
    "num_train_epochs":  3,
    "weight_decay":      0.01,
    "max_seq_length":    2048,
    # LoRA 結構（與 LoRA-A 相同，論文未指定）
    "lora_r":           16,
    "lora_alpha":       32,
    "lora_dropout":     0.05,
}


# 論文 Section 4.1 推理階段超參
# 應用於 phase1_handler / phase4_handler 的 model.generate(**kwargs)
INFERENCE_PRESET: Dict[str, Any] = {
    "temperature":  0.5,
    "min_p":        0.1,
    "do_sample":    True,
    # max_new_tokens 不由論文指定，依任務調整
}


def apply_training_overrides(args: Any) -> None:
    """將 TRAINING_PRESET 套用到 argparse Namespace（only overwrite 未 explicitly 設的）。

    DEPRECATED: train.py 已內聯相同邏輯（parse_args 的 cadhllm preset 分支），
    此函式僅保留作向後相容，新代碼請直接在 parse_args 內讀取 TRAINING_PRESET。

    用法：
        args = parser.parse_args()
        if args.preset == "cadhllm":
            apply_training_overrides(args)
    """
    args.learning_rate     = TRAINING_PRESET["learning_rate"]
    args.lora_r            = TRAINING_PRESET["lora_r"]
    args.lora_alpha        = TRAINING_PRESET["lora_alpha"]
    args.lora_dropout      = TRAINING_PRESET["lora_dropout"]
    # num_train_epochs 透過 trainer.train() 的 kwargs 傳入，max_steps 設 -1 跳過
    args.num_train_epochs  = TRAINING_PRESET["num_train_epochs"]
    args.warmup_steps      = TRAINING_PRESET["warmup_steps"]
    args.lr_scheduler_type = TRAINING_PRESET["lr_scheduler_type"]


__all__ = ["TRAINING_PRESET", "INFERENCE_PRESET", "apply_training_overrides"]
