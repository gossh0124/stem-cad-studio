"""component_bodies_extra.py - Phase 2a C-1 body meshes (part 2/2). See component_bodies.py.
Procedural build123d models authored + validated by the gen-component-body-meshes workflow."""
from __future__ import annotations

from build123d import (
    Align, Axis, Box, BuildPart, Cone, Cylinder, Locations, Mode, Sphere, export_stl, fillet,
)


def gen_mist_atomizer():
    """Piezoelectric mist atomizer: square driver PCB carrying a round cylindrical
    cup/housing that holds the 20mm piezo ceramic disc, plus the oscillator driver IC
    and a 2-pin VCC/GND header. Footprint 25x25mm, overall height ~15mm.

    Dims from SSOT (Mist-Atomizer-class): PCB L=W=25mm; Piezo Disc dia=20mm
    body_h=5.0mm; Osc Driver 8x6mm body_h=1.75mm; VCC/GND header w=5.08mm
    body_h=2.54mm. Target H=15mm reached by the cylindrical cup that surrounds
    and elevates the submersible piezo disc.
    """
    L, W = 25.0, 25.0          # SSOT footprint
    pcb_h = 1.75               # driver PCB thickness (Osc Driver body_h)
    disc_d = 20.0              # piezo disc diameter
    disc_h = 5.0               # piezo disc body height
    target_h = 15.0            # SSOT overall height

    # cylindrical cup wall that holds the disc; rim reaches target height
    cup_wall = 1.5
    cup_outer_r = disc_d / 2 + cup_wall      # 11.5mm -> fits inside 25mm board
    cup_h = target_h - pcb_h                  # 13.25mm of cup above the PCB

    ic_w, ic_d, ic_h = 8.0, 6.0, 1.75         # oscillator driver IC
    hdr_w, hdr_d, hdr_h = 5.08, 3.0, 2.54     # 2-pin VCC/GND header

    # on_board centers translated to a board centred at origin (board span 0..25)
    def c(x, y):
        return (x - L / 2, y - W / 2)

    disc_cx, disc_cy = c(2.5 + disc_d / 2, 2.5 + disc_d / 2)   # (0, 0) centre
    ic_cx, ic_cy = c(1.5 + ic_w / 2, 1.5 + ic_d / 2)           # driver IC
    hdr_cx, hdr_cy = c(1.5 + hdr_w / 2, 0.0 + hdr_d / 2)       # header (bottom edge)

    with BuildPart() as p:
        # driver PCB base, sits on z=0..pcb_h
        Box(L, W, pcb_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # cylindrical cup/housing around the piezo disc
        with Locations([(disc_cx, disc_cy, pcb_h)]):
            Cylinder(cup_outer_r, cup_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        # hollow out the cup interior down to the disc seat
        with Locations([(disc_cx, disc_cy, pcb_h + disc_h)]):
            Cylinder(disc_d / 2, cup_h, mode=Mode.SUBTRACT,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # piezo ceramic disc seated at the bottom of the cup
        with Locations([(disc_cx, disc_cy, pcb_h)]):
            Cylinder(disc_d / 2, disc_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))
        # brass excitation electrode (small raised centre) on the disc
        with Locations([(disc_cx, disc_cy, pcb_h)]):
            Cylinder(disc_d / 4, disc_h + 0.6,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # oscillator driver IC on the PCB
        with Locations([(ic_cx, ic_cy, pcb_h)]):
            Box(ic_w, ic_d, ic_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 2-pin VCC/GND header at the board edge
        with Locations([(hdr_cx, hdr_cy, pcb_h)]):
            Box(hdr_w, hdr_d, hdr_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


def gen_mist_ultrasonic():
    """Ultrasonic mist maker module: ~35x35 base board carrying a tall round
    ultrasonic transducer housing capped by the exposed ceramic disc, plus a
    driver IC and a 2-pin VCC/GND header. Built centred at origin.

    Dims from SSOT (Mist-Ultrasonic-class): footprint 35x35, H=25.
    Sub-components: Ultrasonic Disc dia~25 body_h 5.0; Driver IC 10x8 h1.75;
    VCC/GND header 5.08x3.0 h2.54. PCB-coord disc centre (17.5,17.5)->origin.
    """
    L, W = 35.0, 35.0
    H = 25.0
    base_h = 3.0

    # transducer housing: a cylindrical can rising to near full height,
    # topped by the exposed ceramic disc.
    disc_r = 25.0 / 2          # 12.5
    disc_h = 5.0
    housing_r = disc_r + 1.5   # 14.0 sealed metal shell around the ceramic
    housing_h = H - base_h - disc_h  # 25 - 3 - 5 = 17

    # PCB-coord centres -> offset from disc centre (17.5, 17.5)
    ic_off = (2.0 + 10.0 / 2 - 17.5, 2.0 + 8.0 / 2 - 17.5)   # (-10.5, -11.5)
    hdr_off = (2.0 + 5.08 / 2 - 17.5, 0.0 + 3.0 / 2 - 17.5)  # (-12.96, -16.0)

    with BuildPart() as p:
        # base driver board, top face at z=0
        Box(L, W, base_h, align=(Align.CENTER, Align.CENTER, Align.MAX))

        # sealed cylindrical transducer housing, sitting on the board top (z=0)
        with Locations([(0, 0, 0)]):
            Cylinder(housing_r, housing_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # exposed round ceramic disc on top of the housing
        with Locations([(0, 0, housing_h)]):
            Cylinder(disc_r, disc_h,
                     align=(Align.CENTER, Align.CENTER, Align.MIN))

        # shallow recessed water-contact face on the disc top
        with Locations([(0, 0, housing_h + disc_h)]):
            Cylinder(disc_r - 3.0, 1.2,
                     align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.SUBTRACT)

        # driver IC on the board top
        with Locations([(ic_off[0], ic_off[1], 0)]):
            Box(10.0, 8.0, 1.75, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 2-pin VCC/GND header on the board top
        with Locations([(hdr_off[0], hdr_off[1], 0)]):
            Box(5.08, 3.0, 2.54, align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


def gen_msgeq7():
    """MSGEQ7 graphic-EQ chip as a DIP-8 IC.

    Footprint target L=9.5 (4-pin axis, X), W=6.35 (row-spacing axis, Y),
    H=3.3. Plastic body + two rows of 4 leads bending down.
    """
    L = 9.5            # overall length along pin rows (X)
    W = 6.35           # overall width across rows (Y)
    H = 3.3            # overall height
    pitch = 2.54       # pin-to-pin spacing along X

    # Plastic moulded body: spans the 4 pins in X, narrower than full W in Y,
    # sits on top so leads can hang below.
    body_l = 4 * pitch          # 10.16 -> trim to footprint
    body_l = min(body_l, L)     # keep within 9.5 footprint
    body_w = 3.9                # DIP-8 300mil plastic body width
    body_h = 2.4                # plastic thickness (legs add the rest)
    body_z = H - body_h         # body top at H

    # Lead geometry
    lead_w = 0.5                # lead cross-section
    lead_th = 0.3
    leg_h = body_z              # vertical drop from body underside to z=0
    foot_len = 0.7              # horizontal foot at the tip
    # X positions of the 4 pins per row, centred about 0
    xs = [(-1.5 + i) * pitch for i in range(4)]  # -3.81,-1.27,1.27,3.81
    # Lead row tips placed so tip+foot just reaches the W/2 footprint edge,
    # giving an overall Y span ~= target W (6.35mm).
    y_row = W / 2.0 - foot_len  # leg row; foot extends outward to W/2

    with BuildPart() as p:
        # --- plastic body ---
        with Locations([(0, 0, body_z)]):
            Box(body_l, body_w, body_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # pin-1 notch / orientation dot: small cylinder dimple on top, one corner
        with Locations([(xs[0], -body_w / 2 + 0.9, H)]):
            Cylinder(0.5, 0.4, align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.SUBTRACT)

        # --- leads: vertical leg + horizontal foot, per side ---
        for sy in (+1, -1):
            for x in xs:
                # shoulder: from body edge outward to the lead row
                y_edge = sy * (body_w / 2.0)
                y_tip = sy * y_row
                y_mid = (y_edge + y_tip) / 2.0
                shoulder_len = abs(y_tip - y_edge)
                # horizontal shoulder near top of legs
                with Locations([(x, y_mid, body_z)]):
                    Box(lead_w, shoulder_len, lead_th,
                        align=(Align.CENTER, Align.CENTER, Align.MIN))
                # vertical leg dropping to the board
                with Locations([(x, y_tip, 0)]):
                    Box(lead_w, lead_th, leg_h,
                        align=(Align.CENTER, Align.CENTER, Align.MIN))
                # foot at the bottom tip
                with Locations([(x, y_tip + sy * foot_len / 2.0, 0)]):
                    Box(lead_w, foot_len, lead_th,
                        align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


def gen_led_strip():
    # Footprint from SSOT (Lighting-LED-Strip-class physical):
    #   length_mm=100, width_mm=10, height_mm=3
    L = 100.0
    W = 10.0
    H = 3.0

    # Layout judgement: flexible PCB strip is a thin base; LED chips raised on top.
    pcb_h = 1.5            # thin flexible PCB strip
    led_n = 10             # 10 LEDs evenly spaced along the strip
    led_w = 4.0            # 5050-style square chip ~ 4x4 footprint
    led_h = H - pcb_h      # raised height so total = footprint H (3.0)

    with BuildPart() as p:
        # Main body: the flexible PCB strip, centred at origin, base at z=0
        Box(L, W, pcb_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Row of LED chips raised on top of the strip, evenly spaced
        margin = led_w / 2.0 + 2.0
        if led_n > 1:
            x0 = -(L / 2.0) + margin
            x1 = (L / 2.0) - margin
            step = (x1 - x0) / (led_n - 1)
            led_xs = [x0 + i * step for i in range(led_n)]
        else:
            led_xs = [0.0]
        led_positions = [(x, 0.0, pcb_h) for x in led_xs]
        with Locations(led_positions):
            Box(led_w, led_w, led_h, align=(Align.CENTER, Align.CENTER, Align.MIN))

    return p.part


def gen_switch_generic():
    """Generic SPDT toggle switch (MTS-102 compatible).

    Footprint target L=13 (X) x W=8 (Y) x H=15 (Z) mm.
    Layout: rectangular insulator body (~13x8x7.5) + threaded bushing collar +
    toggle lever (cylinder) protruding up with a ball tip to total H~15 + 3 solder
    pins underneath. Dims from SSOT physical (13x8x15) + _ui_hints
    (TOGGLE-BODY box, 3-pin TERMINALS pitch 3.5). _3d_hints.sub_components_3d is empty.
    """
    L, W = 13.0, 8.0          # SSOT footprint
    body_h = 7.5              # main insulator body height (z=0..7.5)
    bushing_h = 1.5           # threaded mount bushing above body
    pin_h = 2.0               # solder pins protrude below body
    tip_r = 1.5               # ball-tip radius on lever
    overall_h = 15.0          # SSOT overall device height (full bbox span)
    with BuildPart() as p:
        # main rectangular body, base at z=0
        Box(L, W, body_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # threaded bushing collar on top of body (panel-mount neck)
        with Locations([(0, 0, body_h)]):
            Cylinder(3.0, bushing_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # toggle lever: thin cylinder rising from bushing top; size so the
        # ball-tip top reaches z = overall_h - pin_h (total span == overall_h)
        lever_base = body_h + bushing_h
        tip_top = overall_h - pin_h        # highest point of ball tip
        tip_center = tip_top - tip_r
        lever_h = tip_center - lever_base
        with Locations([(0, 0, lever_base)]):
            Cylinder(1.2, lever_h, align=(Align.CENTER, Align.CENTER, Align.MIN))
        # ball tip on top of lever for recognisability
        with Locations([(0, 0, tip_center)]):
            Sphere(tip_r)
        # 3 solder pins underneath, pitch 3.5 along X, protruding down to z=-pin_h
        for px in (-3.5, 0.0, 3.5):
            with Locations([(px, 0, 0)]):
                Cylinder(0.6, pin_h, align=(Align.CENTER, Align.CENTER, Align.MAX))
    return p.part


def gen_usb_adapter():
    """USB 5V power adapter brick.

    Rectangular block (50x28x18) with a recessed USB-A port slot on one end
    and a small cable/barrel stub on the other. Dims from SSOT footprint
    (L=50, W=28, H=18). No _3d_hints.sub_components_3d; USB-A socket size from
    _ui_hints.extra_ports (bodyW=14, bodyH=5.7).
    """
    L, W, H = 50.0, 28.0, 18.0
    with BuildPart() as p:
        # Main adapter body, centred at origin
        Box(L, W, H)
        # USB-A port recess cut into the +X end face.
        # Slot ~ 13 x 6 (USB-A standard), centred vertically, recessed ~20 deep.
        with Locations([(L / 2, 0, 0)]):
            Box(20, 13, 6, align=(Align.MAX, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT)
        # Small barrel / cable stub protruding from the -X end face.
        # Kept short (3 mm) so the overall footprint stays ~ target L=50.
        with Locations([(-L / 2, 0, 0)]):
            Cylinder(4.0, 3.0, rotation=(0, 90, 0),
                     align=(Align.CENTER, Align.CENTER, Align.MAX),
                     mode=Mode.ADD)
    return p.part
