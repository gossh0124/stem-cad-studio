"""lib/cad/mounts.py — Tier 4 機械接合件（非 PCB enclosure）。

伺服馬達、直流馬達、Stepper、水泵、喇叭等元件不適合 box-enclosure 範式，
需要不同型態的機械接合件：bracket / clamp / flange / sleeve / grill。

實作清單（5 種）：
  - build_servo_sg90_bracket   — SG90 標準伺服支架
  - build_dc_motor_clamp       — TT 直流齒輪馬達卡箍（130 size）
  - build_nema17_flange        — NEMA17 stepper 法蘭
  - build_water_pump_sleeve    — 沉水馬達防水套筒
  - build_speaker_grill        — 喇叭聲腔網格

工程參數來源（datasheet 廣泛採用值）：
  - SG90: 22.8×12.2×22.5mm 標準
  - TT motor: 70×22×18mm，⌀5mm 軸
  - NEMA17: 42.3×42.3 法蘭，4 角螺絲孔 31×31mm
  - Speaker: ⌀36×5mm 圓盤，標準 6Ω
"""
from __future__ import annotations
from dataclasses import dataclass


# ════════════════════════════════════════════════════════════════════
# Servo SG90 bracket（既有，沿用）
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ServoBracketSpec:
    """SG90 標準伺服支架規格（鎖耳對應 23×12.2mm 主體 + 主軸圓孔）。

    熱源代表內嵌的 SG90 馬達本體（bracket 本身為被動塑料）。
    """
    servo_l: float = 23.0
    servo_w: float = 12.2
    servo_h: float = 22.5
    ear_thickness: float = 2.5
    ear_extra_l: float = 6.0
    shaft_diameter: float = 5.5
    screw_hole_d: float = 2.2
    bracket_floor_t: float = 2.5
    fillet_r: float = 1.0
    # 內嵌 SG90 馬達熱源
    thermal_typical_mw: float = 750.0    # 150mA × 5V running
    thermal_idle_mw: float = 30.0        # 6mA × 5V quiescent
    thermal_peak_mw: float = 3000.0      # 600mA × 5V stall
    thermal_formula: str = 'SG90 running ~150mA × 5V; stall 600mA'
    thermal_source: str = 'TowerPro SG90 datasheet'


def build_servo_sg90_bracket(spec: ServoBracketSpec | None = None):
    """生成 SG90 伺服支架（U 型 + 主軸孔 + 4 螺絲孔）。"""
    import build123d as bd
    s = spec or ServoBracketSpec()

    total_l = s.servo_l + 2 * s.ear_extra_l
    total_w = s.servo_w + 2 * s.ear_thickness
    total_h = s.bracket_floor_t + s.servo_h

    with bd.BuildPart() as bracket:
        bd.Box(total_l, total_w, total_h)
        cavity_l = s.servo_l + 0.6
        cavity_w = s.servo_w + 0.8
        cavity_h = s.servo_h + 1.0
        cavity_z = -total_h/2 + s.bracket_floor_t + cavity_h/2
        with bd.Locations((0, 0, cavity_z)):
            bd.Box(cavity_l, cavity_w, cavity_h, mode=bd.Mode.SUBTRACT)
        with bd.Locations((0, 0, total_h/2 - 1)):
            bd.Cylinder(radius=s.shaft_diameter/2, height=4.0,
                        mode=bd.Mode.SUBTRACT)
        screw_x = s.servo_l/2 + s.ear_extra_l/2
        screw_z = total_h/2 - 5.0
        for sx_sign in (-1, 1):
            for sz_sign in (-1, 1):
                with bd.Locations((sx_sign * screw_x,
                                   sz_sign * (s.servo_w/2 + s.ear_thickness/2),
                                   screw_z)):
                    bd.Cylinder(radius=s.screw_hole_d/2,
                                height=s.ear_thickness + 2,
                                mode=bd.Mode.SUBTRACT,
                                rotation=(90, 0, 0))

    info = dict(name='Servo-SG90', outer_l=total_l, outer_w=total_w,
                outer_h=total_h, screw_holes=4, shaft_d=s.shaft_diameter)
    return bracket.part, info


