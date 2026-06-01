"""test_verification.py — Verification Spine 報告框架 + L0 完整性檢查測試。"""
import json

import numpy as np
import trimesh
from PIL import Image

from lib.verification import (
    check_svg, check_png, check_mesh,
    CheckResult, VerificationReport, Verdict,
)


# ── 報告聚合規則 ─────────────────────────────────────────────
class TestReportAggregation:
    def test_all_pass(self):
        r = VerificationReport("a", "svg")
        r.add(CheckResult("L0", "x", Verdict.PASS))
        r.add(CheckResult("L1", "y", Verdict.PASS))
        assert r.verdict == Verdict.PASS
        assert r.exit_code() == 0

    def test_blocking_fail_blocks(self):
        r = VerificationReport("a", "mesh")
        r.add(CheckResult("L1", "watertight", Verdict.FAIL))
        assert r.verdict == Verdict.FAIL
        assert r.exit_code() == 1

    def test_l0_fail_blocks(self):
        r = VerificationReport("a", "png")
        r.add(CheckResult("L0", "non_blank", Verdict.FAIL))
        assert r.verdict == Verdict.FAIL

    def test_nonblocking_fail_does_not_block(self):
        r = VerificationReport("a", "svg")
        r.add(CheckResult("L2", "overlap", Verdict.FAIL))
        assert r.verdict == Verdict.PASS          # L2 不擋 gate
        assert r.has_nonblocking_fail is True
        assert r.exit_code() == 0
        assert r.exit_code(strict=True) == 1      # strict 模式才擋

    def test_counts(self):
        r = VerificationReport("a", "svg")
        r.add(CheckResult("L0", "x", Verdict.PASS))
        r.add(CheckResult("L1", "y", Verdict.FAIL))
        r.add(CheckResult("L2", "z", Verdict.WARN))
        assert r.counts() == {"PASS": 1, "FAIL": 1, "WARN": 1}

    def test_to_json_roundtrip(self):
        r = VerificationReport("a", "svg")
        r.add(CheckResult("L0", "x", Verdict.PASS, metric={"n": 5}))
        d = json.loads(r.to_json())
        assert d["verdict"] == "PASS"
        assert d["checks"][0]["metric"]["n"] == 5

    def test_render_text_contains_artifact(self):
        r = VerificationReport("foo.stl", "mesh")
        r.add(CheckResult("L0", "loadable", Verdict.PASS))
        txt = r.render_text()
        assert "foo.stl" in txt
        assert "L0 loadable" in txt


# ── L0 SVG ───────────────────────────────────────────────────
class TestCheckSVG:
    def test_valid_svg_string_passes(self):
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" '
               'viewBox="0 0 10 10"><rect x="1" y="1" width="2" height="2"/></svg>')
        assert check_svg(svg).verdict == Verdict.PASS

    def test_malformed_svg_fails(self):
        assert check_svg("<svg><rect></svg>").verdict == Verdict.FAIL

    def test_empty_svg_fails(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
        assert check_svg(svg).verdict == Verdict.FAIL  # 無子節點 + 無尺寸

    def test_real_schematic_passes(self):
        from lib.schematic import generate_svg
        svg = generate_svg("Arduino", "USB-5V", ["LED_Single"], ["PIR"])
        assert check_svg(svg).verdict == Verdict.PASS


# ── L0 PNG ───────────────────────────────────────────────────
class TestCheckPNG:
    def test_blank_white_image_fails(self, tmp_path):
        p = tmp_path / "blank.png"
        Image.new("RGB", (64, 64), (255, 255, 255)).save(p)
        assert check_png(str(p)).verdict == Verdict.FAIL

    def test_blank_black_image_fails(self, tmp_path):
        p = tmp_path / "black.png"
        Image.new("RGB", (64, 64), (0, 0, 0)).save(p)
        assert check_png(str(p)).verdict == Verdict.FAIL

    def test_content_image_passes(self, tmp_path):
        p = tmp_path / "content.png"
        rng = np.random.default_rng(0)
        arr = (rng.random((64, 64, 3)) * 255).astype("uint8")
        Image.fromarray(arr).save(p)
        assert check_png(str(p)).verdict == Verdict.PASS

    def test_missing_file_fails(self, tmp_path):
        assert check_png(str(tmp_path / "nope.png")).verdict == Verdict.FAIL


# ── L0 Mesh ──────────────────────────────────────────────────
class TestCheckMesh:
    def test_valid_box_passes(self, tmp_path):
        p = tmp_path / "box.stl"
        trimesh.creation.box(extents=(10, 10, 10)).export(str(p))
        assert check_mesh(str(p)).verdict == Verdict.PASS

    def test_missing_file_fails(self, tmp_path):
        assert check_mesh(str(tmp_path / "nope.stl")).verdict == Verdict.FAIL

    def test_degenerate_flat_mesh_fails(self, tmp_path):
        p = tmp_path / "flat.stl"
        verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
        faces = np.array([[0, 1, 2]])
        trimesh.Trimesh(vertices=verts, faces=faces, process=False).export(str(p))
        assert check_mesh(str(p)).verdict == Verdict.FAIL  # z extent = 0
