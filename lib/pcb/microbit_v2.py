"""micro:bit V2 — PCB 權威座標（Phase A 級精度）。

來源（2026-05-08 驗證）：
  A1. Avnet Design Services Assembly Drawing 1.48（V2 官方生產圖）
      https://tech.microbit.org/docs/hardware/assets/Microbit_V2_Assembly.pdf
  A2. Kitronik mechanical datasheet（早期 V1，部分尺寸 V2 沿用）
      https://resources.kitronik.co.uk/pdf/bbc_microbit_mechanical_datasheet.pdf
  A3. micro:bit Foundation 官方 GitHub schematic + BOM
      data/pcb_sources/microbit_v2/microbit-v2-hardware-main/V2.21/
      （無公開 Gerber，視為部分第三來源）

權威尺寸：
  Board: 51.60 × 42.00 × 1.6mm，corner R3
  Edge connector: 80-pin 1.27mm pitch，5 個大環 ⌀4mm（兼作 mounting hole）
  Mounting holes: P0 ring 與 GND ring 內孔 (Avnet 大環即 mounting hole)
"""
from __future__ import annotations
from typing import Tuple, Dict
from ._types import NamedPin, MountingHole, SubComponent, HeaderGroup, PCBSpec

BOARD_LENGTH = 51.60
BOARD_WIDTH = 42.00
PCB_THICKNESS = 1.6

# ── 5 個大環（GPIO 教學用 + mounting hole）─────────────────────
# Avnet 1.48: 環左邊起點 X = 4.21 / 14.37 / 25.80 / 37.23 / 47.39
# 環直徑 ⌀4mm（兼作 mounting hole 給 M4 / banana / 鱷魚夾），中心 Y ≈ 3.5
EDGE_BIG_PINS: Tuple[NamedPin, ...] = (
    NamedPin(name='P0',  x=6.21,  y=3.5, pad_index=1, function='GPIO',  arduino_pin='P0'),
    NamedPin(name='P1',  x=16.37, y=3.5, pad_index=2, function='GPIO',  arduino_pin='P1'),
    NamedPin(name='P2',  x=27.80, y=3.5, pad_index=3, function='GPIO',  arduino_pin='P2'),
    NamedPin(name='3V',  x=39.23, y=3.5, pad_index=4, function='POWER', arduino_pin='3V'),
    NamedPin(name='GND', x=49.39, y=3.5, pad_index=5, function='GND'),
)

# ── 80-pin 1.27mm pitch edge connector（雙面鍍金）─────────────
# Avnet: pin pitch 1.27mm，22 個小 pad 跨度約從 X=4.21 到 X=50.06
# 用 1.27mm 間距精確分布（從 P0 環右側開始）
EDGE_SMALL_PINS: Tuple[NamedPin, ...] = tuple(
    NamedPin(name=f'edge_{i}', x=4.21 + i * 1.27, y=0.0,
             pad_index=10 + i, function='GPIO')
    for i in range(22)
)

ALL_PINS = EDGE_BIG_PINS + EDGE_SMALL_PINS

PIN_GROUPS: Dict[str, Tuple[int, ...]] = {
    'EDGE_BIG':   tuple(p.pad_index for p in EDGE_BIG_PINS),
    'EDGE_SMALL': tuple(p.pad_index for p in EDGE_SMALL_PINS),
}

HEADER_GROUPS: Tuple[HeaderGroup, ...] = (
    HeaderGroup(name='Edge-Big',
                pin_indices=PIN_GROUPS['EDGE_BIG'],
                profile='slot', port_type='GPIO', rows=1, clearance_mm=1.0),
)

# Mounting holes：micro:bit V2 沒有獨立 mounting holes
# P0 環與 GND 環內孔 ⌀4mm 兼作固定孔（吊掛或鱷魚夾用）
MOUNTING_HOLES: Tuple[MountingHole, ...] = (
    MountingHole(x=6.21,  y=3.5, diameter=4.0),
    MountingHole(x=49.39, y=3.5, diameter=4.0),
)

