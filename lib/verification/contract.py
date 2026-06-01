"""lib/verification/contract.py — VS-IC 前後端介接契約驗證。

驗證後端 bridge 給前端 3D 渲染的必要欄位齊全且型別正確，
堵住「後端產出對、前端讀不到欄位、靜默 fallback 成 ghost box」。

對象：bridge["cad_output"]["component_placements"]——
前端 assembly 渲染（views-engineer-assembly）逐欄讀取此清單擺放元件。
欄位缺漏 → 前端 fallback/錯位；座標非數值 → NaN/重疊。

CLI：python -m lib.verification.contract  → 掃 v6/canned 所有 bridge 印契約狀態。
"""
from __future__ import annotations

import json
from pathlib import Path

from .report import CheckResult, VerificationReport, Verdict

_MODELS_ROOT = Path(__file__).resolve().parents[2] / "v6" / "models"

# 前端 assembly 渲染逐筆讀取的 placement 欄位（來源：cad_output 實測 + scene 擺放需求）
_PLACEMENT_REQUIRED = ("type", "role", "x", "y", "L", "W", "H", "face_out")
_PLACEMENT_NUMERIC = ("x", "y", "L", "W", "H")


def check_cad_output_contract(bridge: dict, *, name: str | None = None) -> VerificationReport:
    """驗證 bridge.cad_output 對前端渲染的介接契約。"""
    label = name or (bridge.get("project_name") if isinstance(bridge, dict) else None) or "<bridge>"
    rpt = VerificationReport(artifact=label, artifact_type="cad_output")

    if not isinstance(bridge, dict):
        rpt.add(CheckResult("L1", "bridge_is_dict", Verdict.FAIL, message="bridge 非 dict"))
        return rpt

    co = bridge.get("cad_output")
    if not isinstance(co, dict):
        rpt.add(CheckResult("L1", "cad_output_present", Verdict.FAIL,
                            message="bridge 無 cad_output dict（前端無資料可渲染）"))
        return rpt
    rpt.add(CheckResult("L1", "cad_output_present", Verdict.PASS))

    placements = co.get("component_placements")
    if not isinstance(placements, list) or not placements:
        n = len(placements) if isinstance(placements, list) else 0
        rpt.add(CheckResult("L1", "placements_present", Verdict.FAIL,
                            message="component_placements 缺失或空", metric={"n": n}))
        return rpt
    rpt.add(CheckResult("L1", "placements_present", Verdict.PASS, metric={"n": len(placements)}))

    # 欄位齊全
    missing: dict = {}
    nonnumeric: dict = {}
    for p in placements:
        if not isinstance(p, dict):
            missing["<not-dict>"] = missing.get("<not-dict>", 0) + 1
            continue
        for f in _PLACEMENT_REQUIRED:
            if f not in p:
                missing[f] = missing.get(f, 0) + 1
        for f in _PLACEMENT_NUMERIC:
            v = p.get(f)
            if v is not None and not isinstance(v, (int, float)):
                nonnumeric[f] = nonnumeric.get(f, 0) + 1

    if missing:
        rpt.add(CheckResult("L1", "placement_fields_complete", Verdict.FAIL,
                            message="placement 欄位缺漏（前端渲染會 fallback/錯位）",
                            metric=missing))
    else:
        rpt.add(CheckResult("L1", "placement_fields_complete", Verdict.PASS,
                            metric={"checked_fields": len(_PLACEMENT_REQUIRED)}))

    if nonnumeric:
        rpt.add(CheckResult("L1", "placement_numeric_types", Verdict.FAIL,
                            message="座標/尺寸欄位非數值（前端會 NaN/重疊）", metric=nonnumeric))
    else:
        rpt.add(CheckResult("L1", "placement_numeric_types", Verdict.PASS))

    return rpt


def check_model_registry(registry_path: Path | None = None,
                         models_root: Path | None = None) -> VerificationReport:
    """VS-IC: 驗證 v6/models/registry.json 每筆 file 對應 .step 模型存在且非空。

    registry.json 的 file 路徑相對於 **v6/models/components/**（非 v6/models/）。
    路徑對不上 → 前端 mesh 載入鏈斷、靜默退 ghost box（VS-FE），故須靜態 gate。
    """
    reg_path = Path(registry_path) if registry_path else (_MODELS_ROOT / "registry.json")
    comp_root = Path(models_root) if models_root else (_MODELS_ROOT / "components")
    rpt = VerificationReport(artifact="registry.json", artifact_type="model_registry")

    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        rpt.add(CheckResult("L1", "registry_loadable", Verdict.FAIL, message=f"無法載入：{exc}"))
        return rpt
    rpt.add(CheckResult("L1", "registry_loadable", Verdict.PASS))

    missing: list = []
    empty: list = []
    no_file_key = 0
    n_total = 0
    for key, variants in reg.items():
        if key.startswith("_") or not isinstance(variants, list):
            continue
        for v in variants:
            if not isinstance(v, dict):
                continue
            f = v.get("file")
            if not f:
                no_file_key += 1
                continue
            n_total += 1
            fp = comp_root / f
            if not fp.exists():
                missing.append(f)
            elif fp.stat().st_size == 0:
                empty.append(f)

    if no_file_key:
        rpt.add(CheckResult("L1", "registry_file_key", Verdict.FAIL,
                            message="部分 variant 缺 file 欄位", metric={"n": no_file_key}))
    else:
        rpt.add(CheckResult("L1", "registry_file_key", Verdict.PASS))

    if missing:
        rpt.add(CheckResult("L1", "registry_files_exist", Verdict.FAIL,
                            message="registry 宣告的 .step 不存在（前端 mesh 鏈會斷）",
                            metric={"n_missing": len(missing), "examples": missing[:5]}))
    elif empty:
        rpt.add(CheckResult("L1", "registry_files_exist", Verdict.FAIL,
                            message="registry .step 檔為空",
                            metric={"n_empty": len(empty), "examples": empty[:5]}))
    else:
        rpt.add(CheckResult("L1", "registry_files_exist", Verdict.PASS, metric={"n_checked": n_total}))

    return rpt


