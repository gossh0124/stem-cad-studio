"""scripts/audit_rth_ja.py -- IC-level Rth_ja thermal resistance audit.

Checks all 4 PCB specs for SubComponent thermal resistance data:
  - rth_ja_cw > 0
  - rth_sources has 3 entries (3-source cross-verification)
  - S1 vs S2 deviation < 30%
  - S1 vs S3 deviation < 30%
  - S2 vs S3 deviation < 30%

Usage:
    .venv/Scripts/python.exe scripts/audit_rth_ja.py
    .venv/Scripts/python.exe scripts/audit_rth_ja.py --strict
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from lib.pcb.arduino_uno_r3 import ARDUINO_UNO_R3
from lib.pcb.esp32_devkit_v1 import ESP32_DEVKIT_V1
from lib.pcb.microbit_v2 import MICROBIT_V2
from lib.pcb.raspberry_pi_4b import RASPBERRY_PI_4B

BOARDS = [
    ('Arduino Uno R3', ARDUINO_UNO_R3),
    ('ESP32 DevKit V1', ESP32_DEVKIT_V1),
    ('micro:bit V2', MICROBIT_V2),
    ('Raspberry Pi 4B', RASPBERRY_PI_4B),
]

MAX_DEVIATION_PCT = 30.0


def _deviation_pct(v1: float, v2: float) -> float:
    """Symmetric percentage deviation between two values."""
    if v1 == 0 and v2 == 0:
        return 0.0
    base = max(abs(v1), abs(v2))
    return abs(v1 - v2) / base * 100.0


def audit_board(board_name: str, pcb_spec, strict: bool) -> tuple:
    """Audit a single board. Returns (pass_count, fail_count, skip_count, rows).

    rows: list of (name, package, rth_ja, sources_count, dev12%, dev13%, status)
    """
    passes = 0
    fails = 0
    skips = 0
    rows = []

    for sc in pcb_spec.sub_components:
        # Only audit components that have thermal data
        has_thermal = (
            sc.thermal_typical_mw > 0
            or sc.thermal_peak_mw > 0
            or sc.rth_ja_cw > 0
        )
        if not has_thermal:
            continue

        name = sc.name
        pkg = sc.package
        rth = sc.rth_ja_cw
        srcs = sc.rth_sources
        status_parts = []
        row_fail = False

        # Check 1: rth_ja_cw > 0
        if rth <= 0:
            if strict:
                status_parts.append('FAIL:rth=0')
                row_fail = True
            else:
                status_parts.append('SKIP:no-rth')
                rows.append((name, pkg, rth, 0, '-', '-', 'SKIP'))
                skips += 1
                continue

        # Check 2: rth_sources has 3 entries
        src_count = len(srcs)
        if src_count < 3:
            status_parts.append(f'FAIL:sources={src_count}<3')
            row_fail = True

        # Check 3 & 4: source deviation < 30%
        dev12_str = '-'
        dev13_str = '-'
        if src_count >= 2:
            v1 = srcs[0]['value']
            v2 = srcs[1]['value']
            dev12 = _deviation_pct(v1, v2)
            dev12_str = f'{dev12:.1f}%'
            if dev12 > MAX_DEVIATION_PCT:
                status_parts.append(f'FAIL:S1-S2={dev12:.1f}%>{MAX_DEVIATION_PCT}%')
                row_fail = True

        if src_count >= 3:
            v1 = srcs[0]['value']
            v2 = srcs[1]['value']
            v3 = srcs[2]['value']
            dev13 = _deviation_pct(v1, v3)
            dev13_str = f'{dev13:.1f}%'
            if dev13 > MAX_DEVIATION_PCT:
                status_parts.append(f'FAIL:S1-S3={dev13:.1f}%>{MAX_DEVIATION_PCT}%')
                row_fail = True
            # Check 5: S2 vs S3 deviation < 30% -- guards against two
            # opposite-side outliers passing both pairwise-with-S1 checks
            # while diverging from each other (false PASS otherwise).
            dev23 = _deviation_pct(v2, v3)
            if dev23 > MAX_DEVIATION_PCT:
                status_parts.append(f'FAIL:S2-S3={dev23:.1f}%>{MAX_DEVIATION_PCT}%')
                row_fail = True

        if row_fail:
            status = 'FAIL: ' + '; '.join(status_parts)
            fails += 1
        else:
            status = 'PASS'
            passes += 1

        rows.append((name, pkg, rth, src_count, dev12_str, dev13_str, status))

    return passes, fails, skips, rows


def print_table(board_name: str, rows: list) -> None:
    """Print formatted audit table for one board."""
    if not rows:
        print(f'  (no thermal components)')
        return

    # Column widths
    hdr = ('Component', 'Package', 'Rth_ja', 'Srcs', 'S1-S2', 'S1-S3', 'Status')
    w = [
        max(len(hdr[0]), max(len(r[0]) for r in rows)),
        max(len(hdr[1]), max(len(r[1]) for r in rows)),
        max(len(hdr[2]), 8),
        max(len(hdr[3]), 4),
        max(len(hdr[4]), max(len(str(r[4])) for r in rows)),
        max(len(hdr[5]), max(len(str(r[5])) for r in rows)),
        max(len(hdr[6]), max(len(str(r[6])) for r in rows)),
    ]
    def _row(vals):
        return '  ' + '  '.join(
            f'{str(vals[i]):<{w[i]}}' if i < 2 else f'{str(vals[i]):>{w[i]}}'
            for i in range(len(w))
        )
    sep = '  ' + '-' * (sum(w) + 2 * (len(w) - 1))
    print(_row(hdr))
    print(sep)
    for r in rows:
        rth_str = f'{r[2]:.1f}' if r[2] > 0 else '-'
        print(_row((r[0], r[1], rth_str, r[3], r[4], r[5], r[6])))


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Audit IC-level Rth_ja thermal resistance data across PCB specs.',
    )
    parser.add_argument(
        '--strict', action='store_true',
        help='Strict mode for CI: components with thermal data but no rth_ja count as FAIL.',
    )
    args = parser.parse_args()

    total_pass = 0
    total_fail = 0
    total_skip = 0

    print('=' * 72)
    print('ADR-10 Rth_ja Thermal Resistance Audit')
    print(f'Mode: {"STRICT (CI)" if args.strict else "normal"}')
    print('=' * 72)

    for board_name, spec in BOARDS:
        print(f'\n--- {board_name} ({spec.name}) ---')
        p, f, s, rows = audit_board(board_name, spec, args.strict)
        print_table(board_name, rows)
        print(f'  => pass={p}  fail={f}  skip={s}')
        total_pass += p
        total_fail += f
        total_skip += s

    print('\n' + '=' * 72)
    print(f'TOTAL: pass={total_pass}  fail={total_fail}  skip={total_skip}')
    if total_fail > 0:
        print('RESULT: FAIL')
    else:
        print('RESULT: PASS')
    print('=' * 72)

    return 1 if total_fail > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