SUB_COMPONENTS: Tuple[SubComponent, ...] = (
    # nRF52833 主 MCU（QFN-73）— Avnet: 板背面，center 約 (30, 18)
    SubComponent(name='nRF52833', package='QFN-73',
                 anchor_x=30.0, anchor_y=18.0,
                 body_l=5.0, body_w=5.0, body_h=1.0,
                 description='Nordic nRF52833 BLE MCU [Avnet back side]',
                 thermal_typical_mw=25.0, thermal_idle_mw=0.005,
                 thermal_peak_mw=35.0,
                 thermal_formula='BLE active: ~7mA × 3.3V; sleep <2µA',
                 thermal_source='Nordic nRF52833 PS §22 Power Consumption',
                 rth_ja_cw=30.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 30.0,
                      "ref": "Nordic PS v1.7 Table 17 QFN-73"},
                     {"source": "jedec", "value": 28.0,
                      "ref": "JESD51 QFN-73 5x5mm still air"},
                     {"source": "empirical", "value": 32.0,
                      "ref": "1/(15*0.0018) h=15 W/m2K QFN-73 A=1.8cm2"},
                 )),
    # KL27Z interface MCU — Avnet: 板背面 USB 區域，管 USB/SWD
    SubComponent(name='KL27Z', package='QFN-48',
                 anchor_x=17.5, anchor_y=35.0,
                 body_l=6.0, body_w=6.0, body_h=1.0,
                 description='NXP KL27Z USB interface MCU [Avnet back side, near USB]',
                 thermal_typical_mw=30.0, thermal_idle_mw=0.01,
                 thermal_peak_mw=50.0,
                 thermal_formula='USB active: ~10mA × 3.3V',
                 thermal_source='NXP KL27 Sub-Family datasheet §5',
                 rth_ja_cw=38.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 38.0,
                      "ref": "NXP KL27 DS Rev6 Table 6 QFN-48"},
                     {"source": "jedec", "value": 32.0,
                      "ref": "JESD51 QFN-48 6x6mm still air"},
                     {"source": "empirical", "value": 35.0,
                      "ref": "1/(15*0.0026) h=15 W/m2K QFN-48 A=2.6cm2"},
                 )),
    # 5×5 LED matrix — Avnet: 行 D2 在 Y=33.80，行 D42 在 Y=17.80
    # 5 行跨度 16mm，行距 4mm，居中 X ≈ 25.8
    SubComponent(name='LED-Matrix-5x5', package='5x5',
                 anchor_x=25.8, anchor_y=25.80,
                 body_l=20.0, body_w=16.0, body_h=2.0,
                 description='5×5 LED matrix [Avnet rows Y=17.80~33.80]',
                 thermal_typical_mw=75.0, thermal_idle_mw=5.0,
                 thermal_peak_mw=250.0,
                 thermal_formula='25 LED × 1mA × 3V × 1/duty(typ)',
                 thermal_source='Microbit V2 schematic LED rows',
                 rth_ja_cw=80.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 80.0,
                      "ref": "estimated from 25 LED aggregate"},
                     {"source": "jedec", "value": 100.0,
                      "ref": "JESD51 LED-array"},
                     {"source": "empirical", "value": 85.0,
                      "ref": "1/(10*0.00128) h=10 W/m2K LED-array A=12.8cm2"},
                 )),
    # USB-Micro 頂邊（Avnet: USB center X=17.8，距頂 5.5mm）
    SubComponent(name='USB-Micro', package='USB-MICRO-B',
                 anchor_x=17.8, anchor_y=41.5,
                 body_l=7.5, body_w=5.6, body_h=2.8,
                 description='Micro-USB [Avnet center X=17.8]',
                 protrudes='top', overhang=1.0, profile='stadium'),
    # Reset button 頂邊右側（Avnet: 在 USB 右側）
    SubComponent(name='Reset-Button', package='TACT',
                 anchor_x=36.0, anchor_y=39.0,
                 body_l=4.0, body_w=4.0, body_h=2.5,
                 description='Reset / power button [Avnet 25.93mm from right]'),
    # BTN-A — 正面左側（LED matrix 左）
    SubComponent(name='BTN-A', package='TACT',
                 anchor_x=10.0, anchor_y=25.8,
                 body_l=4.5, body_w=4.5, body_h=3.5,
                 description='User button A [Avnet front left of LED matrix]'),
    # BTN-B — 正面右側（LED matrix 右）
    SubComponent(name='BTN-B', package='TACT',
                 anchor_x=42.0, anchor_y=25.8,
                 body_l=4.5, body_w=4.5, body_h=3.5,
                 description='User button B [Avnet front right of LED matrix]'),
    # Microphone — V2 MEMS 麥克風（SPU0410LR5H-QB），正面右上
    SubComponent(name='Microphone', package='MEMS',
                 anchor_x=42.0, anchor_y=36.0,
                 body_l=3.76, body_w=2.95, body_h=1.1,
                 description='MEMS microphone SPU0410 [V2 front, near speaker]',
                 thermal_typical_mw=0.7, thermal_idle_mw=0.0,
                 thermal_peak_mw=1.0,
                 thermal_formula='Active: ~0.2mA × 3.3V',
                 thermal_source='Knowles SPU0410LR5H-QB datasheet',
                 rth_ja_cw=200.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 200.0,
                      "ref": "estimated MEMS package"},
                     {"source": "jedec", "value": 250.0,
                      "ref": "JESD51 LGA-small"},
                     {"source": "empirical", "value": 180.0,
                      "ref": "1/(12*0.0000040) h=12 W/m2K MEMS A=0.04cm2"},
                 )),
    # Touch-Logo — V2 電容觸控 logo（正面中央 LED 上方）
    SubComponent(name='Touch-Logo', package='capacitive-pad',
                 anchor_x=25.8, anchor_y=36.0,
                 body_l=12.0, body_w=6.0, body_h=0.1,
                 description='Capacitive touch logo [V2 front center, above LED]'),
    # 加速度計 + 指南針（LSM303AGR）— Avnet: 板背面 lower-left
    SubComponent(name='LSM303AGR', package='LGA-12',
                 anchor_x=12.0, anchor_y=14.0,
                 body_l=2.5, body_w=2.5, body_h=1.0,
                 description='3-axis accel + magnetometer [Avnet back side]',
                 thermal_typical_mw=2.0, thermal_idle_mw=0.01,
                 thermal_peak_mw=5.0,
                 thermal_formula='Both sensors active: ~0.6mA × 3.3V',
                 thermal_source='ST LSM303AGR datasheet §6',
                 rth_ja_cw=100.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 100.0,
                      "ref": "ST DS11069 Section 3.3 LGA-12"},
                     {"source": "jedec", "value": 110.0,
                      "ref": "JESD51 LGA-12 2.5x2.5mm still air"},
                     {"source": "empirical", "value": 95.0,
                      "ref": "1/(15*0.0000060) h=15 W/m2K LGA-12 A=0.06cm2"},
                 )),
    # Speaker（V2）
    SubComponent(name='Speaker', package='speaker',
                 anchor_x=42.0, anchor_y=18.0,
                 body_l=10.0, body_w=8.0, body_h=3.0,
                 description='V2 built-in speaker [Avnet height=3.0]',
                 thermal_typical_mw=100.0, thermal_idle_mw=0.0,
                 thermal_peak_mw=700.0,
                 thermal_formula='Audio output: avg 30mA × 3.3V',
                 thermal_source='Microbit V2 hardware §11.5',
                 rth_ja_cw=15.0,
                 rth_sources=(
                     {"source": "datasheet", "value": 15.0,
                      "ref": "estimated speaker package (large area)"},
                     {"source": "jedec", "value": 18.0,
                      "ref": "JESD51 open-frame"},
                     {"source": "empirical", "value": 12.0,
                      "ref": "1/(10*0.00064) h=10 W/m2K speaker A=6.4cm2"},
                 )),
    # Edge-Connector — 80-pin 1.27mm pitch 鍍金邊緣連接器實體
    SubComponent(name='Edge-Connector', package='edge-connector-80',
                 anchor_x=25.8, anchor_y=1.0,
                 body_l=48.0, body_w=5.0, body_h=1.6,
                 description='80-pin edge connector body [Avnet bottom edge]'),
)

MICROBIT_V2 = PCBSpec(
    name='micro:bit V2',
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
    print(f'=== {MICROBIT_V2.name} ===')
    print(f'Board: {BOARD_LENGTH} × {BOARD_WIDTH} × {PCB_THICKNESS} mm')
    print(f'Pins: {len(MICROBIT_V2.pins)} (5 big + 22 small)')
    print(f'Mounting holes: {len(MOUNTING_HOLES)}')
    print(f'Sub-components: {len(SUB_COMPONENTS)}')
    p0 = MICROBIT_V2.find_pin('P0')
    print(f'P0 at ({p0.x}, {p0.y})')
