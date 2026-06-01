# ER2 v3 — `host_structure` Dict Schema Specification

> **Status**: Draft — 2026-05-19  
> **Supersedes**: v2 placeholder string `"external_body"` in `_to_embedded_ref()`  
> **Tracking**: `problem.md` — ER2-v3 upgrade

---

## 1. Problem Statement

### 1.1 What v2 Provides

The ER (Enclosure Relation) v2 system sorts components into five buckets:

| Bucket | Placement rule |
|---|---|
| `internal` | Packed inside main shell |
| `breadboard` | On breadboard inside shell; no individual shell |
| `panel` | Panel-mount cutout on shell face |
| `external` | Fully outside; only a wire hole on shell wall |
| `embedded` | Sunk into a structural host body (tank, chassis, wearable) |

### 1.2 What v2 Lacks

The `embedded` bucket carries a **hardcoded placeholder** throughout the stack:

```python
# lib/assembly_solver/__init__.py  line 168
"host_structure": "external_body",   # ← 無幾何資訊，solver 無法定位
```

```jsx
// v6/views-engineer-assembly.jsx  line 471
{r.host_structure || 'external_body'}  // ← 前端只顯示字串
```

`ComponentSpec` has **no `host_structure` field at all** — the string is injected at
serialization time in `_to_embedded_ref()`, invisible to the registry.

**Consequences:**

1. `assembly_solver` places every embedded component at `(inner_l/2, inner_w/2)`,
   ignoring cavity geometry — coordinates are meaningless for components mounted inside
   a water tank or chassis.
2. Wire entry point defaults to `face_out="bottom"` regardless of which face the tank
   actually exposes.
3. `Mist-Ultrasonic-class` and `Mist-Atomizer-class` are forced to `enclosure_relation='panel'`
   as a v2 compromise, generating incorrect shell cutouts (mist discs belong submerged, not
   panel-mounted).
4. No downstream consumer (3D solver, CAD generator, front-end renderer) can derive a
   physical position or entry geometry from `"external_body"`.

---

## 2. Schema Design

### 2.1 `host_structure` Dict

```python
host_structure: dict = {
    # 主體種類 — 決定 3D 幾何模板
    "kind": Literal["water_tank", "chassis", "wearable_body", "external_body"],

    # 宿主體外部尺寸（元件沉入的容積）
    "dimensions": {
        "length_mm": float,
        "width_mm":  float,
        "height_mm": float,
    },

    # 元件進入宿主體的入口面（cavity 頂面 / 側面 / 底面）
    "entry_port": {
        "face": Literal["top", "bottom", "left", "right", "front", "back"],
        "u": float,   # 歸一化座標 0.0–1.0（沿 face 長邊）
        "v": float,   # 歸一化座標 0.0–1.0（沿 face 短邊）
    },

    # 腔體幾何（元件真正沉入的空間）
    "cavity": {
        "depth_mm":  float,   # 深度（垂直於 entry_port.face）
        "diam_mm":   float | None,   # 圓形腔體直徑；None → 矩形
        "length_mm": float | None,   # 矩形腔體長（若 diam_mm is None）
        "width_mm":  float | None,   # 矩形腔體寬
    },

    # 走線出口（電線離開宿主體進入主殼的位置）
    "wire_entry": {
        "face": Literal["top", "bottom", "left", "right", "front", "back"],
        "u": float,
        "v": float,
        "hole_diam_mm": float,   # 走線孔直徑
    },
}
```

### 2.2 Canonical Example — Mist-Ultrasonic in Water Tank

```python
host_structure = {
    "kind": "water_tank",
    "dimensions": {"length_mm": 120.0, "width_mm": 80.0, "height_mm": 60.0},
    "entry_port": {
        "face": "top",
        "u": 0.5,   # 水箱頂面正中央
        "v": 0.5,
    },
    "cavity": {
        "depth_mm":  20.0,
        "diam_mm":   28.0,   # 圓形槽，匹配 disc 直徑 25mm + 1.5mm 公差
        "length_mm": None,
        "width_mm":  None,
    },
    "wire_entry": {
        "face": "back",
        "u": 0.9,
        "v": 0.5,
        "hole_diam_mm": 8.0,
    },
}
```

