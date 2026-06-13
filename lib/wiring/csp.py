"""
wiring_csp.py — CSP (Constraint Satisfaction Problem) pin allocator.

Replaces the FIFO allocator in wiring.py with backtracking + forward checking.
Returns the same dict structure as the FIFO allocator so callers see no change.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass

from lib.pin_maps import _INPUT_ONLY_PINS, _I2C_HW_PINS, label_mcu_pin  # noqa: F401 (re-exported for tests)
from .comp_class_map import instance_base

_log = logging.getLogger(__name__)


@dataclass
class _Var:
    """One assignment variable: (component_short_name, pin_tag, pin_type)."""
    comp: str
    tag: str
    pin_type: str   # "pwm" | "digital" | "analog" | "i2c_sda" | "i2c_scl"

    @property
    def key(self) -> str:
        return f"{self.comp}.{self.tag}"


def _is_output_need(pin_type: str) -> bool:
    """Return True if the pin drives current out (output from MCU's perspective)."""
    return pin_type in ("pwm", "digital")


def _build_domains(brain_key: str, variables: list[_Var],
                   pool: dict) -> dict[str, list]:
    """Build initial domain for every variable.

    Domains are lists of candidate MCU pins.
    I2C SDA/SCL prefer hardware pins but keep others as fallback.
    """
    input_only = _INPUT_ONLY_PINS.get(brain_key, set())
    hw_sda, hw_scl = _I2C_HW_PINS.get(brain_key, (None, None))

    domains: dict[str, list] = {}
    for v in variables:
        if v.pin_type == "i2c_sda":
            # prefer hw SDA; fallback = empty (i2c pins are fixed)
            domains[v.key] = [hw_sda] if hw_sda is not None else []
        elif v.pin_type == "i2c_scl":
            domains[v.key] = [hw_scl] if hw_scl is not None else []
        elif v.pin_type == "pwm":
            # pwm first, then digital as fallback
            candidates = list(pool["pwm"]) + [
                p for p in pool["digital"] if p not in pool["pwm"]
            ]
            # filter input-only if this is an output need
            if _is_output_need(v.pin_type):
                candidates = [p for p in candidates if p not in input_only]
            domains[v.key] = candidates
        elif v.pin_type == "analog":
            domains[v.key] = list(pool["analog"])
        elif v.pin_type == "spi":
            # SPI 腳位從 pool["spi"] dict 取對應 value；fallback 到 digital
            spi_map = pool.get("spi", {})
            pin_val = spi_map.get(v.tag.lower())
            domains[v.key] = [pin_val] if pin_val is not None else list(pool["digital"])
        elif v.pin_type == "uart":
            # UART 腳位從 pool["uart"] dict 取對應 value；fallback 到 digital
            uart_map = pool.get("uart", {})
            pin_val = uart_map.get(v.tag.lower())
            domains[v.key] = [pin_val] if pin_val is not None else list(pool["digital"])
        else:  # digital
            candidates = list(pool["digital"]) + [
                p for p in pool["pwm"] if p not in pool["digital"]
            ]
            if _is_output_need(v.pin_type):
                candidates = [p for p in candidates if p not in input_only]
            domains[v.key] = candidates
    return domains


def _mrv_order(variables: list[_Var], domains: dict[str, list]) -> list[_Var]:
    """Sort variables by Minimum Remaining Values (most constrained first)."""
    return sorted(variables, key=lambda v: len(domains[v.key]))


def _forward_check(
    var: _Var, assigned_pin, remaining: list[_Var],
    domains: dict[str, list], brain_key: str
) -> bool:
    """Remove `assigned_pin` from domains of unassigned variables.

    Rules:
    - I2C vars (i2c_sda / i2c_scl) share the same hw pin across ALL I2C devices,
      so we never prune the I2C hw pin from other I2C-type domains.
    - For non-I2C vars, uniqueness is enforced: prune `assigned_pin` from every
      other non-I2C domain (and from any I2C domain only if assigned_pin is NOT
      the dedicated hw I2C pin — which can happen on platforms like ESP32 where
      GPIO 21/22 appear in the digital pool).
    Returns False if any domain becomes empty (dead end → trigger backtrack).
    """
    is_i2c_var = var.pin_type in ("i2c_sda", "i2c_scl")
    hw_sda, hw_scl = _I2C_HW_PINS.get(brain_key, (None, None))
    hw_i2c_pins = {hw_sda, hw_scl} - {None}

    for other in remaining:
        other_is_i2c = other.pin_type in ("i2c_sda", "i2c_scl")

        # I2C devices share the same hw SDA/SCL — don't prune those pins
        # from other I2C domains.
        if is_i2c_var and other_is_i2c:
            continue

        # If the assigned pin is a dedicated hw I2C pin, don't evict it from
        # other I2C domains (they need it too).
        if other_is_i2c and assigned_pin in hw_i2c_pins:
            continue

        key = other.key
        if assigned_pin in domains[key]:
            domains[key] = [p for p in domains[key] if p != assigned_pin]
            if not domains[key]:
                return False   # forward-check failure → backtrack
    return True


def _max_bipartite_matching(adj: dict[str, list]) -> dict:
    """Kuhn's augmenting-path maximum bipartite matching (pure stdlib).

    `adj` maps each variable key -> list of candidate pins (its ACTUAL domain).
    Returns {pin: var_key} for matched pins. |result| == size of max matching.
    Complexity O(V * E); V = #vars, E = total domain entries — polynomial.
    """
    match_pin_to_var: dict = {}   # pin -> var_key

    def _augment(var_key: str, seen: set) -> bool:
        for pin in adj[var_key]:
            if pin in seen:
                continue
            seen.add(pin)
            holder = match_pin_to_var.get(pin)
            if holder is None or _augment(holder, seen):
                match_pin_to_var[pin] = var_key
                return True
        return False

    for var_key in adj:
        _augment(var_key, set())
    return match_pin_to_var


# Load-bearing bound: caps explored search-tree nodes so an infeasibility the
# matching precheck cannot see (e.g. the I2C-shared-pin eviction interaction in
# _forward_check) can never spin forever. Generous vs. real designs (<~30 vars,
# MRV + forward-checking prune); worst observed infeasible case fails in ~1.2s.
_MAX_BACKTRACK_NODES = 200_000


def _backtrack(
    idx: int, ordered: list[_Var],
    domains: dict[str, list],
    assignment: dict[str, object],
    brain_key: str,
    node_budget: list[int],
) -> bool:
    """Recursive backtracking search (with a node-count safety bound).

    Returns True if a complete consistent assignment was found
    (results are in `assignment`). Returns False on dead-end OR if the
    node budget is exhausted (hard guard against runaway search).
    """
    node_budget[0] -= 1
    if node_budget[0] <= 0:
        return False   # safety bound hit → treat as no solution → conflict

    if idx == len(ordered):
        return True   # all variables assigned

    var = ordered[idx]
    remaining = ordered[idx + 1:]

    for candidate in domains[var.key]:
        # Consistency check: uniqueness for non-I2C pins
        if var.pin_type not in ("i2c_sda", "i2c_scl"):
            if candidate in assignment.values():
                continue

        assignment[var.key] = candidate

        # Forward checking: snapshot domains, prune, recurse
        saved = {k: list(v) for k, v in domains.items()}
        ok = _forward_check(var, candidate, remaining, domains, brain_key)
        if ok and _backtrack(idx + 1, ordered, domains, assignment,
                             brain_key, node_budget):
            return True

        # Undo
        del assignment[var.key]
        for k, v in saved.items():
            domains[k] = v

    return False   # no candidate worked → backtrack


def csp_allocate(brain_key: str, comps: list[str],
                 pool: dict, comp_pin_needs: dict) -> tuple[dict, dict, list[str]]:
    """CSP pin allocation with backtracking + forward checking.

    Args:
        brain_key:      Normalized brain key ("Arduino" / "ESP32" / …)
        comps:          List of normalized component short names
        pool:           Working copy of PIN_POOLS[brain_key] (lists, not tuples)
        comp_pin_needs: COMP_PIN_NEEDS dict

    Returns:
        (allocation, pin_labels, conflicts)
        - allocation  : {comp: {tag: mcu_pin}}
        - pin_labels  : {comp: "TAG=pin / …"}
        - conflicts   : list of human-readable conflict strings (empty = success)
    """
    # ── 1. Build variables ──────────────────────────────────────
    variables: list[_Var] = []
    for comp in comps:
        # class-level pin-needs lookup 去多實例尾綴；_Var.comp 保留完整實例名(如 Servo~2)
        # 以產生獨立變數 → 每實例配到不同腳。
        needs = comp_pin_needs.get(instance_base(comp))
        if not needs:
            continue
        for n in needs:
            pin_type = n.type
            if pin_type == "i2c":
                pin_type = "i2c_sda" if n.tag in ("SDA", "DATA") else "i2c_scl"
            variables.append(_Var(comp=comp, tag=n.tag, pin_type=pin_type))

    if not variables:
        return {}, {}, []

    # ── 2. Build domains ────────────────────────────────────────
    domains = _build_domains(brain_key, variables, pool)

    # ── 3. MRV ordering ────────────────────────────────────────
    ordered = _mrv_order(variables, domains)

    # ── 4. Check feasibility before search ─────────────────────
    # 4a. Local: any variable with an empty domain is unsatisfiable on its own.
    empty_vars = [v.key for v in ordered if not domains[v.key]]
    if empty_vars:
        conflicts = [
            f"No valid pins for: {', '.join(empty_vars)} on {brain_key}"
        ]
        return {}, {}, conflicts

    # 4b. Global pin-budget (Hall's condition via max bipartite matching).
    # Non-I2C vars each need a UNIQUE pin; I2C sda/scl vars share their fixed hw
    # pin across all devices, impose no uniqueness demand, and are excluded.
    # If the max matching between non-I2C vars and their ACTUAL candidate pins
    # is smaller than the number of non-I2C vars, no injective (collision-free)
    # assignment exists — the design is pin-infeasible. This is exact (Hall's
    # theorem) for the uniqueness constraint and uses the same domains the
    # backtracker uses, so it never rejects a design the backtracker would solve.
    unique_vars = [v for v in ordered
                   if v.pin_type not in ("i2c_sda", "i2c_scl")]
    if unique_vars:
        adj = {v.key: domains[v.key] for v in unique_vars}
        matching = _max_bipartite_matching(adj)
        if len(matching) < len(unique_vars):
            matched_vars = set(matching.values())
            unmatched = [v for v in unique_vars if v.key not in matched_vars]
            # Report the SATURATED resource group, not the global union: count
            # only the vars that compete for the over-subscribed pins (those
            # sharing a candidate with an unmatched var) against the distinct
            # pins in exactly that group. Reporting the global union would mix
            # unrelated pools (e.g. digital/pwm + analog) and give a misleading
            # "N needed, M available" with N < M while still rejecting.
            short_pins = {p for v in unmatched for p in domains[v.key]}
            competing = [v for v in unique_vars
                         if short_pins.intersection(domains[v.key])]
            need = len(competing)
            have = len({p for v in competing for p in domains[v.key]})
            unmatched_keys = sorted(v.key for v in unmatched)
            conflicts = [
                f"Not enough unique pins on {brain_key}: "
                f"{need} pins needed, only {have} available "
                f"(unsatisfiable: {', '.join(unmatched_keys)})"
            ]
            return {}, {}, conflicts

    # ── 5. Backtracking search (bounded) ────────────────────────
    assignment: dict[str, object] = {}
    node_budget = [_MAX_BACKTRACK_NODES]
    success = _backtrack(0, ordered, domains, assignment, brain_key, node_budget)

    if not success:
        # Build a human-readable conflict message
        unmet_by_type: dict[str, list[str]] = {}
        for v in variables:
            if v.key not in assignment:
                unmet_by_type.setdefault(v.pin_type, []).append(f"{v.comp}.{v.tag}")
        parts = [
            f"Not enough {pt} pins for: {', '.join(vs)}"
            for pt, vs in unmet_by_type.items()
        ]
        return {}, {}, parts or [f"CSP found no valid allocation for {brain_key}"]

    # ── 6. Pack results into allocate_pins return format ────────
    allocation: dict[str, dict[str, object]] = {}
    pin_labels: dict[str, str] = {}

    for comp in comps:
        needs = comp_pin_needs.get(instance_base(comp))
        if not needs:
            continue
        pins: dict[str, object] = {}
        parts: list[str] = []
        for n in needs:
            v_type = n.type
            if v_type == "i2c":
                v_type = "i2c_sda" if n.tag in ("SDA", "DATA") else "i2c_scl"
            key = f"{comp}.{n.tag}"
            mcu_pin = assignment.get(key, "?")
            pins[n.tag] = mcu_pin
            parts.append(f"{n.tag}={label_mcu_pin(brain_key, mcu_pin)}")
        allocation[comp] = pins
        pin_labels[comp] = " / ".join(parts)

    return allocation, pin_labels, []
