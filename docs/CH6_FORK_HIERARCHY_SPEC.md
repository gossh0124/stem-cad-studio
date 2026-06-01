# CH6 — Fork × Hierarchy Specification

| Field | Value |
|-------|-------|
| Version | 1.0 |
| Date | 2026-05-19 |
| Author | Claude (system-architect) + Gua SU |
| Status | Design (pre-implementation) |
| Depends on | CH3 (Phase IV Plan→Params split, `docs/CH3_HIERARCHICAL_SPEC.md`) |
| Related | DM4 ("重跑此 phase" button), `problem.md` CH6 entry |
| Source | `docs/224_CAD_HLLM_Generating_Execut.pdf` (ACML 2025, Sichuan Univ.) |

---

## 0. TL;DR

CH3 splits Phase IV into Plan → Params → Shape sub-stages. CH6 exploits this
split to give users fine-grained "Fork" branching: changing a layout re-runs
from Plan; changing a dimension re-runs from Params only; tweaking geometry
re-runs Shape only. Each fork creates a child node in a design tree that shares
the parent's bridge snapshot, avoiding redundant re-computation.

---

## 1. Problem Statement

### 1.1 Current limitation: all-or-nothing Phase IV

```
User edits component X dimension
         │
         ▼
PipelineRunner.run(resume_from=4)
         │
         ├─ Plan   (all layout decisions — WASTED if layout unchanged)
         ├─ Params (all dimensional parameters — WASTED if only one dim changed)
         └─ Shape  (build123d + STL export — 5-8s)
```

Every edit, however small, re-runs all of Phase IV. There is no way to say
"keep the layout, just re-solve dimensions for this component."

### 1.2 DM4 context

DM4 ("重跑此 phase" button) triggers `RESUME_PIPELINE { jobId, resumeFrom }`.
Currently `resumeFrom` is an integer Phase number (1–7). CH6 extends this to
support **sub-phase resume** within Phase IV: `resumeFrom: "4:params"` or
`resumeFrom: "4:shape"`.

### 1.3 Fork vs re-run

A plain re-run overwrites results in place. A **fork** preserves the original
design as a sibling branch, so users can compare variants side-by-side. Both
mechanisms share the same sub-phase resume logic; fork simply allocates a new
`job_id` for the branch.

---

## 2. Hierarchical Phase IV Sub-Stages (CH3 basis)

CH3 (`docs/CH3_HIERARCHICAL_SPEC.md §2`) defines three logical layers:

| Sub-stage | Code symbol | Responsibility | Typical latency |
|-----------|-------------|----------------|-----------------|
| **Plan** | `4:plan` | Component layout decisions: which roles, logical_zone, joints, thermal_strategy | ~1.5s (LoRA-B plan generate) |
| **Params** | `4:params` | Dimensional parameters: x/y/rot, enclosure_spec, wire_routes, vent_placements | ~1.5s (LoRA-B params generate) |
| **Shape** | `4:shape` | CAD geometry: build123d → STL + validate_cad_output (CH2 five checks) | ~5-8s |

Fork granularity maps directly to these sub-stages.

---

## 3. Fork Granularity Rules

### 3.1 Change → resume mapping

| User action | Bridge fields affected | Resume from | Rationale |
|-------------|----------------------|-------------|-----------|
| Add / remove component | `components`, `bom` | `4:plan` | Role set changes → layout must be re-decided |
| Swap component role or zone | `bridge.cad_output.ch3_plan.elements[i].logical_zone` | `4:plan` | Spatial topology changes |
| Change enclosure size | `bridge.cad_output.ch3_params.enclosure_spec` | `4:params` | Dimensions change, layout zones remain valid |
| Adjust x/y of one component | `bridge.cad_output.ch3_params.placements[i]` | `4:params` | Plan's logical_zone still valid; only coordinates change |
| Change wall thickness / tol | `bridge.cad_output.ch3_params.enclosure_spec.{wall,tol}` | `4:params` | Pure dimensional delta |
| Vent face or area change | `bridge.cad_output.ch3_params.vent_placements` | `4:params` | No layout change |
| Wire route path change | `bridge.cad_output.ch3_params.wire_routes[i].path` | `4:params` | Routing style only |
| Snap-fit count / joint method | `bridge.cad_output.ch3_plan.joints` | `4:plan` | Joint method is a Plan-level decision |
| Re-run geometry only (no data change) | — | `4:shape` | Force STL regeneration (e.g. after build123d upgrade) |

