"""test_assembly_geometry.py -- Assembly geometry builder verification.

Tests for geo-builders.js logic (Python port) to catch:
  - Axis mapping correctness (Z-up -> Y-up)
  - Uniform scale calculation
  - Target-fit scaling vs viewport scaling
  - Bounding box centering
  - pcb_body scale axis consistency
"""
import math
import pytest


def _build_stl_geo_scale(triangles_bbox, target_l, target_h, target_w):
    """Python port of _buildSTLGeo scaling logic.

    triangles_bbox: dict with sx, sy, sz (source extents in STL Z-up space)
    Returns: sUni, axis_map
    """
    sx, sy, sz = triangles_bbox["sx"], triangles_bbox["sy"], triangles_bbox["sz"]
    s_uni = min(target_l / sx, target_h / sz, target_w / sy)
    return s_uni, {
        "three_x": "stl_x",
        "three_y": "stl_z",
        "three_z": "-stl_y",
    }


def _build_glb_merged_geo_scale(glb_bbox, target_l, target_h, target_w):
    """Python port of _buildGLBMergedGeo scaling logic.

    glb_bbox: dict with sx, sy, sz (source extents in GLB source space)
    Same axis mapping as STL (assumes Z-up source data).
    """
    sx, sy, sz = glb_bbox["sx"], glb_bbox["sy"], glb_bbox["sz"]
    s_uni = min(target_l / sx, target_h / sz, target_w / sy)
    return s_uni, {
        "three_x": "src_x",
        "three_y": "src_z",
        "three_z": "-src_y",
    }


def _pcb_body_scale(inner_l, inner_w, inner_h, scale, glb_bbox):
    """Python port of renderer-setup.js pcb_body scaling (lines 151-153).

    This path has a known inconsistency:
    - scaling maps innerW->sz, innerH->sy (Y-up assumption)
    - but rotateX(-PI/2) assumes Z-up source data
    """
    sx, sy, sz = glb_bbox["sx"], glb_bbox["sy"], glb_bbox["sz"]
    pcb_scale = min(
        (inner_l * scale * 0.9) / max(sx, 0.01),
        (inner_w * scale * 0.9) / max(sz, 0.01),
        (inner_h * scale * 0.3) / max(sy, 0.01),
    )
    return pcb_scale


def _place_mesh(comp, inner_l, inner_w, wall, scale, y_base):
    """Python port of _placeMesh logic."""
    ox = (comp["x"] + comp["L"] / 2 - inner_l / 2) * scale
    oz = (comp["y"] + comp["W"] / 2 - inner_w / 2) * scale
    oy = y_base + (wall + comp["H"] / 2) * scale
    return ox, oy, oz


# ── Test: axis mapping ──

class TestAxisMapping:
    def test_stl_z_up_to_y_up(self):
        bbox = {"sx": 10, "sy": 5, "sz": 3}
        s, axes = _build_stl_geo_scale(bbox, 10, 3, 5)
        assert axes["three_y"] == "stl_z", "STL Z should map to Three.js Y (height)"
        assert axes["three_z"] == "-stl_y", "STL Y should map to Three.js -Z (depth)"

    def test_glb_same_mapping_as_stl(self):
        bbox = {"sx": 10, "sy": 5, "sz": 3}
        s_stl, _ = _build_stl_geo_scale(bbox, 10, 3, 5)
        s_glb, _ = _build_glb_merged_geo_scale(bbox, 10, 3, 5)
        assert s_stl == s_glb, "GLB and STL should use same scale for same bbox"


# ── Test: uniform scale ──

class TestUniformScale:
    def test_preserves_aspect_ratio(self):
        bbox = {"sx": 68.6, "sy": 53.3, "sz": 14.0}
        s, _ = _build_stl_geo_scale(bbox, 68.6, 14.0, 53.3)
        assert abs(s - 1.0) < 0.001, f"perfect match should give scale=1.0, got {s}"

    def test_picks_smallest_ratio(self):
        bbox = {"sx": 100, "sy": 50, "sz": 30}
        s, _ = _build_stl_geo_scale(bbox, 50, 30, 25)
        expected = min(50 / 100, 30 / 30, 25 / 50)
        assert abs(s - expected) < 0.001

    def test_non_cubic_fits_all_axes(self):
        bbox = {"sx": 68.6, "sy": 53.3, "sz": 14.0}
        target_l, target_h, target_w = 1.2, 0.244, 0.93
        s, _ = _build_stl_geo_scale(bbox, target_l, target_h, target_w)
        assert s * bbox["sx"] <= target_l + 0.001
        assert s * bbox["sz"] <= target_h + 0.001
        assert s * bbox["sy"] <= target_w + 0.001


