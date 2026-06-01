"""Snap-fit 卡扣與外殼適配性診斷分析。

從 build_pcb_two_piece 的預設參數出發，計算：
  1. lip / recess 幾何重疊 (engagement)
  2. arm 撓曲應力 (PETG yield 比較)
  3. 列印方向影響
  4. 與 PCB 元件的 Z 軸關係
  5. 防誤插 (anti-rotation) 評估
"""
from __future__ import annotations
import sys, os
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib.pcb import ARDUINO_UNO_R3
from lib.cad import compute_two_piece_spec

# 純算尺寸，不跑 build123d B-rep（節省 ~3 秒）
print('=== 計算 Phase A 殼體尺寸 ===')
spec = compute_two_piece_spec(ARDUINO_UNO_R3)

L = ARDUINO_UNO_R3.length
W = ARDUINO_UNO_R3.width

# ── 還原 lip / recess / arm 在 ASSEMBLY 座標系（base 為原點）的位置 ─
print('\n=== 1. 幾何位置（assembly 座標系）===')

# 防誤插設計：+Y 與 -Y 邊用不同 X 位置
snap_arm_xs_pos_y = [-spec.outer_l * 0.30, +spec.outer_l * 0.30]
snap_arm_xs_neg_y = [-spec.outer_l * 0.20, +spec.outer_l * 0.20]
print(f'Snap arm X 位置 (+Y 邊): {snap_arm_xs_pos_y}')
print(f'Snap arm X 位置 (-Y 邊): {snap_arm_xs_neg_y}')

# Arm（lid 本地）→ 組裝後 +（base_h+lid_h）/2
# 但 base 中心在 z=0，lid translate dz = (base_h + lid_h)/2 = 12.05
dz = (spec.base_h + spec.lid_h) / 2

# Arm Y/Z (assembly)
y_sign = 1   # +Y face
arm_y = y_sign * (spec.outer_w/2 + spec.snap_gap + spec.snap_arm_t/2)
arm_z_lid_local_center = -spec.lid_h/2 - spec.snap_arm_h/2
arm_z_assembly = arm_z_lid_local_center + dz

# Arm 完整範圍
arm_y_range = (arm_y - spec.snap_arm_t/2, arm_y + spec.snap_arm_t/2)
arm_z_range = (arm_z_assembly - spec.snap_arm_h/2, arm_z_assembly + spec.snap_arm_h/2)
print(f'\nArm（+Y 邊，1 個）:')
print(f'  Y 範圍: [{arm_y_range[0]:.3f} .. {arm_y_range[1]:.3f}]  (寬 {spec.snap_arm_t}mm)')
print(f'  Z 範圍: [{arm_z_range[0]:.3f} .. {arm_z_range[1]:.3f}]  (長 {spec.snap_arm_h}mm)')

# Lip 中心 + 範圍（lid 本地代碼）
lip_y_lid_local = y_sign * (spec.outer_w/2 + spec.snap_gap - spec.snap_lip_d/2)
lip_z_lid_local = -spec.lid_h/2 - spec.snap_arm_h + spec.snap_lip_h/2 + 0.3
lip_y_box_w = spec.snap_lip_d   # 修正後的 lip 盒子 Y 寬度（原 bug 已修）
lip_y_range = (lip_y_lid_local - lip_y_box_w/2, lip_y_lid_local + lip_y_box_w/2)
lip_z_assembly = lip_z_lid_local + dz
lip_z_range = (lip_z_assembly - spec.snap_lip_h/2, lip_z_assembly + spec.snap_lip_h/2)
print(f'\nLip 倒鉤（assembly 座標）:')
print(f'  Y 範圍: [{lip_y_range[0]:.3f} .. {lip_y_range[1]:.3f}]  (寬 {lip_y_box_w}mm)')
print(f'  Z 範圍: [{lip_z_range[0]:.3f} .. {lip_z_range[1]:.3f}]  (高 {spec.snap_lip_h}mm)')

