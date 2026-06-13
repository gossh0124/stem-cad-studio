"""component_bodies.py - procedural build123d body meshes for components that lacked a
PCB-body mesh (Phase 2a C-1, UND-A1/A3). Footprint dims from COMPONENT_REGISTRY (drift-gate
aligned); vertical features from data/component_datasheet_verified.json _3d_hints. Authored +
run-validated by the gen-component-body-meshes workflow (2026-06-03); each function returns a
build123d part. No-fallback: every gen produces real geometry (never a ghost box).

Bake:  .venv/Scripts/python.exe -m lib.cad.component_bodies
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from build123d import (
    Align, Axis, Box, BuildPart, Cone, Cylinder, Locations, Mode, Sphere, export_stl, fillet,
)
from lib.cad.component_bodies_extra import (
    gen_mist_atomizer, gen_mist_ultrasonic, gen_msgeq7, gen_led_strip, gen_switch_generic, gen_usb_adapter,
)
import build123d as bd
from lib.cad.pcb_common import (
    add, box, cyl, export_pcb,
    BLACK, METAL, METAL_DARK, PIN_GOLD, PCB_RED,
)

_REPO = Path(__file__).resolve().parent.parent.parent
_SHELLS = _REPO / "shells"

# COTS body colours not already in pcb_common.
PUMP_BLUE = bd.Color(0.05, 0.45, 0.80)
AA_WRAP = bd.Color(0.15, 0.55, 0.35)
GEARBOX_YELLOW = bd.Color(1.00, 0.922, 0.231)  # #ffeb3b iconic TT/FA-130 gearbox yellow


def _cyl_x(cx, cy, cz, r, length):
    """Solid cylinder with its axis along X (build123d rotation 0,90,0)."""
    with BuildPart() as bp:
        with Locations(bd.Location((cx, cy, cz), (0, 90, 0))):
            Cylinder(r, length)
    return bp.part


def _slotted_cage(cx, cy, z_bottom, r, h, n_slots, slot_w):
    """Cylinder (Z-axis) with n_slots vertical slots cut around the rim — the iconic
    submersible-pump intake strainer cage. z_bottom = bottom face z."""
    cz = z_bottom + h / 2.0
    with BuildPart() as bp:
        with Locations(bd.Location((cx, cy, cz))):
            Cylinder(r, h)
        for i in range(n_slots):
            ang = (i / n_slots) * 360.0
            rad = math.radians(ang)
            sx = cx + math.cos(rad) * r
            sy = cy + math.sin(rad) * r
            with Locations(bd.Location((sx, sy, cz), (0, 0, ang))):
                Box(slot_w, 4.0, h * 0.7, mode=Mode.SUBTRACT)
    return bp.part


def gen_motor_dc():
    # SSOT footprint (Motor-DC-class): L=70 W=22 H=18 mm
    # _3d_hints sub_components_3d: Motor Body body_h=25 (=can dia), Output Shaft body_h=5
    # _ui_hints: motor-dc can @ cx=14 (bodyW=28,bodyD=22); GEARBOX @ cx=49 (bodyW=38,bodyD=16)
    # Real device: rectangular plastic gearbox + cylindrical metal motor can (rear) + output shaft (front)
    L, W, H = 70.0, 22.0, 18.0

    # X axis = length (70). origin centred. Front (output) at +X, rear (can) at -X.
    gearbox_l = 40.0   # plastic gearbox block (the bulk of the body)
    gearbox_w = 22.0   # full width
    gearbox_h = 18.0   # full height -> sets H
    # gearbox occupies the front portion: from x = +35 back to x = -5
    gearbox_cx = (L / 2.0) - (gearbox_l / 2.0)  # = 15.0

    can_l = 25.0       # metal motor can length (Motor Body), axis along X, at rear
    can_r = H / 2.0    # can diameter ~= H (18) -> r=9, recognisable cylinder, fits height
    # can sits behind the gearbox, butting against its rear face
    can_rear_face_x = gearbox_cx - gearbox_l / 2.0  # = -5.0
    can_cx = can_rear_face_x - can_l / 2.0           # = -17.5  (can extends to x=-30)

    shaft_l = 5.0      # output shaft, protrudes from gearbox front face (= hint body_h 5)
    shaft_r = 5.0 / 2.0  # shaft_diameter_mm = 5
    shaft_y = 0.0
    shaft_z = 0.0
    gearbox_front_x = gearbox_cx + gearbox_l / 2.0   # = +35.0

    # Multi-colour body: emit SEPARATE coloured parts (was a fused colourless
    # solid -> 0-material GLB -> flat teal). _cyl_x builds X-axis cylinders, matching
    # the old rotation=(0,90,0) cans. Dims/positions unchanged from the fused version.
    parts: list = []

    # --- plastic gearbox: rectangular body (YELLOW, iconic TT/FA-130 gearbox) ---
    add(parts, box(gearbox_cx, 0.0, 0.0, gearbox_l, gearbox_w, gearbox_h),
        GEARBOX_YELLOW, "Gearbox")

    # --- metal motor can: cylinder, axis along X, at the rear (METAL_DARK can) ---
    add(parts, _cyl_x(can_cx, 0.0, 0.0, can_r, can_l), METAL_DARK, "Motor Body")

    # --- output shaft: small steel cylinder protruding from gearbox front (METAL) ---
    add(parts, _cyl_x(gearbox_front_x + shaft_l / 2.0, shaft_y, shaft_z, shaft_r, shaft_l),
        METAL, "Output Shaft")

    # --- M+ / M- solder terminal tabs at the rear of the can (gold, SSOT pitch 2.54) ---
    # SSOT pin_layout TERMINALS: 2 solder tabs on the rear face; gold #c9b037 ~ PIN_GOLD.
    can_rear_x = can_cx - can_l / 2.0   # = -30.0 (rearmost can face)
    for i, ty in enumerate((-1.27, 1.27)):  # 2.54 pitch across Y, on the rear face
        add(parts, box(can_rear_x - 1.0, ty, 0.0, 2.0, 1.0, 3.0),
            PIN_GOLD, f"Terminal {'M+' if i == 0 else 'M-'}")

    return bd.Compound(children=parts, label="Motor-DC-class")


def gen_motor_servo():
    """SG90 micro servo: rectangular body + 2 flat mounting ears (extend in L) +
    round output shaft/horn on top + thin 3-wire cable stub at rear.

    Dims from SSOT (Motor-Servo-class): body 23 x 12.2 x 22.7mm;
    ears extend L-span to ~32.5mm (each ~4.75mm, 2.5mm thick, 6mm tall) -
    kept modest here so the bbox footprint stays ~ target L; shaft hub reaches
    total H ~32mm; 3-wire cable stub at rear.
    """
    L = 23.0          # body length (X / footprint L)
    W = 12.2          # body width  (Y / footprint W)
    H_body = 22.7     # body-only height (Z)

    ear_ext = 2.5     # how far each ear extends beyond body in +/-X (kept modest so footprint ~ target L)
    ear_th = 2.5      # ear thickness (Z)
    ear_w = 6.0       # ear extent in Y
    ear_z = H_body * 0.70  # ears sit on upper region of body (typical SG90)

    shaft_r = 3.0     # output hub radius (~6mm dia)
    shaft_top = 32.0  # total target height to top of shaft
    shaft_h = shaft_top - H_body  # = 9.3mm hub protrusion

    cable_d = 2.54    # 3-wire cable stub thickness
    cable_len = 3.0   # short stub kept within W footprint for recognisability

    with BuildPart() as p:
        # Main plastic housing, centred at origin in XY, base at z=0
        Box(L, W, H_body, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Two flat mounting ears extending in +/-X, on upper body region
        for sx in (-1.0, 1.0):
            ex = sx * (L / 2 + ear_ext / 2)
            with Locations([(ex, 0, ear_z)]):
                Box(ear_ext, ear_w, ear_th,
                    align=(Align.CENTER, Align.CENTER, Align.MIN))

        # M2 mounting holes through the ears
        for sx in (-1.0, 1.0):
            ex = sx * (L / 2 + ear_ext / 2)
            with Locations([(ex, 0, ear_z + ear_th / 2)]):
                Cylinder(1.0, ear_th + 2,
                         align=(Align.CENTER, Align.CENTER, Align.CENTER),
                         mode=Mode.SUBTRACT)

        # Round output shaft / horn hub on top, offset toward one end (SG90).
        # Reaches z=shaft_top (=32mm) so total height matches target H.
        shaft_x = L / 2 - 6.0
        with Locations([(shaft_x, 0, H_body)]):
            Cylinder(shaft_r, shaft_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 3-wire cable stub at rear, kept inside the W footprint edge for recognisability
        with Locations([(0, -(W / 2 - cable_len / 2), cable_d / 2 + 1.0)]):
            Box(7.0, cable_len, cable_d,
                align=(Align.CENTER, Align.CENTER, Align.CENTER))

    return p.part


def gen_motor_stepper():
    """28BYJ-48 stepper motor + ULN2003 driver board.

    SSOT (Motor-Stepper-class, data/component_datasheet_verified.json):
      combined footprint L=42 W=35 H=30
      driver PCB 35 x 31 x 1.6
      ULN2003A IC 10 x 15, body_h 4.0
      4 LEDs 2 x 2, body_h 1.0
      MOTOR-CONN 12 x 8, body_h 25 (tall white connector)
      INPUT-HDR 15.24 x 4, body_h 2.54
      motor can dia 28 (r=14), height 19; shaft D-cut 5mm

    Layout: PCB lies in XY plane (long axis = X). The round motor sits beside
    the PCB on -X side; the two overlap so combined X span = 42, Y span = 35
    (motor mounting ears widen to target 35). +Z is up.
    """
    from build123d import BuildPart, Box, Cylinder, Locations, Align, Mode

    PCB_L = 35.0          # PCB long axis (X)
    PCB_W = 31.0          # PCB short axis (Y)
    PCB_T = 1.6           # PCB thickness
    MOTOR_R = 14.0        # motor radius (dia 28)
    MOTOR_H = 19.0        # motor body height

    with BuildPart() as p:
        # --- Driver PCB (green board), bottom on z=0, centred in XY ---
        Box(PCB_L, PCB_W, PCB_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
        pcb_top = PCB_T

        # verified.json on_board origin = PCB lower-left (0..35 x, 0..31 y).
        def b2c(x_mm, y_mm):
            return (x_mm - PCB_L / 2.0, y_mm - PCB_W / 2.0)

        # --- ULN2003A DIP IC (black), 10 x 15, h 4.0 ---
        ic_cx, ic_cy = b2c(8.0 + 10.0 / 2, 8.0 + 15.0 / 2)
        with Locations([(ic_cx, ic_cy, pcb_top)]):
            Box(10.0, 15.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- 4 phase indicator LEDs (2 x 2, h 1.0) ---
        for lx, ly in [(22.0, 22.0), (25.0, 22.0), (22.0, 26.0), (25.0, 26.0)]:
            cx, cy = b2c(lx + 1.0, ly + 1.0)
            with Locations([(cx, cy, pcb_top)]):
                Box(2.0, 2.0, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- MOTOR-CONN white connector (12 x 8, tall h 25) ---
        mc_cx, mc_cy = b2c(20.0 + 12.0 / 2, 10.0 + 8.0 / 2)
        with Locations([(mc_cx, mc_cy, pcb_top)]):
            Box(12.0, 8.0, 25.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- INPUT-HDR 6-pin 2.54 header (15.24 x 4, h 2.54) at bottom edge ---
        hdr_cx, hdr_cy = b2c(5.0 + 15.24 / 2, 0.0 + 4.0 / 2)
        with Locations([(hdr_cx, hdr_cy, pcb_top)]):
            Box(15.24, 4.0, 2.54, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- 28BYJ-48 motor (round can) beside PCB on -X side ---
        # PCB +X edge = +17.5; want combined X = 42 -> motor sets min X = -24.5.
        pcb_right = PCB_L / 2.0            # 17.5
        target_min_x = pcb_right - 42.0    # -24.5
        motor_cx = target_min_x + MOTOR_R  # -10.5
        with Locations([(motor_cx, 0.0, 0.0)]):
            Cylinder(MOTOR_R, MOTOR_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # mounting tabs / ears: thin flange across the motor reaching full
        # target width (35 in Y); kept within motor X footprint (no overshoot).
        with Locations([(motor_cx, 0.0, 8.0)]):
            Box(2.0 * MOTOR_R, 35.0, 1.2, align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.ADD)
        # central output gearbox boss on top of motor can
        with Locations([(motor_cx + 4.0, 0.0, MOTOR_H)]):
            Cylinder(5.0, 3.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # output shaft (D-cut 5mm) protruding so total height ~= target 30
        with Locations([(motor_cx + 4.0, 0.0, MOTOR_H + 3.0)]):
            Cylinder(2.5, 8.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


def gen_pump_water():
    """Mini submersible water pump (3–5V) — realistic multi-colour body. The iconic
    submersible shape: a slotted intake strainer cage at the bottom, a cylindrical
    motor housing, a top cap, a barbed outlet spout on top, plus red/black leads.
    SSOT Pump-Water-class footprint 45×30×25, outlet dia 8 on top. User feedback
    2026-06-06: 外型/細節與真實不符 → rebuilt from a generic blue box into a
    recognisable submersible pump (cylindrical, not boxy; strainer + barb detail).
    Geometry is cylindrical (~dia 26); the assembly fits it uniformly into the
    45×30 footprint (no distortion)."""
    body_r = 12.0          # motor housing radius (dia 24)
    body_h = 17.0
    cage_r = 13.0          # intake strainer slightly wider than the body
    cage_h = 6.0
    cap_h = 2.0
    outlet_r = 4.0         # outlet barb base radius (dia 8 per SSOT)
    outlet_h = 11.0

    parts: list = []
    z = 0.0
    # Intake strainer cage at the very bottom (dark, vertical slots).
    add(parts, _slotted_cage(0.0, 0.0, z, cage_r, cage_h, 8, 2.4), METAL_DARK, "Intake Strainer")
    z += cage_h
    # Cylindrical motor housing (blue plastic).
    add(parts, cyl(0.0, 0.0, z + body_h / 2.0, body_r, body_h), PUMP_BLUE, "Motor Body")
    z += body_h
    # Top cap (dark).
    add(parts, cyl(0.0, 0.0, z + cap_h / 2.0, body_r - 0.5, cap_h), BLACK, "Top Cap")
    z += cap_h
    # Barbed outlet spout on top (grey metal), offset toward +Y like the real part.
    oy = 4.0
    add(parts, cyl(0.0, oy, z + outlet_h / 2.0, outlet_r, outlet_h), METAL, "Outlet Spout")
    add(parts, cyl(0.0, oy, z + outlet_h - 0.6, outlet_r + 0.7, 1.4), METAL, "Outlet Barb")
    # Power cable exits the TOP (a real submersible pump routes its sealed motor cable
    # up out of the cap) — two leads as a bundle on the back side, opposite the outlet.
    add(parts, cyl(-1.6, -7.5, z + 4.5, 0.9, 9.0), PCB_RED, "Lead+")
    add(parts, cyl(1.6, -7.5, z + 4.5, 0.9, 9.0), BLACK, "Lead-")
    return bd.Compound(children=parts, label="Pump-Water-class")


def gen_battery_aa():
    """2xAA battery holder — multi-colour body replacing the old single-colour
    cuboid-with-two-holes placeholder (gen_missing_shells.gen_battery_aa, user
    feedback 2026-06-06: 同色長方體+頂面兩洞). SSOT Battery-AA-class L59 W32 H15,
    2 cells in series. Parts: black plastic case (base+walls+divider) + two silver
    AA cells with coloured wrap + gold positive nubs + dark negative springs.
    Cells lie along X and are *visible on top* (the real holder shows cells, not holes)."""
    L, W = 59.0, 32.0
    cell_r = 7.0
    cell_len = 50.5
    cell_cz = 8.0
    cell_ys = (-7.6, 7.6)

    parts: list = []
    # Plastic case: base plate + 4 walls + centre divider (all black).
    add(parts, box(0.0, 0.0, 2.0, L, W, 4.0), BLACK, "Case Base")
    add(parts, box(0.0, 15.5, 7.5, L, 1.0, 15.0), BLACK, "Wall +Y")
    add(parts, box(0.0, -15.5, 7.5, L, 1.0, 15.0), BLACK, "Wall -Y")
    add(parts, box(29.0, 0.0, 7.5, 1.0, W, 15.0), BLACK, "Wall +X")
    add(parts, box(-29.0, 0.0, 7.5, 1.0, W, 15.0), BLACK, "Wall -X")
    add(parts, box(0.0, 0.0, 7.5, L, 1.0, 15.0), BLACK, "Divider")
    # Two AA cells (silver core + coloured wrap band + gold + nub + dark - spring).
    for i, cy in enumerate(cell_ys):
        add(parts, _cyl_x(0.0, cy, cell_cz, cell_r, cell_len), METAL, f"Cell{i+1} Core")
        add(parts, _cyl_x(0.0, cy, cell_cz, cell_r + 0.15, cell_len - 9.0), AA_WRAP, f"Cell{i+1} Wrap")
        add(parts, _cyl_x(cell_len / 2 + 0.8, cy, cell_cz, 1.6, 1.6), PIN_GOLD, f"Cell{i+1} +")
        add(parts, _cyl_x(-cell_len / 2 - 1.5, cy, cell_cz, 5.0, 3.0), METAL_DARK, f"Cell{i+1} Spring")
    return bd.Compound(children=parts, label="Battery-AA-class")


def gen_speaker():
    """Round 36mm passive speaker: metal frame rim (dia 36, h~5) with a
    recessed front cone (sloped truncated cone) and a central permanent-magnet
    cylinder on the rear. Footprint ~36x36, frame height ~5mm.
    Dims from SSOT Speaker-class: physical.diameter_mm=36, height_mm=5;
    on_board MAGNET1 w_mm=16; _3d_hints.sub_components_3d cone/magnet.
    """
    from build123d import BuildPart, Cylinder, Cone, Locations, Align, Mode

    frame_dia = 36.0
    frame_r = frame_dia / 2.0
    frame_h = 5.0          # SSOT physical.height_mm — overall frame envelope
    rim_wall = 2.5         # metal rim thickness around the cone

    cone_top_r = frame_r - rim_wall   # cone mouth radius (inside the rim)
    cone_bottom_r = 5.0               # cone throat radius (small, at center)
    cone_h = 4.0                      # recessed depth (clamped under frame_h)

    magnet_r = 16.0 / 2.0  # SSOT on_board MAGNET1 w_mm=16
    # SSOT Magnet body_h_mm=5: magnet sits mostly within the 5mm frame depth
    # and bulges only modestly out the rear, so total H stays ~target.
    magnet_h = 5.0
    magnet_protrude = 1.5  # how far the magnet pokes below the frame base (z=0)

    with BuildPart() as p:
        # Metal frame rim — overall round body, base at z=0, top at z=frame_h
        Cylinder(frame_r, frame_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Cut a wide shallow recess from the top so the cone sits inside the rim.
        with Locations([(0, 0, frame_h - cone_h)]):
            Cylinder(
                cone_top_r, cone_h + 0.1,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            )

        # Speaker cone — truncated cone (frustum), mouth (wide) at top.
        # Cone(bottom_radius, top_radius, height): small throat -> wide mouth.
        with Locations([(0, 0, frame_h - cone_h)]):
            Cone(
                cone_bottom_r, cone_top_r, cone_h,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )

        # Central permanent magnet — cylinder on the rear. Aligned by its MAX
        # (top) face at z=(magnet_h - magnet_protrude)=3.5, so it spans
        # z=-1.5..3.5: embedded in the frame, protruding ~1.5mm below the base.
        with Locations([(0, 0, magnet_h - magnet_protrude)]):
            Cylinder(
                magnet_r, magnet_h,
                align=(Align.CENTER, Align.CENTER, Align.MAX),
            )

    return p.part


def gen_l298n():
    """L298N dual H-bridge motor driver board.

    PCB ~43x43, dominated by a tall black heatsink (h5) over the L298N IC,
    two green screw terminals for MOTOR-A/MOTOR-B (the tallest visible
    features), a 3-pin PWR-IN screw terminal, a 6-pin logic header, ENA/ENB
    jumpers, a 78M05 5V regulator, and a power LED.

    Footprint origin convention: SSOT on_board_components give (x_mm, y_mm) as
    the bbox lower-left with PCB lower-left at origin. We re-centre the PCB at
    the world origin: cx = x_mm + w_mm/2 - L/2, cy = y_mm + h_mm/2 - W/2.
    """
    L, W = 43.0, 43.0          # PCB footprint
    PCB_H = 1.6                # PCB thickness
    top = PCB_H / 2            # top surface of PCB (parts mount here)

    def c(x_mm, y_mm, w_mm, h_mm):
        """Lower-left footprint coords -> centre coords on re-centred PCB."""
        return (x_mm + w_mm / 2 - L / 2, y_mm + h_mm / 2 - W / 2)

    with BuildPart() as p:
        # --- PCB body, centred at origin ---
        Box(L, W, PCB_H)

        # --- L298N IC (Multiwatt-15) under the heatsink ---
        cx, cy = c(11.5, 13.5, 20.0, 15.0)
        with Locations([(cx, cy, top)]):
            Box(20.0, 15.0, 1.75, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- Heatsink: tallest of the "flat" board features (h5), finned look ---
        cx, cy = c(12.0, 14.0, 19.0, 14.0)
        hs_base = top + 1.75
        with Locations([(cx, cy, hs_base)]):
            Box(19.0, 14.0, 5.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # fins: a few raised ribs on top of the heatsink block
        for i in range(-2, 3):
            with Locations([(cx + i * 4.0, cy, hs_base + 5.0)]):
                Box(1.6, 14.0, 1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- MOTOR-A screw terminal (dominant tall feature) ---
        cx, cy = c(3.0, 37.0, 10.16, 5.0)
        with Locations([(cx, cy, top)]):
            Box(10.16, 5.0, 11.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # two screw heads on top of the terminal block
            for dx in (-2.54, 2.54):
                with Locations([(dx, 0, 11.0)]):
                    Cylinder(1.8, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- MOTOR-B screw terminal ---
        cx, cy = c(29.84, 37.0, 10.16, 5.0)
        with Locations([(cx, cy, top)]):
            Box(10.16, 5.0, 11.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            for dx in (-2.54, 2.54):
                with Locations([(dx, 0, 11.0)]):
                    Cylinder(1.8, 2.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- PWR-IN 3-pin screw terminal (h5 hint -> realistic ~9mm block) ---
        cx, cy = c(2.0, 1.5, 14.0, 5.0)
        with Locations([(cx, cy, top)]):
            Box(14.0, 5.0, 9.0, align=(Align.CENTER, Align.CENTER, Align.MIN))
            for dx in (-4.5, 0.0, 4.5):
                with Locations([(dx, 0, 9.0)]):
                    Cylinder(1.6, 1.5, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- LOGIC 6-pin 2.54mm header (h2.54) ---
        cx, cy = c(16.0, 1.5, 15.24, 4.0)
        with Locations([(cx, cy, top)]):
            Box(15.24, 4.0, 2.54, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- ENA / ENB jumpers (h2.54) ---
        cx, cy = c(2.5, 11.0, 5.0, 3.5)
        with Locations([(cx, cy, top)]):
            Box(5.0, 3.5, 2.54, align=(Align.CENTER, Align.CENTER, Align.MIN))
        cx, cy = c(35.5, 11.0, 5.0, 3.5)
        with Locations([(cx, cy, top)]):
            Box(5.0, 3.5, 2.54, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- 78M05 / LM7805 5V regulator (TO-220-ish, h1.75 body + small tab) ---
        cx, cy = c(2.0, 18.0, 5.0, 5.0)
        with Locations([(cx, cy, top)]):
            Box(5.0, 5.0, 1.75, align=(Align.CENTER, Align.CENTER, Align.MIN))
            # raised metal tab to read as a regulator
            with Locations([(0, 0, 1.75)]):
                Box(5.0, 2.0, 4.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # --- Power LED (small dome, h1.0) ---
        cx, cy = c(37.0, 5.0, 2.0, 2.0)
        with Locations([(cx, cy, top)]):
            Cylinder(1.0, 1.0, align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


_GEN_MAP = {
    'Motor-Servo-class': (gen_motor_servo, 'SG90 Servo'),
    'Motor-Stepper-class': (gen_motor_stepper, '28BYJ-48 + ULN2003'),
    'Speaker-class': (gen_speaker, 'Speaker'),
    'L298N-Driver-class': (gen_l298n, 'L298N Driver'),
    'Mist-Atomizer-class': (gen_mist_atomizer, 'Piezo Atomizer'),
    'Mist-Ultrasonic-class': (gen_mist_ultrasonic, 'Ultrasonic Mist'),
    'Sensor-MSGEQ7-class': (gen_msgeq7, 'MSGEQ7'),
    'Lighting-LED-Strip-class': (gen_led_strip, 'LED Strip'),
    'Switch-Generic-class': (gen_switch_generic, 'Switch'),
    'USB-Adapter-class': (gen_usb_adapter, 'USB Adapter'),
    'Pump-Water-class': (gen_pump_water, 'R385 Pump'),
}

# Multi-colour bodies: returns a coloured Compound, baked via pcb_common.export_pcb
# (writes a multi-colour pcb_body.glb + merged pcb_body.stl directly, overwriting any
# single-colour fallback). ensure_shell_glbs protects pcb_body.glb so it is preserved.
# Entries already present in _GEN_MAP (e.g. Pump-Water-class) are routed through the
# colour exporter by bake_all instead of being baked twice; Battery-AA-class is
# colour-only and lives solely here.
_GEN_MAP_COLORED = {
    'Motor-DC-class': (gen_motor_dc, 'DC Gearmotor'),
    'Battery-AA-class': (gen_battery_aa, '2xAA Holder'),
    'Pump-Water-class': (gen_pump_water, 'R385 Pump'),
}


def _write_meta(d, cls, label, *, glb: bool):
    meta_path = d / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() \
        else {"class_name": cls, "kind": "pcb_body", "label": label}
    files = meta.setdefault("files", {})
    files["pcb_body_stl"] = "pcb_body.stl"
    if glb:
        files["pcb_body_glb"] = "pcb_body.glb"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def bake_all() -> int:
    """Build each body, export shells/<class>/pcb_body.stl, ensure meta.json, then GLB.
    Existing actuator dirs (kind='mount') keep their meta - pcb_body is added and the
    assembly variant order prefers it. Shell-less ghosts get a fresh kind='pcb_body' dir."""
    from lib.cad.glb_convert import ensure_shell_glbs
    ok = 0
    for cls, (fn, label) in _GEN_MAP.items():
        # Colour-routed classes are baked below via export_pcb (multi-colour GLB +
        # merged STL); skip the single-colour STL path so we don't double-bake.
        if cls in _GEN_MAP_COLORED:
            continue
        part = fn()
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        export_stl(part, str(d / "pcb_body.stl"))
        _write_meta(d, cls, label, glb=False)
        print(f"  [OK] {cls:28s} -> pcb_body.stl")
        ok += 1
    # Multi-colour bodies first, so the authoritative pcb_body.glb exists before
    # ensure_shell_glbs runs (it protects pcb_body.glb and will skip these).
    for cls, (fn, label) in _GEN_MAP_COLORED.items():
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        export_pcb(fn(), str(d), cls)
        _write_meta(d, cls, label, glb=True)
        print(f"  [OK] {cls:28s} -> pcb_body.glb (multi-colour)")
        ok += 1
    res = ensure_shell_glbs(_SHELLS)
    print(f"GLB post-process: converted {len(res['converted'])}, skipped {len(res['skipped'])}")
    return ok


if __name__ == "__main__":
    print(f"Done: {bake_all()} component bodies baked.")
