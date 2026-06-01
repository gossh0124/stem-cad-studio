"""tests/test_vllm_client.py — VL2: client 端 prompt+max_tokens 溢出自保。

vLLM 0.20.0 溢出行為 = HTTP 400（不截斷），故送出前須夾 max_tokens 或明確報錯。
這裡測純函式 _estimate_tokens / _fit_max_tokens（無需 server）。
"""
from __future__ import annotations
import pytest

from lib.vllm_client import _estimate_tokens, _fit_max_tokens


class TestEstimateTokens:
    def test_ascii_roughly_3_5_chars_per_token(self):
        n = _estimate_tokens("a" * 350)
        assert 80 <= n <= 130

    def test_cjk_heavier_than_ascii(self):
        assert _estimate_tokens("中" * 100) > _estimate_tokens("a" * 100)

    def test_empty_nonzero(self):
        assert _estimate_tokens("") == 1


class TestFitMaxTokens:
    def test_fits_unchanged(self):
        assert _fit_max_tokens("short prompt", 1536, 4096) == 1536

    def test_clamps_when_over(self):
        prompt = "中" * 3000  # est ~3901 tokens
        out = _fit_max_tokens(prompt, 1536, 4096)
        assert out < 1536
        assert _estimate_tokens(prompt) + out <= 4096  # 不再溢出

    def test_raises_when_no_room(self):
        prompt = "中" * 3200  # est ~4161 > 4096 → 輸出空間 < 下限
        with pytest.raises(RuntimeError):
            _fit_max_tokens(prompt, 1536, 4096)
