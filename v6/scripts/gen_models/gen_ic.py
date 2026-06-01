"""
gen_ic.py - build123d generators for IC packages.

Shape types: ic-dip, ic-soic, ic-qfp, ic-module

Dimension sources (cross-verified):
  - JEDEC MS-001 (DIP), MS-012 (SOIC narrow), MS-013 (SOIC wide), MS-026 (QFP)
  - IPC-7351B land pattern guidelines
  - Espressif ESP-WROOM-32 datasheet v3.4 (module)
"""

from __future__ import annotations

import logging
from pathlib import Path

from v6.scripts.gen_models.generators import register_generator

logger = logging.getLogger(__name__)

# ─── Shared constants (JEDEC / IPC standard values) ─────────────────────────
# DIP: JEDEC MS-001  (300-mil / 600-mil row spacing)
DIP_BODY_H = 3.3          # mm - body height (JEDEC typ)
DIP_LEAD_W = 0.46         # mm - lead width (JEDEC nom 18 mil)
DIP_LEAD_THICK = 0.20     # mm - lead material thickness
DIP_LEAD_BELOW = 3.3      # mm - lead length below body (to PCB)
DIP_NOTCH_R = 0.8         # mm - pin-1 semicircular notch radius
DIP_NOTCH_DEPTH = 0.5     # mm - notch depth into body top

# SOIC: JEDEC MS-012 (narrow, 150-mil body) / MS-013 (wide, 300-mil)
SOIC_BODY_H = 1.75        # mm - body height (JEDEC typ)
SOIC_LEAD_W = 0.40        # mm - lead width
SOIC_LEAD_LEN = 0.72      # mm - gull-wing foot length
SOIC_LEAD_THICK = 0.15    # mm

# QFP: JEDEC MS-026
QFP_BODY_H = 1.60         # mm - body height (JEDEC typ LQFP)
QFP_LEAD_W = 0.30         # mm - lead width (0.5mm pitch)
QFP_LEAD_LEN = 0.60       # mm - foot length
QFP_LEAD_THICK = 0.12     # mm


def _export(part, output_path: Path) -> Path:
    """Export a build123d Part to STEP, creating parent dirs."""
    from build123d import export_step
    output_path.parent.mkdir(parents=True, exist_ok=True)
    export_step(part, str(output_path))
    logger.info("Exported STEP: %s", output_path)
    return output_path


# ─── ic-dip ─────────────────────────────────────────────────────────────────

@register_generator("ic-dip")
def gen_ic_dip(variant: dict, output_path: Path) -> Path:
    """DIP IC package - JEDEC MS-001.

    Params: pins (8-40), pitch (2.54mm std), rows (2)
    Row spacing: 7.62mm (300mil) for pins<=28, 15.24mm (600mil) for pins>28.
    """
    from build123d import (
        Box, Cylinder, BuildPart, Pos,
        Align, Mode,
    )

    pins = variant.get("pins", 8)
    pitch = variant.get("pitch", 2.54)
    rows = variant.get("rows", 2)
    pins_per_side = pins // rows

    # Body dimensions from JEDEC MS-001
    row_spacing = 7.62 if pins <= 28 else 15.24  # 300mil or 600mil
    body_l = (pins_per_side - 1) * pitch + 2.0   # length along pin row
    body_w = row_spacing - 1.0                    # narrower than row spacing
    body_h = DIP_BODY_H

    with BuildPart() as bp:
        # Main body (dark epoxy)
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Pin-1 notch (semicircular on top face, -X end)
        notch_x = -body_l / 2 + DIP_NOTCH_R + 0.3
        Cylinder(DIP_NOTCH_R, DIP_NOTCH_DEPTH,
                 align=(Align.CENTER, Align.CENTER, Align.MAX),
                 mode=Mode.SUBTRACT).locate(
            Pos(notch_x, 0, body_h))

        # Generate leads on both sides
        for side in range(rows):
            y_sign = -1 if side == 0 else 1
            y_base = y_sign * row_spacing / 2
            for i in range(pins_per_side):
                x_pos = -((pins_per_side - 1) * pitch / 2) + i * pitch
                # Vertical lead segment
                Box(DIP_LEAD_W, DIP_LEAD_THICK, DIP_LEAD_BELOW + body_h * 0.3,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                    Pos(x_pos, y_base, -DIP_LEAD_BELOW))
                # Horizontal foot on PCB
                Box(DIP_LEAD_W, DIP_LEAD_THICK * 2, DIP_LEAD_THICK,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                    Pos(x_pos, y_base, -DIP_LEAD_BELOW))

    return _export(bp.part, output_path)


# ─── ic-soic ────────────────────────────────────────────────────────────────

