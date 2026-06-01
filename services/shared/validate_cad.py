"""services/shared/validate_cad.py — CAD output 五項自動驗證（CH2 Invalid Rate 指標）。

來源：docs/224_CAD_HLLM_Generating_Execut.pdf（ACML 2025）
目的：建立 phase4 輸出的可量化品質指標，供 17 template regression 對比。

五項檢查：
  1. exists      — base_stl / lid_stl 檔案存在且 size > 0
  2. parseable   — trimesh 載入無例外、faces > 0
  3. watertight  — mesh.is_watertight 為 True
  4. bbox_ok     — outer_l / outer_w / (base_h+lid_h) 全 ≤ BBOX_LIMIT_MM
  5. snap_fit_ok — spec.wall ≥ MIN_WALL_MM 且 0.1 ≤ spec.tol ≤ 0.5

Invalid = 任一項 fail。Invalid Rate = (NG 範本數) / 總範本數。
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from lib.config import CAD_VALIDATION

BBOX_LIMIT_MM = CAD_VALIDATION["BBOX_LIMIT_MM"]
MIN_WALL_MM   = CAD_VALIDATION["MIN_WALL_MM"]


def _resolve_stl_path(raw: Optional[str], project_root: Path) -> Optional[Path]:
    """cad_output 內 STL 可能是：
       a) URL 形式 '/canned/<id>/...stl' → 對應 v6/canned/<id>/...stl
       b) 絕對 Windows 路徑 → 直接用
       c) None / 空字串 → None
    """
    if not raw:
        return None
    if raw.startswith("/canned/"):
        return project_root / "v6" / raw.lstrip("/")
    p = Path(raw)
    return p if p.is_absolute() else project_root / p


def _check_exists(path: Optional[Path]) -> Tuple[bool, str]:
    if path is None:
        return False, "stl path missing"
    if not path.exists():
        return False, f"file not found: {path.name}"
    if path.stat().st_size == 0:
        return False, f"empty file: {path.name}"
    return True, ""


def _check_parseable(path: Path) -> Tuple[bool, str, Any]:
    if path.stat().st_size > 50 * 1024 * 1024:  # 50MB
        return False, f"STL file exceeds 50MB size limit: {path.name}", None
    try:
        import trimesh
        mesh = trimesh.load(str(path), force="mesh")
        if mesh is None or not hasattr(mesh, "faces") or len(mesh.faces) == 0:
            return False, f"no faces: {path.name}", None
        return True, "", mesh
    except Exception as exc:
        return False, f"trimesh load failed {path.name}: {exc}", None


def _check_watertight(mesh: Any, name: str) -> Tuple[bool, str]:
    try:
        if not mesh.is_watertight:
            return False, f"not watertight: {name}"
        return True, ""
    except Exception as exc:
        return False, f"watertight check failed {name}: {exc}"


def _check_bbox(spec: Dict[str, Any]) -> Tuple[bool, str]:
    outer_l = float(spec.get("outer_l", 0))
    outer_w = float(spec.get("outer_w", 0))
    base_h  = float(spec.get("base_h", 0))
    lid_h   = float(spec.get("lid_h", 0))
    total_h = base_h + lid_h
    over: List[str] = []
    if outer_l > BBOX_LIMIT_MM:
        over.append(f"L={outer_l:.1f}")
    if outer_w > BBOX_LIMIT_MM:
        over.append(f"W={outer_w:.1f}")
    if total_h > BBOX_LIMIT_MM:
        over.append(f"H={total_h:.1f}")
    if over:
        return False, f"bbox > {BBOX_LIMIT_MM}: {','.join(over)}"
    return True, ""


def _check_snap_fit(spec: Dict[str, Any]) -> Tuple[bool, str]:
    wall = float(spec.get("wall", 0))
    tol  = float(spec.get("tol", 0))
    bad: List[str] = []
    if wall < MIN_WALL_MM:
        bad.append(f"wall={wall:.2f}<{MIN_WALL_MM}")
    if not (0.1 <= tol <= 0.5):
        bad.append(f"tol={tol:.2f} not in [0.1,0.5]")
    if bad:
        return False, ",".join(bad)
    return True, ""


def validate_cad_output(
    cad_output: Optional[Dict[str, Any]],
    *,
    project_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """五項驗證 CAD output。

    Args:
        cad_output: bridge["cad_output"]，可能為 None / 缺欄位
        project_root: 專案根目錄；用於 URL 路徑解析（default = StemAiAgentV2/）

    Returns:
        {
          "checks":       {exists, parseable, watertight, bbox_ok, snap_fit_ok}: bool,
          "invalid":      bool,        # 任一項 fail
          "fail_reasons": [str, ...],  # 失敗理由
          "fail_count":   int,
        }
    """
    if project_root is None:
        project_root = Path(__file__).resolve().parents[2]

    checks = {
        "exists":      False,
        "parseable":   False,
        "watertight":  False,
        "bbox_ok":     False,
        "snap_fit_ok": False,
    }
    reasons: List[str] = []

    if not cad_output:
        return {
            "checks": checks,
            "invalid": True,
            "fail_reasons": ["cad_output missing"],
            "fail_count": 5,
        }

    bottom = _resolve_stl_path(cad_output.get("bottom_stl"), project_root)
    lid    = _resolve_stl_path(cad_output.get("lid_stl"), project_root)
    spec   = cad_output.get("spec") or {}

    # 1. exists（base + lid 都要在）
    ok_b, msg_b = _check_exists(bottom)
    ok_l, msg_l = _check_exists(lid)
    checks["exists"] = ok_b and ok_l
    if not ok_b:
        reasons.append(f"exists base: {msg_b}")
    if not ok_l:
        reasons.append(f"exists lid: {msg_l}")

    # 2. parseable + 3. watertight（需要前項通過）
    if checks["exists"]:
        ok_pb, msg_pb, mb = _check_parseable(bottom)
        ok_pl, msg_pl, ml = _check_parseable(lid)
        checks["parseable"] = ok_pb and ok_pl
        if not ok_pb:
            reasons.append(msg_pb)
        if not ok_pl:
            reasons.append(msg_pl)
        if checks["parseable"]:
            ok_wb, msg_wb = _check_watertight(mb, bottom.name)
            ok_wl, msg_wl = _check_watertight(ml, lid.name)
            checks["watertight"] = ok_wb and ok_wl
            if not ok_wb:
                reasons.append(msg_wb)
            if not ok_wl:
                reasons.append(msg_wl)

    # 4. bbox（不依賴 STL）
    ok_b, msg_b = _check_bbox(spec)
    checks["bbox_ok"] = ok_b
    if not ok_b:
        reasons.append(msg_b)

    # 5. snap-fit（不依賴 STL）
    ok_s, msg_s = _check_snap_fit(spec)
    checks["snap_fit_ok"] = ok_s
    if not ok_s:
        reasons.append(msg_s)

    fail_count = sum(1 for v in checks.values() if not v)
    return {
        "checks": checks,
        "invalid": fail_count > 0,
        "fail_reasons": reasons,
        "fail_count": fail_count,
    }


__all__ = ["validate_cad_output", "BBOX_LIMIT_MM", "MIN_WALL_MM"]
