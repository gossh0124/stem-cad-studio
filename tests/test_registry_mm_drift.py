"""REGISTRY_MM drift gate（SCHEM-DEMO-1 Wave A）。

schematic 節點 mm 尺寸（v6/data/component-dimensions.js window.REGISTRY_MM）
須與 verified.json physical 零漂移；手改前端表或改 verified.json 未重跑
derive_schematic_tables.py --write 即觸發此 gate。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from scripts.derive_schematic_tables import SCHEM_MAP, derive, parse_current  # noqa: E402


def test_registry_mm_matches_verified():
    derived = derive()
    current = parse_current()
    for key in SCHEM_MAP:
        assert key in current, f"{key}: 前端 REGISTRY_MM 缺項"
        assert abs(derived[key][0] - current[key][0]) <= 1e-6, \
            f"{key} length drift: derived={derived[key]} vs js={current[key]}"
        assert abs(derived[key][1] - current[key][1]) <= 1e-6, \
            f"{key} width drift: derived={derived[key]} vs js={current[key]}"
