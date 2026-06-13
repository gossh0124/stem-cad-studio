"""Tests for lib/config.py — global configuration and taxonomy."""
from __future__ import annotations

import pytest

from lib.config import (
    MODEL_CONFIG,
    ENCLOSURE_DEFAULTS,
    ENCLOSURE_SIZE_CAPS,
    ENCLOSURE_SIZE_THRESHOLDS,
    AREA_COMPACT_MAX_MM2,
    AREA_MEDIUM_MAX_MM2,
    TAXONOMY_CONFIG,
    EDUCATIONAL_RATIONALE_TEMPLATES,
    ASSEMBLY_V3,
    CAD_VALIDATION,
)


class TestModelConfig:
    """MODEL_CONFIG has required fields."""

    def test_has_base_model(self):
        assert "base_model_4bit" in MODEL_CONFIG
        assert "base_model_full" in MODEL_CONFIG

    def test_max_seq_len(self):
        assert MODEL_CONFIG["max_seq_len"] == 2048

    def test_lora_params(self):
        assert MODEL_CONFIG["lora_r"] == 16
        assert MODEL_CONFIG["lora_alpha"] == 32

    def test_target_modules(self):
        modules = MODEL_CONFIG["target_modules"]
        assert "q_proj" in modules
        assert "v_proj" in modules
        assert len(modules) == 7


class TestEnclosureDefaults:
    """ENCLOSURE_DEFAULTS has valid mechanical values."""

    def test_wall_thickness(self):
        assert 1.0 <= ENCLOSURE_DEFAULTS["wall_thickness_mm"] <= 5.0

    def test_max_dimension(self):
        assert ENCLOSURE_DEFAULTS["max_dimension_mm"] == 150

    def test_material(self):
        assert ENCLOSURE_DEFAULTS["material"] == "PLA"


class TestEnclosureSizeCaps:
    """ENCLOSURE_SIZE_CAPS ordered correctly."""

    def test_ordered(self):
        assert ENCLOSURE_SIZE_CAPS["compact"] < ENCLOSURE_SIZE_CAPS["medium"]
        assert ENCLOSURE_SIZE_CAPS["medium"] < ENCLOSURE_SIZE_CAPS["large"]

    def test_reasonable_range(self):
        for size, val in ENCLOSURE_SIZE_CAPS.items():
            assert 50 <= val <= 500, f"{size} cap {val} out of range"


class TestAreaThresholds:
    """Area thresholds for enclosure sizing."""

    def test_compact_less_than_medium(self):
        assert AREA_COMPACT_MAX_MM2 < AREA_MEDIUM_MAX_MM2

    def test_positive(self):
        assert AREA_COMPACT_MAX_MM2 > 0
        assert AREA_MEDIUM_MAX_MM2 > 0


class TestTaxonomyConfig:
    """TAXONOMY_CONFIG structure and content."""

    def test_core_roles(self):
        assert "Brain" in TAXONOMY_CONFIG["core_roles"]
        assert "Power" in TAXONOMY_CONFIG["core_roles"]
        assert "Control" in TAXONOMY_CONFIG["core_roles"]

    def test_aux_roles(self):
        aux = TAXONOMY_CONFIG["aux_roles"]
        for role in ("Sensor", "Actuator", "Display", "Sound", "Lighting"):
            assert role in aux

    def test_six_categories(self):
        cats = TAXONOMY_CONFIG["project_categories"]
        assert len(cats) == 6
        assert "Smart_Home" in cats
        assert "Gardening" in cats

    def test_component_taxonomy_covers_roles(self):
        taxonomy = TAXONOMY_CONFIG["component_taxonomy"]
        for role in TAXONOMY_CONFIG["core_roles"] + TAXONOMY_CONFIG["aux_roles"]:
            assert role in taxonomy, f"Role {role} missing from taxonomy"

    def test_all_types_end_with_class(self):
        for role, types in TAXONOMY_CONFIG["component_taxonomy"].items():
            for t in types:
                assert t.endswith("-class"), f"{role}/{t} missing -class"

    def test_all_valid_types_set(self):
        assert "all_valid_types" in TAXONOMY_CONFIG
        assert isinstance(TAXONOMY_CONFIG["all_valid_types"], set)
        assert len(TAXONOMY_CONFIG["all_valid_types"]) > 30

    def test_gen_mapping_covers_categories(self):
        gen = TAXONOMY_CONFIG["gen_mapping"]
        for cat in TAXONOMY_CONFIG["project_categories"]:
            assert cat in gen, f"Category {cat} missing from gen_mapping"

    def test_gen_mapping_tuples(self):
        for cat, items in TAXONOMY_CONFIG["gen_mapping"].items():
            for item in items:
                assert len(item) == 2, f"{cat} item not a 2-tuple"
                assert isinstance(item[0], str)  # Chinese name
                assert isinstance(item[1], str)  # English slug


class TestEducationalRationale:
    """EDUCATIONAL_RATIONALE_TEMPLATES covers all taxonomy types."""

    def test_non_empty(self):
        assert len(EDUCATIONAL_RATIONALE_TEMPLATES) > 20

    def test_covers_all_brain_types(self):
        brains = TAXONOMY_CONFIG["component_taxonomy"]["Brain"]
        for b in brains:
            assert b in EDUCATIONAL_RATIONALE_TEMPLATES, f"Brain {b} missing rationale"

    def test_values_are_chinese(self):
        for key, val in EDUCATIONAL_RATIONALE_TEMPLATES.items():
            assert len(val) > 5, f"{key} rationale too short"


class TestAssemblyV3:
    """ASSEMBLY_V3 constants."""

    def test_grid_res(self):
        assert ASSEMBLY_V3["GRID_RES"] == 3

    def test_clearance_positive(self):
        assert ASSEMBLY_V3["CLEARANCE"] > 0

    def test_vent_threshold(self):
        assert ASSEMBLY_V3["VENT_THRESHOLD_MW"] == 1500


class TestCadValidation:
    """CAD_VALIDATION limits."""

    def test_bbox_limit(self):
        assert CAD_VALIDATION["BBOX_LIMIT_MM"] == 300.0

    def test_min_wall(self):
        assert CAD_VALIDATION["MIN_WALL_MM"] == 1.5
