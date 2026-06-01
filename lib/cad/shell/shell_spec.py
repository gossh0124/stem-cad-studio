"""lib/cad/shell/shell_spec.py — Shell dataclasses, constants, validation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, List, Optional

_FALLBACK_COMPONENT_H = 15.0
_LIP_Z_OFFSET = 0.3
_PIN_PITCH = 2.54
_DEFAULT_PIN_HEIGHT = 11.5
_MIN_WALL_MM = 1.5

_MATERIAL_YIELD_STRAIN: dict[str, float] = {
    "PLA":  0.02,
    "PETG": 0.04,
    "ABS":  0.06,
    "TPU":  0.15,
}
_SNAP_FIT_SAFETY_FACTOR = 0.7

_WIRE_DIA_MM = 1.5
_WIRE_GROOVE_CLEARANCE = 1.0
_WIRE_GROOVE_DEPTH = 1.5
_VENT_SLIT_W = 10.0
_VENT_SLIT_H = 1.5
_VENT_SLIT_GAP = 2.0
_DEFAULT_FILLET_R = 2.0

_TOP_DISPLAY_CLASSES = {
    "Display-OLED-class",
    "Display-LCD-class",
    "Display-EInk-class",
    "LED-Matrix-class",
    "Segment-Display-class",
}


def validate_snap_fit_stress(
    snap_arm_t: float,
    snap_arm_h: float,
    snap_lip_d: float,
    material: str = "PLA",
    E_mpa: float | None = None,
) -> dict:
    """PV5: snap-fit cantilever stress analysis. Returns dict with ok/suggestions."""
    _E_DEFAULTS = {"PLA": 3500, "PETG": 2000, "ABS": 2300, "TPU": 100}
    mat = material.upper()
    E = E_mpa or _E_DEFAULTS.get(mat, 2000)
    yield_strain = _MATERIAL_YIELD_STRAIN.get(mat, 0.03)

    strain_max = 3 * snap_arm_t * snap_lip_d / (2 * snap_arm_h ** 2)
    stress_max = strain_max * E
    utilization = strain_max / yield_strain if yield_strain > 0 else 999.0
    ok = utilization < _SNAP_FIT_SAFETY_FACTOR

    result: dict = {
        "ok": ok,
        "material": mat,
        "strain_pct": round(strain_max * 100, 2),
        "yield_strain_pct": round(yield_strain * 100, 1),
        "utilization_pct": round(utilization * 100, 1),
        "stress_mpa": round(stress_max, 1),
        "E_mpa": E,
    }
    if not ok:
        suggestions = []
        if snap_arm_h < 12:
            suggestions.append(f"增加 snap_arm_h（當前 {snap_arm_h}→建議 10~12mm）")
        if snap_lip_d > 0.3:
            suggestions.append(f"減少 snap_lip_d（當前 {snap_lip_d}→建議 0.3mm）")
        if snap_arm_t > 1.2:
            suggestions.append(f"減少 snap_arm_t（當前 {snap_arm_t}→建議 1.0~1.2mm）")
        if mat == "PLA":
            suggestions.append("改用 PETG（yield 4%，較 PLA 2% 韌性翻倍）")
        result["suggestions"] = suggestions
    return result


def _validate_wall_thickness(wall: float) -> float:
    """PV1: raise if wall < _MIN_WALL_MM."""
    if wall < _MIN_WALL_MM:
        raise ValueError(
            f"壁厚 {wall}mm 低於 FDM 安全下限 {_MIN_WALL_MM}mm，"
            f"請使用 ≥{_MIN_WALL_MM}mm（建議 2.0mm）"
        )
    return wall


@dataclass(frozen=True)
class EnclosureSpec:
    """Single-piece enclosure output spec."""
    outer_l: float
    outer_w: float
    outer_h: float
    inner_l: float
    inner_w: float
    inner_h: float
    wall: float
    tol: float
    pcb_top_z: float
    pcb_bottom_z: float
    standoff_height: float
    cutout_count: int
    standoff_count: int


@dataclass(frozen=True)
class AssemblySpec:
    """Multi-component two-piece enclosure spec (assembly_solver integration)."""
    outer_l: float
    outer_w: float
    base_h: float
    lid_h: float
    inner_l: float
    inner_w: float
    inner_h: float
    wall: float
    tol: float
    fillet_r: float
    n_components: int
    n_io_cutouts: int
    n_wire_grooves: int
    n_vents: int
    n_top_windows: int
    project_name: str


@dataclass(frozen=True)
class TwoPieceSpec:
    """Two-piece enclosure (base + lid) spec."""
    outer_l: float
    outer_w: float
    base_h: float
    lid_h: float
    inner_l: float
    inner_w: float
    inner_h: float
    wall: float
    tol: float
    pcb_top_z: float
    pcb_bottom_z: float
    standoff_height: float
    standoff_count: int
    side_cutout_count: int
    lid_cutout_count: int
    snap_count: int
    snap_arm_w: float
    snap_arm_t: float
    snap_arm_h: float
    snap_lip_h: float
    snap_lip_d: float
    snap_gap: float
