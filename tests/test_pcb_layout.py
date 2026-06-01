"""test_pcb_layout.py — VS-PCB 前端佈局 vs 後端 SSOT 對照（純函數）。"""
from lib.verification import audit_pcb_layout, Verdict


def _m(label, fx, fy, sx, sy, fw=None, fh=None, sw=None, sh=None):
    return {"label": label, "fx": fx, "fy": fy, "sx": sx, "sy": sy,
            "fw": fw, "fh": fh, "sw": sw, "sh": sh}


class TestAuditPcbLayout:
    def test_perfect_match_passes(self):
        matched = [_m("A", 10, 10, 10, 10), _m("B", 20, 20, 20.5, 19.8)]
        assert audit_pcb_layout(matched, [], []).verdict == Verdict.PASS

    def test_missing_component_fails(self):
        # 後端有前端無 → L1 FAIL（漏畫）
        rpt = audit_pcb_layout([], [], ["Cap-PC1", "Resonator"])
        assert rpt.verdict == Verdict.FAIL

    def test_position_offset_fails(self):
        matched = [_m("LED", 11.5, 20, 58.4, 36)]  # dx 46.9
        rpt = audit_pcb_layout(matched, [], [], pos_tol_mm=5.0)
        assert rpt.verdict == Verdict.FAIL

    def test_position_within_tol_passes(self):
        matched = [_m("MH", 14.3, 4.5, 13.97, 2.54)]  # dx0.33 dy1.96 < 5
        assert audit_pcb_layout(matched, [], [], pos_tol_mm=5.0).verdict == Verdict.PASS

    def test_extra_component_warns_not_blocks(self):
        # 前端多出 → L2 WARN，不擋 gate
        rpt = audit_pcb_layout([], ["LP2985-3V3"], [])
        assert rpt.verdict == Verdict.PASS
        assert rpt.has_nonblocking_fail is False  # WARN 非 FAIL

    def test_footprint_offset_warns(self):
        # 尺寸偏差 → L2 WARN（不擋）
        matched = [_m("ATmega", 10, 10, 10, 10, fw=35.6, fh=10, sw=35.6, sh=7.6)]
        rpt = audit_pcb_layout(matched, [], [], size_tol_mm=2.0)
        assert rpt.verdict == Verdict.PASS  # 僅 footprint 偏 → WARN 不擋
        # 但應記錄到 footprint check
        fc = [c for c in rpt.checks if c.name == "footprint_within_tol"]
        assert fc and fc[0].verdict == Verdict.WARN

    def test_footprint_within_tol_passes(self):
        matched = [_m("X", 10, 10, 10, 10, fw=35.6, fh=7.6, sw=35.6, sh=7.0)]
        rpt = audit_pcb_layout(matched, [], [], size_tol_mm=2.0)
        fc = [c for c in rpt.checks if c.name == "footprint_within_tol"]
        assert fc and fc[0].verdict == Verdict.PASS
