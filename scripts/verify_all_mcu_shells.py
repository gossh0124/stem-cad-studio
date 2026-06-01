"""驗證 4 個 MCU 殼體生成（多側 cutouts 測試 RPi）。

採用 Verification Spine：
  L0  STL 可載入、有面、bounds 非退化、無 NaN
  L1  watertight（非 watertight → 列印漏水 → FAIL gate）

任一殼體未通過即 exit 1，不再無條件印「成功」。
"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # CP950 終端安全

import trimesh
from lib.pcb import ARDUINO_UNO_R3, ESP32_DEVKIT_V1, MICROBIT_V2, RASPBERRY_PI_4B
from lib.cad import build_pcb_two_piece, export_step, export_stl_high_density
from lib.verification import check_mesh, CheckResult, Verdict, VerificationReport

OUT = Path('output/all_mcu_shells')
OUT.mkdir(parents=True, exist_ok=True)

MCUS = [
    ('arduino_uno', ARDUINO_UNO_R3),
    ('esp32_devkit_v1', ESP32_DEVKIT_V1),
    ('microbit_v2', MICROBIT_V2),
    ('raspberry_pi_4b', RASPBERRY_PI_4B),
]


def verify_stl(path: Path, label: str) -> VerificationReport:
    """L0 完整性 + L1 watertight。"""
    rpt = check_mesh(str(path), name=label)
    # 若 L0 已掛（載入/退化），不再續驗 L1
    if rpt.verdict == Verdict.FAIL:
        return rpt
    try:
        m = trimesh.load(str(path), force='mesh')
        wt = bool(m.is_watertight)
        bodies = len(m.split(only_watertight=False))
        rpt.add(CheckResult(
            layer="L1", name="watertight",
            verdict=Verdict.PASS if wt else Verdict.FAIL,
            metric={"watertight": wt, "bodies": bodies},
            message="" if wt else "mesh 非 watertight（3D 列印會漏/失敗）",
        ))
    except Exception as exc:  # noqa: BLE001
        rpt.add(CheckResult(layer="L1", name="watertight",
                            verdict=Verdict.FAIL, message=f"watertight 檢查失敗: {exc}"))
    return rpt


def main() -> int:
    print('=== 4 MCU Shell Generation ===')
    reports: list[VerificationReport] = []
    for name, pcb in MCUS:
        print(f'\n--- {pcb.name} ---')
        try:
            base, lid, spec = build_pcb_two_piece(pcb)
        except Exception as exc:  # noqa: BLE001 — 生成失敗納入 verdict，不裸 traceback
            r = VerificationReport(artifact=name, artifact_type='shell')
            r.add(CheckResult(layer="L1", name="generation", verdict=Verdict.FAIL,
                              message=f"build_pcb_two_piece 失敗: {exc}"))
            reports.append(r)
            print(f'  [FAIL] 生成失敗: {exc}')
            continue
        print(f'  Outer: {spec.outer_l:.2f} × {spec.outer_w:.2f} × {spec.base_h:.2f}+{spec.lid_h:.2f}mm')
        print(f'  Cutouts: side={spec.side_cutout_count} lid={spec.lid_cutout_count}')
        print(f'  Standoffs: {spec.standoff_count}, Snap arms: {spec.snap_count}')

        base_stl = OUT / f'{name}_base.stl'
        lid_stl = OUT / f'{name}_lid.stl'
        base_tris = export_stl_high_density(base, base_stl)
        lid_tris = export_stl_high_density(lid, lid_stl)
        print(f'  base.stl: {base_tris} tris, lid.stl: {lid_tris} tris')

        reports.append(verify_stl(base_stl, f'{name}_base'))
        reports.append(verify_stl(lid_stl, f'{name}_lid'))

    print('\n=== 驗證結果 ===')
    for r in reports:
        print(r.render_text())

    n_fail = sum(1 for r in reports if r.verdict == Verdict.FAIL)
    if n_fail:
        print(f'\n[FAIL] {n_fail}/{len(reports)} shells did not pass verification.')
        return 1
    print(f'\n[OK] All {len(reports)} shells passed L0+L1 verification.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
