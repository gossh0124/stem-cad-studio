"""P4.2/DEC-H7 prevention gate:class 有 pin_layout.header_groups(SSOT)時,禁手刻腳位表。

2026-06-11 ground truth 更正:audit 的「COMP_PINS 0 違規」是 compKey('SoilMoisture')
vs class 名('Sensor-SoilMoisture-class')命名空間假綠;經 COMPKEY_TO_CLASS 橋接後
23/23 entry 全都有 header_groups SSOT → 已 purge(comp-specs.js 表+export、
elk-layout.js 全部消費點)。本 gate 鎖永不重生(名稱由 provenance_baseline.json
COMP_RENDERERS locus 的 purge_plan 預先註冊):

- comp-specs.js 重建 COMP_PINS 且 key 的 class 有 header_groups → FAIL
- key 查無 COMPKEY_TO_CLASS 對映 → fail-closed FAIL(防改 key 名繞過;無法證明無 SSOT)
- elk-layout.js 重新消費 COMP_PINS → FAIL
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))  # 同 test_provenance_lint.py 模式
import provenance_lint as _pl  # noqa: E402  (重用 _extract_block 括號配對)

from scripts.derive_schematic_pins import COMPKEY_TO_CLASS  # noqa: E402

_COMP_SPECS_JS = ROOT / "v6" / "schematic" / "comp-specs.js"
_ELK_LAYOUT_JS = ROOT / "v6" / "schematic" / "elk-layout.js"
_VERIFIED = ROOT / "data" / "component_datasheet_verified.json"

_MARKER = "const COMP_PINS = {"
_KEY_RE = re.compile(r"^\s*['\"]?([\w+-]+)['\"]?:\s*\{", re.M)


def _load_verified() -> dict:
    d = json.loads(_VERIFIED.read_text(encoding="utf-8"))
    return d.get("components", d) if isinstance(d, dict) else {}


def comp_pins_violations(js_text: str, verified: dict) -> list[str]:
    """回傳手刻 COMP_PINS 的違規清單(空 = 無表或無 SSOT 重疊)。

    fail-closed:key 無 COMPKEY_TO_CLASS 對映也算違規(無法證明該 key 無 SSOT 資料,
    防「改 key 名繞過 gate」)。
    """
    if _MARKER not in js_text:
        return []  # 已 purge(穩態)
    block = _pl._extract_block(js_text, _MARKER)
    violations: list[str] = []
    for key in _KEY_RE.findall(block):
        cls = COMPKEY_TO_CLASS.get(key)
        if cls is None:
            violations.append(
                f"COMP_PINS['{key}'] 無 COMPKEY_TO_CLASS 對映(fail-closed:"
                f"請改用 SCHEM_PINS/derive_schematic_pins,勿手填)")
            continue
        hg = (verified.get(cls, {}).get("pin_layout") or {}).get("header_groups")
        if hg:
            violations.append(
                f"COMP_PINS['{key}'] 手刻腳位,但 {cls} 已有 pin_layout."
                f"header_groups SSOT — 應走 scripts/derive_schematic_pins.py 衍生")
    return violations


class TestPreventionGate:
    def test_comp_pins_absent_or_no_ssot_overlap(self):
        """生產檔穩態:COMP_PINS 已 purge(或殘留 entry 全無 SSOT 重疊)。"""
        text = _COMP_SPECS_JS.read_text(encoding="utf-8")
        violations = comp_pins_violations(text, _load_verified())
        assert violations == [], "\n".join(violations)

    def test_elk_layout_does_not_consume_comp_pins(self):
        """消費端鎖:elk-layout.js 不得再讀 window.COMP_PINS / COMP_PINS[...]。"""
        text = _ELK_LAYOUT_JS.read_text(encoding="utf-8")
        hits = [
            f"L{i}: {ln.strip()}"
            for i, ln in enumerate(text.splitlines(), 1)
            if re.search(r"window\.COMP_PINS|COMP_PINS\s*\[|COMP_PINS\?\.", ln)
        ]
        assert hits == [], "elk-layout.js 重新消費 COMP_PINS:\n" + "\n".join(hits)


class TestGateNotFalseGreen:
    """meta-gate:故意重建手填表,gate 必須抓到(防 no-op 假綠)。"""

    def test_reintroduced_table_with_ssot_class_fails(self):
        mutant = "const COMP_PINS = {\n  Relay: { VCC:[0,.12], IN:[0,.5] },\n};\n"
        v = comp_pins_violations(mutant, _load_verified())
        assert v and "Relay-Module-class" in v[0], v

    def test_unmapped_key_fails_closed(self):
        mutant = "const COMP_PINS = {\n  FooBar9000: { X:[0,.5] },\n};\n"
        v = comp_pins_violations(mutant, _load_verified())
        assert v and "fail-closed" in v[0], v

    def test_purged_text_passes(self):
        assert comp_pins_violations("// no table here\n", _load_verified()) == []