# ════════════════════════════════════════════════════════════════════
# DC Motor clamp（TT 130 motor 圓柱卡箍）
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class DCMotorClampSpec:
    """TT 直流齒輪馬達卡箍（70×22×18mm 主體, ⌀5mm 軸）。

    卡箍是兩半 U 形夾片，靠 2 顆螺絲鎖緊抓住馬達圓柱本體。
    熱源代表內嵌的 130-size DC 齒輪馬達（卡箍本身為被動塑料）。
    """
    motor_d: float = 24.4          # 圓柱本體直徑（小型 130 馬達）
    motor_l: float = 70.0          # 馬達總長（含齒輪箱）
    clamp_l: float = 35.0          # 卡箍長度（沿馬達軸向）
    clamp_thickness: float = 4.0   # 卡箍壁厚
    flange_w: float = 8.0          # 鎖耳延伸
    bolt_hole_d: float = 3.2       # M3 通孔
    base_t: float = 3.0            # 底板厚（鎖到主板用）
    # 內嵌 130-size DC motor 熱源
    thermal_typical_mw: float = 1500.0   # ~250mA × 6V 一般負載
    thermal_idle_mw: float = 100.0       # 無負載空轉
    thermal_peak_mw: float = 5000.0      # ~830mA × 6V stall
    thermal_formula: str = 'TT motor 6V × 250mA running; stall current ~5x'
    thermal_source: str = 'Generic 130-size DC gearmotor datasheet'


def build_dc_motor_clamp(spec: DCMotorClampSpec | None = None):
    """生成 DC 馬達卡箍（U 形抱箍 + 2 鎖耳螺絲孔 + 底板）。

    座標系：卡箍中心在原點，馬達軸向為 X，底板朝 -Z。
    """
    import build123d as bd
    s = spec or DCMotorClampSpec()

    outer_d = s.motor_d + 2 * s.clamp_thickness
    total_l = s.clamp_l
    total_w = outer_d + 2 * s.flange_w
    total_h = outer_d / 2 + s.base_t

    with bd.BuildPart() as clamp:
        # 主體：方形外殼 + 半圓抱箍
        bd.Box(total_l, total_w, total_h)
        # 中心圓柱孔（馬達穿過）
        with bd.Locations((0, 0, s.base_t/2)):
            bd.Cylinder(radius=s.motor_d/2 + 0.3, height=total_l + 1,
                        mode=bd.Mode.SUBTRACT, rotation=(0, 90, 0))
        # 切掉上半部留下 U 形（從上方切到圓孔中心稍下）
        cut_z = total_h/2 - s.base_t - outer_d/2 + 1.0
        with bd.Locations((0, 0, total_h/2)):
            bd.Box(total_l + 1, total_w + 1, total_h - cut_z + 1,
                   mode=bd.Mode.SUBTRACT)
        # 鎖耳螺絲孔（兩側，M3 通孔）
        ear_y = (s.motor_d + s.clamp_thickness)/2 + s.flange_w/2
        for sy_sign in (-1, 1):
            with bd.Locations((0, sy_sign * ear_y, -total_h/2 + s.base_t)):
                bd.Cylinder(radius=s.bolt_hole_d/2, height=s.base_t + 2,
                            mode=bd.Mode.SUBTRACT)

    info = dict(name='DC-Motor-Clamp', outer_l=total_l, outer_w=total_w,
                outer_h=total_h, motor_d=s.motor_d, bolt_holes=2)
    return clamp.part, info


