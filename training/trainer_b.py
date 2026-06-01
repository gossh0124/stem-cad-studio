"""trainer_b.py — Phase IV Layer 2 LoRA-B 訓練器。

與 LoRA-A 共用相同 base model 和訓練流程（unsloth 4bit + SFTTrainer），
差異在 system prompt 和資料內容（已由 data_generator_b.py 處理）。
"""
from __future__ import annotations

from trainer import report_environment, train

__all__ = ["report_environment", "train"]
