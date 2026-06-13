"""test_no_stale_extra_ports.py — 預防機制(2026-06-06)。

extra_ports 不得與 on_board_components 撞 label。撞名 = stale 重複:同一子元件被
在 _ui_hints.extra_ports 用舊手設 cx/cy 又定義一次,deriver 會以它蓋過 datasheet
on_board_components 的 bbox 位置 → render drift(曾致 34 個子元件、最大 40mm 偏移)。

datasheet on_board_components(x/y/w/h)為子元件位置的**唯一真值**;邏輯 port(WIRES 等)
才放 extra_ports,且其 label 不得與任何 on_board_components label 相同。

配套:scripts/derive_component_dimensions.py 的 VS-DEDUP guard(datasheet 優先)讓 render
即使有 dup 也不漂移;本測試是把該類 data bug **大聲 surface** 的 CI 紅線(no-silent-fallback)。
"""
import json
from pathlib import Path

SSOT = Path(__file__).resolve().parent.parent / "data" / "component_datasheet_verified.json"


def test_no_extra_port_collides_with_on_board_component():
    ssot = json.loads(SSOT.read_text(encoding="utf-8"))
    offenders: dict[str, list[str]] = {}
    for cls, spec in ssot.items():
        if not isinstance(spec, dict):
            continue
        obc = {
            (s.get("label") or s.get("name"))
            for s in spec.get("on_board_components", [])
        }
        eps = spec.get("_ui_hints", {}).get("extra_ports", [])
        dup = sorted({e.get("label") for e in eps if e.get("label") in obc})
        if dup:
            offenders[cls] = dup
    assert not offenders, (
        "extra_ports 與 on_board_components 撞 label(stale 重複,datasheet 應為唯一真值):\n"
        + "\n".join(f"  {c}: {d}" for c, d in offenders.items())
    )
