"""train.py — LoRA A/B 訓練入口（Colab 專用，2026-05-08 整合 A/B）。

用法：
    python train.py                           # 預設訓練 A 與 B（both）
    python train.py --target a                # 只訓練 LoRA-A（Phase I 意圖）
    python train.py --target b                # 只訓練 LoRA-B（Phase IV Layer 2 組裝）
    python train.py --target both             # 兩者依序訓練
    python train.py --max-steps 500           # 自訂步數（套用兩者）
    python train.py --dry-run                 # 只印環境與資料樣本，不訓練

LoRA 輸出目錄（對齊 adapter_manager._adapter_path 讀取路徑）：
    LoRA-A → outputs/cadhllm_lora/    → 落地 saved_model/cadhllm_lora/
    LoRA-B → outputs/cadhllm_lora_b/  → 落地 saved_model/cadhllm_lora_b/（CH3 v1.1 雙階段 control token）

兩者皆基於同一 base model（Llama 3.1 8B Instruct 4bit），訓練完成後
透過 adapter hot-swap 在推論階段切換。
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

OUTPUT_DIR_A = str(Path(__file__).parent / "outputs" / "cadhllm_lora")
OUTPUT_DIR_B = str(Path(__file__).parent / "outputs" / "cadhllm_lora_b")


def parse_args():
    p = argparse.ArgumentParser(description="LoRA A/B 訓練（Colab 4bit）")
    p.add_argument("--target",        type=str,   default="both",
                   choices=["a", "b", "both"],
                   help="訓練哪個 adapter：a=Phase I, b=Phase IV Layer 2, both=兩者依序")
    p.add_argument("--preset",        type=str,   default="default",
                   choices=["default", "cadhllm"],
                   help="超參組：default=LoRA-A 既驗超參；cadhllm=論文 ACML 2025 超參 (套用於 b)")
    p.add_argument("--max-steps",     type=int,   default=400)
    p.add_argument("--lora-r",        type=int,   default=16)
    p.add_argument("--lora-alpha",    type=int,   default=32)
    p.add_argument("--lora-dropout",  type=float, default=0.05)
    p.add_argument("--learning-rate", type=float, default=1.5e-4)
    p.add_argument("--warmup-steps",   type=int,   default=20)
    p.add_argument("--lr-scheduler",  type=str,   default="cosine")
    p.add_argument("--num-train-epochs", type=float, default=0.0,
                   help="若 >0 則用 epochs 取代 max_steps")
    p.add_argument("--data-size-a",   type=int,   default=1500,
                   help="LoRA-A 訓練資料筆數（預設 1500）")
    p.add_argument("--data-size-b",   type=int,   default=200,
                   help="LoRA-B 訓練資料筆數（預設 200）")
    p.add_argument("--eval-ratio",    type=float, default=0.08)
    p.add_argument("--output-dir-a",  type=str,   default=OUTPUT_DIR_A)
    p.add_argument("--output-dir-b",  type=str,   default=OUTPUT_DIR_B)
    p.add_argument("--dry-run",       action="store_true")
    args = p.parse_args()

    if args.preset == "cadhllm":
        from cadhllm_hparams import TRAINING_PRESET
        args.learning_rate     = TRAINING_PRESET["learning_rate"]
        args.warmup_steps      = TRAINING_PRESET["warmup_steps"]
        args.lr_scheduler      = TRAINING_PRESET["lr_scheduler_type"]
        args.num_train_epochs  = TRAINING_PRESET["num_train_epochs"]
        args.lora_r            = TRAINING_PRESET["lora_r"]
        args.lora_alpha        = TRAINING_PRESET["lora_alpha"]
        args.lora_dropout      = TRAINING_PRESET["lora_dropout"]
        print(f"[preset=cadhllm] 套用論文超參：lr={args.learning_rate} "
              f"warmup={args.warmup_steps} sched={args.lr_scheduler} "
              f"epochs={args.num_train_epochs}")

    return args


def _build_dataset_a(n: int):
    """LoRA-A：Phase I 意圖理解資料。"""
    from data_generator import DataGenerator
    print(f"\n[A] 生成 LoRA-A 訓練資料（{n} 筆，scope filter 已啟用）...")
    return DataGenerator().generate_synthetic_data(n=n)


def _build_dataset_b(n: int):
    """LoRA-B：Phase IV Layer 2 組裝決策資料。"""
    from data_generator_b import DataGeneratorB
    from datasets import Dataset
    print(f"\n[B] 生成 LoRA-B 訓練資料（{n} 筆，scope filter 已啟用）...")
    raw = DataGeneratorB().generate_synthetic_data(n=n)
    return Dataset.from_list(raw)


def _train_one(*, label: str, dataset, output_dir: str, args):
    """訓練單一 adapter，回傳結果 dict。"""
    from trainer import train
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print(f"\n[{label}] 開始訓練 → {output_dir}")
    return train(
        data=dataset, output_dir=output_dir,
        max_steps=args.max_steps, lora_r=args.lora_r,
        lora_alpha=args.lora_alpha, lora_dropout=args.lora_dropout,
        learning_rate=args.learning_rate, eval_ratio=args.eval_ratio,
        warmup_steps=args.warmup_steps,
        lr_scheduler_type=args.lr_scheduler,
        num_train_epochs=args.num_train_epochs,
    )


def main():
    args = parse_args()

    from trainer import report_environment

    info = report_environment()
    print("=" * 64)
    print(f" LoRA 訓練 — 環境摘要（target={args.target}）")
    print("=" * 64)
    for k, v in info.items():
        print(f"  {k:22s}: {v}")
    print("=" * 64)

    do_a = args.target in ("a", "both")
    do_b = args.target in ("b", "both")

    # ── 生成資料（dry-run 與實際訓練都需要）─────────────────
    dataset_a = _build_dataset_a(args.data_size_a) if do_a else None
    dataset_b = _build_dataset_b(args.data_size_b) if do_b else None

    if args.dry_run:
        eff_batch = 2 * 4
        for label, dataset, output_dir in (
            ("A", dataset_a, args.output_dir_a) if do_a else (),
            ("B", dataset_b, args.output_dir_b) if do_b else (),
        ):
            if dataset is None:
                continue
            n = len(dataset)
            train_n = int(n * (1 - args.eval_ratio))
            steps_per_epoch = max(1, train_n // eff_batch)
            print(f"\n[Dry-run {label}] 設定：")
            print(f"  output_dir       : {output_dir}")
            print(f"  資料筆數         : {n} (train {train_n} / eval {n - train_n})")
            print(f"  effective batch  : {eff_batch}")
            print(f"  steps/epoch      : {steps_per_epoch}")
            print(f"  total epochs     : {args.max_steps / steps_per_epoch:.2f}")
            first = dataset[0]
            print(f"\n[Dry-run {label}] 第一筆 prompt（前 200 字）：")
            print(f"  {first['prompt'][:200]}...")
            print(f"\n[Dry-run {label}] 第一筆 completion（前 200 字）：")
            print(f"  {first['completion'][:200]}...")
        print("\n移除 --dry-run 開始訓練")
        return 0

    # ── 訓練（依序執行 A → B；adapter hot-swap 在推論時做）──
    results = {}
    if do_a:
        results["A"] = _train_one(
            label="A", dataset=dataset_a,
            output_dir=args.output_dir_a, args=args,
        )
        r = results["A"]
        print("=" * 64)
        print(f"  [A] 模式       : {r['mode']}")
        print(f"  [A] 耗時       : {r['elapsed_s']/60:.1f} 分鐘")
        print(f"  [A] 輸出       : {r['output_dir']}")
        print(f"  [A] train/eval : {r['train_size']} / {r['eval_size']}")
        print(f"  [A] best_step  : {r['best_step']}")
        print(f"  [A] best_loss  : {r['best_eval_loss']:.6f}")
        print("=" * 64)

    if do_b:
        results["B"] = _train_one(
            label="B", dataset=dataset_b,
            output_dir=args.output_dir_b, args=args,
        )
        r = results["B"]
        print("=" * 64)
        print(f"  [B] 模式       : {r['mode']}")
        print(f"  [B] 耗時       : {r['elapsed_s']/60:.1f} 分鐘")
        print(f"  [B] 輸出       : {r['output_dir']}")
        print(f"  [B] train/eval : {r['train_size']} / {r['eval_size']}")
        print(f"  [B] best_step  : {r['best_step']}")
        print(f"  [B] best_loss  : {r['best_eval_loss']:.6f}")
        print("=" * 64)

    print("\n下一步：")
    if do_a:
        print(f"  [A] 將 {args.output_dir_a} 複製回主專案 saved_model/cadhllm_lora/")
    if do_b:
        print(f"  [B] 將 {args.output_dir_b} 複製回主專案 saved_model/cadhllm_lora_b/（CH3 v1.1 雙階段，會覆蓋既有 B 案版本）")
    print(f"  啟動 gateway：python run_server.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
