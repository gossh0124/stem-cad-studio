"""
gen_conn.py - build123d generators for connector components.

Shape types: conn-header-male, conn-header-female, conn-usb-micro,
             conn-usb-c, conn-usb-b, conn-screw-terminal, conn-barrel-jack

Dimension sources (cross-verified):
  - IPC-7351B land pattern standard
  - Molex 22-28-4xxx (KK254 pin header) datasheet
  - USB-IF mechanical spec (Micro-B: USB 2.0 Fig 4-1, Type-C: USB 3.1 Fig 3-1)
  - Phoenix Contact 1935161 (screw terminal 5.08mm)
  - CUI PJ-102A (barrel jack 2.1mm)
"""

from __future__ import annotations

import logging
from pathlib import Path

from v6.scripts.gen_models.generators import register_generator

logger = logging.getLogger(__name__)

# ─── Pin header constants (Molex KK254 / generic 2.54mm) ────────────────────
HDR_PITCH = 2.54           # mm - standard 100mil pitch
HDR_PIN_W = 0.64           # mm - pin cross-section (square, 25mil)
HDR_PIN_ABOVE = 6.0        # mm - pin protrusion above housing
HDR_PIN_BELOW = 3.0        # mm - pin protrusion below (through PCB)
HDR_HOUSING_H = 2.54       # mm - plastic housing height
HDR_HOUSING_PAD = 0.5      # mm - housing overhang beyond outer pins

# Female socket constants
FSKT_SOCKET_DEPTH = 3.0    # mm - socket cavity depth
FSKT_WALL = 0.5            # mm - wall thickness

# USB Micro-B: USB 2.0 spec Table 4-1
USB_MICRO_W = 6.85         # mm - shell width
USB_MICRO_D = 5.60         # mm - shell depth
USB_MICRO_H = 1.80         # mm - shell height (without flange)

# USB Type-C: USB 3.1 Figure 3-1
USB_C_W = 8.94             # mm - shell width
USB_C_D = 7.30             # mm - shell depth
USB_C_H = 3.26             # mm - shell height

# USB Type-B (full size): USB 2.0 spec Table 5-4
USB_B_W = 12.0             # mm
USB_B_D = 16.0             # mm (includes PCB mount overhang)
USB_B_H = 11.0             # mm

# Screw terminal: Phoenix Contact 1935161 (5.08mm)
SCRW_BODY_H = 8.6          # mm - body height
SCRW_BODY_D = 7.5          # mm - body depth
SCRW_WIRE_HOLE = 2.5       # mm - wire entry diameter

# Barrel jack: CUI PJ-102A (2.1mm center pin)
BARREL_W = 14.0            # mm - body length
BARREL_D = 9.0             # mm - body width
BARREL_H = 11.0            # mm - body height
BARREL_OUTER_D = 6.3       # mm - outer barrel diameter
BARREL_INNER_D = 2.1       # mm - center pin diameter


def _export(part, output_path: Path) -> Path:
    from build123d import export_step
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_step(part, str(output_path))
    logger.info("Exported STEP: %s", output_path)
    return output_path


# ─── conn-header-male ───────────────────────────────────────────────────────

