"""lib/cad/pcb_peripherals.py -- 周邊模組 PCB 3D 模型（build123d）。

8 種周邊模組：Relay / OLED / LCD / E-Ink / LED Matrix / MP3 / Joystick / Car Chassis。
所有幾何中心原點，使用 pcb_common 共用工具。
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from lib.cad.pcb_common import (
    box, cyl, add, make_pcb_board, add_pin_header, add_smd_ic,
    add_trimpot, add_led, export_pcb,
    PCB_BLUE, PCB_GREEN, PCB_RED, PCB_BLACK, METAL, METAL_DARK,
    BLACK, IC_DARK, PIN_GOLD, LED_GREEN, LED_RED, LED_BLUE, WHITE,
    RELAY_BLUE, DISPLAY_DARK, DISPLAY_GRAY, BROWN, RUBBER_BLACK,
    ACRYLIC, CONNECTOR_WHT, SHIELD_TIN, USB_SILVER, GOLD_TRACE,
)
import build123d as bd


# =====================================================================
# 1. Relay Module (50x26x19mm, PCB_BLUE)
# =====================================================================
def build_relay_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 1.0  # board thickness

    # PCB
    parts.append(make_pcb_board(50, 26, pz, PCB_BLUE, "Relay_PCB"))

    # Relay body -- shifted left so it clears the +X screw terminals (was x=8,
    # span -1.5..17.5, overlapped terminals at 15..20). Now cx=-2 → span -11.5..7.5
    # (+X edge 7.5 < 15). Taller can (dz 15.5→18) to read like real SRD-05VDC.
    relay_navy = bd.Color(0.118, 0.227, 0.373)  # #1e3a5f
    add(parts, box(-2, 0, pz + 9.0, 19, 15.5, 18), relay_navy, "Relay_Body")
    # Top label stripe (same x as can, sits on raised top: pz + 18 = 19)
    add(parts, box(-2, 0, pz + 18.02, 15, 3, 0.04), WHITE, "Relay_Label")

    # Screw terminal block (3 terminals at +X edge). 5mm pitch → terminal width must be
    # < 5 or the three blocks merge into one (was dy=7 → overlapping; fixed to 4.6).
    tx = 50 / 2 - 7.5
    term_blue = bd.Color(0.133, 0.400, 0.667)  # #2266aa
    for i in range(3):
        ty = -5 + i * 5
        add(parts, box(tx, ty, pz + 4, 5, 4.6, 8), term_blue, f"Terminal_{i}")
        add(parts, cyl(tx, ty, pz + 8.2, 1.2, 0.6), METAL, f"Screw_{i}")

    # Optocoupler DIP-4
    add_smd_ic(parts, -10, 0, pz, 4, 6, 3, "Optocoupler")

    # Transistor SOT-23
    add(parts, box(-4, -6, pz + 0.5, 3, 1.5, 1), IC_DARK, "Transistor")

    # Status LED
    add_led(parts, 2, -10, pz, LED_RED, "Status_LED")

    # Flyback diode
    add(parts, box(0, 6, pz + 0.5, 2, 1, 1), BLACK, "Flyback_Diode")

    # 3-pin header at -X edge
    hx = -50 / 2 + 3
    pins = [(hx, -2.54), (hx, 0), (hx, 2.54)]
    add_pin_header(parts, pz, pins, "IN", is_male=True)

    return bd.Compound(children=parts, label="Relay-Module-class")


# =====================================================================
# 2. OLED Display (27x27x4mm, PCB_BLACK)
# =====================================================================
def build_oled_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 0.8

    parts.append(make_pcb_board(27, 27, pz, PCB_BLACK, "OLED_PCB"))

    # OLED glass -- centered upper area. Shrunk 26x15→22x12 so a PCB border shows
    # (was overhanging the 27x27 board edges).
    add(parts, box(0, 3, pz + 0.75, 22, 12, 1.5), DISPLAY_DARK, "OLED_Glass")

    # Active display area (SSOT 21.7x10.9). Distinct screen tint (#13183a, was
    # near-identical to glass) and raised above glass top with real thickness so
    # it is visible and not z-fighting with the glass.
    active_color = bd.Color(0.075, 0.094, 0.227)  # #13183a
    add(parts, box(0, 3, pz + 1.6, 21.7, 10.9, 0.3), active_color, "OLED_Active")

    # FPC ribbon behind display
    add(parts, box(0, 3, pz - 0.15, 25, 3, 0.3), BROWN, "FPC_Ribbon")

    # 4-pin header at bottom edge
    hy = -27 / 2 + 2
    pins = [(i * 2.54 - 3.81, hy) for i in range(4)]
    add_pin_header(parts, pz, pins, "I2C", is_male=True)

    # Decoupling caps
    add(parts, box(10, -4, pz + 0.25, 1, 0.5, 0.5), BROWN, "Cap_1")
    add(parts, box(10, -6, pz + 0.25, 1, 0.5, 0.5), BROWN, "Cap_2")

    return bd.Compound(children=parts, label="Display-OLED-class")


# =====================================================================
# 3. LCD 16x2 Display (80x36x12mm, PCB_GREEN)
# =====================================================================
def build_lcd_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 1.0

    holes = [(37, 15.5, 1.5), (-37, 15.5, 1.5),
             (37, -15.5, 1.5), (-37, -15.5, 1.5)]
    parts.append(make_pcb_board(80, 36, pz, PCB_GREEN, "LCD_PCB", holes=holes))

    # LCD module metal frame
    add(parts, box(0, 0, pz + 3.5, 71, 24, 7), METAL_DARK, "LCD_Frame")

    # Viewing area
    add(parts, box(0, 0, pz + 7.02, 64.5, 13.8, 0.04), DISPLAY_GRAY, "LCD_Window")

    # 16-pin header at bottom edge
    hy = -36 / 2 + 3
    pins = [(i * 2.54 - 19.05, hy) for i in range(16)]
    add_pin_header(parts, pz, pins, "LCD_16P")

    # Contrast trimpot
    add_trimpot(parts, -35, -12, pz, "Contrast_Pot")

    # Backlight LED
    add_led(parts, 35, -14, pz, LED_GREEN, "Backlight_LED")

    return bd.Compound(children=parts, label="Display-LCD-class")


# =====================================================================
# 4. E-Ink Display (89x38x5mm, PCB_BLACK)
# =====================================================================
def build_eink_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 0.8

    holes = [(40, 16, 1.5), (-40, -16, 1.5)]
    parts.append(make_pcb_board(89, 38, pz, PCB_BLACK, "EInk_PCB", holes=holes))

    # E-Ink panel
    add(parts, box(0, 0, pz + 0.5, 79, 32, 1.0), DISPLAY_GRAY, "EInk_Panel")

    # Active area
    add(parts, box(0, 0, pz + 1.02, 66.9, 29.1, 0.04), WHITE, "EInk_Active")

    # FPC connector at +X short edge
    add(parts, box(89 / 2 - 12, 0, pz + 0.75, 24, 3, 1.5), BROWN, "FPC_Connector")

    # 8-pin header at -X edge
    hx = -89 / 2 + 4
    pins = [(hx, i * 2.54 - 8.89) for i in range(8)]
    add_pin_header(parts, pz, pins, "EInk_HDR", is_male=True)

    return bd.Compound(children=parts, label="Display-EInk-class")


# =====================================================================
# 5. LED Matrix 8x8 with MAX7219 (32x32x13mm, PCB_RED)
# =====================================================================
def build_led_matrix_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 1.0

    parts.append(make_pcb_board(32, 32, pz, PCB_RED, "LEDMatrix_PCB"))

    # LED matrix body -- upper area
    my = 3
    add(parts, box(0, my, pz + 4, 20, 20, 8), LED_RED, "Matrix_Body")

    # 8x8 LED grid on top
    for row in range(8):
        for col in range(8):
            lx = -8.75 + col * 2.5
            ly = my - 8.75 + row * 2.5
            add(parts, cyl(lx, ly, pz + 8.05, 0.5, 0.1), WHITE,
                f"LED_{row}_{col}")

    # MAX7219 DIP-24 below matrix
    add(parts, box(0, -10, pz + 1.5, 28, 6, 3), IC_DARK, "MAX7219")
    add(parts, cyl(-14 + 0.6, -10 + 3 - 0.6, pz + 3.02, 0.25, 0.04),
        WHITE, "MAX7219_Pin1")

    # 5-pin input header at -X
    hx = -32 / 2 + 3
    pins = [(hx, i * 2.54 - 5.08) for i in range(5)]
    add_pin_header(parts, pz, pins, "IN_HDR", is_male=True)

    # 5-pin output header at +X
    hx = 32 / 2 - 3
    pins = [(hx, i * 2.54 - 5.08) for i in range(5)]
    add_pin_header(parts, pz, pins, "OUT_HDR", is_male=True)

    # Decoupling cap + resistor
    add(parts, box(12, -14, pz + 0.3, 1.6, 0.8, 0.6), BROWN, "DecoupCap")
    add(parts, box(9, -14, pz + 0.3, 1.6, 0.8, 0.5), BROWN, "Resistor")

    return bd.Compound(children=parts, label="LED-Matrix-class")


# =====================================================================
# 6. DFPlayer Mini MP3 Module (20.7x20.7x5mm, PCB_BLUE)
# =====================================================================
def build_mp3_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 0.8

    parts.append(make_pcb_board(20.7, 20.7, pz, PCB_BLUE, "MP3_PCB"))

    # Main IC YX5200 QFN
    add_smd_ic(parts, 0, 0, pz, 5, 5, 1, "YX5200")

    # MicroSD card slot -- protruding from -Y edge
    sd_y = -20.7 / 2 + 6
    add(parts, box(0, sd_y, pz + 0.75, 11, 12, 1.5), METAL, "MicroSD_Slot")

    # Gold pads: 2 rows of 8 on left/right edges
    for side in (-1, 1):
        px = side * (20.7 / 2 - 0.75)
        for i in range(8):
            py = -8.89 + i * 2.54
            add(parts, box(px, py, pz + 0.02, 1.5, 1, 0.04),
                GOLD_TRACE, f"Pad_{'+' if side > 0 else '-'}_{i}")

    # Crystal oscillator
    add(parts, box(5, 5, pz + 0.25, 2, 1, 0.5), METAL, "Crystal_Osc")

    # DAC IC
    add_smd_ic(parts, -4, 4, pz, 3, 3, 0.8, "DAC_IC")

    # Decoupling caps
    add(parts, box(6, -2, pz + 0.25, 1, 0.5, 0.5), BROWN, "Cap_D1")
    add(parts, box(-6, -2, pz + 0.25, 1, 0.5, 0.5), BROWN, "Cap_D2")

    return bd.Compound(children=parts, label="MP3-Module-class")


# =====================================================================
# 7. Joystick KY-023 (34x26x32mm, PCB_RED)
# =====================================================================
def build_joystick_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    pz = 1.0

    parts.append(make_pcb_board(34, 26, pz, PCB_RED, "Joystick_PCB"))

    # Mechanism base
    add(parts, box(0, 0, pz + 5, 17, 17, 10), BLACK, "Mechanism_Base")

    # 2 potentiometers (partially hidden by mechanism)
    add(parts, cyl(-7, 0, pz + 1.5, 3.5, 3), METAL_DARK, "Pot_X")
    add(parts, cyl(7, 0, pz + 1.5, 3.5, 3), METAL_DARK, "Pot_Y")

    # Joystick shaft
    add(parts, cyl(0, 0, pz + 10 + 7.5, 2.5, 15), METAL, "Shaft")

    # Mushroom cap
    add(parts, cyl(0, 0, pz + 10 + 15 + 2.5, 5, 5), RUBBER_BLACK, "Cap")

    # Button trace pad for press-to-click
    add(parts, box(0, 0, pz + 0.02, 4, 4, 0.04), GOLD_TRACE, "SW_Pad")

    # 5-pin header at -Y edge
    hy = -26 / 2 + 2
    pins = [(i * 2.54 - 5.08, hy) for i in range(5)]
    add_pin_header(parts, pz, pins, "JOY_HDR", is_male=True)

    return bd.Compound(children=parts, label="Joystick-class")


# =====================================================================
# 8. Robot Car Chassis (200x150x30mm, acrylic plate)
# =====================================================================
def build_chassis_pcb_body() -> bd.Compound:
    parts: list[bd.Shape] = []
    plate_t = 3.0

    # Acrylic plate (reuse make_pcb_board with thickness=3)
    holes = [(90, 65, 1.5), (-90, 65, 1.5),
             (90, -65, 1.5), (-90, -65, 1.5)]
    plate = make_pcb_board(200, 150, plate_t, ACRYLIC, "Chassis_Plate",
                           holes=holes)
    parts.append(plate)

    # Motor mount slot indicators (dark rectangles on sides)
    for sx in (-1, 1):
        mx = sx * (100 - 15)
        add(parts, box(mx, 0, plate_t + 0.02, 30, 15, 0.04),
            BLACK, f"MotorSlot_{'R' if sx > 0 else 'L'}")

    # 4 standoff pillars
    for sx in (-1, 1):
        for sy in (-1, 1):
            add(parts, cyl(sx * 70, sy * 50, plate_t + 12.5, 3, 25),
                METAL, f"Standoff_{sx}_{sy}")

    # Caster wheel mount holes (dark circles at front +Y)
    for sx in (-1, 1):
        add(parts, cyl(sx * 25, 60, plate_t + 0.02, 5, 0.04),
            BLACK, f"CasterHole_{sx}")

    # Battery compartment outline at center-back (-Y)
    add(parts, box(0, -40, plate_t + 0.02, 60, 30, 0.04),
        WHITE, "Battery_Outline")

    return bd.Compound(children=parts, label="Chassis-Car-class")


# =====================================================================
# CLI
# =====================================================================
if __name__ == "__main__":
    import pathlib
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    for cls_name, builder in [
        ("Relay-Module-class", build_relay_pcb_body),
        ("Display-OLED-class", build_oled_pcb_body),
        ("Display-LCD-class", build_lcd_pcb_body),
        ("Display-EInk-class", build_eink_pcb_body),
        ("LED-Matrix-class", build_led_matrix_pcb_body),
        ("MP3-Module-class", build_mp3_pcb_body),
        ("Joystick-class", build_joystick_pcb_body),
        ("Chassis-Car-class", build_chassis_pcb_body),
    ]:
        print(f"[pcb] Building {cls_name} ...")
        compound = builder()
        export_pcb(compound, str(ROOT / "shells" / cls_name), cls_name)
        bb = compound.bounding_box()
        print(f"  BBox: {bb.max.X-bb.min.X:.1f}x"
              f"{bb.max.Y-bb.min.Y:.1f}x"
              f"{bb.max.Z-bb.min.Z:.1f}mm")
