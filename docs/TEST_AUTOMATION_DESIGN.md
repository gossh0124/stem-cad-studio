# Test Automation Design

**Project**: StemAiAgentV2  
**Date**: 2026-05-19  
**Test count**: ~1461 across 35 files  
**Runner**: pytest (no `pyproject.toml` / `conftest.py` / `pytest.ini` yet)

---

## 1. Test Lifecycle

### Creation

Every test file follows the naming convention:

```
tests/test_{module}[_{variant}].py
```

- `{module}` mirrors the source import path: `lib/registry.py` -> `test_registry.py`
- `{variant}` is optional for splits: `test_assembly_solver.py` (v2) vs `test_assembly_solver_v3.py`
- Each file MUST start with a docstring listing coverage targets (`Coverage targets: 1. ...`)

### Execution

```bash
# Local (use project venv -- system Python 3.14 breaks transformers)
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short

# CI (lint-test.yml) -- currently runs only 3 of 35 files
pytest tests/test_auto_skill_distill.py tests/test_session_cleanup.py tests/test_prompt_alignment.py -v --tb=short
```

### Cleanup

- Test files that create temp directories MUST use `tempfile.mkdtemp()` and `shutil.rmtree()` in teardown (see `test_session_cleanup.py`, `test_phase4_e2e.py`).
- No test artifacts may be committed to git.
- Files generated under `.ai/` during test runs must be cleaned up in the same test.

### Archival

- Superseded test files are deleted, not renamed. Git history preserves the record.
- When a module is removed, its test file is removed in the same commit.

### Fixture Scoping Guidelines

| Scope | Use case | Example |
|---|---|---|
| `function` (default) | Mutable state, mock objects | `mock_queue`, `basic_job` |
| `module` | Immutable config reconstructed per file | `minimal_bridge` payload |
| `session` | Expensive read-only data loaded once | `datasheet_json` (900 KB JSON) |

**Current gap**: No `tests/conftest.py` exists. Each test file redeclares Job, bridge, and queue fixtures locally (~20 duplicates). A shared conftest is tracked as open item GA-C3-1.

---

## 2. Artifact Management

### Current State

Test files manage their own temp directories via `tempfile` + `shutil`. There is no session-scope fixture for centralized tmpdir management.

### Recommended `conftest.py` Fixture

```python
# tests/conftest.py
import pytest, shutil, tempfile
from pathlib import Path

@pytest.fixture(scope="session")
def test_artifacts_dir():
    """Session-wide temp directory. Auto-removed on teardown."""
    d = Path(tempfile.mkdtemp(prefix="stemai_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)

@pytest.fixture
def work_dir(test_artifacts_dir):
    """Per-test subdirectory under session artifacts."""
    d = test_artifacts_dir / f"test_{id(object()):x}"
    d.mkdir(exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)
```

### Git Exclusion

`.gitignore` already covers `__pycache__` and `.pytest_cache`. Temp files created under system temp directories are outside the repo. No additional exclusion needed unless tests write to `tests/` directly (they should not).

---

## 3. CI Tier Classification

### Tier Definitions

| Tier | Label | Time budget | Characteristics | pytest marker |
|---|---|---|---|---|
| **Tier 1** | Unit | < 2 min | Pure logic, no I/O, no network, no subprocess | `@pytest.mark.unit` |
| **Tier 2** | Integration | < 10 min | File I/O, subprocess, local services, mock LLM | `@pytest.mark.integration` |
| **Tier 3** | E2E | < 30 min | Full pipeline, CAD rendering, external APIs | `@pytest.mark.e2e` |

### Current File Classification

**Tier 1 -- Unit** (23 files):
`test_registry`, `test_assembly_solver`, `test_assembly_solver_v3`, `test_wiring`,
`test_bus_routing`, `test_placement_dag`, `test_schematic_svg`, `test_module_builder`,
`test_shared_models`, `test_shell`, `test_hl_dsl`, `test_firmware_edu`,
`test_firmware_reactions`, `test_power_ma_coverage`, `test_enclosure_relation`,
`test_connector_port_derivation`, `test_voltage_domain_drc`, `test_thermal_mw`,
`test_thermal_profile`, `test_thermal_index_autowrite`, `test_weight_g`,
`test_csp_pin_allocation`, `test_ensemble_filter`

