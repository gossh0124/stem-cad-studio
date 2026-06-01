"""Validation helpers for v3 embedded host_structure dict schema."""
from __future__ import annotations

_HOST_KINDS = {"water_tank", "chassis", "wearable_body", "external_body"}
_FACES = {"top", "bottom", "left", "right", "front", "back"}


def validate_host_structure(hs: dict, class_name: str = "") -> None:
    """Raise ValueError on malformed v3 host_structure dict.

    Validates:
      - kind is one of the known host kinds
      - entry_port.face is a valid face literal
      - entry_port.u and entry_port.v are within [0.0, 1.0]
    """
    if hs.get("kind") not in _HOST_KINDS:
        raise ValueError(
            f"{class_name}: host_structure.kind must be one of "
            f"{_HOST_KINDS}, got {hs.get('kind')!r}"
        )
    ep = hs.get("entry_port", {})
    if ep.get("face") not in _FACES:
        raise ValueError(
            f"{class_name}: entry_port.face must be one of "
            f"{_FACES}, got {ep.get('face')!r}"
        )
    for key in ("u", "v"):
        if key not in ep:
            raise ValueError(
                f"{class_name}: entry_port.{key} is missing (must be in [0,1])"
            )
        val = ep[key]
        if not (0.0 <= val <= 1.0):
            raise ValueError(
                f"{class_name}: entry_port.{key}={val} out of [0,1]"
            )
