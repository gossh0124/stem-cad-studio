"""Wiring subsystem -- consolidated from flat modules.

Backward-compatible re-exports so ``from lib.wiring import X`` keeps working.
Sub-module direct imports (e.g. ``from lib.wiring.csp import csp_allocate``)
are also supported.
"""

from .engine import (  # noqa: F401
    PinNeed,
    PinAllocationError,
    PIN_POOLS,
    COMP_PIN_NEEDS,
    COMP_LIBS,
    WIRING_TEMPLATES,
    normalize_comp,
    normalize_brain,
    normalize_comps,
    WireExtra,
    WiringTemplate,
    allocate_pins,
    resolve_wiring,
    to_json,
)
from .constants import MCU_POWER_PASSIVES  # noqa: F401
from .csp import csp_allocate  # noqa: F401
from .notes import generate_wiring_notes  # noqa: F401
from .validate import (  # noqa: F401
    WiringIssue,
    validate_wiring,
    resolve_wiring_pin_level,
    ssot_pin_info,
)

__all__ = [
    # constants
    "MCU_POWER_PASSIVES",
    # engine
    "PinNeed", "PinAllocationError", "PIN_POOLS", "COMP_PIN_NEEDS", "COMP_LIBS", "WIRING_TEMPLATES",
    "normalize_comp", "normalize_brain", "normalize_comps",
    "WireExtra", "WiringTemplate",
    "allocate_pins", "resolve_wiring", "to_json",
    # csp
    "csp_allocate",
    # notes
    "generate_wiring_notes",
    # validate
    "WiringIssue", "validate_wiring", "resolve_wiring_pin_level", "ssot_pin_info",
]
