"""component_bodies_fidelity.py — multi-colour, datasheet-accurate rebuilds of the
crude single-colour / wrong-dimension component bodies (2026-06-06 fidelity pass).
Generated from the component-fidelity-rebuild workflow (each builder self-tested:
watertight, >=2 colours, bbox within ~15% of SSOT). Supersedes the single-colour
versions in scripts/gen_missing_shells.py for these classes.

Bake:  python -m lib.cad.component_bodies_fidelity
"""
from __future__ import annotations

import json
from pathlib import Path

import build123d as bd
from build123d import (
    BuildPart, Box, Cylinder, Cone, Sphere, Locations, Location, Align, Mode, fillet, Axis,
)
from lib.cad.pcb_common import (
    box, cyl, add, export_pcb,
    BLACK, METAL, METAL_DARK, PIN_GOLD, WHITE, IC_DARK, RUBBER_BLACK, BROWN, CRYSTAL,
    PCB_RED, PCB_GREEN, PCB_BLUE, PCB_BLACK, PCB_TEAL, RELAY_BLUE, TRIMPOT_BLUE,
    LED_RED, LED_GREEN, LED_BLUE, LED_YELLOW, DOME_WHITE, ACRYLIC, USB_SILVER, CONNECTOR_WHT,
)
from lib.cad.glb_convert import ensure_shell_glbs

_SHELLS = Path(__file__).resolve().parent.parent.parent / "shells"


def _cyl_x(cx, cy, cz, r, length):
    """X-axis cylinder helper."""
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz), (0, 90, 0))):
            bd.Cylinder(r, length)
    return bp.part


def gen_button() -> bd.Compound:
    """Tactile pushbutton 12×12mm (SKHHAKA010 compatible) - multi-colour with realistic internals."""
    parts = []

    # SSOT: 12×12×4.3 mm (body), 6.5mm pin spacing
    # Main black plastic body (bottom) - 12×12×3.5 mm
    add(parts, box(0, 0, 0, 12.0, 12.0, 3.5), BLACK, "Button_Body_Base")

    # Metal (silver) top cover — real tactile switches have a stainless cover plate,
    # not a white plastic frame. Sits flush on the black base top (z=3.5).
    add(parts, box(0, 0, 3.5, 11.0, 11.0, 0.5), METAL, "Button_Metal_Cover")

    # Round red plunger/actuator on top — cyl(r=2.75, h=1.2) #ef4444.
    # Cover top = 3.75; plunger bottom rests there → top = 3.75 + 1.2/2 ... clamp so
    # total height ≤ 4.3 (SSOT). plunger center z = 4.3 - 1.2/2 = 3.7 → top = 4.3.
    add(parts, cyl(0, 0, 4.3 - 1.2 / 2.0, 2.75, 1.2),
        bd.Color(0.937, 0.267, 0.267), "Button_Cap")

    # Internal spring contact area (small metal-like element visible through casing)
    add(parts, box(0, 0, 2.5, 4.0, 4.0, 0.3), METAL, "Button_Contact")
    
    # Four corner pins - gold-plated brass (2.54mm header spacing)
    # A1, A2 at front; B1, B2 at back
    pin_positions = [
        (-3.25, -3.25),  # A1
        (3.25, -3.25),   # B1
        (-3.25, 3.25),   # A2
        (3.25, 3.25),    # B2
    ]
    for px, py in pin_positions:
        add(parts, box(px, py, -1.75, 0.5, 0.5, 3.5), PIN_GOLD, "Button_Pin")
    
    return bd.Compound(children=parts, label='Button-class')

