"""lib/verification/l0_integrity.py — L0 產出完整性檢查。

L0 回答最基本的問題：「東西真的生出來了嗎？還是空的/壞的/沒呈現？」
這一層專門堵「畫面沒出來卻回報成功」的洞。

不負責正確性（那是 L1），只負責：
  - 檔案能否解析/載入
  - 內容是否非空（SVG 有節點 / PNG 非空白 / mesh 有面）
  - 數值是否健全（bounds 非退化、無 NaN）

每個 check_* 回傳一份 VerificationReport（單一產出物）。
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from .report import CheckResult, VerificationReport, Verdict

# ── 閾值 ────────────────────────────────────────────────────
_BLANK_STD = 2.0        # 灰階標準差低於此 → 視為空白圖（全白/全黑/單色）
_BBOX_EPS = 1e-6        # 任一維 extent 小於此 → 退化幾何
_MIN_SVG_NODES = 2      # <svg> 本身算 1，至少要有 1 個子節點


def _ok(layer, name, msg="", **metric):
    return CheckResult(layer=layer, name=name, verdict=Verdict.PASS,
                       message=msg, metric=metric)


def _fail(layer, name, msg, **metric):
    return CheckResult(layer=layer, name=name, verdict=Verdict.FAIL,
                       message=msg, metric=metric)


# ── SVG ─────────────────────────────────────────────────────
def check_svg(source: str, *, name: str | None = None) -> VerificationReport:
    """source 可為 SVG 檔路徑或 SVG 字串。"""
    is_path = len(source) < 1024 and os.path.exists(source)
    label = name or (source if is_path else "<svg-string>")
    rpt = VerificationReport(artifact=label, artifact_type="svg")

    raw = None
    if is_path:
        try:
            raw = Path(source).read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            rpt.add(_fail("L0", "readable", f"無法讀取: {exc}"))
            return rpt
        if not raw.strip():
            rpt.add(_fail("L0", "non_empty", "檔案為空", bytes=0))
            return rpt
    else:
        raw = source

    rpt.add(_ok("L0", "non_empty", "", bytes=len(raw)))

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        rpt.add(_fail("L0", "parseable", f"SVG 解析失敗: {exc}"))
        return rpt
    rpt.add(_ok("L0", "parseable"))

    n_nodes = sum(1 for _ in root.iter())
    if n_nodes < _MIN_SVG_NODES:
        rpt.add(_fail("L0", "has_content", "SVG 無任何子節點（空圖）",
                      n_nodes=n_nodes))
    else:
        rpt.add(_ok("L0", "has_content", n_nodes=n_nodes))

    has_box = ("viewBox" in root.attrib
               or ("width" in root.attrib and "height" in root.attrib))
    if has_box:
        rpt.add(_ok("L0", "has_dimensions",
                    viewBox=root.attrib.get("viewBox"),
                    width=root.attrib.get("width")))
    else:
        rpt.add(_fail("L0", "has_dimensions", "缺 viewBox / width+height"))

    return rpt


# ── PNG ─────────────────────────────────────────────────────
def check_png(path: str, *, name: str | None = None,
              blank_std: float = _BLANK_STD) -> VerificationReport:
    """檢查點陣圖：可載入、尺寸>0、非空白。"""
    label = name or path
    rpt = VerificationReport(artifact=label, artifact_type="png")

    if not os.path.exists(path):
        rpt.add(_fail("L0", "exists", "檔案不存在"))
        return rpt
    size = os.path.getsize(path)
    if size == 0:
        rpt.add(_fail("L0", "non_empty", "檔案為 0 byte", bytes=0))
        return rpt
    rpt.add(_ok("L0", "non_empty", bytes=size))

    try:
        from PIL import Image
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        rpt.add(_fail("L0", "loadable", f"圖片載入失敗: {exc}"))
        return rpt

    w, h = img.size
    if w <= 0 or h <= 0:
        rpt.add(_fail("L0", "valid_size", "尺寸非法", width=w, height=h))
        return rpt
    rpt.add(_ok("L0", "loadable", width=w, height=h))

    arr = np.asarray(img.convert("L"), dtype=np.float64)
    std = float(arr.std())
    n_unique = int(np.unique(arr).size)
    if std < blank_std:
        rpt.add(_fail("L0", "non_blank",
                      "畫面疑似空白（像素變異過低）",
                      std=round(std, 3), unique_levels=n_unique))
    else:
        rpt.add(_ok("L0", "non_blank",
                    std=round(std, 3), unique_levels=n_unique))
    return rpt


# ── Mesh (STL / 3MF / STEP→mesh) ────────────────────────────
def check_mesh(path: str, *, name: str | None = None) -> VerificationReport:
    """檢查 3D mesh：可載入、有面、bounds 非退化、無 NaN。

    注意：watertight / manifold / 碰撞屬 L1（正確性），不在此處判定。
    """
    label = name or path
    rpt = VerificationReport(artifact=label, artifact_type="mesh")

    if not os.path.exists(path):
        rpt.add(_fail("L0", "exists", "檔案不存在"))
        return rpt
    if os.path.getsize(path) == 0:
        rpt.add(_fail("L0", "non_empty", "檔案為 0 byte", bytes=0))
        return rpt

    try:
        import trimesh
        mesh = trimesh.load(path, force="mesh")
    except Exception as exc:  # noqa: BLE001
        rpt.add(_fail("L0", "loadable", f"mesh 載入失敗: {exc}"))
        return rpt

    n_faces = int(getattr(mesh, "faces", np.empty((0,))).shape[0])
    n_verts = int(getattr(mesh, "vertices", np.empty((0,))).shape[0])
    if n_faces == 0 or n_verts == 0:
        rpt.add(_fail("L0", "has_geometry", "mesh 無面或無頂點",
                      n_faces=n_faces, n_vertices=n_verts))
        return rpt
    rpt.add(_ok("L0", "loadable", n_faces=n_faces, n_vertices=n_verts))

    verts = np.asarray(mesh.vertices, dtype=np.float64)
    if not np.isfinite(verts).all():
        rpt.add(_fail("L0", "finite_coords", "頂點含 NaN / Inf",
                      n_nonfinite=int((~np.isfinite(verts)).sum())))
        return rpt
    rpt.add(_ok("L0", "finite_coords"))

    extents = np.asarray(mesh.extents, dtype=np.float64)
    degenerate = [i for i, e in enumerate(extents) if e < _BBOX_EPS]
    if degenerate:
        rpt.add(_fail("L0", "non_degenerate_bbox",
                      f"bounding box 在軸 {degenerate} 退化（厚度≈0）",
                      extents=[round(float(e), 4) for e in extents]))
    else:
        rpt.add(_ok("L0", "non_degenerate_bbox",
                    extents=[round(float(e), 4) for e in extents]))
    return rpt
