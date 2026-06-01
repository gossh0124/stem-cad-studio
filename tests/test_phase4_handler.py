"""tests/test_phase4_handler.py — Phase 4 Handler 單元測試（INF2）。

涵蓋：
  1. bridge JSON 解析（_resolve_brain_class）
  2. prompt SSOT import chain（training.prompts 常數 + builder）
  3. LoRA-B merge 邏輯（_merge_lora_b_into_solver）
  4. 檔名安全處理（_safe_project_name）
  5. 多元件佈局判定（_has_multi_component_layout）
  6. 錯誤處理 & 邊界條件
"""
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock

from services.phase_handlers.phase4_handler import (
    _resolve_brain_class,
    _merge_lora_b_into_solver,
    _safe_project_name,
    _has_multi_component_layout,
    _SAFE_PROJECT_NAME_FALLBACK,
    Phase4Handler,
)


# ═══════════════════════════════════════════════════════════════
# 1. _resolve_brain_class — bridge 元件解析
# ═══════════════════════════════════════════════════════════════

class TestResolveBrainClass:
    """從 components list 找出 role='Brain' 的 class_name。"""

    def test_find_brain_by_type(self):
        comps = [
            {"role": "Sensor", "type": "DHT22"},
            {"role": "Brain", "type": "Arduino-Uno"},
        ]
        assert _resolve_brain_class(comps) == "Arduino-Uno"

    def test_find_brain_by_class_name_fallback(self):
        comps = [{"role": "Brain", "class_name": "ESP32-DevKit"}]
        assert _resolve_brain_class(comps) == "ESP32-DevKit"

    def test_type_takes_precedence_over_class_name(self):
        comps = [{"role": "Brain", "type": "Uno", "class_name": "Arduino-Uno"}]
        assert _resolve_brain_class(comps) == "Uno"

    def test_no_brain_returns_none(self):
        comps = [
            {"role": "Sensor", "type": "DHT22"},
            {"role": "Actuator", "type": "SG90"},
        ]
        assert _resolve_brain_class(comps) is None

    def test_empty_list_returns_none(self):
        assert _resolve_brain_class([]) is None

    def test_case_insensitive_role(self):
        comps = [{"role": "brain", "type": "Nano"}]
        assert _resolve_brain_class(comps) == "Nano"

    def test_brain_with_no_type_or_class_name(self):
        comps = [{"role": "Brain"}]
        assert _resolve_brain_class(comps) is None

    def test_multiple_brains_returns_first(self):
        comps = [
            {"role": "Brain", "type": "Arduino-Uno"},
            {"role": "Brain", "type": "ESP32"},
        ]
        assert _resolve_brain_class(comps) == "Arduino-Uno"


# ═══════════════════════════════════════════════════════════════
# 2. training.prompts — import chain 防護（INF12）
# ═══════════════════════════════════════════════════════════════

class TestPromptsImportChain:
    """確認 training.prompts 的常數與 builder 可正常 import。"""

    def test_sys_plan_is_nonempty_string(self):
        from training.prompts import SYS_PLAN
        assert isinstance(SYS_PLAN, str)
        assert len(SYS_PLAN) > 20

    def test_sys_params_is_nonempty_string(self):
        from training.prompts import SYS_PARAMS
        assert isinstance(SYS_PARAMS, str)
        assert len(SYS_PARAMS) > 20

    def test_sys_plan_contains_plan_keywords(self):
        from training.prompts import SYS_PLAN
        assert "Plan" in SYS_PLAN or "plan" in SYS_PLAN or "PlanJSON" in SYS_PLAN

    def test_sys_params_contains_params_keywords(self):
        from training.prompts import SYS_PARAMS
        assert "Params" in SYS_PARAMS or "ParamsJSON" in SYS_PARAMS

    def test_build_plan_user_prompt_returns_string(self):
        from training.prompts import build_plan_user_prompt
        result = build_plan_user_prompt(
            project_name="TestBot",
            category="robotics",
            subsystems=["Arduino-Uno-class(weight=25.0g, thermal=250.0mW)"],
            total_weight=25.0,
            total_thermal=250.0,
        )
        assert isinstance(result, str)
        assert "TestBot" in result
        assert "<|im_start|>plan" in result

    def test_build_params_user_prompt_returns_string(self):
        from training.prompts import build_params_user_prompt
        result = build_params_user_prompt(
            project_name="TestBot",
            category="robotics",
            plan={"layout": [{"component": "Arduino-Uno", "zone": "center"}]},
        )
        assert isinstance(result, str)
        assert "TestBot" in result
        assert "<|im_start|>params" in result
        assert "PlanJSON" in result

    def test_all_exports_match(self):
        from training.prompts import __all__
        expected = {"SYS_PLAN", "SYS_PARAMS", "SYS_PHASE1",
                    "build_plan_user_prompt", "build_params_user_prompt"}
        assert set(__all__) == expected


