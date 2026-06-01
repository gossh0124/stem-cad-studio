"""Tier 2 高頻模組板 PCBSpec — 6 個常用 sensor/output 模組。

⚠️ Phase A-2 限制：
  Tier 2 模組通常是教育市場「白牌」設計，多家廠商 clone，
  整板尺寸有變體（PCB 外形 ±2mm 是常見差異）。

驗證來源：
  ✅ Pin 拓樸（pitch、count）：KiCad 官方 footprint 已抓
     data/pcb_sources/modules/AM2302_DHT22.kicad_mod (pin pitch 2.54mm 確認)
  ⚠️ PCB 外形：採用最常見白牌規格（vendor datasheet + 實物商品頁）
  ❌ 子元件 (sensor body) 位置：估算值，需實物校驗

模組板共通特徵：
  - 小型 PCB (10~80mm)
  - 1 排 N pin header (pitch 2.54mm)
  - 0~4 個 mounting holes
  - 1 個主 IC / sensor 本體
  - 部分有突出邊緣的 connector（USB/Audio/screw terminal）
"""
from __future__ import annotations
from typing import Tuple, Dict
from ._types import NamedPin, MountingHole, SubComponent, HeaderGroup, PCBSpec


def _make_inline_header(pin_names: Tuple[str, ...], y: float = 1.27,
                        x_start: float = 1.27, pitch: float = 2.54,
                        port_type: str = 'GPIO') -> Tuple[NamedPin, ...]:
    """工廠：產生一排線性排針 NamedPin。"""
    return tuple(
        NamedPin(name=name, x=x_start + i * pitch, y=y,
                 pad_index=i + 1, function=port_type)
        for i, name in enumerate(pin_names)
    )


