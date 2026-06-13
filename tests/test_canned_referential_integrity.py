"""tests/test_canned_referential_integrity.py — P0.6：canned 參照完整性 + unmapped fail-loud 鎖。

緣由:規劃書 P0.6 原據 audit「Chassis-Car 未註冊 SSOT、direction 驗證被靜默 skip」。實查更正:
  - Chassis-Car-class **在** SSOT(audit 把「不在 wiring _SHORT_TO_CLASS」誤當「未註冊 SSOT」;
    它屬結構 Housing 無電氣 pin,正確排除於 wiring 映射)。
  - `validate.py:285-297` 對 unmapped class **已 fail-loud**(surface error issue,非靜默)。
故原 premise 已被既有碼解掉。本檔改提供兩個**真實新防禦**:
  (1) 每個 canned template 引用的 *-class 必在 SSOT(防 demo 引用 typo/缺失 class 的靜默斷裂)。
  (2) 回歸鎖:unmapped class → validate_wiring 必 surface error(防 fail-loud 被改回靜默)。
"""
import json
from pathlib import Path

import pytest

from lib.canned_template_defs import TEMPLATE_DEFS

_REPO = Path(__file__).resolve().parent.parent
_SSOT = set(json.loads(
    (_REPO / "data" / "component_datasheet_verified.json").read_text(encoding="utf-8")).keys())


def _collect_types(obj) -> set[str]:
    """遞迴收集 TEMPLATE_DEFS 內所有 'type' 值。"""
    found: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "type" and isinstance(v, str):
                found.add(v)
            else:
                found |= _collect_types(v)
    elif isinstance(obj, list):
        for it in obj:
            found |= _collect_types(it)
    return found


_CLASS_TYPES = sorted(t for t in _collect_types(TEMPLATE_DEFS) if t.endswith("-class"))


@pytest.mark.parametrize("cls", _CLASS_TYPES)
def test_canned_component_class_in_ssot(cls):
    """canned 引用的 *-class 必存在 SSOT(DEC-H7:不可引用無依據 class)。"""
    assert cls in _SSOT, f"canned template 引用的 class 不在 SSOT: {cls}"


def test_canned_corpus_nonempty():
    assert len(TEMPLATE_DEFS) >= 16, "canned demo 數異常少"
    assert len(_CLASS_TYPES) >= 20, "canned 引用的 class 數異常少（_collect_types 失準?）"


def test_unmapped_class_surfaces_error_not_silent():
    """回歸鎖:unmapped class(不在 _SHORT_TO_CLASS)→ validate_wiring 必 surface error,
    不可靜默 all-clear(這才是 audit 真正擔心的點;既有碼已 fail-loud,此測防回歸)。"""
    from lib.wiring.validate import validate_wiring
    issues = validate_wiring("Arduino", ["NotARealComponent-class"])
    errs = [i for i in issues if getattr(i, "severity", "") == "error"]
    assert errs, "unmapped class 未 surface error(靜默 all-clear 回歸)"
