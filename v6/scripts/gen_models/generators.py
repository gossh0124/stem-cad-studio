"""
generators.py - Generator registry hub for STEM AI 3D model pipeline.

Thin hub: defines GENERATORS dict and register_generator decorator,
then imports sub-modules which populate it via the decorator.

Sub-modules:
    gen_ic.py      - IC packages (ic-dip, ic-soic, ic-qfp, ic-module)
    gen_conn.py    - Connectors (header, USB, screw-terminal, barrel-jack)
    gen_passive.py - Passive components (cap, res, crystal, led, buzzer)
    gen_mech.py    - Mechanical parts (relay, button, pot, motor, vreg, sensor)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# ─── Generator registry ─────────────────────────────────────────────────────
# Maps shape_type str -> callable(variant, output_path) -> Path
GENERATORS: dict[str, Callable[[dict, Path], Path]] = {}


def register_generator(shape_type: str):
    """Decorator to register a model generator for a shape type."""
    def decorator(func: Callable[[dict, Path], Path]):
        GENERATORS[shape_type] = func
        return func
    return decorator


# ─── Import sub-modules to trigger registration ─────────────────────────────
# Each sub-module uses @register_generator at module level.
from v6.scripts.gen_models.gen_ic import *       # noqa: F401,F403
from v6.scripts.gen_models.gen_conn import *     # noqa: F401,F403
from v6.scripts.gen_models.gen_passive import *  # noqa: F401,F403
from v6.scripts.gen_models.gen_mech import *     # noqa: F401,F403