def check_scene_graph_meshes(
    scene_graph_v3: dict,
    registry_path: str | None = None,
    models_root: str | None = None,
) -> "VerificationReport":
    """VS-IC ②: 驗證 scene_graph_v3 各模組 mesh 引用可解析到 registry 有效 key。

    每個 module.meshes[].url 必須非空，且其 shape/component 類型必須存在於
    registry.json 的頂層 key；若 format 為 stl/glb，則同時確認檔案存在於
    models_root 下。

    修復目標：mesh ref 未解析 → 前端載入鏈斷、ghost box（VS-IC ②）。
    """
    reg_path = Path(registry_path) if registry_path else (_MODELS_ROOT / "registry.json")
    comp_root = Path(models_root) if models_root else (_MODELS_ROOT / "components")
    rpt = VerificationReport(artifact="scene_graph_v3", artifact_type="scene_graph_meshes")

    # 載入 registry
    try:
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        rpt.add(CheckResult("L1", "registry_loadable", Verdict.FAIL, message=f"無法載入 registry：{exc}"))
        return rpt
    rpt.add(CheckResult("L1", "registry_loadable", Verdict.PASS))

    registry_keys = {k for k in reg if not k.startswith("_") and isinstance(reg[k], list)}

    modules = scene_graph_v3.get("modules", []) if isinstance(scene_graph_v3, dict) else []
    if not modules:
        rpt.add(CheckResult("L1", "scene_modules_checked", Verdict.PASS,
                            message="無 module，跳過 mesh 驗證", metric={"n_modules": 0}))
        return rpt

    empty_url: list[str] = []
    unresolved: list[str] = []
    missing_file: list[str] = []
    n_checked = 0

    for mod in modules:
        if not isinstance(mod, dict):
            continue
        mod_id = mod.get("id") or mod.get("type") or "<module>"
        # 從 module 取得 shape 型別：優先 shape 欄位，其次 type，再由 URL 推導
        mod_shape = mod.get("shape") or mod.get("type") or ""
        meshes = mod.get("meshes", [])
        if not isinstance(meshes, list):
            continue
        for mesh in meshes:
            if not isinstance(mesh, dict):
                continue
            url = mesh.get("url", "")
            fmt = mesh.get("format", "")
            n_checked += 1

            # 1. URL 非空
            if not url:
                empty_url.append(mod_id)
                continue

            # 2. 解析 shape key：從 URL 路徑第一段提取，例如 "ic-dip/dip-8.glb" → "ic-dip"
            url_shape = url.split("/")[0] if "/" in url else ""
            shape_key = url_shape or mod_shape
            # 去掉副檔名後綴（如 .glb / .stl）
            shape_key = shape_key.split(".")[0] if "." in shape_key else shape_key

            if not shape_key or shape_key not in registry_keys:
                unresolved.append(f"{mod_id}:{url}")
                continue

            # 3. 若為 stl/glb，確認實際檔案存在
            if fmt in ("stl", "glb"):
                file_path = comp_root / url
                if not file_path.exists():
                    missing_file.append(url)

    if empty_url:
        rpt.add(CheckResult("L1", "mesh_url_nonempty", Verdict.FAIL,
                            message="mesh URL 為空（前端無法載入模型）",
                            metric={"n": len(empty_url), "modules": empty_url[:5]}))
    else:
        rpt.add(CheckResult("L1", "mesh_url_nonempty", Verdict.PASS))

    if unresolved:
        rpt.add(CheckResult("L1", "mesh_shape_in_registry", Verdict.FAIL,
                            message="mesh shape 未對應到 registry key（mesh ref 斷鏈）",
                            metric={"n": len(unresolved), "examples": unresolved[:5]}))
    else:
        rpt.add(CheckResult("L1", "mesh_shape_in_registry", Verdict.PASS,
                            metric={"n_checked": n_checked}))

    if missing_file:
        rpt.add(CheckResult("L1", "mesh_file_exists", Verdict.FAIL,
                            message="mesh 檔案不存在於 models_root（前端 404）",
                            metric={"n": len(missing_file), "examples": missing_file[:5]}))
    elif n_checked > 0:
        rpt.add(CheckResult("L1", "mesh_file_exists", Verdict.PASS))

    return rpt


def _scan_canned() -> int:
    """掃 v6/canned 所有 bridge，印每個的介接契約狀態。"""
    import sys
    import json
    from pathlib import Path
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    root = Path(__file__).resolve().parents[2]
    files = sorted((root / "v6" / "canned").glob("*.json"))
    files = [f for f in files if f.name != "_index.json"]

    print("=== 前後端介接契約掃描（v6/canned）===")
    n_fail = 0
    for f in files:
        try:
            bridge = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[skip] {f.name}: {exc}")
            continue
        rpt = check_cad_output_contract(bridge, name=f.stem)
        print(rpt.render_text())
        if rpt.verdict == Verdict.FAIL:
            n_fail += 1
    print(f"\n{'=' * 50}")
    print(f"{len(files) - n_fail}/{len(files)} canned 通過前端渲染介接契約")
    return 1 if n_fail else 0


if __name__ == "__main__":
    import sys
    sys.exit(_scan_canned())
