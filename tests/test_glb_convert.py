"""test_glb_convert.py — shells STL→GLB 後處理測試。

驗證 assembly 逐模組 GLB 化（D7 修正案）：轉換正確、體積更小、保護多色 pcb_body、
缺件正常跳過、失敗禁容錯（raise）。
"""
import struct
from pathlib import Path

import pytest

trimesh = pytest.importorskip("trimesh")

from lib.cad.glb_convert import stl_to_glb, ensure_shell_glbs


def _write_box_stl(path: Path, size: float = 10.0) -> None:
    box = trimesh.creation.box(extents=(size, size, size))
    box.export(str(path), file_type="stl")


# ── stl_to_glb ───────────────────────────────────────────────
class TestStlToGlb:
    def test_creates_glb(self, tmp_path):
        stl = tmp_path / "base_stl.stl"
        _write_box_stl(stl)
        glb = tmp_path / "base.glb"
        assert stl_to_glb(stl, glb) is True
        assert glb.exists() and glb.stat().st_size > 0

    def test_glb_smaller_than_stl(self, tmp_path):
        # 用較細網格放大差距（box 太小看不出，用 icosphere 高面數）
        sph = trimesh.creation.icosphere(subdivisions=4)
        stl = tmp_path / "m_stl.stl"
        sph.export(str(stl), file_type="stl")
        glb = tmp_path / "m.glb"
        stl_to_glb(stl, glb)
        assert glb.stat().st_size < stl.stat().st_size  # 索引化更小

    def test_glb_loadable(self, tmp_path):
        stl = tmp_path / "lid_stl.stl"
        _write_box_stl(stl)
        glb = tmp_path / "lid.glb"
        stl_to_glb(stl, glb)
        loaded = trimesh.load(str(glb), file_type="glb", force="mesh")
        assert len(loaded.faces) > 0

    def test_missing_stl_raises(self, tmp_path):
        with pytest.raises(Exception):
            stl_to_glb(tmp_path / "nope.stl", tmp_path / "nope.glb")


# ── ensure_shell_glbs ────────────────────────────────────────
class TestEnsureShellGlbs:
    def _make_type(self, root: Path, name: str, files: list) -> Path:
        d = root / name
        d.mkdir(parents=True)
        for f in files:
            _write_box_stl(d / f)
        return d

    def test_converts_base_lid_mount(self, tmp_path):
        self._make_type(tmp_path, "Foo-class", ["base_stl.stl", "lid_stl.stl", "mount_stl.stl"])
        res = ensure_shell_glbs(tmp_path, types=["Foo-class"])
        names = {c.split("/")[-1] for c in res["converted"]}
        assert {"base.glb", "lid.glb", "mount.glb"} <= names
        for g in ("base.glb", "lid.glb", "mount.glb"):
            assert (tmp_path / "Foo-class" / g).exists()

    def test_missing_variant_is_skipped_not_error(self, tmp_path):
        # 只有 base，無 lid/mount → 不應報錯
        self._make_type(tmp_path, "Bar-class", ["base_stl.stl"])
        res = ensure_shell_glbs(tmp_path, types=["Bar-class"])
        assert any("base.glb" in c for c in res["converted"])

    def test_existing_glb_skipped(self, tmp_path):
        d = self._make_type(tmp_path, "Baz-class", ["base_stl.stl"])
        stl_to_glb(d / "base_stl.stl", d / "base.glb")
        res = ensure_shell_glbs(tmp_path, types=["Baz-class"])
        assert any("base.glb" in s for s in res["skipped"])
        assert not res["converted"]

    def test_pcb_body_multicolor_protected_even_with_overwrite(self, tmp_path):
        d = self._make_type(tmp_path, "Pcb-class", ["pcb_body.stl"])
        # 模擬既有多色 pcb_body.glb（內容標記）
        marker = b"MULTICOLOR_AUTHORITATIVE"
        (d / "pcb_body.glb").write_bytes(marker)
        ensure_shell_glbs(tmp_path, types=["Pcb-class"], overwrite=True)
        assert (d / "pcb_body.glb").read_bytes() == marker  # 未被覆蓋

    def test_pcb_body_converted_when_glb_absent(self, tmp_path):
        self._make_type(tmp_path, "PcbNo-class", ["pcb_body.stl"])
        res = ensure_shell_glbs(tmp_path, types=["PcbNo-class"])
        assert any("pcb_body.glb" in c for c in res["converted"])

    def test_bad_stl_raises(self, tmp_path):
        d = tmp_path / "Broken-class"
        d.mkdir()
        (d / "base_stl.stl").write_bytes(b"not a real stl")
        with pytest.raises(RuntimeError, match="禁容錯"):
            ensure_shell_glbs(tmp_path, types=["Broken-class"])
