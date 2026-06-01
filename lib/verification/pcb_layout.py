"""lib/verification/pcb_layout.py — VS-PCB 前端 PCB 佈局對照後端權威 SSOT。

前端 v6/data/component-dimensions.js 是手工硬編碼的 PCB 元件佈局；
後端 lib/pcb/*.py 是三來源交叉驗證（EAGLE + KiCad + PDF，誤差 0.000mm）的
權威 SSOT。本層量化兩者偏差，把「PCB 內容位置/尺寸錯」變成可計算清單：

  no_missing_components  後端有但前端未繪（漏畫）→ L1 FAIL
  position_within_tol    對應元件位置偏差 > 容差 → L1 FAIL
  no_extra_components    前端有但後端無（疑似虛構/未驗證）→ L2 WARN
  footprint_within_tol   平面尺寸偏差 > 容差 → L2 WARN

純判定。座標 dump / footprint 估算 / 名稱映射由 scripts/audit_pcb_layout.py
負責，本模組只吃已配對的資料，確保對照邏輯可單測。
"""
from __future__ import annotations

from .report import CheckResult, VerificationReport, Verdict


def audit_pcb_layout(matched: list, frontend_only: list, ssot_only: list, *,
                     name: str | None = None,
                     pos_tol_mm: float = 3.0,
                     size_tol_mm: float = 2.0) -> VerificationReport:
    """對照已配對的前端 / 後端 PCB 元件。

    matched: [{label, fx, fy, sx, sy, fw?, fh?, sw?, sh?}]
             f* = 前端值, s* = 後端 SSOT 值（同座標系，mm）。
    frontend_only: 前端有、後端 SSOT 無的 label 清單。
    ssot_only:     後端 SSOT 有、前端無的 name 清單。
    """
    rpt = VerificationReport(artifact=name or "<pcb>", artifact_type="pcb_layout")

    # ── 漏畫（後端有前端無）→ L1 FAIL ──
    if ssot_only:
        rpt.add(CheckResult("L1", "no_missing_components", Verdict.FAIL,
                            message="後端 SSOT 有但前端未繪（漏畫元件）",
                            metric={"n_missing": len(ssot_only), "missing": ssot_only[:12]}))
    else:
        rpt.add(CheckResult("L1", "no_missing_components", Verdict.PASS))

    # ── 位置偏差 → L1 FAIL ──
    pos_off = []
    for m in matched:
        dx = abs(m["fx"] - m["sx"])
        dy = abs(m["fy"] - m["sy"])
        if dx > pos_tol_mm or dy > pos_tol_mm:
            pos_off.append({"label": m["label"], "dx": round(dx, 1), "dy": round(dy, 1)})
    if pos_off:
        rpt.add(CheckResult("L1", "position_within_tol", Verdict.FAIL,
                            message=f"位置偏差 > {pos_tol_mm}mm（vs 後端 SSOT）",
                            metric={"tol_mm": pos_tol_mm, "n_off": len(pos_off),
                                    "off": pos_off[:12]}))
    else:
        rpt.add(CheckResult("L1", "position_within_tol", Verdict.PASS,
                            metric={"n_matched": len(matched)}))

    # ── 前端多出（後端無）→ L2 WARN ──
    if frontend_only:
        rpt.add(CheckResult("L2", "no_extra_components", Verdict.WARN,
                            message="前端有但後端 SSOT 無（疑似虛構/未驗證）",
                            metric={"n_extra": len(frontend_only), "extra": frontend_only[:12]}))
    else:
        rpt.add(CheckResult("L2", "no_extra_components", Verdict.PASS))

    # ── 平面尺寸偏差 → L2 WARN ──
    size_off = []
    for m in matched:
        if m.get("fw") is None or m.get("sw") is None:
            continue
        f = sorted([m["fw"], m["fh"]])
        s = sorted([m["sw"], m["sh"]])
        if abs(f[0] - s[0]) > size_tol_mm or abs(f[1] - s[1]) > size_tol_mm:
            size_off.append({"label": m["label"],
                             "frontend": [round(m["fw"], 1), round(m["fh"], 1)],
                             "ssot": [round(m["sw"], 1), round(m["sh"], 1)]})
    if size_off:
        rpt.add(CheckResult("L2", "footprint_within_tol", Verdict.WARN,
                            message=f"平面尺寸偏差 > {size_tol_mm}mm",
                            metric={"tol_mm": size_tol_mm, "n_off": len(size_off),
                                    "off": size_off[:12]}))
    else:
        rpt.add(CheckResult("L2", "footprint_within_tol", Verdict.PASS))

    return rpt
