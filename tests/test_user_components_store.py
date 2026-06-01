"""tests/test_user_components_store.py — UserComponentSpec + CRUD operations.

Covers:
  - services/shared/user_components_store.py: UserComponentSpec validation,
    add_component, get_spec, list_components, remove_component,
    record_usage, promote_candidates

Uses tmp_path for filesystem isolation.

Run: .venv/Scripts/python.exe -m pytest tests/test_user_components_store.py -v
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.shared.user_components_store import (
    UserComponentSpec,
    _USER_ENCLOSURE_RELATIONS,
    add_component, get_spec, list_components, remove_component,
    record_usage, promote_candidates,
    _load_index, _save_index, _read_json, _write_json,
    _USER_COMP_ROOT, _INDEX_PATH,
)


# ── UserComponentSpec dataclass ──────────────────────────────

class TestUserComponentSpec:
    def test_valid_creation(self):
        spec = UserComponentSpec(
            name="BH1750", class_name="User-BH1750-class",
            length_mm=20, width_mm=15, height_mm=8,
            tags=["bus:i2c", "measure:light"],
        )
        assert spec.name == "BH1750"
        assert spec.source == "user"

    def test_invalid_enclosure_relation(self):
        with pytest.raises(ValueError, match="enclosure_relation"):
            UserComponentSpec(
                name="X", class_name="X-class",
                length_mm=1, width_mm=1, height_mm=1,
                enclosure_relation="invalid_value",
            )

    @pytest.mark.parametrize("rel", sorted(_USER_ENCLOSURE_RELATIONS))
    def test_valid_enclosure_relations(self, rel):
        spec = UserComponentSpec(
            name="X", class_name="X-class",
            length_mm=1, width_mm=1, height_mm=1,
            enclosure_relation=rel,
        )
        assert spec.enclosure_relation in _USER_ENCLOSURE_RELATIONS

    def test_external_sets_skip_enclosure_true(self):
        spec = UserComponentSpec(
            name="X", class_name="X-class",
            length_mm=1, width_mm=1, height_mm=1,
            enclosure_relation="external",
        )
        assert spec.skip_enclosure is True

    def test_internal_with_skip_forces_external(self):
        spec = UserComponentSpec(
            name="X", class_name="X-class",
            length_mm=1, width_mm=1, height_mm=1,
            enclosure_relation="internal", skip_enclosure=True,
        )
        assert spec.enclosure_relation == "external"

    def test_internal_without_skip_stays(self):
        spec = UserComponentSpec(
            name="X", class_name="X-class",
            length_mm=1, width_mm=1, height_mm=1,
            enclosure_relation="internal", skip_enclosure=False,
        )
        assert spec.enclosure_relation == "internal"

    def test_defaults(self):
        spec = UserComponentSpec(
            name="X", class_name="X-class",
            length_mm=1, width_mm=1, height_mm=1,
        )
        assert spec.voltage_v == 5.0
        assert spec.current_ma == 50.0
        assert spec.weight_g == 10.0
        assert spec.thermal_mw == 0.0
        assert spec.tags == []
        assert spec.connector_ports == []


# ── CRUD operations (filesystem isolated) ────────────────────

@pytest.fixture
def isolated_store(tmp_path):
    """Patch the store root + index path to use tmp_path."""
    root = tmp_path / "user_components"
    root.mkdir()
    index = root / "_index.json"
    with patch("services.shared.user_components_store._USER_COMP_ROOT", root), \
         patch("services.shared.user_components_store._INDEX_PATH", index):
        yield root, index


def _make_spec(name="TestSensor", class_name="User-TestSensor-class", **kw):
    defaults = dict(
        length_mm=20, width_mm=15, height_mm=8,
        tags=["bus:i2c", "measure:light"],
    )
    defaults.update(kw)
    return UserComponentSpec(name=name, class_name=class_name, **defaults)


class TestAddComponent:
    def test_creates_spec_json(self, isolated_store):
        root, _ = isolated_store
        spec = _make_spec()
        path = add_component(spec)
        assert path.exists()
        assert path.name == "spec.json"

    def test_creates_index_entry(self, isolated_store):
        root, index = isolated_store
        spec = _make_spec()
        add_component(spec)
        idx = _read_json(index)
        assert spec.class_name in idx["components"]
        assert idx["components"][spec.class_name]["name"] == "TestSensor"

    def test_creates_used_in_json(self, isolated_store):
        root, _ = isolated_store
        spec = _make_spec()
        add_component(spec)
        used_path = root / spec.class_name / "used_in.json"
        assert used_path.exists()

    def test_raises_on_missing_name(self, isolated_store):
        with pytest.raises(ValueError):
            add_component(_make_spec(name=""))

    def test_raises_on_missing_tags(self, isolated_store):
        with pytest.raises(ValueError):
            add_component(_make_spec(tags=[]))

    def test_overwrite_existing(self, isolated_store):
        spec1 = _make_spec(name="V1")
        add_component(spec1)
        spec2 = _make_spec(name="V2")
        add_component(spec2)
        retrieved = get_spec(spec2.class_name)
        assert retrieved.name == "V2"


class TestGetSpec:
    def test_returns_spec(self, isolated_store):
        spec = _make_spec()
        add_component(spec)
        result = get_spec(spec.class_name)
        assert result is not None
        assert result.name == spec.name
        assert result.length_mm == spec.length_mm

    def test_returns_none_for_missing(self, isolated_store):
        assert get_spec("nonexistent-class") is None


class TestListComponents:
    def test_empty_initially(self, isolated_store):
        result = list_components()
        assert result == {}

    def test_lists_added(self, isolated_store):
        add_component(_make_spec("A", "User-A-class"))
        add_component(_make_spec("B", "User-B-class"))
        result = list_components()
        assert len(result) == 2
        assert "User-A-class" in result
        assert "User-B-class" in result


class TestRemoveComponent:
    def test_removes_existing(self, isolated_store):
        root, _ = isolated_store
        spec = _make_spec()
        add_component(spec)
        assert remove_component(spec.class_name) is True
        assert not (root / spec.class_name).exists()
        assert spec.class_name not in list_components()

    def test_returns_false_for_missing(self, isolated_store):
        assert remove_component("nonexistent-class") is False


class TestRecordUsage:
    def test_records_usage(self, isolated_store):
        root, _ = isolated_store
        spec = _make_spec()
        add_component(spec)
        record_usage(spec.class_name, "job-1", "Project Alpha")
        used = _read_json(root / spec.class_name / "used_in.json")
        assert len(used) == 1
        assert used[0]["job_id"] == "job-1"

    def test_dedup_same_job(self, isolated_store):
        root, _ = isolated_store
        spec = _make_spec()
        add_component(spec)
        record_usage(spec.class_name, "job-1", "P1")
        record_usage(spec.class_name, "job-1", "P1")
        used = _read_json(root / spec.class_name / "used_in.json")
        assert len(used) == 1

    def test_updates_n_projects(self, isolated_store):
        _, index = isolated_store
        spec = _make_spec()
        add_component(spec)
        record_usage(spec.class_name, "j1", "P1")
        record_usage(spec.class_name, "j2", "P2")
        idx = _read_json(index)
        assert idx["components"][spec.class_name]["n_projects"] == 2


class TestPromoteCandidates:
    def test_empty_when_no_usage(self, isolated_store):
        add_component(_make_spec())
        assert promote_candidates(min_projects=1) == []

    def test_returns_candidates(self, isolated_store):
        spec = _make_spec()
        add_component(spec)
        for i in range(3):
            record_usage(spec.class_name, f"j{i}", f"P{i}")
        result = promote_candidates(min_projects=3)
        assert len(result) == 1
        assert result[0][0] == spec.class_name
        assert result[0][1] == 3

    def test_sorted_descending(self, isolated_store):
        s1 = _make_spec("A", "User-A-class")
        s2 = _make_spec("B", "User-B-class")
        add_component(s1)
        add_component(s2)
        for i in range(5):
            record_usage(s1.class_name, f"j{i}", f"P{i}")
        for i in range(3):
            record_usage(s2.class_name, f"k{i}", f"Q{i}")
        result = promote_candidates(min_projects=3)
        assert result[0][1] >= result[-1][1]
