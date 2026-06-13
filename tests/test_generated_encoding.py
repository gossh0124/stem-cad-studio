"""tests/test_generated_encoding.py — P0.8：生成檔須 UTF-8 無 BOM（CP950 機器鐵則）。

CLAUDE.md：寫給別的工具讀的檔一律 UTF-8 無 BOM。derive 出的 .js 資料檔餵 node/前端;
帶 BOM 會讓 native 消費端炸或亂碼。本 gate 防 deriver 回歸到 Set-Content/Out-File(帶 BOM)。
"""
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_BOM = b"\xef\xbb\xbf"

# 明列的 deriver 輸出 + 自動涵蓋 v6/data 內標 AUTO-GENERATED 的生成檔。
_EXPLICIT = [
    "v6/data/schematic-pins.js",
    "v6/data/component-dimensions.js",
]


def _discover() -> list[str]:
    rels = set(_EXPLICIT)
    for p in (_REPO / "v6" / "data").glob("*.js"):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:200]
        except OSError:
            continue
        if "AUTO-GENERATED" in head or "AUTO GENERATED" in head:
            rels.add(p.relative_to(_REPO).as_posix())
    return sorted(rels)


@pytest.mark.parametrize("rel", _discover())
def test_generated_file_is_utf8_no_bom(rel):
    p = _REPO / rel
    if not p.exists():
        pytest.skip(f"{rel} 不存在")
    raw = p.read_bytes()
    assert not raw.startswith(_BOM), (
        f"{rel} 有 UTF-8 BOM(CP950 機器禁;用 Write 工具或 UTF8Encoding($false) 重生)")
    # 不可解碼為 UTF-8 → 拋例外 = fail（fail-closed）
    raw.decode("utf-8")
