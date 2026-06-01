"""ADR-9: Dependency DAG + topological sort for component placement ordering.

Kahn's algorithm (BFS) determines placement order based on structural deps.
Returns layers where same-layer components can be placed in parallel.
"""
from __future__ import annotations

import warnings
from collections import deque
from typing import Dict, List, Optional, Set

# Placement priority tiers (lower = placed earlier)
_TIER_MCU = 0
_TIER_POWER = 1
_TIER_INTERNAL = 2
_TIER_PANEL = 3
_TIER_EXTERNAL = 4

_BRAIN_ROLES = {"Brain", "brain", "MCU", "mcu"}
_POWER_ROLES = {"Power", "power", "Battery", "battery", "PSU", "psu"}
_POWER_TYPES_KEYWORDS = ("battery", "power", "psu", "regulator", "buck", "boost")


def _classify_tier(comp: dict) -> int:
    """Classify a component into a placement priority tier."""
    role = comp.get("role", "")
    comp_type = comp.get("type", "").lower()
    enclosure = comp.get("enclosure_relation", "internal")

    if role in _BRAIN_ROLES or "arduino" in comp_type or "esp32" in comp_type:
        return _TIER_MCU
    if role in _POWER_ROLES or any(kw in comp_type for kw in _POWER_TYPES_KEYWORDS):
        return _TIER_POWER
    if enclosure == "external":
        return _TIER_EXTERNAL
    if enclosure == "panel":
        return _TIER_PANEL
    return _TIER_INTERNAL


def _get_i2c_components(comps: List[dict], wiring: Optional[dict] = None) -> List[str]:
    """Identify I2C bus components from wiring info."""
    if not wiring:
        return []
    i2c_types: List[str] = []
    for comp_key, info in wiring.items():
        pins = info.get("pins", [])
        for pin in pins:
            mcu_pin = pin.get("mcu", "").upper()
            if "SDA" in mcu_pin or "SCL" in mcu_pin:
                # Find matching component type
                for c in comps:
                    ct = c.get("type", "")
                    short = ct.replace("-class", "").replace("-", "").lower()
                    ck_lower = comp_key.replace("-", "").lower()
                    if short in ck_lower or ck_lower in short:
                        if ct not in i2c_types:
                            i2c_types.append(ct)
                        break
                break
    return i2c_types


def build_placement_dag(
    components: List[dict],
    wiring: Optional[dict] = None,
    bus_routes: Optional[List[dict]] = None,
) -> Dict[str, Set[str]]:
    """Build directed dependency graph for placement. Returns node -> deps set."""
    graph: Dict[str, Set[str]] = {}

    # H8: 前置檢查每個 component 必須有 'type' 鍵
    for i, c in enumerate(components):
        if "type" not in c:
            raise ValueError(
                f"components[{i}] 缺少 'type' 鍵: {c}"
            )
    comp_types = [c["type"] for c in components]

    for ct in comp_types:
        graph[ct] = set()

    # Classify all components
    tier_map: Dict[str, int] = {}
    for c in components:
        ct = c["type"]
        tier_map[ct] = _classify_tier(c)

    # Find MCU and power components
    mcu_types = [ct for ct, tier in tier_map.items() if tier == _TIER_MCU]
    power_types = [ct for ct, tier in tier_map.items() if tier == _TIER_POWER]

    # Rule 1: All non-MCU components depend on MCU
    for ct in comp_types:
        if ct not in mcu_types:
            graph[ct].update(mcu_types)

    # Rule 2: Non-power, non-MCU depend on power sources
    for ct in comp_types:
        if tier_map.get(ct, _TIER_INTERNAL) > _TIER_POWER:
            graph[ct].update(power_types)

    # Rule 3: External components depend on all internal/panel components
    external_types = [ct for ct, t in tier_map.items() if t == _TIER_EXTERNAL]
    non_external = [ct for ct, t in tier_map.items() if t < _TIER_EXTERNAL]
    for ext in external_types:
        graph[ext].update(non_external)

    # Rule 4: I2C bus components ordered by trunk direction
    i2c_comps = _get_i2c_components(components, wiring)

    # If bus_routes available, use trunk ordering for I2C chain
    if bus_routes:
        for bus in bus_routes:
            if bus.get("bus_type") == "i2c":
                drops = bus.get("drops", [])
                # Order by trunk percentage (earlier on trunk = placed first)
                sorted_drops = sorted(drops, key=lambda d: d.get("from_trunk_pct", 0))
                for i in range(1, len(sorted_drops)):
                    cur = sorted_drops[i].get("to", "")
                    prev = sorted_drops[i - 1].get("to", "")
                    if not cur or not prev:
                        warnings.warn("缺 to 欄位,跳過此依賴邊")
                        continue
                    if cur in graph and prev in comp_types:
                        graph[cur].add(prev)

    return graph


def topological_sort_layers(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Kahn's algorithm: layered topo sort. Raises ValueError on cycle."""
    if not graph:
        return []

    # Build in-degree map and adjacency (reversed: edge from dep -> dependent)
    in_degree: Dict[str, int] = {node: 0 for node in graph}
    # forward_adj: dep -> list of nodes that depend on it
    forward_adj: Dict[str, List[str]] = {node: [] for node in graph}

    for node, deps in graph.items():
        for dep in deps:
            if dep in graph:
                in_degree[node] = in_degree.get(node, 0) + 1
                forward_adj.setdefault(dep, []).append(node)
            # Skip deps not in graph (missing components)

    # Recount in-degree accurately
    for node in graph:
        in_degree[node] = sum(1 for d in graph[node] if d in graph)

    # Start with nodes that have zero in-degree
    queue: deque = deque()
    for node, deg in in_degree.items():
        if deg == 0:
            queue.append(node)

    layers: List[List[str]] = []
    processed = 0

    while queue:
        # All nodes in current queue form one layer
        layer: List[str] = []
        next_queue: deque = deque()

        while queue:
            node = queue.popleft()
            layer.append(node)
            processed += 1

            # Reduce in-degree of dependents
            for dependent in forward_adj.get(node, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)

        layer.sort()  # Deterministic ordering within layer
        layers.append(layer)
        queue = next_queue

    if processed < len(graph):
        # Cycle detected - collect unprocessed nodes for error message
        remaining = [n for n in graph if in_degree.get(n, 0) > 0]
        raise ValueError(
            f"Cycle detected in placement DAG. "
            f"Unresolved nodes: {remaining[:5]}"
        )

    return layers


def compute_placement_order(
    components: List[dict],
    wiring: Optional[dict] = None,
    bus_routes: Optional[List[dict]] = None,
) -> List[List[str]]:
    """High-level API: build DAG and return layered placement order."""
    if not components:
        return []

    graph = build_placement_dag(components, wiring, bus_routes)
    return topological_sort_layers(graph)
