"""training/prompts.py — LoRA prompt SSOT（單一定義來源）。

Phase I (LoRA-A) 與 Phase IV (LoRA-B) 的 system prompt 皆定義於此。

**規則**：訓練端 (data_generator.py / data_generator_b.py) 與 inference 端
(lib/tools.py / lib/adapter_manager.py / phase1_handler.py)
都必須 import 此模組，禁止 hardcode system_msg / user_msg 字串。

訓練資料 jsonl 的 system_msg + user_msg 由此模組產出 → LoRA 學到這些 prompt
對應的 schema → inference 端必須用相同 prompt 才能取得對應 schema 的輸出。

任何修改：
  - SYS_PHASE1 / SYS_PLAN / SYS_PARAMS 常數
  - build_plan_user_prompt / build_params_user_prompt 簽名與輸出格式
必須**同時**：
  1. 重新跑 data_generator / data_generator_b 產生新 jsonl
  2. 用新 jsonl 重訓 LoRA-A / LoRA-B
  3. 跑 scripts/_lora_b_inference_smoke.py 驗 schema
  4. 跑 tools/prompt_alignment_check.py --strict 確認 byte-level alignment

**所有標點全形（：，。（））必須與訓練 jsonl byte-level 一致**。
"""
from __future__ import annotations
import json
from typing import Any, Dict, List


__all__ = [
    "SYS_PHASE1",
    "SYS_PLAN", "SYS_PARAMS",
    "build_plan_user_prompt", "build_params_user_prompt",
]


# ── Phase I system message (固定字串，變動須同步重訓 LoRA-A) ──
# 注意：標點全形（：，。）— 跟訓練 jsonl byte-level 一致。
SYS_PHASE1 = (
    "你是 STEM 教育 IoT 專案設計助手。根據學生的專案構想與類似案例的參考設計，"
    "你的任務是：\n"
    "1. 分析意圖：辨識學生想做什麼，核心功能為何，需要哪些感測、致動、顯示、電源能力。\n"
    "2. 選擇元件：從可用元件庫中為每個辨識出的需求選擇適當元件。\n"
    "3. 補全缺漏：若學生的描述暗示某個能力但未明確提及元件，"
    "主動加入必要元件並在 cot_plan.subsystems 的 reason 中標注"
    "「inferred：<推理原因>」。\n"
    "4. 驗證可行：確認所有元件與所選 MCU 及電源預算相容。\n"
    "5. 輸出 JSON：完整、可行的元件規格，格式嚴格遵守以下規則。\n\n"
    "規則：\n"
    "1. 只輸出 JSON 物件，不要 Markdown、不要前言。\n"
    "2. components 必須包含 Brain、Power、Control 角色。inventory_mentions 必須是 []。\n"
    "3. 依需求加入 Sensor/Actuator/Sound/Display/Lighting 角色。\n"
    "4. 所有 type 必須使用 canonical name（-class 後綴）。\n"
    "5. cot_plan.subsystems 必須包含中文角色名與推理。\n\n"
    "關鍵原則：\n"
    "- 專案描述暗示的每個感測/致動能力都必須有對應元件。\n"
    "- 參考案例僅供設計啟發，不可盲目複製。\n"
    "- 不確定時優先選擇較簡單/常見的元件。\n"
    "- 補全的元件必須在 cot_plan.subsystems 的 reason 中標注"
    "「inferred：<原因>」。\n"
)


# ── Phase IV system messages (固定字串，變動須同步重訓 LoRA-B) ─
# 注意：標點全形（：，。）— 跟訓練 jsonl byte-level 一致。
SYS_PLAN = (
    "你是 Phase IV Layer 2 階層式組裝決策師（Plan 階段）。"
    "根據子系統列表、環境條件與物理約束，輸出 PlanJSON（高層決策）。"
    "決策因子：物理平衡、熱源管理、光照方向、結構強度、線路最短、維護性。"
    "每個元件需標註 enclosure_relation：internal=殼內 / breadboard=焊主板 / "
    "panel=穿殼開窗 / external=殼外 / embedded=結構體內。"
    "只輸出 JSON 物件，不要 Markdown。"
)
SYS_PARAMS = (
    "你是 Phase IV Layer 2 階層式組裝決策師（Params 階段）。"
    "已知 PlanJSON，請輸出 ParamsJSON（低層幾何參數）：enclosure_spec / placements / "
    "wire_routes / vent_placements。座標單位 mm，wall 在 1.5 到 4.0，tol 在 0.1 到 0.5。"
    "只輸出 JSON 物件，不要 Markdown。"
)


# ── User prompt builders ────────────────────────────────────
def build_plan_user_prompt(
    *,
    project_name: str,
    category: str,
    subsystems: List[str],
    total_weight: float,
    total_thermal: float,
    env_name: str = "indoor",
    env_waterproof: bool = False,
    env_ip: str = "IP20",
    enclosure_constraint: str = "compact（≤150mm）",
) -> str:
    """Plan 階段 user prompt（control token <|im_start|>plan）。

    Parameters
    ----------
    subsystems
        預格式化好的字串列表，如：
        ["Arduino-Uno-class(weight=25.0g, thermal=250.0mW)", ...]
    enclosure_constraint
        外殼尺寸描述字串（訓練資料慣用 "compact（≤150mm）"）。
    """
    return (
        f"<|im_start|>plan\n"
        f"專案：{project_name}（{category}）\n"
        f"子系統：{', '.join(subsystems)}\n"
        f"總重量：{total_weight:.0f}g，總發熱：{total_thermal:.0f}mW\n"
        f"環境：{env_name}，防水：{env_waterproof}，IP：{env_ip}\n"
        f"外殼尺寸約束：{enclosure_constraint}"
    )


def build_params_user_prompt(
    *,
    project_name: str,
    category: str,
    plan: Dict[str, Any],
) -> str:
    """Params 階段 user prompt（control token <|im_start|>params + PlanJSON）。"""
    plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
    return (
        f"<|im_start|>params\n"
        f"專案：{project_name}（{category}）\n"
        f"PlanJSON：\n{plan_json}\n"
        f"請依 Plan 輸出對應 ParamsJSON（座標 + 線路 + 通風幾何）。"
    )
