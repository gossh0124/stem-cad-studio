"""lib/cad/pcb_body.py — Arduino Uno R3 PCB 本體 3D 模型（build123d）。

座標系（與 shell.py 一致，中心原點）：
  PCB 中心 = (0, 0, thickness/2)
  X 軸 = PCB 長軸 (68.58mm)；Y 軸 = PCB 短軸 (53.34mm)；Z 軸向上
  PCB 表面 Z = 1.6mm（板厚）

所有元件座標直接引用 lib/pcb/arduino_uno_r3.py 的 EAGLE 驗證資料：
  - USB-B / DC-Jack: 從 -X 側（x=0 邊）凸出
  - JANALOG (POWER+AD): y=2.54mm（底邊 -Y 側）
  - JDIGITAL (IOL+IOH): y=50.80mm（頂邊 +Y 側）
  - ATmega328P: anchor (46.355, 16.383), DIP-28 封裝
  - ATmega16U2: anchor (19.939, 34.671), QFN-32 封裝
  - Crystal 16MHz: anchor (18.923, 26.162)

匯出格式：GLB（glTF Binary）— 保留每個元件的個別顏色。
若 trimesh[easy] 未安裝，fallback 為單色 STL。
"""
from __future__ import annotations

import os
import sys
import pathlib
from typing import Tuple, List

import build123d as bd

# SSOT import — 確保 project root 在 sys.path
try:
    from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3
except ImportError:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
    from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3


def _ssot_sub(name: str):
    """從 SSOT 取得指定名稱的 SubComponent。"""
    for sc in ARDUINO_UNO_R3.sub_components:
        if sc.name == name:
            return sc
    raise KeyError(f"SubComponent {name!r} not found in SSOT")


def _rotated_xy(sub) -> Tuple[float, float]:
    """依 EAGLE rotation 回傳 box 在 X/Y 軸的實際尺寸。"""
    if sub.rotation in ('R90', 'R270'):
        return sub.body_w, sub.body_l
    return sub.body_l, sub.body_w


# ---------------------------------------------------------------------------
# 顏色定義（真實 Arduino Uno R3 參照）
# ---------------------------------------------------------------------------
_PCB_TEAL    = bd.Color(0.00, 0.33, 0.42)     # Arduino 藍綠色 PCB 基板
_SOLDER_MASK = bd.Color(0.00, 0.28, 0.36)     # 焊盤罩（略深）
_METAL       = bd.Color(0.78, 0.78, 0.82)     # 金屬色（USB 外殼、pin 腳）
_BLACK       = bd.Color(0.10, 0.10, 0.10)     # 黑色塑膠
_IC_DARK     = bd.Color(0.12, 0.12, 0.14)     # IC 封裝深灰
_PIN_GOLD    = bd.Color(0.85, 0.70, 0.15)     # 金色 pin 腳
_LED_GREEN   = bd.Color(0.10, 0.85, 0.10)     # 綠色 LED
_LED_YELLOW  = bd.Color(0.90, 0.80, 0.10)     # 黃色 LED
_LED_RED     = bd.Color(0.85, 0.10, 0.10)     # 紅色 LED
_CRYSTAL     = bd.Color(0.78, 0.78, 0.75)     # 石英振盪器
_CAP_DARK    = bd.Color(0.18, 0.18, 0.20)     # 電解電容
_WHITE       = bd.Color(1.00, 1.00, 1.00)     # 絲印文字
_DIP_BROWN   = bd.Color(0.22, 0.15, 0.10)     # DIP-28 IC 座深棕

# ---------------------------------------------------------------------------
# PCB 基本尺寸 & 座標轉換
# ---------------------------------------------------------------------------
PCB_L = 68.58    # X 全長 mm (EAGLE)
PCB_W = 53.34    # Y 全寬 mm
PCB_T = 1.6      # 板厚

_OX = -PCB_L / 2
_OY = -PCB_W / 2


