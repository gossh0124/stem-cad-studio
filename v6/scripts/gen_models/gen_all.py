"""
gen_all.py - Orchestrator for STEM AI 3D model generation pipeline.

Reads v6/models/registry.json, drives per-shape-type generators (build123d),
and converts resulting STEP files to mesh.json via convert_step_to_mesh.

Models are stored at:
    v6/models/components/{shape-type}/{filename}.step
    v6/models/components/{shape-type}/{filename}.mesh.json

Usage:
    python gen_all.py                  # generate all missing models
    python gen_all.py --shape ic-dip   # generate only ic-dip variants
    python gen_all.py --force          # regenerate even if files exist
    python gen_all.py --dry-run        # show what would be generated

Wave 0 scaffold: architecture + interfaces defined. Actual build123d model
building functions to be added per shape type in Wave 1.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Project paths ───────────────────────────────────────────────────────────
# Resolved relative to this script's location (v6/scripts/gen_models/)
_SCRIPT_DIR = Path(__file__).resolve().parent
_V6_DIR = _SCRIPT_DIR.parent.parent          # v6/
_PROJECT_ROOT = _V6_DIR.parent               # project root
_REGISTRY_PATH = _V6_DIR / "models" / "registry.json"
_COMPONENTS_DIR = _V6_DIR / "models" / "components"


# ─── Import generators (populates GENERATORS dict on import) ─────────────────
from v6.scripts.gen_models.generators import GENERATORS


# ─── Registry loading ────────────────────────────────────────────────────────

def load_registry(registry_path: Path | None = None) -> dict[str, list[dict]]:
    """Load and validate the model registry JSON.

    Returns:
        Dict mapping shape type -> list of variant configs.
        Strips keys starting with '_' (metadata).
    """
    path = registry_path or _REGISTRY_PATH
    if not path.exists():
        raise FileNotFoundError(f"Registry not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Filter out metadata keys (e.g. _doc, _format, _total_models)
    registry = {k: v for k, v in raw.items() if not k.startswith("_")}

    total = sum(len(variants) for variants in registry.values())
    logger.info(
        "Loaded registry: %d shape types, %d total variants",
        len(registry), total,
    )
    return registry


# ─── Status tracking ─────────────────────────────────────────────────────────

class GenerationStatus:
    """Tracks which models exist and which need generation."""

    def __init__(self, components_dir: Path):
        self.components_dir = components_dir
        self.existing_step: list[str] = []
        self.existing_mesh: list[str] = []
        self.missing_step: list[str] = []
        self.missing_mesh: list[str] = []

    def scan(self, registry: dict[str, list[dict]]) -> None:
        """Scan filesystem and classify each variant as existing or missing."""
        self.existing_step.clear()
        self.existing_mesh.clear()
        self.missing_step.clear()
        self.missing_mesh.clear()

        for _shape_type, variants in registry.items():
            for variant in variants:
                rel_file = variant.get("file", "")
                if not rel_file:
                    continue

                step_path = self.components_dir / rel_file
                mesh_path = step_path.with_suffix(".mesh.json")

                if step_path.exists():
                    self.existing_step.append(rel_file)
                else:
                    self.missing_step.append(rel_file)

                if mesh_path.exists():
                    self.existing_mesh.append(rel_file)
                else:
                    self.missing_mesh.append(rel_file)

    def summary(self) -> str:
        total = len(self.existing_step) + len(self.missing_step)
        return (
            f"Models: {total} total | "
            f"STEP: {len(self.existing_step)} exist, "
            f"{len(self.missing_step)} missing | "
            f"mesh.json: {len(self.existing_mesh)} exist, "
            f"{len(self.missing_mesh)} missing"
        )


# ─── Generation pipeline ────────────────────────────────────────────────────

def _convert_step_to_mesh(step_path: Path) -> Path:
    """Convert a .step file to .mesh.json using the converter module.

    Imports at function level to avoid circular imports and to allow
    this module to work even when OCP is not installed.
    """
    from v6.scripts.gen_models.convert_step_to_mesh import convert_step_to_mesh
    return convert_step_to_mesh(step_path)


def generate_model(
    shape_type: str,
    variant: dict,
    components_dir: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Generate a single model variant (STEP + mesh.json).

    Returns a result dict:
        {"file": str, "step": status, "mesh": status, "error": str|None}
    """
    rel_file = variant.get("file", "")
    result: dict[str, Any] = {
        "file": rel_file,
        "step": "skipped",
        "mesh": "skipped",
        "error": None,
    }

    if not rel_file:
        result["error"] = "No 'file' key in variant config"
        result["step"] = "error"
        return result

    generator = GENERATORS.get(shape_type)
    if generator is None:
        result["error"] = f"No generator for shape type: {shape_type}"
        result["step"] = "error"
        return result

    step_path = components_dir / rel_file
    mesh_path = step_path.with_suffix(".mesh.json")

    # ── STEP generation ──
    need_step = force or not step_path.exists()
    if need_step:
        if dry_run:
            result["step"] = "dry-run"
            logger.info("[DRY-RUN] Would generate STEP: %s", rel_file)
        else:
            try:
                step_path.parent.mkdir(parents=True, exist_ok=True)
                generator(variant, step_path)
                result["step"] = "ok"
                logger.info("Generated STEP: %s", rel_file)
            except NotImplementedError as e:
                result["step"] = "not-implemented"
                result["error"] = str(e)
                logger.debug("Generator stub: %s - %s", rel_file, e)
            except Exception as e:
                result["step"] = "error"
                result["error"] = str(e)
                logger.error("STEP generation failed: %s - %s", rel_file, e)
    else:
        logger.debug("STEP exists, skipping: %s", rel_file)

    # ── mesh.json conversion ──
    need_mesh = force or not mesh_path.exists()
    if need_mesh and step_path.exists():
        if dry_run:
            result["mesh"] = "dry-run"
            logger.info("[DRY-RUN] Would convert mesh: %s", mesh_path.name)
        else:
            try:
                _convert_step_to_mesh(step_path)
                result["mesh"] = "ok"
                logger.info("Converted mesh: %s", mesh_path.name)
            except NotImplementedError as e:
                result["mesh"] = "not-implemented"
                if not result["error"]:
                    result["error"] = str(e)
                logger.debug("Converter stub: %s", mesh_path.name)
            except Exception as e:
                result["mesh"] = "error"
                if not result["error"]:
                    result["error"] = str(e)
                logger.error("Mesh conversion failed: %s - %s", mesh_path.name, e)
    elif not step_path.exists():
        logger.debug("No STEP file, skipping mesh: %s", rel_file)

    return result


