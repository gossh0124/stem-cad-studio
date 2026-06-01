"""
gen_passive.py - build123d generators for passive electronic components.

Shape types: cap-electrolytic, cap-ceramic, res-smd, crystal-hc49,
             led-tht, led-smd, buzzer

Dimension sources (cross-verified):
  - IPC-7351B land pattern standard (SMD passives)
  - Nichicon UVR / UVZ series (electrolytic capacitor)
  - Murata GRM series (ceramic cap, 0805/1206)
  - Yageo RC series (SMD resistor 0805)
  - HC-49/S: IEC 60444 crystal spec
  - Kingbright WP710A10 (5mm LED)
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


# ─── cap-electrolytic ───────────────────────────────────────────────────────

@register_generator("cap-electrolytic")
def gen_cap_electrolytic(variant: dict, output_path: Path) -> Path:
    """Radial electrolytic capacitor (Nichicon UVR series).

    Params: diameter (5-16mm), height from variant.
    """
    from build123d import Cylinder, Box, BuildPart, Pos, Align, Mode

    dia = variant.get("diameter", 8.0)
    height = variant.get("bodyH", dia * 1.5)
    lead_pitch = max(2.5, dia * 0.4)  # IPC-7351B standard

    with BuildPart() as bp:
        # Cylindrical body (aluminum sleeve)
        Cylinder(dia / 2, height,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Top vent scoring (K-mark, simplified as cross groove)
        Cylinder(dia / 2 - 0.5, 0.3, mode=Mode.SUBTRACT,
                 align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(0, 0, height))
        Box(dia - 1.5, 0.4, 0.3, mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(0, 0, height))

        # Polarity stripe (negative side, raised strip)
        Box(0.4, dia * 0.8, height * 0.7,
            align=(Align.MIN, Align.CENTER, Align.MIN)).locate(
            Pos(dia / 2 - 0.5, 0, height * 0.15))

        # Through-hole leads (positive longer)
        for i, x_sign in enumerate((-1, 1)):
            lead_h = 3.5 if i == 0 else 3.0  # anode slightly longer
            Box(0.5, 0.5, lead_h,
                align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * lead_pitch / 2, 0, 0))

    return _export(bp.part, output_path)


# ─── cap-ceramic ────────────────────────────────────────────────────────────

@register_generator("cap-ceramic")
def gen_cap_ceramic(variant: dict, output_path: Path) -> Path:
    """Ceramic SMD capacitor (Murata GRM, 0805/1206 package)."""
    from build123d import Box, BuildPart, Pos, Align

    # 0805 = 2.0 x 1.25 x 0.6 mm (IPC-7351B)
    body_l = variant.get("bodyW", 2.0)
    body_w = variant.get("bodyD", 1.25)
    body_h = variant.get("bodyH", 0.6)
    cap_len = 0.5  # end-cap metallization length

    with BuildPart() as bp:
        # Ceramic body (tan/brown)
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Metal end-caps
        for x_sign in (-1, 1):
            Box(cap_len, body_w + 0.05, body_h + 0.05,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (body_l / 2 - cap_len / 2), 0, 0))

    return _export(bp.part, output_path)


# ─── res-smd ────────────────────────────────────────────────────────────────

@register_generator("res-smd")
def gen_res_smd(variant: dict, output_path: Path) -> Path:
    """SMD chip resistor (Yageo RC series, 0805 package)."""
    from build123d import Box, BuildPart, Pos, Align

    body_l = variant.get("bodyW", 2.0)
    body_w = variant.get("bodyD", 1.25)
    body_h = variant.get("bodyH", 0.5)
    cap_len = 0.4

    with BuildPart() as bp:
        # Dark alumina body
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Metal end-caps (Sn-plated)
        for x_sign in (-1, 1):
            Box(cap_len, body_w + 0.02, body_h + 0.02,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (body_l / 2 - cap_len / 2), 0, 0))

    return _export(bp.part, output_path)


# ─── crystal-hc49 ──────────────────────────────────────────────────────────

@register_generator("crystal-hc49")
def gen_crystal_hc49(variant: dict, output_path: Path) -> Path:
    """HC-49/S crystal oscillator (IEC 60444)."""
    from build123d import Box, Cylinder, BuildPart, Pos, Align

    body_l = variant.get("bodyW", 11.05)
    body_w = variant.get("bodyD", 4.65)
    body_h = variant.get("bodyH", 3.50)

    with BuildPart() as bp:
        # Metal can (rounded ends simplified as box)
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Seam line (thin raised strip around middle height)
        Box(body_l + 0.1, body_w + 0.1, 0.2,
            align=(Align.CENTER, Align.CENTER, Align.CENTER)).locate(
            Pos(0, 0, body_h / 2))

        # 2 leads (4.88mm pitch per IEC 60444)
        lead_pitch = 4.88
        for x_sign in (-1, 1):
            Cylinder(0.25, 3.5,
                     align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * lead_pitch / 2, 0, 0))

    return _export(bp.part, output_path)


# ─── led-tht ───────────────────────────────────────────────────────────────

@register_generator("led-tht")
def gen_led_tht(variant: dict, output_path: Path) -> Path:
    """5mm through-hole LED (Kingbright WP710A10)."""
    from build123d import Cylinder, Sphere, BuildPart, Pos, Align

    dia = variant.get("diameter", 5.0)
    body_h = variant.get("bodyH", 8.6)  # total height to dome top
    base_h = body_h - dia / 2           # cylindrical portion
    lead_pitch = 2.54

    with BuildPart() as bp:
        # Cylindrical base
        Cylinder(dia / 2, base_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Dome top (hemisphere)
        Sphere(dia / 2,
               align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, base_h))

        # Flat cathode mark (small flange at base)
        Cylinder(dia / 2 + 0.3, 1.0,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # 2 leads (anode +, cathode -)
        for i, x_sign in enumerate((-1, 1)):
            lead_h = 25.0 if i == 0 else 22.0  # anode longer
            Cylinder(0.3, lead_h,
                     align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * lead_pitch / 2, 0, 0))

    return _export(bp.part, output_path)


# ─── led-smd ───────────────────────────────────────────────────────────────

@register_generator("led-smd")
def gen_led_smd(variant: dict, output_path: Path) -> Path:
    """SMD LED (0805 package)."""
    from build123d import Box, BuildPart, Pos, Align

    body_l = variant.get("bodyW", 2.0)
    body_w = variant.get("bodyD", 1.25)
    body_h = variant.get("bodyH", 0.8)

    with BuildPart() as bp:
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Lens window on top
        Box(body_l * 0.6, body_w * 0.6, 0.1,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, body_h))

        # End-cap pads
        for x_sign in (-1, 1):
            Box(0.4, body_w + 0.02, body_h + 0.02,
                align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                Pos(x_sign * (body_l / 2 - 0.2), 0, 0))

    return _export(bp.part, output_path)


# ─── buzzer ─────────────────────────────────────────────────────────────────

@register_generator("buzzer")
def gen_buzzer(variant: dict, output_path: Path) -> Path:
    """Piezo buzzer (12mm diameter, through-hole)."""
    from build123d import Cylinder, Box, BuildPart, Pos, Align, Mode

    dia = variant.get("diameter", 12.0)
    body_h = variant.get("bodyH", 9.5)

    with BuildPart() as bp:
        Cylinder(dia / 2, body_h,
                 align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Sound hole on top
        Cylinder(1.5, 1.0, mode=Mode.SUBTRACT,
                 align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(0, 0, body_h))

        # Polarity mark (+ symbol)
        Box(2.0, 0.3, 0.15,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(-dia / 4, 0, body_h))
        Box(0.3, 2.0, 0.15,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(-dia / 4, 0, body_h))

        # 2 leads
        for x_sign in (-1, 1):
            Cylinder(0.3, 3.5,
                     align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
                Pos(x_sign * 3.0, 0, 0))

    return _export(bp.part, output_path)