# ═══════════════════════════════════════════════════════════════
# 3. _merge_lora_b_into_solver — LoRA-B 合併邏輯
# ═══════════════════════════════════════════════════════════════

class TestMergeLorabIntoSolver:
    """LoRA-B Assembly Plan 合併進 solver 結果。"""

    @staticmethod
    def _make_cb():
        return MagicMock()

    @staticmethod
    def _log(cb, msg):
        if cb:
            cb(msg)

    def test_zone_and_face_out_merged(self):
        solver = {
            "placements": [
                {"type": "Arduino-Uno", "x": 10, "y": 20},
                {"type": "DHT22", "x": 30, "y": 40},
            ]
        }
        plan = {
            "layout": [
                {"component": "Arduino-Uno", "zone": "center", "face_out": "top"},
            ]
        }
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        uno = result["placements"][0]
        assert uno["zone"] == "center"
        assert uno["face_out"] == "top"
        assert uno["_lora_b_reason"] == ""
        # DHT22 should remain untouched
        dht = result["placements"][1]
        assert "zone" not in dht

    def test_joints_merged(self):
        solver = {"placements": []}
        plan = {"layout": [], "joints": {"lid_method": "snap_fit", "reason": "easy"}}
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        assert result["joints"]["lid_method"] == "snap_fit"

    def test_thermal_strategy_merged(self):
        solver = {"placements": []}
        plan = {
            "layout": [],
            "thermal": {"strategy": "passive_vent", "vent_placement": "side"},
        }
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        tf = result["thermal_field"]
        assert tf["lora_b_strategy"] == "passive_vent"
        assert tf["lora_b_vent_placement"] == "side"

    def test_cable_routing_merged(self):
        solver = {"placements": []}
        plan = {"layout": [], "cable_routing": [{"from": "A", "to": "B"}]}
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        assert result["lora_b_cable_routing"] == [{"from": "A", "to": "B"}]

    def test_empty_plan_no_crash(self):
        solver = {"placements": [{"type": "X", "x": 0, "y": 0}]}
        plan = {"layout": []}
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        assert result["placements"][0]["type"] == "X"
        assert "zone" not in result["placements"][0]

    def test_rationale_stored(self):
        solver = {"placements": []}
        plan = {"layout": [], "placement_rationale": "balanced layout"}
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        assert result["_lora_b_rationale"] == "balanced layout"

    def test_reason_propagated_to_placement(self):
        solver = {"placements": [{"type": "SG90", "x": 0, "y": 0}]}
        plan = {
            "layout": [
                {"component": "SG90", "zone": "edge", "reason": "arm reach"},
            ],
        }
        result = _merge_lora_b_into_solver(solver, plan, self._make_cb(), self._log)
        assert result["placements"][0]["_lora_b_reason"] == "arm reach"


# ═══════════════════════════════════════════════════════════════
# 4. _safe_project_name — 檔名安全處理（J1 故事化命名）
# ═══════════════════════════════════════════════════════════════

class TestSafeProjectName:
    """bridge.project_name → ASCII-safe 檔名。"""

    def test_ascii_passthrough(self):
        assert _safe_project_name({"project_name": "my_robot"}) == "my_robot"

    def test_cjk_replaced_with_underscore(self):
        result = _safe_project_name({"project_name": "智慧小車"})
        assert result.isascii()
        # CJK characters should be replaced, not kept
        assert "智" not in result

    def test_hyphen_allowed(self):
        assert _safe_project_name({"project_name": "robo-arm"}) == "robo-arm"

    def test_spaces_replaced(self):
        result = _safe_project_name({"project_name": "my robot"})
        assert " " not in result

    def test_empty_project_name_fallback(self):
        assert _safe_project_name({"project_name": ""}) == _SAFE_PROJECT_NAME_FALLBACK

    def test_missing_project_name_fallback(self):
        assert _safe_project_name({}) == _SAFE_PROJECT_NAME_FALLBACK

    def test_none_project_name_fallback(self):
        assert _safe_project_name({"project_name": None}) == _SAFE_PROJECT_NAME_FALLBACK

    def test_special_chars_stripped(self):
        result = _safe_project_name({"project_name": "a@b#c$d"})
        assert result == "a_b_c_d"

    def test_all_underscores_fallback(self):
        """純特殊字元 → strip('_') 後為空 → fallback。"""
        result = _safe_project_name({"project_name": "!!!"})
        assert result == _SAFE_PROJECT_NAME_FALLBACK

    def test_emoji_stripped(self):
        result = _safe_project_name({"project_name": "robot🤖arm"})
        assert result.isascii()
        assert "robot" in result
        assert "arm" in result