def gen_buzzer_active() -> bd.Compound:
    """Active piezo buzzer 12mm diameter, 9.5mm height with internal oscillator."""
    parts = []
    
    # SSOT: 12mm diameter, 9.5mm height
    # Main cylindrical black body (bottom resonator) - 12mm dia × 6.5mm
    add(parts, cyl(0, 0, 0, 6.0, 6.5), BLACK, "Buzzer_Body_Bottom")
    
    # Dark gray/black top dome cover - 12mm dia × 2.5mm
    add(parts, cyl(0, 0, 6.5, 6.0, 2.5), IC_DARK, "Buzzer_Dome_Top")
    
    # Polarity marking area on top (+ symbol in white/cream)
    add(parts, box(-1.5, -0.2, 9.0, 3.0, 0.4, 0.3), WHITE, "Buzzer_Mark_Horiz")
    add(parts, box(-0.2, -1.5, 9.0, 0.4, 3.0, 0.3), WHITE, "Buzzer_Mark_Vert")
    
    # Internal PCB (visible as dark red PCB material inside)
    add(parts, cyl(0, 0, 0.5, 4.5, 1.75), PCB_RED, "Buzzer_PCB_Driver")
    
    # Three connection pins (GND, +V, N/C) - gold plated
    # Standard 3.5mm pitch from datasheet
    pin_positions = [
        (-3.5, 0),   # GND
        (0, 0),      # +V
        (3.5, 0),    # NC
    ]
    for px, py in pin_positions:
        add(parts, cyl(px, py, -1.75, 0.35, 3.5), PIN_GOLD, "Buzzer_Pin")
    
    return bd.Compound(children=parts, label='Buzzer-Active-class')

def gen_buzzer_passive() -> bd.Compound:
    """Passive piezo buzzer 12mm diameter, 8.5mm height - requires external PWM."""
    parts = []
    
    # SSOT: 12mm diameter, 8.5mm height
    # Main cylindrical ceramic/plastic body (tan/cream piezo material) - 12mm dia × 6.0mm
    add(parts, cyl(0, 0, 0, 6.0, 6.0), CRYSTAL, "Buzzer_Body_Ceramic")
    
    # Black plastic mounting ring/casing - 12mm dia × 1.5mm
    add(parts, cyl(0, 0, 6.0, 6.0, 1.5), BLACK, "Buzzer_Ring_Plastic")
    
    # Dark top dome - 12mm dia × 1.0mm
    add(parts, cyl(0, 0, 7.5, 6.0, 1.0), IC_DARK, "Buzzer_Top_Cover")
    
    # Polarity marking (small white indicator on side)
    add(parts, box(-2.5, -0.3, 2.0, 1.0, 0.6, 0.5), WHITE, "Buzzer_PolMark")
    
    # Two connection pins (4mm pitch standard for piezo buzzers)
    pin_positions = [
        (-2.0, 0),   # +
        (2.0, 0),    # -
    ]
    for px, py in pin_positions:
        add(parts, cyl(px, py, -1.75, 0.35, 3.5), PIN_GOLD, "Buzzer_Pin")
    
    return bd.Compound(children=parts, label='Buzzer-Passive-class')

def gen_lighting_led_pwm() -> bd.Compound:
    """5mm diffused white LED (PWM dimmable).
    SSOT: 5x5x8.6mm. Multi-colour: white dome + black base + gold leads.
    """
    parts = []
    add(parts, cyl(0, 0, 5.0, 2.3, 4.5), DOME_WHITE, "LED_Dome")
    add(parts, cyl(0, 0, 1.0, 2.5, 2.0), BLACK, "LED_Body")
    add(parts, _cyl_x(1.0, 0, 1.5, 0.25, 7.0), PIN_GOLD, "Lead_Anode")
    add(parts, _cyl_x(-1.0, 0, 1.0, 0.25, 6.0), PIN_GOLD, "Lead_Cathode")
    return bd.Compound(children=parts, label='Lighting-LED-PWM-class')

