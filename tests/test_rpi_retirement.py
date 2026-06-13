"""tests/test_rpi_retirement.py — RaspberryPi-class 退役（方案 B）雙向回歸鎖。

使用者 2026-06-13 裁定：小型 STEM demo 目標下不需 Linux SBC（過於複雜、價格/功耗高、
消費級 3D 列印無益）→ RaspberryPi-class 從**使用者可選詞彙/taxonomy** 退役，但
**infra 休眠保留**（registry ComponentSpec / SSOT verified.json / lib/pcb / firmware /
MCU_COMPONENTS=5 皆不動，僅退出選型詞彙）。零資料遺失。

本檔鎖兩個方向：
  ① 退役：RaspberryPi-class **不得**出現在 user-facing Brain taxonomy / all_valid_types /
     rationale / alias（防有人把它加回選型空間）。
  ② 休眠保留：RaspberryPi-class **必須**仍在 COMPONENT_REGISTRY 且 MCU_COMPONENTS 維持 5
     （防有人把「退役」誤解為「刪 infra」→ 破壞 pcb/firmware/SSOT 鏈）。

對應 [[Key Decisions]] demo 換 MCU / 範本收斂、[[No-Silent-Fallback 設計哲學]]（退役須可查、非靜默）。
"""
from lib.config import TAXONOMY_CONFIG, EDUCATIONAL_RATIONALE_TEMPLATES
from lib.registry import COMPONENT_REGISTRY
from lib.registry._reg_mcu import MCU_COMPONENTS

_RPI = "RaspberryPi-class"


def test_rpi_retired_from_user_facing_taxonomy():
    """RPi 不在 prod 使用者可選 Brain 詞彙 / 衍生 all_valid_types / rationale / alias。"""
    assert _RPI not in TAXONOMY_CONFIG["component_taxonomy"]["Brain"], "RPi 不應在 Brain taxonomy"
    assert _RPI not in TAXONOMY_CONFIG["all_valid_types"], "RPi 不應在 all_valid_types（衍生）"
    assert _RPI not in EDUCATIONAL_RATIONALE_TEMPLATES, "RPi 不應在選型 rationale"
    assert _RPI not in set(TAXONOMY_CONFIG["alias_mapping"].values()), "alias 不應映射到 RPi"
    # Brain 詞彙 = 4 個現役 MCU（Uno / Nano / ESP32 / Microbit）
    assert set(TAXONOMY_CONFIG["component_taxonomy"]["Brain"]) == {
        "Arduino-Uno-class", "Arduino-Nano-class", "ESP32-class", "Microbit-class"}


def test_rpi_retired_from_training_taxonomy():
    """訓練詞彙也退役（不在退役選項上訓練）。"""
    from training.config import TAXONOMY_CONFIG as TRAIN_TAXONOMY, EDUCATIONAL_RATIONALE
    assert _RPI not in TRAIN_TAXONOMY["component_taxonomy"]["Brain"]
    assert _RPI not in EDUCATIONAL_RATIONALE


def test_rpi_infra_kept_dormant():
    """休眠保留：infra（registry ComponentSpec + MCU 計數）不得因退役被刪。"""
    assert _RPI in COMPONENT_REGISTRY, "退役≠刪 infra：RaspberryPi-class 應仍在 COMPONENT_REGISTRY"
    assert _RPI in MCU_COMPONENTS, "RaspberryPi-class 應仍在 MCU_COMPONENTS（infra 休眠）"
    assert len(MCU_COMPONENTS) == 5, f"MCU_COMPONENTS 應維持 5（含休眠 RPi），實得 {len(MCU_COMPONENTS)}"