# ════════════════════════════════════════════════════════════════════
# NEMA17 stepper flange（標準法蘭板，4 角螺絲孔 31mm 間距）
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class NEMA17FlangeSpec:
    """NEMA17 stepper 法蘭板（馬達 42.3×42.3, 4 螺絲孔角距 31×31mm）。

    熱源代表內嵌的 NEMA17 stepper（法蘭板本身為被動金屬/塑料）。
    """
    motor_size: float = 42.3       # 馬達側面寬（正方形）
    flange_size: float = 60.0      # 法蘭板總寬
    flange_t: float = 5.0          # 法蘭板厚度
    motor_screw_hole_d: float = 3.2  # M3 鎖馬達
    motor_screw_pitch: float = 31.0  # 馬達 4 螺絲孔角距（NEMA17 規範）
    center_hole_d: float = 24.0    # 馬達突出圓柱孔（boss）
    mount_hole_d: float = 4.5      # M4 鎖到底板用
    mount_screw_pitch: float = 50.0  # 底板鎖孔角距（user-defined）
    # 內嵌 NEMA17 stepper 熱源（兩相通電）
    thermal_typical_mw: float = 8000.0   # 1.5A × 2.7V × 2 phases ≈ 8W
    thermal_idle_mw: float = 1000.0      # holding current
    thermal_peak_mw: float = 24000.0     # full step at rated voltage
    thermal_formula: str = '2 phases × 1.5A × 2.7V continuous'
    thermal_source: str = 'NEMA17 17HS19-2004S1 datasheet'


def build_nema17_flange(spec: NEMA17FlangeSpec | None = None):
    """生成 NEMA17 法蘭板（中心 boss 孔 + 4 馬達孔 + 4 底板孔）。

    座標系：法蘭板中心在原點，馬達朝 +Z 方向裝入。
    """
    import build123d as bd
    s = spec or NEMA17FlangeSpec()

    with bd.BuildPart() as flange:
        bd.Box(s.flange_size, s.flange_size, s.flange_t)
        # 中心 boss 孔
        bd.Cylinder(radius=s.center_hole_d/2, height=s.flange_t + 1,
                    mode=bd.Mode.SUBTRACT)
        # 4 個 NEMA17 馬達螺絲孔
        for sx in (-1, 1):
            for sy in (-1, 1):
                with bd.Locations((sx * s.motor_screw_pitch/2,
                                   sy * s.motor_screw_pitch/2, 0)):
                    bd.Cylinder(radius=s.motor_screw_hole_d/2,
                                height=s.flange_t + 1,
                                mode=bd.Mode.SUBTRACT)
        # 4 個底板鎖孔（更靠外角）
        for sx in (-1, 1):
            for sy in (-1, 1):
                with bd.Locations((sx * s.mount_screw_pitch/2,
                                   sy * s.mount_screw_pitch/2, 0)):
                    bd.Cylinder(radius=s.mount_hole_d/2,
                                height=s.flange_t + 1,
                                mode=bd.Mode.SUBTRACT)

    info = dict(name='NEMA17-Flange', outer_l=s.flange_size, outer_w=s.flange_size,
                outer_h=s.flange_t, motor_screws=4, mount_screws=4)
    return flange.part, info


# ════════════════════════════════════════════════════════════════════
# Water pump sleeve（沉水馬達防水套筒，⌀25 圓柱主體）
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class WaterPumpSleeveSpec:
    """沉水馬達防水套筒（圓柱抱筒 + 出水口開孔）。

    熱源代表內嵌的 R385/3-6V mini 沉水泵（套筒本身為被動塑料）。
    水冷散熱主導，空氣熱仿真可低估。
    """
    pump_d: float = 25.0           # 馬達外徑
    pump_h: float = 30.0           # 馬達高度
    sleeve_thickness: float = 3.0
    outlet_d: float = 8.0          # 出水口直徑（馬達側面）
    outlet_z: float = 22.0         # 出水口從底量起的高度
    cable_slot_w: float = 5.0      # 電源線槽寬
    # 內嵌沉水泵熱源（水冷 in-situ）
    thermal_typical_mw: float = 1500.0   # ~250mA × 6V 一般操作
    thermal_idle_mw: float = 0.0         # OFF 時無耗
    thermal_peak_mw: float = 2400.0      # 400mA × 6V stall
    thermal_formula: str = 'R385 12V mini pump 200mA × 12V; 6V mode 250mA'
    thermal_source: str = 'R385 mini submersible pump generic spec'


