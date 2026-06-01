"""data_generator_b.py — Phase IV Layer 2 LoRA-B 訓練資料生成器（C 案）。

2026-05-15 重寫：採 C 案（單一 LoRA + control token）取代 B 案（雙 adapter）。
- 單一 adapter `saved_model/cadhllm_lora_b/`
- 用 control token `<|im_start|>plan` / `<|im_start|>params` 區分兩階段
- 訓練資料合一 jsonl：N 範本 × 2 樣本 = 2N 行（plan + params 各 N）
- 對齊 docs/CH3_HIERARCHICAL_SPEC.md §3.1 / §3.2 / §4
- 對齊 commit f915b7c：每元件 layout 帶 enclosure_relation（從 registry SSOT 查）

輸出：
  訓練資料 → training/data/cadhllm_lora_b_ch3.jsonl
  每行格式：{"messages": [{"role":"system","content":...},
                          {"role":"user","content":...},
                          {"role":"assistant","content":...}]}

Scope（M2 沿用）：室內 / 桌面 / 純電子或單軸簡單機構。
共用常數 / 模板 / 屬性 helpers 放 training/data_generator_b_helpers.py（CLAUDE.md 500 行規則）。
"""
from __future__ import annotations
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 確保 repo root 在 sys.path（推理端 import + Colab 讀 lib.registry 都需要）
def _ensure_import_path() -> None:
    """將 repo root 插入 sys.path（dev + Colab 兩環境均適用）。"""
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

_ensure_import_path()

try:
    from training.data_generator_b_helpers import (
        CATEGORY_TEMPLATES, CURRENT_MA, ENVIRONMENTS, THERMAL_MW, VENT_PLACEMENTS,
        VENT_FACE_FOR_STRATEGY, WEIGHT_G, ZONES,
        components_of, enclosure_relation_for, env_cfg_of, face_out_for,
        placement_reason, role_of, vary_template,
    )
except ImportError:
    # Colab fallback（cwd=training/）
    from data_generator_b_helpers import (
        CATEGORY_TEMPLATES, CURRENT_MA, ENVIRONMENTS, THERMAL_MW, VENT_PLACEMENTS,
        VENT_FACE_FOR_STRATEGY, WEIGHT_G, ZONES,
        components_of, enclosure_relation_for, env_cfg_of, face_out_for,
        placement_reason, role_of, vary_template,
    )

__all__ = [
    "DataGeneratorB", "generate_dataset",
    "generate_plan_sample", "generate_params_sample",
    "write_jsonl",
    # SSOT prompts/builders（供 lib.adapter_manager inference 端 import，保證 prompt 一致）
    "SYS_PLAN", "SYS_PARAMS",
    "build_plan_user_prompt", "build_params_user_prompt",
]

