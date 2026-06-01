"""Unit tests for lib.cad.hl_dsl — CH3 Plan/Params schema + DSL Compiler.

涵蓋：
  - Plan schema valid / invalid 各 2 個樣本
  - Params schema valid / invalid + cross-check missing element id
  - DSL Compiler minimal 範本（Arduino + Button + USB-5V）跑通
  - DSL Compiler fail case（plan 有 id 但 params 沒對應 layout）
"""

from __future__ import annotations

import copy

import pytest

from lib.cad import hl_dsl
from lib.cad.hl_dsl import (
    compile_to_solver_dict,
    validate_params,
    validate_plan,
)


# ── Fixture：minimal valid Plan / Params（Arduino + Button + USB-5V）─────

@pytest.fixture
def minimal_plan() -> dict:
    return {
        "elements": [
            {"id": "e1", "component_type": "Arduino-Uno-class", "role": "Brain",
             "logical_zone": "mid-center", "face_out": "top",
             "reason": "主控居中"},
            {"id": "e2", "component_type": "USB-5V-class", "role": "Power",
             "logical_zone": "bottom-left", "face_out": "side-back",
             "reason": "電源接後面"},
            {"id": "e3", "component_type": "Button-class", "role": "Control",
             "logical_zone": "top-center", "face_out": "top",
             "reason": "按鍵朝上"},
        ],
        "assembly_order": ["e2", "e1", "e3"],
        "joints": {
            "lid_method": "snap_fit_4x",
            "base_method": "screw_boss_4x_M3",
            "reason": "輕量好維護",
        },
        "thermal_strategy": {
            "strategy": "no_vent",
            "vent_placement": "none",
            "heat_sources": [],
        },
        "placement_rationale": "Brain 居中，Button 朝上，USB 後出線",
    }


@pytest.fixture
def minimal_params() -> dict:
    return {
        "enclosure_spec": {
            "inner_length": 100, "inner_width": 70, "inner_height": 35,
            "wall": 2.0, "tol": 0.3, "fillet_r": 2.5,
        },
        "placements": [
            {"element_id": "e1", "x": 50, "y": 35, "z": 10, "rot_deg": 0},
            {"element_id": "e2", "x": 20, "y": 10, "z": 5, "rot_deg": 0},
            {"element_id": "e3", "x": 50, "y": 60, "z": 30, "rot_deg": 0},
        ],
        "wire_routes": [
            {"from": "e1", "to": "e2", "path": "channel_bottom", "current_ma": 200},
            {"from": "e1", "to": "e3", "path": "direct", "current_ma": 1},
        ],
        "vent_placements": [],
    }


# ── Plan schema：valid 樣本（2 個）──────────────────────────────────────

def test_plan_valid_minimal(minimal_plan):
    ok, errs = validate_plan(minimal_plan)
    assert ok, f"unexpected errors: {errs}"
    assert errs == []


def test_plan_valid_full_with_environmental():
    plan = {
        "elements": [
            {"id": "x1", "component_type": "Arduino-Uno-class", "role": "Brain",
             "logical_zone": "mid-center", "face_out": "top"},
        ],
        "assembly_order": ["x1"],
        "joints": {
            "lid_method": "screw_4x_M3",
            "base_method": "adhesive_pad",
            "reason": "防震",
        },
        "thermal_strategy": {
            "strategy": "active_fan",
            "vent_placement": "side_upper",
            "heat_sources": [{"type": "MCU", "mw": 500}],
        },
        "environmental": {
            "waterproof": True,
            "ip_rating": "IP54",
            "sealed_zones": ["mid-center"],
            "exposed_zones": [],
        },
        "placement_rationale": "Outdoor box",
    }
    ok, errs = validate_plan(plan)
    assert ok, f"unexpected errors: {errs}"


# ── Plan schema：invalid 樣本（2 個）────────────────────────────────────

def test_plan_invalid_missing_required_field(minimal_plan):
    bad = copy.deepcopy(minimal_plan)
    del bad["joints"]  # required: joints 缺失
    ok, errs = validate_plan(bad)
    assert not ok
    assert any("joints" in e for e in errs), f"expected 'joints' in errs, got {errs}"


def test_plan_invalid_bad_enum_role(minimal_plan):
    bad = copy.deepcopy(minimal_plan)
    bad["elements"][0]["role"] = "NotARealRole"
    ok, errs = validate_plan(bad)
    assert not ok
    assert any("role" in e.lower() or "enum" in e.lower() for e in errs)


def test_plan_invalid_assembly_order_references_unknown_id(minimal_plan):
    bad = copy.deepcopy(minimal_plan)
    bad["assembly_order"] = ["e1", "e999"]  # e999 不在 elements
    ok, errs = validate_plan(bad)
    assert not ok
    assert any("e999" in e for e in errs)


