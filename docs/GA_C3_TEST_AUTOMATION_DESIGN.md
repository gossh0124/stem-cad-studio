# GA-C3: Test Automation Maintenance Design

**Status**: Living Document  
**Date**: 2026-05-18  
**Scope**: StemAiAgentV2 — pytest suite, CI pipeline, SSOT test generation

---

## 1. Current State

### 1.1 Test Inventory

| Category | Files | Description |
|---|---|---|
| Unit — lib/ | test_registry, test_assembly_solver, test_assembly_solver_v3, test_wiring, test_bus_routing, test_placement_dag, test_schematic_svg, test_module_builder | Core domain logic, no I/O |
| Unit — lib/specs | test_power_ma_coverage, test_enclosure_relation, test_connector_port_derivation, test_voltage_domain_drc, test_thermal_mw, test_thermal_profile, test_thermal_index_autowrite, test_weight_g, test_csp_pin_allocation | SSOT cross-validation |
| Integration — services | test_pipeline_runner, test_gate_logic, test_phase3_handler, test_phase4_handler, test_phase4_e2e, test_adapter_manager, test_pcb_modules | Phase handlers + pipeline dispatcher |
| Training & tools | test_data_generator_b_helpers, test_trainer_messages_branch, test_ensemble_filter, test_firmware_edu, test_validate_cad, test_hl_dsl | Training pipeline hygiene |
| Infrastructure | test_auto_skill_distill, test_session_cleanup, test_prompt_alignment, test_shell, test_shared_models | Dev tooling and schema contracts |

**Total: 35 test files.** Approximate test count: 1461 (as of 2026-05-18).

### 1.2 CI Configuration (`.github/workflows/lint-test.yml`)

The workflow runs two parallel jobs on `ubuntu-latest` / Python 3.11:

- **lint** — `problem_lint.py --strict`, `auto_skill_audit.py --check`, `file_size_lint.py` (non-blocking), `prompt_alignment_check.py --strict`
- **test** — `pytest tests/test_auto_skill_distill.py tests/test_session_cleanup.py tests/test_prompt_alignment.py`

**Gap**: Only 3 of 35 test files run in CI. The remaining 32 files (including all phase handler integration tests and SSOT cross-validations) run locally only.

---

## 2. Test Organization Strategy

### 2.1 Naming Convention

```
tests/test_<module>_<variant>.py
```

- `<module>` mirrors the import path: `lib/registry.py` → `test_registry.py`
- `<variant>` for splits: `test_assembly_solver.py` (v2), `test_assembly_solver_v3.py`
- Coverage targets documented in module docstring (`Coverage targets: 1. ... 2. ...`)

### 2.2 Directory Structure (Target)

```
tests/
  conftest.py              # shared fixtures (Job, bridge, mock_queue)
  unit/
    lib/                   # pure domain tests
    specs/                 # SSOT cross-validation tests
  integration/
    services/              # phase handler + pipeline tests
    training/              # data generator + alignment tests
  infra/                   # tooling, schema, cleanup
```

**Current state**: flat layout. Grouping is logical only (by file prefix). No migration required unless test count exceeds 100 files.

### 2.3 Test Class Convention

Group related cases under a class when testing the same unit:
```python
class TestComponentSpec:           # dataclass behaviour
class TestRegistryCompleteness:    # coverage checks
class TestPowerMaAlignment:        # cross-source drift
```

Standalone `test_*` functions are acceptable for simple path tests.

---

## 3. Fixture Reuse Patterns

### 3.1 Current State: No `conftest.py`

Each test file re-declares `basic_job`, `mock_queue`, and bridge payloads locally. This leads to ~20 duplicate Job/bridge fixtures.

### 3.2 Recommended `conftest.py`

Create `tests/conftest.py` with:

