"""shared/constants.py — 向後相容 re-export 層。

實際資料已移至 lib/specs.py（硬體規格）與 lib/ui_constants.py（UI 常數）。
本檔僅 re-export + 保留 pipeline 專用的少量常數，使既有 import 不壞。
"""
from __future__ import annotations

# ── Re-export: 元件硬體規格（SSOT 在 lib/specs.py）────────
from lib.specs import (                         # noqa: F401
    POWER_MA,
    PRICE_NTD,
    VOLTAGE_V,
    SUPPLY_V,
    USB_BUDGET_MA,
    RAIL_3V3_BUDGET_MA,
    THERMAL_THRESHOLD_MW,
    POWER_BUDGET_MA,
    STALL_MA,
    BOM_URLS,
    COMPONENT_NAME_ALIASES,
    COMPONENT_SHORTHAND_ALIASES,
    WEIGHT_G,
    THERMAL_MW,
    lookup_constant,
    resolve_component_alias,
)

# ── Re-export: UI 常數（SSOT 在 lib/ui_constants.py）──────
from lib.ui_constants import (                  # noqa: F401
    UI_KEY_TO_CLASS,
    UI_COMP_MA,
    UI_COMP_ALT,
    UI_PROMPT_CORE_PATTERNS,
    UI_POWER_BUDGETS,
    UI_ROLE_COLOR,
    get_ui_constants,
)

# ── Pipeline 專用（僅 services 層使用）────────────────────

def truncate_issues(issues: list, limit: int = 5) -> list:
    """截取前 limit 項，超出時追加提示。"""
    if len(issues) <= limit:
        return issues[:limit]
    return issues[:limit] + [f"…另有 {len(issues) - limit} 項問題未顯示"]


CHOICE_SKIP_GATE = "skip_gate"
CHOICE_CONFIRM_SWAPS = "confirm_swaps"

# ── Pipeline 運行參數 ────────────────────────────────────

MAX_GATE_ITERATIONS: int = 5
GATE_TIMEOUT_S: float = 300.0