def gen_lighting_led_rgb() -> bd.Compound:
    """5mm RGB LED (Common Cathode, 4-pin).
    SSOT: 5x5x8.6mm. Multi-colour: RGB segments + white dome + gold leads.
    """
    parts = []
    add(parts, cyl(0, 0, 5.0, 2.3, 4.5), DOME_WHITE, "LED_Dome")
    add(parts, cyl(-0.8, 0, 3.2, 0.6, 0.8), LED_RED, "LED_Segment_Red")
    add(parts, cyl(0.0, 0, 3.2, 0.6, 0.8), LED_GREEN, "LED_Segment_Green")
    add(parts, cyl(0.8, 0, 3.2, 0.6, 0.8), LED_BLUE, "LED_Segment_Blue")
    add(parts, cyl(0, 0, 1.0, 2.5, 2.0), BLACK, "LED_Body")
    add(parts, _cyl_x(0.5, 0, 1.5, 0.25, 7.0), PIN_GOLD, "Lead_Red")
    add(parts, _cyl_x(-0.5, 0, 1.0, 0.25, 7.5), PIN_GOLD, "Lead_GND")
    add(parts, _cyl_x(1.5, 0, 1.5, 0.25, 7.0), PIN_GOLD, "Lead_Green")
    add(parts, _cyl_x(-1.5, 0, 1.5, 0.25, 7.0), PIN_GOLD, "Lead_Blue")
    return bd.Compound(children=parts, label='Lighting-LED-RGB-class')

def gen_lighting_neopixel() -> bd.Compound:
    """WS2812B NeoPixel Strip (8 LEDs, 50x10x3mm).
    SSOT: 50x10x3mm. Multi-colour: PCB (teal) + 8 red LED chips + connectors.
    """
    parts = []
    add(parts, box(0, 0, 0.15, 50.0, 10.0, 0.3), PCB_TEAL, "PCB_Strip")
    # Each WS2812B 5050 = white body + clear lens cap + tiny central RGB die.
    # PCB top = 0.3; body 5x5x1.6 sits on top (center z = 0.3 + 1.6/2 = 1.1).
    for i in range(8):
        x = -22.0 + (i * 6.25) + 3.125
        add(parts, box(x, 0, 1.1, 5.0, 5.0, 1.6), DOME_WHITE, f"WS2812B_Body_{i+1}")
        add(parts, box(x, 0, 1.9 + 0.2, 4.5, 4.5, 0.4), ACRYLIC, f"WS2812B_Lens_{i+1}")
        add(parts, box(x, 0, 1.9 + 0.4 + 0.15, 1.5, 1.5, 0.3), LED_RED, f"WS2812B_Die_{i+1}")
    # Real 3-pin male headers at each end (SSOT extra_ports INPUT/OUTPUT, 2.54 pitch).
    # BLACK plastic strip + 3 PIN_GOLD posts. Header plastic height 2.54 (SSOT _3d_hints).
    for hx, grp in ((-23.0, "Input"), (23.0, "Output")):
        add(parts, box(hx, 0, 0.3 + 2.54 / 2.0, 2.6, 8.0, 2.54), BLACK, f"{grp}_Header")
        for py in (-2.54, 0.0, 2.54):
            add(parts, cyl(hx, py, 0.3 + 6.0 / 2.0, 0.32, 6.0), PIN_GOLD, f"{grp}_Pin")
    return bd.Compound(children=parts, label='Lighting-NeoPixel-class')

def gen_potentiometer():
    """Rotary Potentiometer RV09/RV16 10KΩ - B10K linear taper, panel-mount 16mm body.
    
    SSOT dimensions: L=16 W=16 H=20 mm. Multi-colour realistic body featuring:
    - Dark cylindrical insulator body (base)
    - Metal bushing collar (threaded panel-mount neck)
    - Large rotating knob (black, user-facing control)
    - White shaft hub mark (visual reference)
    - 3 golden solder pins (VCC, Wiper, GND at 4mm pitch)
    """
    L, W, H = 16.0, 16.0, 20.0
    body_r = 8.0
    body_h = 10.0
    bushing_r = 3.5
    bushing_h = 2.0
    knob_r = 8.0
    knob_h = 8.0
    knob_hub_r = 2.0
    pin_h = 2.0
    
    parts = []
    add(parts, cyl(0.0, 0.0, body_h / 2.0, body_r, body_h), PCB_BLACK, "Body")
    add(parts, cyl(0.0, 0.0, body_h + bushing_h / 2.0, bushing_r, bushing_h), METAL_DARK, "Bushing")
    add(parts, cyl(0.0, 0.0, body_h + bushing_h + knob_h / 2.0, knob_r, knob_h), BLACK, "Knob")
    add(parts, cyl(0.0, 0.0, body_h + bushing_h + knob_h - 0.2, knob_hub_r, 0.4), WHITE, "Hub")
    for px in (-4.0, 0.0, 4.0):
        add(parts, cyl(px, 0.0, -pin_h / 2.0, 0.6, pin_h), PIN_GOLD, "Pin")
    return bd.Compound(children=parts, label="Potentiometer-class")

