"""ESP32 DevKit V1 (DOIT, 30-pin) — PCB 座標（Phase A-1 級，社群 clone）。

⚠️ Phase A-1 限制：
  DOIT 沒有發布官方 Gerber / EAGLE / KiCad 原始檔，
  該板由社群 clone 出多個變體（51.45×23.37 vs 51.80×28.20 兩種寬度）。
  本檔採用最常見的 51.45×28 mm 寬版（22.86mm row spacing），
  須以實物 caliper 測量驗證才能達 Phase A 級。

來源：
  A1. ESP32-WROOM-32 KiCad footprint (KiCad 官方 RF_Module.pretty)
      data/pcb_sources/esp32_devkit_v1/Module_ESP-WROOM-32.kicad_mod
      （僅 SMD 模組，不是整板）
  A2. ESP32 + ESP32-WROOM-32 datasheet (Espressif)
      data/pcb_sources/esp32_devkit_v1/esp32-datasheet.pdf
  A3. 社群高解析 pinout 圖（mischianti.org SVG / espboards.dev 數據）
      手動測量值整合，無第三獨立來源

公開最佳實踐參考：
  - github.com/TronixLab/DOIT_ESP32_DevKit-v1_30P (社群 KiCad 反向工程)
  - mischianti.org/doit-esp32-dev-kit-v1-high-resolution-pinout-and-specs/

關鍵尺寸（51.45×28 寬變體）：
  Board: 51.45 × 28.0 × 1.6mm
  Pin pitch 2.54mm，左右各 15 pins
  Row spacing: 22.86mm (0.9", 9-pitch)
  Pin 1 X (USB 那端): 1.27mm
  Micro-USB body 7.5×5.6×2.4mm，突出短邊約 0.5mm
"""
from __future__ import annotations
from typing import Tuple, Dict
from ._types import NamedPin, MountingHole, SubComponent, HeaderGroup, PCBSpec

BOARD_LENGTH = 51.45  # Phase A-1 ESTIMATED：DOIT 社群 clone 無官方 Gerber/EAGLE，
                      # 採最常見引用值 51.45mm（mischianti/espboards），須 caliper 實測（problem.md E6）。
                      # SSOT19 對齊：verified.json length_mm=51.45 同值。
BOARD_WIDTH = 28.0
PCB_THICKNESS = 1.6

# Header row spacing：寬變體 22.86mm
# 左排 y=2.57，右排 y=25.43（中心對稱於 14.0mm）
_LEFT_HEADER_Y = 2.57
_RIGHT_HEADER_Y = 25.43

# ── 左排 (y=2.57, 15 pins, 命名以 USB 那側為 pin 1) ─────────────
LEFT_HEADER_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='EN',     x=1.27,  y=_LEFT_HEADER_Y, pad_index=1,  function='RESET', arduino_pin='EN'),
    NamedPin(name='VP',     x=3.81,  y=_LEFT_HEADER_Y, pad_index=2,  function='ANALOG', arduino_pin='GPIO36'),
    NamedPin(name='VN',     x=6.35,  y=_LEFT_HEADER_Y, pad_index=3,  function='ANALOG', arduino_pin='GPIO39'),
    NamedPin(name='GPIO34', x=8.89,  y=_LEFT_HEADER_Y, pad_index=4,  function='GPIO',   arduino_pin='GPIO34'),
    NamedPin(name='GPIO35', x=11.43, y=_LEFT_HEADER_Y, pad_index=5,  function='GPIO',   arduino_pin='GPIO35'),
    NamedPin(name='GPIO32', x=13.97, y=_LEFT_HEADER_Y, pad_index=6,  function='GPIO',   arduino_pin='GPIO32'),
    NamedPin(name='GPIO33', x=16.51, y=_LEFT_HEADER_Y, pad_index=7,  function='GPIO',   arduino_pin='GPIO33'),
    NamedPin(name='GPIO25', x=19.05, y=_LEFT_HEADER_Y, pad_index=8,  function='GPIO',   arduino_pin='GPIO25'),
    NamedPin(name='GPIO26', x=21.59, y=_LEFT_HEADER_Y, pad_index=9,  function='GPIO',   arduino_pin='GPIO26'),
    NamedPin(name='GPIO27', x=24.13, y=_LEFT_HEADER_Y, pad_index=10, function='GPIO',   arduino_pin='GPIO27'),
    NamedPin(name='GPIO14', x=26.67, y=_LEFT_HEADER_Y, pad_index=11, function='GPIO',   arduino_pin='GPIO14'),
    NamedPin(name='GPIO12', x=29.21, y=_LEFT_HEADER_Y, pad_index=12, function='GPIO',   arduino_pin='GPIO12'),
    NamedPin(name='GND_L',  x=31.75, y=_LEFT_HEADER_Y, pad_index=13, function='GND'),
    NamedPin(name='GPIO13', x=34.29, y=_LEFT_HEADER_Y, pad_index=14, function='GPIO',   arduino_pin='GPIO13'),
    NamedPin(name='GPIO9',  x=36.83, y=_LEFT_HEADER_Y, pad_index=15, function='GPIO',   arduino_pin='GPIO9'),
)

