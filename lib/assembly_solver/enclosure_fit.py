"""Enclosure auto-sizing + non-internal bucket placement for Assembly V3.

Split from assembly_solver_v3.py to keep that module under the 500-line budget.

The enclosure is an *independently generated* shell: internal modules are packed
on the floor, then the inner dimensions shrink-wrap to that footprint
(+clearance), floored by the caller's requested dims — every internal module
fits with no out-of-bounds by construction. Panel parts (buttons/LEDs/knobs) are
*face-mounted* on the lid with a cutout per their mounting method. External
devices sit outside the wall and their wires pass through reserved holes.
"""
from __future__ import annotations

import copy
import math
from typing import Callable, List, Tuple

from lib.config import ASSEMBLY_V3
from lib.module_builder import ComponentModule
from lib.registry import COMPONENT_REGISTRY

_CLEARANCE = ASSEMBLY_V3["CLEARANCE"]
_EXTERNAL_GAP = ASSEMBLY_V3.get("EXTERNAL_GAP", 8.0)  # wall-to-external-module gap (mm)
_MIN_INNER = 20.0  # mm floor — avoids degenerate enclosures when no internal mods
_PACK_EFFICIENCY = 0.65  # area utilisation for initial work-area estimate
_HOLE_DIAMETER = 6.0  # mm default cable-gland / wire pass-through

# Floor-packed inside the shell.
PACKED_RELATIONS = ("internal", "breadboard")
# Mounted on an enclosure face (lid) with a cutout, wired internally.
FACE_RELATIONS = ("panel",)
# Physically separate devices whose wires must pierce the wall through a hole.
WALL_CROSSING_RELATIONS = frozenset({"external", "embedded"})
# LED tags that mount through a round press-fit hole (single emitters, not strips).
_ROUND_LIGHT_TAGS = frozenset({"light:single", "light:rgb", "light:pwm"})

PackFn = Callable[[List[ComponentModule], float, float], List[Tuple[float, float, bool]]]


def autosize_enclosure(
    pack_mods: List[ComponentModule],
    pack_pos: List[Tuple[float, float]],
    min_l: float, min_w: float, min_h: float,
    panel_max_h: float = 0.0,
) -> Tuple[float, float, float]:
    """Shrink-wrap inner dims to the packed footprint (+clearance).

    Floored by the caller's requested dims so an explicitly larger box is
    honoured while the box always grows enough to fit every internal module.
    Height reserves a routing layer above the tallest internal AND clears the
    tallest face-mounted panel (which hangs down from the lid into the cavity).
    """
    if not pack_mods:
        return (round(max(min_l, _MIN_INNER), 1),
                round(max(min_w, _MIN_INNER), 1),
                round(max(min_h, _MIN_INNER), 1))
    max_x = max(pack_pos[i][0] + pack_mods[i].length for i in range(len(pack_mods)))
    max_y = max(pack_pos[i][1] + pack_mods[i].width for i in range(len(pack_mods)))
    max_h = max(m.height for m in pack_mods)
    il = max(min_l, max_x + _CLEARANCE)
    iw = max(min_w, max_y + _CLEARANCE)
    # Clearance budget for height:
    #   floor→module: 0 (modules sit on floor, no bottom gap)
    #   module_top→panel_bottom: _CLEARANCE (routing + collision gap)
    #   panel hangs from lid into the cavity; its height eats inner space
    ih = max(min_h, max_h + panel_max_h + _CLEARANCE)
    return round(il, 1), round(iw, 1), round(ih, 1)


_SIDE_ROT_CCW = {"left": "bottom", "bottom": "right",
                 "right": "top", "top": "left", "face": "face"}


def _rotate_module(m: ComponentModule) -> ComponentModule:
    """Return a 90 deg CCW-rotated copy: footprint L<->W, ports/pins transformed.

    Point map on footprint [0,L]x[0,W] -> [0,W]x[0,L]:  (x, y) -> (W - y, x).
    Keeps the packer's rotation consistent with rendered geometry and wire
    endpoints so a rotated module never reads back as overlapping.
    """
    r = copy.deepcopy(m)
    L, W = m.length, m.width
    r.length, r.width = W, L
    for p in r.pins:
        p.x, p.y = round(W - p.y, 2), round(p.x, 2)
    for sp in r.shell_ports:
        sp.x, sp.y = round(W - sp.y, 2), round(sp.x, 2)
        sp.width, sp.height = sp.height, sp.width
        sp.side = _SIDE_ROT_CCW.get(sp.side, sp.side)
    return r


