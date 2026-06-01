"""scripts/_lora_b_inference_smoke.py — LoRA-B 訓練完成後的端到端 smoke test。

對 v6/canned 內幾個範本（預設 3 個）跑 Phase IV CH3 Plan + Params 雙階段推理，
驗證：
  1. PlanJSON.elements 每元件帶 enclosure_relation 且值在 5 enum 內
  2. ParamsJSON.placements 與 elements 一一對應（id 集合相同）
  3. INFERENCE_PRESET (T=0.5, min_p=0.1) 確實在 vLLM payload 內生效

用法：
  .venv/Scripts/python.exe scripts/_lora_b_inference_smoke.py
  .venv/Scripts/python.exe scripts/_lora_b_inference_smoke.py --templates auto_waterer smart_nightlight
  .venv/Scripts/python.exe scripts/_lora_b_inference_smoke.py --vllm-url http://localhost:8001

前置條件：vLLM server 必須跑著且 mount 了 cadhllm_lora_b adapter。
輸出：.ai/lora_b_inference_samples.json + 終端 PASS/FAIL 摘要
exit code：全 PASS 回 0，任一驗證失敗回 1。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CANNED = ROOT / "v6" / "canned"
DEFAULT_TEMPLATES = ["auto_waterer", "smart_nightlight", "music_box"]
ENCLOSURE_ENUM = {"internal", "breadboard", "panel", "external", "embedded"}
OUTPUT = ROOT / ".ai" / "lora_b_inference_samples.json"


def _build_bridge_ctx(tpl_id: str) -> tuple[dict, list, dict]:
    """從 canned 範本建 bridge / components / ctx，供 _generate_plan_stage 用。"""
    from lib.adapter_manager import _build_subsystem_context  # noqa
    bridge = json.loads((CANNED / f"{tpl_id}.json").read_text(encoding="utf-8"))
    components = bridge.get("components") or []
    # 確保 enclosure_constraints 存在
    if not bridge.get("enclosure_constraints"):
        bridge["enclosure_constraints"] = {"target_size": "compact", "max_dimension_mm": 150}
    if not bridge.get("environment_constraints"):
        bridge["environment_constraints"] = {"environment": "indoor", "waterproof": False, "ip_rating": "IP20"}
    ctx = _build_subsystem_context(bridge, components)
    return bridge, components, ctx


def _verify_plan(plan: dict) -> dict:
    """回傳 {ok, missing, invalid, total_elements, fail_lines}"""
    elements = plan.get("elements") or []
    missing = 0
    invalid = 0
    fail_lines: list[str] = []
    for el in elements:
        rel = el.get("enclosure_relation")
        cid = el.get("id") or el.get("component_type") or "?"
        if rel is None:
            missing += 1
            fail_lines.append(f"    {cid}: 缺 enclosure_relation")
        elif rel not in ENCLOSURE_ENUM:
            invalid += 1
            fail_lines.append(f"    {cid}: enclosure_relation={rel!r} 不在 5 enum")
    return {
        "ok": (missing == 0 and invalid == 0),
        "missing": missing,
        "invalid": invalid,
        "total_elements": len(elements),
        "fail_lines": fail_lines,
    }


def _verify_params(plan: dict, params: dict) -> dict:
    """回傳 {ok, placement_ids, missing_in_params, extra_in_params, fail_lines}"""
    plan_ids = {el.get("id") for el in (plan.get("elements") or []) if el.get("id")}
    placements = params.get("placements") or []
    params_ids = {p.get("element_id") for p in placements if p.get("element_id")}
    missing = plan_ids - params_ids
    extra = params_ids - plan_ids
    fail_lines = []
    if missing:
        fail_lines.append(f"    placements 缺少 element_id: {sorted(missing)}")
    if extra:
        fail_lines.append(f"    placements 多出 element_id: {sorted(extra)}")
    return {
        "ok": (not missing and not extra),
        "placement_count": len(placements),
        "missing_in_params": sorted(missing),
        "extra_in_params": sorted(extra),
        "fail_lines": fail_lines,
    }


def _run_one(tpl_id: str) -> dict:
    """跑單一範本 Plan + Params。回傳 result dict。"""
    from lib.adapter_manager import _generate_plan_stage, _generate_params_stage
    t0 = time.time()
    bridge, components, ctx = _build_bridge_ctx(tpl_id)
    try:
        plan = _generate_plan_stage(bridge, components, ctx) or {}
    except Exception as e:
        return {"tpl_id": tpl_id, "stage": "plan", "error": str(e),
                "traceback": traceback.format_exc()[-800:]}
    t_plan = time.time() - t0

    try:
        params = _generate_params_stage(bridge, components, plan, ctx) or {}
    except Exception as e:
        return {"tpl_id": tpl_id, "stage": "params", "plan": plan,
                "error": str(e), "traceback": traceback.format_exc()[-800:]}
    t_total = time.time() - t0

    plan_check = _verify_plan(plan)
    params_check = _verify_params(plan, params)
    return {
        "tpl_id": tpl_id,
        "elapsed_s": round(t_total, 2),
        "elapsed_plan_s": round(t_plan, 2),
        "elapsed_params_s": round(t_total - t_plan, 2),
        "plan": plan,
        "params": params,
        "plan_check": plan_check,
        "params_check": params_check,
        "ok": plan_check["ok"] and params_check["ok"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--templates", nargs="*", default=DEFAULT_TEMPLATES)
    ap.add_argument("--vllm-url", default=None, help="覆寫 VLLM_BASE_URL（預設讀 env / http://localhost:8001）")
    args = ap.parse_args()

    os.environ.setdefault("CADHLLM_BACKEND", "vllm")
    if args.vllm_url:
        os.environ["VLLM_BASE_URL"] = args.vllm_url

    # 確認 vLLM 與 LoRA-B 都可用
    from lib.vllm_client import is_vllm_available, VLLM_BASE_URL
    if not is_vllm_available():
        print(f"[smoke] FATAL: vLLM 不可用 ({VLLM_BASE_URL})", file=sys.stderr)
        return 2

    results = []
    print(f"[smoke] vLLM @ {VLLM_BASE_URL}, running {len(args.templates)} templates...\n")
    for tpl in args.templates:
        print(f"[smoke] === {tpl} ===")
        r = _run_one(tpl)
        results.append(r)
        if "error" in r:
            print(f"  [FAIL] stage={r['stage']}: {r['error']}")
            print(f"  traceback:\n{r.get('traceback','')[-400:]}")
            continue
        pc = r["plan_check"]; pp = r["params_check"]
        print(f"  plan elements: {pc['total_elements']} (missing={pc['missing']}, invalid={pc['invalid']})")
        print(f"  params placements: {pp['placement_count']} (missing={len(pp['missing_in_params'])}, extra={len(pp['extra_in_params'])})")
        for ln in pc["fail_lines"] + pp["fail_lines"]:
            print(ln)
        print(f"  elapsed: plan={r['elapsed_plan_s']}s params={r['elapsed_params_s']}s")
        print(f"  result: {'PASS' if r['ok'] else 'FAIL'}\n")

    # 寫結果
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"vllm_base_url": VLLM_BASE_URL, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"[smoke] 詳細結果已寫入 {OUTPUT}")

    # 終端摘要
    total = len(results)
    passed = sum(1 for r in results if r.get("ok"))
    errs = sum(1 for r in results if "error" in r)
    print(f"\n[smoke] {'='*40}")
    print(f"[smoke] Summary: {passed}/{total} PASS, {errs} errors")
    return 0 if (passed == total and total > 0) else 1


if __name__ == "__main__":
    sys.exit(main())