**Tier 2 -- Integration** (9 files):
`test_pipeline_runner`, `test_gate_logic`, `test_phase3_handler`,
`test_phase4_handler`, `test_adapter_manager`, `test_pcb_modules`,
`test_data_generator_b_helpers`, `test_trainer_messages_branch`,
`test_auto_skill_distill`

**Tier 3 -- E2E** (3 files):
`test_phase4_e2e`, `test_validate_cad`, `test_session_cleanup`

### CI Mapping

```yaml
# lint-test.yml additions
- name: Tier 1 -- Unit tests
  run: pytest -m unit -v --tb=short -x

- name: Tier 2 -- Integration tests
  run: pytest -m integration -v --tb=short

- name: Tier 3 -- E2E tests (optional, manual trigger only)
  if: github.event_name == 'workflow_dispatch'
  run: pytest -m e2e -v --tb=short
```

---

## 4. pyproject.toml Configuration

No `pyproject.toml` exists yet. Recommended baseline:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: Pure logic tests, no I/O (Tier 1, <2min)",
    "integration: File I/O, subprocess, local services (Tier 2, <10min)",
    "e2e: Full pipeline, CAD rendering, external APIs (Tier 3, <30min)",
    "slow: Tests requiring CAD runtime or GPU (local-only)",
]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
]

[tool.coverage.run]
source = ["lib", "services"]
omit = [
    "tests/*",
    "tools/*",
    "scripts/*",
    "services/gateway/*",
]

[tool.coverage.report]
fail_under = 60
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.",
    "raise NotImplementedError",
]
```

### Key Settings

- **`--strict-markers`**: Prevents typos in marker names from silently passing.
- **`fail_under = 60`**: Conservative floor; increase to 70 once conftest consolidation is done.
- **`source`**: Only measures `lib/` and `services/` -- the production code.

---

## 5. Auto-Classification

### Problem

35 test files have no tier markers. Manually classifying each is tedious and error-prone as new files are added.

### Script-Based Approach

Scan each test file's imports and function bodies to auto-suggest a tier:

```python
# tools/test_tier_classifier.py
"""Scan test files and suggest pytest tier markers."""
import ast, sys
from pathlib import Path

INTEGRATION_MODULES = {
    "subprocess", "tempfile", "shutil", "socket", "http",
    "requests", "httpx", "aiohttp", "urllib.request",
}
E2E_MODULES = {
    "selenium", "playwright", "build123d", "cadquery",
}
E2E_INTERNAL = {
    "services.phase_handlers.phase4_handler",
    "services.pipeline_runner",
}

def classify(filepath: Path) -> str:
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
            imports.add(node.module)
    if imports & E2E_MODULES or imports & E2E_INTERNAL:
        return "e2e"
    if imports & INTEGRATION_MODULES:
        return "integration"
    return "unit"

if __name__ == "__main__":
    for f in sorted(Path("tests").glob("test_*.py")):
        tier = classify(f)
        print(f"  {tier:15s}  {f.name}")
```

### Classification Rules

| Signal | Suggested tier |
|---|---|
| Only `pytest`, `unittest.mock`, project `lib.*` imports | **unit** |
| Imports `subprocess`, `tempfile`, `shutil`, `requests` | **integration** |
| Imports `selenium`, `build123d`, or full pipeline handlers | **e2e** |
| Uses `@pytest.mark.parametrize` with live registry data | **unit** (SSOT cross-validation) |

### Integration with CI

Run the classifier as a pre-commit or CI check to warn when a new test file is added without a tier marker:

```yaml
- name: Check test tier markers
  run: python tools/test_tier_classifier.py --check
```

The `--check` flag exits non-zero if any test file lacks a `@pytest.mark.{unit,integration,e2e}` decorator.

---

## Appendix: Open Items

| ID | Item | Priority |
|---|---|---|
| GA-C3-1 | Create `tests/conftest.py` with shared fixtures | P1 |
| GA-C3-2 | Expand CI test job from 3 -> 35 files | P1 |
| GA-C3-3 | Create `pyproject.toml` with markers + coverage config | P1 |
| GA-C3-4 | Write `tools/test_tier_classifier.py` | P2 |
| GA-C3-5 | Add tier markers to all 35 existing test files | P2 |
| GA-C3-6 | Enable `pytest-cov` in CI with 60% floor | P2 |
| GA-C3-7 | Tag CAD rendering tests with `@pytest.mark.slow` | P3 |