```python
import pytest
from unittest.mock import MagicMock
from services.shared.models import Job

@pytest.fixture
def basic_job():
    return Job(job_id="ci-test-001", project_name="TestProject",
               instruction="make a smart nightlight")

@pytest.fixture
def mock_queue():
    q = MagicMock()
    q.update = MagicMock()
    return q

@pytest.fixture(scope="module")
def minimal_bridge():
    return {
        "project_name": "TestProject",
        "project_category": "Smart_Home",
        "components": [
            {"role": "Brain",    "type": "Arduino-Uno-class",     "qty": 1},
            {"role": "Power",    "type": "USB-5V-class",           "qty": 1},
            {"role": "Control",  "type": "Button-class",           "qty": 1},
            {"role": "Sensor",   "type": "Sensor-PIR-class",       "qty": 1},
            {"role": "Actuator", "type": "Lighting-NeoPixel-class","qty": 1},
        ],
        "enclosure_constraints": {"target_size": "compact", "max_dimension_mm": 150},
        "inventory_mentions": [],
        "_instruction": "make a smart nightlight",
        "bom": [],
        "power_budget": {"ok": True},
    }

@pytest.fixture(scope="session")
def datasheet_json():
    import json, os
    path = os.path.join(os.path.dirname(__file__), "..", "data",
                        "component_datasheet_verified.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

`scope="module"` for bridge (reconstructed per file), `scope="session"` for the 900 KB datasheet JSON (load once per `pytest` run).

---

## 4. SSOT Test Generation Strategy

### 4.1 SSOT Sources

| Source | Path | Downstream Tests |
|---|---|---|
| Component datasheet | `data/component_datasheet_verified.json` | test_registry, test_power_ma_coverage, test_connector_port_derivation, test_thermal_mw, test_weight_g |
| Registry | `lib/registry.py` | test_enclosure_relation, test_voltage_domain_drc, test_csp_pin_allocation |
| Specs | `lib/specs.py` | test_power_ma_coverage (POWER_MA vs helpers.CURRENT_MA drift table) |

### 4.2 Auto-Parametrize from Datasheet

When a new component is added to `component_datasheet_verified.json`, the following tests automatically cover it through dynamic parametrize:

```python
# Pattern used in test_registry.py and test_power_ma_coverage.py
@pytest.mark.parametrize("class_name", list(COMPONENT_REGISTRY.keys()))
def test_registry_entry_has_required_fields(class_name):
    spec = COMPONENT_REGISTRY[class_name]
    assert spec.length_mm > 0
    assert spec.enclosure_relation in ENCLOSURE_RELATIONS
```

**Rule**: SSOT cross-validation tests MUST use `parametrize` driven by the live registry/datasheet — never a hardcoded list of class names.

### 4.3 Known-Drift Table Pattern

When a value mismatch is intentional (different source semantics), document it in a `_KNOWN_DRIFT` dict at module level with `(source_a_value, source_b_value)` tuples. Tests should `pytest.skip` known drift entries and fail on undocumented new drifts. See `test_power_ma_coverage.py:_KNOWN_DRIFT` as reference.

---

## 5. CI Pipeline Optimization

### 5.1 Immediate: Expand CI Test Matrix

Add to `lint-test.yml` `test` job:

```yaml
- name: Run unit tests (lib/)
  run: pytest tests/test_registry.py tests/test_assembly_solver.py
       tests/test_enclosure_relation.py tests/test_power_ma_coverage.py
       tests/test_shared_models.py tests/test_wiring.py -v --tb=short

- name: Run integration tests (services/)
  run: pytest tests/test_pipeline_runner.py tests/test_gate_logic.py
       tests/test_phase3_handler.py tests/test_phase4_handler.py -v --tb=short
```

Tests that require CAD rendering or external GPU (test_phase4_e2e, test_validate_cad) remain local-only with `@pytest.mark.slow`.

### 5.2 Parallelization with pytest-xdist

```yaml
- name: Install test deps
  run: pip install pytest pytest-xdist pyyaml

- name: Run unit tests (parallel)
  run: pytest tests/unit/ -n auto --tb=short
```

Unit tests (no shared state) are safe for `-n auto`. Integration tests with singleton runners should use `-n 1`.

### 5.3 Dependency Caching

Current CI already uses `cache: pip` on `actions/setup-python@v5`. No change needed.

### 5.4 Fail-Fast Strategy

```yaml
# In test job — stop on first failure in integration suite
- run: pytest tests/test_pipeline_runner.py tests/test_gate_logic.py -x --tb=short
```

Use `-x` (fail-fast) for integration tests; omit for unit/SSOT tests to surface all drift at once.

---

## 6. Coverage Tracking

### 6.1 Tools

```yaml
- name: Install coverage
  run: pip install pytest-cov