# ════════════════════════════════════════════════════════════════════
# HC-SR04 超音波測距模組
# ════════════════════════════════════════════════════════════════════
# Datasheet: 45×20×15mm，4 pin header（VCC/Trig/Echo/GND）pitch 2.54mm
# 兩顆超音波 transducer (TX/RX) 圓柱直徑 16mm，間距 26mm
HCSR04_PINS = _make_inline_header(
    ('VCC', 'Trig', 'Echo', 'GND'),
    y=1.27, x_start=12.31, pitch=2.54,
    port_type='GPIO',
)
HCSR04 = PCBSpec(
    name='HC-SR04 Ultrasonic Sensor',
    length=45.0, width=20.0, pcb_thickness=1.6,
    pins=HCSR04_PINS,
    pin_groups={'HEADER': tuple(p.pad_index for p in HCSR04_PINS)},
    mounting_holes=(),
    sub_components=(
        SubComponent(name='TX-Transducer', package='UltrasonicTX',
                     anchor_x=10.0, anchor_y=10.0,
                     body_l=16.0, body_w=16.0, body_h=12.0,
                     description='40kHz TX transducer',
                     thermal_typical_mw=70.0, thermal_idle_mw=10.0,
                     thermal_peak_mw=240.0,
                     thermal_formula='Module 15mA avg × 5V = 75mW; ping burst 50mA',
                     thermal_source='HC-SR04 datasheet (Cytron/ElecFreaks)'),
        SubComponent(name='RX-Transducer', package='UltrasonicRX',
                     anchor_x=36.0, anchor_y=10.0,
                     body_l=16.0, body_w=16.0, body_h=12.0,
                     description='40kHz RX transducer',
                     thermal_typical_mw=5.0, thermal_idle_mw=1.0,
                     thermal_peak_mw=10.0,
                     thermal_formula='Op-amp + comparator: ~1mA × 5V',
                     thermal_source='HC-SR04 datasheet (Cytron/ElecFreaks)'),
    ),
    header_groups=(
        HeaderGroup(name='4Pin-Header', pin_indices=tuple(p.pad_index for p in HCSR04_PINS),
                    profile='slot', port_type='GPIO', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# DHT22 溫濕度感測器（PCB 版）
# ════════════════════════════════════════════════════════════════════
# 25×15×8mm（含 PCB；主感測器本體 14×7×4mm）
# 4 pin header pitch 2.54mm（部分版本只標 3 pin: VCC/Data/GND）
DHT22_PINS = _make_inline_header(
    ('VCC', 'Data', 'NC', 'GND'),
    y=1.27, x_start=8.46, pitch=2.54,
    port_type='GPIO',
)
DHT22 = PCBSpec(
    name='DHT22 Temp/Humidity Sensor',
    length=25.1, width=15.1, pcb_thickness=1.6,
    pins=DHT22_PINS,
    pin_groups={'HEADER': tuple(p.pad_index for p in DHT22_PINS)},
    mounting_holes=(),
    sub_components=(
        SubComponent(name='DHT22-Sensor', package='AM2302',
                     anchor_x=12.5, anchor_y=8.5,
                     body_l=14.0, body_w=7.0, body_h=6.1,
                     description='AM2302 capacitive humidity + thermistor',
                     thermal_typical_mw=5.0, thermal_idle_mw=0.16,
                     thermal_peak_mw=8.0,
                     thermal_formula='Active 1.5mA × 3.3V; sleep 50µA × 3.3V',
                     thermal_source='AM2302 (DHT22) datasheet §5'),
    ),
    header_groups=(
        HeaderGroup(name='4Pin-Header', pin_indices=tuple(p.pad_index for p in DHT22_PINS),
                    profile='slot', port_type='GPIO', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# HC-SR501 PIR 動作感測器
# ════════════════════════════════════════════════════════════════════
# 32×24×25mm（含 Fresnel lens 圓頂 ⌀23×8mm）
# 3 pin header (VCC/OUT/GND) + 2 個 trim pot 旋鈕
PIR_PINS = _make_inline_header(
    ('VCC', 'OUT', 'GND'),
    y=1.27, x_start=12.73, pitch=2.54,
    port_type='GPIO',
)
PIR_HCSR501 = PCBSpec(
    name='HC-SR501 PIR Motion Sensor',
    length=32.0, width=24.0, pcb_thickness=1.6,
    pins=PIR_PINS,
    pin_groups={'HEADER': tuple(p.pad_index for p in PIR_PINS)},
    mounting_holes=(),
    sub_components=(
        SubComponent(name='Fresnel-Dome', package='Fresnel-23',
                     anchor_x=16.0, anchor_y=14.0,
                     body_l=23.0, body_w=23.0, body_h=15.0,
                     description='白色 Fresnel lens 圓頂（包含 PIR 元件）',
                     thermal_typical_mw=5.0, thermal_idle_mw=0.5,
                     thermal_peak_mw=25.0,
                     thermal_formula='Module quiescent ~1mA × 5V; trig + LED 5mA',
                     thermal_source='HC-SR501 datasheet'),
    ),
    header_groups=(
        HeaderGroup(name='3Pin-Header', pin_indices=tuple(p.pad_index for p in PIR_PINS),
                    profile='slot', port_type='GPIO', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# SSD1306 OLED 0.96"
# ════════════════════════════════════════════════════════════════════
# 27×27×4mm（部分版本 27×28），4 pin (VCC/GND/SCL/SDA) I2C
# 顯示螢幕 21.7×11.2mm 居中，4 個 ⌀2mm mounting holes
OLED_PINS = _make_inline_header(
    ('GND', 'VCC', 'SCL', 'SDA'),
    y=25.0, x_start=8.46, pitch=2.54,
    port_type='I2C',
)
OLED_SSD1306 = PCBSpec(
    name='SSD1306 OLED 0.96"',
    length=27.0, width=27.0, pcb_thickness=1.0,
    pins=OLED_PINS,
    pin_groups={'I2C': tuple(p.pad_index for p in OLED_PINS)},
    mounting_holes=(
        MountingHole(x=2.5, y=2.5, diameter=2.0),
        MountingHole(x=24.5, y=2.5, diameter=2.0),
        MountingHole(x=2.5, y=22.5, diameter=2.0),
        MountingHole(x=24.5, y=22.5, diameter=2.0),
    ),
    sub_components=(
        SubComponent(name='OLED-Screen', package='OLED-21.7x11.2',
                     anchor_x=13.5, anchor_y=14.0,
                     body_l=21.7, body_w=11.2, body_h=1.5,
                     description='128×64 monochrome OLED display',
                     thermal_typical_mw=10.0, thermal_idle_mw=1.0,
                     thermal_peak_mw=15.0,
                     thermal_formula='SSD1306 active: ~3mA × 3.3V; all-on ~5mA',
                     thermal_source='SSD1306 datasheet §11.4'),
    ),
    header_groups=(
        HeaderGroup(name='I2C-Header', pin_indices=tuple(p.pad_index for p in OLED_PINS),
                    profile='slot', port_type='I2C', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# LCD 1602 (HD44780 + I2C backpack)
# ════════════════════════════════════════════════════════════════════
# 80×36×12mm（無 backpack 板厚 1.6mm；含 I2C backpack 後 +12mm）
# 16 pin header + I2C backpack 4 pin (VCC/GND/SDA/SCL)
# 顯示區 64.5×16mm 居中
LCD1602_PINS = _make_inline_header(
    ('GND', 'VCC', 'SDA', 'SCL'),
    y=33.0, x_start=2.5, pitch=2.54,
    port_type='I2C',
)
LCD_1602 = PCBSpec(
    name='LCD 1602 with I2C Backpack',
    length=80.0, width=36.0, pcb_thickness=1.6,
    pins=LCD1602_PINS,
    pin_groups={'I2C': tuple(p.pad_index for p in LCD1602_PINS)},
    mounting_holes=(
        MountingHole(x=2.5, y=2.5, diameter=3.0),
        MountingHole(x=77.5, y=2.5, diameter=3.0),
        MountingHole(x=2.5, y=33.5, diameter=3.0),
        MountingHole(x=77.5, y=33.5, diameter=3.0),
    ),
    sub_components=(
        SubComponent(name='LCD-Display', package='LCD-64.5x16',
                     anchor_x=40.0, anchor_y=18.0,
                     body_l=64.5, body_w=16.0, body_h=8.0,
                     description='HD44780 16×2 character LCD',
                     thermal_typical_mw=125.0, thermal_idle_mw=5.0,
                     thermal_peak_mw=150.0,
                     thermal_formula='Backlight LED 24mA × 5V dominates; HD44780 1mA',
                     thermal_source='HD44780 datasheet §13.2 + LED backlight'),
    ),
    header_groups=(
        HeaderGroup(name='I2C-Header', pin_indices=tuple(p.pad_index for p in LCD1602_PINS),
                    profile='slot', port_type='I2C', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# 1-Channel 5V Relay Module
# ════════════════════════════════════════════════════════════════════
# 50×26×19mm，input 3 pin (VCC/GND/IN) + screw terminals (NO/COM/NC)
# 主件：JQC-3FF 5V relay (19×15.5×15.5mm) 矩形繼電器
RELAY_PINS = _make_inline_header(
    ('IN', 'GND', 'VCC'),
    y=1.27, x_start=2.5, pitch=2.54,
    port_type='GPIO',
)
RELAY_1CH = PCBSpec(
    name='1-Channel 5V Relay Module',
    length=50.0, width=26.0, pcb_thickness=1.6,
    pins=RELAY_PINS,
    pin_groups={'CTRL': tuple(p.pad_index for p in RELAY_PINS)},
    mounting_holes=(
        MountingHole(x=2.5, y=23.5, diameter=3.0),
        MountingHole(x=12.5, y=23.5, diameter=3.0),
    ),
    sub_components=(
        SubComponent(name='Relay-JQC-3FF', package='JQC-3FF',
                     anchor_x=22.0, anchor_y=15.0,
                     body_l=19.0, body_w=15.5, body_h=15.5,
                     description='SRD-05VDC-SL-C 5V relay (10A 250VAC)',
                     thermal_typical_mw=360.0, thermal_idle_mw=0.0,
                     thermal_peak_mw=400.0,
                     thermal_formula='Coil energized: 71.4mA × 5V = 357mW',
                     thermal_source='SRD-05VDC-SL-C datasheet §3'),
        SubComponent(name='Screw-Terminals', package='3.81mm-3pos',
                     anchor_x=42.0, anchor_y=15.0,
                     body_l=11.5, body_w=10.0, body_h=10.0,
                     description='3-pos screw terminal block (NO/COM/NC)',
                     protrudes='right', overhang=2.0, profile='rect'),
    ),
    header_groups=(
        HeaderGroup(name='Control-Header', pin_indices=tuple(p.pad_index for p in RELAY_PINS),
                    profile='slot', port_type='GPIO', clearance_mm=1.0),
    ),
)


# ════════════════════════════════════════════════════════════════════
# 模組註冊表（給 registry.py 統一接接）
# ════════════════════════════════════════════════════════════════════

ALL_MODULES = {
    'Sensor-Ultrasonic-class':  HCSR04,
    'Sensor-TempHumid-class':   DHT22,
    'Sensor-PIR-class':         PIR_HCSR501,
    'Display-OLED-class':       OLED_SSD1306,
    'Display-LCD-class':        LCD_1602,
    'Relay-Module-class':       RELAY_1CH,
}


if __name__ == '__main__':
    for class_name, mod in ALL_MODULES.items():
        print(f'{class_name:30s} {mod.name:35s} {mod.length}×{mod.width}mm '
              f'pins={len(mod.pins)} sub={len(mod.sub_components)}')
