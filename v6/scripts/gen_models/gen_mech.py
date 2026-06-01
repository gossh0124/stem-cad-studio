"""
gen_mech.py - build123d generators for mechanical & electromechanical parts.

Shape types: relay, button-tactile, pot-trimmer, pot-shaft,
  motor-dc, motor-servo, motor-stepper, vreg-to220,
  sensor-dome, mounting-hole

Dimension sources (cross-verified):
  - Songle SRD-05VDC-SL-C relay datasheet
  - Omron B3F-1000 (tactile switch)
  - Bourns 3296W (trimmer pot)
  - Alpha RV16AF-10 (panel pot)
  - Mabuchi FA-130 (DC motor)
  - Tower Pro SG90 (servo)
  - 28BYJ-48 (stepper)
  - JEDEC TO-220AB (voltage regulator)
  - HC-SR501 (PIR dome sensor)
"""

from __future__ import annotations

import logging
from pathlib import Path

from v6.scripts.gen_models.generators import register_generator

logger = logging.getLogger(__name__)


def _export(part, output_path: Path) -> Path:
    from build123d import export_step
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_step(part, str(output_path))
    logger.info("Exported STEP: %s", output_path)
    return output_path


# ─── relay ──────────────────────────────────────────────────────────────────

@register_generator("relay")
def gen_relay(variant: dict, output_path: Path) -> Path:
    """PCB relay (Songle SRD-05VDC-SL-C style)."""
    from build123d import Box, BuildPart, Pos, Align

    body_l = variant.get("bodyW", 19.0)
    body_w = variant.get("bodyD", 15.3)
    body_h = variant.get("bodyH", 15.5)

    with BuildPart() as bp:
        # Main body (blue/black plastic)
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Label area (slightly recessed on top)
        Box(body_l - 2.0, body_w - 2.0, 0.2,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))

        # 5 through-hole pins (2+3 pattern, 2.54mm grid)
        pin_positions = [
            (-7.5, -5.0), (-7.5, 5.0),
            (7.5, -5.0), (7.5, 0.0), (7.5, 5.0),
        ]
        for px, py in pin_positions:
            Box(0.6, 0.6, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(px, py, 0))

    return _export(bp.part, output_path)


# ─── button-tactile ─────────────────────────────────────────────────────────

@register_generator("button-tactile")
def gen_button_tactile(variant: dict, output_path: Path) -> Path:
    """6x6mm tactile pushbutton (Omron B3F-1000)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align

    body_w = variant.get("bodyW", 6.0)
    body_d = variant.get("bodyD", 6.0)
    body_h = variant.get("bodyH", 4.3)
    cap_dia = 3.5
    cap_h = 1.0

    with BuildPart() as bp:
        Box(body_w, body_d, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Round cap (actuator)
        Cylinder(cap_dia / 2, cap_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))

        # 4 leads (2 per side, 4.5mm apart)
        for x_sign in (-1, 1):
            for y_sign in (-1, 1):
                Box(0.5, 0.3, 3.5,
                    align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                    Pos(x_sign * 3.25, y_sign * 2.25, 0))

    return _export(bp.part, output_path)


# ─── pot-trimmer ────────────────────────────────────────────────────────────

@register_generator("pot-trimmer")
def gen_pot_trimmer(variant: dict, output_path: Path) -> Path:
    """Multi-turn trimmer pot (Bourns 3296W style)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align, Mode

    body_l = variant.get("bodyW", 9.53)
    body_w = variant.get("bodyD", 4.83)
    body_h = variant.get("bodyH", 11.55)

    with BuildPart() as bp:
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Adjustment screw (top)
        Cylinder(1.2, 0.5,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))
        Box(2.0, 0.5, 0.3, mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(0, 0, body_h + 0.5))

        # 3 leads (2.54mm pitch)
        for i in range(3):
            Box(0.5, 0.5, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos((i - 1) * 2.54, 0, 0))

    return _export(bp.part, output_path)


# ─── pot-shaft ──────────────────────────────────────────────────────────────

