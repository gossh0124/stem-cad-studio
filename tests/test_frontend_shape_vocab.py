"""test_frontend_shape_vocab.py — 預防機制:SSOT 的每個 frontend_shape.shape
必須存在於渲染器 lookup map(v6/engineer/shapes-*.js 的 __IC_CONN_SHAPES /
__PASSIVE_MECH_SHAPES)。

防止「在 SSOT _ui_hints.frontend_shape 引用一個渲染器沒有 builder 的 shape」——
那會讓 3D 渲染靜默畫不出該子元件(等同 no-silent-fallback 違反)。

SOURCE: 渲染器 lookup map = 唯一權威 shape vocab。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SSOT = ROOT / "data" / "component_datasheet_verified.json"
SHAPE_FILES = [
    ROOT / "v6" / "engineer" / "shapes-ic-conn.js",
    ROOT / "v6" / "engineer" / "shapes-passive-mech.js",
]


def _renderer_vocab() -> set[str]:
    vocab: set[str] = set()
    for f in SHAPE_FILES:
        txt = f.read_text(encoding="utf-8")
        # lookup map entries:  'shape-name': buildXxx,
        for m in re.finditer(r"'([a-z][a-z0-9-]+)'\s*:\s*build", txt):
            vocab.add(m.group(1))
    return vocab


def _used_shapes() -> dict[str, set[str]]:
    ssot = json.loads(SSOT.read_text(encoding="utf-8"))
    used: dict[str, set[str]] = {}
    for cls, spec in ssot.items():
        if not isinstance(spec, dict):
            continue
        fs = spec.get("_ui_hints", {}).get("frontend_shape", {})
        for label, info in fs.items():
            if isinstance(info, dict) and "shape" in info:
                used.setdefault(info["shape"], set()).add(f"{cls}/{label}")
    return used


def test_every_frontend_shape_exists_in_renderer():
    vocab = _renderer_vocab()
    assert vocab, "renderer vocab empty — shapes-*.js lookup map parse failed"
    used = _used_shapes()
    missing = {s: sorted(refs) for s, refs in used.items() if s not in vocab}
    assert not missing, (
        "frontend_shape 引用了渲染器沒有的 shape(no-silent-fallback 違反):\n"
        + "\n".join(f"  '{s}' used by {refs}" for s, refs in missing.items())
        + f"\n  renderer vocab = {sorted(vocab)}"
    )
