"""test_contract.py — VS-IC 前後端介接契約測試。"""
import json
from pathlib import Path

from lib.verification import check_cad_output_contract, check_model_registry, check_scene_graph_meshes, Verdict

ROOT = Path(__file__).resolve().parents[1]


def _canned(name: str) -> dict:
    return json.loads((ROOT / "v6" / "canned" / f"{name}.json").read_text(encoding="utf-8"))


def _valid_module() -> dict:
    return {"position": [1.0, 2.0, 3.0], "dimensions": [30.0, 24.0, 25.0], "type": "Sensor-PIR-class"}


class TestContract:
    def test_real_canned_passes(self):
        rpt = check_cad_output_contract(_canned("auto_waterer"))
        assert rpt.verdict == Verdict.PASS, rpt.render_text()

    def test_valid_synthetic_passes(self):
        b = {"cad_output": {"scene_graph_v3": {"modules": [_valid_module()]}}}
        assert check_cad_output_contract(b).verdict == Verdict.PASS

    def test_no_cad_output_fails(self):
        assert check_cad_output_contract({"project_name": "x"}).verdict == Verdict.FAIL

    def test_empty_placements_fails(self):
        b = {"cad_output": {"scene_graph_v3": {"modules": []}}}
        assert check_cad_output_contract(b).verdict == Verdict.FAIL

    def test_missing_field_fails(self):
        m = _valid_module()
        del m["dimensions"]
        b = {"cad_output": {"scene_graph_v3": {"modules": [m]}}}
        assert check_cad_output_contract(b).verdict == Verdict.FAIL

    def test_nonnumeric_coord_fails(self):
        m = _valid_module()
        m["position"][0] = "oops"
        b = {"cad_output": {"scene_graph_v3": {"modules": [m]}}}
        assert check_cad_output_contract(b).verdict == Verdict.FAIL

    def test_not_dict_fails(self):
        assert check_cad_output_contract(None).verdict == Verdict.FAIL


class TestModelRegistry:
    """VS-IC ①: registry.json 每筆 file 對應 .step 存在且非空。"""

    def test_real_registry_passes(self):
        rpt = check_model_registry()
        assert rpt.verdict == Verdict.PASS, rpt.render_text()

    def _reg(self, tmp_path, data: dict) -> Path:
        p = tmp_path / "registry.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_present_file_passes(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/x.step"}]})
        comp = tmp_path / "components" / "ic-dip"
        comp.mkdir(parents=True)
        (comp / "x.step").write_text("SOLID", encoding="utf-8")
        rpt = check_model_registry(registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.PASS

    def test_missing_file_fails(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/nope.step"}]})
        rpt = check_model_registry(registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.FAIL

    def test_empty_file_fails(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/x.step"}]})
        comp = tmp_path / "components" / "ic-dip"
        comp.mkdir(parents=True)
        (comp / "x.step").write_text("", encoding="utf-8")  # 0 byte
        rpt = check_model_registry(registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.FAIL

    def test_missing_file_key_fails(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8}]})  # 無 file 欄位
        rpt = check_model_registry(registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.FAIL

    def test_underscore_keys_skipped(self, tmp_path):
        reg = self._reg(tmp_path, {"_doc": "x", "_total_models": 5})
        rpt = check_model_registry(registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.PASS


class TestSceneGraphMeshes:
    """VS-IC ②: scene_graph_v3 mesh ref → registry key 驗證。"""

    def _reg(self, tmp_path: Path, data: dict) -> Path:
        p = tmp_path / "registry.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def _sg(self, modules: list) -> dict:
        """建立最小 scene_graph_v3 結構。"""
        return {"version": "v3", "modules": modules}

    # ── 合法 mesh ref 全 PASS ───────────────────────────────
    def test_scene_graph_valid_meshes(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/dip-8.step"}]})
        sg = self._sg([
            {"id": "U1", "type": "ic-dip", "meshes": [
                {"variant": "dip-8", "url": "ic-dip/dip-8.glb", "format": "glb"}
            ]}
        ])
        # 不傳 models_root 檔案存在性；只驗 registry 對應
        comp_root = tmp_path / "components"
        comp_root.mkdir()
        (comp_root / "ic-dip").mkdir()
        (comp_root / "ic-dip" / "dip-8.glb").write_text("BINARY", encoding="utf-8")
        rpt = check_scene_graph_meshes(sg, registry_path=reg, models_root=comp_root)
        assert rpt.verdict == Verdict.PASS, rpt.render_text()

    # ── 未知 shape → FAIL ───────────────────────────────────
    def test_scene_graph_missing_shape(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/dip-8.step"}]})
        sg = self._sg([
            {"id": "X1", "type": "mystery-ic", "meshes": [
                {"variant": "x", "url": "mystery-ic/x.glb", "format": "glb"}
            ]}
        ])
        rpt = check_scene_graph_meshes(sg, registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.FAIL, rpt.render_text()
        names = [c.name for c in rpt.checks if c.verdict.value == "FAIL"]
        assert "mesh_shape_in_registry" in names

    # ── 空 URL → FAIL ───────────────────────────────────────
    def test_scene_graph_empty_url(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/dip-8.step"}]})
        sg = self._sg([
            {"id": "U2", "type": "ic-dip", "meshes": [
                {"variant": "dip-8", "url": "", "format": "glb"}
            ]}
        ])
        rpt = check_scene_graph_meshes(sg, registry_path=reg, models_root=tmp_path / "components")
        assert rpt.verdict == Verdict.FAIL, rpt.render_text()
        names = [c.name for c in rpt.checks if c.verdict.value == "FAIL"]
        assert "mesh_url_nonempty" in names

    # ── 無 modules → PASS（無可驗對象）──────────────────────
    def test_scene_graph_no_modules(self, tmp_path):
        reg = self._reg(tmp_path, {"ic-dip": [{"pins": 8, "file": "ic-dip/dip-8.step"}]})
        for sg in [
            {},                            # 完全空
            {"version": "v3"},             # 無 modules key
            {"version": "v3", "modules": []},  # 空 modules
        ]:
            rpt = check_scene_graph_meshes(sg, registry_path=reg, models_root=tmp_path / "components")
            assert rpt.verdict == Verdict.PASS, f"應 PASS 但 FAIL：{sg!r}\n{rpt.render_text()}"
