"""Phase 4 端到端測試 — 模擬 bridge JSON 跑完整 dispatch。

驗證項：
  1. Brain (Arduino) → main_base.stl + main_lid.stl
  2. Tier 4 (Servo) → mount_sg90_bracket.stl
  3. Tier 3 (Button, skip_enclosure=True) → 略過
  4. cad_output 結構正確
"""
import os, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.phase_handlers.phase4_handler import Phase4Handler
from services.shared.models import Job, PhaseID, JobStatus
from datetime import datetime
import uuid


def _make_job(workdir: Path) -> Job:
    """測試用 Job — 寫到 workdir。"""
    return Job(
        job_id=str(uuid.uuid4())[:8],
        project_name='test_phase4',
        instruction='test phase4',
        status=JobStatus.RUNNING,
    )


def main():
    # 模擬 bridge — Brain (Arduino) + Servo + Button
    bridge = {
        'project_name': 'test_phase4',
        'components': [
            {'role': 'Brain',   'type': 'Arduino-Uno-class', 'qty': 1},
            {'role': 'Control', 'type': 'Motor-Servo-class', 'qty': 1},
            {'role': 'Input',   'type': 'Button-class',      'qty': 1},
            {'role': 'Sensor',  'type': 'Sensor-TempHumid-class', 'qty': 1},
        ],
    }

    tmpdir = Path(tempfile.mkdtemp(prefix='phase4_test_'))
    print(f'tempdir: {tmpdir}')

    # 暫時把 project_output_dir 指到 tmpdir（讓 phase4 寫到那裡）
    import services.shared.bridge_store as bs
    original_proj_dir = bs.project_output_dir
    bs.project_output_dir = lambda job: str(tmpdir)

    try:
        handler = Phase4Handler()
        job = _make_job(tmpdir)

        msgs = []
        bridge_out, artifacts = handler.execute(
            job, bridge, progress_cb=lambda m: msgs.append(m))

        print('\n=== 進度訊息 ===')
        for m in msgs:
            print(f'  {m}')

        print('\n=== artifacts ===')
        for k, v in artifacts.items():
            print(f'  {k}: {v}')

        cad = bridge_out.get('cad_output', {})
        print('\n=== cad_output ===')
        for k, v in cad.items():
            if k == 'component_shells':
                print(f'  {k}: {len(v)} shells')
                for s in v:
                    print(f'    - {s}')
            else:
                print(f'  {k}: {v}')

        # 驗證生成的檔案
        print('\n=== 生成的檔案 ===')
        for f in sorted((tmpdir / 'cad').glob('*')):
            print(f'  {f.name}: {f.stat().st_size:,} bytes')

        # ── 驗收 ─────────────────────────────────────────
        bottom = cad.get('bottom_stl')
        lid = cad.get('lid_stl')
        shells = cad.get('component_shells', [])

        print('\n=== 驗收 ===')
        assert bottom and Path(bottom).exists(), 'bottom_stl 未生成'
        print(f'  ✅ bottom_stl: {Path(bottom).name}')
        assert lid and Path(lid).exists(), 'lid_stl 未生成'
        print(f'  ✅ lid_stl: {Path(lid).name}')

        servo_shells = [s for s in shells if s.get('class') == 'Motor-Servo-class']
        assert servo_shells, 'Servo mount 未生成'
        servo_stl = servo_shells[0].get('stl')
        assert servo_stl and Path(servo_stl).exists(), 'Servo STL 檔不存在'
        print(f'  ✅ Servo mount: {Path(servo_stl).name}')

        button_shells = [s for s in shells if s.get('class') == 'Button-class']
        assert not button_shells, 'Button 應被 skip_enclosure 跳過但卻生成了'
        print(f'  ✅ Button 正確被略過（skip_enclosure=True）')

        # 驗 watertight
        import trimesh
        for stl_path in [bottom, lid, servo_stl]:
            m = trimesh.load(stl_path)
            assert m.is_watertight, f'{Path(stl_path).name} not watertight'
            print(f'  ✅ {Path(stl_path).name} watertight ({len(m.faces)} faces)')

        print('\n=== Phase 4 E2E 測試通過 ===')
    finally:
        bs.project_output_dir = original_proj_dir
        # 保留 tmpdir 給人檢查
        print(f'\n（保留 tempdir 供檢查：{tmpdir}）')


if __name__ == '__main__':
    main()