def build_water_pump_sleeve(spec: WaterPumpSleeveSpec | None = None):
    """生成沉水馬達防水套筒（圓柱 + 底封 + 側壁出水孔 + 線槽）。"""
    import build123d as bd
    s = spec or WaterPumpSleeveSpec()

    outer_d = s.pump_d + 2 * s.sleeve_thickness
    total_h = s.pump_h + s.sleeve_thickness

    with bd.BuildPart() as sleeve:
        # 外圓柱
        bd.Cylinder(radius=outer_d/2, height=total_h)
        # 內圓柱（馬達置入空間）
        with bd.Locations((0, 0, s.sleeve_thickness/2)):
            bd.Cylinder(radius=s.pump_d/2 + 0.3,
                        height=total_h - s.sleeve_thickness + 1,
                        mode=bd.Mode.SUBTRACT)
        # 出水孔（側壁圓孔，X 軸方向）
        outlet_z_local = -total_h/2 + s.sleeve_thickness + s.outlet_z
        with bd.Locations((outer_d/2, 0, outlet_z_local)):
            bd.Cylinder(radius=s.outlet_d/2, height=s.sleeve_thickness * 3,
                        mode=bd.Mode.SUBTRACT, rotation=(0, 90, 0))
        # 電源線槽（頂部開口）
        with bd.Locations((0, 0, total_h/2 - s.sleeve_thickness)):
            bd.Box(s.cable_slot_w, outer_d + 2, s.sleeve_thickness * 2,
                   mode=bd.Mode.SUBTRACT)

    info = dict(name='Water-Pump-Sleeve', outer_d=outer_d, outer_h=total_h,
                outlet_d=s.outlet_d)
    return sleeve.part, info


# ════════════════════════════════════════════════════════════════════
# Speaker grill（喇叭聲腔網格，⌀36 圓盤喇叭）
# ════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SpeakerGrillSpec:
    """喇叭聲腔網格（標準 6Ω ⌀36×5mm 圓盤）。

    Grill 是個圓盤蓋，正面有同心環的聲音穿孔陣列，背面有座圈固定喇叭本體。
    熱源代表內嵌的 0.5W 喇叭（grill 本身為被動塑料）。
    """
    speaker_d: float = 36.0
    speaker_h: float = 5.0
    grill_outer_d: float = 44.0    # 外圓直徑（含外圈）
    grill_t: float = 3.0           # 整體厚度
    sound_hole_d: float = 2.5      # 單一聲孔直徑
    sound_ring_count: int = 3      # 同心環數
    holes_per_ring: int = 12       # 每環孔數
    mount_hole_d: float = 3.2      # 鎖到主殼用
    # 內嵌 0.5W 6Ω 喇叭熱源
    thermal_typical_mw: float = 250.0    # 平均音量輸出
    thermal_idle_mw: float = 0.0         # 靜音
    thermal_peak_mw: float = 500.0       # 額定 0.5W 上限
    thermal_formula: str = '0.5W rated × 50% avg utilization'
    thermal_source: str = 'Generic 6Ω 0.5W speaker datasheet'