# ── 右排 (y=26.73, 15 pins) ────────────────────────────────────
RIGHT_HEADER_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='Vin',    x=1.27,  y=_RIGHT_HEADER_Y, pad_index=16, function='POWER', arduino_pin='Vin'),
    NamedPin(name='GND_R',  x=3.81,  y=_RIGHT_HEADER_Y, pad_index=17, function='GND'),
    NamedPin(name='+3V3',   x=6.35,  y=_RIGHT_HEADER_Y, pad_index=18, function='POWER', arduino_pin='+3V3'),
    NamedPin(name='GPIO15', x=8.89,  y=_RIGHT_HEADER_Y, pad_index=19, function='GPIO',   arduino_pin='GPIO15'),
    NamedPin(name='GPIO2',  x=11.43, y=_RIGHT_HEADER_Y, pad_index=20, function='GPIO',   arduino_pin='GPIO2'),
    NamedPin(name='GPIO4',  x=13.97, y=_RIGHT_HEADER_Y, pad_index=21, function='GPIO',   arduino_pin='GPIO4'),
    NamedPin(name='RX2',    x=16.51, y=_RIGHT_HEADER_Y, pad_index=22, function='UART',   arduino_pin='GPIO16'),
    NamedPin(name='TX2',    x=19.05, y=_RIGHT_HEADER_Y, pad_index=23, function='UART',   arduino_pin='GPIO17'),
    NamedPin(name='GPIO5',  x=21.59, y=_RIGHT_HEADER_Y, pad_index=24, function='SPI',    arduino_pin='GPIO5'),
    NamedPin(name='GPIO18', x=24.13, y=_RIGHT_HEADER_Y, pad_index=25, function='SPI',    arduino_pin='GPIO18'),
    NamedPin(name='GPIO19', x=26.67, y=_RIGHT_HEADER_Y, pad_index=26, function='SPI',    arduino_pin='GPIO19'),
    NamedPin(name='GPIO21', x=29.21, y=_RIGHT_HEADER_Y, pad_index=27, function='I2C',    arduino_pin='GPIO21'),
    NamedPin(name='RX0',    x=31.75, y=_RIGHT_HEADER_Y, pad_index=28, function='UART',   arduino_pin='GPIO3'),
    NamedPin(name='TX0',    x=34.29, y=_RIGHT_HEADER_Y, pad_index=29, function='UART',   arduino_pin='GPIO1'),
    NamedPin(name='GPIO22', x=36.83, y=_RIGHT_HEADER_Y, pad_index=30, function='I2C',    arduino_pin='GPIO22'),
)

ALL_PINS: Tuple[NamedPin, ...] = LEFT_HEADER_PINS + RIGHT_HEADER_PINS

PIN_GROUPS: Dict[str, Tuple[int, ...]] = {
    'LEFT':  tuple(p.pad_index for p in LEFT_HEADER_PINS),
    'RIGHT': tuple(p.pad_index for p in RIGHT_HEADER_PINS),
}

HEADER_GROUPS: Tuple[HeaderGroup, ...] = (
    HeaderGroup(name='Left-Header',
                pin_indices=PIN_GROUPS['LEFT'],
                profile='slot', port_type='GPIO', rows=1, clearance_mm=1.0),
    HeaderGroup(name='Right-Header',
                pin_indices=PIN_GROUPS['RIGHT'],
                profile='slot', port_type='GPIO', rows=1, clearance_mm=1.0),
)

# DOIT V1 無 mounting holes
MOUNTING_HOLES: Tuple[MountingHole, ...] = ()

