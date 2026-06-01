"""lib/assembly_solver_v3.py -- Assembly V3 three-stage constraint solver.

Pipeline:  Stage 1 MaxRects 2D bin-packing (BSSF) -> Stage 2 True 3D A* routing
-> Stage 3 Coord transform (Z-up -> Y-up) + thermal/CoG validation.
Output: SceneGraph JSON consumed by the Three.js renderer.
"""
from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lib.config import ASSEMBLY_V3
from lib.module_builder import ComponentModule, Pin3D, ShellPort, build_modules
from lib.assembly_solver.ic_validation import (
    validate_assembly, clamp_wire_to_enclosure,
)
from lib.assembly_solver.enclosure_fit import (
    pack_compact, place_buckets, compute_wall_holes, panel_cutouts,
    PACKED_RELATIONS, FACE_RELATIONS, WALL_CROSSING_RELATIONS,
)

_log = logging.getLogger("cadhllm.assembly_solver_v3")

_WIRE_SIGNAL_COLORS: Dict[str, str] = {
    "power": "#ff4444", "gnd": "#333333",
    "analog": "#ffaa00", "digital": "#44cc44",
    "i2c": "#44ddff", "spi": "#dd44ff", "pwm": "#44cc44",
    "uart": "#44ddff",
}
_GRID_RES = ASSEMBLY_V3["GRID_RES"]
_CLEARANCE = ASSEMBLY_V3["CLEARANCE"]
_TURN_PENALTY = ASSEMBLY_V3["TURN_PENALTY"]
_WIRE_MARGIN = ASSEMBLY_V3["WIRE_MARGIN"]
_VENT_THRESHOLD_MW = ASSEMBLY_V3["VENT_THRESHOLD_MW"]
_H_CONV = ASSEMBLY_V3["H_CONV"]
_DT_MAX = ASSEMBLY_V3["DT_MAX"]

# -- Stage 1: MaxRects BSSF ------------------------------------------------

@dataclass
class _Rect:
    x: float; y: float; w: float; h: float   # noqa: E702


def _pack_maxrects(
    modules: List[ComponentModule], inner_l: float, inner_w: float,
) -> List[Tuple[float, float, bool]]:
    """MaxRects BSSF packing.  Returns (x, y, rotated) per module in input order.

    `rotated` means the module's footprint was swapped (L<->W) to fit; callers
    must apply that swap (and rotate ports) so downstream geometry matches.
    """
    pad = _CLEARANCE
    eff_l, eff_w = inner_l - 2 * pad, inner_w - 2 * pad
    indices = sorted(range(len(modules)),
                     key=lambda i: modules[i].length * modules[i].width, reverse=True)
    free: List[_Rect] = [_Rect(pad, pad, eff_l, eff_w)]
    pos: Dict[int, Tuple[float, float, bool]] = {}

    for idx in indices:
        m = modules[idx]
        mw, mh = m.length + pad, m.width + pad
        best_r: Optional[_Rect] = None
        # BSSF tie-break fix: use (score, fr.x, fr.y) as the canonical key so
        # tie resolution is independent of free-rect list order (which varies with
        # _split_rect/_prune ordering across refactors). rot=False < rot=True via
        # stable iteration order, giving the unrotated orientation priority on ties.
        best_key = (float("inf"), float("inf"), float("inf"))
        best_rot = False
        for fr in free:
            for rot in (False, True):
                pw, ph = (mh, mw) if rot else (mw, mh)
                if pw <= fr.w + 0.01 and ph <= fr.h + 0.01:
                    ss = min(fr.w - pw, fr.h - ph)
                    key = (ss, fr.x, fr.y)
                    if key < best_key:
                        best_key, best_r, best_rot = key, fr, rot
        if best_r is None:
            my = pad
            for pi, (px, py, pr) in pos.items():
                eff_w_pi = modules[pi].length if pr else modules[pi].width
                my = max(my, py + eff_w_pi + pad)
            pos[idx] = (pad, my, False)
            _log.warning("MaxRects overflow for %s", m.comp_type)
            continue
        pw, ph = (mh, mw) if best_rot else (mw, mh)
        pos[idx] = (best_r.x, best_r.y, best_rot)
        placed = _Rect(best_r.x, best_r.y, pw, ph)
        nf: List[_Rect] = []
        for fr in free:
            nf.extend(_split_rect(fr, placed))
        free = _prune([r for r in nf if r.w > 1.0 and r.h > 1.0])
    return [pos.get(i, (pad, pad, False)) for i in range(len(modules))]