def build_speaker_grill(spec: SpeakerGrillSpec | None = None):
    """生成喇叭聲腔網格（圓盤 + 聲孔陣列 + 喇叭座圈 + 鎖孔）。"""
    import build123d as bd
    import math
    s = spec or SpeakerGrillSpec()

    with bd.BuildPart() as grill:
        # 外圓盤
        bd.Cylinder(radius=s.grill_outer_d/2, height=s.grill_t)
        # 喇叭座圈（背面凹陷放喇叭本體）
        with bd.Locations((0, 0, -s.grill_t/2 + s.speaker_h/2 - 0.5)):
            bd.Cylinder(radius=s.speaker_d/2 + 0.3, height=s.speaker_h + 1,
                        mode=bd.Mode.SUBTRACT)
        # 聲孔陣列（同心環）
        for ring in range(s.sound_ring_count):
            r = (ring + 1) * (s.speaker_d / 2 / (s.sound_ring_count + 1))
            for i in range(s.holes_per_ring):
                angle = 2 * math.pi * i / s.holes_per_ring
                hx = r * math.cos(angle)
                hy = r * math.sin(angle)
                with bd.Locations((hx, hy, 0)):
                    bd.Cylinder(radius=s.sound_hole_d/2, height=s.grill_t + 1,
                                mode=bd.Mode.SUBTRACT)
        # 中心聲孔
        bd.Cylinder(radius=s.sound_hole_d/2 * 1.5, height=s.grill_t + 1,
                    mode=bd.Mode.SUBTRACT)
        # 4 個鎖孔（外圈邊緣）
        mount_r = s.grill_outer_d / 2 - 2.0
        for i in range(4):
            angle = math.pi / 4 + i * math.pi / 2
            mx = mount_r * math.cos(angle)
            my = mount_r * math.sin(angle)
            with bd.Locations((mx, my, 0)):
                bd.Cylinder(radius=s.mount_hole_d/2, height=s.grill_t + 1,
                            mode=bd.Mode.SUBTRACT)

    info = dict(name='Speaker-Grill', outer_d=s.grill_outer_d,
                outer_h=s.grill_t,
                sound_holes=s.sound_ring_count * s.holes_per_ring + 1,
                mount_holes=4)
    return grill.part, info


# ════════════════════════════════════════════════════════════════════
# Generic component cradle（通用元件托座）— 給 B/C/D 類沒有 bespoke mount 的元件
# ════════════════════════════════════════════════════════════════════
# 使用者需求 2026-06-06：B/C/D 元件需有「外殼/托座」才能安裝到 assembly 殼體上
# （水泵除外，沉水不裝殼內）。Brain 板用 2 件式 case;有專屬 mount 的致動器用其
# builder;其餘一律用此通用 cradle —— 依元件 footprint 生成「開頂托盤 + 定位低牆 +
# 兩端走線槽 + 平底（黏/鎖到殼體地板）」。

@dataclass
class GenericCradleSpec:
    length: float = 30.0
    width: float = 20.0
    height: float = 10.0
    wall: float = 2.0
    floor_t: float = 2.0
    tol: float = 0.6
    lip_frac: float = 0.45        # 定位牆高 = height × frac（夾在 min/max）
    lip_min: float = 3.0
    lip_max: float = 9.0
    wire_slot_w: float = 6.0
    thermal_idle_mw: float = 0.0
    thermal_peak_mw: float = 0.0
    thermal_formula: str = 'passive holder (no active heat)'
    thermal_source: str = 'generic component cradle'