# Recess 範圍（base 本地，與 assembly 同因 base 中心在 0）
recess_d = spec.snap_lip_d + 0.4   # snap_recess_extra 預設 0.4
recess_w = spec.snap_arm_w + 0.4
recess_h = spec.snap_lip_h + 0.4
ry = y_sign * (spec.outer_w/2 - recess_d/2)
rz = spec.base_h/2 - spec.snap_arm_h + spec.snap_lip_h/2 + 0.3
recess_y_range = (ry - recess_d/2, ry + recess_d/2)
recess_z_range = (rz - recess_h/2, rz + recess_h/2)
outer_wall_face = y_sign * spec.outer_w/2
print(f'\nRecess 凹槽（base 本地）:')
print(f'  Y 範圍: [{recess_y_range[0]:.3f} .. {recess_y_range[1]:.3f}]  (深 {recess_d}mm 進牆)')
print(f'  Z 範圍: [{recess_z_range[0]:.3f} .. {recess_z_range[1]:.3f}]  (高 {recess_h}mm)')
print(f'  外壁面在 y = {outer_wall_face}')

# ── 重疊分析 ────────────────────────────────────────────
print('\n=== 2. Lip ↔ Recess 重疊分析 ===')
overlap_y_min = max(lip_y_range[0], recess_y_range[0])
overlap_y_max = min(lip_y_range[1], recess_y_range[1])
overlap_y = max(0, overlap_y_max - overlap_y_min)
overlap_z_min = max(lip_z_range[0], recess_z_range[0])
overlap_z_max = min(lip_z_range[1], recess_z_range[1])
overlap_z = max(0, overlap_z_max - overlap_z_min)
print(f'Y 方向重疊量: {overlap_y:.3f}mm  (需 ≥ 0.5mm 才能可靠扣合)')
print(f'Z 方向重疊量: {overlap_z:.3f}mm  (需 = snap_lip_h = {spec.snap_lip_h}mm)')

# Lip 探出外壁的部分（Y 方向）
lip_outside_wall = max(0, lip_y_range[1] - outer_wall_face) if y_sign > 0 else max(0, outer_wall_face - lip_y_range[0])
print(f'Lip 探出外壁面（無支撐部份）: {lip_outside_wall:.3f}mm  ({"[WARN] waste/protrusion" if lip_outside_wall > 0.2 else "[OK]"})')

# ── 應力分析 ─────────────────────────────────────────────
print('\n=== 3. 懸臂應力分析（PETG, E=2000 MPa）===')
E = 2000        # MPa = N/mm²
yield_strain_petg = 0.04   # PETG 約 4-5%
yield_strain_pla = 0.02    # PLA 約 2-3%
yield_strain_abs = 0.06    # ABS 約 6%

L_arm = spec.snap_arm_h
w = spec.snap_arm_w
t = spec.snap_arm_t
deflection = spec.snap_lip_d   # 插入時 arm 必須撓曲量（lip 須清越外壁）

I = w * t**3 / 12   # 慣性矩
P = 3 * E * I * deflection / L_arm**3   # 端部反作用力
strain_max = 3 * t * deflection / (2 * L_arm**2)   # 最大應變
stress_max = strain_max * E   # 最大應力

print(f'懸臂尺寸:    L={L_arm} × w={w} × t={t}mm')
print(f'撓曲位移:    {deflection}mm')
print(f'慣性矩 I:    {I:.4f} mm⁴')
print(f'端部反作用力: {P:.2f} N (插入/拔取阻力)')
print(f'最大應變:    {strain_max*100:.2f}%')
print(f'最大應力:    {stress_max:.1f} MPa')
print()
for name, ystrain in [('PLA', yield_strain_pla), ('PETG', yield_strain_petg), ('ABS', yield_strain_abs)]:
    ratio = strain_max / ystrain
    flag = '[OK]' if ratio < 0.7 else ('[WARN] near yield' if ratio < 1.0 else '[FAIL] over yield')
    print(f'  {name:5s} (yield {ystrain*100:.0f}%): 利用率 {ratio*100:.1f}%  {flag}')

# 4 個 arm 一起的總插入力
total_insert_force = P * spec.snap_count
print(f'\n4 arm total insertion force: {total_insert_force:.1f} N  ({"[OK] hand-pressable" if total_insert_force < 80 else "[WARN] needs tool"})')

# ── PCB header 高度 vs lid 切口位置 ─────────────────────
print('\n=== 4. PCB Header ↔ Lid Cutout Z 對位 ===')
# 假設 pin header 高度 = 11.5mm（DIP 排針）
pin_header_h = 11.5
pcb_top_assembly = spec.pcb_top_z   # base 本地 = assembly
header_top_assembly = pcb_top_assembly + pin_header_h
lid_bottom_assembly = spec.base_h/2  # base top
lid_top_assembly = lid_bottom_assembly + spec.lid_h