- name: Run with coverage
  run: pytest tests/ --cov=services --cov=lib --cov-report=term-missing --cov-fail-under=70
```

### 6.2 Coverage Targets by Module

| Module | Target | Notes |
|---|---|---|
| `lib/registry.py` | 90% | SSOT — every field path must be exercised |
| `lib/specs.py` | 85% | All POWER_MA / STALL_MA keys covered |
| `services/pipeline_runner.py` | 80% | Core dispatcher |
| `services/phase_handlers/phase[1-4]_handler.py` | 75% | Happy path + error branches |
| `services/pipeline/gate_logic.py` | 80% | All gate action paths |
| `training/` | 60% | Best-effort; training data generators not critical-path |

### 6.3 Exclusions

Add to `pyproject.toml` or `setup.cfg`:
```ini
[tool:pytest]
addopts = --cov-config=.coveragerc

# .coveragerc
[report]
omit = tests/*, tools/*, services/gateway/*, scripts/*
```

---

## 7. Test Maintenance SOP

### 7.1 When to Add Tests

| Trigger | Action |
|---|---|
| New component added to `component_datasheet_verified.json` | Verify parametrized SSOT tests cover new entry automatically; add targeted test if new field type introduced |
| New phase handler method added | Add unit test in corresponding `test_phase*_handler.py` |
| Bug fix merged | Add regression test that reproduces the original failure |
| New `_KNOWN_DRIFT` entry | Document in drift table with comment linking to issue/PR |

### 7.2 When to Update Tests

| Trigger | Action |
|---|---|
| Refactor renames class/method | Update all imports and fixture usages |
| SSOT value changes (e.g., POWER_MA entry updated) | Remove from `_KNOWN_DRIFT` if drift is resolved; update expected values |
| Phase handler contract changes | Update `basic_bridge` fixture to match new required fields |

### 7.3 When to Remove Tests

- Test covers a deleted feature with no replacement
- Test is superseded by a more comprehensive parametrized version
- Test is permanently xfail with no assigned fix (`@pytest.mark.xfail(strict=False, reason="...")` acceptable only for known infrastructure limits)

### 7.4 File Size Rule

Keep every test file under 500 lines (mirrors project rule). If a test file exceeds 400 lines, split by responsibility (e.g., `test_pipeline_runner.py` → `test_gate_logic.py` split, as done in STR18).

---

## 8. Regression Strategy per Phase Handler

| Phase | Handler | Regression Scope | Test File |
|---|---|---|---|
| Phase 1 | `phase1_handler.py` | LLM output parsing, BOM assembly, role completeness | `test_shared_models.py` + add `test_phase1_handler.py` |
| Phase 2 | (power gate in pipeline) | Power budget calculation, gate payload assembly, swap suggestions | `test_gate_logic.py` |
| Phase 3 | `phase3_handler.py` | GPIO validation (EW1-EW6), interference detection, wiring checks | `test_phase3_handler.py` |
| Phase 4 | `phase4_handler.py` | CAD dispatch, STL output structure, tier routing | `test_phase4_handler.py`, `test_phase4_e2e.py` |

Every phase handler regression test MUST cover: (1) valid bridge → `PhaseResult(status=OK)`, (2) malformed field → `PhaseResult(status=ERROR, error_message!=None)`, (3) boundary edge case specific to the phase.

---

## 9. Open Items

| ID | Issue | Priority |
|---|---|---|
| GA-C3-1 | Add `conftest.py` with shared fixtures | P1 |
| GA-C3-2 | Expand CI `test` job to cover unit + integration (32 files) | P1 |
| GA-C3-3 | Add `test_phase1_handler.py` (no file exists) | P2 |
| GA-C3-4 | Enable `pytest-cov` in CI with 70% floor | P2 |
| GA-C3-5 | Tag Phase 4 CAD tests with `@pytest.mark.slow` for local-only | P3 |