# ── Plan 與 Params 標籤建構 ───────────────────────────────
def _build_plan_label(template: Dict[str, Any]) -> Dict[str, Any]:
    """從 template 建出 PlanJSON（CH3 SPEC §3.1）— 兩階段共享的 ground-truth bridge。"""
    components = components_of(template)
    env_cfg = env_cfg_of(template)

    available_zones = list(ZONES)
    random.shuffle(available_zones)
    elements: List[Dict[str, Any]] = []
    for idx, ctype in enumerate(components):
        eid = f"e{idx + 1}"
        w = WEIGHT_G.get(ctype, 10.0)
        if w >= 30 and "bottom-center" in available_zones:
            zone = "bottom-center"; available_zones.remove(zone)
        elif "Sensor-SoilMoisture" in ctype and "bottom-probe" in available_zones:
            zone = "bottom-probe"; available_zones.remove(zone)
        elif available_zones:
            zone = available_zones.pop(0)
        else:
            zone = random.choice(ZONES)
        elements.append({
            "id": eid,
            "component_type": ctype,
            "role": role_of(ctype),
            "logical_zone": zone,
            "face_out": face_out_for(ctype),
            "enclosure_relation": enclosure_relation_for(ctype),
            "reason": placement_reason(ctype, zone),
        })

    assembly_order = [e["id"] for e in
                      sorted(elements, key=lambda e: -WEIGHT_G.get(e["component_type"], 0.0))]

    total_weight = sum(WEIGHT_G.get(c, 10.0) for c in components)
    if total_weight > 200:
        joints = {"lid_method": "screw_4x_M3", "base_method": "screw_boss_4x_M3",
                  "reason": "總重量較大，使用螺絲提供足夠固定力"}
    else:
        joints = {"lid_method": random.choice(["snap_fit_4x", "snap_fit_2x"]),
                  "base_method": "screw_boss_4x_M3",
                  "reason": "室內輕量使用，上蓋卡扣方便維護"}

    heat_sources = [{"type": c, "mw": THERMAL_MW.get(c, 0.0)}
                    for c in components if THERMAL_MW.get(c, 0.0) > 0]
    total_mw = sum(h["mw"] for h in heat_sources)
    if total_mw >= 3000:
        strategy = "active_fan"
    elif total_mw >= 1500:
        strategy = random.choice(["side_vent_passive", "top_vent_passive"])
    elif total_mw >= 500:
        strategy = "bottom_vent_passive"
    else:
        strategy = "no_vent"
    thermal_strategy = {
        "strategy": strategy,
        "vent_placement": random.choice(VENT_PLACEMENTS) if strategy != "no_vent" else "none",
        "heat_sources": heat_sources,
    }

    heaviest = max(components, key=lambda c: WEIGHT_G.get(c, 0))
    hottest = max(components, key=lambda c: THERMAL_MW.get(c, 0))
    rationale = (
        f"{heaviest} 最重({WEIGHT_G.get(heaviest, 0)}g)放底部穩定重心，"
        f"{hottest} 發熱最高({THERMAL_MW.get(hottest, 0)}mW)遠離感測器並靠近通風口"
    )

    # cable_routing: brain to each non-brain component
    brain_type = template["brain"]
    cable_routing = []
    for idx, ctype in enumerate(components):
        if ctype == brain_type:
            continue
        ma = CURRENT_MA.get(ctype, 20.0)
        if ma >= 300:
            strategy_cr = "channel_isolated"
        elif ma >= 100:
            strategy_cr = random.choice(["channel_bottom", "channel_side"])
        elif ma <= 5:
            strategy_cr = "direct"
        else:
            strategy_cr = random.choice(["channel_bottom", "channel_side", "direct"])
        cable_routing.append({
            "from_role": role_of(brain_type),
            "to_role": role_of(ctype),
            "to_type": ctype,
            "strategy": strategy_cr,
            "reason": f"電流 {ma}mA，" + (
                "大電流隔離走線" if ma >= 300 else
                "中電流走凹槽" if ma >= 100 else
                "低電流直連" if ma <= 5 else
                "一般走線"
            ),
        })

    return {
        "elements": elements,
        "assembly_order": assembly_order,
        "joints": joints,
        "thermal": thermal_strategy,
        "environmental": {
            "waterproof":   env_cfg["waterproof"],
            "ip_rating":    env_cfg["ip"],
            "sealed_zones": env_cfg["sealed"],
            "exposed_zones": env_cfg["exposed"],
        },
        "cable_routing": cable_routing,
        "placement_rationale": rationale,
    }