print(f'PCB 表面 Z:        {pcb_top_assembly:.2f}')
print(f'Pin header 頂端 Z: {header_top_assembly:.2f}  (PCB 表面 +11.5mm)')
print(f'Lid 底面 Z:        {lid_bottom_assembly:.2f}')
print(f'Lid 頂面 Z:        {lid_top_assembly:.2f}')

gap_above_header = lid_bottom_assembly - header_top_assembly
print(f'\nHeader 頂端到 Lid 底面間距: {gap_above_header:.2f}mm')
if gap_above_header > 5:
    print('  [FAIL] gap too large, pin header won\'t reach lid cutout')
elif gap_above_header > 1:
    print('  [WARN] pin header inside lid, dupont cable must go through cutout')
elif gap_above_header > -2:
    print('  [OK] pin header flush with lid cutout')
else:
    print('  [FAIL] pin header collides with lid, cannot assemble')

# ── 標準件相容性 ─────────────────────────────────────────
print('\n=== 5. Standoff 螺絲適配 ===')
standoff_outer_d = 5.0
standoff_inner_d = 2.5
print(f'Standoff: 外⌀{standoff_outer_d} / 內⌀{standoff_inner_d}mm')
print(f'PCB mounting hole: ⌀3.2mm')
print()
SCREWS = [
    ('M2.5 self-tap', 2.5, 2.0, 'PETG'),
    ('M3 self-tap',   3.0, 2.5, 'PETG'),
    ('M2.5 機械螺紋', 2.5, 2.5, 'with insert'),
    ('M3 機械螺紋',   3.0, 2.7, 'with insert'),
]
for name, thread_od, pilot_d, note in SCREWS:
    fits_pcb = thread_od < 3.2
    fits_pilot = abs(pilot_d - standoff_inner_d) < 0.3
    flag = '✅' if (fits_pcb and fits_pilot) else '❌'
    print(f'  {name:20s} 軸⌀{thread_od} / 建議底孔⌀{pilot_d:.1f}  PCB:{"✓" if fits_pcb else "✗"} 底孔:{"✓" if fits_pilot else "✗"}  {flag}  ({note})')

print(f'\n當前 ⌀{standoff_inner_d} 底孔最匹配: M3 self-tap 螺絲（PETG）')

# ── 對稱/防誤插評估 ─────────────────────────────────────
print('\n=== 6. 防誤插評估（Lid 旋轉對稱性） ===')
print(f'+Y 邊 arm X: {[round(x, 2) for x in snap_arm_xs_pos_y]}')
print(f'-Y 邊 arm X: {[round(x, 2) for x in snap_arm_xs_neg_y]}')
print()
# 模擬 180° 旋轉：(x, y) → (-x, -y)
print('180° 旋轉後的 arm 位置（檢查是否仍能對到 base recess）:')
mismatch_count = 0
for orig_y_sign, orig_xs in [(+1, snap_arm_xs_pos_y), (-1, snap_arm_xs_neg_y)]:
    for ox in orig_xs:
        rotated_x = -ox
        rotated_y_sign = -orig_y_sign
        # 檢查是否能對到任何 base recess
        target_xs = snap_arm_xs_pos_y if rotated_y_sign == +1 else snap_arm_xs_neg_y
        match = any(abs(rotated_x - tx) < 0.5 for tx in target_xs)
        if not match:
            mismatch_count += 1
print(f'  共 {mismatch_count}/4 個 arm 在 180° 旋轉後對不到 recess')
if mismatch_count >= 2:
    print('  [OK] anti-rotation effective (>=2 arms misaligned)')
else:
    print('  [FAIL] anti-rotation ineffective')

# ── 列印方向建議 ─────────────────────────────────────
print('\n=== 7. 列印方向 ===')
print('Base:  底面朝下印（standoffs 朝上）— 自然，無支撐材')
print('Lid:   平板面朝下印（snap arms 朝上）— 必須這樣，否則：')
print('       [FAIL] arms down: layer-line delamination on flexure')
print('       [OK] arms up: flex direction = in-layer, max strength')
print('       額外：lid header cutouts 是穿透孔，無支撐材問題')

print('\n=== 結論 ===')