### 2.3 Backward Compatibility Rule

If `host_structure` is a plain `str` (v2 legacy), treat it as:

```python
{"kind": host_structure, "dimensions": {}, "entry_port": {}, "cavity": {}, "wire_entry": {}}
```

Both `ComponentSpec.__post_init__` and the solver must accept string values without error.

---

## 3. Changes in `lib/registry/component_spec.py`

### 3.1 Add `host_structure` to `ComponentSpec`

```python
from typing import Optional, Union

@dataclass
class ComponentSpec:
    # … existing fields unchanged …

    # v3 new field — only meaningful when enclosure_relation == "embedded"
    # 向後相容：接受 str（v2）或 dict（v3）
    host_structure: Optional[Union[str, dict]] = None

    def __post_init__(self):
        # … existing enclosure_relation validation unchanged …

        # v3: validate host_structure when embedded
        if self.enclosure_relation == "embedded" and self.host_structure is None:
            # Default to legacy placeholder; warn for dev visibility
            import warnings
            warnings.warn(
                f"{self.class_name}: embedded component has no host_structure; "
                "defaulting to 'external_body'. Upgrade to v3 dict schema.",
                stacklevel=2,
            )
            object.__setattr__(self, "host_structure", "external_body")
```

### 3.2 Update `to_dict()`

```python
def to_dict(self) -> dict:
    d = { … }   # existing keys unchanged
    if self.host_structure is not None:
        d["host_structure"] = self.host_structure
    return d
```

### 3.3 Registry Data Updates (`registry_data.py`)

Upgrade affected entries from `enclosure_relation='panel'` to `embedded` + v3 dict:

```python
'Mist-Ultrasonic-class': ComponentSpec(
    …,
    enclosure_relation='embedded',
    host_structure={
        "kind": "water_tank",
        "dimensions": {"length_mm": 120.0, "width_mm": 80.0, "height_mm": 60.0},
        "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
        "cavity": {"depth_mm": 20.0, "diam_mm": 28.0, "length_mm": None, "width_mm": None},
        "wire_entry": {"face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 8.0},
    },
),
'Mist-Atomizer-class': ComponentSpec(
    …,
    enclosure_relation='embedded',
    host_structure={
        "kind": "water_tank",
        "dimensions": {"length_mm": 80.0, "width_mm": 60.0, "height_mm": 40.0},
        "entry_port": {"face": "top", "u": 0.5, "v": 0.5},
        "cavity": {"depth_mm": 15.0, "diam_mm": 23.0, "length_mm": None, "width_mm": None},
        "wire_entry": {"face": "back", "u": 0.9, "v": 0.5, "hole_diam_mm": 6.0},
    },
),
```

---

## 4. Changes in `lib/assembly_solver/`

### 4.1 Extend `_Comp` (`_types.py`)

```python
@dataclass
class _Comp:
    # … existing fields …
    host_structure: Any = None   # str or dict; populated from ComponentSpec
```

Populate in `_build_comp_list()`:

```python
out.append(_Comp(
    …,
    host_structure=getattr(spec, "host_structure", None),
))
```

### 4.2 Step 5b — Embedded Placement Logic (`__init__.py`)

Replace the current placeholder loop (lines 100–104) with geometry-aware placement:

