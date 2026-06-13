"""Phase 2a C-1 gate: every procedural component-body mesh (lib/cad/component_bodies)
builds a valid non-degenerate solid whose footprint is in the ballpark of the SSOT
COMPONENT_REGISTRY dims. Guards the 12 build123d gen functions against regressions —
no-fallback: each must produce real geometry, never an empty/degenerate part.
"""
import pytest

pytest.importorskip("build123d")  # tests build123d component-body gen functions (lib.cad.component_bodies)

from lib.registry import COMPONENT_REGISTRY

# The 12 classes that lacked a PCB-body mesh and now have a procedural one.
_EXPECTED = {
    "Motor-DC-class", "Motor-Servo-class", "Motor-Stepper-class", "Pump-Water-class",
    "Speaker-class", "L298N-Driver-class", "Mist-Atomizer-class", "Mist-Ultrasonic-class",
    "Sensor-MSGEQ7-class", "Lighting-LED-Strip-class", "Switch-Generic-class", "USB-Adapter-class",
}


def _all_procedural():
    """Every procedural body across the plain + colour maps.

    Colour-routed classes (Motor-DC, Pump-Water) live in _GEN_MAP_COLORED, and
    some (Battery-AA) are colour-only. The C-1 gate covers the union so a body
    isn't dropped from the guard just because it moved to the colour map.
    """
    import lib.cad.component_bodies as cb
    return {**cb._GEN_MAP, **cb._GEN_MAP_COLORED}


def test_gen_map_covers_the_twelve():
    missing = _EXPECTED - set(_all_procedural())
    assert not missing, f"procedural bodies missing for: {sorted(missing)}"


@pytest.mark.parametrize("cls", sorted(_EXPECTED))
def test_body_builds_valid_solid(cls):
    fn, _label = _all_procedural()[cls]
    part = fn()
    sz = part.bounding_box().size
    # Non-degenerate in every axis (real geometry, not a flat/empty part).
    assert sz.X > 1 and sz.Y > 1 and sz.Z > 1, f"{cls}: degenerate bbox ({sz.X},{sz.Y},{sz.Z})"
    assert part.volume > 1.0, f"{cls}: empty/near-zero volume {part.volume}"
    # Footprint in the ballpark of the SSOT registry dims (protruding features allowed).
    spec = COMPONENT_REGISTRY[cls]
    for got, target, axis in ((sz.X, spec.length_mm, "L"), (sz.Y, spec.width_mm, "W")):
        assert 0.5 * target <= got <= 1.8 * target, \
            f"{cls} {axis}: bbox {got:.1f}mm far from registry footprint {target}mm"
