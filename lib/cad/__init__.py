"""lib/cad — 3D CAD 殼體生成層（Phase C）。

引擎：build123d (OCCT B-rep)
依賴：lib/pcb/ 的 PCBSpec 權威座標數據

模組：
  shell.py        — PCB enclosure 殼體生成（單件 + 兩件式）
  tessellation.py — STL 高密度 tessellation
"""
from .shell import (
    build_pcb_enclosure,
    build_pcb_two_piece,
    compute_two_piece_spec,
    build_assembly_from_scene,
    EnclosureSpec,
    TwoPieceSpec,
    AssemblySpec,
)
from .tessellation import export_step, export_stl_high_density
from .mounts import (
    ServoBracketSpec, DCMotorClampSpec, NEMA17FlangeSpec,
    WaterPumpSleeveSpec, SpeakerGrillSpec,
    build_servo_sg90_bracket,
    build_dc_motor_clamp,
    build_nema17_flange,
    build_water_pump_sleeve,
    build_speaker_grill,
    ALL_MOUNTS,
)
# component_bodies imports build123d eagerly (heavy OCCT dep). Lazy-load its
# symbols via PEP 562 so `import lib.cad` and non-geometry submodules (e.g.
# mounts Spec dataclasses, tests/test_cad_mounts.py) stay importable without
# build123d. Accessing any symbol below imports component_bodies on demand,
# raising loudly if build123d is genuinely absent at use time (no silent fallback).
_LAZY_COMPONENT_BODIES = {
    'gen_body_motor_dc': 'gen_motor_dc',
    'gen_body_motor_servo': 'gen_motor_servo',
    'gen_body_motor_stepper': 'gen_motor_stepper',
    'gen_pump_water': 'gen_pump_water',
    'gen_speaker': 'gen_speaker',
    'gen_l298n': 'gen_l298n',
    'COMPONENT_BODY_GEN_MAP': '_GEN_MAP',
    'bake_component_bodies': 'bake_all',
}


def __getattr__(name):
    src = _LAZY_COMPONENT_BODIES.get(name)
    if src is not None:
        from . import component_bodies
        return getattr(component_bodies, src)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'build_pcb_enclosure',
    'build_pcb_two_piece',
    'compute_two_piece_spec',
    'build_assembly_from_scene',
    'EnclosureSpec',
    'TwoPieceSpec',
    'AssemblySpec',
    'export_step',
    'export_stl_high_density',
    # Tier 4 機械接合件
    'ServoBracketSpec', 'DCMotorClampSpec', 'NEMA17FlangeSpec',
    'WaterPumpSleeveSpec', 'SpeakerGrillSpec',
    'build_servo_sg90_bracket',
    'build_dc_motor_clamp',
    'build_nema17_flange',
    'build_water_pump_sleeve',
    'build_speaker_grill',
    'ALL_MOUNTS',
    # Component body meshes (Phase 2a C-1, salvaged from V2)
    'gen_body_motor_dc',
    'gen_body_motor_servo',
    'gen_body_motor_stepper',
    'gen_pump_water',
    'gen_speaker',
    'gen_l298n',
    'COMPONENT_BODY_GEN_MAP',
    'bake_component_bodies',
]