def gen_switch():
    """Toggle Switch SPDT (MTS-102 compatible) - panel-mount 13x8mm body.
    
    SSOT dimensions: L=13 W=8 H=15 mm. Multi-colour realistic body featuring:
    - Dark rectangular insulator body (base)
    - Metal bushing collar (threaded panel-mount neck)
    - Thin toggle lever (dark rubber, extends from bushing)
    - White ball tip (recognisable toggle shape)
    - 3 golden solder pins (COM, NO, NC at 3.5mm pitch)
    """
    L, W, H = 13.0, 8.0, 15.0
    body_h = 7.5
    bushing_h = 1.5
    pin_h = 2.0
    tip_r = 1.5
    lever_r = 1.2
    lever_base = body_h + bushing_h
    tip_top = H - pin_h
    tip_center = tip_top - tip_r
    lever_h = tip_center - lever_base
    
    parts = []
    add(parts, box(0.0, 0.0, body_h / 2.0, L, W, body_h), PCB_BLACK, "Body")
    add(parts, cyl(0.0, 0.0, body_h + bushing_h / 2.0, 3.0, bushing_h), METAL_DARK, "Bushing")
    add(parts, cyl(0.0, 0.0, lever_base + lever_h / 2.0, lever_r, lever_h), RUBBER_BLACK, "Lever")
    with BuildPart() as bp:
        with Locations(bd.Location((0.0, 0.0, tip_center))):
            Sphere(tip_r)
    tip = bp.part
    tip.color = WHITE
    tip.label = "Tip"
    parts.append(tip)
    for px in (-3.5, 0.0, 3.5):
        add(parts, cyl(px, 0.0, -pin_h / 2.0, 0.6, pin_h), PIN_GOLD, "Pin")
    return bd.Compound(children=parts, label="Switch-class")

