"""lib/cad/glb_convert.py — shells/ 的 STL→GLB 後處理（索引化、縮小、載入更快）。

assembly 視圖（v6/views-engineer-assembly-v3.jsx）逐模組從 shells/{type}/ 載入 mesh。
STL 是無索引三角湯，GLB 焊接重複頂點 + 索引化二進位 → 同幾何約 1/3~1/4 大、載入更快。

策略（對齊 D7 修正案：逐模組 GLB + 載一次快取，保留 assembly 互動）：
  base / lid / mount  : STL → 同名 .glb（單色，前端自行上色）。
  pcb_body            : 已由 lib/cad/pcb_common.export_glb 產生多色 GLB，**不在此覆蓋**。

無容錯：轉換失敗一律收集後 raise，不靜默略過（pcb_body/缺檔屬正常 N/A 才跳過）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

# variant → (STL 來源檔, GLB 目標檔)。
# pcb_body 多色 GLB 由 export_glb 產生；此處僅在「無 pcb_body.glb」時由 STL 補單色版
# （overwrite 預設 False 保護既有多色檔，見 ensure_shell_glbs 的 skip 規則）。
_VARIANT_STL_GLB = {
    "base":     ("base_stl.stl",  "base.glb"),
    "lid":      ("lid_stl.stl",   "lid.glb"),
    "mount":    ("mount_stl.stl", "mount.glb"),
    "pcb_body": ("pcb_body.stl",  "pcb_body.glb"),
}


def stl_to_glb(stl_path, glb_path=None) -> bool:
    """單檔 STL → GLB（trimesh，process=True 焊接頂點→索引化）。
    RF1: STL 是 Z-up（3D 列印慣例），GLB 必須 Y-up（glTF spec）。轉換時套用 (x,y,z)→(x,z,-y)。失敗 raise。
    """
    import trimesh
    import numpy as np

    stl_path = Path(stl_path)
    if glb_path is None:
        glb_path = stl_path.with_suffix(".glb")
    mesh = trimesh.load(str(stl_path), file_type="stl", process=True)
    n_faces = getattr(mesh, "faces", None)
    if mesh.is_empty or n_faces is None or len(n_faces) == 0:
        raise ValueError(f"STL 載入為空或無面: {stl_path}")
    # Z-up → Y-up: (x, y, z) → (x, z, -y)
    v = mesh.vertices
    mesh.vertices = np.column_stack([v[:, 0], v[:, 2], -v[:, 1]])
    mesh.export(str(glb_path), file_type="glb")
    return True


def ensure_shell_glbs(shells_dir, types: Optional[Sequence[str]] = None, *,
                      overwrite: bool = False) -> Dict[str, List[str]]:
    """對 shells/{type}/ 的 base/lid/mount STL 產生對應 GLB。

    types=None → 掃全部子目錄。回 {converted, skipped}。
    任何轉換失敗收集後 raise RuntimeError（禁容錯）；無此 variant 屬正常，跳過不報錯。
    """
    shells_dir = Path(shells_dir)
    if types:
        type_dirs = [shells_dir / t for t in types]
    else:
        type_dirs = [d for d in sorted(shells_dir.iterdir()) if d.is_dir()]

    converted: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []

    for d in type_dirs:
        if not d.is_dir():
            errors.append(f"{d.name}: shells 子目錄不存在")
            continue
        for variant, (stl_name, glb_name) in _VARIANT_STL_GLB.items():
            stl = d / stl_name
            glb = d / glb_name
            if not stl.exists():
                continue  # 此 type 無此 variant — 正常 N/A
            # pcb_body.glb 多色版為權威（export_all_pcb 產生），絕不覆蓋；
            # 僅在缺檔時由 STL 補單色 fallback。其餘 variant 受 overwrite 控制。
            protect = (variant == "pcb_body")
            if glb.exists() and (protect or not overwrite):
                skipped.append(f"{d.name}/{glb_name}")
                continue
            try:
                stl_to_glb(stl, glb)
                converted.append(f"{d.name}/{glb_name}")
            except Exception as e:  # noqa: BLE001 — 收集後統一 raise
                errors.append(f"{d.name}/{glb_name}: {e}")

    if errors:
        raise RuntimeError(
            "ensure_shell_glbs 轉換失敗（禁容錯）:\n  - " + "\n  - ".join(errors))
    return {"converted": converted, "skipped": skipped}