def _split_rect(free: _Rect, placed: _Rect) -> List[_Rect]:
    """Split *free* around *placed* (maximal-rectangles, up to 4 strips)."""
    if (placed.x >= free.x + free.w - 0.01 or placed.x + placed.w <= free.x + 0.01 or
            placed.y >= free.y + free.h - 0.01 or placed.y + placed.h <= free.y + 0.01):
        return [free]
    r: List[_Rect] = []
    if placed.x > free.x + 0.01:
        r.append(_Rect(free.x, free.y, placed.x - free.x, free.h))
    re = placed.x + placed.w
    if re < free.x + free.w - 0.01:
        r.append(_Rect(re, free.y, free.x + free.w - re, free.h))
    if placed.y > free.y + 0.01:
        r.append(_Rect(free.x, free.y, free.w, placed.y - free.y))
    te = placed.y + placed.h
    if te < free.y + free.h - 0.01:
        r.append(_Rect(free.x, te, free.w, free.y + free.h - te))
    return r


def _prune(rects: List[_Rect]) -> List[_Rect]:
    """Remove rects strictly contained in another."""
    n = len(rects)
    skip = [False] * n
    for i in range(n):
        if skip[i]:
            continue
        a = rects[i]
        for j in range(n):
            if i == j or skip[j]:
                continue
            b = rects[j]
            if (b.x <= a.x + 0.01 and b.y <= a.y + 0.01 and
                    b.x + b.w >= a.x + a.w - 0.01 and b.y + b.h >= a.y + a.h - 0.01):
                skip[i] = True
                break
    return [rects[i] for i in range(n) if not skip[i]]

# -- Stage 2: 3D A* router -------------------------------------------------

def _route_wires_3d(
    modules: List[ComponentModule], placements: List[Tuple[float, float]],
    pairs: List[dict], inner_l: float, inner_w: float, inner_h: float,
    zbase: Optional[List[float]] = None,
) -> List[dict]:
    """True 3D A* routing, 6-dir with turn penalty.

    Routes at an elevated z-layer above the tallest component, with vertical
    risers from port z to routing z.  This prevents wires from being blocked
    by component bounding boxes on the floor plane.
    """
    res = _GRID_RES
    gxm = max(1, int(inner_l / res))
    gym = max(1, int(inner_w / res))
    gzm = max(1, int(inner_h / res))
    blocked: set = set()
    max_comp_h = 0.0
    for i, m in enumerate(modules):
        if m.enclosure_relation not in ("internal", "breadboard"):
            continue
        mx, my = placements[i]
        max_comp_h = max(max_comp_h, m.height)
        for bx in range(max(0, int(mx / res) - 1), min(gxm, int((mx + m.length) / res) + 1)):
            for by in range(max(0, int(my / res) - 1), min(gym, int((my + m.width) / res) + 1)):
                for bz in range(0, min(gzm, int(m.height / res) + 1)):
                    blocked.add((bx, by, bz))
    route_z = max_comp_h + _CLEARANCE
    wires: List[dict] = []
    zb = zbase or [0.0] * len(modules)
    for wi, pair in enumerate(pairs):
        fm, tm = modules[pair["from_module"]], modules[pair["to_module"]]
        fp, tp = placements[pair["from_module"]], placements[pair["to_module"]]
        port_s = _port_world(fm, fp, pair["from_port"], pair["from_pin"], zb[pair["from_module"]])
        port_e = _port_world(tm, tp, pair["to_port"], pair["to_pin"], zb[pair["to_module"]])
        start_3d = (port_s[0], port_s[1], route_z)
        end_3d = (port_e[0], port_e[1], route_z)
        path = _astar3(start_3d, end_3d, blocked, gxm, gym, gzm, res)
        full_path = [port_s, (port_s[0], port_s[1], route_z)]
        full_path.extend(path)
        full_path.append((port_e[0], port_e[1], route_z))
        full_path.append(port_e)
        # Wires are tubes — they can run parallel along the same path (like a real
        # cable harness). Adding the routed path back to `blocked` made every
        # subsequent wire fall back to a straight line. Only components block.
        sig = pair.get("signal", "digital")
        wires.append({
            "id": f"w{wi}",
            "from": {"module": _mid(fm, pair["from_module"]),
                     "port": pair["from_port"], "pin": pair["from_pin"]},
            "to":   {"module": _mid(tm, pair["to_module"]),
                     "port": pair["to_port"], "pin": pair["to_pin"]},
            "signal": sig, "color": _WIRE_SIGNAL_COLORS.get(sig, "#8888cc"),
            "path3d": _simplify_3d(full_path), "style": "catmull-rom",
        })
    return wires


