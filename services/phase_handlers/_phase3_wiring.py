"""Phase III wiring generation and geometry/interference checks.

Extracted from phase3_handler.py — contains pin allocation, SVG schematic
generation, chamfer distance estimation, and 2D AABB interference detection.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional


# ── Helper ─────────────────────────────────────────────────────────

def _log(cb: Optional[Callable], msg: str) -> None:
    prefix = "[Phase III] "
    if cb:
        cb(prefix + msg)
    else:
        print(prefix + msg)


# ── Pin allocation + Wiring + Schematic SVG ────────────────────────

def generate_wiring(
    components: List[dict],
    brain_type: str,
    progress_cb: Optional[Callable] = None,
) -> Optional[dict]:
    """Call lib/wiring + lib/schematic to produce wiring data and SVG."""
    try:
        from lib.wiring import (
            to_json as wiring_to_json,
            PinAllocationError,
            normalize_brain,
            normalize_comp,
        )
        from lib.schematic import generate_svg
    except ImportError as e:
        _log(progress_cb, f"  ⚠️ wiring/schematic import 失敗：{e}")
        return None

    brain_key = normalize_brain(brain_type)

    outputs: List[str] = []
    sensors: List[str] = []
    power_key = "USB-5V"
    _OUTPUT_ROLES = {"Output", "Actuator", "Lighting", "Display", "Motor",
                     "Audio", "Control", "Sound", "Mist", "Chassis", "Enclosure"}
    _SENSOR_ROLES = {"Sensor", "Input"}
    for c in components:
        role = c.get("role", "")
        ctype = c.get("type", "")
        short = normalize_comp(ctype)
        if role in _OUTPUT_ROLES:
            outputs.append(short)
        elif role in _SENSOR_ROLES:
            sensors.append(short)
        elif role == "Power":
            power_key = short

    all_comps = outputs + sensors
    if not all_comps:
        _log(progress_cb, "  ⚠️ 無 Output/Sensor 元件，跳過接線生成")
        return None

    try:
        wiring_result = wiring_to_json(brain_key, all_comps, power=power_key)
    except PinAllocationError as e:
        _log(progress_cb, f"  ❌ Pin 分配失敗：{e}")
        raise ValueError(
            f"[Phase III] Pin 接線配置失敗 — {e}\n"
            f"檢查元件引腳需求是否超過 {brain_type} 可用 Pin 數量。"
        )

    n_alloc = len(wiring_result.get("allocation", {}))
    _log(progress_cb, f"  ✅ Pin 分配完成：{n_alloc} 個元件")

    try:
        svg = generate_svg(brain_key, power_key, outputs, sensors)
        _log(progress_cb, f"  ✅ Schematic SVG 生成完成（{len(svg)} bytes）")
        schematic_error = None
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        # 已知的 schematic 生成錯誤：記錄明確的 error marker,
        # 不要用空字串假裝成功(下游無法分辨「不需要 schematic」與「生成崩潰」)。
        # 非預期的例外仍會往上拋,不再被靜默吞掉。
        _log(progress_cb, f"  ⚠️ Schematic SVG 生成失敗：{e}")
        svg = ""
        schematic_error = str(e)

    return {
        "allocation": wiring_result.get("allocation", {}),
        "pin_labels": wiring_result.get("pin_labels", {}),
        "wiring": wiring_result.get("wiring", {}),
        "schematic_svg": svg,
        "schematic_error": schematic_error,
        # S-power-inject: SSOT-derived power injection fields (None if unavailable)
        "power_injection": wiring_result.get("power_injection"),
        "load_power_injection": wiring_result.get("load_power_injection"),
        # S-netlist: build_netlist 模型(供 runtime galvanic-isolation gate;原僅 to_json
        # 內部用於 schematic ELK 配色,未往外傳)。[] 表 build_netlist 失敗或無 net。
        "nets": wiring_result.get("nets", []),
    }


# ── Chamfer Distance geometry estimate ─────────────────────────────

def estimate_layout_chamfer(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
    padding_mm: float = 5.0,
) -> dict:
    """Estimate spatial layout compatibility using chamfer distance."""
    try:
        import numpy as np
    except ImportError:
        return {"status": "SKIP", "msg": "numpy 不可用", "spatial_ok": True}

    specs = [c.get("spec") or {} for c in components if c.get("spec")]
    if not specs:
        return {"status": "SKIP", "msg": "無規格資料", "spatial_ok": True}

    n = len(specs)
    n_cols = max(2, math.ceil(math.sqrt(n)))
    n_rows = math.ceil(n / n_cols)
    for _s in specs:
        for _k in ("length_mm", "width_mm", "height_mm"):
            if _k not in _s:
                raise ValueError(
                    f"[Phase III] estimate_layout_chamfer: spec 缺少 '{_k}' 幾何尺寸，"
                    f"無法估算空間佈局。請確認元件 spec 已含 length_mm/width_mm/height_mm。"
                )
    max_L = max(s["length_mm"] for s in specs)
    max_W = max(s["width_mm"]  for s in specs)
    max_H = max(s["height_mm"] for s in specs)
    cell_L = max_L + padding_mm
    cell_W = max_W + padding_mm
    inner_L = n_cols * cell_L + (n_cols + 1) * padding_mm
    inner_W = n_rows * cell_W + (n_rows + 1) * padding_mm
    min_required_mm = max(inner_L, inner_W, max_H)

    positions = []
    for i, spec in enumerate(specs):
        col, row = i % n_cols, i // n_cols
        cx = col * cell_L + padding_mm + spec["length_mm"] / 2
        cy = row * cell_W + padding_mm + spec["width_mm"]  / 2
        positions.append(np.array([cx, cy, 0.0]))

    min_gaps = []
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            min_gaps.append(float(np.linalg.norm(positions[i] - positions[j])))

    chamfer_est = min(min_gaps) if min_gaps else float("inf")
    spatial_ok  = chamfer_est > padding_mm * 0.5

    result = {
        "status": "OK" if spatial_ok else "WARN",
        "grid": f"{n_cols}×{n_rows}",
        "estimated_inner_L": round(inner_L, 1),
        "estimated_inner_W": round(inner_W, 1),
        "max_component_H": round(max_H, 1),
        "min_required_mm": round(min_required_mm, 1),
        "chamfer_distance_est": round(chamfer_est, 2),
        "spatial_ok": bool(spatial_ok),
    }
    status_icon = "✅" if spatial_ok else "⚠️"
    _log(progress_cb,
        f"  {status_icon} 幾何估算：{n_cols}×{n_rows} 格，"
        f"最小間距 {chamfer_est:.1f}mm，"
        f"估計內尺寸 {inner_L:.0f}×{inner_W:.0f} mm")
    return result


# ── 2D AABB Interference / Keep-out Zone detection ─────────────────

def check_interference(
    components: List[dict],
    progress_cb: Optional[Callable] = None,
    keepout_mm: float = 3.0,
) -> dict:
    """2D AABB interference detection with keep-out zones."""
    specs = []
    for i, c in enumerate(components):
        s = c.get("spec") or {}
        if not s:
            continue
        for _k in ("length_mm", "width_mm"):
            if _k not in s:
                raise ValueError(
                    f"[Phase III] check_interference: 元件 {c.get('type', '?')} 的 spec "
                    f"缺少 '{_k}' 幾何尺寸，無法進行干涉檢測。"
                )
        l = float(s["length_mm"])
        w = float(s["width_mm"])
        specs.append({"idx": i, "type": c.get("type", "?"), "l": l, "w": w})

    if len(specs) < 2:
        return {"ok": True, "msg": "元件不足 2 個，無需干涉檢測", "collisions": []}

    n = len(specs)
    n_cols = max(2, math.ceil(math.sqrt(n)))
    padding = 5.0

    max_l = max(s["l"] for s in specs)
    max_w = max(s["w"] for s in specs)
    cell_l = max_l + padding + 8.0
    cell_w = max_w + padding + 8.0

    boxes = []
    for slot, s in enumerate(specs):
        col, row = slot % n_cols, slot // n_cols
        cx = col * cell_l + padding + s["l"] / 2
        cy = row * cell_w + padding + s["w"] / 2
        half_l = s["l"] / 2 + keepout_mm
        half_w = s["w"] / 2 + keepout_mm
        boxes.append({
            "type": s["type"],
            "x_min": cx - half_l, "x_max": cx + half_l,
            "y_min": cy - half_w, "y_max": cy + half_w,
        })

    collisions = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a["x_max"], b["x_max"]) - max(a["x_min"], b["x_min"])
            oy = min(a["y_max"], b["y_max"]) - max(a["y_min"], b["y_min"])
            if ox > 0 and oy > 0:
                collisions.append({
                    "a": a["type"], "b": b["type"],
                    "overlap_mm": round(ox * oy, 1),
                })

    ok = len(collisions) == 0
    if ok:
        _log(progress_cb,
            f"  ✅ 干涉檢測通過（{len(boxes)} 元件，keep-out {keepout_mm}mm）")
    else:
        _log(progress_cb,
            f"  ⚠️ 發現 {len(collisions)} 組干涉")
    return {"ok": ok, "collisions": collisions, "keepout_mm": keepout_mm}
