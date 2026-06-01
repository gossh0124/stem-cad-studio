"""
convert_step_to_mesh.py - STEP to mesh.json converter for STEM AI 3D pipeline.

Tessellates a STEP file using OpenCascade (via build123d/OCP) and outputs
a mesh.json file with per-part vertices, normals, indices, and material data.

Usage:
    python convert_step_to_mesh.py input.step [output.mesh.json]

If output path is omitted, writes {input_stem}.mesh.json alongside the input.

Wave 0 scaffold: core tessellation architecture defined, OCP integration in Wave 1.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Material preset table ──────────────────────────────────────────────────
# Maps OCP face color (approximate RGB) to named material presets.
# Each preset carries color + PBR roughness/metalness for the mesh.json output.
MATERIAL_PRESETS: dict[str, dict[str, Any]] = {
    "ic-body": {
        "color": [34, 34, 34],
        "roughness": 0.85,
        "metalness": 0.0,
        "match_colors": [(34, 34, 34), (51, 51, 51), (30, 30, 30)],
    },
    "ic-pin": {
        "color": [192, 192, 192],
        "roughness": 0.30,
        "metalness": 0.80,
        "match_colors": [(192, 192, 192), (170, 170, 170), (160, 160, 160)],
    },
    "gold-pin": {
        "color": [201, 176, 55],
        "roughness": 0.30,
        "metalness": 0.70,
        "match_colors": [(201, 176, 55), (196, 160, 53), (210, 180, 60)],
    },
    "connector": {
        "color": [212, 212, 212],
        "roughness": 0.20,
        "metalness": 0.85,
        "match_colors": [(212, 212, 212), (200, 200, 200), (220, 220, 220)],
    },
    "plastic-black": {
        "color": [26, 26, 26],
        "roughness": 0.70,
        "metalness": 0.0,
        "match_colors": [(26, 26, 26), (17, 17, 17), (20, 20, 20)],
    },
    "plastic-blue": {
        "color": [37, 99, 235],
        "roughness": 0.70,
        "metalness": 0.0,
        "match_colors": [(37, 99, 235), (30, 58, 95)],
    },
    "ceramic": {
        "color": [196, 160, 53],
        "roughness": 0.60,
        "metalness": 0.10,
        "match_colors": [(196, 160, 53), (180, 150, 50)],
    },
    "motor": {
        "color": [100, 100, 100],
        "roughness": 0.40,
        "metalness": 0.50,
        "match_colors": [(100, 100, 100), (80, 80, 80)],
    },
    "pcb-green": {
        "color": [45, 106, 45],
        "roughness": 0.80,
        "metalness": 0.0,
        "match_colors": [(45, 106, 45), (30, 80, 30)],
    },
    "led-translucent": {
        "color": [232, 232, 232],
        "roughness": 0.30,
        "metalness": 0.0,
        "match_colors": [(232, 232, 232), (240, 240, 240)],
    },
    "default": {
        "color": [128, 128, 128],
        "roughness": 0.50,
        "metalness": 0.20,
        "match_colors": [],
    },
}


def _color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance in RGB space."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def match_material(rgb: tuple[int, int, int], threshold: float = 40.0) -> str:
    """Find the closest material preset for a given face RGB color.

    Returns the preset name, or 'default' if no preset is within threshold.
    """
    best_name = "default"
    best_dist = threshold

    for name, preset in MATERIAL_PRESETS.items():
        if name == "default":
            continue
        for ref_color in preset["match_colors"]:
            dist = _color_distance(rgb, ref_color)
            if dist < best_dist:
                best_dist = dist
                best_name = name

    return best_name


def get_material_props(preset_name: str) -> dict[str, Any]:
    """Return color, roughness, metalness for a named preset."""
    preset = MATERIAL_PRESETS.get(preset_name, MATERIAL_PRESETS["default"])
    return {
        "color": list(preset["color"]),
        "roughness": preset["roughness"],
        "metalness": preset["metalness"],
    }


# ─── STEP loading ────────────────────────────────────────────────────────────

def _load_step(step_path: Path) -> Any:
    """Load a STEP file via build123d and return the OCP TopoDS_Shape."""
    from build123d import import_step
    shape = import_step(str(step_path))
    return shape.wrapped  # unwrap to raw OCP TopoDS_Shape


# ─── Tessellation ────────────────────────────────────────────────────────────

def _tessellate_shape(shape: Any, linear_deflection: float = 0.1,
                      angular_deflection: float = 0.5) -> list[dict[str, Any]]:
    """Tessellate an OCP shape into per-face mesh dicts.

    Returns list of dicts with: name, vertices, normals, indices, color.
    Uses OCP BRepMesh for tessellation and face normal computation.
    """
    import math
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.BRep import BRep_Tool
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS

    BRepMesh_IncrementalMesh(shape, linear_deflection, False,
                             angular_deflection, True)

    faces: list[dict[str, Any]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    fi = 0

    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        explorer.Next()
        if tri is None:
            continue

        xform = loc.Transformation()
        n_nodes = tri.NbNodes()
        n_tris = tri.NbTriangles()

        # Extract vertices
        vertices: list[float] = []
        for i in range(1, n_nodes + 1):
            pt = tri.Node(i).Transformed(xform)
            vertices.extend([round(pt.X(), 5), round(pt.Y(), 5),
                             round(pt.Z(), 5)])

        # Extract indices (OCP is 1-based → 0-based)
        indices: list[int] = []
        for i in range(1, n_tris + 1):
            t = tri.Triangle(i)
            n1, n2, n3 = t.Get()
            indices.extend([n1 - 1, n2 - 1, n3 - 1])

        # Compute per-vertex normals from adjacent triangles
        normals = [0.0] * (n_nodes * 3)
        for i in range(0, len(indices), 3):
            i0, i1, i2 = indices[i], indices[i+1], indices[i+2]
            ax, ay, az = vertices[i0*3:i0*3+3]
            bx, by, bz = vertices[i1*3:i1*3+3]
            cx, cy, cz = vertices[i2*3:i2*3+3]
            # Cross product (b-a) x (c-a)
            nx = (by - ay) * (cz - az) - (bz - az) * (cy - ay)
            ny = (bz - az) * (cx - ax) - (bx - ax) * (cz - az)
            nz = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            for vi in (i0, i1, i2):
                normals[vi*3] += nx
                normals[vi*3+1] += ny
                normals[vi*3+2] += nz

        # Normalize
        for i in range(n_nodes):
            nx, ny, nz = normals[i*3], normals[i*3+1], normals[i*3+2]
            ln = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
            normals[i*3] = round(nx / ln, 5)
            normals[i*3+1] = round(ny / ln, 5)
            normals[i*3+2] = round(nz / ln, 5)

        faces.append({
            "name": f"face_{fi}",
            "vertices": vertices,
            "normals": normals,
            "indices": indices,
            "color": [128, 128, 128],  # default; overridden by material mapping
        })
        fi += 1

    return faces


def _group_faces_by_material(
    faces: list[dict[str, Any]],
    shape_type: str = "default",
) -> list[dict[str, Any]]:
    """Merge all faces into a single part with default material.

    Since build123d STEP files are monochrome, we assign material based
    on shape_type from the file path convention.
    """
    if not faces:
        return []

    # Merge all face geometry into one part
    all_verts: list[float] = []
    all_normals: list[float] = []
    all_indices: list[int] = []

    for face in faces:
        offset = len(all_verts) // 3
        all_verts.extend(face["vertices"])
        all_normals.extend(face["normals"])
        all_indices.extend(i + offset for i in face["indices"])

    # Map shape_type to material preset
    _SHAPE_MATERIAL: dict[str, str] = {
        "ic-dip": "ic-body", "ic-soic": "ic-body", "ic-qfp": "ic-body",
        "ic-module": "connector",
        "conn-header-male": "plastic-black", "conn-header-female": "plastic-black",
        "conn-usb-micro": "connector", "conn-usb-c": "connector",
        "conn-usb-b": "connector", "conn-barrel-jack": "connector",
        "conn-screw-terminal": "plastic-blue",
        "cap-electrolytic": "connector", "cap-ceramic": "ceramic",
        "res-smd": "ic-body", "crystal-hc49": "connector",
        "relay": "plastic-black", "button-tactile": "plastic-black",
        "led-tht": "led-translucent", "led-smd": "led-translucent",
        "buzzer": "plastic-black", "motor-dc": "motor",
        "motor-servo": "plastic-blue", "motor-stepper": "motor",
        "vreg-to220": "ic-body", "sensor-dome": "led-translucent",
        "mounting-hole": "pcb-green",
    }
    preset_name = _SHAPE_MATERIAL.get(shape_type, "default")
    mat = get_material_props(preset_name)

    return [{
        "name": shape_type or "mesh",
        "vertices": all_verts,
        "normals": all_normals,
        "indices": all_indices,
        **mat,
    }]


# ─── Main conversion ────────────────────────────────────────────────────────

def convert_step_to_mesh(
    step_path: Path,
    output_path: Path | None = None,
    *,
    linear_deflection: float = 0.1,
    angular_deflection: float = 0.5,
) -> Path:
    """Convert a STEP file to mesh.json format.

    Args:
        step_path: Path to input .step file.
        output_path: Path for output .mesh.json. If None, writes alongside input.
        linear_deflection: Tessellation chord height tolerance (mm).
        angular_deflection: Tessellation angular tolerance (radians).

    Returns:
        Path to the written mesh.json file.

    Raises:
        FileNotFoundError: If step_path does not exist.
        RuntimeError: If STEP loading or tessellation fails.
    """
    step_path = Path(step_path).resolve()
    if not step_path.exists():
        raise FileNotFoundError(f"STEP file not found: {step_path}")

    if output_path is None:
        output_path = step_path.with_suffix(".mesh.json")
    else:
        output_path = Path(output_path).resolve()

    logger.info("Converting: %s -> %s", step_path, output_path)

    # Step 1: load STEP
    shape = _load_step(step_path)

    # Step 2: tessellate into per-face parts
    raw_faces = _tessellate_shape(
        shape,
        linear_deflection=linear_deflection,
        angular_deflection=angular_deflection,
    )

    # Step 3: infer shape type from path convention
    # e.g. v6/models/components/ic-dip/dip-8-254.step -> "ic-dip"
    shape_type = step_path.parent.name if step_path.parent.name != "components" else "unknown"

    # Step 4: group faces by material (uses shape_type for preset mapping)
    parts = _group_faces_by_material(raw_faces, shape_type)

    # Step 5: build mesh.json envelope
    mesh_data: dict[str, Any] = {
        "format": "mesh-v1",
        "shape": shape_type,
        "variant": {},  # TODO [Wave 1]: extract variant params from filename/registry
        "parts": parts,
    }

    # Step 6: write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(mesh_data, f, indent=2, ensure_ascii=False)

    logger.info("Wrote mesh.json: %s (%d parts)", output_path, len(parts))
    return output_path


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a STEP file to mesh.json for the STEM AI 3D viewer.",
        epilog="Example: python convert_step_to_mesh.py models/ic-dip/dip-8.step",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to input .step file",
    )
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        default=None,
        help="Path to output .mesh.json (default: alongside input file)",
    )
    parser.add_argument(
        "--linear-deflection",
        type=float,
        default=0.1,
        help="Tessellation chord height tolerance in mm (default: 0.1)",
    )
    parser.add_argument(
        "--angular-deflection",
        type=float,
        default=0.5,
        help="Tessellation angular tolerance in radians (default: 0.5)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on success, 1 on error."""
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    step_path = args.input.resolve()
    if not step_path.exists():
        logger.error("Input file not found: %s", step_path)
        return 1

    if step_path.suffix.lower() not in (".step", ".stp"):
        logger.error("Expected .step or .stp file, got: %s", step_path.suffix)
        return 1

    try:
        out = convert_step_to_mesh(
            step_path,
            args.output,
            linear_deflection=args.linear_deflection,
            angular_deflection=args.angular_deflection,
        )
        print(f"OK: {out}")
        return 0
    except NotImplementedError as e:
        logger.warning("Wave 1 not yet implemented: %s", e)
        return 2
    except Exception as e:
        logger.error("Conversion failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
