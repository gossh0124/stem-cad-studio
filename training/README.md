# CADHLLM Phase I — Training Package (Colab)

獨立的 LoRA 訓練包，上傳到 Google Colab 執行。

## 檔案結構

```
training/
├── train.py            ← 入口：一鍵訓練
├── config.py           ← TAXONOMY_CONFIG + MODEL_CONFIG
├── data_generator.py   ← 訓練資料生成器
├── trainer.py          ← LoRA 訓練器（unsloth 4bit）
├── requirements.txt    ← Python 依賴
└── outputs/
    └── cadhllm_lora/   ← 訓練產出（下載回主機）
```

## Colab 使用流程

```python
# 1. 上傳 training/ 資料夾到 Colab

# 2. 安裝依賴
!pip install -r requirements.txt

# 3. 檢查環境（不訓練）
!python train.py --dry-run

# 4. 開始訓練
!python train.py

# 5. 客製化
!python train.py --max-steps 500 --lora-r 32 --data-size 1500
```

## 訓練完成後

將 `outputs/cadhllm_lora/` 下載回主專案：

```bash
cp -r outputs/cadhllm_lora/ /path/to/StemAiAgent/saved_model/cadhllm_lora/
```

## 模型

- Base: `unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit`
- 訓練方式: LoRA r=16, alpha=32, 4bit quantization
- 輸出格式: Llama 3.1 chat template + JSON

## GPU 需求

| 環境 | GPU | VRAM | 預估時間 |
|------|-----|------|---------|
| Colab Free | T4 | 15GB | ~1-2 小時 |
| Colab Pro | A100 | 40GB | ~15-20 分鐘 |