def _packing_overlap(
    mods: List[ComponentModule], pos: List[Tuple[float, float]], tol: float = 0.1,
) -> bool:
    """True if any two placed module footprints overlap in the XY plane."""
    for i in range(len(mods)):
        xi, yi = pos[i]
        for j in range(i + 1, len(mods)):
            xj, yj = pos[j]
            ox = min(xi + mods[i].length, xj + mods[j].length) - max(xi, xj)
            oy = min(yi + mods[i].width, yj + mods[j].width) - max(yi, yj)
            if ox > tol and oy > tol:
                return True
    return False


def pack_compact(
    pack_mods: List[ComponentModule],
    pack_fn: PackFn,
    min_l: float, min_w: float, min_h: float,
    panel_max_h: float = 0.0,
) -> Tuple[List[ComponentModule], List[Tuple[float, float]], float, float, float]:
    """Pack internal modules into the most compact, overlap-free enclosure.

    MaxRects BSSF minimises per-placement short-side fit, not the overall
    bounding box, so a single fixed work area can sprawl or (on free-rect
    fragmentation) overflow into overlaps. We try several work widths, apply the
    packer's rotation to each module, and keep the smallest-area packing that is
    provably overlap-free. Returns the (possibly rotated) module copies aligned
    with their positions so all downstream geometry stays consistent.
    """
    if not pack_mods:
        return [], [], round(max(min_l, _MIN_INNER), 1), \
            round(max(min_w, _MIN_INNER), 1), \
            round(max(min_h, panel_max_h + _CLEARANCE, _MIN_INNER), 1)

    total = sum(m.length * m.width for m in pack_mods)
    base = math.sqrt(total / _PACK_EFFICIENCY) if total > 0 else _MIN_INNER
    floor_w = max(min(m.length, m.width) for m in pack_mods) + 3 * _CLEARANCE
    tall = sum(max(m.length, m.width) + _CLEARANCE for m in pack_mods) + 2 * _CLEARANCE

    widths = sorted({round(max(floor_w, base * r), 1)
                     for r in (0.6, 0.7, 0.8, 0.9, 1.0, 1.15, 1.3, 1.5, 2.0)})

    best = None       # smallest-area overlap-free candidate
    for width in widths:
        raw = pack_fn(pack_mods, width, tall)
        placed: List[ComponentModule] = []
        positions: List[Tuple[float, float]] = []
        for k, (x, y, rot) in enumerate(raw):
            placed.append(_rotate_module(pack_mods[k]) if rot else pack_mods[k])
            positions.append((x, y))
        il, iw, ih = autosize_enclosure(
            placed, positions, min_l, min_w, min_h, panel_max_h)
        cand = (il * iw, placed, positions, il, iw, ih)
        if not _packing_overlap(placed, positions):
            if best is None or cand[0] < best[0]:
                best = cand

    if best is None:
        # Every trial width overlapped: returning `fallback` would violate the
        # stated overlap-free invariant silently. Fail loud instead.
        raise RuntimeError(
            "pack_compact: no overlap-free packing found across "
            f"{len(widths)} trial widths for {len(pack_mods)} modules; "
            "refusing to return an overlapping fallback (no-overlap invariant)."
        )
    _, placed, positions, il, iw, ih = best
    return placed, positions, il, iw, ih


def _pack_on_face(panel_idx: List[int], modules: List[ComponentModule],
                  il: float) -> dict:
    """Shelf-pack panel footprints across the lid plane (row-major, wraps at il)."""
    pos: dict = {}
    cx = cy = _CLEARANCE
    row_h = 0.0
    for i in panel_idx:
        m = modules[i]
        if cx > _CLEARANCE and cx + m.length + _CLEARANCE > il:
            cx = _CLEARANCE
            cy += row_h + _CLEARANCE
            row_h = 0.0
        pos[i] = (round(cx, 1), round(cy, 1))
        cx += m.length + _CLEARANCE
        row_h = max(row_h, m.width)
    return pos