@register_generator("pot-shaft")
def gen_pot_shaft(variant: dict, output_path: Path) -> Path:
    """Panel-mount potentiometer (Alpha RV16AF style)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align

    body_dia = variant.get("diameter", 16.0)
    body_h = variant.get("bodyH", 6.5)
    shaft_dia = 6.0
    shaft_h = 15.0

    with BuildPart() as bp:
        Cylinder(body_dia / 2, body_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Shaft
        Cylinder(shaft_dia / 2, shaft_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))

        # Mounting nut hex (simplified as cylinder)
        Cylinder(body_dia / 2 + 1.0, 1.5,
                 align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(0, 0, body_h))

        # 3 leads
        for i in range(3):
            Box(0.5, 0.5, 3.5,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos((i - 1) * 5.0, body_dia / 2 - 2.0, 0))

    return _export(bp.part, output_path)


# ─── motor-dc ──────────────────────────────────────────────────────────────

@register_generator("motor-dc")
def gen_motor_dc(variant: dict, output_path: Path) -> Path:
    """DC motor (Mabuchi FA-130 style)."""
    from build123d import Cylinder, Box, BuildPart, Pos, Align

    body_l = variant.get("bodyW", 25.0)
    body_dia = variant.get("bodyD", 20.4)
    shaft_dia = 2.0
    shaft_len = 8.0

    with BuildPart() as bp:
        Cylinder(body_dia / 2, body_l,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Output shaft
        Cylinder(shaft_dia / 2, shaft_len,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_l))

        # Terminal tabs (rear)
        for x_sign in (-1, 1):
            Box(3.0, 0.5, 5.0,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * 4.0, 0, 0))

    return _export(bp.part, output_path)


# ─── motor-servo ────────────────────────────────────────────────────────────

@register_generator("motor-servo")
def gen_motor_servo(variant: dict, output_path: Path) -> Path:
    """Micro servo (Tower Pro SG90 datasheet)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align

    # SG90: 22.2 x 11.8 x 31.0 mm (with shaft)
    body_l = variant.get("bodyW", 22.2)
    body_w = variant.get("bodyD", 11.8)
    body_h = variant.get("bodyH", 22.7)

    with BuildPart() as bp:
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Mounting ears (extend +-X)
        Box(body_l + 10.0, body_w, 2.5,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h - 6.0))

        # Output shaft gear
        Cylinder(5.5, 4.0,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(-body_l / 2 + 6.0, 0, body_h))

        # Shaft nub
        Cylinder(2.0, 3.0,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(-body_l / 2 + 6.0, 0, body_h + 4.0))

        # Wire block (rear bottom)
        Box(5.0, body_w, 3.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(body_l / 2 - 3.0, 0, 0))

    return _export(bp.part, output_path)


# ─── motor-stepper ──────────────────────────────────────────────────────────

@register_generator("motor-stepper")
def gen_motor_stepper(variant: dict, output_path: Path) -> Path:
    """Stepper motor (28BYJ-48 datasheet)."""
    from build123d import Cylinder, Box, BuildPart, Pos, Align

    body_dia = variant.get("diameter", 28.0)
    body_h = variant.get("bodyH", 19.0)

    with BuildPart() as bp:
        Cylinder(body_dia / 2, body_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Mounting ears
        for x_sign in (-1, 1):
            Box(7.0, 0.8, body_h,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (body_dia / 2 + 3.0), 0, 0))

        # Output shaft
        Cylinder(2.5, 6.0,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))

        # 5-pin connector block (rear)
        Box(8.0, 5.0, 5.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, body_dia / 2 - 2.0, body_h * 0.3))

    return _export(bp.part, output_path)


# ─── vreg-to220 ────────────────────────────────────────────────────────────

@register_generator("vreg-to220")
def gen_vreg_to220(variant: dict, output_path: Path) -> Path:
    """TO-220 voltage regulator (JEDEC TO-220AB)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align, Mode

    body_l = variant.get("bodyW", 10.0)
    body_w = variant.get("bodyD", 4.5)
    body_h = variant.get("bodyH", 15.0)
    tab_h = 8.5

    with BuildPart() as bp:
        # Plastic body (lower portion)
        Box(body_l, body_w, body_h - tab_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Metal heatsink tab
        Box(body_l, 0.6, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Mounting hole in tab
        Cylinder(1.7, 1.0, mode=Mode.SUBTRACT,
                 align=(Align.CENTER, Align.CENTER, Align.CENTER)).locate(
            Pos(0, 0, body_h - 3.0))

        # 3 leads (2.54mm pitch)
        for i in range(3):
            Box(0.6, 0.5, 13.0,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos((i - 1) * 2.54, 0, 0))

    return _export(bp.part, output_path)


# ─── sensor-dome ────────────────────────────────────────────────────────────

@register_generator("sensor-dome")
def gen_sensor_dome(variant: dict, output_path: Path) -> Path:
    """PIR sensor with fresnel dome (HC-SR501 style)."""
    from build123d import Cylinder, Sphere, BuildPart, Pos, Align

    body_dia = variant.get("diameter", 24.0)
    body_h = variant.get("bodyH", 18.0)
    dome_dia = 23.0
    pcb_dia = 32.0

    with BuildPart() as bp:
        # PCB base (circular)
        Cylinder(pcb_dia / 2, 1.6,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Sensor housing
        Cylinder(body_dia / 2, body_h - dome_dia / 2,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, 1.6))

        # Fresnel dome (hemisphere)
        Sphere(dome_dia / 2,
               align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, 1.6 + body_h - dome_dia / 2))

        # 3 header pins
        for i in range(3):
            Cylinder(0.4, 7.0,
                     align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos((i - 1) * 2.54, pcb_dia / 2 - 5.0, 0))

    return _export(bp.part, output_path)


# ─── mounting-hole ──────────────────────────────────────────────────────────

@register_generator("mounting-hole")
def gen_mounting_hole(variant: dict, output_path: Path) -> Path:
    """PCB mounting hole with annular ring."""
    from build123d import Cylinder, BuildPart, Pos, Align, Mode

    hole_dia = variant.get("diameter", 3.2)
    pad_dia = variant.get("padDia", hole_dia + 2.0)

    with BuildPart() as bp:
        Cylinder(pad_dia / 2, 1.6,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        Cylinder(hole_dia / 2, 1.8, mode=Mode.SUBTRACT,
                 align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, -0.1))

    return _export(bp.part, output_path)