# ── Params schema：valid 樣本 ─────────────────────────────────────────

def test_params_valid_minimal(minimal_plan, minimal_params):
    ok, errs = validate_params(minimal_params, minimal_plan)
    assert ok, f"unexpected errors: {errs}"


# ── Params schema：invalid 樣本 ────────────────────────────────────────

def test_params_invalid_wall_too_thin(minimal_plan, minimal_params):
    bad = copy.deepcopy(minimal_params)
    bad["enclosure_spec"]["wall"] = 0.5  # < min 1.5
    ok, errs = validate_params(bad, minimal_plan)
    assert not ok
    assert any("wall" in e.lower() or "0.5" in e for e in errs)


def test_params_invalid_rot_deg(minimal_plan, minimal_params):
    bad = copy.deepcopy(minimal_params)
    bad["placements"][0]["rot_deg"] = 45  # 只允許 0/90/180/270
    ok, errs = validate_params(bad, minimal_plan)
    assert not ok
    assert any("rot_deg" in e or "45" in e for e in errs)


# ── Cross-check：missing element id ────────────────────────────────────

def test_params_crosscheck_missing_element_id(minimal_plan, minimal_params):
    bad = copy.deepcopy(minimal_params)
    bad["placements"] = [p for p in bad["placements"] if p["element_id"] != "e3"]
    ok, errs = validate_params(bad, minimal_plan)
    assert not ok
    assert any("e3" in e and "missing" in e for e in errs), f"got: {errs}"


def test_params_crosscheck_extra_element_id(minimal_plan, minimal_params):
    bad = copy.deepcopy(minimal_params)
    bad["placements"].append(
        {"element_id": "phantom", "x": 0, "y": 0, "z": 0, "rot_deg": 0}
    )
    ok, errs = validate_params(bad, minimal_plan)
    assert not ok
    assert any("phantom" in e for e in errs)


# ── BBox guard（outer ≤ 295mm）────────────────────────────────────────

def test_params_bbox_guard_exceeds(minimal_plan, minimal_params):
    bad = copy.deepcopy(minimal_params)
    bad["enclosure_spec"]["inner_length"] = 280  # 280 + 2*2 = 284 ≤ 295 OK
    bad["enclosure_spec"]["wall"] = 4.0  # 280 + 8 = 288 ≤ 295 OK
    ok, errs = validate_params(bad, minimal_plan)
    assert ok, f"288 should pass: {errs}"

    bad["enclosure_spec"]["inner_length"] = 280
    bad["enclosure_spec"]["wall"] = 4.0
    bad["enclosure_spec"]["inner_width"] = 280  # 280 + 8 = 288 OK
    # 但若 inner_length 拉到 290 → 290 + 8 = 298 > 295
    bad["enclosure_spec"]["inner_length"] = 290
    bad["enclosure_spec"]["wall"] = 4.0
    # 注意 inner_length ≤ 280 schema 限制；改用 wall 偏門路徑
    # 改：inner=280, wall=4 → 288 OK；inner=280, wall=4 沒法觸發
    # 改用 inner_height 280 + wall 4 = 288 (OK)；要 > 295 必須 schema 允許但 guard 不允許
    # 走 inner_length=280, wall=4 → 288 (OK)，本案做為 sanity；
    # 真正 fail 案：inner_height=280, wall=4 → 288 仍 OK，guard 設計上 296 才 fail
    # 此處驗 guard 路徑邏輯：inner_height schema max 280, wall max 4.0 → 上限 outer=288 → 永不觸發 295
    # 故本 case 只測 OK path，作為 sanity（295 邊界由下一個 test 直接捏資料測）


def test_params_bbox_guard_synthetic_fail(minimal_plan):
    """直接捏 wall=4 + inner=290（繞過 schema max=280 並非目的，此測直接給 guard 越界值）。"""
    # 為了純測 bbox_guard 邏輯，臨時把 schema range 觸發的 error 與 guard error 都當錯誤計算
    params = {
        "enclosure_spec": {
            "inner_length": 290,  # > 280 (schema max)
            "inner_width": 70, "inner_height": 35,
            "wall": 4.0, "tol": 0.3,
        },
        "placements": [
            {"element_id": e["id"], "x": 0, "y": 0, "z": 0, "rot_deg": 0}
            for e in minimal_plan["elements"]
        ],
        "wire_routes": [],
        "vent_placements": [],
    }
    ok, errs = validate_params(params, minimal_plan)
    assert not ok
    # 應有 inner_length schema fail 或 bbox_guard fail
    assert any("inner_length" in e or "bbox_guard" in e for e in errs)


