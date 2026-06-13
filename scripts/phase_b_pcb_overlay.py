"""Phase B 視覺化驗證 — Arduino Uno R3 PCB 佈局 + datasheet overlay。

輸出：
  1. PCB 完整佈局圖（38 個 named pins + ICs + headers + 對齊輔助線）
  2. PDF page 12 (Board Outline) 抽取為 PNG
  3. registry.py spec.ports vs PCBSpec 一致性檢查
"""
from __future__ import annotations
import sys, os
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError) as exc:
    print(f"[phase_b_pcb_overlay] reconfigure failed: {exc}", file=sys.stderr, flush=True)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from lib.pcb import (
    ARDUINO_UNO_R3, JANALOG_PINS, JDIGITAL_PINS, ICSP_PINS,
    HEADER_GROUPS, derive_connector_port_specs, find_pin,
)
from lib.pcb.arduino_uno_r3 import SUB_COMPONENTS

OUT_DIR = Path('output/phase_b_verify')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def draw_pcb_layout():
    """生成 Arduino Uno R3 完整 PCB 佈局圖（含所有 38 pins + ICs）。"""
    fig, ax = plt.subplots(figsize=(18, 14))
    ax.set_title('Arduino Uno R3 — PCB Layout (Phase A 三來源權威座標)',
                 fontsize=16, fontweight='bold')

    L, W = ARDUINO_UNO_R3.length, ARDUINO_UNO_R3.width
    # PCB 板
    ax.add_patch(mpatches.Rectangle((0, 0), L, W,
                 lw=2.5, ec='black', fc='#e8f5e9', zorder=1))

    # Mounting holes
    for h in ARDUINO_UNO_R3.mounting_holes:
        ax.add_patch(mpatches.Circle((h.x, h.y), h.diameter/2,
                     lw=1.5, ec='red', fc='white', zorder=10))
        ax.text(h.x, h.y - 3, f'⌀{h.diameter}', ha='center', va='top',
                fontsize=6, color='red')

    # Sub-components (ICs, connectors, etc.)
    SC_COLORS = {
        'USB-B': '#e74c3c', 'DC-Jack': '#f39c12',
        'ATmega328P': '#34495e', 'ATmega16U2': '#7f8c8d',
        'V-Reg-5V': '#16a085', 'Crystal-16MHz': '#8e44ad',
        'Resonator-ATmega': '#c39bd3', 'ICSP-16U2': '#5d6d7e',
    }
    for sc in SUB_COMPONENTS:
        color = SC_COLORS.get(sc.name, '#bdc3c7')
        # 簡化：以 anchor 為中心畫 body box（不考慮旋轉）
        bx, by = sc.anchor_x - sc.body_l/2, sc.anchor_y - sc.body_w/2
        ax.add_patch(mpatches.Rectangle((bx, by), sc.body_l, sc.body_w,
                     lw=1.2, ec=color, fc=color, alpha=0.5, zorder=5))
        ax.text(sc.anchor_x, sc.anchor_y, sc.name,
                ha='center', va='center', fontsize=7,
                fontweight='bold', color='white', zorder=6)

    # Header groups (slots) 從 derive_connector_port_specs
    ports = derive_connector_port_specs()
    HG_COLORS = {
        'Power-Header': '#e67e22', 'Analog-A0~A5': '#3498db',
        'Digital-D0~D7': '#27ae60', 'Digital-D8~SCL': '#2ecc71',
        'ICSP': '#9b59b6',
    }
    for p in ports:
        if p['side'] == 'left':
            continue  # USB / DC-Jack 已由 SUB_COMPONENTS 畫
        color = HG_COLORS.get(p['name'], '#95a5a6')
        cx, cy = p['x'], p['y']
        bx = cx - p['width']/2
        by = cy - p['height']/2
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx, by), p['width'], p['height'],
            boxstyle='round,pad=0.05,rounding_size=0.8',
            lw=1.2, ec=color, fc=color, alpha=0.4, zorder=4))
        ax.text(cx, cy + p['height']/2 + 1.5, p['name'],
                ha='center', va='bottom', fontsize=7,
                color=color, fontweight='bold')

    # 38 個 NamedPin 個別繪製（金色方塊）
    for pin in list(JANALOG_PINS) + list(JDIGITAL_PINS) + list(ICSP_PINS):
        ax.add_patch(mpatches.Rectangle((pin.x - 0.6, pin.y - 0.6), 1.2, 1.2,
                     lw=0.5, ec='black', fc='gold', alpha=0.95, zorder=8))
        # 顯示 arduino_pin name 或 NC
        label = pin.arduino_pin or pin.name.split('/')[0]
        # 只標部分（避免擁擠）
        if pin.pad_index in (1, 8, 9, 14, 15, 22, 23, 32) or pin in ICSP_PINS:
            offset_y = -2.5 if pin.y < 30 else 2.5
            ax.text(pin.x, pin.y + offset_y, label,
                    ha='center', va='center' if abs(offset_y) > 1 else 'baseline',
                    fontsize=5.5, color='black')

    # ── 關鍵交叉驗證標註 ────────────────────────────────────────
    # A5 / D0 對齊線
    a5 = find_pin('A5')
    d0 = find_pin('D0')
    ax.plot([a5.x, a5.x], [-2, W + 2], '--', color='red', lw=1.2, alpha=0.7, zorder=3)
    ax.text(a5.x + 0.3, W + 3.5, f'A5 = D0 = x={a5.x:.3f}',
            color='red', fontsize=8, ha='left', fontweight='bold')

    # NC ~ A5 跨距 vs ATmega328P 長度
    nc = JANALOG_PINS[0]
    ax.annotate('', xy=(nc.x, -7), xytext=(a5.x, -7),
                arrowprops=dict(arrowstyle='<->', color='#e67e22', lw=1.5))
    ax.text((nc.x + a5.x)/2, -8.5, f'NC~A5 = {a5.x - nc.x:.3f}mm',
            color='#e67e22', fontsize=9, ha='center', fontweight='bold')
    # ATmega328P 長度標註
    atm = next(s for s in SUB_COMPONENTS if s.name == 'ATmega328P')
    atm_left = atm.anchor_x - atm.body_l/2
    atm_right = atm.anchor_x + atm.body_l/2
    ax.annotate('', xy=(atm_left, -12), xytext=(atm_right, -12),
                arrowprops=dict(arrowstyle='<->', color='#34495e', lw=1.5))
    ax.text(atm.anchor_x, -13.5,
            f'ATmega328P body = {atm.body_l:.3f}mm  (應等於 NC~A5)',
            color='#34495e', fontsize=9, ha='center', fontweight='bold')

    # D7-D8 非標 gap
    d7 = find_pin('D7')
    d8 = find_pin('D8')
    ax.annotate('', xy=(d8.x, W + 6), xytext=(d7.x, W + 6),
                arrowprops=dict(arrowstyle='<->', color='#c0392b', lw=1.2))
    ax.text((d7.x + d8.x)/2, W + 7.5, f'D7-D8 gap = {d7.x - d8.x:.3f}mm (160mil)',
            color='#c0392b', fontsize=8, ha='center', fontweight='bold')

    # VIN-A0 gap
    vin = find_pin('VIN')
    a0 = find_pin('A0')
    ax.annotate('', xy=(vin.x, -3.5), xytext=(a0.x, -3.5),
                arrowprops=dict(arrowstyle='<->', color='#2980b9', lw=1.2))
    ax.text((vin.x + a0.x)/2, -4.8, f'VIN-A0 = {a0.x - vin.x:.3f}mm (200mil)',
            color='#2980b9', fontsize=8, ha='center', fontweight='bold')

    ax.set_xlim(-5, L + 6)
    ax.set_ylim(-18, W + 12)
    ax.set_aspect('equal')
    ax.set_xlabel('X (mm) — PCB 左下角為原點', fontsize=10)
    ax.set_ylabel('Y (mm)', fontsize=10)
    ax.grid(True, ls=':', alpha=0.3)

    out = OUT_DIR / 'arduino_uno_r3_pcb_layout.png'
    fig.savefig(out, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'[1/3] PCB layout saved: {out}')


