"""lib/cad/pcb_sensors.py — 感測器模組 PCB 3D 模型（build123d）。

六種常見教育用感測器的 PCB body 模型：
  1. Sensor-TempHumid-class   — DHT11 溫濕度
  2. Sensor-Ultrasonic-class  — HC-SR04 超音波
  3. Sensor-PIR-class         — HC-SR501 PIR 人體紅外
  4. Sensor-SoilMoisture-class — 電容式土壤濕度
  5. Sensor-Light-class       — LDR 光敏電阻模組
  6. Sensor-IR-class          — FC-51 紅外避障

座標系：中心原點 (0,0)，Z 向上，PCB 表面 = Z=thickness。
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib.cad.pcb_common import (  # noqa: E402
    box, cyl, add, make_pcb_board, add_pin_header,
    add_smd_ic, add_trimpot, add_led, export_pcb,
    PCB_BLUE, PCB_GREEN, METAL, BLACK, IC_DARK, PIN_GOLD,
    LED_GREEN, LED_RED, LED_BLUE, LED_YELLOW, WHITE,
    DOME_WHITE, GOLD_TRACE, TRIMPOT_BLUE, BROWN, CRYSTAL,
)
import build123d as bd  # noqa: E402

PITCH = 2.54  # 標準 2.54mm 排針間距


# =====================================================================
# 1. DHT11 溫濕度感測器 (25.1×15.1×7.7mm)
# =====================================================================
def build_temp_humid_pcb_body() -> bd.Compound:
    """DHT11 溫濕度模組 — 白色自封裝 + 小載板。"""
    parts: list[bd.Solid] = []
    T = 1.0  # 載板厚度

    # 載板 PCB（薄小藍板）
    pcb = make_pcb_board(25.1, 15.1, T, PCB_BLUE, "CarrierPCB")
    parts.append(pcb)

    # 白色塑膠本體 (居中，坐在載板上方) — SSOT bodyW=21 × bodyD=8.5
    add(parts, box(0, 0, T + 7.2 / 2, 21.0, 8.5, 7.2),
        DOME_WHITE, "DHT22_Body")

    # 感測柵格 — 前面凹陷的訊號柵格（DHT 招牌特徵）
    # SSOT Sensing_Grid 17×4，淡藍灰色 #a0c8f0，與白色本體明顯區隔
    GRID_BLUE = bd.Color(0.627, 0.784, 0.941)  # #a0c8f0
    add(parts, box(0, 8.5 / 2 - 0.5, T + 7.2 / 2, 17.0, 1.0, 4.0),
        GRID_BLUE, "Sensing_Grid")

    # 4 根金色引腳（向下穿過載板）
    x_start = -1.5 * PITCH
    for i in range(4):
        px = x_start + i * PITCH
        add(parts, cyl(px, 0, -5.0 / 2, 0.25, 5.0),
            PIN_GOLD, f"Pin_{i}")

    return bd.Compound(children=parts, label="Sensor-TempHumid-class")


# =====================================================================
# 2. HC-SR04 超音波感測器 (45×20×15mm)
# =====================================================================
def build_ultrasonic_pcb_body() -> bd.Compound:
    """HC-SR04 超音波測距模組。"""
    parts: list[bd.Solid] = []
    T = 1.2

    pcb = make_pcb_board(45, 20, T, PCB_BLUE, "PCB")
    parts.append(pcb)

    # 兩個超音波換能器 — 圓柱，中心間距 26mm
    for sign in (-1, 1):
        cx = sign * 13.0
        add(parts, cyl(cx, 0, T + 12.0 / 2, 8.0, 12.0),
            METAL, f"Transducer_{'L' if sign < 0 else 'R'}")

    # 石英振盪器 — 兩換能器之間
    add(parts, box(0, 0, T + 1.5 / 2, 5.0, 2.0, 1.5),
        CRYSTAL, "CrystalOsc")

    # 接收 IC — SOIC-8
    add_smd_ic(parts, 0, -5.0, T, 5.0, 4.0, 1.5, "ReceiverIC")

    # 4-pin 排針 (-Y 短邊)
    pins = [(-1.5 * PITCH + i * PITCH, -9.0) for i in range(4)]
    add_pin_header(parts, T, pins, "Hdr4", is_male=True)

    return bd.Compound(children=parts, label="Sensor-Ultrasonic-class")


# =====================================================================
# 3. HC-SR501 PIR 人體紅外感測器 (⌀32mm, 高 25mm)
# =====================================================================
def build_pir_pcb_body() -> bd.Compound:
    """HC-SR501 圓形 PIR 感測模組。"""
    parts: list[bd.Solid] = []
    T = 1.2

    # 圓形 PCB（用圓柱模擬）
    add(parts, cyl(0, 0, T / 2, 16.0, T), PCB_GREEN, "PCB_Round")

    # 白色菲涅爾透鏡罩 — 圓潤半球穹頂（SSOT dome ⌀23），取代原平頂瓶蓋雙圓柱
    # 圓柱裙座 + 上半球冠（整球減去下半部 → 平底貼合裙座頂面）
    DOME_R = 11.5          # ⌀23mm
    SKIRT_H = 1.5          # 裙座高度
    add(parts, cyl(0, 0, T + SKIRT_H / 2, DOME_R, SKIRT_H),
        DOME_WHITE, "FresnelDome_Skirt")
    skirt_top = T + SKIRT_H
    with bd.BuildPart() as _dome_bp:
        with bd.Locations(bd.Location((0, 0, skirt_top))):
            bd.Sphere(DOME_R)
        # 削去赤道以下半球，使穹頂平底坐落於裙座頂面
        with bd.Locations(bd.Location((0, 0, skirt_top - DOME_R))):
            bd.Box(2 * DOME_R + 2, 2 * DOME_R + 2, 2 * DOME_R,
                   mode=bd.Mode.SUBTRACT)
    _dome = _dome_bp.part
    add(parts, _dome, DOME_WHITE, "FresnelDome_Cap")

    # BISS0001 IC — DIP-8
    add(parts, box(-4.0, -3.0, T + 3.0 / 2, 10.0, 6.0, 3.0),
        IC_DARK, "BISS0001")

    # 2 個微調電位器（內縮至 x=-8，留在 ⌀32 圓板內）
    add_trimpot(parts, -8.0, 6.0, T, "TrimPot_Sens")
    add_trimpot(parts, -8.0, -6.0, T, "TrimPot_Time")

    # 3-pin 排針（底部邊緣 -Y 側）
    pins = [(-PITCH, -14.0), (0, -14.0), (PITCH, -14.0)]
    add_pin_header(parts, T, pins, "Hdr3_Out", is_male=True)

    # 跳線排針 — 3-pin 沿底部邊緣（3 根座標各異，y=-12 完全避開 ⌀23 透鏡罩，且留在 ⌀32 板內）
    jmp_pins = [(4.0 + i * PITCH, -12.0) for i in range(3)]
    add_pin_header(parts, T, jmp_pins, "Jumper", is_male=True)

    return bd.Compound(children=parts, label="Sensor-PIR-class")


# =====================================================================
# 4. 電容式土壤濕度感測器 (98×23×3.5mm)
# =====================================================================
def build_soil_moisture_pcb_body() -> bd.Compound:
    """電容式土壤濕度感測模組 — 長條形。"""
    parts: list[bd.Solid] = []
    T = 1.0

    # 安裝孔依 SSOT verified.json（x=3,y=3,d=2）→ 中心原點換算 (3-49, 3-11.5) = (-46,-8.5)
    pcb = make_pcb_board(98, 23, T, PCB_BLUE, "PCB",
                         holes=[(-46.0, -8.5, 1.0)])  # 安裝孔 ⌀2mm
    parts.append(pcb)

    # 金色交指電極 — 10 條水平金色軌跡（探針區）
    for i in range(10):
        y_off = -9.0 + i * 2.0
        add(parts, box(10.0, y_off, T + 0.04 / 2, 55.0, 1.5, 0.04),
            GOLD_TRACE, f"Trace_{i}")

    # NE555 / 比較器 IC — 控制端（-X 側）
    add_smd_ic(parts, -38.0, 0, T, 4.0, 4.0, 1.5, "NE555")

    # 電容
    add(parts, box(-32.0, 5.0, T + 1.0 / 2, 2.0, 2.0, 1.0),
        BROWN, "Capacitor")

    # 3-pin 排針（-X 端）
    pins = [(-46.0, -PITCH), (-46.0, 0), (-46.0, PITCH)]
    add_pin_header(parts, T, pins, "Hdr3", is_male=True)

    return bd.Compound(children=parts, label="Sensor-SoilMoisture-class")


# =====================================================================
# 5. LDR 光敏電阻模組 (30×15×7mm)
# =====================================================================
def build_light_sensor_pcb_body() -> bd.Compound:
    """LDR 光敏電阻模組。"""
    parts: list[bd.Solid] = []
    T = 1.0

    pcb = make_pcb_board(30, 15, T, PCB_BLUE, "PCB")
    parts.append(pcb)

    # LDR 光敏電阻 — CdS 元件（中心偏右）
    add(parts, cyl(5.0, 0, T + 2.5 / 2, 2.5, 2.5),
        BROWN, "LDR_Body")

    # LDR 頂部玻璃窗
    add(parts, cyl(5.0, 0, T + 2.5 + 0.3 / 2, 2.0, 0.3),
        LED_YELLOW, "LDR_Window")

    # LM393 比較器 IC — SOIC-8（中心偏左）
    add_smd_ic(parts, -5.0, 0, T, 4.0, 5.0, 1.5, "LM393")

    # 微調電位器 — LDR 與 IC 之間
    add_trimpot(parts, 0, 0, T, "TrimPot")

    # 電源指示 LED（綠色，靠近排針）
    add_led(parts, -12.0, 3.0, T, LED_GREEN, "PowerLED")

    # 4-pin 排針（-X 短邊）
    pins = [(-13.0, -1.5 * PITCH + i * PITCH) for i in range(4)]
    add_pin_header(parts, T, pins, "Hdr4", is_male=True)

    return bd.Compound(children=parts, label="Sensor-Light-class")


# =====================================================================
# 6. FC-51 紅外避障感測器 (32×14×10mm)
# =====================================================================
def build_ir_sensor_pcb_body() -> bd.Compound:
    """FC-51 紅外避障模組。"""
    parts: list[bd.Solid] = []
    T = 1.0

    # 安裝孔依 SSOT verified.json（x=3,y=7,d=3）→ 中心原點換算 (3-16, 7-7) = (-13,0)
    pcb = make_pcb_board(32, 14, T, PCB_BLUE, "PCB",
                         holes=[(-13.0, 0.0, 1.5)])  # 安裝孔 ⌀3mm

    parts.append(pcb)

    # IR LED 發射器（+X 端，淡藍色）
    IR_LIGHT = bd.Color(0.40, 0.55, 0.90)  # 淡藍透明感
    add(parts, cyl(12.0, 0, T + 5.0 / 2, 1.5, 5.0),
        IR_LIGHT, "IR_LED_TX")

    # IR 光電晶體 接收器（黑色，間距 6mm）
    add(parts, cyl(6.0, 0, T + 5.0 / 2, 1.5, 5.0),
        BLACK, "IR_Phototransistor_RX")

    # LM393 比較器 IC — SOIC-8
    add_smd_ic(parts, -2.0, 0, T, 4.0, 5.0, 1.5, "LM393")

    # 微調電位器
    add_trimpot(parts, -8.0, 4.0, T, "TrimPot")

    # 電源指示 LED（綠色）
    add_led(parts, -8.0, -4.0, T, LED_GREEN, "PowerLED")

    # 3-pin 排針（-X 端）
    pins = [(-14.0, -PITCH), (-14.0, 0), (-14.0, PITCH)]
    add_pin_header(parts, T, pins, "Hdr3", is_male=True)

    return bd.Compound(children=parts, label="Sensor-IR-class")


# =====================================================================
# CLI — 批次建構並匯出
# =====================================================================
if __name__ == "__main__":
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    for cls_name, builder in [
        ("Sensor-TempHumid-class", build_temp_humid_pcb_body),
        ("Sensor-Ultrasonic-class", build_ultrasonic_pcb_body),
        ("Sensor-PIR-class", build_pir_pcb_body),
        ("Sensor-SoilMoisture-class", build_soil_moisture_pcb_body),
        ("Sensor-Light-class", build_light_sensor_pcb_body),
        ("Sensor-IR-class", build_ir_sensor_pcb_body),
    ]:
        print(f"[pcb] Building {cls_name} ...")
        compound = builder()
        export_pcb(compound, str(ROOT / "shells" / cls_name), cls_name)
        bb = compound.bounding_box()
        print(f"  BBox: {bb.max.X - bb.min.X:.1f}"
              f"×{bb.max.Y - bb.min.Y:.1f}"
              f"×{bb.max.Z - bb.min.Z:.1f}mm")