def _build_params_label(template: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """依 PlanJSON 推 ParamsJSON（CH3 SPEC §3.2）。x/y 由 zone → 網格映射。"""
    components = components_of(template)
    n = len(components)

    # 以總重量估外殼內尺寸（與 assembly_solver bbox 約束 outer ≤ 300mm 對齊，內尺寸 ≤ 280）
    base = max(80, min(220, 60 + 18 * n))
    inner_l = base + random.choice([-10, 0, 10])
    inner_w = max(60, base - 30 + random.choice([-5, 0, 5]))
    inner_h = max(25, 30 + random.choice([0, 10, 15]))

    # zone → (x, y) 網格中心；z 依重量 layer：重 → 底，輕 → 上
    zone_xy = {
        "top-left":      (inner_l * 0.20, inner_w * 0.80),
        "top-center":    (inner_l * 0.50, inner_w * 0.80),
        "top-right":     (inner_l * 0.80, inner_w * 0.80),
        "mid-left":      (inner_l * 0.20, inner_w * 0.50),
        "mid-center":    (inner_l * 0.50, inner_w * 0.50),
        "mid-right":     (inner_l * 0.80, inner_w * 0.50),
        "bottom-left":   (inner_l * 0.20, inner_w * 0.20),
        "bottom-center": (inner_l * 0.50, inner_w * 0.20),
        "bottom-right":  (inner_l * 0.80, inner_w * 0.20),
        "bottom-probe":  (inner_l * 0.50, inner_w * 0.20),
    }
    placements = []
    for el in plan["elements"]:
        x, y = zone_xy.get(el["logical_zone"], (inner_l / 2, inner_w / 2))
        w = WEIGHT_G.get(el["component_type"], 10.0)
        z = 2.0 if w >= 20 else (inner_h - 10.0 if "top-" in el["logical_zone"] else 8.0)
        ctype = el["component_type"]
        if "Motor" in ctype or "Pump" in ctype:
            rot = random.choice([0, 90, 180, 270])
        elif "Display" in ctype or "LED-Matrix" in ctype:
            rot = random.choice([0, 180])  # upright or flipped
        elif "USB" in ctype or "AC-Adapter" in ctype:
            rot = random.choice([0, 90, 270])  # connector orientation
        else:
            rot = random.choice([0, 0, 0, 90, 270])  # mostly 0, occasionally rotated
        placements.append({
            "element_id": el["id"], "x": round(x, 1), "y": round(y, 1),
            "z": round(z, 1), "rot_deg": rot,
        })

    brain = template["brain"]
    brain_id = next((e["id"] for e in plan["elements"] if e["component_type"] == brain),
                    plan["elements"][0]["id"])
    wire_routes = []
    for el in plan["elements"]:
        if el["id"] == brain_id:
            continue
        ma = CURRENT_MA.get(el["component_type"], 20.0)
        path = ("channel_isolated" if ma >= 300
                else random.choice(["channel_bottom", "channel_side", "direct"]))
        wire_routes.append({"from": brain_id, "to": el["id"], "path": path, "current_ma": ma})

    strategy = plan["thermal"]["strategy"]
    vent_placements = []
    if strategy != "no_vent":
        face = VENT_FACE_FOR_STRATEGY.get(strategy, "side-front")
        total_mw = sum(h["mw"] for h in plan["thermal"].get("heat_sources", []))
        vent_placements.append({"face": face, "area_mm2": max(60.0, round(total_mw * 0.04, 1))})

    return {
        "enclosure_spec": {
            "inner_length": float(inner_l), "inner_width": float(inner_w),
            "inner_height": float(inner_h), "wall": round(random.choice([1.6, 1.8, 2.0, 2.0, 2.0, 2.4, 2.8, 3.0]), 1), "tol": 0.3, "fillet_r": 3.0,
        },
        "placements": placements,
        "wire_routes": wire_routes,
        "vent_placements": vent_placements,
    }


# ── Prompt SSOT — training.prompts 為單一定義源 ─
# 推理端（lib/adapter_manager.py）與訓練端都 import 同一模組，禁止 hardcode。
# _ensure_import_path() already called above; try both package and module forms.
try:
    from training.prompts import (
        SYS_PLAN, SYS_PARAMS,
        build_plan_user_prompt, build_params_user_prompt,
    )
except ImportError:
    from prompts import (  # Colab fallback（cwd=training/）
        SYS_PLAN, SYS_PARAMS,
        build_plan_user_prompt, build_params_user_prompt,
    )


def _build_plan_prompt(template: Dict[str, Any], category: str) -> str:
    """內部 wrapper:從 template 抽欄位後呼共用 builder。"""
    components = components_of(template)
    env_cfg = env_cfg_of(template)
    subsystems_desc = [
        f"{c}(weight={WEIGHT_G.get(c, 10.0)}g, thermal={THERMAL_MW.get(c, 0.0)}mW)"
        for c in components
    ]
    return build_plan_user_prompt(
        project_name=template['name'],
        category=category,
        subsystems=subsystems_desc,
        total_weight=sum(WEIGHT_G.get(c, 10.0) for c in components),
        total_thermal=sum(THERMAL_MW.get(c, 0.0) for c in components),
        env_name=env_cfg['name'],
        env_waterproof=env_cfg['waterproof'],
        env_ip=env_cfg['ip'],
    )


def _build_params_prompt(template: Dict[str, Any], category: str,
                         plan: Dict[str, Any]) -> str:
    """內部 wrapper:呼共用 builder。"""
    return build_params_user_prompt(
        project_name=template['name'],
        category=category,
        plan=plan,
    )


# ── 公開 API ──────────────────────────────────────────────
def generate_plan_sample(template: Dict[str, Any], category: str,
                         plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """從 bridge/template 抽 Plan 級欄位，回傳 messages 格式樣本（含 control token）。

    若呼叫者已預生 plan（讓 plan/params 共享 ground truth），可傳入；否則本函式自建。
    """
    if plan is None:
        plan = _build_plan_label(template)
    user_prompt = _build_plan_prompt(template, category)
    assistant_completion = json.dumps(plan, ensure_ascii=False, indent=2)
    return {
        "messages": [
            {"role": "system", "content": SYS_PLAN},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_completion},
        ],
        "_meta": {"stage": "plan", "category": category, "template": template["name"]},
    }


def generate_params_sample(template: Dict[str, Any], category: str,
                           plan: Dict[str, Any],
                           params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """從 bridge + Plan 抽 Params 級欄位；prompt 含 Plan，control token <|im_start|>params。"""
    if params is None:
        params = _build_params_label(template, plan)
    user_prompt = _build_params_prompt(template, category, plan)
    assistant_completion = json.dumps(params, ensure_ascii=False, indent=2)
    return {
        "messages": [
            {"role": "system", "content": SYS_PARAMS},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_completion},
        ],
        "_meta": {"stage": "params", "category": category, "template": template["name"]},
    }


def generate_dataset(n_samples: int = 200, *, seed: Optional[int] = 3407) -> List[Dict[str, Any]]:
    """跑 N 個範本，每範本生 plan + params 各 1 樣本 → 2N 行 jsonl 資料。

    n_samples：plan 樣本數（params 同；總行數 = 2 * n_samples）。
    seed：固定 seed 保證可重現（None → 不設）。
    """
    if seed is not None:
        random.seed(seed)
    dataset: List[Dict[str, Any]] = []
    categories = list(CATEGORY_TEMPLATES.keys())
    cat_idx = 0
    while len(dataset) // 2 < n_samples:
        cat = categories[cat_idx % len(categories)]
        cat_idx += 1
        base = random.choice(CATEGORY_TEMPLATES[cat])
        template = vary_template(base) if random.random() < 0.6 else base
        plan = _build_plan_label(template)
        params = _build_params_label(template, plan)
        dataset.append(generate_plan_sample(template, cat, plan=plan))
        dataset.append(generate_params_sample(template, cat, plan=plan, params=params))
    return dataset[: 2 * n_samples]


def write_jsonl(samples: List[Dict[str, Any]], out_path: os.PathLike) -> int:
    """寫 jsonl；丟掉 _meta（訓練不用）。"""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for s in samples:
            row = {"messages": s["messages"]}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(samples)


# ── 向後相容包裝（保留 DataGeneratorB 名稱，給 train.py / colab notebook）──
class DataGeneratorB:
    """C 案 LoRA-B 訓練資料生成器（取代 B 案雙 adapter 版本）。"""

    def generate_synthetic_data(self, n: int = 200) -> List[Dict[str, Any]]:
        """回傳 2*n 筆 messages 格式樣本（plan + params 交錯）。

        n：plan 樣本數；總筆數 = 2 * n。
        """
        return generate_dataset(n_samples=n)


# ── CLI（CH3 SPEC §9.4 hard gate #2 dry-run / 完整訓練 jsonl 產出）─
if __name__ == "__main__":
    import argparse
    # Windows console 預設 cp950，強制 UTF-8 以印中文系統訊息
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception as exc:
        print(f"[data_generator_b] reconfigure failed: {exc}", file=sys.stderr, flush=True)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=5,
                    help="plan 範本數（總行數 = 2*n，plan + params 交錯）；預設 5 (dry-run)，建議 100 (正式訓練)")
    ap.add_argument("--out", type=Path, default=None,
                    help="輸出 jsonl 路徑；預設 dry-run → cadhllm_lora_b_ch3_dryrun.jsonl，n≥50 → cadhllm_lora_b_ch3.jsonl")
    ap.add_argument("--seed", type=int, default=3407, help="random seed")
    ap.add_argument("--verify-distribution", action="store_true",
                    help="生成後印 enclosure_relation 分布 + 5 enum 涵蓋率")
    ap.add_argument("--no-print", action="store_true", help="不印 SAMPLE [0]/[1] 內容")
    args = ap.parse_args()

    samples = generate_dataset(n_samples=args.n, seed=args.seed)
    print(f"Generated {len(samples)} samples (expect {2*args.n} = {args.n} plan + {args.n} params)")

    if not args.no_print:
        for label, idx in [("PLAN SAMPLE [0]", 0), ("PARAMS SAMPLE [1]", 1)]:
            print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
            s = samples[idx]
            print(f"[meta] {s['_meta']}")
            for m in s["messages"]:
                print(f"\n<{m['role']}>")
                content = m["content"]
                print(content[:700] + ("..." if len(content) > 700 else ""))

    if args.verify_distribution:
        from collections import Counter
        cnt = Counter()
        for s in samples:
            msgs = s["messages"]
            user = next((m for m in msgs if m["role"] == "user"), {})
            if "<|im_start|>plan" not in (user.get("content") or ""):
                continue
            asst = next((m for m in msgs if m["role"] == "assistant"), None)
            if not asst:
                continue
            try:
                plan = json.loads(asst["content"])
            except json.JSONDecodeError:
                continue
            for el in plan.get("elements", []):
                cnt[el.get("enclosure_relation", "MISSING")] += 1
        print(f"\n[verify] enclosure_relation 分布 ({sum(cnt.values())} elements):")
        for k in ("internal", "breadboard", "panel", "external", "embedded", "MISSING"):
            print(f"  {k:12} {cnt.get(k, 0)}")
        enums_seen = {k for k in cnt if k != "MISSING"}
        target = {"internal", "breadboard", "panel", "external", "embedded"}
        print(f"  5 enum 涵蓋率: {len(enums_seen & target)}/5 = {sorted(enums_seen & target)}")
        missing_enums = target - enums_seen
        if missing_enums:
            print(f"  [WARN] 未覆蓋 enum: {sorted(missing_enums)} (registry 內可能無對應元件)")

    default_out = Path(__file__).resolve().parents[0] / "data" / (
        "cadhllm_lora_b_ch3.jsonl" if args.n >= 50 else "cadhllm_lora_b_ch3_dryrun.jsonl"
    )
    out_path = args.out or default_out
    n_written = write_jsonl(samples, out_path)
    print(f"\n[{'train' if args.n >= 50 else 'dry-run'}] wrote {n_written} rows -> {out_path}")
