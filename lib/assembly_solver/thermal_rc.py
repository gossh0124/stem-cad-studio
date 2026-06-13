"""ADR-10: IC-level lumped RC thermal network solver.

Each SubComponent with rth_ja_cw > 0 becomes a node in a thermal resistance
network. Steady-state solve: T = T_ambient + R * P (matrix form).
Supports inter-node coupling via PCB copper thermal resistance.

Usage:
    from lib.assembly_solver.thermal_rc import thermal_rc_report
    report = thermal_rc_report(ARDUINO_UNO_R3, mode='typical', ambient_c=25.0)
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

from lib.pcb._types import PCBSpec, SubComponent

# Physical constants
K_COPPER = 385.0     # W/(m*K) — copper thermal conductivity
K_FR4 = 0.25         # W/(m*K) — FR4 substrate thermal conductivity
MAX_COUPLING_DIST_MM = 50.0  # max distance for thermal coupling (mm)

# Warning thresholds (deg C)
WARN_ELEVATED_C = 70.0
WARN_CRITICAL_C = 85.0

# Try numpy for matrix solve; fall back to diagonal-only solve
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


def _distance_mm(a_x: float, a_y: float, b_x: float, b_y: float) -> float:
    """Euclidean distance between two points in mm."""
    return math.sqrt((a_x - b_x) ** 2 + (a_y - b_y) ** 2)


def _thermal_power_mw(sc: SubComponent, mode: str) -> float:
    """Get power in mW for a SubComponent in the given mode."""
    attr = f'thermal_{mode}_mw'
    return getattr(sc, attr, 0.0)


def compute_coupling_resistance(
    comp_a: SubComponent,
    comp_b: SubComponent,
    pcb_thickness: float = 1.6,
    copper_fraction: float = 0.3,
) -> float:
    """Estimate thermal coupling between two SubComponents via PCB.

    R_coupling = distance / (k_eff * A_cross)
    k_eff = copper_fraction * k_copper + (1-copper_fraction) * k_fr4
    A_cross = pcb_thickness * min(body_w_a, body_w_b)  (in m^2)

    Returns thermal resistance in deg C/W.
    """
    dist_mm = _distance_mm(
        comp_a.anchor_x, comp_a.anchor_y,
        comp_b.anchor_x, comp_b.anchor_y,
    )
    if dist_mm <= 0:
        # Overlapping components: use a small nominal resistance
        return 1.0

    k_eff = copper_fraction * K_COPPER + (1 - copper_fraction) * K_FR4
    # Cross-section area: pcb_thickness * min body width (convert mm -> m)
    min_w_mm = min(comp_a.body_w, comp_b.body_w)
    if min_w_mm <= 0:
        min_w_mm = 1.0  # fallback for zero-width components
    a_cross_m2 = (pcb_thickness / 1000.0) * (min_w_mm / 1000.0)

    # Distance in meters
    dist_m = dist_mm / 1000.0

    r_coupling = dist_m / (k_eff * a_cross_m2)
    return r_coupling


def build_thermal_network(
    pcb_spec: PCBSpec,
    mode: str = 'typical',
    ambient_c: float = 25.0,
) -> dict:
    """Build thermal network from PCB SubComponents.

    Returns dict with:
      - nodes: list of {name, package, rth_ja, power_mw, position}
      - adjacency: list of {from, to, r_coupling} (PCB copper coupling)
      - pcb_thickness: board thickness in mm
    """
    nodes: List[dict] = []
    thermal_scs: List[SubComponent] = []

    for sc in pcb_spec.sub_components:
        if sc.rth_ja_cw <= 0:
            continue
        power_mw = _thermal_power_mw(sc, mode)
        nodes.append({
            'name': sc.name,
            'package': sc.package,
            'rth_ja': sc.rth_ja_cw,
            'power_mw': power_mw,
            'position': (sc.anchor_x, sc.anchor_y),
        })
        thermal_scs.append(sc)

    # Build adjacency (coupling) for nodes within MAX_COUPLING_DIST_MM
    adjacency: List[dict] = []
    pcb_thick = getattr(pcb_spec, 'pcb_thickness', 1.6)
    for i in range(len(thermal_scs)):
        for j in range(i + 1, len(thermal_scs)):
            dist = _distance_mm(
                thermal_scs[i].anchor_x, thermal_scs[i].anchor_y,
                thermal_scs[j].anchor_x, thermal_scs[j].anchor_y,
            )
            if dist <= MAX_COUPLING_DIST_MM:
                r_coup = compute_coupling_resistance(
                    thermal_scs[i], thermal_scs[j],
                    pcb_thickness=pcb_thick,
                )
                adjacency.append({
                    'from': thermal_scs[i].name,
                    'to': thermal_scs[j].name,
                    'r_coupling': r_coup,
                })

    return {
        'nodes': nodes,
        'adjacency': adjacency,
        'pcb_thickness': pcb_thick,
    }


def _solve_with_numpy(network: dict, ambient_c: float) -> list:
    """Matrix solve: G * dT = P, T = dT + T_ambient."""
    nodes = network['nodes']
    adjacency = network['adjacency']
    n = len(nodes)

    name_to_idx = {nd['name']: i for i, nd in enumerate(nodes)}

    # Build conductance matrix G and power vector P
    G = np.zeros((n, n), dtype=float)
    P = np.zeros(n, dtype=float)

    for i, nd in enumerate(nodes):
        rth_ja = nd['rth_ja']
        if rth_ja > 0:
            G[i, i] += 1.0 / rth_ja
        P[i] = nd['power_mw'] / 1000.0  # convert mW -> W

    for edge in adjacency:
        i = name_to_idx[edge['from']]
        j = name_to_idx[edge['to']]
        r_c = edge['r_coupling']
        if r_c > 0:
            g_c = 1.0 / r_c
            G[i, i] += g_c
            G[j, j] += g_c
            G[i, j] -= g_c
            G[j, i] -= g_c

    # Solve G * dT = P
    dT = np.linalg.solve(G, P)

    results = []
    for i, nd in enumerate(nodes):
        temp_c = ambient_c + dT[i]
        results.append({
            'name': nd['name'],
            'temp_c': round(temp_c, 2),
            'delta_t': round(dT[i], 2),
            'power_mw': nd['power_mw'],
            'rth_ja': nd['rth_ja'],
        })
    return results


def _solve_diagonal(network: dict, ambient_c: float) -> list:
    """Fallback diagonal solve (no coupling): dT[i] = Rth_ja[i] * P[i]."""
    nodes = network['nodes']
    results = []
    for nd in nodes:
        power_w = nd['power_mw'] / 1000.0
        rth_ja = nd['rth_ja']
        delta_t = rth_ja * power_w
        temp_c = ambient_c + delta_t
        results.append({
            'name': nd['name'],
            'temp_c': round(temp_c, 2),
            'delta_t': round(delta_t, 2),
            'power_mw': nd['power_mw'],
            'rth_ja': nd['rth_ja'],
        })
    return results


def solve_steady_state(
    network: dict,
    ambient_c: float = 25.0,
) -> list:
    """Solve T = T_ambient + R_network * P for each node.

    For N nodes:
      G[i,i] = 1/Rth_ja[i] + sum(1/R_coupling[i,j] for j neighbors)
      G[i,j] = -1/R_coupling[i,j]
      P[i] = power_w[i]
      T = G_inv * P + T_ambient

    Returns list of {name, temp_c, delta_t, power_mw, rth_ja}.
    Falls back to diagonal solve if numpy is unavailable.
    """
    nodes = network['nodes']
    if not nodes:
        return []

    if len(nodes) == 1:
        # Single node: simple R*P calculation
        return _solve_diagonal(network, ambient_c)

    if network.get('adjacency'):
        if not _HAS_NUMPY:
            # Multi-node board WITH coupling but numpy missing: refuse to
            # silently drop inter-node coupling (off-diagonal G terms), which
            # would yield systematically lower/incorrect junction temps with
            # no surfaced error. Zero-fallback: surface the deployment defect.
            raise RuntimeError(
                "coupled thermal solve requires numpy: network has "
                f"{len(network['adjacency'])} coupling edge(s) but numpy is "
                "unavailable; refusing to return a coupling-free approximation")
        return _solve_with_numpy(network, ambient_c)

    # No coupling adjacency: diagonal solve is exact (no inter-node terms).
    return _solve_diagonal(network, ambient_c)


def _generate_warnings(solved_nodes: list) -> list:
    """Generate thermal warnings based on junction temperature."""
    warnings = []
    for nd in solved_nodes:
        temp = nd['temp_c']
        name = nd['name']
        if temp > WARN_CRITICAL_C:
            warnings.append({
                'level': 'critical',
                'node': name,
                'temp_c': temp,
                'message': (
                    f'{name}: Tj={temp:.1f}C > {WARN_CRITICAL_C}C -- '
                    f'critical thermal risk, active cooling required'
                ),
            })
        elif temp > WARN_ELEVATED_C:
            warnings.append({
                'level': 'elevated',
                'node': name,
                'temp_c': temp,
                'message': (
                    f'{name}: Tj={temp:.1f}C > {WARN_ELEVATED_C}C -- '
                    f'elevated temperature, consider thermal management'
                ),
            })
    return warnings


def thermal_rc_report(
    pcb_spec: PCBSpec,
    mode: str = 'typical',
    ambient_c: float = 25.0,
) -> dict:
    """High-level API: build network + solve + return structured report.

    Returns dict:
      - nodes: list of solved node temperatures
      - max_temp_c: highest junction temperature
      - max_delta_t: highest temperature rise
      - ambient_c: ambient temperature used
      - mode: thermal mode used
      - coupling_count: number of inter-node couplings
      - warnings: list of warnings (e.g., temp > 85C)
      - board_name: PCB board name
    """
    network = build_thermal_network(pcb_spec, mode=mode, ambient_c=ambient_c)
    solved = solve_steady_state(network, ambient_c=ambient_c)
    warnings = _generate_warnings(solved)

    max_temp = max((nd['temp_c'] for nd in solved), default=ambient_c)
    max_delta = max((nd['delta_t'] for nd in solved), default=0.0)

    return {
        'nodes': solved,
        'max_temp_c': max_temp,
        'max_delta_t': max_delta,
        'ambient_c': ambient_c,
        'mode': mode,
        'coupling_count': len(network['adjacency']),
        'warnings': warnings,
        'board_name': pcb_spec.name,
    }


def ic_thermal_for(comp_type: str, mode: str = 'typical') -> list:
    """A5.1: per-IC steady-state junction temps for a module's PCB, joined with board
    position, for the assembly scene graph (renderer colours the matching mesh part).

    Returns [] for modules whose PCB has no sub-components carrying rth_ja_cw>0 (or no
    PCBSpec at all). Zero-fallback: if a PCB DOES have thermal sub-components but the
    RC solve yields no nodes, raise rather than silently emit [] — a solve regression
    must surface, never be masked as "no thermal data".
    """
    from lib.pcb import PCB_REGISTRY  # lazy import to avoid circular-import risk
    pcb_spec = PCB_REGISTRY.get(comp_type)
    if pcb_spec is None:
        return []
    subs = list(getattr(pcb_spec, 'sub_components', None) or [])
    thermal_subs = [sc for sc in subs if getattr(sc, 'rth_ja_cw', 0.0) > 0]
    if not thermal_subs:
        return []
    report = thermal_rc_report(pcb_spec, mode=mode)
    nodes = {nd['name']: nd for nd in report.get('nodes', [])}
    if not nodes:
        raise ValueError(
            f"{comp_type}: PCB has {len(thermal_subs)} thermal sub-components but "
            "thermal_rc_report returned no nodes (refusing silent empty ic_thermal)")
    out: list = []
    for sc in thermal_subs:
        nd = nodes.get(sc.name)
        if nd is None:
            continue
        out.append({
            'name': sc.name,
            'temp_c': round(nd['temp_c'], 2),
            'delta_t': round(nd['delta_t'], 2),
            'power_mw': round(nd.get('power_mw', getattr(sc, 'thermal_typical_mw', 0.0)), 1),
            'anchor_x': sc.anchor_x, 'anchor_y': sc.anchor_y,
            'body_l': sc.body_l, 'body_w': sc.body_w,
        })
    return out
