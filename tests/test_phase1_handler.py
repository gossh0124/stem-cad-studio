"""tests/test_phase1_handler.py — PR3: Phase I 抽象輸入 graceful 處理。

驗證模型輸出無法解析 / 無元件時，execute() 拋 Phase1InputError（友善引導），
而非生硬 ValueError + traceback；pipeline 端可特判只回引導訊息。
"""
from __future__ import annotations
import pytest
from unittest.mock import patch

from services.phase_handlers.phase1_handler import (
    Phase1Handler, Phase1InputError, _INPUT_TOO_ABSTRACT_MSG,
)
from services.shared.models import Job


def _job():
    return Job(job_id="pr3-test", project_name="Test",
               instruction="保護房間不被弟弟亂進來")


class TestPhase1GracefulInput:
    def test_unparseable_output_raises_input_error(self):
        """模型輸出無法解析為 JSON → Phase1InputError（非裸 ValueError 訊息）。"""
        h = Phase1Handler()
        bridge: dict = {}
        with patch.object(h, "_build_prompt_with_rag", return_value="PROMPT"), \
             patch.object(h, "_infer", return_value=("這不是 JSON 隨便講講", 1, "test")):
            with pytest.raises(Phase1InputError):
                h.execute(_job(), bridge)
        # 失敗時仍保留原始輸出供除錯
        assert bridge.get("_p1_raw")

    def test_empty_components_raises_input_error(self):
        """可解析但無 components → Phase1InputError。"""
        h = Phase1Handler()
        empty_json = '{"project_name": "x", "components": []}'
        with patch.object(h, "_build_prompt_with_rag", return_value="PROMPT"), \
             patch.object(h, "_infer", return_value=(empty_json, 1, "test")):
            with pytest.raises(Phase1InputError):
                h.execute(_job(), {})

    def test_input_error_is_valueerror_subclass(self):
        """向後相容：pipeline 既有 except Exception/ValueError 仍接得住。"""
        assert issubclass(Phase1InputError, ValueError)

    def test_friendly_message_actionable(self):
        """引導訊息可行動（要求具體說明物理現象），非 raw traceback。"""
        assert "具體" in _INPUT_TOO_ABSTRACT_MSG
        assert "偵測" in _INPUT_TOO_ABSTRACT_MSG
        assert "traceback" not in _INPUT_TOO_ABSTRACT_MSG.lower()