@register_generator("ic-soic")
def gen_ic_soic(variant: dict, output_path: Path) -> Path:
    """SOIC package - JEDEC MS-012 (narrow) / MS-013 (wide).

    Params: pins (8-28), gull-wing leads.
    Body width: 3.9mm (narrow <=16 pin), 7.5mm (wide >16 pin).
    """
    from build123d import (
        Box, BuildPart, Pos, Align, Mode,
    )

    pins = variant.get("pins", 8)
    pitch = variant.get("pitch", 1.27)
    if pins == 0:
        pins = 8  # generic fallback

    pins_per_side = pins // 2
    is_wide = pins > 16
    body_w = 7.50 if is_wide else 3.90   # JEDEC MS-012 vs MS-013
    body_l = max((pins_per_side - 1) * pitch + 1.5, 4.0)
    body_h = SOIC_BODY_H
    span = body_w + 2 * SOIC_LEAD_LEN  # total pin span

    with BuildPart() as bp:
        # Main body
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Pin-1 dot (shallow cylinder subtraction)
        dot_x = -body_l / 2 + 0.8
        dot_y = -body_w / 2 + 0.8
        Box(0.5, 0.5, 0.1, mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(dot_x, dot_y, body_h))

        # Gull-wing leads
        for side in range(2):
            y_sign = -1 if side == 0 else 1
            y_body_edge = y_sign * body_w / 2
            for i in range(pins_per_side):
                x_pos = -((pins_per_side - 1) * pitch / 2) + i * pitch
                # Horizontal foot
                Box(SOIC_LEAD_W, SOIC_LEAD_LEN, SOIC_LEAD_THICK,
                    align=(Align.CENTER,
                           Align.MIN if side == 1 else Align.MAX,
                           Align.MIN)).locate(
                    Pos(x_pos, y_body_edge, 0))
                # Vertical knee
                Box(SOIC_LEAD_W, SOIC_LEAD_THICK, body_h * 0.5,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                    Pos(x_pos,
                        y_body_edge + y_sign * SOIC_LEAD_LEN * 0.7,
                        SOIC_LEAD_THICK))

    return _export(bp.part, output_path)


# ─── ic-qfp ─────────────────────────────────────────────────────────────────

@register_generator("ic-qfp")
def gen_ic_qfp(variant: dict, output_path: Path) -> Path:
    """QFP package - JEDEC MS-026 (quad flat pack).

    Params: pins (28-100+), 4-side gull-wing leads.
    Pitch: 0.5mm (<80 pin) or 0.65mm.
    """
    from build123d import (
        Box, BuildPart, Pos, Align, Mode,
    )

    pins = variant.get("pins", 32)
    pitch = variant.get("pitch", 0.5 if pins > 44 else 0.65)
    pins_per_side = pins // 4

    # Body sizing from JEDEC MS-026 tables
    body_side = max((pins_per_side - 1) * pitch + 2.0, 5.0)
    body_h = QFP_BODY_H
    span = body_side + 2 * QFP_LEAD_LEN

    with BuildPart() as bp:
        # Main body (square)
        Box(body_side, body_side, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Pin-1 dot
        Box(0.4, 0.4, 0.1, mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.CENTER, Align.MAX)).locate(
            Pos(-body_side / 2 + 0.8, -body_side / 2 + 0.8, body_h))

        # Leads on all 4 sides
        for face_idx in range(4):
            for i in range(pins_per_side):
                offset = -((pins_per_side - 1) * pitch / 2) + i * pitch
                edge = body_side / 2

                if face_idx == 0:    # -Y side
                    bx, by = offset, -edge - QFP_LEAD_LEN / 2
                elif face_idx == 1:  # +X side
                    bx, by = edge + QFP_LEAD_LEN / 2, offset
                elif face_idx == 2:  # +Y side
                    bx, by = -offset, edge + QFP_LEAD_LEN / 2
                else:                # -X side
                    bx, by = -edge - QFP_LEAD_LEN / 2, -offset

                if face_idx in (0, 2):
                    Box(QFP_LEAD_W, QFP_LEAD_LEN, QFP_LEAD_THICK,
                        align=(Align.CENTER, Align.CENTER, Align.MIN)
                        ).locate(Pos(bx, by, 0))
                else:
                    Box(QFP_LEAD_LEN, QFP_LEAD_W, QFP_LEAD_THICK,
                        align=(Align.CENTER, Align.CENTER, Align.MIN)
                        ).locate(Pos(bx, by, 0))

    return _export(bp.part, output_path)


# ─── ic-module ──────────────────────────────────────────────────────────────

@register_generator("ic-module")
def gen_ic_module(variant: dict, output_path: Path) -> Path:
    """Shielded RF module (ESP-WROOM-32 style).

    Dimensions: Espressif ESP-WROOM-32 datasheet v3.4
    Body: 25.5 x 18.0 x 3.1 mm, metal shield + antenna area.
    """
    from build123d import (
        Box, BuildPart, Pos, Align, Mode,
    )

    # ESP-WROOM-32 datasheet v3.4 dimensions
    body_l = variant.get("bodyW", 25.5)
    body_w = variant.get("bodyD", 18.0)
    body_h = variant.get("bodyH", 3.1)
    shield_thick = 0.2   # metal shield thickness

    with BuildPart() as bp:
        # Metal shield (outer shell)
        Box(body_l, body_w, body_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

        # Hollow interior (subtract inner volume)
        Box(body_l - shield_thick * 2,
            body_w - shield_thick * 2,
            body_h - shield_thick,
            mode=Mode.SUBTRACT,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(0, 0, shield_thick))

        # Antenna PCB area (extend beyond shield, FR4 material)
        ant_l = 5.0   # antenna section length
        Box(ant_l, body_w - 2.0, 0.8,
            align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
            Pos(body_l / 2 + ant_l / 2 - 1.0, 0, 0))

        # Castellated pads (simplified as small boxes along edges)
        pad_pitch = 1.27
        pad_count_side = int((body_w - 4.0) / pad_pitch)
        for i in range(pad_count_side):
            y_pos = -(pad_count_side - 1) * pad_pitch / 2 + i * pad_pitch
            for x_sign in (-1, 1):
                x_pos = x_sign * body_l / 2
                Box(0.5, 0.8, body_h * 0.8,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)).locate(
                    Pos(x_pos, y_pos, 0))

    return _export(bp.part, output_path)