def place_buckets(
    modules: List[ComponentModule],
    pidx: List[int],
    pack_pos: List[Tuple[float, float]],
    il: float, iw: float,
) -> List[Tuple[float, float]]:
    """Absolute (x, y) per module in solver coords (origin at inner corner).

    internal / breadboard -> floor-packed positions inside [0,il] x [0,iw]
    panel                 -> shelf-packed on the lid plane (z handled by caller)
    external              -> outside the +x wall, stacked along y
    embedded              -> outside the +y wall, stacked along x
    """
    pidx_pos = {idx: pack_pos[k] for k, idx in enumerate(pidx)}
    panel_pos = _pack_on_face(
        [i for i, m in enumerate(modules) if m.enclosure_relation in FACE_RELATIONS],
        modules, il)
    allp: List[Tuple[float, float]] = []
    ext_cursor = _CLEARANCE   # external devices stacked beyond the +x wall
    emb_cursor = _CLEARANCE   # embedded hosts stacked beyond the +y wall
    for i, m in enumerate(modules):
        if i in pidx_pos:
            allp.append(pidx_pos[i])
        elif i in panel_pos:
            allp.append(panel_pos[i])
        elif m.enclosure_relation == "external":
            allp.append((round(il + _EXTERNAL_GAP, 1), round(ext_cursor, 1)))
            ext_cursor += m.width + _CLEARANCE
        elif m.enclosure_relation == "embedded":
            # Sit the host structure (water tank etc.) outside the +y wall and
            # place the embedded module at the host's entry_port. Falls back to
            # stacked-outside if host_structure metadata is absent.
            hs = getattr(m, "host_structure", None)
            ep = hs.get("entry_port") if isinstance(hs, dict) else None
            if isinstance(ep, dict):
                dims = hs.get("dimensions") or {}
                host_l = float(dims.get("length_mm", m.length * 2))
                host_w = float(dims.get("width_mm", m.width * 2))
                # H7/NSF: missing u/v must fail loud, not silent-center at 0.5.
                if "u" not in ep or "v" not in ep:
                    raise ValueError(
                        f"{getattr(m, 'comp_type', '<module>')}: embedded entry_port 缺少 u/v "
                        f"(got {ep!r})，拒絕靜默置中 0.5"
                    )
                u = float(ep["u"])
                v = float(ep["v"])
                host_x0 = il / 2 - host_l / 2
                host_y0 = iw + _EXTERNAL_GAP
                allp.append((round(host_x0 + u * host_l - m.length / 2, 1),
                             round(host_y0 + v * host_w - m.width / 2, 1)))
            else:
                allp.append((round(emb_cursor, 1), round(iw + _EXTERNAL_GAP, 1)))
                emb_cursor += m.length + _CLEARANCE
        else:  # unknown -> centre placeholder
            allp.append((round(il / 2 - m.length / 2, 1),
                         round(iw / 2 - m.width / 2, 1)))
    return allp


def _panel_cutout_shape(comp_type: str, L: float, W: float) -> dict:
    """Derive the face opening from the component's mounting method.

    threaded bushing (mounting_holes) -> round hole of that diameter (pot/switch);
    single LED (round light tag)       -> round press-fit hole of the body width;
    everything else (button/strip/...) -> rectangular footprint cutout.
    """
    spec = COMPONENT_REGISTRY.get(comp_type)
    holes = getattr(spec, "mounting_holes", None) if spec else None
    tags = (getattr(spec, "tags", None) or []) if spec else []
    if holes:
        return {"shape": "round", "diameter": round(holes[0].diameter, 1),
                "mount": "threaded"}
    if any(t in _ROUND_LIGHT_TAGS for t in tags):
        return {"shape": "round", "diameter": round(max(L, W), 1),
                "mount": "press_fit"}
    return {"shape": "rect", "width": round(L, 1), "height": round(W, 1),
            "mount": "cutout"}


def panel_cutouts(
    modules: List[ComponentModule],
    allp: List[Tuple[float, float]],
    il: float, iw: float, ih: float,
) -> List[dict]:
    """Face openings (scene y-up coords) for each face-mounted panel module.

    Centre sits on the lid plane (scene Y = ih); the component straddles it with
    its actuator/lens poking out and pins inside. Shape follows the mount method.
    """
    cuts: List[dict] = []
    for i, m in enumerate(modules):
        if m.enclosure_relation not in FACE_RELATIONS:
            continue
        mx, my = allp[i]
        cx, cy = mx + m.length / 2, my + m.width / 2
        shape = _panel_cutout_shape(m.comp_type, m.length, m.width)
        cuts.append({
            "face": "top",
            "center": [round(cx - il / 2, 1), round(ih, 1), round(cy - iw / 2, 1)],
            "comp_type": m.comp_type,
            **shape,
        })
    return cuts


def cross_wall_modules(modules: List[ComponentModule], pairs: List[dict]) -> dict:
    """idx -> True for external/embedded modules wired to a module inside.

    Panel parts are wall-mounted but wired internally, so they never count as a
    wall crossing — only physically separate devices pierce the shell.
    """
    out: dict = {}
    for p in pairs:
        fi, ti = p["from_module"], p["to_module"]
        f_cross = modules[fi].enclosure_relation in WALL_CROSSING_RELATIONS
        t_cross = modules[ti].enclosure_relation in WALL_CROSSING_RELATIONS
        if f_cross != t_cross:                 # exactly one outside -> crosses wall
            out[fi if f_cross else ti] = True
    return out


