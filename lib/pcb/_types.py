"""lib/pcb/_types.py — 通用 PCB 資料結構基類。

所有單板（Arduino / ESP32 / RPi / Microbit）與感測器模組共用此 schema。
座標系：PCB 左下角為原點，X 向右，Y 向上，Z 垂直 PCB 表面向上，單位 mm。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Tuple, List, Optional


@dataclass(frozen=True)
class NamedPin:
    """單一 pin 的絕對 PCB 座標 + 邏輯命名。"""
    name: str
    x: float
    y: float
    pad_index: int = 0
    eagle_ref: str = ''
    function: str = ''      # 'GPIO'|'ANALOG'|'POWER'|'GND'|'I2C'|'SPI'|'UART'|'NC'
    arduino_pin: str = ''   # Arduino IDE 命名（D0/A5/+5V/IOREF...）
    avr_port: str = ''      # MCU 內部 port（PD0/PC5/PB3...）


@dataclass(frozen=True)
class MountingHole:
    x: float
    y: float
    diameter: float = 3.2


@dataclass(frozen=True)
class SubComponent:
    """PCB 上實體子元件（IC / 連接器 / 晶振等）。

    protrudes / overhang / profile 用於 3D 殼體 cutout：
      protrudes  = 'left'|'right'|'top'|'bottom'|''（'' = 不突出 PCB 邊緣）
      overhang   = 突出 PCB 邊緣的距離（mm）
      profile    = 'rect'|'circle'|'stadium'|''（'' = 不需殼體 cutout）

    熱源剖面（thermal_*）— 用於 Phase 4 熱場分析：
      thermal_typical_mw = 典型操作功耗
      thermal_idle_mw    = 待機/sleep
      thermal_peak_mw    = 峰值（短時，≥ typical）
      thermal_formula    = 計算依據（"50mA × 5V"）
      thermal_source     = datasheet 章節（"A000066 §29.2"）
    """
    name: str
    package: str
    anchor_x: float
    anchor_y: float
    body_l: float
    body_w: float
    body_h: float
    z: float = 0.0
    rotation: str = 'R0'
    description: str = ''
    protrudes: str = ''
    overhang: float = 0.0
    profile: str = ''
    # 熱源資料
    thermal_typical_mw: float = 0.0
    thermal_idle_mw: float = 0.0
    thermal_peak_mw: float = 0.0
    thermal_formula: str = ''
    thermal_source: str = ''
    # ADR-10: IC 級熱阻（三來源交叉驗證）
    rth_ja_cw: float = 0.0  # junction-to-ambient thermal resistance, deg C/W
    rth_sources: Tuple[dict, ...] = ()  # ({source, value, ref}, ...) 三來源記錄


@dataclass(frozen=True)
class HeaderGroup:
    """3D 外殼開孔用的 header 群組（合併相鄰 pins 為單一 slot）。"""
    name: str
    pin_indices: Tuple[int, ...]
    profile: str                # 'slot' (1 row) / 'rect' (2x3 ICSP)
    port_type: str              # 用於 ConnectorPort.port_type
    rows: int = 1
    clearance_mm: float = 1.0


@dataclass(frozen=True)
class PCBSpec:
    """通用 PCB 規格。

    `pins` 是所有 pin 的單一統一列表，用 `pad_index` 唯一識別。
    `pin_groups` 是邏輯分組（如 Arduino: {'JANALOG':(1..14), 'JDIGITAL':(15..32), 'ICSP':(101..106)}），
    供按邏輯區段查詢使用，不影響 3D 切口（切口看 header_groups）。
    """
    name: str
    length: float
    width: float
    pcb_thickness: float
    pins: Tuple[NamedPin, ...]
    pin_groups: Dict[str, Tuple[int, ...]]
    mounting_holes: Tuple[MountingHole, ...]
    sub_components: Tuple[SubComponent, ...]
    header_groups: Tuple[HeaderGroup, ...] = field(default_factory=tuple)

    def pin_index_map(self) -> dict:
        """{pad_index: NamedPin} 表，含所有 pins。"""
        return {p.pad_index: p for p in self.pins}

    def find_pin(self, query: str) -> Optional[NamedPin]:
        """以 name / arduino_pin / avr_port 任一欄位查 pin。"""
        for p in self.pins:
            if p.name == query or p.arduino_pin == query or p.avr_port == query:
                return p
        return None

    def pins_in_group(self, group_name: str) -> Tuple[NamedPin, ...]:
        """回傳指定邏輯群組的 pins（依 pin_groups 配置）。"""
        idx_map = self.pin_index_map()
        idxs = self.pin_groups.get(group_name, ())
        return tuple(idx_map[i] for i in idxs if i in idx_map)

    def thermal_profile(self, mode: str = 'typical') -> List[dict]:
        """回傳 [{x, y, z, mw, sub_name, source}, ...] — 給 2D/3D 熱場 solver。

        mode = 'typical' / 'idle' / 'peak'，過濾 mw=0 的 sub。
        座標已轉為 PCB 絕對座標（anchor_x/y 已是）。
        """
        attr = f'thermal_{mode}_mw'
        out = []
        for sc in self.sub_components:
            mw = getattr(sc, attr, 0.0)
            if mw > 0:
                out.append({
                    'sub_name': sc.name,
                    'package':  sc.package,
                    'x':        sc.anchor_x,
                    'y':        sc.anchor_y,
                    'z':        sc.z,
                    'body_l':   sc.body_l,
                    'body_w':   sc.body_w,
                    'mw':       mw,
                    'formula':  sc.thermal_formula,
                    'source':   sc.thermal_source,
                })
        return out

    def total_thermal_mw(self, mode: str = 'typical') -> float:
        """總功耗（mW）— sum of all sub_components in given mode。"""
        attr = f'thermal_{mode}_mw'
        return sum(getattr(sc, attr, 0.0) for sc in self.sub_components)


def derive_connector_ports_generic(pcb_spec: PCBSpec) -> List[dict]:
    """通用 ConnectorPort 推導 — 適用任何 PCBSpec。

    處理三類連接器：
      1. 突出 PCB 邊緣的 SubComponent（USB / DC-Jack / Ethernet 等）→ side ports
      2. header_groups 中的排針 → face ports（slot 切口）
      3. 非突出且 profile='' 的內部 IC → 不產生 port

    回傳的 dict 直接餵給 lib/registry.py 構造 ConnectorPort。
    """
    ports: List[dict] = []
    L, W = pcb_spec.length, pcb_spec.width

    # 突出邊緣的連接器
    for sc in pcb_spec.sub_components:
        if not sc.protrudes or not sc.profile:
            continue
        # rotation 後 body_l/body_w 對應軸交換
        if sc.rotation in ('R90', 'R270'):
            body_along_y, body_along_x = sc.body_l, sc.body_w
        else:
            body_along_y, body_along_x = sc.body_w, sc.body_l

        if sc.protrudes in ('left', 'right'):
            # 沿 Y 方向的 cutout
            port_y = sc.anchor_y    # 已是 PCB 座標
            port_w = body_along_y
            port_h = sc.body_h
            side = sc.protrudes
            x_in_spec = 0.0 if sc.protrudes == 'left' else L
        else:  # top / bottom
            # 與 left/right 對稱：沿 top/bottom 邊的連接器，x=沿邊位置(anchor_x)、y=邊界(0/W)。
            # （舊碼把 anchor_x 存進 y、邊界存進 x，x/y 對調 → 開孔位置錯，見 BUG-SCAN C4）
            port_y = 0.0 if sc.protrudes == 'bottom' else W   # Y 邊界
            port_w = body_along_x
            port_h = sc.body_h
            side = sc.protrudes
            x_in_spec = sc.anchor_x   # 沿 X 軸的 cutout 位置（PCB 座標）

        ports.append(dict(
            name=sc.name, port_type='PWR' if 'USB' in sc.name or 'PWR' in sc.name else 'OTHER',
            x=x_in_spec, y=port_y,
            width=port_w, height=port_h,
            side=side, z=sc.z,
        ))

    # Header groups（face 開孔）
    pin_index = pcb_spec.pin_index_map()
    for grp in pcb_spec.header_groups:
        grp_pins = [pin_index[i] for i in grp.pin_indices if i in pin_index]
        if not grp_pins:
            continue
        xs = [p.x for p in grp_pins]
        ys = [p.y for p in grp_pins]
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        width = span_x + 2.54 + 2 * grp.clearance_mm
        if grp.profile == 'slot' and grp.rows == 1:
            height = 2.54 + 2 * grp.clearance_mm
        else:
            height = span_y + 2.54 + 2 * grp.clearance_mm
        ports.append(dict(
            name=grp.name, port_type=grp.port_type,
            x=cx, y=cy, width=width, height=height,
            side='face', z=0.0,
        ))

    return ports