def _port_world(m: ComponentModule, pl: Tuple[float,float],
                port: str, pin: str, zbase: float = 0.0) -> Tuple[float,float,float]:
    mx, my = pl
    for sp in m.shell_ports:
        if sp.name == port:
            return (mx+sp.x, my+sp.y, zbase+sp.z)
    for p in m.pins:
        if p.name == pin or p.arduino_pin == pin:
            return (mx+p.x, my+p.y, zbase+p.z)
    return (mx+m.length/2, my+m.width/2, zbase+m.height)


def _astar3(start, end, blocked, gxm, gym, gzm, res):
    """6-direction 3D A* with turn penalty. Falls back to straight line."""
    tg = lambda x, y, z: (max(0,min(gxm-1,int(x/res))),
                           max(0,min(gym-1,int(y/res))),
                           max(0,min(gzm-1,int(z/res))))
    tw = lambda g: (g[0]*res+res/2, g[1]*res+res/2, g[2]*res+res/2)
    sg, eg = tg(*start), tg(*end)
    if sg == eg:
        return [start, end]
    dirs = [(1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)]
    h = lambda a, b: abs(a[0]-b[0])+abs(a[1]-b[1])+abs(a[2]-b[2])
    cnt = 0; oset: list = []; g_sc: Dict[tuple,float] = {sg: 0.0}
    came: Dict[tuple,tuple] = {}
    heapq.heappush(oset, (0.0, cnt, sg, -1))
    mx_v = gxm * gym * gzm * 2; vis = 0
    while oset and vis < mx_v:
        _, _, cur, pd = heapq.heappop(oset); vis += 1
        if cur == eg:
            path = [end]; n = eg
            while n in came:
                n = came[n]; path.append(tw(n))
            path.append(start); path.reverse(); return path
        for di, (dx,dy,dz) in enumerate(dirs):
            nb = (cur[0]+dx, cur[1]+dy, cur[2]+dz)
            if nb[0]<0 or nb[0]>=gxm or nb[1]<0 or nb[1]>=gym or nb[2]<0 or nb[2]>=gzm:
                continue
            if nb in blocked:
                continue
            tc = _TURN_PENALTY if (pd >= 0 and di != pd) else 0.0
            tent = g_sc[cur] + 1.0 + tc
            if tent < g_sc.get(nb, float("inf")):
                came[nb] = cur; g_sc[nb] = tent; cnt += 1
                heapq.heappush(oset, (tent + h(nb, eg), cnt, nb, di))
    _log.warning("A* fallback %s->%s", start, end)
    return [start, end]


def _simplify_3d(path) -> List[List[float]]:
    if len(path) <= 2:
        return [[round(p[0],1), round(p[1],1), round(p[2],1)] for p in path]
    res = [path[0]]
    for i in range(1, len(path)-1):
        pr, cu, nx = res[-1], path[i], path[i+1]
        d1 = (cu[0]-pr[0], cu[1]-pr[1], cu[2]-pr[2])
        d2 = (nx[0]-cu[0], nx[1]-cu[1], nx[2]-cu[2])
        cross = (abs(d1[1]*d2[2]-d1[2]*d2[1]) + abs(d1[2]*d2[0]-d1[0]*d2[2])
                 + abs(d1[0]*d2[1]-d1[1]*d2[0]))
        if cross > 0.01:
            res.append(cu)
    res.append(path[-1])
    return [[round(p[0],1), round(p[1],1), round(p[2],1)] for p in res]