### 3.2 Classifier helper (proposed)

```python
# services/pipeline/fork_classifier.py  (新增)

def classify_fork(original_bridge: dict, patched_bridge: dict) -> str:
    """Return the earliest sub-stage that must re-run.
    Returns: '4:plan' | '4:params' | '4:shape'
    """
    plan_keys = {"components", "bom"}          # Plan-layer bridge keys
    params_keys = {"ch3_params", "ch3_plan"}   # Params-layer cad_output keys

    # 觸碰 components/bom → Plan 層變動
    for k in plan_keys:
        if original_bridge.get(k) != patched_bridge.get(k):
            return "4:plan"

    orig_out = original_bridge.get("cad_output", {})
    patch_out = patched_bridge.get("cad_output", {})

    # 觸碰 ch3_plan (joints / zone) → Plan 層
    if orig_out.get("ch3_plan") != patch_out.get("ch3_plan"):
        return "4:plan"

    # 觸碰 ch3_params (x/y/enclosure) → Params 層
    if orig_out.get("ch3_params") != patch_out.get("ch3_params"):
        return "4:params"

    # 其餘只重跑 Shape
    return "4:shape"
```

---

## 4. Data Model: Design Tree

### 4.1 Node schema (stored in `services/shared/design_tree_store.py`)

```python
@dataclass
class DesignNode:
    node_id: str          # UUID; root node == original job_id
    parent_id: str | None # None for root
    job_id: str           # Associated PipelineRunner job
    label: str            # User-visible name ("Fork 1 – smaller enclosure")
    fork_point: str       # '4:plan' | '4:params' | '4:shape' | None (root)
    bridge_snapshot: str  # Path to frozen bridge JSON at fork creation
    created_at: float     # Unix timestamp
    children: list[str]   # child node_ids
```

### 4.2 Storage layout

```
data/design_trees/
  {job_id}/
    root.json             ← DesignNode for original run
    {node_id}.json        ← one file per fork node
    snapshots/
      {node_id}_bridge.json  ← bridge frozen at fork point
```

Forks share the snapshot of their **common ancestor** — the bridge state just
before the fork sub-stage. This avoids duplicating Plan output when two forks
only differ in Params.

### 4.3 Snapshot policy

| Fork level | What is frozen in snapshot |
|------------|---------------------------|
| `4:plan` | bridge up to end of Phase III (components, bom, power_budget, wiring, phase3_constraint_check) |
| `4:params` | above + `cad_output.ch3_plan` |
| `4:shape` | above + `cad_output.ch3_params` |

---

## 5. Pipeline Integration

### 5.1 Sub-phase resume extension to PipelineRunner

```python
# services/shared/models.py — extend PhaseID or add SubPhaseID
class SubPhaseID(str, Enum):
    P4_PLAN   = "4:plan"
    P4_PARAMS = "4:params"
    P4_SHAPE  = "4:shape"
```

```python
# services/pipeline_runner.py — PipelineRunner.__init__ extension
def __init__(self, ..., resume_from: int | str = 0):
    ...
    # '4:params' → skip Phase IV Plan sub-stage, start from Params
    self._sub_resume: SubPhaseID | None = None
    if isinstance(resume_from, str) and ":" in resume_from:
        self._sub_resume = SubPhaseID(resume_from)
        self._resume_from = 4   # resume Phase IV, sub-stage filtered inside
```

Phase4Handler already receives `bridge` containing a frozen Plan snapshot when
`_sub_resume == "4:params"` — it skips the LoRA-B plan generate call and
proceeds directly to params generate. When `_sub_resume == "4:shape"` it skips
both LLM calls and goes straight to `build_assembly_two_piece`.

