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
    build_assembly_two_piece,
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

__all__ = [
    'build_pcb_enclosure',
    'build_pcb_two_piece',
    'compute_two_piece_spec',
    'build_assembly_two_piece',
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
]