def _ds(x: float, y: float) -> Tuple[float, float]:
    """Datasheet 座標 (左下角原點) → 中心原點。"""
    return (x + _OX, y + _OY)


# ---------------------------------------------------------------------------
# 輔助建模
# ---------------------------------------------------------------------------
def _box(cx, cy, cz, dx, dy, dz) -> bd.Solid:
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Box(dx, dy, dz)
    return bp.part


def _cyl(cx, cy, cz, r, h) -> bd.Solid:
    with bd.BuildPart() as bp:
        with bd.Locations(bd.Location((cx, cy, cz))):
            bd.Cylinder(r, h)
    return bp.part


def _add(parts, solid, color, label):
    solid.color = color
    solid.label = label
    parts.append(solid)


# 真實外型細節 helper 移至 pcb_common（可跨板共用），別名沿用底線命名
from lib.cad.pcb_common import (  # noqa: E402
    box_holes as _box_holes,
    box_port as _box_port,
    tube_x as _tube_x,
    notched_box as _notched_box,
    rounded_can as _rounded_can,
    export_glb as _export_glb,
)


# ---------------------------------------------------------------------------
# 主建模
# ---------------------------------------------------------------------------
def build_arduino_pcb_body() -> bd.Compound:
    """建立 Arduino Uno R3 PCB — 使用 EAGLE 座標。"""
    parts: list[bd.Shape] = []
    pz = PCB_T   # PCB 表面 Z

    # ─── 1. PCB 基板 ────────────────────────────────────────
    with bd.BuildPart() as pcb_bp:
        with bd.Locations(bd.Location((0, 0, pz / 2))):
            bd.Box(PCB_L, PCB_W, PCB_T)
        # 4 個螺絲孔
        for hx, hy in [(13.97, 2.54), (15.24, 50.80), (66.04, 7.62), (66.04, 35.56)]:
            cx, cy = _ds(hx, hy)
            with bd.Locations(bd.Location((cx, cy, pz / 2))):
                bd.Cylinder(1.6, PCB_T + 0.2, mode=bd.Mode.SUBTRACT)
    _add(parts, pcb_bp.part, _PCB_TEAL, "PCB_Board")

    # ─── 2. USB-B 連接器（-X 側凸出）───────────────────────
    # EAGLE anchor: (3.81, 38.10), body 12×16×11mm, rot R270
    # 元件從 x=0 邊凸出（protrudes='left'）
    usb_body_l, usb_body_w, usb_h = 16.0, 12.0, 11.0  # R270: l↔w swap
    usb_protrude = 2.5
    # USB 中心 X：anchor_x=3.81，向左凸出 → 中心在 -(protrude/2) 附近
    usb_cx = _ds(-usb_protrude + usb_body_l / 2, 0)[0]
    usb_cy = _ds(0, 38.10)[1]
    usb_cz = pz + usb_h / 2 - 0.5
    # 金屬殼 + -X 面凹進插口開孔（真實連接器外型，非實心方盒）
    _add(parts, _box_port(usb_cx, usb_cy, usb_cz, usb_body_l, usb_body_w, usb_h,
                          port_w=8.0, port_h=7.0, port_depth=6.0, dz_off=0.5),
         _METAL, "USB_B_Shell")
    # 插口內黑色塑膠舌片
    _add(parts, _box(usb_cx - usb_body_l / 2 + 3.5, usb_cy, usb_cz + 0.5, 3.0, 5.0, 2.0),
         _BLACK, "USB_B_Insert")

    # ─── 3. DC Barrel Jack（-X 側凸出）─────────────────────
    # EAGLE anchor: (5.334, 8.382), body 14×9×11mm, rot R90
    dc_body_l, dc_body_w, dc_h = 14.0, 9.0, 11.0
    dc_protrude = 3.0
    dc_cx = _ds(-dc_protrude + dc_body_l / 2, 0)[0]
    dc_cy = _ds(0, 8.382)[1]
    dc_cz = pz + dc_h / 2 - 0.5
    _add(parts, _box(dc_cx, dc_cy, dc_cz, dc_body_l, dc_body_w, dc_h),
         _BLACK, "DC_Barrel_Body")

    # DC 圓桶插孔（沿 X 軸中空圓柱，朝 -X 凸出；非方盒）
    barrel_r = 3.3
    barrel_len = 6.0
    barrel_cx = _ds(-dc_protrude - barrel_len / 2 + 1.0, 0)[0]
    _add(parts, _tube_x(barrel_cx, dc_cy, dc_cz, barrel_r, barrel_r * 0.45, barrel_len),
         _BLACK, "DC_Barrel_Jack")

    # ─── 4. ATmega328P（DIP-28 封裝 + IC 座）──────────────
    # EAGLE anchor: (46.355, 16.383), body 35.56×7.62×3.3mm, rot R180
    mcu_l, mcu_w, mcu_h = 35.56, 7.62, 3.3
    mcu_cx, mcu_cy = _ds(46.355, 16.383)
    mcu_cz = pz + mcu_h / 2

    # IC 座（黑色方塊，略大於 IC body）
    socket_h = 1.5
    _add(parts, _box(mcu_cx, mcu_cy, pz + socket_h / 2,
                     mcu_l + 1.5, mcu_w + 1.5, socket_h),
         _BLACK, "ATmega328P_Socket")

    # IC 本體（深棕色 DIP 封裝 + -X 端 pin1 半圓缺口）
    _body_h = mcu_h - socket_h
    _add(parts, _notched_box(mcu_cx, mcu_cy, pz + socket_h + _body_h / 2,
                             mcu_l, mcu_w, _body_h, notch_r=1.4),
         _DIP_BROWN, "ATmega328P_Body")

    # DIP-28 pin 腳（14 pin 每側，2.54mm pitch）
    for side in (-1, 1):  # -Y 側 和 +Y 側
        for i in range(14):
            pin_x = mcu_cx - mcu_l / 2 + 1.27 + i * 2.54
            pin_y = mcu_cy + side * (mcu_w / 2 + 0.5)
            _add(parts, _box(pin_x, pin_y, pz + 0.25, 0.5, 1.2, 0.5),
                 _METAL, f"MCU_DIP_Pin_{side}_{i}")

    # Pin 1 白點（緊鄰缺口）
    _add(parts, _cyl(mcu_cx - mcu_l / 2 + 2.2, mcu_cy + mcu_w / 2 - 1.2,
                     pz + mcu_h + 0.02, 0.4, 0.04),
         _WHITE, "MCU_Pin1_Dot")

    # ─── 5. ATmega16U2（QFN-32，USB 控制器）────────────────
    # EAGLE anchor: (19.939, 34.671), 5×5×1mm, rot R90
    u2_cx, u2_cy = _ds(19.939, 34.671)
    _add(parts, _box(u2_cx, u2_cy, pz + 0.5, 5.0, 5.0, 1.0),
         _IC_DARK, "ATmega16U2")
    # Pin 1 dot
    _add(parts, _cyl(u2_cx - 1.8, u2_cy + 1.8, pz + 1.02, 0.3, 0.04),
         _WHITE, "16U2_Pin1")

    # ─── 6. JANALOG Header（底邊 y=2.54mm，14 pins: POWER 8 + AD 6）──
    # POWER 群組：x = 27.94 ~ 45.72 (NC ~ VIN)
    _add_header_row(parts, pz,
        [(27.940, 2.54), (30.480, 2.54), (33.020, 2.54), (35.560, 2.54),
         (38.100, 2.54), (40.640, 2.54), (43.180, 2.54), (45.720, 2.54)],
        "POWER", "bottom")

    # ANALOG 群組：x = 50.80 ~ 63.50 (A0 ~ A5)
    _add_header_row(parts, pz,
        [(50.800, 2.54), (53.340, 2.54), (55.880, 2.54),
         (58.420, 2.54), (60.960, 2.54), (63.500, 2.54)],
        "ANALOG", "bottom")

    # ─── 7. JDIGITAL Header（頂邊 y=50.80mm，18 pins: IOL 8 + IOH 10）──
    # IOL 群組：D0~D7
    _add_header_row(parts, pz,
        [(63.500, 50.80), (60.960, 50.80), (58.420, 50.80), (55.880, 50.80),
         (53.340, 50.80), (50.800, 50.80), (48.260, 50.80), (45.720, 50.80)],
        "DIGITAL_LOW", "top")

    # IOH 群組：D8~SCL
    _add_header_row(parts, pz,
        [(41.656, 50.80), (39.116, 50.80), (36.576, 50.80), (34.036, 50.80),
         (31.496, 50.80), (28.956, 50.80), (26.416, 50.80), (23.876, 50.80),
         (21.336, 50.80), (18.796, 50.80)],
        "DIGITAL_HIGH", "top")

    # ─── 8. ICSP Header（2×3，ATmega328P 用）───────────────
    # EAGLE pins: (63.627,30.48), (66.167,30.48), ..., (66.167,25.40)
    icsp_pins = [
        (63.627, 30.480), (66.167, 30.480),
        (63.627, 27.940), (66.167, 27.940),
        (63.627, 25.400), (66.167, 25.400),
    ]
    icsp_xs = [p[0] for p in icsp_pins]
    icsp_ys = [p[1] for p in icsp_pins]
    icsp_cx, icsp_cy = _ds((min(icsp_xs)+max(icsp_xs))/2, (min(icsp_ys)+max(icsp_ys))/2)
    icsp_span_x = max(icsp_xs) - min(icsp_xs) + 2.54
    icsp_span_y = max(icsp_ys) - min(icsp_ys) + 2.54

    _add(parts, _box(icsp_cx, icsp_cy, pz + 1.27, icsp_span_x, icsp_span_y, 2.54),
         _BLACK, "ICSP_Plastic")
    for px, py in icsp_pins:
        cx, cy = _ds(px, py)
        _add(parts, _cyl(cx, cy, pz + 5.0, 0.32, 8.5),
             _PIN_GOLD, f"ICSP_Pin")

    # ─── 9. ICSP2 Header（ATmega16U2 用）───────────────────
    # EAGLE anchor: (18.288, 46.228), 2×3 header
    icsp2_cx, icsp2_cy = _ds(18.288, 46.228)
    _add(parts, _box(icsp2_cx, icsp2_cy, pz + 1.27, 5.08, 7.62, 2.54),
         _BLACK, "ICSP2_Plastic")

    # ─── 10. 16MHz Crystal ─────────────────────────────────
    # EAGLE anchor: (18.923, 26.162), HC49 11.4×4.7×4.0mm
    xtal_cx, xtal_cy = _ds(18.923, 26.162)
    _add(parts, _rounded_can(xtal_cx, xtal_cy, pz, 11.4, 4.7, 4.0, radius=2.2),
         _CRYSTAL, "Crystal_16MHz")

    # ─── 11. Resonator（ATmega328P 附近）───────────────────
    # EAGLE anchor: (41.275, 24.892)
    res_cx, res_cy = _ds(41.275, 24.892)
    _add(parts, _box(res_cx, res_cy, pz + 1.0, 8.0, 2.5, 2.0),
         _CRYSTAL, "Resonator")

    # ─── 12. Voltage Regulator（SOT-223）───────────────────
    # EAGLE anchor: (7.747, 17.399), rot R90
    vreg_cx, vreg_cy = _ds(7.747, 17.399)
    _add(parts, _box(vreg_cx, vreg_cy, pz + 0.8, 3.5, 6.5, 1.6),  # R90: l↔w
         _IC_DARK, "VReg_5V")
    # 散熱片 tab
    _add(parts, _box(vreg_cx + 1.5, vreg_cy, pz + 0.4, 2.0, 6.5, 0.8),
         _METAL, "VReg_Tab")

    # ─── 13. 電解電容 PC1 / PC2 ────────────────────────────
    # SSOT: lib/pcb/arduino_uno_r3.py — Cap-PC1 / Cap-PC2
    # PANASONIC_D 47μF: ⌀6.3 × 高 5.4mm，靠近 DC Jack
    for cap_name in ("Cap-PC1", "Cap-PC2"):
        sc = _ssot_sub(cap_name)
        cx, cy = _ds(sc.anchor_x, sc.anchor_y)
        r = sc.body_l / 2.0
        _add(parts, _cyl(cx, cy, pz + sc.body_h / 2, r, sc.body_h),
             _CAP_DARK, cap_name)
        # 頂部洩壓刻痕（淺色淺盤）+ 極性條（-Y 側淺帶）
        _add(parts, _cyl(cx, cy, pz + sc.body_h + 0.05, r * 0.72, 0.1),
             _METAL, f"{cap_name}_Vent")
        _add(parts, _box(cx, cy - r + 0.25, pz + sc.body_h / 2,
                         r, 0.5, sc.body_h * 0.85), _WHITE, f"{cap_name}_Stripe")

    # ─── 14. LED 指示燈（ON / TX / RX / L）────────────────
    # SSOT: lib/pcb/arduino_uno_r3.py — LED-ON / LED-RX / LED-TX / LED-L
    # 顏色依 EAGLE SCH part value：ON=GREEN, RX/TX/L=YELLOW（A2 來源驗證）
    _LED_COLORS = {
        "LED-ON": _LED_GREEN,
        "LED-RX": _LED_YELLOW,
        "LED-TX": _LED_YELLOW,
        "LED-L":  _LED_YELLOW,
    }
    for led_name, led_color in _LED_COLORS.items():
        sc = _ssot_sub(led_name)
        cx, cy = _ds(sc.anchor_x, sc.anchor_y)
        dx, dy = _rotated_xy(sc)
        lbl = led_name.replace("-", "_")
        _add(parts, _box(cx, cy, pz + sc.body_h / 2, dx, dy, sc.body_h),
             led_color, lbl)
        # 透鏡微凸（同色圓盤）
        _add(parts, _cyl(cx, cy, pz + sc.body_h + 0.15, min(dx, dy) * 0.35, 0.3),
             led_color, f"{lbl}_Lens")

    # ─── 15. Reset Button ──────────────────────────────────
    # SSOT: lib/pcb/arduino_uno_r3.py — Reset-Switch (TS42031-160R-TR-7260)
    # 真實位置：EAGLE (6.35, 49.403) — 左上角貼著 USB-B（並非靠近 ATmega328P）
    rst = _ssot_sub("Reset-Switch")
    rst_cx, rst_cy = _ds(rst.anchor_x, rst.anchor_y)
    rst_base_h = rst.body_h - 1.5   # 本體高 - 按鈕突出
    # 黑色塑膠本體
    _add(parts, _box(rst_cx, rst_cy, pz + rst_base_h / 2,
                     rst.body_l, rst.body_w, rst_base_h),
         _BLACK, "Reset_Button")
    # 黃色按鈕帽（TS42 系列典型外觀）
    _add(parts, _cyl(rst_cx, rst_cy, pz + rst_base_h + 0.75, 1.5, 1.5),
         _LED_YELLOW, "Reset_Top")

    # ─── 16. Arduino Logo 絲印 ────────────────────────────
    _add(parts, _box(*_ds(34.0, 42.0), pz + 0.02, 15.0, 3.0, 0.04),
         _WHITE, "Arduino_Logo")

    return bd.Compound(children=parts, label="Arduino_Uno_R3_PCB")


