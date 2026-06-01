"""lib/pcb — PCB 權威座標資料層。

每個檔案經過至少兩個獨立來源（EAGLE/KiCad/官方 PDF）交叉驗證，
容差 ±0.1mm 以內。座標系：PCB 左下角為原點，X 向右，Y 向上，單位 mm。

通用型別在 _types.py，個別 PCB 在各檔案。
"""
from ._types import (
    NamedPin,
    MountingHole,
    SubComponent,
    HeaderGroup,
    PCBSpec,
    derive_connector_ports_generic,
)
from .arduino_uno_r3 import (
    ARDUINO_UNO_R3,
    HEADER_GROUPS,
    JANALOG_PINS,
    JDIGITAL_PINS,
    ICSP_PINS,
    MOUNTING_HOLES,
    SUB_COMPONENTS,
    derive_connector_port_specs,
    find_pin,
    get_all_pins,
)
from .esp32_devkit_v1 import ESP32_DEVKIT_V1
from .microbit_v2 import MICROBIT_V2
from .raspberry_pi_4b import RASPBERRY_PI_4B
from .modules import (
    HCSR04, DHT22, PIR_HCSR501,
    OLED_SSD1306, LCD_1602, RELAY_1CH,
    ALL_MODULES,
)
from . import eagle_parse      # noqa: F401
from . import layout_export    # noqa: F401

__all__ = [
    # 通用型別
    'NamedPin', 'MountingHole', 'SubComponent', 'HeaderGroup', 'PCBSpec',
    'derive_connector_ports_generic',
    # Arduino Uno R3
    'ARDUINO_UNO_R3',
    'HEADER_GROUPS', 'JANALOG_PINS', 'JDIGITAL_PINS', 'ICSP_PINS',
    'MOUNTING_HOLES', 'SUB_COMPONENTS',
    'derive_connector_port_specs', 'find_pin', 'get_all_pins',
    # 其他 MCU
    'ESP32_DEVKIT_V1', 'MICROBIT_V2', 'RASPBERRY_PI_4B',
    # Tier 2 高頻模組
    'HCSR04', 'DHT22', 'PIR_HCSR501',
    'OLED_SSD1306', 'LCD_1602', 'RELAY_1CH',
    'ALL_MODULES',
    # Sub-modules
    'eagle_parse', 'layout_export',
    # registry
    'PCB_REGISTRY',
]


# ── class_name → PCBSpec 對應表（Phase 4 dispatch 用）──────────
PCB_REGISTRY = {
    # Tier 1 MCU
    'Arduino-Uno-class':   ARDUINO_UNO_R3,
    'ESP32-class':         ESP32_DEVKIT_V1,
    'Microbit-class':      MICROBIT_V2,
    'RaspberryPi-class':   RASPBERRY_PI_4B,
    # Tier 2 高頻模組（沿用 ALL_MODULES）
    **ALL_MODULES,
}