@register_generator("conn-header-male")
def gen_conn_header_male(variant: dict, output_path: Path) -> Path:
    """Male pin header (through-hole, 2.54mm pitch).

    Params: pins, pitch, rows (1 or 2)
    """
    from build123d import Box, BuildPart, Pos, Align

    pins = variant.get("pins", 8)
    pitch = variant.get("pitch", HDR_PITCH)
    rows = variant.get("rows", 1)
    cols = pins // rows if rows > 1 else pins

    housing_l = (cols - 1) * pitch + HDR_HOUSING_PAD * 2 + HDR_PIN_W
    housing_w = (rows - 1) * pitch + HDR_HOUSING_PAD * 2 + HDR_PIN_W
    housing_h = HDR_HOUSING_H

    with BuildPart() as bp:
        # Plastic housing
        Box(housing_l, housing_w, housing_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Gold-plated square pins
        for row in range(rows):
            y_pos = -(rows - 1) * pitch / 2 + row * pitch
            for col in range(cols):
                x_pos = -(cols - 1) * pitch / 2 + col * pitch
                # Pin above housing
                Box(HDR_PIN_W, HDR_PIN_W, HDR_PIN_ABOVE,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                    Pos(x_pos, y_pos, housing_h))
                # Pin below housing (through PCB)
                Box(HDR_PIN_W, HDR_PIN_W, HDR_PIN_BELOW,
                    align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                    Pos(x_pos, y_pos, 0))

    return _export(bp.part, output_path)


# ─── conn-header-female ─────────────────────────────────────────────────────

@register_generator("conn-header-female")
def gen_conn_header_female(variant: dict, output_path: Path) -> Path:
    """Female pin header socket (through-hole, 2.54mm pitch).

    Params: pins, pitch, rows (1 or 2)
    """
    from build123d import Box, BuildPart, Pos, Align, Mode

    pins = variant.get("pins", 8)
    pitch = variant.get("pitch", HDR_PITCH)
    rows = variant.get("rows", 1)
    cols = pins // rows if rows > 1 else pins

    housing_l = (cols - 1) * pitch + FSKT_WALL * 2 + HDR_PIN_W + 0.5
    housing_w = (rows - 1) * pitch + FSKT_WALL * 2 + HDR_PIN_W + 0.5
    housing_h = HDR_HOUSING_H + FSKT_SOCKET_DEPTH

    with BuildPart() as bp:
        # Outer housing
        Box(housing_l, housing_w, housing_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Socket cavities (subtract)
        for row in range(rows):
            y_pos = -(rows - 1) * pitch / 2 + row * pitch
            for col in range(cols):
                x_pos = -(cols - 1) * pitch / 2 + col * pitch
                Box(1.0, 1.0, FSKT_SOCKET_DEPTH + 0.1,
                    mode=Mode.SUBTRACT,
                    align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                    Pos(x_pos, y_pos, housing_h))

        # Through-hole pins below
        for row in range(rows):
            y_pos = -(rows - 1) * pitch / 2 + row * pitch
            for col in range(cols):
                x_pos = -(cols - 1) * pitch / 2 + col * pitch
                Box(HDR_PIN_W, HDR_PIN_W, HDR_PIN_BELOW,
                    align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                    Pos(x_pos, y_pos, 0))

    return _export(bp.part, output_path)


# ─── conn-usb-micro ─────────────────────────────────────────────────────────

@register_generator("conn-usb-micro")
def gen_conn_usb_micro(variant: dict, output_path: Path) -> Path:
    """Micro-USB Type-B connector (SMD, USB 2.0 spec Table 4-1)."""
    from build123d import Box, BuildPart, Pos, Align, Mode

    with BuildPart() as bp:
        # Metal shell
        Box(USB_MICRO_W, USB_MICRO_D, USB_MICRO_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Trapezoidal port void (simplified as smaller box)
        Box(USB_MICRO_W - 1.2, USB_MICRO_D - 1.5, USB_MICRO_H - 0.4,
            mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.MIN, Align.MIN)).locate(
            Pos(0, -USB_MICRO_D / 2, 0.2))

        # Shell flange / mounting tabs
        for x_sign in (-1, 1):
            Box(1.5, USB_MICRO_D + 1.0, 0.3,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (USB_MICRO_W / 2 + 0.5), 0, 0))

    return _export(bp.part, output_path)


# ─── conn-usb-c ─────────────────────────────────────────────────────────────

@register_generator("conn-usb-c")
def gen_conn_usb_c(variant: dict, output_path: Path) -> Path:
    """USB Type-C connector (USB 3.1 spec Figure 3-1)."""
    from build123d import Box, BuildPart, Pos, Align, Mode, Cylinder

    with BuildPart() as bp:
        # Metal shell (rounded profile simplified as box)
        Box(USB_C_W, USB_C_D, USB_C_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Oval port void
        Box(USB_C_W - 1.6, USB_C_D - 2.0, USB_C_H - 0.8,
            mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.MIN, Align.CENTER)).locate(
            Pos(0, -USB_C_D / 2, USB_C_H / 2))

        # Rounded port ends (cylinders at left/right of opening)
        for x_sign in (-1, 1):
            Cylinder(
                (USB_C_H - 0.8) / 2, 0.5,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
                mode=Mode.SUBTRACT,
            ).locate(
                Pos(x_sign * (USB_C_W / 2 - 1.2), -USB_C_D / 2 + 0.5,
                    USB_C_H / 2))

        # Mounting shield tabs
        for x_sign in (-1, 1):
            Box(1.0, USB_C_D + 0.5, 0.3,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (USB_C_W / 2 + 0.3), 0, 0))

    return _export(bp.part, output_path)


