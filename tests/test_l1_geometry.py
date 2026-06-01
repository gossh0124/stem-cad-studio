"""test_l1_geometry.py — VS-3D-Z 殘留碰撞驗證（純判定）。"""
import json
from pathlib import Path

from lib.verification import check_placement_collisions, Verdict

ROOT = Path(__file__).resolve().parents[1]


def _pl(t: str, x: float, y: float, L: float, W: float, rel: str = "internal") -> dict:
    return {"type": t, "role": "Sensor", "x": x, "y": y, "L": L, "W": W,
            "H": 10.0, "enclosure_relation": rel}


class TestPlacementCollisions:
    def test_no_overlap_passes(self):
        pls = [_pl("A", 0, 0, 10, 10), _pl("B", 20, 20, 10, 10)]
        assert check_placement_collisions(pls).verdict == Verdict.PASS

    def test_overlap_fails(self):
        pls = [_pl("A", 0, 0, 20, 20), _pl("B", 5, 5, 20, 20)]
        rpt = check_placement_collisions(pls)
        assert rpt.verdict == Verdict.FAIL

    def test_empty_passes(self):
        assert check_placement_collisions([]).verdict == Verdict.PASS

    def test_panel_relation_skipped(self):
        # panel 元件貼殼面，不在 internal x/y 平面驗證範圍
        pls = [_pl("A", 0, 0, 20, 20, "panel"), _pl("B", 5, 5, 20, 20, "panel")]
        assert check_placement_collisions(pls).verdict == Verdict.PASS

    def test_touching_edge_not_overlap(self):
        # 邊緣相接（重疊量=0）不算碰撞
        pls = [_pl("A", 0, 0, 10, 10), _pl("B", 10, 0, 10, 10)]
        assert check_placement_collisions(pls).verdict == Verdict.PASS

    def test_missing_fields_skipped_gracefully(self):
        # 欄位不全不應 crash（交由 contract 契約負責），視為無法判定→不誤報
        pls = [{"type": "A", "x": 0, "y": 0}, {"type": "B", "x": 5, "y": 5}]
        rpt = check_placement_collisions(pls)
        assert rpt.verdict == Verdict.PASS

    def test_real_canned_no_overlap(self):
        b = json.loads((ROOT / "v6" / "canned" / "auto_waterer.json").read_text(encoding="utf-8"))
        pls = b["cad_output"]["component_placements"]
        rpt = check_placement_collisions(pls)
        assert rpt.verdict == Verdict.PASS, rpt.render_text()
