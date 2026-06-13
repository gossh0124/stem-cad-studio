"""lib/cad/pcb_boards.py — ESP32 / Raspberry Pi / micro:bit PCB 本體模型。

每個 build_*_pcb_body() 回傳 bd.Compound（center-origin，Z up from surface）。
共用輔助全部來自 lib.cad.pcb_common。
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from lib.cad.pcb_common import (        # noqa: E402
    bd, box, cyl, add, make_pcb_board,
    add_pin_header, add_smd_ic, add_led, export_pcb,
    PCB_BLUE, PCB_GREEN, PCB_BLACK,
    METAL, METAL_DARK, BLACK, IC_DARK, PIN_GOLD,
    LED_GREEN, LED_RED, LED_BLUE, WHITE,
    USB_SILVER, SHIELD_TIN, GOLD_TRACE, DOME_WHITE,
)

# =====================================================================
# 1. ESP32-DevKitC V4  (51.4 × 28 × 12 mm)
# =====================================================================

def build_esp32_pcb_body() -> bd.Compound:
    """ESP32-DevKitC V4 (30-pin variant) — 藍色 PCB, WROOM-32 模組.

    Axis convention (matches PCBSpec ESP32-class — long edge = X, width = Y,
    centre-origin: x∈[-L/2,+L/2], y∈[-W/2,+W/2]):
      -X end  = Micro-USB / CP2102 / AMS1117 / EN+BOOT buttons / LEDs
      +X end  = WROOM-32 module (antenna pokes off +X edge)
      Headers run ALONG X at y=±11.4 (matches PCBSpec pin coords:
        Left-Header y_local=2.6 → centred y=-11.4; Right y_local=25.4 → +11.4)

    The previous build rotated everything 90° (headers down the Y axis
    spilling off the 28 mm width, USB on a long side, WROOM almost edge-to-
    edge across the board) — this rewrite aligns with the PCBSpec data so
    Components view and Assembly view show what the real DevKit looks like.
    """
    L, W, T = 51.4, 28.0, 1.6   # ESP32-DevKitC V4 real outline
    pz = T                       # PCB top surface (Z=0 is board bottom)
    parts: list[bd.Solid] = []

    # --- PCB 基板 ---
    parts.append(make_pcb_board(L, W, T, PCB_BLUE, "ESP32_PCB"))

    # --- ESP-WROOM-32 RF 模組 (SHIELD_TIN metal can + shallow top recess) ---
    # Real module: 18 (Y) × 25.5 (X) × 3.1 mm. Long axis along PCB length.
    # SSOT frontend_shape ic-module bodyW=25.5 bodyD=18 bodyH=3.1; can has a
    # stamped lid with a shallow recess (subtract a thinner inner box from top).
    mod_dx, mod_dy, mod_dz = 25.5, 18.0, 3.2
    mod_cx = L / 2 - mod_dx / 2 - 3.0        # leave +X room for antenna stub
    recess_depth = 0.5                        # shallow stamped lid recess
    with bd.BuildPart() as _can:
        with bd.Locations(bd.Location((mod_cx, 0.0, pz + mod_dz / 2))):
            bd.Box(mod_dx, mod_dy, mod_dz)
        # recess: inner box cut from the top face, leaving a ~1mm rim
        with bd.Locations(bd.Location(
                (mod_cx, 0.0, pz + mod_dz - recess_depth / 2 + 0.01))):
            bd.Box(mod_dx - 2.0, mod_dy - 2.0, recess_depth + 0.02,
                   mode=bd.Mode.SUBTRACT)
    add(parts, _can.part, SHIELD_TIN, "ESP_WROOM32")

    # --- 天線殘段 (antenna stub poking off +X edge of the can, PCB/white) ---
    # Mirror SSOT Antenna-Area dims: w_mm=2.5 (X) × h_mm=7.0 (Y). The trace
    # antenna sits at the very +X tip of the module, just past the metal can.
    ant_dx, ant_dy, ant_dz = 2.5, 7.0, 0.8
    can_x_max = mod_cx + mod_dx / 2
    ant_cx = can_x_max + ant_dx / 2 + 0.1     # poke off the can's +X face
    add(parts, box(ant_cx, 0.0, pz + ant_dz / 2,
                   ant_dx, ant_dy, ant_dz),
        WHITE, "Antenna_Stub")

    # --- Micro-USB 接口 (-X 短邊, 突出邊緣 ~0.5mm, 開孔成插口) ---
    # Real connector: 7.5 wide (Y) × 5.9 long (X) × 2.6 tall.
    # Hollow the -X face so it reads as a connector mouth, not a solid brick.
    usb_dx, usb_dy, usb_dz = 5.9, 7.5, 2.6
    usb_cx = -L / 2 + usb_dx / 2 - 0.5       # 0.5mm overhang on -X
    mouth_depth = usb_dx - 1.2               # leave ~1.2mm back wall
    with bd.BuildPart() as _usb:
        with bd.Locations(bd.Location((usb_cx, 0.0, pz + usb_dz / 2))):
            bd.Box(usb_dx, usb_dy, usb_dz)
        # cut the slot mouth from the -X face (smaller than the shell)
        face_x = usb_cx - usb_dx / 2
        with bd.Locations(bd.Location(
                (face_x + mouth_depth / 2 - 0.01, 0.0, pz + usb_dz / 2))):
            bd.Box(mouth_depth + 0.02, usb_dy - 1.4, usb_dz - 1.2,
                   mode=bd.Mode.SUBTRACT)
    add(parts, _usb.part, USB_SILVER, "MicroUSB")

    # --- 2×15 排針, 沿 X 軸跑, 兩列在 y=±11.4 (對齊 PCBSpec) ---
    # SSOT extra_ports LEFT/RIGHT_HDR: pitch 2.54. Keep add_pin_header (black
    # plastic strip + gold receptacle pins) AND add a square BLACK post per pin
    # on top so the header reads as discrete pins, not a flat strip.
    pitch = 2.54
    n_pins = 15
    post_w, post_h = 0.64, 3.0                # square pin shank
    # PCBSpec: pin 0 (EN) at x_local=1.3 → centred x = -L/2 + 1.3 = -25.7+1.3 = -24.4
    x_start = -L / 2 + 1.3
    for side, sy in [("L", -11.4), ("R", 11.4)]:
        pins = [(x_start + i * pitch, sy) for i in range(n_pins)]
        add_pin_header(parts, pz, pins, f"Header_{side}",
                       pitch=pitch, plastic_h=2.54, is_male=True)
        # per-pin square black posts standing above the plastic strip
        for px, py in pins:
            add(parts, box(px, py, pz + 2.54 + post_h / 2,
                           post_w, post_w, post_h),
                BLACK, f"Post_{side}")

    # --- EN / BOOT 按鍵 (USB 端, -X side, 在兩排 header 中間) ---
    btn_dx, btn_dy, btn_dz = 2.5, 3.3, 1.5
    btn_cx = -L / 2 + 6.0
    for by, lbl in [(-4.5, "EN"), (4.5, "BOOT")]:
        add(parts, box(btn_cx, by, pz + btn_dz / 2,
                       btn_dx, btn_dy, btn_dz),
            BLACK, f"Btn_{lbl}")

    # --- CP2102 USB-UART IC (QFP, SSOT ic-qfp pins=28 bodyW=4.9 bodyD=3.9) ---
    # Keep add_smd_ic for the dark IC body + pin1 dot, then add 4 thin gold
    # lead rows around the perimeter so it reads as a leaded QFP, not a QFN pad.
    cp_cx, cp_cy = -L / 2 + 12.0, 0.0
    cp_bw, cp_bd, cp_bh = 4.9, 3.9, 0.9
    add_smd_ic(parts, cp_cx, cp_cy, pz, cp_bw, cp_bd, cp_bh, "CP2102")
    lead_pitch = 0.65
    lead_len, lead_t, lead_h = 0.45, 0.3, 0.2
    n_side_x = 7                              # 7+7+7+7 = 28 leads
    n_side_y = 7
    lead_z = pz + lead_h / 2
    # leads on ±Y faces (run along X)
    for i in range(n_side_x):
        lx = cp_cx + (i - (n_side_x - 1) / 2) * lead_pitch
        for sy in (cp_cy + cp_bd / 2 + lead_len / 2,
                   cp_cy - cp_bd / 2 - lead_len / 2):
            add(parts, box(lx, sy, lead_z, lead_t, lead_len, lead_h),
                PIN_GOLD, "CP2102_Lead")
    # leads on ±X faces (run along Y)
    for i in range(n_side_y):
        ly = cp_cy + (i - (n_side_y - 1) / 2) * lead_pitch
        for sx in (cp_cx + cp_bw / 2 + lead_len / 2,
                   cp_cx - cp_bw / 2 - lead_len / 2):
            add(parts, box(sx, ly, lead_z, lead_len, lead_t, lead_h),
                PIN_GOLD, "CP2102_Lead")

    # --- AMS1117 穩壓器 (SOT-223: dark body + large metal heat tab) ---
    ams_cx, ams_cy = -L / 2 + 18.0, 5.0
    ams_dx, ams_dy, ams_dz = 3.0, 4.0, 1.5
    add(parts, box(ams_cx, ams_cy, pz + ams_dz / 2,
                   ams_dx, ams_dy, ams_dz),
        IC_DARK, "AMS1117")
    # SOT-223 exposed metal tab on the -X side (solder pad / heatsink)
    tab_dx, tab_dy, tab_dz = 1.0, ams_dy - 0.6, 0.25
    add(parts, box(ams_cx - ams_dx / 2 - tab_dx / 2 + 0.1, ams_cy,
                   pz + tab_dz / 2, tab_dx, tab_dy, tab_dz),
        METAL_DARK, "AMS1117_Tab")

    # --- LED (PWR / USER) — USB 端 + WROOM 旁 ---
    # Keep add_led for the coloured SMD body, then cap each with a small
    # DOME_WHITE translucent lens so it reads as an emitter, not a flat chip.
    led_body_h = 0.8                          # matches add_led box height
    for lx, ly, lc, lbl in [(-L / 2 + 4.0, -3.0, LED_RED, "PWR_LED"),
                            (-L / 2 + 4.0, 3.0, LED_BLUE, "USER_LED")]:
        add_led(parts, lx, ly, pz, lc, lbl)
        add(parts, cyl(lx, ly, pz + led_body_h + 0.15, 0.45, 0.3),
            DOME_WHITE, f"{lbl}_Lens")

    # --- 絲印標籤 (沿長邊放, 不再橫向占滿) ---
    add(parts, box(-L / 2 + 10.0, -8.0, pz + 0.02, 14.0, 2.0, 0.04),
        WHITE, "Silkscreen_ESP32")

    return bd.Compound(children=parts, label="ESP32-DevKitC_V4")


# =====================================================================
# 2. Raspberry Pi 4 Model B  (85 × 56 × 17 mm)
# =====================================================================

def build_rpi_pcb_body() -> bd.Compound:
    """Raspberry Pi 4 Model B — 綠色 PCB.

    Axis convention (PCBSpec): X = long axis (85mm), Y = short axis (56mm).
    +X: USB-A stacks + Ethernet. -X: USB-C power.
    +Y: GPIO headers. -Y: micro-HDMI + microSD.
    """
    L, W, T = 85.0, 56.0, 1.4
    pz = T
    parts: list[bd.Solid] = []

    # --- PCB 基板（含 4 個角落安裝孔）---
    holes = [
        (+29.0, +24.5, 1.4), (+29.0, -24.5, 1.4),
        (-29.0, +24.5, 1.4), (-29.0, -24.5, 1.4),
    ]
    parts.append(make_pcb_board(L, W, T, PCB_GREEN, "RPi4_PCB", holes=holes))

    # --- BCM2711 SoC (15×15×1.2 QFN) ---
    add_smd_ic(parts, -8.0, 2.0, pz, 15.0, 15.0, 1.2, "BCM2711")

    # --- LPDDR4 RAM (9×14×1.0) ---
    add_smd_ic(parts, -8.0, -12.0, pz, 9.0, 14.0, 1.0, "LPDDR4")

    # --- 40-pin GPIO (2×20) 沿 +Y 側 ---
    pitch = 2.54
    gpio_pins = []
    for row in range(2):
        ry = W / 2 - 3.5 - row * pitch
        for col in range(20):
            px = -29.0 + col * pitch
            gpio_pins.append((px, ry))
    add_pin_header(parts, pz, gpio_pins, "GPIO_40",
                   pitch=pitch, plastic_h=2.54, is_male=True)

    # --- 2× 堆疊 USB-A (14×13×15.5 per pair) ---
    usba_dx, usba_dy, usba_dz = 14.0, 13.0, 15.5
    for i, uy in [(0, 10.0), (1, -7.0)]:
        add(parts, box(L / 2 - usba_dx / 2 + 2.0, uy,
                       pz + usba_dz / 2, usba_dx, usba_dy, usba_dz),
            USB_SILVER, f"USB_A_Stack_{i}")

    # --- USB-C 電源 (−X 側) ---
    usbc_dx, usbc_dy, usbc_dz = 9.0, 7.0, 3.2
    add(parts, box(-L / 2 + usbc_dx / 2 - 1.0, -W / 2 + 11.0,
                   pz + usbc_dz / 2, usbc_dx, usbc_dy, usbc_dz),
        USB_SILVER, "USB_C_Power")

    # --- Ethernet RJ45 (+X 側中央) ---
    eth_dx, eth_dy, eth_dz = 16.0, 14.0, 13.5
    add(parts, box(L / 2 - eth_dx / 2 + 2.0, -22.0,
                   pz + eth_dz / 2, eth_dx, eth_dy, eth_dz),
        METAL, "Ethernet_RJ45")

    # --- 2× micro-HDMI (−Y 側) ---
    hdmi_dx, hdmi_dy, hdmi_dz = 6.5, 2.8, 1.5
    for i, hx in [(0, -12.0), (1, -1.0)]:
        add(parts, box(hx, -W / 2 + hdmi_dy / 2 - 0.5,
                       pz + hdmi_dz / 2, hdmi_dx, hdmi_dy, hdmi_dz),
            METAL, f"MicroHDMI_{i}")

    # --- WiFi/BT 遮蔽罩 (12×10×2) ---
    add(parts, box(10.0, 2.0, pz + 1.0, 12.0, 10.0, 2.0),
        SHIELD_TIN, "WiFi_BT_Shield")

    # --- microSD 插槽 (−Y 側靠 −X 角) ---
    sd_dx, sd_dy, sd_dz = 11.5, 12.0, 1.5
    add(parts, box(-L / 2 + sd_dx / 2 + 2.0,
                   -W / 2 + sd_dy / 2 - 0.5, pz + sd_dz / 2,
                   sd_dx, sd_dy, sd_dz),
        METAL, "MicroSD_Slot")

    # --- LED ---
    add_led(parts, -L / 2 + 5.0, W / 2 - 4.0, pz, LED_RED, "PWR_LED")
    add_led(parts, -L / 2 + 8.0, W / 2 - 4.0, pz, LED_GREEN, "ACT_LED")

    return bd.Compound(children=parts, label="RaspberryPi_4B")


# =====================================================================
# 3. BBC micro:bit V2  (51.8 × 42 × 11.7 mm)
# =====================================================================

def build_microbit_pcb_body() -> bd.Compound:
    """BBC micro:bit V2 — 黑色 PCB，5×5 LED matrix.

    Axis convention (PCBSpec): X = long axis (51.8mm), Y = short axis (42mm).
    +Y: Micro-USB. -Y: Edge Connector.
    Buttons A/B at x=-/+11.4, y=+7.
    """
    L, W, T = 51.8, 42.0, 1.6
    pz = T
    parts: list[bd.Solid] = []

    # --- PCB 基板 ---
    parts.append(make_pcb_board(L, W, T, PCB_BLACK, "Microbit_PCB"))

    # --- 5×5 LED 矩陣 (20×20mm 區域，居中上半部) ---
    led_size = 3.0
    spacing = 4.0
    matrix_cy = 8.0  # 矩陣中心偏上
    for row in range(5):
        for col in range(5):
            lx = (col - 2) * spacing
            ly = matrix_cy + (row - 2) * spacing
            add(parts,
                box(lx, ly, pz + 0.3, led_size, led_size, 0.6),
                LED_RED, f"LED_{row}_{col}")

    # --- Button A (左, x=-11.4, y=+7) ---
    btn_dx, btn_dy, btn_dz = 6.0, 4.0, 2.0
    add(parts, box(-11.4, 7.0, pz + btn_dz / 2,
                   btn_dx, btn_dy, btn_dz),
        BLACK, "Btn_A")
    add(parts, cyl(-11.4, 7.0, pz + btn_dz + 0.02, 1.5, 0.04),
        WHITE, "Btn_A_Label")

    # --- Button B (右, x=+11.4, y=+7) ---
    add(parts, box(11.4, 7.0, pz + btn_dz / 2,
                   btn_dx, btn_dy, btn_dz),
        BLACK, "Btn_B")
    add(parts, cyl(11.4, 7.0, pz + btn_dz + 0.02, 1.5, 0.04),
        WHITE, "Btn_B_Label")

    # --- 底邊金手指接口 (Edge Connector) ---
    ec_span = 48.0
    ec_h = 5.0
    ec_cy = -W / 2 - ec_h / 2 + 0.5  # 延伸到 PCB 下方

    # 5 個大環形焊盤 (0, 1, 2, 3V3, GND)
    big_pad_w = 4.0
    big_positions = [-20.0, -10.0, 0.0, 10.0, 20.0]
    for i, bpx in enumerate(big_positions):
        labels = ["P0", "P1", "P2", "3V3", "GND"]
        add(parts, box(bpx, ec_cy, T / 2,
                       big_pad_w, ec_h, T),
            GOLD_TRACE, f"Edge_{labels[i]}")

    # 20 個小焊盤
    small_pad_w = 1.3
    small_gap = (ec_span - 5 * big_pad_w) / 20
    placed = 0
    for seg in range(4):
        seg_start = big_positions[seg] + big_pad_w / 2 + small_gap / 2
        seg_end = big_positions[seg + 1] - big_pad_w / 2 - small_gap / 2
        n_in_seg = 5
        step = (seg_end - seg_start) / max(n_in_seg - 1, 1)
        for j in range(n_in_seg):
            spx = seg_start + j * step
            add(parts, box(spx, ec_cy, T / 2,
                           small_pad_w, ec_h, T),
                GOLD_TRACE, f"Edge_Small_{placed}")
            placed += 1

    # --- Micro-USB (+Y 頂邊) ---
    usb_dx, usb_dy, usb_dz = 7.5, 5.9, 2.6
    add(parts, box(0, W / 2 - usb_dy / 2 + 0.5, pz + usb_dz / 2,
                   usb_dx, usb_dy, usb_dz),
        USB_SILVER, "MicroUSB")

    # --- Nordic nRF52833 SoC (7×7×0.9 QFN) ---
    add_smd_ic(parts, 0, 0, pz, 7.0, 7.0, 0.9, "nRF52833")

    # --- 揚聲器 (背面中央, ⌀10mm, h=2.5mm) ---
    add(parts, cyl(0, -5.0, -1.25, 5.0, 2.5), BLACK, "Speaker")

    # --- Reset 按鍵 (頂邊附近) ---
    add(parts, box(10.0, W / 2 - 5.0, pz + 0.75, 2.5, 2.0, 1.5),
        BLACK, "Btn_Reset")

    # --- Touch Logo (金色圓形, ⌀12mm, y=0) ---
    add(parts, cyl(0, 0, pz + 0.02, 6.0, 0.04), GOLD_TRACE, "Touch_Logo")

    return bd.Compound(children=parts, label="BBC_microbit_V2")


# =====================================================================
# CLI — 批次建模 + 匯出
# =====================================================================
if __name__ == "__main__":
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    for cls_name, builder in [
        ("ESP32-class", build_esp32_pcb_body),
        ("RaspberryPi-class", build_rpi_pcb_body),
        ("Microbit-class", build_microbit_pcb_body),
    ]:
        print(f"[pcb] Building {cls_name} ...")
        compound = builder()
        export_pcb(compound, str(ROOT / "shells" / cls_name), cls_name)
        bb = compound.bounding_box()
        print(f"  BBox: {bb.max.X - bb.min.X:.1f}"
              f"×{bb.max.Y - bb.min.Y:.1f}"
              f"×{bb.max.Z - bb.min.Z:.1f}mm")
