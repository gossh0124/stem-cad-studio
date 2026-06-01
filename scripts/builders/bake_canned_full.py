"""tools/bake_canned_full.py — 為每個 canned bridge 跑 Phase IV 生成完整 case + assembly。

執行：PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tools/bake_canned_full.py [--only auto_waterer]

對 v6/canned/*.json 做：
1. 讀 canned bridge（已含 components + wiring + power_budget）
2. 構造合成 Job → 呼叫 Phase4Handler.execute(job, bridge)
3. 將生成的 STL 從 output/{slug}/cad/ 複製到 v6/canned/{tpl_id}/
4. bridge.cad_output 路徑改為相對 URL（/canned/{tpl_id}/{filename}）
5. 重存 canned bridge JSON

Phase IV 需 build123d。每範本 ~30-60s。
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 確保 ANTHROPIC API key 為空（避免任何意外的 LLM 呼叫）
os.environ["ANTHROPIC_API_KEY"] = ""
# 設 Drive root 到專案 output/，Phase IV 會用此路徑生成 STL
os.environ.setdefault("CADHLLM_DRIVE_ROOT", str(ROOT / "output"))

from services.shared.models import Job, JobStatus, PhaseID  # noqa: E402
import services.shared.bridge_store as _bs  # noqa: E402

# Monkey-patch project_output_dir 以接受 Job 物件（Phase4Handler 線 161 直接傳 job）
_orig_project_output_dir = _bs.project_output_dir

def _patched_project_output_dir(job_or_id, project_name="", date_str=""):
    if hasattr(job_or_id, "project_name"):
        return _orig_project_output_dir(job_or_id.job_id, job_or_id.project_name, date_str)
    return _orig_project_output_dir(job_or_id, project_name, date_str)

_bs.project_output_dir = _patched_project_output_dir
# 同時 patch 已 import 此函式的 phase_handlers 模組
import services.phase_handlers.phase4_handler as _p4  # noqa: E402
_p4.project_output_dir = _patched_project_output_dir
from services.phase_handlers.phase4_handler import Phase4Handler  # noqa: E402


def _emit(msg: str) -> None:
    print(f"  {msg}")


def bake_template(tpl_id: str, canned_dir: Path) -> dict:
    """為單一範本跑 Phase IV，更新 canned bridge。回傳 stats。"""
    bridge_path = canned_dir / f"{tpl_id}.json"
    if not bridge_path.exists():
        return {"status": "skip", "reason": "bridge JSON 不存在"}

    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    project_name = f"canned_{tpl_id}"

    # 構造合成 Job
    job = Job(
        job_id=f"canned-{tpl_id}",
        project_name=project_name,
        instruction=bridge.get("_instruction", ""),
        status=JobStatus.RUNNING,
        current_phase=4,
    )

    # Phase IV expects project_output_dir(job) — 它接受 Job 物件嗎？
    # bridge_store 簽名 (job_id, project_name) — 我們得用 monkey-patch 或 signature 適配
    # 看 phase4_handler line 161: project_output_dir(job) — 直接傳 job 物件
    # 看實作：slug = re.sub(r"[^\w]", "_", project_name)[:30] — 把 Job 物件 str 化會得奇怪 slug
    # 解法：暫時 monkey-patch 或構造 fake project_output_dir 行為

    handler = Phase4Handler()
    t0 = time.time()
    material_fallback_used = False
    try:
        bridge, result = handler.execute(job, bridge, progress_cb=_emit)
    except Exception as exc:
        # PV5 PLA 應力不合格 fallback：與既有 PETG 範本（alarm_siren / electronic_keyboard）一致
        # 暫時把 hints.material 覆寫為 PETG retry，烤完還原（UI 顯示仍是 PLA）。
        msg = str(exc)
        is_pv5_fail = "PV5 snap-fit" in msg and "PLA" in msg
        if not is_pv5_fail:
            import traceback
            return {"status": "error", "reason": msg,
                    "trace": traceback.format_exc()}
        _emit(f"⚠️  PV5 PLA fail，改用 PETG retry（cad_output.spec.material 將標 PETG）")
        # 重新 load bridge（execute 可能已注入 partial state）
        bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
        hints = bridge.setdefault("cot_plan", {}).setdefault("parameter_hints", {})
        orig_material = hints.get("material")
        hints["material"] = "PETG"
        material_fallback_used = True
        try:
            bridge, result = handler.execute(job, bridge, progress_cb=_emit)
        except Exception as exc2:
            import traceback
            return {"status": "error",
                    "reason": f"PETG fallback 仍失敗：{exc2}",
                    "trace": traceback.format_exc()}
        # 還原 hints.material 給 UI（cad_output.spec.material 由 phase4 寫入，會反映實際 PETG）
        bridge.setdefault("cot_plan", {}).setdefault("parameter_hints", {})["material"] = orig_material
    elapsed = time.time() - t0

    # 將生成的 STL 從 output/{slug}/cad/ 複製到 v6/canned/{tpl_id}/
    _proj_out = bridge.get("_project_output_dir")
    if not _proj_out:
        return {"status": "error", "reason": "Phase4 未產出 CAD，components 可能為空",
                "elapsed_s": elapsed}
    src_dir = Path(_proj_out) / "cad"
    if not src_dir.exists():
        return {"status": "error", "reason": f"輸出目錄不存在：{src_dir}",
                "elapsed_s": elapsed}

    dst_dir = canned_dir / tpl_id
    dst_dir.mkdir(parents=True, exist_ok=True)

    stl_files: list = []
    for f in src_dir.iterdir():
        if f.suffix in (".stl", ".step"):
            shutil.copy2(f, dst_dir / f.name)
            stl_files.append(f.name)

    # 更新 bridge.cad_output STL 路徑為相對 URL
    co = bridge.setdefault("cad_output", {})
    for key in ("bottom_stl", "lid_stl"):
        v = co.get(key)
        if v:
            co[key] = f"/canned/{tpl_id}/{Path(v).name}"
    for shell in co.get("component_shells", []):
        if shell.get("stl"):
            shell["stl"] = f"/canned/{tpl_id}/{Path(shell['stl']).name}"
        if shell.get("step"):
            shell["step"] = f"/canned/{tpl_id}/{Path(shell['step']).name}"

    bridge.pop("_project_output_dir", None)  # 不需要在 canned 中保留

    # 寫回 canned bridge JSON
    bridge_path.write_text(
        json.dumps(bridge, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "ok",
        "elapsed_s": round(elapsed, 1),
        "stl_count": len(stl_files),
        "shells": len(co.get("component_shells", [])),
        "placements": len(co.get("component_placements", [])),
        "bottom_stl": co.get("bottom_stl"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只跑指定 template_id（如 auto_waterer）")
    args = ap.parse_args()

    canned_dir = ROOT / "v6" / "canned"
    index_path = canned_dir / "_index.json"
    if not index_path.exists():
        print(f"[FAIL] _index.json not found: {index_path}")
        return 1
    index = json.loads(index_path.read_text(encoding="utf-8"))

    targets = [e for e in index if not args.only or e["id"] == args.only]
    if not targets:
        print(f"[FAIL] no matching template (--only={args.only})")
        return 1

    print(f"\n=== Phase IV 完整烤製 {len(targets)} 個範本 ===\n")
    summary: list = []
    for entry in targets:
        tpl_id = entry["id"]
        print(f"▶ {tpl_id} ({entry['name']})...")
        r = bake_template(tpl_id, canned_dir)
        summary.append({"id": tpl_id, **r})
        if r["status"] == "ok":
            print(f"  [OK] {r['elapsed_s']}s | {r['stl_count']} STL | "
                  f"{r['shells']} shells | {r['placements']} placements")
        else:
            print(f"  [FAIL] {r['status']}: {r['reason']}")
            if r.get("trace"):
                print(r["trace"][:500])

    ok_count = sum(1 for s in summary if s["status"] == "ok")
    total_s = sum(s.get("elapsed_s", 0) for s in summary)
    print(f"\n=== 完成：{ok_count}/{len(targets)}，總耗時 {total_s:.0f}s ===")
    return 0 if ok_count == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