# -- Wiring pair extraction -------------------------------------------------

def _extract_module_pairs(wiring_raw: dict, modules: List[ComponentModule]) -> List[dict]:
    """Extract inter-module wiring pairs (format A: connections list, B: legacy keyed)."""
    idx_s: Dict[str, int] = {}
    for i, m in enumerate(modules):
        short = m.comp_type.replace("-class","").replace("-","").lower()
        idx_s[short] = i
        for part in m.comp_type.replace("-class","").split("-"):
            k = part.lower()
            if k not in ("class","module","sensor"):
                idx_s[k] = i
    brain: Optional[int] = next((i for i,m in enumerate(modules) if m.role=="Brain"), None)
    pairs: List[dict] = []
    conns = wiring_raw.get("connections", [])
    if conns:
        for c in conns:
            fi, fp, fpin = _resolve_ep(c.get("from",""), modules, idx_s)
            ti, tp, tpin = _resolve_ep(c.get("to",""), modules, idx_s)
            if fi is not None and ti is not None:
                pairs.append({"from_module":fi,"from_port":fp,"from_pin":fpin,
                              "to_module":ti,"to_port":tp,"to_pin":tpin,
                              "signal":c.get("signal","digital")})
        return pairs
    if brain is None:
        return pairs
    for ck, info in wiring_raw.items():
        if ck == "connections":
            continue
        ckl = ck.replace("-","").lower()
        ti = next((idx for s, idx in idx_s.items() if (s in ckl or ckl in s) and idx != brain), None)
        if ti is None:
            continue
        for pin in info.get("pins", []):
            mp, cp = pin.get("mcu",""), pin.get("comp", pin.get("label",""))
            if mp == "LOAD":
                continue
            sig = _classify_signal(mp, cp)
            pairs.append({"from_module":brain, "from_port":_find_port(modules[brain],mp),
                          "from_pin":mp, "to_module":ti,
                          "to_port":_find_port(modules[ti],cp), "to_pin":cp, "signal":sig})
    return pairs


def _resolve_ep(spec, modules, idx_s):
    if "." not in spec:
        return (None, "", spec)
    comp, pin = spec.rsplit(".", 1)
    short = comp.replace("-class","").replace("-","").lower()
    idx = next((i for s,i in idx_s.items() if s in short or short in s), None)
    if idx is None:
        return (None, "", pin)
    return (idx, _find_port(modules[idx], pin), pin)


def _find_port(m: ComponentModule, pin: str) -> str:
    for sp in m.shell_ports:
        if pin in sp.pins:
            return sp.name
    return m.shell_ports[0].name if m.shell_ports else ""


def _classify_signal(mcu: str, comp: str) -> str:
    p = mcu.upper()
    if p.startswith("A") and p[1:].isdigit(): return "analog"
    if "SDA" in p or "SCL" in p: return "i2c"
    if any(k in p for k in ("MOSI","MISO","SCK","SS")): return "spi"
    if p in ("5V","VCC","3.3V","3V3","VIN"): return "power"
    if p == "GND": return "gnd"
    c = comp.upper()
    if c in ("VCC","V+","BAT+"): return "power"
    if c in ("GND","V-","BAT-"): return "gnd"
    return "digital"

# -- Stage 3: coord transform + validation ----------------------------------

def _to_yup(x, y, z, il, iw) -> List[float]:
    """Z-up solver -> Y-up scene (enclosure centre origin)."""
    return [round(x - il/2, 1), round(z, 1), round(y - iw/2, 1)]


def _validate_thermal(modules: List[ComponentModule]) -> dict:
    src, mw = [], 0.0
    for m in modules:
        if m.thermal_mw > 0:
            src.append({"type": m.comp_type, "power_mw": round(m.thermal_mw, 1)})
        mw += m.thermal_mw
    w = mw / 1000.0
    vent = mw > _VENT_THRESHOLD_MW
    vp = [{"face":"side_lower","area_mm2":round(max(40,w/(_H_CONV*_DT_MAX)*1e6),0)}] if vent else []
    dt = w / (_H_CONV * 0.01) if w > 0 else 0.0
    return {"heat_sources":src, "total_power_mw":round(mw,1),
            "needs_venting":vent, "vent_placements":vp, "estimated_dt_c":round(dt,1)}