def _wall_face_for_module(
    m: ComponentModule, pos: Tuple[float, float], il: float, iw: float,
) -> Tuple[str, float, float] | None:
    """Identify which inner wall an outside module sits beyond. Returns
    ``(face, wall_x_or_None, wall_y_or_None)`` in solver coords, or None."""
    x, y = pos
    if x >= il:
        return ("x+", il, None)
    if x + m.length <= 0:
        return ("x-", 0.0, None)
    if y >= iw:
        return ("y+", None, iw)
    if y + m.width <= 0:
        return ("y-", None, 0.0)
    return None


def _segment_wall_crossing(
    p1: Tuple[float, float, float], p2: Tuple[float, float, float],
    face: str, wall: float,
) -> Tuple[float, float, float] | None:
    """Interpolate the (x,y,z) point where segment p1→p2 crosses the named wall."""
    if face in ("x+", "x-"):
        dx = p2[0] - p1[0]
        if dx == 0 or (p1[0] - wall) * (p2[0] - wall) > 0:
            return None
        t = (wall - p1[0]) / dx
        return (wall, p1[1] + t * (p2[1] - p1[1]), p1[2] + t * (p2[2] - p1[2]))
    dy = p2[1] - p1[1]
    if dy == 0 or (p1[1] - wall) * (p2[1] - wall) > 0:
        return None
    t = (wall - p1[1]) / dy
    return (p1[0] + t * (p2[0] - p1[0]), wall, p1[2] + t * (p2[2] - p1[2]))


def compute_wall_holes(
    modules: List[ComponentModule],
    allp: List[Tuple[float, float]],
    pairs: List[dict],
    il: float, iw: float, ih: float,
    wires: List[dict] | None = None,
) -> Tuple[List[dict], dict]:
    """Reserve one wall hole **per cross-wall wire** at its actual crossing point.

    If ``wires`` is omitted, falls back to one hole per outside module at its
    centre projection (legacy behaviour). Wire-aligned holes guarantee the
    rendered tube visibly passes through the hole centre.

    Returns ``(holes, ext_idx)``. Holes are in scene (y-up) coords following the
    _to_yup convention ``[x-il/2, z, y-iw/2]``.
    """
    ext_idx = cross_wall_modules(modules, pairs)
    holes: List[dict] = []

    if wires is None:
        # Legacy fallback: per-module hole at the module's centre projection.
        hy = min(ih * 0.5, max(_HOLE_DIAMETER, ih - _HOLE_DIAMETER))
        for idx in sorted(ext_idx):
            m = modules[idx]
            face_info = _wall_face_for_module(m, allp[idx], il, iw)
            if face_info is None:
                continue
            face, wx, wy = face_info
            cx, cy = allp[idx][0] + m.length / 2, allp[idx][1] + m.width / 2
            sx = wx if wx is not None else min(max(cx, 0.0), il)
            sy = wy if wy is not None else min(max(cy, 0.0), iw)
            holes.append({
                "face": face,
                "center": [round(sx - il / 2, 1), round(hy, 1),
                           round(sy - iw / 2, 1)],
                "diameter": _HOLE_DIAMETER,
                "comp_type": m.comp_type,
            })
        return holes, ext_idx

    # Wire-aligned: per cross-wall wire, hole at the actual wall crossing.
    for wire, pair in zip(wires, pairs):
        f_outside = modules[pair["from_module"]].enclosure_relation in WALL_CROSSING_RELATIONS
        t_outside = modules[pair["to_module"]].enclosure_relation in WALL_CROSSING_RELATIONS
        if f_outside == t_outside:
            continue
        outside_i = pair["from_module"] if f_outside else pair["to_module"]
        m = modules[outside_i]
        face_info = _wall_face_for_module(m, allp[outside_i], il, iw)
        if face_info is None:
            continue
        face, wx, wy = face_info
        wall = wx if wx is not None else wy
        crossing = None
        path = wire.get("path3d", [])
        for i in range(len(path) - 1):
            crossing = _segment_wall_crossing(path[i], path[i + 1], face, wall)
            if crossing is not None:
                break
        if crossing is None:
            continue
        cx_s, cy_s, cz_s = crossing
        center = [round(cx_s - il / 2, 1), round(cz_s, 1), round(cy_s - iw / 2, 1)]
        holes.append({
            "face": face,
            "center": center,
            "diameter": _HOLE_DIAMETER,
            "comp_type": m.comp_type,
            "wire_id": wire.get("id"),
        })
    return holes, ext_idx