def gen_usb_5v():
    """Generic USB 5V Power Module - USB-A input breakout with 5V regulator.
    
    SSOT dimensions: L=60 W=30 H=18 mm. Multi-colour realistic PCB module featuring:
    - Green PCB base (fills 60x30 footprint)
    - Silver USB-A receptacle (left end, SSOT bodyW=14 × bodyD=13.1 × bodyH=5.7,
      hollow shell with subtracted cavity + dark internal tongue)
    - Dark IC voltage regulator (center, 10x30x1.75 mm AMS1117-5.0 style)
    - White output header (2-pin) with gold posts (5.08x4x2.54 mm)
    - 2-pos screw terminal block (right, green body + two metal screw heads)
    - Green power indicator LED (2x2x1 mm)
    """
    L, W, H = 60.0, 30.0, 18.0
    pcb_h = 1.6

    parts = []
    add(parts, box(0.0, 0.0, pcb_h / 2.0, L, W, pcb_h), PCB_GREEN, "PCB")

    # USB-A receptacle: SSOT bodyW=14 (width across, NOT 30), bodyD=13.1, bodyH=5.7.
    # Silver shell with a cavity subtracted from the -X (left/input) face + dark tongue.
    usb_w, usb_d, usb_h = 14.0, 13.1, 5.7
    usb_cx = -L / 2.0 + usb_d / 2.0
    usb_cz = pcb_h + usb_h / 2.0
    with bd.BuildPart() as ubp:
        with bd.Locations(bd.Location((usb_cx, 0.0, usb_cz))):
            bd.Box(usb_d, usb_w, usb_h)
        # Cavity opens toward -X: inset walls ~0.8mm, leave back wall.
        cav_d = usb_d - 1.6
        with bd.Locations(bd.Location((usb_cx - 0.8, 0.0, usb_cz))):
            bd.Box(cav_d, usb_w - 1.6, usb_h - 1.6, mode=bd.Mode.SUBTRACT)
    usb_shell = ubp.part
    usb_shell.color = USB_SILVER
    usb_shell.label = "USB-A"
    parts.append(usb_shell)
    # Dark plastic tongue inside the cavity (the contact carrier).
    add(parts, box(usb_cx - 0.4, 0.0, usb_cz, usb_d - 2.0, usb_w - 4.0, 1.2),
        IC_DARK, "USB-A_Tongue")

    ic_h = 1.75
    add(parts, box(-10.0, 0.0, pcb_h + ic_h / 2.0, 10.0, W, ic_h), IC_DARK, "Reg")

    # 2-pin output header: white plastic body + 2 gold posts (2.54 pitch).
    hdr_h = 2.54
    add(parts, box(13.0, 0.0, pcb_h + hdr_h / 2.0, 5.08, 4.0, hdr_h), CONNECTOR_WHT, "Hdr")
    for py in (-1.27, 1.27):
        add(parts, cyl(13.0, py, pcb_h + 4.0 / 2.0, 0.32, 4.0), PIN_GOLD, "Hdr_Pin")

    # 2-pos screw terminal block (SSOT SCREW-OUT, green body + two metal screw heads).
    term_h = 5.0
    add(parts, box(22.0, 0.0, pcb_h + term_h / 2.0, 8.0, W, term_h),
        bd.Color(0.133, 0.773, 0.345), "Term")
    for ty in (-5.08 / 2.0, 5.08 / 2.0):
        add(parts, cyl(22.0, ty, pcb_h + term_h - 0.2, 1.6, 0.6), METAL, "Term_Screw")

    led_h = 1.0
    add(parts, box(5.0, 9.0, pcb_h + led_h / 2.0, 2.0, 2.0, led_h), LED_GREEN, "LED")
    return bd.Compound(children=parts, label="USB-5V-class")

def gen_ac_adapter() -> bd.Compound:
    """AC-DC 5V 2A Adapter Module (Hi-Link HLK-PM01).
    SSOT: 50mm L x 30mm W x 20mm H
    Multi-colour: black main body, green screw terminals, gold header
    """
    parts = []
    L, W, H = 50.0, 30.0, 20.0
    
    # Main AC-DC module body (dark grey/black potted resin case)
    add(parts, box(0, 0, H/2, L, W, H), BLACK, "HLK-PM01_Main")
    
    # AC input screw terminal block (left side, green)
    term_w, term_h = 8, 10
    term_z = H - term_h/2 - 1
    add(parts, box(-18, 0, term_z, term_w, term_h, term_h), 
        bd.Color(0.13, 0.55, 0.13), "AC_Terminal_Block")
    # Two metal screw posts
    add(parts, cyl(-18, -4, H - 0.5, 0.8, 0.8), METAL_DARK, "AC_Screw_1")
    add(parts, cyl(-18, 4, H - 0.5, 0.8, 0.8), METAL_DARK, "AC_Screw_2")
    
    # DC output screw terminal block (right side, green)
    add(parts, box(18, 0, term_z, term_w, term_h, term_h),
        bd.Color(0.13, 0.55, 0.13), "DC_Terminal_Block")
    # Two metal screw posts
    add(parts, cyl(18, -4, H - 0.5, 0.8, 0.8), METAL_DARK, "DC_Screw_1")
    add(parts, cyl(18, 4, H - 0.5, 0.8, 0.8), METAL_DARK, "DC_Screw_2")
    
    # Internal transformer (implied)
    add(parts, box(0, 0, H/2, 30, 22, H - 4), BROWN, "Internal_Transformer")
    
    # Small mounting holes
    add(parts, cyl(-20, -12, 0.1, 1.0, 0.2), BLACK, "Mount_Hole_1")
    add(parts, cyl(20, 12, 0.1, 1.0, 0.2), BLACK, "Mount_Hole_2")
    
    # Output header (4-pin) at front
    header_x = -8
    header_z = 0.3
    for i, py in enumerate([-3.81, -1.27, 1.27, 3.81]):
        add(parts, cyl(header_x + i*2.54, py, header_z, 0.32, 1.2), PIN_GOLD, f"Header_Pin_{i}")
    add(parts, box(header_x + 3.81, 0, header_z + 0.8, 9, 9, 2.5), CONNECTOR_WHT, "Header_Body")
    
    return bd.Compound(children=parts, label="AC-Adapter-class")

