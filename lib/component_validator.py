"""component_validator.py — U6/U7/U8 元件數值互證 + 量測驗證 + 熱源估算。

Extracted from component_resolver.py to keep files under 500 lines.
Public API: role_stats(), cross_validate_user_spec(), validate_measurement(),
estimate_thermal_confidence().
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from .registry import COMPONENT_REGISTRY
from .config import TAXONOMY_CONFIG

_log = logging.getLogger(__name__)


_VALIDATE_FIELDS = ["voltage_v", "current_ma", "length_mm", "width_mm",
                    "height_mm", "weight_g", "thermal_mw"]

_FIELD_LABELS = {
    "voltage_v":  ("電壓", "V"),
    "current_ma": ("電流", "mA"),
    "length_mm":  ("長度", "mm"),
    "width_mm":   ("寬度", "mm"),
    "height_mm":  ("高度", "mm"),
    "weight_g":   ("重量", "g"),
    "thermal_mw": ("發熱量", "mW"),
}


def _role_for_type(type_key: str) -> Optional[str]:
    """從 TAXONOMY_CONFIG 反查 type -> role。"""
    ct = TAXONOMY_CONFIG.get("component_taxonomy", {})
    for role, types in ct.items():
        if type_key in types:
            return role
    return None


def role_stats(role: str) -> Dict[str, Dict[str, float]]:
    """計算同 role 全部 REGISTRY 元件的中位數與標準差（public API）。

    Returns
    -------
    dict mapping field name -> {"median", "sigma", "min", "max", "n"}
    Only fields with >= 2 positive values are included.
    """
    ct = TAXONOMY_CONFIG.get("component_taxonomy", {})
    type_keys = ct.get(role, [])

    field_values: Dict[str, List[float]] = {f: [] for f in _VALIDATE_FIELDS}
    for tk in type_keys:
        spec = COMPONENT_REGISTRY.get(tk)
        if spec is None:
            # registry_data import-time cross-check (H21) should have caught this;
            # reaching here means COMPONENT_REGISTRY or TAXONOMY_CONFIG was mutated
            # post-import (e.g. test monkey-patch). Raise loud — no silent stats skip.
            raise RuntimeError(
                f"taxonomy/registry internal inconsistency: type_key {tk!r}"
                f" (role={role!r}) missing from COMPONENT_REGISTRY after"
                " import-time cross-check. Was COMPONENT_REGISTRY mutated?"
            )
        for f in _VALIDATE_FIELDS:
            v = getattr(spec, f, None)
            if v is not None and v > 0:
                field_values[f].append(v)

    stats: Dict[str, Dict[str, float]] = {}
    for f, vals in field_values.items():
        if len(vals) < 2:
            continue
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        median = vals_sorted[n // 2] if n % 2 else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2
        mean = sum(vals) / n
        variance = sum((v - mean) ** 2 for v in vals) / n
        sigma = math.sqrt(variance) if variance > 0 else 0.0
        stats[f] = {
            "median": round(median, 2),
            "sigma": round(sigma, 2),
            "min": round(vals_sorted[0], 2),
            "max": round(vals_sorted[-1], 2),
            "n": n,
        }
    return stats


def cross_validate_user_spec(
    user_spec: Dict[str, Any],
    role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """比對用戶自填元件數值 vs 同 role REGISTRY 中位數 +/- 2 sigma。

    Parameters
    ----------
    user_spec : dict
        用戶元件規格（需含 voltage_v, current_ma, length_mm 等欄位）。
    role : str, optional
        元件 role（Sensor/Actuator/...）。若 None 則嘗試從 tags 推斷。

    Returns
    -------
    list of dict
        每個 dict = {"field", "label", "unit", "user_value", "median",
                     "sigma", "range_min", "range_max", "n_peers", "severity"}
        severity: "warning"（> 2 sigma）或 "info"（> 1 sigma 但 <= 2 sigma）。
    """
    if role is None:
        tags = user_spec.get("tags", [])
        for tag in tags:
            for prefix in ("mcu:", "measure:", "actuate:", "display:", "sound:",
                           "light:", "control:", "power:", "structure:"):
                if tag.startswith(prefix):
                    role_guess = {
                        "mcu:": "Brain", "measure:": "Sensor", "actuate:": "Actuator",
                        "display:": "Display", "sound:": "Sound", "light:": "Lighting",
                        "control:": "Control", "power:": "Power", "structure:": "Chassis",
                    }.get(prefix)
                    if role_guess:
                        role = role_guess
                        break
            if role:
                break

    if not role:
        return []

    stats = role_stats(role)
    if not stats:
        return []

    warnings: List[Dict[str, Any]] = []
    for f in _VALIDATE_FIELDS:
        user_val = user_spec.get(f)
        if user_val is None or user_val <= 0:
            continue
        st = stats.get(f)
        if st is None:
            continue

        median = st["median"]
        sigma = st["sigma"]
        label, unit = _FIELD_LABELS[f]

        if sigma > 0:
            deviation = abs(user_val - median) / sigma
        else:
            deviation = 0.0 if user_val == median else 999.0

        if deviation > 2.0:
            severity = "warning"
        elif deviation > 1.0:
            severity = "info"
        else:
            continue

        warnings.append({
            "field": f,
            "label": label,
            "unit": unit,
            "user_value": round(user_val, 2),
            "median": median,
            "sigma": sigma,
            "range_min": st["min"],
            "range_max": st["max"],
            "n_peers": st["n"],
            "severity": severity,
        })

    return warnings


def validate_measurement(
    measured: Dict[str, float],
    role: str,
) -> List[Dict[str, Any]]:
    """驗證 caliper 量測值是否落在同 role 合理範圍內。

    Parameters
    ----------
    measured : dict
        至少含 length_mm / width_mm / height_mm 其一。
    role : str
        元件 role（Brain/Sensor/Actuator/...）。

    Returns
    -------
    list of dict
        每個 dict = {"field", "label", "unit", "measured", "median",
                     "sigma", "range_min", "range_max", "n_peers", "severity"}
        severity: "error"（> 3 sigma）/ "warning"（> 2 sigma）/ "info"（> 1 sigma）。
        空 list 表示全部合理。
    """
    stats = role_stats(role)
    if not stats:
        return []

    results: List[Dict[str, Any]] = []
    for f in ("length_mm", "width_mm", "height_mm"):
        val = measured.get(f)
        if val is None or val <= 0:
            continue
        st = stats.get(f)
        if st is None:
            continue

        median = st["median"]
        sigma = st["sigma"]
        label, unit = _FIELD_LABELS[f]

        if sigma > 0:
            deviation = abs(val - median) / sigma
        else:
            deviation = 0.0 if val == median else 999.0

        if deviation > 3.0:
            severity = "error"
        elif deviation > 2.0:
            severity = "warning"
        elif deviation > 1.0:
            severity = "info"
        else:
            continue

        results.append({
            "field": f,
            "label": label,
            "unit": unit,
            "measured": round(val, 2),
            "median": median,
            "sigma": sigma,
            "range_min": st["min"],
            "range_max": st["max"],
            "n_peers": st["n"],
            "severity": severity,
        })
    return results


def estimate_thermal_confidence(
    thermal_mw: float,
    role: str,
) -> Dict[str, Any]:
    """評估 V x I x eta 熱估算值相對於同 role 的信心度。

    Returns
    -------
    dict with keys:
        confidence: "high" | "medium" | "low"
        deviation_sigma: float
        median_mw: float
        range_min_mw: float
        range_max_mw: float
        n_peers: int
        needs_user_confirm: bool（low confidence 時為 True）
    如果同 role 統計不足，回傳 {"confidence": "unknown", "needs_user_confirm": True}
    """
    stats = role_stats(role)
    th_stats = stats.get("thermal_mw")
    if th_stats is None:
        return {"confidence": "unknown", "needs_user_confirm": True}

    median = th_stats["median"]
    sigma = th_stats["sigma"]

    if sigma > 0:
        deviation = abs(thermal_mw - median) / sigma
    else:
        deviation = 0.0 if thermal_mw == median else 999.0

    if deviation <= 1.0:
        confidence = "high"
    elif deviation <= 2.0:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "confidence": confidence,
        "deviation_sigma": round(deviation, 2),
        "median_mw": median,
        "range_min_mw": th_stats["min"],
        "range_max_mw": th_stats["max"],
        "n_peers": th_stats["n"],
        "needs_user_confirm": confidence == "low",
    }
