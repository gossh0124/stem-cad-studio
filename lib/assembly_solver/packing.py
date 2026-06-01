"""Steps 1-5: Weight sort, thermal classify, zone assign, shelf packing,
collision detection, CoG check, panel layout, port orientation, overflow escalation.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from ._types import _Comp, _Decision, _THERMAL_HOT_MW, _CLEARANCE_MM

_ZONE_RULES = {
    "Brain": "center",
    "Power": "bottom-edge",
    "Sensor": "face-edge",
    "Output": "bottom-center",
    "Actuator": "bottom-center",
    "Display": "top-face",
    "Sound": "top-face",
    "Lighting": "top-face",
    "Motor": "bottom-center",
}

_PANEL_PORT_FACE_MAP = {
    "top":    "top",
    "face":   "top",
    "bottom": "side-front",
    "left":   "side-left",
    "right":  "side-right",
}

_UTIL_TARGET = 95.0


def _sort_by_weight(comps: List[_Comp], decisions: List[_Decision]) -> None:
    comps.sort(key=lambda c: c.weight_g, reverse=True)
    heaviest = comps[0] if comps else None
    total_g = sum(c.weight_g for c in comps)
    decisions.append(_Decision(
        step="gravity_sort",
        principle="重心穩定",
        description=(
            f"依重量排序 {len(comps)} 個元件（總重 {total_g:.0f}g）。"
            f"最重：{heaviest.type.replace('-class', '')} ({heaviest.weight_g:.0f}g)，優先放置於底部。"
        ) if heaviest else "無元件可排序。",
        formula="placement_priority = sorted(components, key=weight_g, desc)",
    ))


def _classify_thermal(comps: List[_Comp], decisions: List[_Decision]) -> set:
    hot = {c.type for c in comps if c.thermal_mw is not None and c.thermal_mw > _THERMAL_HOT_MW}
    cold_sensors = [c for c in comps if c.role == "Sensor" and c.type not in hot]
    hot_list = [c for c in comps if c.type in hot]
    hot_names = ", ".join(f"{c.type.replace('-class', '')}({c.thermal_mw:.0f}mW)" for c in hot_list if c.thermal_mw is not None)
    decisions.append(_Decision(
        step="thermal_classify",
        principle="熱源隔離",
        description=(
            f"功耗 > {_THERMAL_HOT_MW}mW 的熱源：{hot_names or '無'}。"
            f"需與 {len(cold_sensors)} 個感測器保持距離，避免溫度影響量測精度。"
        ),
        formula=f"hot_threshold = {_THERMAL_HOT_MW} mW",
    ))
    return hot


def _assign_zones(comps: List[_Comp], hot_set: set, decisions: List[_Decision]):
    assignments = []
    for c in comps:
        if c.type in hot_set and c.role != "Brain":
            c.zone = "bottom-edge"
        else:
            c.zone = _ZONE_RULES.get(c.role, "center")
        assignments.append(f"{c.type.replace('-class', '')}→{c.zone}")
    decisions.append(_Decision(
        step="zone_assign",
        principle="功能分區",
        description=(
            f"依角色分區：{'; '.join(assignments[:5])}"
            f"{'…' if len(assignments) > 5 else ''}。"
            "Brain 居中便於走線輻射，感測器靠外壁便於開窗，"
            "熱源置底利用自然對流散熱。"
        ),
        formula="zone = f(role, is_hot)",
    ))


def _escalate_overflow(
    pack_comps: List[_Comp],
    panel_comps: List[_Comp],
    inner_l: float, inner_w: float, inner_h: float,
    util: float,
    decisions: List[_Decision],
) -> Tuple[List[_Comp], List[_Comp], dict]:
    """Escalate overflowing internal comps: panel -> external -> shell resize."""
    escalations: List[str] = []
    target_area = inner_l * inner_w * (_UTIL_TARGET / 100.0)
    remaining = sorted(pack_comps, key=lambda c: c.L * c.W, reverse=True)

    def _drain(bucket_rel: str) -> List[_Comp]:
        moved: List[_Comp] = []
        while remaining and sum(c.L * c.W for c in remaining) > target_area:
            v = remaining.pop(0)
            v.enclosure_relation = bucket_rel
            moved.append(v)
            escalations.append(f"{v.type.replace('-class','')}→{bucket_rel}")
        return moved

    moved_to_panel = _drain("panel")
    moved_to_external = _drain("external")
    new_panel = panel_comps + moved_to_panel

    new_enc = {"inner_length": inner_l, "inner_width": inner_w, "inner_height": inner_h}
    if remaining and sum(c.L * c.W for c in remaining) > target_area:
        new_l = round(max(inner_l, max(c.L for c in remaining) + _CLEARANCE_MM * 2) * 1.2, 1)
        new_w = round((sum(c.W for c in remaining) + _CLEARANCE_MM * (len(remaining) + 1)) * 1.2, 1)
        new_h = round(max(inner_h, max(c.H for c in remaining) * 1.2), 1)
        new_enc = {"inner_length": new_l, "inner_width": new_w, "inner_height": new_h}
        escalations.append(f"shell_resize:{inner_l:.0f}x{inner_w:.0f}→{new_l:.0f}x{new_w:.0f}mm")

    if escalations:
        decisions.append(_Decision(
            step="overflow_escalate", principle="溢出升級鏈",
            description=(
                f"利用率 {util:.0f}% 超出殼體，執行升級鏈：{'; '.join(escalations)}。"
                f"升級後 internal={len(remaining)}，panel+={len(moved_to_panel)}，"
                f"external+={len(moved_to_external)}。"
            ),
            formula=f"target_util={_UTIL_TARGET}%; escalate largest comps first",
        ))
    return remaining, new_panel, new_enc


def _pack_shelf_ffd(
    comps: List[_Comp],
    inner_l: float, inner_w: float,
    decisions: List[_Decision],
) -> Tuple[float, float]:
    comps = list(comps)
    _PRIORITY_ROLES = {"Display", "Lighting", "Sound"}
    brain = [c for c in comps if c.role == "Brain"]
    priority = [c for c in comps if c.role in _PRIORITY_ROLES]
    others = [c for c in comps if c.role != "Brain" and c.role not in _PRIORITY_ROLES]
    comps[:] = brain + priority + others

    pad = _CLEARANCE_MM
    rotated_count = 0

    def _try_pack(comp_list, cl_pad):
        nonlocal rotated_count
        cx = cl_pad
        cy = cl_pad
        row_h = 0.0
        for c in comp_list:
            best_l, best_w = c.L, c.W
            if cx + best_l + cl_pad > inner_l - cl_pad:
                if cx + best_w + cl_pad <= inner_l - cl_pad and best_w != best_l:
                    best_l, best_w = c.W, c.L
                    rotated_count += 1
            cl = best_l + cl_pad
            cw = best_w + cl_pad
            if cx + cl > inner_l - cl_pad:
                cx = cl_pad
                cy += row_h + cl_pad
                row_h = 0.0
            c.x = cx
            c.y = cy
            c.L = best_l
            c.W = best_w
            cx += cl
            if cw > row_h:
                row_h = cw
        max_y = max((c.y + c.W for c in comp_list), default=0)
        return max_y

    max_y = _try_pack(comps, pad)
    if max_y > inner_w - pad:
        rotated_count = 0
        max_y = _try_pack(comps, max(1.0, pad - 1))

    used_area = sum(c.L * c.W for c in comps)
    total_area = inner_l * inner_w
    util = (used_area / total_area * 100) if total_area > 0 else 0
    overflow = max_y > inner_w
    decisions.append(_Decision(
        step="shelf_pack",
        principle="空間最佳化",
        description=(
            f"First-Fit Decreasing shelf packing：{len(comps)} 元件排入 "
            f"{inner_l:.0f}x{inner_w:.0f}mm 空間，面積利用率 {util:.0f}%。"
            + (f"旋轉 {rotated_count} 個元件以適配。" if rotated_count else "")
            + (f" 注意：元件溢出殼體，建議加大外殼。" if overflow else "")
            + f"元件間距 {pad:.0f}mm 確保組裝空間與走線通道。"
        ),
        formula=f"utilization = {used_area:.0f} / {total_area:.0f} = {util:.0f}%",
    ))
    return max_y, util


def _check_collisions(comps: List[_Comp], decisions: List[_Decision],
                      inner_l: float | None = None, inner_w: float | None = None,
                      inner_h: float | None = None,
                      max_iter: int = 30) -> None:
    """收斂式 3D AABB 碰撞修復。

    舊版單次 pass 推移不收斂（推 j 可能撞到 k）、且不限制邊界（可能推出殼外）。
    新版：迭代偵測→沿較小重疊軸推移→clamp 在 inner 邊界，重複到無重疊或達上限；
    殘留碰撞（空間不足）誠實回報，不再假裝修好。z 軸往上推（元件坐落在 z=0 底板）。
    """
    pad = _CLEARANCE_MM

    def _detect() -> list:
        cols = []
        for i in range(len(comps)):
            for j in range(i + 1, len(comps)):
                a, b = comps[i], comps[j]
                ox = min(a.x + a.L, b.x + b.L) - max(a.x, b.x)
                oy = min(a.y + a.W, b.y + b.W) - max(a.y, b.y)
                oz = min(a.z + a.H, b.z + b.H) - max(a.z, b.z)
                if ox > 0 and oy > 0 and oz > 0:
                    cols.append((i, j, ox, oy, oz))
        return cols

    initial = _detect()
    n_initial = len(initial)
    n_iter = 0
    cols = initial
    while cols and n_iter < max_iter:
        for i, j, ox, oy, oz in cols:
            b = comps[j]
            min_ov = min(ox, oy, oz)
            shift = min_ov + pad
            if min_ov == oz:
                b.z += shift
                if inner_h is not None:
                    b.z = max(0.0, min(b.z, inner_h - b.H))
            elif ox <= oy:
                b.x += shift
                if inner_l is not None:
                    b.x = max(pad, min(b.x, inner_l - pad - b.L))
            else:
                b.y += shift
                if inner_w is not None:
                    b.y = max(pad, min(b.y, inner_w - pad - b.W))
        n_iter += 1
        cols = _detect()
    residual = cols

    if n_initial == 0:
        decisions.append(_Decision(
            step="collision_check",
            principle="干涉防護（PV2）",
            description=f"無碰撞：{len(comps)} 個元件 3D AABB 無重疊 ✓",
        ))
    elif not residual:
        decisions.append(_Decision(
            step="collision_check",
            principle="干涉防護（PV2）",
            description=(
                f"偵測 {n_initial} 組 3D AABB 碰撞，收斂式推移 {n_iter} 輪後全部消除 ✓"
            ),
            formula="iterate: shift = min(ox,oy,oz)+clearance along min axis, clamp to inner bounds",
        ))
    else:
        rnames = [f"{comps[i].type.replace('-class','')}"
                  f"↔{comps[j].type.replace('-class','')}"
                  f"(ox={ox:.1f},oy={oy:.1f},oz={oz:.1f})"
                  for i, j, ox, oy, oz in residual]
        decisions.append(_Decision(
            step="collision_check",
            principle="干涉防護（PV2）",
            description=(
                f"偵測 {n_initial} 組碰撞，迭代 {n_iter} 輪後仍殘留 {len(residual)} 組"
                f"（{'; '.join(rnames[:3])}{'…' if len(rnames) > 3 else ''}）"
                f"——空間不足，建議加大殼體或外移元件。"
            ),
            formula="residual collision after clamp ⇒ enclosure too small",
        ))


def _check_cog(
    comps: List[_Comp],
    inner_l: float, inner_w: float,
    decisions: List[_Decision],
) -> None:
    total_w = sum(c.weight_g for c in comps)
    if total_w < 0.1:
        decisions.append(_Decision(
            step="cog_check",
            principle="重心穩定（PV4）",
            description="元件總重量接近 0g，跳過重心驗證。",
        ))
        return

    cog_x = sum((c.x + c.L / 2) * c.weight_g for c in comps) / total_w
    cog_y = sum((c.y + c.W / 2) * c.weight_g for c in comps) / total_w

    center_x = inner_l / 2
    center_y = inner_w / 2
    margin_x = inner_l / 3
    margin_y = inner_w / 3

    ok = (abs(cog_x - center_x) <= margin_x and
          abs(cog_y - center_y) <= margin_y)

    if ok:
        decisions.append(_Decision(
            step="cog_check",
            principle="重心穩定（PV4）",
            description=(
                f"重心 ({cog_x:.1f}, {cog_y:.1f}) 位於底座中央 2/3 區域內 "
                f"（中心 {center_x:.1f}, {center_y:.1f}）✓"
            ),
            formula="CoG ∈ [L/6, 5L/6] × [W/6, 5W/6]",
        ))
    else:
        heaviest = max(comps, key=lambda c: c.weight_g)
        heaviest.x = center_x - heaviest.L / 2
        heaviest.y = center_y - heaviest.W / 2

        cog_x2 = sum((c.x + c.L / 2) * c.weight_g for c in comps) / total_w
        cog_y2 = sum((c.y + c.W / 2) * c.weight_g for c in comps) / total_w
        decisions.append(_Decision(
            step="cog_check",
            principle="重心穩定（PV4）",
            description=(
                f"重心 ({cog_x:.1f}, {cog_y:.1f}) 偏離中央 2/3 區域，"
                f"已將最重元件 {heaviest.type.replace('-class', '')} "
                f"({heaviest.weight_g:.0f}g) 移至中心，"
                f"修正後重心 ({cog_x2:.1f}, {cog_y2:.1f})。"
            ),
            formula="CoG ∈ [L/6, 5L/6] × [W/6, 5W/6]",
        ))


def _layout_panel(
    panel_comps: List[_Comp],
    inner_l: float, inner_w: float, inner_h: float,
    decisions: List[_Decision],
):
    for c in panel_comps:
        side_votes: Dict[str, int] = {}
        for p in c.ports:
            face = _PANEL_PORT_FACE_MAP.get(p.get("side", "face"), "top")
            side_votes[face] = side_votes.get(face, 0) + 1
        c.face_out = max(side_votes, key=side_votes.get) if side_votes else "top"

    face_extent = {
        "top": inner_l, "bottom": inner_l,
        "side-left": inner_w, "side-right": inner_w,
        "side-front": inner_l, "side-back": inner_l,
    }
    face_cursor: Dict[str, float] = {}
    overflow_faces = set()
    for c in panel_comps:
        face = c.face_out
        u = face_cursor.get(face, _CLEARANCE_MM)
        c.x = u
        c.y = _CLEARANCE_MM
        c.zone = f"panel-{face}"
        next_u = u + c.L + _CLEARANCE_MM
        if next_u > face_extent.get(face, inner_l):
            overflow_faces.add(face)
        face_cursor[face] = next_u

    face_summary = "; ".join(
        f"{c.type.replace('-class', '')}→{c.face_out}@u={c.x:.0f}"
        for c in panel_comps[:5]
    )
    decisions.append(_Decision(
        step="panel_layout",
        principle="面板元件分配",
        description=(
            f"{len(panel_comps)} 個 panel 元件分配至殼面：{face_summary}"
            f"{'…' if len(panel_comps) > 5 else ''}。"
            + (f" 注意：{sorted(overflow_faces)} 面元件溢出，建議擴大殼面或拆移至其他面。"
               if overflow_faces else " 各面有效寬度足夠容納。")
        ),
        formula="face = majority_vote(port.side); u = sum(L+clearance) per face",
    ))


def _orient_ports(
    comps: List[_Comp],
    inner_l: float, inner_w: float,
    decisions: List[_Decision],
):
    _TOP_FACING_ROLES = {"Display", "Lighting", "Sound"}
    oriented = []
    for c in comps:
        usb_ports = [p for p in c.ports if p.get("port_type") in ("USB", "PWR")]
        cx = c.x + c.L / 2
        cy = c.y + c.W / 2
        distances = {
            "side-left": cx,
            "side-right": inner_l - cx,
            "side-front": cy,
            "side-back": inner_w - cy,
        }
        nearest = min(distances, key=distances.get)
        if c.role in _TOP_FACING_ROLES:
            c.face_out = "top"
            oriented.append(f"{c.type.replace('-class', '')}→top(使用者面)")
        elif c.role == "Sensor":
            c.face_out = "top"
            oriented.append(f"{c.type.replace('-class', '')}→top")
        elif usb_ports:
            c.face_out = nearest
            oriented.append(f"{c.type.replace('-class', '')} USB→{nearest}")
        else:
            c.face_out = nearest

    decisions.append(_Decision(
        step="port_orient",
        principle="介面可達性",
        description=(
            f"Port 朝向最近外壁：{'; '.join(oriented[:4])}"
            f"{'…' if len(oriented) > 4 else ''}。"
            "USB/電源口朝外便於插拔，感測器朝上或朝外便於偵測。"
        ),
        formula="face_out = argmin(distance_to_wall)",
    ))
