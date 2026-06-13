"""lib/verification/l1_geometry.py — L1 幾何/裝配正確性驗證。

目前涵蓋：assembly placement 殘留碰撞（AABB 重疊）= VS-3D-Z。
未來：mesh watertight/manifold、spec conformance（bbox/孔位/體積）、
panel↔internal 真 3D（z 分層）碰撞。

驗證層原則：只判定、不修復（修復屬生成階段 assembly_solver 的職責）。
"""
from __future__ import annotations

from .report import CheckResult, VerificationReport, Verdict

_INTERNAL_RELATIONS = ("internal", "breadboard")


def check_placement_collisions(placements: list, *, name: str | None = None,
                               clearance: float = 0.0) -> VerificationReport:
    """驗證 internal placements 在 x/y 平面無殘留 AABB 重疊。

    注意：placement 目前無 z 欄位（internal 元件貼底 z=0、同平面），
    故以 x/y AABB 判定即等價 3D；z 分層（panel/embedded 貼殼面）
    待 placement 帶 z 後再擴充真 3D 判定。

    clearance: 容許的最小間距，重疊量需 > clearance 才算碰撞（預設 0=嚴格）。
    """
    label = name or "<placements>"
    rpt = VerificationReport(artifact=label, artifact_type="placements")

    pl = [p for p in (placements or []) if isinstance(p, dict)]
    internal = [p for p in pl
                if p.get("enclosure_relation", "internal") in _INTERNAL_RELATIONS]

    if not internal:
        rpt.add(CheckResult("L1", "placements_present", Verdict.PASS,
                            message="無 internal placement 需驗", metric={"n": 0}))
        return rpt
    rpt.add(CheckResult("L1", "placements_present", Verdict.PASS,
                        metric={"n": len(internal)}))

    overlaps = []
    for i in range(len(internal)):
        for j in range(i + 1, len(internal)):
            a, b = internal[i], internal[j]
            try:
                ox = min(a["x"] + a["L"], b["x"] + b["L"]) - max(a["x"], b["x"])
                oy = min(a["y"] + a["W"], b["y"] + b["W"]) - max(a["y"], b["y"])
            except (KeyError, TypeError):
                continue  # 欄位不全交由 contract 契約檢查負責
            if ox > clearance and oy > clearance:
                overlaps.append((a.get("type", "?"), b.get("type", "?"),
                                 round(ox, 2), round(oy, 2)))

    n_pairs = len(internal) * (len(internal) - 1) // 2
    if overlaps:
        names = [f"{t1.replace('-class','')}↔{t2.replace('-class','')}"
                 for t1, t2, _, _ in overlaps]
        rpt.add(CheckResult("L1", "no_overlap", Verdict.FAIL,
                            message="元件 AABB 重疊（assembly 物件穿模）",
                            metric={"n_overlap": len(overlaps), "pairs": names[:8]}))
    else:
        rpt.add(CheckResult("L1", "no_overlap", Verdict.PASS,
                            metric={"n_pairs_checked": n_pairs}))
    return rpt


def placements_from_scene_graph(scene_graph: dict) -> list:
    """Adapt scene_graph_v3 modules → top-down placement dicts for
    check_placement_collisions.

    scene_graph_v3 is y-up 3D: ``position=[x, y, z]`` is the module CENTER and
    ``dimensions=[L, W, H]`` are sizes along scene x / z / y respectively (y = up).
    The footprint plane is therefore x–z, mapped to the checker's x / y axes with
    corner (not centre) origin. ``component_placements`` (old corner-based x/y/L/W
    schema) is deprecated; the pipeline now emits scene_graph_v3 only.
    """
    out = []
    for m in scene_graph.get("modules", []):
        pos = m.get("position") or []
        dim = m.get("dimensions") or []
        if len(pos) < 3 or len(dim) < 2:
            continue
        L, W = dim[0], dim[1]
        out.append({
            "type": m.get("comp_type", "?"),
            "role": m.get("role", "?"),
            "x": pos[0] - L / 2.0,
            "y": pos[2] - W / 2.0,
            "L": L, "W": W,
            "enclosure_relation": m.get("enclosure_relation", "internal"),
        })
    return out
