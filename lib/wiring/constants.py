"""Wiring subsystem constants — MCU-specific power passives lookup."""
from __future__ import annotations

# ── 通用被動元件粗估成本目錄（不進 verified.json，只作 BOM 成本加總用） ──
# unit_ntd: 單顆粗估新台幣；current_ma/thermal_mw 強制零（被動不耗電）
PASSIVE_CATALOG: dict[str, dict] = {
    "R": {"unit_ntd": 1, "current_ma": 0.0, "thermal_mw": 0.0},
    "C": {"unit_ntd": 2, "current_ma": 0.0, "thermal_mw": 0.0},
    "D": {"unit_ntd": 2, "current_ma": 0.0, "thermal_mw": 0.0},
}

# ── MCU 電源軌被動元件（由 MCU config 驅動，不硬編碼） ────────
MCU_POWER_PASSIVES: dict[str, list[dict]] = {
    "Arduino": [
        {"kind": "C", "value": "100µF", "topo": "bulk", "net": "5V"},
        {"kind": "C", "value": "100nF", "topo": "decoupling", "net": "5V"},
    ],
    "ESP32": [
        {"kind": "C", "value": "470µF", "topo": "bulk", "net": "3V3"},
        {"kind": "C", "value": "100nF", "topo": "decoupling", "net": "3V3"},
    ],
    "Microbit": [
        {"kind": "C", "value": "100µF", "topo": "bulk", "net": "3V3"},
        {"kind": "C", "value": "100nF", "topo": "decoupling", "net": "3V3"},
    ],
    "RPi": [],  # RPi 自帶完整電源管理
}