def _check_cog(modules, placements, il, iw):
    tw = sum(m.weight_g for m in modules)
    if tw < 0.1:
        return {"ok":True, "cog":[0,0], "msg":"near-zero weight"}
    cx = sum((placements[i][0]+m.length/2)*m.weight_g for i,m in enumerate(modules))/tw
    cy = sum((placements[i][1]+m.width/2)*m.weight_g for i,m in enumerate(modules))/tw
    ok = abs(cx-il/2) <= il/3 and abs(cy-iw/2) <= iw/3
    return {"ok":ok, "cog":[round(cx,1),round(cy,1)],
            "msg":"within 2/3 zone" if ok else "off-centre"}


def _mid(m: ComponentModule, i: int) -> str:
    return f"{m.comp_type.replace('-class','').lower()}-{i}"

# -- Public API -------------------------------------------------------------

def solve_v3(components: List[dict], wiring_raw: dict, enclosure_spec: dict) -> dict:
    """Assembly V3 main entry.  Returns a SceneGraph JSON dict."""
    min_il = enclosure_spec.get("inner_length", 80)
    min_iw = enclosure_spec.get("inner_width", 60)
    min_ih = enclosure_spec.get("inner_height", 40)
    wall = enclosure_spec.get("wall", 2.5)
    modules = build_modules(components)
    if not modules:
        return _empty_scene(min_il, min_iw, min_ih, wall)

    pidx = [i for i, m in enumerate(modules)
            if m.enclosure_relation in PACKED_RELATIONS]
    pack_mods = [modules[i] for i in pidx]
    # Tallest panel hangs down from the lid into the cavity — autosize must add
    # its height on top of the internal max so they never collide.
    panel_max_h = max((m.height for m in modules
                       if m.enclosure_relation in FACE_RELATIONS), default=0.0)
    # Independent enclosure: pack internal modules into the most compact,
    # overlap-free footprint, then shrink-wrap the shell to fit (no OOB by
    # construction). Rotated modules are returned already transformed.
    placed_mods, pack_pos, il, iw, ih = pack_compact(
        pack_mods, _pack_maxrects, min_il, min_iw, min_ih, panel_max_h)
    for k, i in enumerate(pidx):
        modules[i] = placed_mods[k]
    allp = place_buckets(modules, pidx, pack_pos, il, iw)
    # Panel parts mount on the lid: lift their bottom to (ih - height) so pins sit
    # just under the top face and wires route up to meet them.
    zbase = [(ih - m.height) if m.enclosure_relation in FACE_RELATIONS else 0.0
             for m in modules]
    # B3 validation: assert no panel has inverted or out-of-enclosure z placement.
    # autosize_enclosure guarantees ih >= max_internal_h + panel_max_h + _CLEARANCE,
    # so zbase for the tallest panel = ih - panel_max_h >= max_internal_h + _CLEARANCE > 0.
    _TOL_Z = 0.5  # mm — rounding tolerance
    for _i, (_m, _zb) in enumerate(zip(modules, zbase)):
        if _m.enclosure_relation in FACE_RELATIONS:
            if _zb < -_TOL_Z:
                raise ValueError(
                    f"B3 zbase inversion: module {_m.comp_type!r} (idx={_i}) "
                    f"has zbase={_zb:.2f} < 0 (ih={ih}, height={_m.height}). "
                    f"autosize_enclosure did not grow ih enough."
                )
            if _zb + _m.height > ih + _TOL_Z:
                raise ValueError(
                    f"B3 zbase OOB: module {_m.comp_type!r} (idx={_i}) "
                    f"top={_zb + _m.height:.2f} > ih={ih}. Panel exceeds inner box."
                )
    cutouts = panel_cutouts(modules, allp, il, iw, ih)

    pairs = _extract_module_pairs(wiring_raw, modules)
    ws = _route_wires_3d(modules, allp, pairs, il, iw, ih, zbase)
    holes, _ext_idx = compute_wall_holes(modules, allp, pairs, il, iw, ih, ws)
    thermal = _validate_thermal(modules)
    cog = _check_cog(modules, allp, il, iw)

    decisions = [
        f"Enclosure auto-sized to {il}x{iw}x{ih}mm inner, fitting {len(pack_mods)} packed modules",
        f"3D A* routed {len(ws)} wires (grid {_GRID_RES}mm, 6-dir, turn penalty {_TURN_PENALTY})",
        f"Thermal: {thermal['total_power_mw']}mW, vent={thermal['needs_venting']}, dT~{thermal.get('estimated_dt_c',0)}C",
        f"CoG: {cog['msg']} at {cog['cog']}",
    ]
    if holes:
        decisions.append(
            f"Reserved {len(holes)} wall hole(s) for external wiring")
    if cutouts:
        decisions.append(
            f"Face-mounted {len(cutouts)} panel part(s) on the lid with cutouts")

    scene_mods = []
    for i, m in enumerate(modules):
        mx, my = allp[i]
        zb = zbase[i]
        is_face = m.enclosure_relation in FACE_RELATIONS
        center_z = (ih - m.height / 2) if is_face else 0.0
        sp_list = [{"name":sp.name, "world":_to_yup(mx+sp.x,my+sp.y,zb+sp.z,il,iw),
                     "port_type":sp.port_type, "side":sp.side,
                     "width":sp.width, "height":sp.height, "pins":sp.pins}
                    for sp in m.shell_ports]
        entry = {
            "id":_mid(m,i), "comp_type":m.comp_type, "role":m.role,
            "position":_to_yup(mx+m.length/2, my+m.width/2, center_z, il, iw),
            "dimensions":[m.length, m.width, m.height],
            "enclosure_relation":m.enclosure_relation,
            "meshes":[{"variant":mr.variant,"url":mr.url,"format":mr.format} for mr in m.meshes],
            "shell_ports":sp_list, "thermal_mw":m.thermal_mw,
        }
        if getattr(m, "host_structure", None) is not None:
            entry["host_structure"] = m.host_structure
        scene_mods.append(entry)

    enclosure_inner = [il, iw, ih]
    scene_wires = []
    for w, pair in zip(ws, pairs):
        sw = dict(w)
        raw_path = [_to_yup(p[0], p[1], p[2], il, iw) for p in w["path3d"]]
        f_x = modules[pair["from_module"]].enclosure_relation in WALL_CROSSING_RELATIONS
        t_x = modules[pair["to_module"]].enclosure_relation in WALL_CROSSING_RELATIONS
        if f_x != t_x and len(raw_path) >= 2:
            # Crosses a wall: keep the outside endpoint(s) so the wire enters
            # through a reserved hole; clamp only the interior waypoints.
            body = clamp_wire_to_enclosure(raw_path[1:-1], enclosure_inner)
            sw["path3d"] = [raw_path[0]] + body + [raw_path[-1]]
            sw["crosses_wall"] = True
        else:
            sw["path3d"] = clamp_wire_to_enclosure(raw_path, enclosure_inner)
        scene_wires.append(sw)

    scene = {
        "version":"3.0", "coordinate_system":"y-up",
        "enclosure":{"inner":enclosure_inner, "wall":wall, "holes":holes,
                     "face_cutouts":cutouts, "meshes":[]},
        "modules":scene_mods, "wires":scene_wires,
        "thermal_field":thermal, "decisions":decisions,
    }

    validation = validate_assembly(scene)
    scene["validation"] = validation.to_dict()
    if not validation.passed:
        n_err = len([i for i in validation.issues if i.severity == "error"])
        decisions.append(f"Validation: {n_err} error(s) detected")
    else:
        decisions.append("Validation: all checks passed")

    return scene


def _empty_scene(il, iw, ih, wall):
    return {"version":"3.0", "coordinate_system":"y-up",
            "enclosure":{"inner":[il,iw,ih],"wall":wall,"meshes":[]},
            "modules":[], "wires":[],
            "thermal_field":{"heat_sources":[],"total_power_mw":0,
                             "needs_venting":False,"vent_placements":[]},
            "decisions":[],
            "validation":{"passed":True,"checks_run":0,"checks_passed":0,"issues":[]}}