def extract_datasheet_mechanical_drawing():
    """從 A000066 PDF page 12 抽取 Mechanical Information 機械圖為 PNG。"""
    try:
        import fitz
    except ImportError:
        print('  [WARN] PyMuPDF not installed, skipping')
        return

    pdf = 'data/pcb_sources/arduino_uno_r3/A000066-datasheet.pdf'
    doc = fitz.open(pdf)
    # Page 12 (index 11) has the board outline
    for page_num in [11, 12]:
        if page_num >= len(doc):
            continue
        page = doc[page_num]
        pix = page.get_pixmap(dpi=200)
        out = OUT_DIR / f'datasheet_page_{page_num+1}.png'
        pix.save(str(out))
        print(f'[2/3] Datasheet page {page_num+1} saved: {out}')


def consistency_check():
    """registry.spec.ports vs PCBSpec.derive_connector_port_specs() 一致性。"""
    from lib.registry import COMPONENT_REGISTRY
    spec = COMPONENT_REGISTRY['Arduino-Uno-class']
    derived = derive_connector_port_specs()

    print('[3/3] Consistency check: registry vs PCBSpec')
    if len(spec.ports) != len(derived):
        print(f'  [FAIL] Port count mismatch: registry={len(spec.ports)} vs derived={len(derived)}')
        return False

    all_match = True
    for reg_port, der in zip(spec.ports, derived):
        if (reg_port.name != der['name'] or
            abs(reg_port.x - der['x']) > 0.001 or
            abs(reg_port.y - der['y']) > 0.001 or
            abs(reg_port.width - der['width']) > 0.001 or
            abs(reg_port.height - der['height']) > 0.001):
            print(f'  [FAIL] {reg_port.name}: registry({reg_port.x},{reg_port.y},{reg_port.width}x{reg_port.height}) '
                  f'vs derived({der["x"]},{der["y"]},{der["width"]}x{der["height"]})')
            all_match = False
    if all_match:
        print(f'  [OK] All {len(spec.ports)} ports match exactly between registry and PCBSpec')
    return all_match


if __name__ == '__main__':
    draw_pcb_layout()
    extract_datasheet_mechanical_drawing()
    ok = consistency_check()
    sys.exit(0 if ok else 1)
