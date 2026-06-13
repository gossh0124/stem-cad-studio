"""lib/vllm_client.py — vLLM OpenAI-compatible API client。

替換 transformers model.generate()，透過 HTTP 呼叫 WSL2 內的 vLLM server。
支援 LoRA adapter 切換（透過 model 參數指定）。

用法：
    from lib.vllm_client import vllm_generate, is_vllm_available

    if is_vllm_available():
        result = vllm_generate(prompt, max_tokens=1536, temperature=0.1)
    else:
        # fallback to transformers
"""
from __future__ import annotations
import logging
import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional

_log = logging.getLogger(__name__)

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL", "http://localhost:8001")
VLLM_TIMEOUT  = int(os.environ.get("VLLM_TIMEOUT", "120"))  # seconds

# LoRA adapter 名稱對應
ADAPTER_LORA_A = "cadhllm_lora"     # Phase I / VI / VII
ADAPTER_LORA_B = "cadhllm_lora_b"   # Phase IV Layer 2

# VL2: vLLM 0.20.0 溢出行為 = HTTP 400（不截斷），client 端須自保
_MIN_OUTPUT_TOKENS = 128            # 夾取後若輸出空間低於此 → 明確報錯而非硬送 400


def _estimate_tokens(text: str) -> int:
    """粗估 Llama 3.1 token 數（混合 CJK/英文/JSON）。

    CJK/全形 約 1 char≈1.3 token、ASCII 約 3.5 char≈1 token；偏保守（略高）
    以確保不低估而仍溢出。僅供 pre-check 夾取，非精確計數。
    """
    cjk = sum(1 for ch in text
              if '一' <= ch <= '鿿'      # CJK 統一表意
              or '　' <= ch <= 'ヿ'      # CJK 標點 + 假名
              or '＀' <= ch <= '￯')     # 全形
    return int(cjk * 1.3 + (len(text) - cjk) / 3.5) + 1


def _fit_max_tokens(prompt: str, max_tokens: int, max_model_len: int) -> int:
    """VL2: 確保 prompt + max_tokens ≤ max_model_len。

    超出則夾 max_tokens 到可容範圍；連 _MIN_OUTPUT_TOKENS 都放不下 → raise
    （明確錯誤勝過 vLLM 0.20.0 的 HTTP 400 BadRequestError）。
    """
    est = _estimate_tokens(prompt)
    if est + max_tokens <= max_model_len:
        return max_tokens
    safe = max_model_len - est - 8  # 8 token 裕量（特殊 token 等）
    if safe < _MIN_OUTPUT_TOKENS:
        raise RuntimeError(
            f"prompt 估約 {est} tokens 已逼近 max_model_len {max_model_len}，"
            f"輸出空間僅 {safe}（< {_MIN_OUTPUT_TOKENS}）。"
            f"請縮短輸入或提高 VLLM_MAX_MODEL_LEN。"
        )
    _log.warning(
        "[vLLM] prompt~%s + max_tokens %s > max_model_len %s → 夾 max_tokens=%s",
        est, max_tokens, max_model_len, safe,
    )
    return safe


def is_vllm_available() -> bool:
    """檢查 vLLM server 是否可用。"""
    try:
        req = urllib.request.Request(
            f"{VLLM_BASE_URL}/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        # server 有回應但非 2xx（如 503 載入中）→ 視為尚未就緒，但記錄以利診斷
        _log.warning("[vLLM] /health 回傳 HTTP %s（%s）→ 視為未就緒", e.code, VLLM_BASE_URL)
        return False
    except urllib.error.URLError as e:
        # 連線/逾時/DNS 等網路層失敗 → 不可用，但記錄以區分「設定錯誤」與「刻意關閉」
        _log.warning("[vLLM] /health 連線失敗 (%s): %s → 視為不可用", VLLM_BASE_URL, e)
        return False
    # 其餘非預期例外（如 request 建構 bug）不吞，讓設定錯誤浮現


def vllm_generate(
    prompt: str,
    *,
    max_tokens: int = 1536,
    temperature: float = 0.1,
    min_p: float = 0.0,
    lora_adapter: Optional[str] = ADAPTER_LORA_A,
    stop: Optional[list[str]] = None,
    timeout: Optional[int] = None,
) -> str:
    """透過 vLLM OpenAI-compatible API 生成文字。

    Args:
        prompt: 完整的 prompt（含 Llama 3.1 chat template）
        max_tokens: 最大生成 token 數
        temperature: 取樣溫度
        min_p: vLLM min-p sampling 閾值（0.0 = 不啟用；CAD-HLLM INFERENCE_PRESET 用 0.1）
        lora_adapter: LoRA adapter 名稱（None = 使用 base model）
        stop: 停止序列
        timeout: 請求超時秒數（預設 VLLM_TIMEOUT）

    Returns:
        生成的文字（已去除 prompt 和 stop token）

    Raises:
        ConnectionError: vLLM server 不可用
        RuntimeError: vLLM 回傳錯誤
    """
    # 決定 model 名稱（有 LoRA 時用 adapter 名稱）
    model_name = lora_adapter if lora_adapter else "default"
    if model_name == "default":
        _log.debug("no lora_adapter specified, using 'default' model name")

    # VL2: 送出前自保 prompt + max_tokens ≤ max_model_len（vLLM 0.20.0 溢出 = HTTP 400）
    max_tokens = _fit_max_tokens(
        prompt, max_tokens, int(os.environ.get("VLLM_MAX_MODEL_LEN", "4096")))

    payload = {
        "model": model_name,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stop": stop or ["<|eot_id|>"],
    }
    if min_p > 0:
        payload["min_p"] = min_p
    if temperature <= 0:
        payload["temperature"] = 0
        payload.pop("min_p", None)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{VLLM_BASE_URL}/v1/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout or VLLM_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # HTTPError 是 URLError 子類，必須先 catch；否則 4xx/5xx 會被誤判為「server 不可用」
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"vLLM 錯誤 (HTTP {e.code}): {error_body[:500]}"
        ) from e
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"vLLM server 不可用 ({VLLM_BASE_URL}): {e}"
        ) from e

    elapsed = round(time.time() - t0, 1)

    # 解析回應
    choices = result.get("choices", [])
    if not choices:
        raise RuntimeError(f"vLLM 回傳空結果: {json.dumps(result, ensure_ascii=False)[:300]}")

    text = choices[0].get("text", "")
    usage = result.get("usage", {})

    # Log 推論統計
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    tokens_per_sec = completion_tokens / elapsed if elapsed > 0 else 0
    _log.info(
        "[vLLM] %ss | prompt=%s completion=%s | %.1f tok/s | adapter=%s",
        elapsed, prompt_tokens, completion_tokens, tokens_per_sec,
        lora_adapter or 'base'
    )

    return text.strip()
