"""scripts/regression_invalid_rate.py — CH2 Invalid Rate 16 範本回歸基線。

對 v6/canned/*.json 每個範本跑 services.shared.validate_cad.validate_cad_output()，
彙整出本專案 phase4 輸出的當前 Invalid Rate baseline，供未來 LoRA-B 訓練前後對比。

用法：.venv/Scripts/python.exe scripts/regression_invalid_rate.py
      .venv/Scripts/python.exe scripts/regression_invalid_rate.py --fail-above 0.1
      .venv/Scripts/python.exe scripts/regression_invalid_rate.py --lenient
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.shared.validate_cad import validate_cad_output  # noqa: E402

CANNED = ROOT / "v6" / "canned"
INDEX = CANNED / "_index.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CH2 Invalid Rate regression baseline")
    parser.add_argument(
        "--fail-above", type=float, default=0.0,
        help="Exit 1 if invalid rate exceeds this threshold (0.0-1.0, default 0.0)",
    )
    parser.add_argument(
        "--lenient", action="store_true",
        help="Always exit 0 regardless of invalid rate (for info-only runs)",
    )
    args = parser.parse_args(argv)

    templates = json.loads(INDEX.read_text(encoding="utf-8"))
    print(f"{'tpl_id':<22} {'exi':>3} {'prs':>3} {'wat':>3} {'bbx':>3} {'snp':>3}  status")
    print("-" * 80)

    per_check_fail: dict[str, int] = {
        "exists": 0, "parseable": 0, "watertight": 0,
        "bbox_ok": 0, "snap_fit_ok": 0,
    }
    invalid_count = 0

    for entry in templates:
        tpl_id = entry["id"]
        bridge = json.loads((CANNED / f"{tpl_id}.json").read_text(encoding="utf-8"))
        res = validate_cad_output(bridge.get("cad_output"), project_root=ROOT)
        cks = res["checks"]
        flags = " ".join(
            ("OK " if cks[k] else "NG ").rstrip() + " "
            for k in ("exists", "parseable", "watertight", "bbox_ok", "snap_fit_ok")
        )
        status = "INVALID" if res["invalid"] else "valid"
        print(f"{tpl_id:<22} {flags} {status}")
        if res["invalid"]:
            invalid_count += 1
            for k, ok in cks.items():
                if not ok:
                    per_check_fail[k] += 1
            for r in res["fail_reasons"]:
                print(f"    - {r}")

    n = len(templates)
    invalid_rate = invalid_count / n if n else 0.0
    print()
    print("=" * 80)
    print(f"Baseline Invalid Rate: {invalid_count} / {n} = {invalid_rate*100:.1f}%")
    print()
    print("Per-check failure counts:")
    for k, v in per_check_fail.items():
        print(f"  {k:<14} {v}")

    if args.lenient:
        return 0
    if invalid_rate > args.fail_above:
        print(f"\nFAIL: invalid rate {invalid_rate*100:.1f}% > threshold {args.fail_above*100:.1f}%")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
