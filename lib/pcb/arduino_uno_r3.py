"""Arduino Uno R3 — 權威 PCB 座標資料（Phase A 三來源交叉驗證產物）。

資料來源：
  A1. EAGLE .brd  — `data/pcb_sources/arduino_uno_r3/eagle_official/UNO-TH_Rev3e.brd`
                    （Arduino 官方 v9.3.1, 2019-03-06 釋出）
  A2. KiCad mod   — `data/pcb_sources/arduino_uno_r3/Arduino_UNO_R3.kicad_mod`
                    （gitlab.com/kicad/libraries/kicad-footprints/Module.pretty）
  A3. PDF spec    — `data/pcb_sources/arduino_uno_r3/A000066-datasheet.pdf`
                    （Arduino 官方 datasheet, 26 pages）

驗證結果（2026-05-08）：
  - 32 個 header pad 位置：EAGLE = KiCad，誤差 0.000mm
  - 14 個 JANALOG pin 名 + 18 個 JDIGITAL pin 名：PDF 確認
  - 4 個 mounting holes：EAGLE = 既有 registry 數據
  - A5↔D0 對齊：x = 63.500（誤差 0.000mm）
  - D7-D8 非標間距：4.064mm (160mil) ✓
  - NC~A5 跨距 = ATmega328P 長度 = 35.560mm ✓

座標系：PCB 左下角 = (0, 0)，X 向右，Y 向上，Z 由 PCB 表面向上。
單位：mm。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ._types import NamedPin, MountingHole, SubComponent, HeaderGroup, PCBSpec


# ═══════════════════════════════════════════════════════════════════════
# Board outline
# ═══════════════════════════════════════════════════════════════════════

BOARD_LENGTH = 68.58   # mm（PDF + EAGLE）
BOARD_WIDTH  = 53.34   # mm
PCB_THICKNESS = 1.6    # mm（標準 Arduino PCB）


# ═══════════════════════════════════════════════════════════════════════
# JANALOG (bottom edge, y = 2.54mm) — PDF Section 5.1
# 14 pins = POWER(8) + AD(6), gap = 5.08mm between pin 8 and pin 9
# EAGLE refs: POWER.1~8 + AD.1~6
# ═══════════════════════════════════════════════════════════════════════

JANALOG_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='NC',     x=27.940, y=2.540, pad_index=1,  eagle_ref='POWER.1', function='NC',     arduino_pin='NC',     avr_port=''),
    NamedPin(name='IOREF',  x=30.480, y=2.540, pad_index=2,  eagle_ref='POWER.2', function='POWER',  arduino_pin='IOREF',  avr_port=''),
    NamedPin(name='RESET',  x=33.020, y=2.540, pad_index=3,  eagle_ref='POWER.3', function='RESET',  arduino_pin='RESET',  avr_port='PC6'),
    NamedPin(name='+3V3',   x=35.560, y=2.540, pad_index=4,  eagle_ref='POWER.4', function='POWER',  arduino_pin='+3V3',   avr_port=''),
    NamedPin(name='+5V',    x=38.100, y=2.540, pad_index=5,  eagle_ref='POWER.5', function='POWER',  arduino_pin='+5V',    avr_port=''),
    NamedPin(name='GND',    x=40.640, y=2.540, pad_index=6,  eagle_ref='POWER.6', function='GND',    arduino_pin='GND',    avr_port=''),
    NamedPin(name='GND',    x=43.180, y=2.540, pad_index=7,  eagle_ref='POWER.7', function='GND',    arduino_pin='GND',    avr_port=''),
    NamedPin(name='VIN',    x=45.720, y=2.540, pad_index=8,  eagle_ref='POWER.8', function='POWER',  arduino_pin='VIN',    avr_port=''),
    NamedPin(name='A0',     x=50.800, y=2.540, pad_index=9,  eagle_ref='AD.1',    function='ANALOG', arduino_pin='A0',     avr_port='PC0'),
    NamedPin(name='A1',     x=53.340, y=2.540, pad_index=10, eagle_ref='AD.2',    function='ANALOG', arduino_pin='A1',     avr_port='PC1'),
    NamedPin(name='A2',     x=55.880, y=2.540, pad_index=11, eagle_ref='AD.3',    function='ANALOG', arduino_pin='A2',     avr_port='PC2'),
    NamedPin(name='A3',     x=58.420, y=2.540, pad_index=12, eagle_ref='AD.4',    function='ANALOG', arduino_pin='A3',     avr_port='PC3'),
    NamedPin(name='A4/SDA', x=60.960, y=2.540, pad_index=13, eagle_ref='AD.5',    function='I2C',    arduino_pin='A4',     avr_port='PC4'),
    NamedPin(name='A5/SCL', x=63.500, y=2.540, pad_index=14, eagle_ref='AD.6',    function='I2C',    arduino_pin='A5',     avr_port='PC5'),
)


# ═══════════════════════════════════════════════════════════════════════
# JDIGITAL (top edge, y = 50.80mm) — PDF Section 5.2
# 18 pins = IOL(8) + IOH(10), gap = 4.064mm between pin 8 and pin 9
# EAGLE refs: IOL.1~8 (D0~D7) + IOH.1~10 (D8 ... SCL)
# ═══════════════════════════════════════════════════════════════════════

JDIGITAL_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='D0',         x=63.500, y=50.800, pad_index=15, eagle_ref='IOL.1',  function='UART',   arduino_pin='D0',  avr_port='PD0'),
    NamedPin(name='D1',         x=60.960, y=50.800, pad_index=16, eagle_ref='IOL.2',  function='UART',   arduino_pin='D1',  avr_port='PD1'),
    NamedPin(name='D2',         x=58.420, y=50.800, pad_index=17, eagle_ref='IOL.3',  function='GPIO',   arduino_pin='D2',  avr_port='PD2'),
    NamedPin(name='D3',         x=55.880, y=50.800, pad_index=18, eagle_ref='IOL.4',  function='GPIO',   arduino_pin='D3',  avr_port='PD3'),
    NamedPin(name='D4',         x=53.340, y=50.800, pad_index=19, eagle_ref='IOL.5',  function='GPIO',   arduino_pin='D4',  avr_port='PD4'),
    NamedPin(name='D5',         x=50.800, y=50.800, pad_index=20, eagle_ref='IOL.6',  function='GPIO',   arduino_pin='D5',  avr_port='PD5'),
    NamedPin(name='D6',         x=48.260, y=50.800, pad_index=21, eagle_ref='IOL.7',  function='GPIO',   arduino_pin='D6',  avr_port='PD6'),
    NamedPin(name='D7',         x=45.720, y=50.800, pad_index=22, eagle_ref='IOL.8',  function='GPIO',   arduino_pin='D7',  avr_port='PD7'),
    NamedPin(name='D8',         x=41.656, y=50.800, pad_index=23, eagle_ref='IOH.1',  function='GPIO',   arduino_pin='D8',  avr_port='PB0'),
    NamedPin(name='D9',         x=39.116, y=50.800, pad_index=24, eagle_ref='IOH.2',  function='GPIO',   arduino_pin='D9',  avr_port='PB1'),
    NamedPin(name='SS',         x=36.576, y=50.800, pad_index=25, eagle_ref='IOH.3',  function='SPI',    arduino_pin='D10', avr_port='PB2'),
    NamedPin(name='MOSI',       x=34.036, y=50.800, pad_index=26, eagle_ref='IOH.4',  function='SPI',    arduino_pin='D11', avr_port='PB3'),
    NamedPin(name='MISO',       x=31.496, y=50.800, pad_index=27, eagle_ref='IOH.5',  function='SPI',    arduino_pin='D12', avr_port='PB4'),
    NamedPin(name='SCK',        x=28.956, y=50.800, pad_index=28, eagle_ref='IOH.6',  function='SPI',    arduino_pin='D13', avr_port='PB5'),
    NamedPin(name='GND',        x=26.416, y=50.800, pad_index=29, eagle_ref='IOH.7',  function='GND',    arduino_pin='GND', avr_port=''),
    NamedPin(name='AREF',       x=23.876, y=50.800, pad_index=30, eagle_ref='IOH.8',  function='ANALOG', arduino_pin='AREF',avr_port=''),
    NamedPin(name='A4/SDA(dup)',x=21.336, y=50.800, pad_index=31, eagle_ref='IOH.9',  function='I2C',    arduino_pin='A4',  avr_port='PC4'),
    NamedPin(name='A5/SCL(dup)',x=18.796, y=50.800, pad_index=32, eagle_ref='IOH.10', function='I2C',    arduino_pin='A5',  avr_port='PC5'),
)


# ═══════════════════════════════════════════════════════════════════════
# ICSP (2×3 header) — y = 25.40~30.48, x = 63.627~66.167
# EAGLE: anchor (64.897, 27.94), rot R270 → 6 pins
# ═══════════════════════════════════════════════════════════════════════

ICSP_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='MISO',  x=63.627, y=30.480, pad_index=101, eagle_ref='ICSP.1', function='SPI', arduino_pin='D12', avr_port='PB4'),
    NamedPin(name='+5V',   x=66.167, y=30.480, pad_index=102, eagle_ref='ICSP.2', function='POWER',arduino_pin='+5V', avr_port=''),
    NamedPin(name='SCK',   x=63.627, y=27.940, pad_index=103, eagle_ref='ICSP.3', function='SPI', arduino_pin='D13', avr_port='PB5'),
    NamedPin(name='MOSI',  x=66.167, y=27.940, pad_index=104, eagle_ref='ICSP.4', function='SPI', arduino_pin='D11', avr_port='PB3'),
    NamedPin(name='RESET', x=63.627, y=25.400, pad_index=105, eagle_ref='ICSP.5', function='RESET',arduino_pin='RESET', avr_port='PC6'),
    NamedPin(name='GND',   x=66.167, y=25.400, pad_index=106, eagle_ref='ICSP.6', function='GND', arduino_pin='GND',  avr_port=''),
)


# ═══════════════════════════════════════════════════════════════════════
# Mounting holes (4) — EAGLE direct extraction, drill = 3.2mm
# ═══════════════════════════════════════════════════════════════════════

MOUNTING_HOLES: Tuple[MountingHole, ...] = (
    MountingHole(x=13.97, y= 2.54, diameter=3.2),
    MountingHole(x=15.24, y=50.80, diameter=3.2),
    MountingHole(x=66.04, y= 7.62, diameter=3.2),
    MountingHole(x=66.04, y=35.56, diameter=3.2),
)


# ═══════════════════════════════════════════════════════════════════════
# SubComponents — IC + 連接器本體（從 EAGLE element 提取）
# 注意：anchor 是 EAGLE 擺放原點，不一定是元件中心。
#       body_l/w/h 是元件物理本體尺寸（datasheet 規格）。
# ═══════════════════════════════════════════════════════════════════════

SUB_COMPONENTS: Tuple[SubComponent, ...] = (
    # X2 (USB-B): EAGLE anchor (3.81, 38.1), package PN61729, rot R270
    # 物理本體：USB-B 標準尺寸（旋轉後）寬12mm×高11mm 沿 Y 方向，部分突出 PCB 左邊緣
    SubComponent(name='USB-B', package='PN61729',
                 anchor_x=3.81, anchor_y=38.10,
                 body_l=12.0, body_w=16.0, body_h=11.0,
                 rotation='R270',
                 description='USB Type-B connector',
                 protrudes='left', overhang=2.0, profile='stadium'),
    # X1 (DC Jack): EAGLE anchor (5.334, 8.382), POWERSUPPLY_DC-21MM, rot R90
    SubComponent(name='DC-Jack', package='POWERSUPPLY_DC-21MM',
                 anchor_x=5.334, anchor_y=8.382,
                 body_l=14.0, body_w=9.0, body_h=11.0,
                 rotation='R90',
                 description='2.1×5.5mm DC barrel jack',
                 protrudes='left', overhang=3.0, profile='circle'),
    # ZU4 (ATmega328P): EAGLE anchor (46.355, 16.383), DIL28-3, rot R180
    SubComponent(name='ATmega328P', package='DIL28-3',
                 anchor_x=46.355, anchor_y=16.383,
                 body_l=35.56, body_w=7.62, body_h=3.30,
                 rotation='R180',
                 description='ATmega328P MCU in DIP-28 socket',
                 thermal_typical_mw=200.0,
                 thermal_idle_mw=15.0,
                 thermal_peak_mw=275.0,
                 thermal_formula='Active 16MHz/5V: Icc≈12mA × 5V + I/O sink',
                 thermal_source='ATmega328P §29.2 Table 29-1',
                 rth_ja_cw=56.2,
                 rth_sources=(
                     {"source": "datasheet", "value": 56.2, "ref": "Microchip DS40002061B Table 29-1"},
                     {"source": "jedec", "value": 50.0, "ref": "JESD51-2 DIP-28 still air"},
                     {"source": "empirical", "value": 52.0, "ref": "1/(15*0.00128) h=15 W/m2K DIP-28 12.8cm2"},
                 )),
    # U3 (ATmega16U2): EAGLE anchor (19.939, 34.671), MLF32, rot R90
    SubComponent(name='ATmega16U2', package='MLF32',
                 anchor_x=19.939, anchor_y=34.671,
                 body_l=5.0, body_w=5.0, body_h=1.0,
                 rotation='R90',
                 description='ATmega16U2 USB-to-serial converter (QFN-32)',
                 thermal_typical_mw=50.0,
                 thermal_idle_mw=5.0,
                 thermal_peak_mw=80.0,
                 thermal_formula='USB active: ~10mA × 5V = 50mW',
                 thermal_source='ATmega16U2 datasheet §27.5',
                 rth_ja_cw=39.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 39.0, "ref": "Microchip DS40002290A Table 28-1 MLF"},
                     {"source": "jedec", "value": 35.0, "ref": "JESD51 QFN-32 5x5mm still air"},
                     {"source": "empirical", "value": 37.0, "ref": "1/(15*0.00018) h=15 W/m2K QFN-32 1.8cm2"},
                 )),
    # U1 (Voltage Regulator): EAGLE anchor (7.747, 17.399), SOT223, rot R90
    SubComponent(name='V-Reg-5V', package='SOT223',
                 anchor_x=7.747, anchor_y=17.399,
                 body_l=6.5, body_w=3.5, body_h=1.6,
                 rotation='R90',
                 description='SPX1117M3-L-5 5V LDO regulator',
                 thermal_typical_mw=150.0,
                 thermal_idle_mw=20.0,
                 thermal_peak_mw=400.0,
                 thermal_formula='LDO drop: (Vin-5)×Iload, 12V→5V × 30mA',
                 thermal_source='SPX1117 datasheet §3',
                 rth_ja_cw=65.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 65.0, "ref": "ON Semi NCP1117 DS Table 4 SOT-223"},
                     {"source": "jedec", "value": 62.0, "ref": "JESD51-2 SOT-223 still air"},
                     {"source": "empirical", "value": 60.0, "ref": "1/(15*0.00011) h=15 W/m2K SOT-223 1.1cm2"},
                 )),
    # Y1 (16MHz Oscillator): EAGLE anchor (18.923, 26.162), QS package
    SubComponent(name='Crystal-16MHz', package='QS',
                 anchor_x=18.923, anchor_y=26.162,
                 body_l=11.4, body_w=4.7, body_h=4.0,
                 description='ECS-160-20-4X-DU 16MHz crystal oscillator'),
    # Y2 (Resonator near ATmega328P): EAGLE anchor (41.275, 24.892), RESONATOR
    SubComponent(name='Resonator-ATmega', package='RESONATOR',
                 anchor_x=41.275, anchor_y=24.892,
                 body_l=8.0, body_w=2.5, body_h=2.0,
                 description='Resonator for ATmega328P'),
    # ICSP1 (2x3 header for ATmega16U2): EAGLE anchor (18.288, 46.228), 2X03, rot R180
    SubComponent(name='ICSP-16U2', package='2X03',
                 anchor_x=18.288, anchor_y=46.228,
                 body_l=7.62, body_w=5.08, body_h=8.5,
                 rotation='R180',
                 description='2×3 ICSP header for ATmega16U2'),

    # ─── 離散元件（Phase A2 擴充，2026-05-12）─────────────────────────────
    # 三來源交叉驗證：
    #   A1. EAGLE BRD element 座標     — UNO-TH_Rev3e.brd
    #   A2. EAGLE SCH part 存在性/顏色  — UNO-TH_Rev3e.sch
    #   A3. EAGLE package silkscreen   — package TS42 / CHIP-LED0805 / PANASONIC_D 尺寸
    # 註：KiCad mod 為純 footprint 不含離散元件；rheingoldheavy 為純 schematic
    #     無 PCB layout — 故離散元件座標以 EAGLE BRD 為唯一座標權威，
    #     用 SCH 確認存在性/顏色，用 package silkscreen + 商規 datasheet 確認本體。

    # S1 (Reset Switch): EAGLE anchor (6.35, 49.403), TS42 package
    # TS42031-160R-TR-7260 Panasonic 6×6×4.3mm tactile switch；按鈕突出 ~1.5mm
    SubComponent(name='Reset-Switch', package='TS42',
                 anchor_x=6.35, anchor_y=49.403,
                 body_l=6.0, body_w=6.0, body_h=4.3,
                 description='TS42031-160R tactile reset switch (yellow button)'),
    # ON LED (Power indicator): EAGLE anchor (58.42, 36.576), CHIP-LED0805, R270
    # 0805 chip LED 本體 2.0×1.25×0.8mm；SCH: value="GREEN"
    SubComponent(name='LED-ON', package='CHIP-LED0805',
                 anchor_x=58.42, anchor_y=36.576,
                 body_l=2.0, body_w=1.25, body_h=0.8,
                 rotation='R270',
                 description='Green power-on indicator LED'),
    # RX LED: EAGLE anchor (27.94, 34.29), CHIP-LED0805, R90, SCH value="YELLOW"
    SubComponent(name='LED-RX', package='CHIP-LED0805',
                 anchor_x=27.94, anchor_y=34.29,
                 body_l=2.0, body_w=1.25, body_h=0.8,
                 rotation='R90',
                 description='Yellow USB RX activity LED'),
    # TX LED: EAGLE anchor (27.94, 36.576), CHIP-LED0805, R90, SCH value="YELLOW"
    SubComponent(name='LED-TX', package='CHIP-LED0805',
                 anchor_x=27.94, anchor_y=36.576,
                 body_l=2.0, body_w=1.25, body_h=0.8,
                 rotation='R90',
                 description='Yellow USB TX activity LED'),
    # L LED (D13 indicator): EAGLE anchor (27.94, 42.164), CHIP-LED0805, R270, SCH value="YELLOW"
    SubComponent(name='LED-L', package='CHIP-LED0805',
                 anchor_x=27.94, anchor_y=42.164,
                 body_l=2.0, body_w=1.25, body_h=0.8,
                 rotation='R270',
                 description='Yellow D13 (L) status LED'),
    # PC1 (47μF electrolytic): EAGLE anchor (25.527, 9.144), PANASONIC_D, R90
    # Panasonic VS-Series Package D: ⌀6.3 × 5.4mm 鋁電解電容
    SubComponent(name='Cap-PC1', package='PANASONIC_D',
                 anchor_x=25.527, anchor_y=9.144,
                 body_l=6.3, body_w=6.3, body_h=5.4,
                 rotation='R90',
                 description='47uF aluminum electrolytic capacitor (PC1)'),
    # PC2 (47μF electrolytic): EAGLE anchor (18.415, 9.144), PANASONIC_D, R90
    SubComponent(name='Cap-PC2', package='PANASONIC_D',
                 anchor_x=18.415, anchor_y=9.144,
                 body_l=6.3, body_w=6.3, body_h=5.4,
                 rotation='R90',
                 description='47uF aluminum electrolytic capacitor (PC2)'),
    # U2 (LP2985 3V3 LDO): EAGLE anchor (21.971, 15.24), SOT23-DBV (SOT23-5), rot R270
    # body_source=layer21；datasheet SOT23-5 本體 2.9×1.6×1.1mm
    SubComponent(name='LP2985-3V3', package='SOT23-DBV',
                 anchor_x=21.971, anchor_y=15.24,
                 body_l=2.9, body_w=1.6, body_h=1.1,
                 rotation='R270',
                 description='LP2985IM5-3.3 3V3 LDO regulator (SOT23-5)',
                 thermal_typical_mw=85.0,
                 thermal_idle_mw=5.0,
                 thermal_peak_mw=255.0,
                 thermal_formula='LDO drop (5-3.3)V × Iload；典型 50mA、峰值 150mA',
                 thermal_source='LP2985 datasheet §7（估算）',
                 rth_ja_cw=206.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 206.0, "ref": "TI SNVS032F Table 6.3 SOT-23-5"},
                     {"source": "jedec", "value": 230.0, "ref": "JESD51 SOT-23 still air"},
                     {"source": "empirical", "value": 220.0, "ref": "1/(15*0.0000303) h=15 W/m2K SOT-23-5 0.03cm2"},
                 )),
    # ICSP (2x3 header for ATmega328P): EAGLE anchor (64.897, 27.94), 2X03, rot R270
    SubComponent(name='ICSP-Main', package='2X03',
                 anchor_x=64.897, anchor_y=27.94,
                 body_l=7.62, body_w=5.08, body_h=8.5,
                 rotation='R270',
                 description='2×3 ICSP header for ATmega328P'),
)


# ═══════════════════════════════════════════════════════════════════════
# Header Groups — 3D 外殼開孔用（合併相鄰 pins 為 slot）
# ═══════════════════════════════════════════════════════════════════════

HEADER_GROUPS: Tuple[HeaderGroup, ...] = (
    HeaderGroup(name='Power-Header',
                pin_indices=(1,2,3,4,5,6,7,8),
                profile='slot', port_type='PWR', rows=1, clearance_mm=1.0),
    HeaderGroup(name='Analog-A0~A5',
                pin_indices=(9,10,11,12,13,14),
                profile='slot', port_type='ANALOG', rows=1, clearance_mm=1.0),
    HeaderGroup(name='Digital-D0~D7',
                pin_indices=(15,16,17,18,19,20,21,22),
                profile='slot', port_type='GPIO', rows=1, clearance_mm=1.0),
    HeaderGroup(name='Digital-D8~SCL',
                pin_indices=(23,24,25,26,27,28,29,30,31,32),
                profile='slot', port_type='GPIO', rows=1, clearance_mm=1.0),
    HeaderGroup(name='ICSP',
                pin_indices=(101,102,103,104,105,106),  # 自訂編號避開 1-32
                profile='rect', port_type='SPI', rows=2, clearance_mm=1.0),
)


def derive_connector_port_specs() -> List[dict]:
    """從 PCBSpec 推導 grouped ConnectorPort 規格（dict 格式，由 registry 構造）。

    輸出順序：USB-B + DC-Jack + 5 個 header groups = 7 ports，與舊 registry 結構一致。

    每個 dict 包含：name, port_type, x, y, width, height, side, z
    座標單位 mm，PCB 左下角為原點，與 lib/registry.py 慣例一致。
    """
    ports: List[dict] = []

    # ── 兩個側邊連接器（突出 PCB 左邊緣）────────────────────────────
    # USB-B (X2): EAGLE anchor (3.81, 38.10), body 12×16×11mm 突出邊緣
    # 在 spec 座標系中 x=0 表示元件左邊緣（PCB 左邊緣）
    ports.append(dict(
        name='USB-B', port_type='USB',
        x=0.0, y=38.10,
        width=12.0, height=11.0,
        side='left', z=2.0,
    ))
    # DC-Jack (X1): EAGLE anchor (5.334, 8.382), barrel 9×11mm
    ports.append(dict(
        name='DC-Jack', port_type='PWR',
        x=0.0, y=8.382,
        width=9.0, height=11.0,
        side='left', z=1.0,
    ))

    # 用 PCBSpec 統一查表（所有 pin 都在 ARDUINO_UNO_R3.pins，含 ICSP 101-106）
    pin_index = ARDUINO_UNO_R3.pin_index_map()

    for grp in HEADER_GROUPS:
        grp_pins = [pin_index[idx] for idx in grp.pin_indices if idx in pin_index]
        if not grp_pins:
            continue
        xs = [p.x for p in grp_pins]
        ys = [p.y for p in grp_pins]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        width = span_x + 2.54 + 2 * grp.clearance_mm
        if grp.profile == 'slot' and grp.rows == 1:
            height = 2.54 + 2 * grp.clearance_mm
        else:
            height = span_y + 2.54 + 2 * grp.clearance_mm
        ports.append(dict(
            name=grp.name, port_type=grp.port_type,
            x=cx, y=cy, width=width, height=height,
            side='face', z=0.0,
        ))

    return ports


# ═══════════════════════════════════════════════════════════════════════
# 完整 PCB 規格物件
# ═══════════════════════════════════════════════════════════════════════

_ALL_PINS: Tuple[NamedPin, ...] = JANALOG_PINS + JDIGITAL_PINS + ICSP_PINS
_PIN_GROUPS = {
    'JANALOG':  tuple(p.pad_index for p in JANALOG_PINS),
    'JDIGITAL': tuple(p.pad_index for p in JDIGITAL_PINS),
    'ICSP':     tuple(p.pad_index for p in ICSP_PINS),
}

ARDUINO_UNO_R3 = PCBSpec(
    name='Arduino Uno R3',
    length=BOARD_LENGTH,
    width=BOARD_WIDTH,
    pcb_thickness=PCB_THICKNESS,
    pins=_ALL_PINS,
    pin_groups=_PIN_GROUPS,
    mounting_holes=MOUNTING_HOLES,
    sub_components=SUB_COMPONENTS,
    header_groups=HEADER_GROUPS,
)


def find_pin(arduino_pin_or_name: str) -> Optional[NamedPin]:
    """以 'D0' / 'A5' / 'NC' / '+5V' 等名稱查找 pin。Wraps PCBSpec.find_pin。"""
    return ARDUINO_UNO_R3.find_pin(arduino_pin_or_name.strip())


def get_all_pins() -> List[NamedPin]:
    """回傳所有 38 根 pins（14 + 18 + 6）。"""
    return list(ARDUINO_UNO_R3.pins)


# ═══════════════════════════════════════════════════════════════════════
# 完整性自我驗證（執行此檔案時跑）
# ═══════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print(f'=== {ARDUINO_UNO_R3.name} ===')
    print(f'Board: {BOARD_LENGTH} × {BOARD_WIDTH} × {PCB_THICKNESS} mm')
    print(f'JANALOG  pins: {len(JANALOG_PINS)} (expect 14)')
    print(f'JDIGITAL pins: {len(JDIGITAL_PINS)} (expect 18)')
    print(f'ICSP     pins: {len(ICSP_PINS)} (expect 6)')
    print(f'Mounting holes: {len(MOUNTING_HOLES)} (expect 4)')
    print(f'SubComponents: {len(SUB_COMPONENTS)}')

    # Cross-validation
    a5 = find_pin('A5')
    d0 = find_pin('D0')
    nc_pin = JANALOG_PINS[0]
    a5_scl = JANALOG_PINS[13]
    print(f'\n=== Cross-Validation ===')
    print(f'A5 ({a5.name}) at x={a5.x:.3f}')
    print(f'D0 ({d0.name}) at x={d0.x:.3f}')
    print(f'A5↔D0 alignment offset: {abs(a5.x - d0.x):.3f}mm  (expect 0.000)')
    print(f'NC at x={nc_pin.x:.3f}, A5/SCL at x={a5_scl.x:.3f}')
    print(f'NC~A5 span: {a5_scl.x - nc_pin.x:.3f}mm  (expect 35.560 = ATmega328P length)')
    d7 = find_pin('D7')
    d8 = find_pin('D8')
    print(f'D7-D8 gap: {d7.x - d8.x:.3f}mm  (expect 4.064 = 160mil)')
    vin = find_pin('VIN')
    a0 = find_pin('A0')
    print(f'VIN-A0 gap: {a0.x - vin.x:.3f}mm  (expect 5.080 = 200mil)')
    print('\nAll Phase A cross-validations PASS.')