# ═══════════════════════════════════════════════════════════════
# 5. _has_multi_component_layout — 多元件佈局判定
# ═══════════════════════════════════════════════════════════════

class TestHasMultiComponentLayout:
    """判定走 build_assembly_two_piece 路徑的條件。"""

    def test_empty_placements(self):
        assert _has_multi_component_layout([]) is False

    def test_single_placement(self):
        assert _has_multi_component_layout([{"type": "A"}]) is False

    def test_two_placements(self):
        assert _has_multi_component_layout([{"type": "A"}, {"type": "B"}]) is True

    def test_many_placements(self):
        placements = [{"type": f"comp_{i}"} for i in range(10)]
        assert _has_multi_component_layout(placements) is True

    def test_none_input(self):
        """None → bool(None) is False → 回傳 False。"""
        assert _has_multi_component_layout(None) is False


# ═══════════════════════════════════════════════════════════════
# 6. Phase4Handler 類別屬性 & _log
# ═══════════════════════════════════════════════════════════════

class TestPhase4HandlerMeta:
    """Handler 類別層級屬性與靜態方法。"""

    def test_phase_id_is_p4(self):
        from services.shared.models import PhaseID
        assert Phase4Handler.phase_id == PhaseID.P4

    def test_log_with_callback(self):
        cb = MagicMock()
        Phase4Handler._log(cb, "test message")
        cb.assert_called_once_with("[Phase IV] test message")

    def test_log_without_callback(self, capsys):
        Phase4Handler._log(None, "hello")
        captured = capsys.readouterr()
        assert "[Phase IV] hello" in captured.out


# ═══════════════════════════════════════════════════════════════
# 7. 錯誤 & 邊界條件
# ═══════════════════════════════════════════════════════════════

class TestEdgeCases:
    """錯誤處理與邊界情境。"""

    def test_resolve_brain_missing_role_key(self):
        """元件缺少 role key → 不 crash。"""
        comps = [{"type": "Arduino-Uno"}, {"name": "sensor"}]
        assert _resolve_brain_class(comps) is None

    def test_merge_with_no_placements_key(self):
        """solver_result 沒有 placements → 預設空 list。"""
        solver = {}
        plan = {"layout": [{"component": "X", "zone": "top"}]}
        cb = MagicMock()
        result = _merge_lora_b_into_solver(solver, plan, cb, lambda c, m: None)
        assert result.get("placements", []) == []

    def test_merge_with_no_layout_key(self):
        """plan 沒有 layout → 不 crash。"""
        solver = {"placements": [{"type": "A", "x": 0, "y": 0}]}
        plan = {}
        cb = MagicMock()
        result = _merge_lora_b_into_solver(solver, plan, cb, lambda c, m: None)
        assert result["placements"][0]["type"] == "A"

    def test_safe_project_name_numeric(self):
        """純數字 project_name → 應正常回傳。"""
        assert _safe_project_name({"project_name": "12345"}) == "12345"

    def test_merge_duplicate_component_in_layout(self):
        """layout 有重複 component → 後者覆寫（dict 語意）。"""
        solver = {"placements": [{"type": "A", "x": 0, "y": 0}]}
        plan = {
            "layout": [
                {"component": "A", "zone": "top"},
                {"component": "A", "zone": "bottom"},
            ]
        }
        cb = MagicMock()
        result = _merge_lora_b_into_solver(solver, plan, cb, lambda c, m: None)
        assert result["placements"][0]["zone"] == "bottom"

    def test_merge_preserves_solver_coordinates(self):
        """LoRA-B 覆寫 zone/face_out 但 x/y 座標不動。"""
        solver = {"placements": [{"type": "M", "x": 55, "y": 77}]}
        plan = {"layout": [{"component": "M", "zone": "left", "face_out": "front"}]}
        cb = MagicMock()
        result = _merge_lora_b_into_solver(solver, plan, cb, lambda c, m: None)
        p = result["placements"][0]
        assert p["x"] == 55
        assert p["y"] == 77
        assert p["zone"] == "left"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