# ---------------------------------------------------------------------------
# Header Row 輔助
# ---------------------------------------------------------------------------
_PLASTIC_H = 8.5
_PIN_DIA = 0.64


def _add_header_row(parts: list, pz: float,
                    pin_coords: List[Tuple[float, float]],
                    group_name: str, side: str):
    """添加一組 female header receptacle：黑色塑膠座 + 內部金色接觸片。

    Args:
        pin_coords: [(ds_x, ds_y), ...] datasheet 座標
        side: 'bottom' (y=2.54, -Y edge) 或 'top' (y=50.80, +Y edge)
    """
    if not pin_coords:
        return

    xs = [p[0] for p in pin_coords]
    ys = [p[1] for p in pin_coords]
    span_x = max(xs) - min(xs) + 2.54
    center_x = (min(xs) + max(xs)) / 2
    center_y = (min(ys) + max(ys)) / 2
    cx, cy = _ds(center_x, center_y)

    # 塑膠座（母頭較高）+ 每 pin 由頂面挖出方形受孔（真實母排外型）
    holes = [_ds(px_ds, py_ds) for px_ds, py_ds in pin_coords]
    _add(parts, _box_holes(cx, cy, pz + _PLASTIC_H / 2, span_x, 2.54, _PLASTIC_H,
                           holes, hole=1.6, depth=6.0),
         _BLACK, f"Header_{group_name}_Plastic")

    # 受孔底部金色接觸片（凹進孔內）
    contact_h = 3.0
    for px, py in holes:
        _add(parts, _cyl(px, py, pz + contact_h / 2, _PIN_DIA / 2, contact_h),
             _PIN_GOLD, f"Pin_{group_name}")