```python
for c in embedded_comps:
    hs = c.host_structure
    if isinstance(hs, dict) and hs.get("entry_port"):
        ep = hs["entry_port"]
        dims = hs.get("dimensions", {})
        host_l = dims.get("length_mm", inner_l)
        host_w = dims.get("width_mm", inner_w)
        # u/v → absolute mm on host face
        c.x = round(ep.get("u", 0.5) * host_l, 1)
        c.y = round(ep.get("v", 0.5) * host_w, 1)
        c.face_out = ep.get("face", "top")
        c.zone = f"embedded-{hs.get('kind', 'host')}"
    else:
        # v2 fallback — legacy string or missing host_structure
        c.x = max(0.0, inner_l / 2 - c.L / 2)
        c.y = max(0.0, inner_w / 2 - c.W / 2)
        c.zone = "embedded-host"
        c.face_out = "bottom"
```

### 4.3 Update `_to_embedded_ref()`

```python
def _to_embedded_ref(c: _Comp) -> dict:
    hs = c.host_structure
    ref = {
        "type": c.type, "role": c.role,
        "host_structure": hs if hs else "external_body",
        "thermal_mw": c.thermal_mw,
        "enclosure_relation": "embedded",
        "x": c.x, "y": c.y,
        "face_out": c.face_out,
        "zone": c.zone,
    }
    # v3: expose wire_entry for downstream CAD
    if isinstance(hs, dict) and hs.get("wire_entry"):
        ref["wire_entry"] = hs["wire_entry"]
    return ref
```

### 4.4 Validation Helper

Add to `_types.py` or a new `embedded_validator.py`:

```python
_HOST_KINDS = {"water_tank", "chassis", "wearable_body", "external_body"}
_FACES = {"top", "bottom", "left", "right", "front", "back"}

def validate_host_structure(hs: dict, class_name: str = "") -> None:
    """Raise ValueError on malformed v3 host_structure dict."""
    if hs.get("kind") not in _HOST_KINDS:
        raise ValueError(f"{class_name}: host_structure.kind must be one of {_HOST_KINDS}")
    ep = hs.get("entry_port", {})
    if ep.get("face") not in _FACES:
        raise ValueError(f"{class_name}: entry_port.face must be one of {_FACES}")
    for key in ("u", "v"):
        val = ep.get(key, 0.0)
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"{class_name}: entry_port.{key}={val} out of [0,1]")
```

---

## 5. Frontend Changes in `v6/views-engineer-assembly.jsx`

### 5.1 Current Rendering (line 466–474)

The current `embeddedRefs.map()` block shows only `r.host_structure` as a plain string.

### 5.2 v3 Rendering

Replace the embedded ref row to surface geometry details when available:

```jsx
{embeddedRefs.map((r, i) => {
  const hs = r.host_structure;
  const isV3 = typeof hs === 'object' && hs !== null;
  const label = isV3 ? hs.kind : (hs || 'external_body');
  const epLabel = isV3 && hs.entry_port
    ? `${hs.entry_port.face} (u=${hs.entry_port.u}, v=${hs.entry_port.v})`
    : null;
  const wireLabel = isV3 && hs.wire_entry
    ? `wire→${hs.wire_entry.face} ⌀${hs.wire_entry.hole_diam_mm}mm`
    : null;
  return (
    <div key={`emb-${i}`} style={{
      padding: '4px 8px',
      background: 'rgba(153,136,221,0.08)',
      borderLeft: '2px solid #9988dd',
      borderRadius: 2,
    }}>
      {/* 沉入宿主種類 */}
      <span style={{ color: '#9988dd', fontWeight: 600 }}>embedded</span>
      <span style={{ marginLeft: 6, color: 'var(--text-primary)' }}>{shortLabel(r.type)}</span>
      <span style={{ marginLeft: 6, color: 'var(--text-tertiary)' }}>
        ↳ <code style={{ fontFamily: 'var(--font-mono)' }}>{label}</code>
      </span>
      {/* v3 幾何詳情 */}
      {epLabel && (
        <div style={{ paddingLeft: 16, color: 'var(--text-tertiary)', fontSize: 11 }}>
          entry: {epLabel}
          {wireLabel && <span style={{ marginLeft: 8 }}>{wireLabel}</span>}
        </div>
      )}
    </div>
  );
})}
```

