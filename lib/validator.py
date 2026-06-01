"""validator.py — JSON schema and AdvancedValidator for P1 output validation."""
import json
from typing import Dict, Any, List, Tuple

import jsonschema

from .config import TAXONOMY_CONFIG, ENCLOSURE_DEFAULTS, ENCLOSURE_SIZE_THRESHOLDS


STEAM_JSON_SCHEMA = {
    "type": "object",
    "required": ["project_name", "project_category", "components", "enclosure_constraints", "inventory_mentions"],
    "properties": {
        "project_name":     {"type": "string"},
        "project_category": {"type": "string", "enum": TAXONOMY_CONFIG["project_categories"]},
        "cot_plan": {
            "type": "object",
            "properties": {
                "high_level_plan": {"type": "string"},
                "step_by_step":    {"type": "array", "items": {"type": "string"}},
                "subsystems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["role", "part", "type", "reason"],
                        "properties": {
                            "role":     {"type": "string"},
                            "part":     {"type": "string"},
                            "type":     {"type": "string", "pattern": ".*-class$"},
                            "reason":   {"type": "string", "minLength": 1},
                            "power_mw": {"type": "number", "minimum": 0},
                            "pins":     {"type": "integer", "minimum": 0},
                        }
                    }
                },
                "parameter_hints": {"type": "object"},
                "power_summary": {
                    "type": "object",
                    "properties": {
                        "total_mw":  {"type": "number"},
                        "budget_mw": {"type": "number"},
                    }
                },
                "total_pins": {"type": "integer", "minimum": 0},
            }
        },
        "components": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["role", "type", "qty"],
                "properties": {
                    "role": {"type": "string"},
                    "type": {"type": "string", "pattern": ".*-class$"},
                    "qty":  {"type": "integer", "minimum": 1}
                }
            }
        },
        "user_components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["class_name", "name", "tags"],
                "properties": {
                    "class_name": {"type": "string"},
                    "name":       {"type": "string"},
                    "tags":       {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "enclosure_constraints": {
            "type": "object",
            "required": ["target_size", "wall_thickness_mm", "material"],
            "properties": {
                "target_size":      {"type": "string", "enum": ["compact", "medium", "large"]},
                "max_dimension_mm": {"type": "number", "minimum": 1},
                "wall_thickness_mm":{"type": "number", "minimum": 0.5},
                "material":         {"type": "string"}
            }
        },
        "inventory_mentions": {"type": "array", "maxItems": 0}
    }
}


class AdvancedValidator:
    # 2026-05-08 移除 Wearable / Health alias（Wearables category 已移除，
    # 改由 _infer_default_category 的關鍵字分析回退到 6 個合法 category）
    _CATEGORY_NORMALIZE = {
        'Home_Automation': 'Smart_Home',
        'Home':            'Smart_Home',
        'Audio':           'Smart_Home',
        'Pet_Care':        'Gardening',
        'IoT':             'Smart_Home',
        'Entertainment':   'Interactive_Art',
        'Agriculture':     'Gardening',
        'Garden':          'Gardening',
        'Automation':      'Smart_Home',
        'Robot':           'Robotics',
        'Vehicle':         'Robotics',
        'Music':           'Interactive_Art',
        'Art':             'Interactive_Art',
    }

    @staticmethod
    def normalize_type(t_str: str) -> Tuple[str, bool]:
        if t_str in TAXONOMY_CONFIG["all_valid_types"]:
            return t_str, False
        if t_str in TAXONOMY_CONFIG["alias_mapping"]:
            return TAXONOMY_CONFIG["alias_mapping"][t_str], True
        return t_str, False

    @staticmethod
    def validate(instance: Dict[str, Any], input_text: str = "") -> Tuple[bool, str, List[str], Dict[str, Any]]:
        warnings = []
        stats = {'raw_tax_hits': 0, 'norm_tax_hits': 0, 'unknown_raw': [], 'unknown_norm': []}
        if not isinstance(instance, dict):
            return False, "not_dict", warnings, stats

        # Category 正規化
        raw_cat = instance.get("project_category", "")
        if raw_cat in AdvancedValidator._CATEGORY_NORMALIZE:
            instance["project_category"] = AdvancedValidator._CATEGORY_NORMALIZE[raw_cat]
            warnings.append(f"category_normalized_{raw_cat}_to_{instance['project_category']}")

        # L1: Schema
        try:
            jsonschema.validate(instance=instance, schema=STEAM_JSON_SCHEMA)
        except jsonschema.ValidationError as e:
            return False, f"Schema Error: {e.message}", warnings, stats

        # L2: Core role coverage (Brain / Power / Control 必須存在)
        components = instance.get("components", [])
        present_roles = {c.get("role") for c in components if isinstance(c, dict)}
        for role in TAXONOMY_CONFIG["core_roles"]:
            if role not in present_roles:
                return False, f"missing_core_{role}", warnings, stats

        # L3: Taxonomy validation for all component types
        all_valid = TAXONOMY_CONFIG["all_valid_types"]
        role_to_tax = TAXONOMY_CONFIG["component_taxonomy"]
        for comp in components:
            role = comp.get("role", "")
            ctype = comp.get("type", "")
            if not ctype:
                continue
            canon, converted = AdvancedValidator.normalize_type(ctype)
            if canon not in all_valid:
                warnings.append(f"unknown_type_{ctype}")
                stats['unknown_raw'].append(ctype)
            else:
                valid_for_role = role_to_tax.get(role, [])
                if valid_for_role and canon not in valid_for_role:
                    warnings.append(f"type_{ctype}_not_in_role_{role}")
                stats['norm_tax_hits' if converted else 'raw_tax_hits'] += 1

        return True, "ok", warnings, stats

    def auto_fix(self, data: dict) -> dict:
        """自動修正常見錯誤（bridge JSON 格式）。"""
        if data.get("project_category", "") not in set(TAXONOMY_CONFIG["project_categories"]):
            raw = data.get("project_category", "")
            if raw in self._CATEGORY_NORMALIZE:
                data["project_category"] = self._CATEGORY_NORMALIZE[raw]
            else:
                data["project_category"] = "Education"

        for comp in data.get("components", []):
            t = comp.get("type", "")
            if t and not t.endswith("-class"):
                comp["type"] = t + "-class"

        data["inventory_mentions"] = []

        if "cot_plan" not in data:
            components = data.get("components", [])
            n_comps = sum(c.get("qty", 1) for c in components)
            has_large = any("RaspberryPi" in c.get("type", "") for c in components)
            if has_large or n_comps > ENCLOSURE_SIZE_THRESHOLDS["large_component_count"]:
                enc_size = "large"
            elif n_comps > ENCLOSURE_SIZE_THRESHOLDS["medium_component_count"]:
                enc_size = "medium"
            else:
                enc_size = "compact"
            data["cot_plan"] = {
                "high_level_plan": "Auto-generated fallback plan",
                "step_by_step": ["Select components", "Calculate dimensions", "Generate enclosure"],
                "parameter_hints": {
                    "enclosure_size": enc_size,
                    "material": ENCLOSURE_DEFAULTS["material"],
                    "has_lid": True,
                    "wall_thickness_mm": ENCLOSURE_DEFAULTS["wall_thickness_mm"],
                },
            }
        return data