# ---------------------------------------------------------------------------
# 匯出（GLB 多色 → 落回 STL 單色）
# ---------------------------------------------------------------------------
# _export_glb 由 lib.cad.pcb_common.export_glb 提供（見上方 import 別名）。
# 該共用版本含 os.makedirs 目錄保護，並把 teal/低色彩多樣性 fallback 升級為
# RuntimeError，避免在兩處重複維護同一份匯出邏輯。
def export_arduino_pcb(output_dir: str) -> str:
    """建立 Arduino Uno R3 PCB 並匯出。

    嘗試匯出 GLB（多色）；若 trimesh 不可用，fallback 為 STL。
    回傳匯出的檔案路徑。
    """
    os.makedirs(output_dir, exist_ok=True)
    compound = build_arduino_pcb_body()

    # 嘗試 GLB
    glb_path = os.path.join(output_dir, "pcb_body.glb")
    if _export_glb(compound, glb_path):
        print(f"[pcb_body] GLB exported → {glb_path}")
        # 同時匯出 STL（向後兼容）
        stl_path = os.path.join(output_dir, "pcb_body.stl")
        bd.export_stl(compound, stl_path, tolerance=0.05)
        return glb_path

    # Fallback: STL only
    stl_path = os.path.join(output_dir, "pcb_body.stl")
    bd.export_stl(compound, stl_path, tolerance=0.05)
    print(f"[pcb_body] STL exported → {stl_path}")
    return stl_path


def export_arduino_pcb_stl(output_path: str) -> None:
    """向後兼容：匯出 STL。"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    compound = build_arduino_pcb_body()
    bd.export_stl(compound, output_path, tolerance=0.05)
    print(f"[pcb_body] STL exported → {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    out_dir = str(repo_root / "shells" / "Arduino-Uno-class")

    print("[pcb_body] Building Arduino Uno R3 PCB model …")
    result = export_arduino_pcb(out_dir)

    # 驗證 BBox
    compound = build_arduino_pcb_body()
    bb = compound.bounding_box()
    print(f"[pcb_body] BBox: X=[{bb.min.X:.1f}, {bb.max.X:.1f}] "
          f"Y=[{bb.min.Y:.1f}, {bb.max.Y:.1f}] "
          f"Z=[{bb.min.Z:.1f}, {bb.max.Z:.1f}]")
    print(f"[pcb_body] Size: {bb.max.X-bb.min.X:.1f} × {bb.max.Y-bb.min.Y:.1f} × {bb.max.Z-bb.min.Z:.1f} mm")
    print("[pcb_body] Done.")