### 5.3 "Sunken into Host" Visual Hint

When `isV3` and `hs.kind === 'water_tank'`, add a water-drop indicator to signal
the component is submerged (avoids confusion with panel-mount):

```jsx
{isV3 && hs.kind === 'water_tank' && (
  <span style={{ marginLeft: 4, opacity: 0.6 }} title="submerged in water tank">💧</span>
)}
```

---

## 6. Migration Strategy

### 6.1 Backward Compatibility Matrix

| Source | `host_structure` value | v3 behavior |
|---|---|---|
| Registry entry (v2) | `"external_body"` (default from `__post_init__` warn) | Solver uses legacy fallback path |
| Registry entry (v3) | `dict` with full schema | Solver uses geometry-aware path |
| `_to_embedded_ref` output (v2) | `"external_body"` string | Front-end renders string label |
| `_to_embedded_ref` output (v3) | `dict` | Front-end renders geometry detail |

### 6.2 Upgrade Sequence

1. **Phase A** — `component_spec.py`: add `host_structure: Optional[Union[str, dict]] = None`  
   with `__post_init__` warning. No behavior change; all existing tests pass.

2. **Phase B** — `_types.py` + `assembly_solver/__init__.py`: extend `_Comp`,  
   update `_build_comp_list`, rewrite Step 5b and `_to_embedded_ref`.

3. **Phase C** — `registry_data.py`: upgrade `Mist-Ultrasonic-class`, `Mist-Atomizer-class`  
   (and any other embedded candidates identified via `grep enclosure_relation='embedded'`).

4. **Phase D** — `views-engineer-assembly.jsx`: ship v3 rendering.

5. **Phase E** — `routes_design.py`: add validation call to `validate_host_structure()`  
   when payload contains `enclosure_relation: "embedded"`.

Phases A–B are non-breaking and can ship independently. Phase C depends on Phase A.
Phase D can deploy before Phase C (graceful string-fallback rendering already present).

---

## 7. Test Plan

### 7.1 Unit Tests (`tests/test_embedded_v3.py`)

| Test | Assertion |
|---|---|
| `test_host_structure_dict_valid` | `validate_host_structure()` passes for canonical Mist-Ultrasonic dict |
| `test_host_structure_invalid_kind` | Raises `ValueError` for unknown `kind` |
| `test_host_structure_u_out_of_range` | Raises `ValueError` for `u > 1.0` |
| `test_legacy_string_passthrough` | Solver accepts `host_structure="external_body"` without error |
| `test_embedded_placement_v3` | Solver sets `c.x = u * host_l`, `c.face_out = entry_port.face` |
| `test_embedded_placement_v2_fallback` | Missing dict → solver uses `inner_l/2, inner_w/2` |
| `test_to_embedded_ref_v3` | Output dict contains `wire_entry` key |
| `test_component_spec_warns_no_host` | `embedded` entry with `host_structure=None` issues `UserWarning` |

### 7.2 Integration Checks

- Run `scripts/_verify_canned_power.py` after Phase C registry changes.
- Run `python -m pytest tests/test_assembly_solver.py` — existing bucket-count assertions
  must still pass (Mist-* bucket shifts from `panel` → `embedded`; update fixtures).
- Visually verify `views-engineer-assembly.jsx` renders entry geometry in the Mist
  auto-watering template (`auto_waterer` Phase IV view).

### 7.3 Regression Guard

Add to CI:

```bash
python -c "
from lib.registry import COMPONENT_REGISTRY
from lib.assembly_solver.embedded_validator import validate_host_structure
for name, spec in COMPONENT_REGISTRY.items():
    if spec.enclosure_relation == 'embedded' and isinstance(spec.host_structure, dict):
        validate_host_structure(spec.host_structure, name)
print('All embedded host_structure entries valid.')
"
```