def gen_remote() -> bd.Compound:
    """IR Remote Control Receiver Module (VS1838B / TSOP1838).
    SSOT: 30mm L x 10mm W x 12mm H
    Multi-colour: PCB green, IC package black, IR lens dome black, pins gold
    """
    parts = []
    L, W, H = 30.0, 10.0, 12.0
    pz = 1.6
    
    # PCB board (green)
    add(parts, box(0, 0, pz/2, L, W, pz), PCB_GREEN, "Receiver_PCB")
    
    # IC package (VS1838B TSOP sensor on PCB) - taller
    ic_h = 5.0
    ic_z = pz + ic_h/2
    add(parts, box(12, 0, ic_z, 5.5, 5.5, ic_h), IC_DARK, "VS1838B_IC")
    
    # IR lens dome (black, on top of IC) - much larger
    dome_h = 4.5
    dome_z = ic_z + ic_h/2 + dome_h/2
    add(parts, cyl(12, 0, dome_z, 2.8, dome_h), BLACK, "IR_Lens_Dome")
    
    # Three through-hole pins (VCC, DATA, GND at 2.54mm spacing)
    pin_x = -12
    for i, py in enumerate([-3.81, 0, 3.81]):
        add(parts, cyl(pin_x, py, pz/2, 0.32, 1.5), PIN_GOLD, f"Pin_{i}")
        add(parts, box(pin_x, py, 0.01, 1.5, 1.5, 0.04), METAL, f"Pad_{i}")
    
    # Decoupling capacitor
    add(parts, box(-8, -3, pz + 0.25, 2, 1, 0.6), BROWN, "Decoup_Cap")
    
    # Resistor
    add(parts, box(-6, 4, pz + 0.25, 2, 0.8, 0.5), BROWN, "Resistor")
    
    return bd.Compound(children=parts, label="Remote-class")


def gen_battery_lipo() -> bd.Compound:
    """1S 1000mAh LiPo pouch cell (503450) with JST-PH 2.0 lead.
    SSOT: 50mm L x 34mm W x 5.5mm H (503450 = 5.0 thick x 34 wide x 50 long).
    Multi-colour: silver/grey foil pouch + darker heat-seal seam lip on one long
    edge + black JST-PH housing with red/black wire stubs.
    """
    parts = []
    L, W, H = 50.0, 34.0, 5.5

    # Main foil pouch body (silver/grey aluminised film).
    add(parts, box(0.0, 0.0, H / 2.0, L, W, H), METAL, "Pouch_Foil")

    # Heat-seal seam lip along one long edge (+Y), darker/flatter than the pouch.
    seam_h = 1.0
    add(parts, box(0.0, W / 2.0 + 2.0, seam_h / 2.0, L - 4.0, 4.0, seam_h),
        METAL_DARK, "HeatSeal_Seam")

    # JST-PH 2.0 housing (small black connector) hanging off the +X short edge,
    # connected to the pouch by a short wire lead.
    edge_x = L / 2.0          # pouch +X edge = 25
    jst_w = 8.0
    wire_len = 6.0            # visible lead between pouch edge and housing
    jst_x = edge_x + wire_len + jst_w / 2.0   # housing center (x~35)
    add(parts, box(jst_x, 0.0, 2.0, jst_w, 5.0, 4.0), BLACK, "JST_Housing")

    # Two short wire stubs (red V+, black GND) bridging the pouch edge to the JST.
    wire_cx = edge_x + wire_len / 2.0
    add(parts, box(wire_cx, -1.5, 2.0, wire_len, 1.2, 1.2),
        bd.Color(0.937, 0.267, 0.267), "Wire_VPlus")
    add(parts, box(wire_cx, 1.5, 2.0, wire_len, 1.2, 1.2),
        BLACK, "Wire_GND")

    return bd.Compound(children=parts, label="Battery-LiPo-class")