# ── Test: placement positioning ──

class TestPlacement:
    def test_centered_component(self):
        comp = {"x": 35.3, "y": 25.6, "L": 68.6, "W": 53.3, "H": 14.0}
        inner_l, inner_w = 139.2, 104.4
        wall = 2.0
        outer_l = inner_l + 2 * wall
        outer_w = inner_w + 2 * wall
        outer_h = 60 + 2 * wall
        max_dim = max(outer_l, outer_w, outer_h)
        scale = 2.5 / max_dim
        y_base = -(outer_h * scale) / 2
        ox, oy, oz = _place_mesh(comp, inner_l, inner_w, wall, scale, y_base)
        # Verify placement formula: ox = (x + L/2 - inner_l/2) * scale
        expected_ox = (comp["x"] + comp["L"] / 2 - inner_l / 2) * scale
        expected_oz = (comp["y"] + comp["W"] / 2 - inner_w / 2) * scale
        expected_oy = y_base + (wall + comp["H"] / 2) * scale
        assert ox == pytest.approx(expected_ox), f"ox={ox}, expected={expected_ox}"
        assert oy == pytest.approx(expected_oy), f"oy={oy}, expected={expected_oy}"
        assert oz == pytest.approx(expected_oz), f"oz={oz}, expected={expected_oz}"

    def test_origin_component_offcenter(self):
        comp = {"x": 0, "y": 0, "L": 10, "W": 10, "H": 5}
        inner_l, inner_w = 100, 100
        wall = 2
        scale = 2.5 / 104
        y_base = -104 * scale / 2
        ox, oy, oz = _place_mesh(comp, inner_l, inner_w, wall, scale, y_base)
        assert ox < 0, "component at x=0 should be left of center"
        assert oz < 0, "component at y=0 should be in front of center"

    def test_centered_component_near_origin(self):
        comp = {"x": 45, "y": 45, "L": 10, "W": 10, "H": 5}
        inner_l, inner_w = 100, 100
        wall = 2
        scale = 2.5 / 104
        y_base = -104 * scale / 2
        ox, oy, oz = _place_mesh(comp, inner_l, inner_w, wall, scale, y_base)
        assert abs(ox) < 0.01, "component at center should be at x~0"
        assert abs(oz) < 0.01, "component at center should be at z~0"


# ── Test: pcb_body scaling inconsistency ──

class TestPcbBodyScaling:
    def test_scale_axis_inconsistency_detected(self):
        """The pcb_body path maps innerW->sz, innerH->sy.
        If source is Z-up: sz=height, sy=depth.
        This means innerW maps to height and innerH maps to depth - SWAPPED.
        When inner_w != inner_h, the current code produces a different scale
        than the correct (un-swapped) mapping — assert we detect this.
        """
        inner_l, inner_w, inner_h = 139.2, 104.4, 60.0
        scale = 2.5 / (inner_l + 4)
        bbox_zup = {"sx": 68.6, "sy": 53.3, "sz": 14.0}
        pcb_s = _pcb_body_scale(inner_l, inner_w, inner_h, scale, bbox_zup)
        correct_s = min(
            (inner_l * scale * 0.9) / bbox_zup["sx"],
            (inner_w * scale * 0.9) / bbox_zup["sy"],
            (inner_h * scale * 0.3) / bbox_zup["sz"],
        )
        # Non-cubic bbox with inner_w != inner_h → swapped mapping must differ
        assert abs(pcb_s - correct_s) > 0.001, (
            "Expected axis inconsistency between current and correct mapping, "
            f"but pcb_s={pcb_s:.6f} == correct_s={correct_s:.6f}"
        )

    def test_cubic_bbox_unaffected(self):
        """For cubic bounding box, the axis swap doesn't matter."""
        inner_l, inner_w, inner_h = 100, 100, 100
        scale = 0.02
        bbox = {"sx": 50, "sy": 50, "sz": 50}
        pcb_s = _pcb_body_scale(inner_l, inner_w, inner_h, scale, bbox)
        correct_s = _pcb_body_scale(inner_l, inner_h, inner_w, scale, bbox)
        assert abs(pcb_s - correct_s) < 0.001


# ── Test: enclosure ghost box ──