# ─── conn-usb-b ─────────────────────────────────────────────────────────────

@register_generator("conn-usb-b")
def gen_conn_usb_b(variant: dict, output_path: Path) -> Path:
    """USB Type-B (full size) connector (USB 2.0 spec Table 5-4)."""
    from build123d import Box, BuildPart, Pos, Align, Mode

    with BuildPart() as bp:
        # Metal shell
        Box(USB_B_W, USB_B_D, USB_B_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Port void (square with beveled top)
        Box(USB_B_W - 2.0, USB_B_D * 0.6, USB_B_H - 2.0,
            mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.MIN, Align.CENTER)).locate(
            Pos(0, -USB_B_D / 2, USB_B_H / 2))

        # Internal tongue
        Box(USB_B_W - 4.0, USB_B_D * 0.3, 1.5,
            align=(Align.CENTER, Align.MIN, Align.MIN)).locate(
            Pos(0, -USB_B_D / 2 + 1.0, USB_B_H * 0.3))

        # PCB mounting legs
        for x_sign in (-1, 1):
            Box(0.8, 2.0, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * (USB_B_W / 2 - 1.0), USB_B_D / 2 - 1.0, 0))

    return _export(bp.part, output_path)


# ─── conn-screw-terminal ────────────────────────────────────────────────────

@register_generator("conn-screw-terminal")
def gen_conn_screw_terminal(variant: dict, output_path: Path) -> Path:
    """Screw terminal block (Phoenix Contact 1935161 style, 5.08mm pitch)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align, Mode

    pins = variant.get("pins", 2)
    pitch = variant.get("pitch", 5.08)

    body_l = (pins - 1) * pitch + pitch  # one pitch width per pin position
    body_d = SCRW_BODY_D
    body_h = SCRW_BODY_H

    with BuildPart() as bp:
        # Main body (green/blue plastic)
        Box(body_l, body_d, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Per-pin features
        for i in range(pins):
            x_pos = -(pins - 1) * pitch / 2 + i * pitch

            # Wire entry hole (front face)
            Cylinder(SCRW_WIRE_HOLE / 2, body_d * 0.3,
                     mode=Mode.SUBTRACT,
                     align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_pos, -body_d / 2, body_h * 0.5))

            # Screw head (top)
            Cylinder(1.5, 1.0,
                     align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_pos, 0, body_h))

            # Screw slot (subtract from screw head)
            Box(2.5, 0.5, 0.3, mode=Mode.SUBTRACT,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_pos, 0, body_h + 1.0))

            # Through-hole pin
            Box(0.8, 0.8, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_pos, body_d / 2 - 1.5, 0))

    return _export(bp.part, output_path)


# ─── conn-barrel-jack ───────────────────────────────────────────────────────

@register_generator("conn-barrel-jack")
def gen_conn_barrel_jack(variant: dict, output_path: Path) -> Path:
    """DC barrel jack (CUI PJ-102A style, 2.1mm center pin)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align, Mode

    with BuildPart() as bp:
        # Main body
        Box(BARREL_W, BARREL_D, BARREL_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Barrel opening (front face, cylindrical)
        Cylinder(BARREL_OUTER_D / 2, BARREL_D * 0.6,
                 mode=Mode.SUBTRACT,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, -BARREL_D / 2, BARREL_H * 0.5))

        # Center pin inside barrel
        Cylinder(BARREL_INNER_D / 2, BARREL_D * 0.4,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, -BARREL_D / 2 + 0.5, BARREL_H * 0.5))

        # PCB mounting pins (3 pins: tip, ring, switch)
        pin_positions = [
            (-BARREL_W / 2 + 2.0, BARREL_D / 2 - 1.0),
            (BARREL_W / 2 - 2.0, BARREL_D / 2 - 1.0),
            (0, BARREL_D / 2 - 1.0),
        ]
        for px, py in pin_positions:
            Box(0.8, 0.8, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(px, py, 0))

    return _export(bp.part, output_path)