def build_generic_cradle(spec: 'GenericCradleSpec | None' = None):
    """通用元件托座：開頂托盤,依 footprint 容納元件並以平底安裝到殼體地板。"""
    import build123d as bd
    s = spec or GenericCradleSpec()
    inner_l = s.length + 2 * s.tol
    inner_w = s.width + 2 * s.tol
    lip_h = min(max(s.height * s.lip_frac, s.lip_min), s.lip_max)
    outer_l = inner_l + 2 * s.wall
    outer_w = inner_w + 2 * s.wall
    total_h = s.floor_t + lip_h
    slot_w = min(s.wire_slot_w, inner_w * 0.6)

    with bd.BuildPart() as p:
        bd.Box(outer_l, outer_w, total_h,
               align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        # 元件穴（開頂）— 留底厚 floor_t
        with bd.Locations((0, 0, s.floor_t + lip_h / 2 + 0.6)):
            bd.Box(inner_l, inner_w, lip_h + 1.2, mode=bd.Mode.SUBTRACT)
        # 兩端短牆走線槽（讓線材出來）
        for sx in (-1.0, 1.0):
            with bd.Locations((sx * (outer_l / 2), 0, s.floor_t + lip_h / 2 + 0.6)):
                bd.Box(s.wall * 3, slot_w, lip_h + 1.2, mode=bd.Mode.SUBTRACT)

    info = dict(name='generic-cradle', outer_l=round(outer_l, 2),
                outer_w=round(outer_w, 2), outer_h=round(total_h, 2),
                lip_h=round(lip_h, 2))
    return p.part, info


def build_generic_two_piece(length, width, height, *, wall=2.0, floor_t=2.0,
                            tol=0.6, lid_h=2.0, clearance_h=3.0):
    """Generic MCU-style 2-piece case (base tray + lid) sized from a component footprint,
    for holder-needing parts WITHOUT a PCBSpec. Mirrors build_pcb_two_piece's base+lid
    structure so all holders share the MCU-case design language (user 2026-06-06:
    比對 mcu 的外殼進行設計). Returns (base_part, lid_part, spec_dict)."""
    import build123d as bd
    inner_l = length + 2 * tol
    inner_w = width + 2 * tol
    inner_h = height + clearance_h
    outer_l = inner_l + 2 * wall
    outer_w = inner_w + 2 * wall
    base_h = floor_t + inner_h
    slot_w = min(6.0, inner_w * 0.5)

    with bd.BuildPart() as base:
        bd.Box(outer_l, outer_w, base_h, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
        with bd.Locations((0, 0, floor_t + inner_h / 2 + 0.5)):
            bd.Box(inner_l, inner_w, inner_h + 1, mode=bd.Mode.SUBTRACT)   # open-top cavity
        for sx in (-1.0, 1.0):                                             # wire-exit slots
            with bd.Locations((sx * outer_l / 2, 0, floor_t + inner_h / 2 + 0.5)):
                bd.Box(wall * 3, slot_w, inner_h, mode=bd.Mode.SUBTRACT)

    with bd.BuildPart() as lid:
        bd.Box(outer_l, outer_w, lid_h, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))

    spec_dict = dict(inner_length=round(inner_l, 2), inner_width=round(inner_w, 2),
                     inner_height=round(inner_h, 2), wall=wall, tol=tol,
                     outer_l=round(outer_l, 2), outer_w=round(outer_w, 2),
                     base_h=round(base_h, 2), lid_h=lid_h, kind='two_piece_generic')
    return base.part, lid.part, spec_dict


# ════════════════════════════════════════════════════════════════════
# 統一註冊表
# ════════════════════════════════════════════════════════════════════

ALL_MOUNTS = {
    # class_name → (mount_kind, label, builder)
    'Motor-Servo-class':   ('sg90_bracket',     'SG90 bracket',         build_servo_sg90_bracket),
    'Motor-DC-class':      ('tt_motor_clamp',   'TT motor clamp',       build_dc_motor_clamp),
    'Motor-Stepper-class': ('nema17_flange',    'NEMA17 flange',        build_nema17_flange),
    'Pump-Water-class':    ('water_pump_sleeve','water pump sleeve',    build_water_pump_sleeve),
    'Speaker-class':       ('speaker_grill',    'speaker grill',        build_speaker_grill),
}


# kind → default Spec instance（給 shell_cache fingerprint / thermal_index 用）
DEFAULT_MOUNT_SPECS = {
    'sg90_bracket':       ServoBracketSpec(),
    'tt_motor_clamp':     DCMotorClampSpec(),
    'nema17_flange':      NEMA17FlangeSpec(),
    'water_pump_sleeve':  WaterPumpSleeveSpec(),
    'speaker_grill':      SpeakerGrillSpec(),
}


if __name__ == '__main__':
    from pathlib import Path
    from .tessellation import export_step, export_stl_high_density

    out = Path('output/tier4_mounts')
    out.mkdir(parents=True, exist_ok=True)

    for class_name, (kind, label, builder) in ALL_MOUNTS.items():
        part, info = builder()
        stl = out / f'{kind}.stl'
        export_step(part, out / f'{kind}.step')
        tris = export_stl_high_density(part, stl)
        print(f'{class_name:25s} {label:20s} {tris:5d} tris  -> {stl.name}')
