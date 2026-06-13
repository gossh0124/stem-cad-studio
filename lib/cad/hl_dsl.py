"""CH3 Hierarchical DSL — Plan + Params schema + validator + compiler.

純函式，無 build123d / LLM 依賴。
SPEC: docs/CH3_HIERARCHICAL_SPEC.md §3.1 (Plan) / §3.2 (Params) / §3.3 (DSL).

公開 API：
    PLAN_SCHEMA, PARAMS_SCHEMA              — JSON Schema constants
    validate_plan(plan)                     -> (ok, errors)
    validate_params(params, plan)           -> (ok, errors)（含 cross-check）
    compile_to_solver_dict(plan, params, bridge) -> dict
        合 Plan + Params → assembly_solver-compatible dict
        欄位：placements / thermal_field / wire_routes / joints / decisions / vent_placements
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

try:
    import jsonschema
    from jsonschema import Draft202012Validator
    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover
    _HAS_JSONSCHEMA = False


# ── enum constants（與 SPEC §3.1 / §3.2 對齊）────────────────────────────

_ROLES = [
    "Brain", "Power", "Control", "Sensor", "Actuator",
    "Display", "Sound", "Lighting", "Motor", "Mist", "Structural",
]

_ZONES = [
    "top-center", "top-left", "top-right",
    "mid-center", "mid-left", "mid-right",
    "bottom-center", "bottom-left", "bottom-right",
    "bottom-probe",
]

_FACE_OUTS = [
    "side-front", "side-back", "side-left", "side-right",
    "top", "bottom", "face",
]

_LID_METHODS = [
    "snap_fit_4x", "snap_fit_2x",
    "screw_4x_M3", "screw_4x_M2.5",
    "friction_fit", "magnetic_4x",
]

_BASE_METHODS = [
    "screw_boss_4x_M3", "screw_boss_4x_M2.5",
    "adhesive_pad", "belt_clip",
]

_THERMAL_STRATEGIES = [
    "no_vent", "side_vent_passive", "top_vent_passive",
    "bottom_vent_passive", "active_fan",
]

_VENT_PLACEMENTS = [
    "none", "side_lower", "side_upper",
    "top_grid", "bottom_holes", "perimeter",
]

_WIRE_PATHS = [
    "channel_bottom", "channel_side", "channel_isolated",
    "direct", "flex_cable",
]

_FACES = [
    "side-front", "side-back", "side-left", "side-right",
    "top", "bottom",
]


# ── Schema 常數（SPEC §3.1 / §3.2）─────────────────────────────────────

PLAN_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["elements", "assembly_order", "joints", "thermal_strategy"],
    "properties": {
        "elements": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "component_type", "role", "logical_zone"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "component_type": {"type": "string", "minLength": 1},
                    "role": {"enum": _ROLES},
                    "logical_zone": {"enum": _ZONES},
                    "face_out": {"enum": _FACE_OUTS},
                    "reason": {"type": "string", "maxLength": 120},
                },
            },
        },
        "assembly_order": {
            "type": "array",
            "items": {"type": "string"},
        },
        "joints": {
            "type": "object",
            "required": ["lid_method", "base_method", "reason"],
            "properties": {
                "lid_method": {"enum": _LID_METHODS},
                "base_method": {"enum": _BASE_METHODS},
                "reason": {"type": "string"},
            },
        },
        "thermal_strategy": {
            "type": "object",
            "required": ["strategy"],
            "properties": {
                "strategy": {"enum": _THERMAL_STRATEGIES},
                "vent_placement": {"enum": _VENT_PLACEMENTS},
                "heat_sources": {
                    "type": "array",
                    "items": {"type": "object"},
                },
            },
        },
        "environmental": {
            "type": "object",
            "properties": {
                "waterproof": {"type": "boolean"},
                "ip_rating": {"type": "string", "pattern": "^IP[0-9]{2}$"},
                "sealed_zones": {"type": "array", "items": {"type": "string"}},
                "exposed_zones": {"type": "array", "items": {"type": "string"}},
            },
        },
        "placement_rationale": {"type": "string", "maxLength": 200},
    },
}

PARAMS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["enclosure_spec", "placements", "wire_routes"],
    "properties": {
        "enclosure_spec": {
            "type": "object",
            "required": ["inner_length", "inner_width", "inner_height", "wall", "tol"],
            "properties": {
                "inner_length": {"type": "number", "minimum": 20, "maximum": 280},
                "inner_width": {"type": "number", "minimum": 20, "maximum": 280},
                "inner_height": {"type": "number", "minimum": 15, "maximum": 280},
                "wall": {"type": "number", "minimum": 1.5, "maximum": 4.0},
                "tol": {"type": "number", "minimum": 0.1, "maximum": 0.5},
                "fillet_r": {"type": "number", "minimum": 0, "maximum": 10},
            },
        },
        "placements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["element_id", "x", "y", "rot_deg"],
                "properties": {
                    "element_id": {"type": "string"},
                    "x": {"type": "number"},
                    "y": {"type": "number"},
                    "z": {"type": "number"},
                    "rot_deg": {"type": "number", "enum": [0, 90, 180, 270]},
                },
            },
        },
        "wire_routes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from", "to", "path"],
                "properties": {
                    "from": {"type": "string"},
                    "to": {"type": "string"},
                    "path": {"enum": _WIRE_PATHS},
                    "current_ma": {"type": "number"},
                },
            },
        },
        "vent_placements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["face", "area_mm2"],
                "properties": {
                    "face": {"enum": _FACES},
                    "area_mm2": {"type": "number", "minimum": 0},
                },
            },
        },
    },
}


# ── 簡易 fallback validator（jsonschema 缺席時使用）─────────────────────

def _fallback_validate(instance: Any, schema: dict, path: str = "$") -> list[str]:
    """極簡 jsonschema fallback；只覆蓋本 SPEC 用到的關鍵字。"""
    errors: list[str] = []
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(instance, dict):
            errors.append(f"{path}: expected object, got {type(instance).__name__}")
            return errors
        for req in schema.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required key '{req}'")
        for k, sub in (schema.get("properties") or {}).items():
            if k in instance:
                errors.extend(_fallback_validate(instance[k], sub, f"{path}.{k}"))
    elif expected == "array":
        if not isinstance(instance, list):
            errors.append(f"{path}: expected array, got {type(instance).__name__}")
            return errors
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: array len {len(instance)} < minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for i, item in enumerate(instance):
                errors.extend(_fallback_validate(item, item_schema, f"{path}[{i}]"))
    elif expected == "string":
        if not isinstance(instance, str):
            errors.append(f"{path}: expected string, got {type(instance).__name__}")
    elif expected == "number":
        if not isinstance(instance, (int, float)) or isinstance(instance, bool):
            errors.append(f"{path}: expected number")
        else:
            if "minimum" in schema and instance < schema["minimum"]:
                errors.append(f"{path}: {instance} < min {schema['minimum']}")
            if "maximum" in schema and instance > schema["maximum"]:
                errors.append(f"{path}: {instance} > max {schema['maximum']}")
    elif expected == "boolean":
        if not isinstance(instance, bool):
            errors.append(f"{path}: expected boolean")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: '{instance}' not in enum {schema['enum']}")
    return errors


def _validate_against(instance: Any, schema: dict) -> list[str]:
    if _HAS_JSONSCHEMA:
        v = Draft202012Validator(schema)
        return [
            f"{'.'.join(str(p) for p in e.absolute_path) or '$'}: {e.message}"
            for e in v.iter_errors(instance)
        ]
    return _fallback_validate(instance, schema)


# ── 公開 validator API ─────────────────────────────────────────────────

def validate_plan(plan_dict: dict) -> tuple[bool, list[str]]:
    """jsonschema validate Plan；回 (ok, errors)。"""
    if not isinstance(plan_dict, dict):
        return False, ["plan must be a dict"]
    errors = _validate_against(plan_dict, PLAN_SCHEMA)

    # extra invariant：assembly_order 內每個 id 必須在 elements[].id
    if not errors:
        element_ids = {e.get("id") for e in plan_dict.get("elements", [])}
        for i, oid in enumerate(plan_dict.get("assembly_order", [])):
            if oid not in element_ids:
                errors.append(f"assembly_order[{i}]: '{oid}' not in elements[].id")
    return (len(errors) == 0), errors


def validate_params(params_dict: dict, plan_dict: dict) -> tuple[bool, list[str]]:
    """validate Params；含 cross-check（plan.elements[].id ↔ params.placements[].element_id）。"""
    if not isinstance(params_dict, dict):
        return False, ["params must be a dict"]
    errors = _validate_against(params_dict, PARAMS_SCHEMA)

    # cross-check：每個 plan.elements[].id 必須在 params.placements[].element_id 出現
    plan_ids = {e.get("id") for e in (plan_dict or {}).get("elements", [])}
    param_ids = {p.get("element_id") for p in params_dict.get("placements", [])}

    missing_in_params = plan_ids - param_ids
    extra_in_params = param_ids - plan_ids

    for mid in sorted(x for x in missing_in_params if x is not None):
        errors.append(f"cross_check: plan element '{mid}' missing in params.placements")
    for eid in sorted(x for x in extra_in_params if x is not None):
        errors.append(f"cross_check: params placement '{eid}' not declared in plan.elements")

    # bbox guard（SPEC §6.1）：outer = inner + 2*wall ≤ 295（300 留 5mm buffer）
    spec = params_dict.get("enclosure_spec") or {}
    wall = spec.get("wall")
    if isinstance(wall, (int, float)):
        for axis in ("inner_length", "inner_width", "inner_height"):
            inner = spec.get(axis)
            if isinstance(inner, (int, float)):
                outer = inner + 2 * wall
                if outer > 295:
                    errors.append(
                        f"bbox_guard: {axis} outer={outer:.1f} > 295mm (inner={inner}, wall={wall})"
                    )

    return (len(errors) == 0), errors


# ── DSL Compiler（SPEC §3.3）───────────────────────────────────────────

def _lookup_component_dims(component_type: str, bridge: dict) -> tuple[float, float, float]:
    """從 registry 查 L/W/H；找不到 raise ValueError（呼叫端補 elem_id context 後 re-raise）。"""
    try:
        from lib.registry import COMPONENT_REGISTRY  # noqa: WPS433
    except ImportError:
        # registry 為選用相依：缺席時退到 bridge dim hint。其他錯誤不在此吞掉。
        COMPONENT_REGISTRY = None
    if COMPONENT_REGISTRY is not None:
        spec = COMPONENT_REGISTRY.get(component_type)
        if spec is not None:
            return (
                float(getattr(spec, "length_mm", 20.0)),
                float(getattr(spec, "width_mm", 20.0)),
                float(getattr(spec, "height_mm", 10.0)),
            )
    # 二次查源：bridge.components[] 自帶 dim hint
    for comp in (bridge or {}).get("components", []) or []:
        if comp.get("type") == component_type or comp.get("class_name") == component_type:
            def _dim(*keys: str) -> float:
                for key in keys:
                    val = comp.get(key)
                    if val is not None:
                        dim = float(val)
                        if dim <= 0:
                            raise ValueError(
                                f"bridge component {component_type!r} has non-positive "
                                f"dimension {key}={val}"
                            )
                        return dim
                raise ValueError(
                    f"bridge component {component_type!r} missing dimension (tried {keys})"
                )

            return (
                _dim("length_mm", "L"),
                _dim("width_mm", "W"),
                _dim("height_mm", "H"),
            )
    raise ValueError(f"component_type not found in registry or bridge dims: {component_type!r}")


def _make_decision(step: str, principle: str, description: str,
                   formula: str = "", six_e_stage: str = "engineer") -> dict:
    """建一條 assembly_solver-相容的 _Decision dict。"""
    return {
        "step": step,
        "principle": principle,
        "description": description,
        "formula": formula,
        "6e_stage": six_e_stage,
    }


def _total_power_mw(plan: dict) -> float:
    """從 plan.thermal_strategy.heat_sources 加總 mw。"""
    total = 0.0
    for hs in (plan.get("thermal_strategy") or {}).get("heat_sources", []) or []:
        mw = hs.get("mw") or hs.get("power_mw") or 0
        try:
            total += float(mw)
        except (TypeError, ValueError):
            continue
    return total


def compile_to_solver_dict(plan: dict, params: dict, bridge: dict) -> dict:
    """合 Plan + Params 兩段 JSON 為 assembly_solver-compatible dict。

    輸出欄位（與 lib.assembly_solver.solve 對齊）：
        placements / thermal_field / wire_routes / joints / decisions / vent_placements

    失敗（schema 不過或 cross-check fail）raise ValueError。
    """
    ok_plan, plan_errors = validate_plan(plan)
    if not ok_plan:
        raise ValueError(f"Plan schema invalid: {plan_errors}")

    ok_params, params_errors = validate_params(params, plan)
    if not ok_params:
        raise ValueError(f"Params schema invalid or cross-check fail: {params_errors}")

    # element_id → plan element 映射
    elem_by_id: dict[str, dict] = {e["id"]: e for e in plan["elements"]}

    # element_id → placement 映射
    placement_by_id: dict[str, dict] = {
        p["element_id"]: p for p in params.get("placements", [])
    }

    # 1) placements 合併（plan 元數據 + params 物理座標 + registry 尺寸）
    placements: list[dict] = []
    for elem_id in plan.get("assembly_order") or list(elem_by_id.keys()):
        elem = elem_by_id[elem_id]
        place = placement_by_id.get(elem_id, {})
        ctype = elem["component_type"]
        try:
            L, W, H = _lookup_component_dims(ctype, bridge)
        except ValueError as exc:
            raise ValueError(f"[elem_id={elem_id!r}] {exc}") from exc
        placements.append({
            "type": ctype,
            "role": elem["role"],
            "x": round(float(place.get("x", 0.0)), 1),
            "y": round(float(place.get("y", 0.0)), 1),
            "L": L, "W": W, "H": H,
            "zone": elem["logical_zone"],
            "face_out": elem.get("face_out", "top"),
            "rot_deg": float(place.get("rot_deg", 0)),
            "enclosure_relation": "internal",
        })

    # 2) thermal_field（plan + params 合）
    thermal = plan.get("thermal_strategy") or {}
    heat_sources = thermal.get("heat_sources") or []
    vent_placements_raw = params.get("vent_placements") or []
    thermal_field = {
        "heat_sources": list(heat_sources),
        "total_power_mw": _total_power_mw(plan),
        "needs_venting": thermal.get("strategy", "no_vent") != "no_vent",
        "vent_placements": [v.get("face") for v in vent_placements_raw],
        "strategy": thermal.get("strategy", "no_vent"),
        "vent_placement": thermal.get("vent_placement", "none"),
    }

    # 3) wire_routes（params 直出）
    wire_routes = [
        {
            "from": w["from"],
            "to": w["to"],
            "path": w["path"],
            "current_ma": float(w.get("current_ma", 0)),
        }
        for w in params.get("wire_routes", [])
    ]

    # 4) joints（plan 直出）
    joints = dict(plan.get("joints") or {})

    # 5) decisions — 自動產 6 條 6E-tagged（對齊 assembly_solver.solve 步驟）
    rationale = plan.get("placement_rationale", "")
    elements_desc = "; ".join(
        f"{e['id']}({e['role']})→{e['logical_zone']}" for e in plan["elements"]
    )
    n_elements = len(plan["elements"])
    n_routes = len(wire_routes)
    decisions = [
        _make_decision(
            "gravity_sort",
            "重心排序",
            f"plan.assembly_order 排序 {n_elements} 元件；rationale: {rationale}",
            "order = topological(elements by mass)",
            "engineer",
        ),
        _make_decision(
            "thermal_classify",
            "熱源分類",
            f"thermal_strategy={thermal.get('strategy', 'no_vent')}，"
            f"total_power_mw={thermal_field['total_power_mw']:.1f}",
            "needs_venting = (strategy != 'no_vent')",
            "engineer",
        ),
        _make_decision(
            "zone_assign",
            "邏輯區位分配",
            f"plan 指派 zone：{elements_desc}",
            "zone = plan.elements[i].logical_zone",
            "engineer",
        ),
        _make_decision(
            "packing",
            "物理座標 packing",
            f"params 提供 {len(params.get('placements', []))} 個 placements（x/y/rot）",
            "x,y,rot ← params.placements[]",
            "engineer",
        ),
        _make_decision(
            "wire_routing",
            "線路走向",
            f"params 規劃 {n_routes} 條 wire_routes；total_current={sum(w['current_ma'] for w in wire_routes):.0f}mA",
            "path ← params.wire_routes[i].path",
            "engineer",
        ),
        _make_decision(
            "joints_and_vent",
            "接合 + 通風",
            f"lid={joints.get('lid_method', 'snap_fit_4x')}, "
            f"base={joints.get('base_method', 'screw_boss_4x_M3')}, "
            f"vent_faces={thermal_field['vent_placements']}",
            "joints ← plan.joints; vents ← params.vent_placements",
            "engineer",
        ),
    ]

    return {
        "placements": placements,
        "thermal_field": thermal_field,
        "wire_routes": wire_routes,
        "joints": joints,
        "decisions": decisions,
        "vent_placements": list(vent_placements_raw),
        "enclosure_spec": dict(params.get("enclosure_spec") or {}),
        "ch3_source": "lora_b",
    }


__all__ = [
    "PLAN_SCHEMA",
    "PARAMS_SCHEMA",
    "validate_plan",
    "validate_params",
    "compile_to_solver_dict",
]