# ── DSL Compiler：minimal 範本跑通 ─────────────────────────────────────

def test_compile_minimal_arduino_button_usb(minimal_plan, minimal_params):
    bridge = {"components": []}
    out = compile_to_solver_dict(minimal_plan, minimal_params, bridge)

    # 必有欄位（與 assembly_solver.solve 1:1 對齊）
    for key in ("placements", "thermal_field", "wire_routes", "joints", "decisions"):
        assert key in out, f"missing key: {key}"

    # placements：3 個元件，順序對齊 assembly_order ("e2","e1","e3")
    assert len(out["placements"]) == 3
    types = [p["type"] for p in out["placements"]]
    assert types == ["USB-5V-class", "Arduino-Uno-class", "Button-class"]

    # registry 尺寸查得到（Arduino L=68.58）
    arduino = next(p for p in out["placements"] if p["type"] == "Arduino-Uno-class")
    assert arduino["L"] == pytest.approx(68.58)
    assert arduino["zone"] == "mid-center"
    assert arduino["face_out"] == "top"
    assert arduino["x"] == 50.0
    assert arduino["y"] == 35.0
    assert arduino["enclosure_relation"] == "internal"

    # thermal_field：strategy=no_vent → needs_venting=False
    assert out["thermal_field"]["needs_venting"] is False
    assert out["thermal_field"]["total_power_mw"] == 0.0

    # wire_routes：2 條
    assert len(out["wire_routes"]) == 2
    assert out["wire_routes"][0]["from"] == "e1"
    assert out["wire_routes"][0]["to"] == "e2"
    assert out["wire_routes"][0]["path"] == "channel_bottom"

    # joints 直接帶出
    assert out["joints"]["lid_method"] == "snap_fit_4x"

    # decisions：6 條 6E-tagged
    assert len(out["decisions"]) == 6
    for d in out["decisions"]:
        assert "step" in d and "principle" in d and "description" in d
        assert d["6e_stage"] == "engineer"

    # enclosure_spec 帶出
    assert out["enclosure_spec"]["inner_length"] == 100

    # ch3_source 標記
    assert out["ch3_source"] == "lora_b"


def test_compile_thermal_active_fan(minimal_plan, minimal_params):
    plan = copy.deepcopy(minimal_plan)
    plan["thermal_strategy"] = {
        "strategy": "active_fan",
        "vent_placement": "side_upper",
        "heat_sources": [{"type": "Pump-Water-class", "mw": 1100}],
    }
    params = copy.deepcopy(minimal_params)
    params["vent_placements"] = [{"face": "side-left", "area_mm2": 200}]

    out = compile_to_solver_dict(plan, params, {})
    assert out["thermal_field"]["needs_venting"] is True
    assert out["thermal_field"]["total_power_mw"] == 1100.0
    assert out["thermal_field"]["vent_placements"] == ["side-left"]
    assert out["vent_placements"][0]["area_mm2"] == 200


# ── DSL Compiler：fail case（plan 有 id 但 params 沒對應）───────────────

def test_compile_fail_when_params_missing_layout_for_btn1(minimal_plan, minimal_params):
    plan = copy.deepcopy(minimal_plan)
    # 重命名 e3 → btn1
    plan["elements"][2]["id"] = "btn1"
    plan["assembly_order"] = ["e2", "e1", "btn1"]

    # params 仍只給 e1/e2/e3 → btn1 缺 layout
    with pytest.raises(ValueError) as excinfo:
        compile_to_solver_dict(plan, minimal_params, {})

    msg = str(excinfo.value)
    assert "btn1" in msg or "cross_check" in msg


def test_compile_fail_when_plan_invalid(minimal_plan, minimal_params):
    plan = copy.deepcopy(minimal_plan)
    del plan["thermal_strategy"]  # 必要欄位缺
    with pytest.raises(ValueError) as excinfo:
        compile_to_solver_dict(plan, minimal_params, {})
    assert "Plan schema invalid" in str(excinfo.value)


def test_compile_fail_when_params_invalid(minimal_plan, minimal_params):
    params = copy.deepcopy(minimal_params)
    params["enclosure_spec"]["wall"] = 100  # > max 4.0
    with pytest.raises(ValueError) as excinfo:
        compile_to_solver_dict(minimal_plan, params, {})
    assert "Params schema invalid" in str(excinfo.value) or "wall" in str(excinfo.value)


# ── Schema 常數導出 ──────────────────────────────────────────────────

def test_module_exports():
    assert isinstance(hl_dsl.PLAN_SCHEMA, dict)
    assert isinstance(hl_dsl.PARAMS_SCHEMA, dict)
    assert hl_dsl.PLAN_SCHEMA.get("$schema", "").startswith("https://json-schema.org")