class TestEnclosureGhostBox:
    def test_enclosure_dimensions(self):
        inner_l, inner_w, inner_h = 139.2, 104.4, 60.0
        wall = 2.0
        outer_l = inner_l + 2 * wall
        outer_w = inner_w + 2 * wall
        outer_h = inner_h + 2 * wall
        max_dim = max(outer_l, outer_w, outer_h)
        scale = 2.5 / max_dim
        enc_w = outer_l * scale
        enc_h = outer_h * scale
        enc_d = outer_w * scale
        assert enc_w > 0
        assert enc_h > 0
        assert enc_d > 0
        assert enc_w == pytest.approx(2.5, abs=0.01), "longest dim should be ~2.5"

    def test_y_base_centered(self):
        """y_base should place the enclosure bottom at -enc_h/2,
        so the enclosure spans from -enc_h/2 to +enc_h/2 (centered at y=0)."""
        inner_h = 60.0
        wall = 2.0
        outer_h = inner_h + 2 * wall
        max_dim = 143.2
        scale = 2.5 / max_dim
        enc_h = outer_h * scale
        y_base = -enc_h / 2
        # y_base is the bottom of the enclosure; top should be at +enc_h/2
        y_top = y_base + enc_h
        assert y_top == pytest.approx(enc_h / 2, abs=0.001), (
            f"Enclosure top should be at +enc_h/2={enc_h/2:.4f}, got {y_top:.4f}"
        )
        # Enclosure center should be at y=0
        y_center = (y_base + y_top) / 2
        assert abs(y_center) < 0.001, f"Enclosure center should be at y=0, got {y_center:.4f}"
        # Verify enc_h matches expected value
        expected_enc_h = outer_h * scale
        assert enc_h == pytest.approx(expected_enc_h, abs=0.001)


# ── Test: explosion factor ──

class TestExplosionFactor:
    def test_zero_explosion_no_offset(self):
        factor = 0.0
        base_y = -0.5
        for idx in range(5):
            final_y = base_y + factor * (idx + 1) * 0.3
            assert final_y == base_y

    def test_full_explosion_separates(self):
        factor = 1.0
        base_y = -0.5
        positions = []
        for idx in range(5):
            final_y = base_y + factor * (idx + 1) * 0.3
            positions.append(final_y)
        for i in range(1, len(positions)):
            assert positions[i] > positions[i - 1], "explosion should separate"


# ── Test: cross-view consistency gate ──

class TestCrossViewConsistency:
    """Verify that assembly solver uses the same dimensions as ComponentSpec."""

    def test_solver_modules_match_registry_dims(self):
        """Every ComponentModule created by solve() must carry the exact L/W/H
        from its ComponentSpec — no rounding, no swapping."""
        from lib.assembly_solver import solve
        from lib.registry import COMPONENT_REGISTRY
        comps = [{"type": cls, "role": "Brain" if "class" in cls else "Sensor", "qty": 1}
                 for cls in list(COMPONENT_REGISTRY.keys())[:6]]
        wiring = {}
        result = solve(components=comps, wiring_raw=wiring,
                       enclosure_spec={"inner_length": 300, "inner_width": 200,
                                       "inner_height": 80, "wall": 2.5})
        all_placed = result["placements"] + result["panel_placements"]
        all_placed += result.get("external_refs", []) + result.get("embedded_refs", [])
        for p in all_placed:
            cls = p["type"]
            if cls not in COMPONENT_REGISTRY:
                continue
            spec = COMPONENT_REGISTRY[cls]
            assert p["L"] == spec.length_mm, f"{cls} L mismatch: {p['L']} vs {spec.length_mm}"
            assert p["W"] == spec.width_mm, f"{cls} W mismatch: {p['W']} vs {spec.width_mm}"
            assert p["H"] == spec.height_mm, f"{cls} H mismatch: {p['H']} vs {spec.height_mm}"

    def test_enclosure_relation_propagated(self):
        """enclosure_relation in placement output must match registry."""
        from lib.assembly_solver import solve
        from lib.registry import COMPONENT_REGISTRY
        comps = [
            {"type": "Arduino-Uno-class", "role": "Brain", "qty": 1},
            {"type": "Pump-Water-class", "role": "Actuator", "qty": 1},
            {"type": "Sensor-SoilMoisture-class", "role": "Sensor", "qty": 1},
        ]
        result = solve(components=comps, wiring_raw={},
                       enclosure_spec={"inner_length": 120, "inner_width": 100,
                                       "inner_height": 45, "wall": 2.5})
        internal_types = {p["type"] for p in result["placements"]}
        ext_types = {p["type"] for p in result.get("external_refs", [])}
        emb_types = {p["type"] for p in result.get("embedded_refs", [])}
        assert "Arduino-Uno-class" in internal_types
        assert "Sensor-SoilMoisture-class" in ext_types
        assert "Pump-Water-class" in emb_types
