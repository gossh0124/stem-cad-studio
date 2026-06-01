#!/bin/bash
# vllm_serve.sh — 在 WSL2 中啟動 vLLM OpenAI-compatible server
#
# 用法：
#   wsl -d Ubuntu-24.04 -u root -- bash <repo>/scripts/vllm_serve.sh
#
# 環境變數：
#   VLLM_PORT          — 監聽 port（預設 8001）
#   VLLM_MODEL         — 模型 ID（預設 meta-llama/Meta-Llama-3.1-8B-Instruct）
#   VLLM_LORA_PATH     — LoRA adapter 路徑（預設自動偵測）
#   VLLM_MAX_MODEL_LEN — 最大序列長度（預設 4096）
#   VLLM_GPU_MEM_UTIL  — GPU 顯存占用比（預設 0.48；啟 APC 時自動 0.68）
#   VLLM_ENABLE_APC    — 1=啟動 prefix caching（CAG/長 prefix 加速）；預設關
#   HF_TOKEN           — HuggingFace token（若需要 gated model）
#
# ── VL3 實測（2026-05-22）─────────────────────────────────────
# 環境：Ubuntu-24.04 · vLLM 0.20.0 · torch 2.11.0 · bnb 0.49.2 · RTX 5070 Ti 16GB
# APC + multi-LoRA(2 adapter rank32) + bitsandbytes 在 0.20.0 三者相容。
# 0.48 + APC → KV cache OOM 起不來（No available memory for the cache blocks）
# 0.68 + APC → KV 3.18GiB / 26,016 tokens / 2048ctx 併發 12.7x（可跑）
# 注意：新版 CUDA graph profiling 讓 0.68 實效 ≈ 0.61
# ──────────────────────────────────────────────────────────────

set -euo pipefail

PORT="${VLLM_PORT:-8001}"
MODEL="${VLLM_MODEL:-unsloth/Meta-Llama-3.1-8B-Instruct}"
MAX_LEN="${VLLM_MAX_MODEL_LEN:-4096}"
QUANTIZATION="${VLLM_QUANTIZATION:-bitsandbytes}"  # 預設 bitsandbytes 4bit
ENABLE_APC="${VLLM_ENABLE_APC:-0}"                  # 預設關（與其他 GPU 任務共存優先）

# APC 啟動時 GPU 預設 0.68（VL3 實測下限）；user 顯式設值優先
if [ "${ENABLE_APC}" = "1" ]; then
    GPU_MEM_UTIL="${VLLM_GPU_MEM_UTIL:-0.68}"
else
    GPU_MEM_UTIL="${VLLM_GPU_MEM_UTIL:-0.48}"
fi

# 自動偵測 LoRA adapter（Windows 路徑 → WSL 路徑）
# 支援 LoRA-A（Phase 1/6/7）+ LoRA-B（Phase 4 Layer 2，CH3 雙階段）同時 mount
LORA_A_PATH="${VLLM_LORA_PATH:-${REPO_ROOT:-.}/saved_model/cadhllm_lora}"
LORA_B_PATH="${VLLM_LORA_B_PATH:-${REPO_ROOT:-.}/saved_model/cadhllm_lora_b}"

LORA_MODULES=()
# vLLM 要 adapter_config.json 才能載入；缺檔的目錄直接跳過避免 startup 失敗
if [ -f "${LORA_A_PATH}/adapter_config.json" ]; then
    LORA_MODULES+=("cadhllm_lora=${LORA_A_PATH}"); echo "[vLLM] LoRA-A: ${LORA_A_PATH}"
elif [ -d "${LORA_A_PATH}" ]; then
    echo "[vLLM] LoRA-A SKIP: ${LORA_A_PATH} 存在但缺 adapter_config.json"
fi
if [ -f "${LORA_B_PATH}/adapter_config.json" ]; then
    LORA_MODULES+=("cadhllm_lora_b=${LORA_B_PATH}"); echo "[vLLM] LoRA-B: ${LORA_B_PATH}"
elif [ -d "${LORA_B_PATH}" ]; then
    echo "[vLLM] LoRA-B SKIP: ${LORA_B_PATH} 存在但缺 adapter_config.json"
fi

LORA_ARGS=""
if [ "${#LORA_MODULES[@]}" -gt 0 ]; then
    LORA_ARGS="--enable-lora --lora-modules ${LORA_MODULES[*]} --max-lora-rank 32 --max-loras ${#LORA_MODULES[@]}"
else
    echo "[vLLM] WARNING: No LoRA adapter found, running base model only"
fi

QUANT_ARGS=""
if [ -n "${QUANTIZATION}" ]; then
    QUANT_ARGS="--quantization ${QUANTIZATION}"
fi

APC_ARGS=""
if [ "${ENABLE_APC}" = "1" ]; then
    APC_ARGS="--enable-prefix-caching"
    # 預警：APC + low GPU mem 會觸發 "No available memory for the cache blocks"
    if awk "BEGIN{exit !(${GPU_MEM_UTIL} < 0.65)}"; then
        echo "[vLLM] WARNING: APC enabled but GPU_MEM_UTIL=${GPU_MEM_UTIL} < 0.65 — KV cache 可能 OOM"
        echo "[vLLM]          VL3 實測下限 0.68（KV 3.18GiB / 26k tokens / 2048ctx 12.7x）"
    fi
fi

echo "========================================"
echo "[vLLM] Starting server"
echo "  Model:    ${MODEL}"
echo "  Port:     ${PORT}"
echo "  Max Len:  ${MAX_LEN}"
echo "  GPU Mem:  ${GPU_MEM_UTIL}"
echo "  APC:      ${ENABLE_APC} (prefix-caching)"
echo "  LoRA:     ${LORA_A_PATH} + ${LORA_B_PATH:-none}"
echo "========================================"

exec /opt/vllm-env/bin/python3 -m vllm.entrypoints.openai.api_server \
    --model "${MODEL}" \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --max-model-len "${MAX_LEN}" \
    --dtype auto \
    --gpu-memory-utilization "${GPU_MEM_UTIL}" \
    ${QUANT_ARGS} \
    ${APC_ARGS} \
    ${LORA_ARGS} \
    --no-enable-log-requests \
    2>&1