def generate_all(
    registry: dict[str, list[dict]],
    components_dir: Path,
    *,
    shape_filter: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Generate all models in the registry (or a filtered subset).

    Returns list of per-variant result dicts.
    """
    results: list[dict[str, Any]] = []
    t0 = time.monotonic()

    shape_types = [shape_filter] if shape_filter else list(registry.keys())

    for shape_type in shape_types:
        if shape_type not in registry:
            logger.warning("Shape type '%s' not in registry", shape_type)
            continue

        variants = registry[shape_type]
        logger.info(
            "Processing: %s (%d variants)", shape_type, len(variants),
        )

        for variant in variants:
            result = generate_model(
                shape_type, variant, components_dir,
                force=force, dry_run=dry_run,
            )
            result["shape_type"] = shape_type
            results.append(result)

    elapsed = time.monotonic() - t0
    logger.info("Generation complete in %.1fs", elapsed)
    return results


def print_report(results: list[dict[str, Any]]) -> None:
    """Print a summary table of generation results."""
    if not results:
        print("No models processed.")
        return

    counts: dict[str, int] = {}
    errors: list[dict[str, Any]] = []
    for r in results:
        status = r["step"]
        counts[status] = counts.get(status, 0) + 1
        if r["error"] and status == "error":
            errors.append(r)

    print(f"\n{'=' * 60}")
    print(f"Generation Report: {len(results)} models processed")
    print(f"{'=' * 60}")

    status_icons = {
        "ok": "[OK]", "skipped": "[SKIP]", "error": "[ERR]",
        "dry-run": "[DRY]", "not-implemented": "[STUB]",
    }
    for status, count in sorted(counts.items()):
        icon = status_icons.get(status, f"[{status}]")
        print(f"  {icon:>8}  {count}")

    if errors:
        print(f"\nErrors:")
        for r in errors:
            print(f"  - {r['file']}: {r['error']}")
    print()


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate 3D component models for the STEM AI viewer.",
        epilog=(
            "Examples:\n"
            "  python gen_all.py                    # generate all missing\n"
            "  python gen_all.py --shape ic-dip      # only ic-dip\n"
            "  python gen_all.py --force --shape relay  # force-regen relay\n"
            "  python gen_all.py --dry-run            # preview actions\n"
            "  python gen_all.py --status             # show model status\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--shape", type=str, default=None,
        help="Generate only this shape type (e.g. ic-dip, conn-header-male)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even if STEP/mesh files already exist",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be generated without creating files",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show model existence status and exit",
    )
    parser.add_argument(
        "--registry", type=Path, default=None,
        help=f"Path to registry.json (default: {_REGISTRY_PATH})",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help=f"Path to components output dir (default: {_COMPONENTS_DIR})",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
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

    # Load registry
    registry_path = args.registry or _REGISTRY_PATH
    try:
        registry = load_registry(registry_path)
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in registry: %s", e)
        return 1

    components_dir = args.output_dir or _COMPONENTS_DIR

    # Status mode
    if args.status:
        status = GenerationStatus(components_dir)
        status.scan(registry)
        print(status.summary())
        reg_types = set(registry.keys())
        gen_types = set(GENERATORS.keys())
        missing = reg_types - gen_types
        if missing:
            print(f"\nNo generator: {', '.join(sorted(missing))}")
        else:
            print(f"\nAll {len(reg_types)} shape types have generators.")
        return 0

    # Validate shape filter
    if args.shape and args.shape not in registry:
        logger.error(
            "Shape '%s' not in registry. Available: %s",
            args.shape, ", ".join(sorted(registry.keys())),
        )
        return 1

    # Run generation
    results = generate_all(
        registry, components_dir,
        shape_filter=args.shape, force=args.force, dry_run=args.dry_run,
    )
    print_report(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