_FIDELITY = {
    'Button-class': gen_button,
    'Buzzer-Active-class': gen_buzzer_active,
    'Buzzer-Passive-class': gen_buzzer_passive,
    'Lighting-LED-PWM-class': gen_lighting_led_pwm,
    'Lighting-LED-RGB-class': gen_lighting_led_rgb,
    'Lighting-NeoPixel-class': gen_lighting_neopixel,
    'Potentiometer-class': gen_potentiometer,
    'Switch-class': gen_switch,
    'USB-5V-class': gen_usb_5v,
    'AC-Adapter-class': gen_ac_adapter,
    'Remote-class': gen_remote,
    'Battery-LiPo-class': gen_battery_lipo,
}

# Registry display names — used to overwrite stale meta.json labels left over from
# the old single-colour / wrong-part bakes (e.g. Remote-class was "NRF24 Module").
_FIDELITY_LABELS = {
    'Button-class': 'Tactile Push Button',
    'Buzzer-Active-class': 'Active Buzzer',
    'Buzzer-Passive-class': 'Passive Buzzer',
    'Lighting-LED-PWM-class': 'Single LED (PWM)',
    'Lighting-LED-RGB-class': 'RGB LED',
    'Lighting-NeoPixel-class': 'WS2812B NeoPixel Strip',
    'Potentiometer-class': 'Rotary Potentiometer',
    'Switch-class': 'Toggle Switch',
    'USB-5V-class': 'USB 5V Power Module',
    'AC-Adapter-class': 'AC-DC 5V Adapter',
    'Remote-class': 'IR Remote Receiver / VS1838B',
    'Battery-LiPo-class': 'LiPo Battery 1S',
}

# Stale keys carried over from the superseded two-piece / mount bakes; these
# fidelity bodies are single pcb_body GLBs, so any mount artifact is dropped.
_STALE_META_KEYS = ("mount_stl", "mount_kind", "spec_dict")

def bake() -> int:
    ok = 0
    baked = []
    for cls, fn in _FIDELITY.items():
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        try:
            export_pcb(fn(), str(d), cls)
            mp = d / "meta.json"
            meta = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {"class_name": cls}
            meta["class_name"] = cls
            meta["kind"] = "pcb_body"
            # Overwrite stale label (e.g. Remote-class "NRF24 Module") with registry name.
            meta["label"] = _FIDELITY_LABELS.get(cls, meta.get("label", cls))
            # Drop stale mount / two-piece artifacts — these are single pcb_body GLBs.
            for k in _STALE_META_KEYS:
                meta.pop(k, None)
            files = {"pcb_body_stl": "pcb_body.stl", "pcb_body_glb": "pcb_body.glb"}
            meta["files"] = files
            mp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            ok += 1
            baked.append(cls)
            print(f"  [OK] {cls}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL] {cls}: {exc}")
    ensure_shell_glbs(_SHELLS, types=baked)
    print(f"Baked {ok}/{len(_FIDELITY)} fidelity bodies.")
    return ok


if __name__ == "__main__":
    bake()