### 5.2 Fork dispatch (API endpoint)

```
POST /api/fork
{
  "parent_job_id": "abc123",
  "label": "Smaller enclosure",
  "patch": {
    "cad_output.ch3_params.enclosure_spec.inner_length": 90
  }
}

Response:
{
  "fork_node_id": "node_xyz",
  "new_job_id": "def456",
  "resume_from": "4:params"   ← computed by classify_fork()
}
```

Server workflow:
1. Load parent bridge from `design_tree_store`
2. Apply `patch` to a copy of the bridge
3. Call `classify_fork(original, patched)` → `resume_from`
4. Snapshot the bridge at the correct fork point
5. Enqueue a new Job with `resume_from = resume_from`
6. Save `DesignNode` linking parent → child

### 5.3 RESUME_PIPELINE dispatch (DM4 re-run button)

DM4 sends:
```json
{ "action": "resume_pipeline", "jobId": "abc123", "resumeFrom": "4:params" }
```

This is a **non-fork re-run** (overwrites existing job, no new node). Handler
calls `make_runner(queue, resume_from="4:params")` directly.

---

## 6. UI Integration

### 6.1 Fork button placement

The Fork button lives in the Phase IV result panel (Engineer stage), next to the
existing "重跑此 Phase" (DM4) button. It opens a side drawer with:

- Node label input field
- Change summary (auto-detected delta from `classify_fork`)
- "Which sub-stage to fork from" radio (auto-selected, user can override)
- Confirm button → POST /api/fork

### 6.2 Design tree panel

A collapsible "Design Variants" panel shows the tree:

```
● Original (root)
  ├─ Fork 1 – smaller enclosure   [4:params]  ✓ done
  │    └─ Fork 3 – change joints  [4:plan]    ⏳ running
  └─ Fork 2 – add vent            [4:params]  ✓ done
```

Clicking a node switches the main view to that node's result. Active (running)
nodes show a spinner.

---

## 7. Non-Goals

- No fork support for Phases I–III or V–VII (out of scope for CH6)
- No automatic merge of two forks (user picks the winner manually)
- No distributed parallel execution of fork branches (sequential queue)
- No UI diff view between two forks (future CH7+ consideration)

---

## 8. Risk & Mitigation

| # | Risk | Prob | Mitigation |
|---|------|------|------------|
| R1 | Snapshot bridge grows large (many forks) | M | Gzip snapshots; purge nodes older than 30 days via cleanup job |
| R2 | `classify_fork` misclassifies → over-runs Plan when only Params changed | M | Whitelist exact bridge key paths per sub-stage; add unit tests with 10 diff scenarios |
| R3 | Phase4Handler ignores `_sub_resume` and always runs full Plan+Params | M | Add explicit `if sub_resume == "4:params": skip_plan = True` guard in phase4_handler + integration test |
| R4 | Design tree diverges from actual job state (node saved but job failed) | L | DesignNode status mirrors JobStatus; tree UI shows node status from job queue |

---

## 9. Milestones

| # | Task | Output |
|---|------|--------|
| M1 | `SubPhaseID` enum + `PipelineRunner` sub-resume logic | `resume_from="4:params"` skips Plan sub-stage end-to-end |
| M2 | `fork_classifier.py` + unit tests (10 diff scenarios) | `classify_fork()` returns correct sub-stage for all cases |
| M3 | `design_tree_store.py` + snapshot persistence | DesignNode CRUD + bridge snapshot save/load |
| M4 | `POST /api/fork` endpoint | Fork creates new job, saves node |
| M5 | Phase4Handler sub-resume guard | `_sub_resume` respected; params/shape-only re-run verified |
| M6 | Frontend: Fork button + Design tree panel | UI integration with Phase IV result panel |

**Pre-condition**: CH3 must be trained and merged (`ch3_source != "solver_fallback"` on ≥80% of runs) before M5 is meaningful.

---

## 10. Change Log

| Ver | Date | Change |
|-----|------|--------|
| 1.0 | 2026-05-19 | Initial draft — Fork × Hierarchy spec for CH6 / DM4 integration |