SUB_COMPONENTS: Tuple[SubComponent, ...] = (
    # ESP32-WROOM-32 module — opposite end from USB
    SubComponent(name='ESP32-WROOM-32', package='SMD-WROOM',
                 anchor_x=43.0, anchor_y=14.0,
                 body_l=18.0, body_w=25.5, body_h=3.2,
                 description='ESP32-WROOM-32 module (metal RF shield)',
                 thermal_typical_mw=800.0, thermal_idle_mw=100.0,
                 thermal_peak_mw=1300.0,
                 thermal_formula='WiFi active: 160mA x 5V; TX burst peak 240mA',
                 thermal_source='Espressif ESP32 datasheet S5 RF Power',
                 rth_ja_cw=32.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 32.0, "ref": "Espressif ESP32 DS Section 5.3 module-level"},
                     {"source": "jedec", "value": 30.0, "ref": "JESD51 SMD-module 18x25mm still air"},
                     {"source": "empirical", "value": 28.0, "ref": "1/(12*0.0029) h=12 W/m2K WROOM 29cm2"},
                 )),
    # PCB trace antenna area at top of WROOM module (keep-out zone)
    SubComponent(name='Antenna-Area', package='PCB-TRACE',
                 anchor_x=47.0, anchor_y=14.0,
                 body_l=2.5, body_w=7.0, body_h=0.0,
                 description='PCB trace antenna, keep-out zone'),
    # Micro-USB connector — protrudes from x=0 edge, centered on y=14
    SubComponent(name='USB-Micro', package='USB-MICRO-B',
                 anchor_x=2.5, anchor_y=14.0,
                 body_l=5.6, body_w=7.5, body_h=2.4,
                 rotation='R270',
                 description='Micro-USB 5V connector',
                 protrudes='left', overhang=0.5, profile='stadium'),
    # AMS1117 LDO (3.3V regulator, SOT-223)
    SubComponent(name='LDO-AMS1117', package='SOT-223',
                 anchor_x=15.0, anchor_y=22.0,
                 body_l=6.5, body_w=3.5, body_h=1.6,
                 description='AMS1117-3.3 3.3V LDO regulator',
                 thermal_typical_mw=80.0, thermal_idle_mw=10.0,
                 thermal_peak_mw=200.0,
                 thermal_formula='LDO drop: (5-3.3)V x 50mA = 85mW',
                 thermal_source='AMS1117 datasheet S3',
                 rth_ja_cw=75.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 75.0, "ref": "AMS AMS1117 DS Table 2 SOT-223"},
                     {"source": "jedec", "value": 62.0, "ref": "JESD51-2 SOT-223 still air"},
                     {"source": "empirical", "value": 60.0, "ref": "1/(15*0.00011) h=15 W/m2K SOT-223 1.1cm2"},
                 )),
    # CP2102 / CH340 USB-UART bridge
    SubComponent(name='USB-UART', package='SOIC-8',
                 anchor_x=8.0, anchor_y=22.0,
                 body_l=4.9, body_w=3.9, body_h=1.5,
                 description='CP2102 / CH340 USB-UART converter',
                 thermal_typical_mw=25.0, thermal_idle_mw=2.0,
                 thermal_peak_mw=50.0,
                 thermal_formula='USB active: 5mA x 5V = 25mW',
                 thermal_source='CP2102 datasheet S3.5',
                 rth_ja_cw=125.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 125.0, "ref": "Silicon Labs AN721 Table 1 SOIC-8"},
                     {"source": "jedec", "value": 130.0, "ref": "JESD51 SOIC-8 still air"},
                     {"source": "empirical", "value": 120.0, "ref": "1/(12*0.0007) h=12 W/m2K SOIC-8 0.7cm2"},
                 )),
    # EN (reset) tactile button — right side near USB end
    SubComponent(name='BTN-EN', package='SW-SMD-4P',
                 anchor_x=6.0, anchor_y=24.0,
                 body_l=4.0, body_w=4.0, body_h=2.5,
                 description='EN (Enable/Reset) tactile button'),
    # BOOT (GPIO0) tactile button — left side near USB end
    SubComponent(name='BTN-BOOT', package='SW-SMD-4P',
                 anchor_x=6.0, anchor_y=4.0,
                 body_l=4.0, body_w=4.0, body_h=2.5,
                 description='BOOT (GPIO0) tactile button'),
    # Power indicator LED (red)
    SubComponent(name='LED-PWR', package='LED-0805',
                 anchor_x=10.0, anchor_y=23.0,
                 body_l=2.0, body_w=1.2, body_h=0.8,
                 description='Red power indicator LED'),
)

ESP32_DEVKIT_V1 = PCBSpec(
    name='ESP32 DevKit V1 (DOIT 30-pin)',
    length=BOARD_LENGTH,
    width=BOARD_WIDTH,
    pcb_thickness=PCB_THICKNESS,
    pins=ALL_PINS,
    pin_groups=PIN_GROUPS,
    mounting_holes=MOUNTING_HOLES,
    sub_components=SUB_COMPONENTS,
    header_groups=HEADER_GROUPS,
)


if __name__ == '__main__':
    print(f'=== {ESP32_DEVKIT_V1.name} ===')
    print(f'Board: {BOARD_LENGTH} × {BOARD_WIDTH} × {PCB_THICKNESS} mm')
    print(f'Pins: {len(ESP32_DEVKIT_V1.pins)} (expect 30)')
    print(f'Header groups: {len(HEADER_GROUPS)}')
    print(f'Sub-components: {len(SUB_COMPONENTS)}')
    print(f'Mounting holes: {len(MOUNTING_HOLES)} (expect 0)')

    # 驗證
    p1 = ESP32_DEVKIT_V1.find_pin('+3V3')
    print(f'\n+3V3 at ({p1.x}, {p1.y}) on right header')
    span_l = LEFT_HEADER_PINS[-1].x - LEFT_HEADER_PINS[0].x
    print(f'Left header span: {span_l:.2f}mm = {span_l/2.54:.0f} pitches')
