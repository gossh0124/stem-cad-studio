"""adapter_manager.py — LoRA adapter hot-swap 管理器。

同一 base model 常駐 VRAM，按需切換 LoRA-A（Phase I/VI/VII）和 LoRA-B（Phase IV Layer 2）。
避免重複載入 base model，切換 adapter 只需毫秒級 PEFT 操作。
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .tools import extract_json as _extract_json

# CAD-HLLM 論文驗證之推理超參（T=0.5, min_p=0.1, do_sample=True）
# LoRA-B Plan / Params 兩階段共用；LoRA-A 仍走預設保守 T=0.3
try:
    from training.cadhllm_hparams import INFERENCE_PRESET
except ImportError:
    INFERENCE_PRESET = {"temperature": 0.5, "min_p": 0.1, "do_sample": True}

_lock = threading.Lock()

ADAPTER_LORA_A = "lora_a"
ADAPTER_LORA_B = "lora_b"

# 模組級單例
_base_model = None
_tokenizer = None
_current_adapter: Optional[str] = None


def _adapter_path(name: str) -> Optional[str]:
    """解析 adapter 路徑。"""
    if name == "lora_a":
        p = os.environ.get("CADHLLM_ADAPTER_PATH", "./saved_model/cadhllm_lora")
        if "CADHLLM_ADAPTER_PATH" not in os.environ:
            _log.info("CADHLLM_ADAPTER_PATH not set, using default: %s", p)
        return p if Path(p).exists() else None
    elif name == "lora_b":
        p = os.environ.get("CADHLLM_LORA_B_PATH", "./saved_model/cadhllm_lora_b")
        if "CADHLLM_LORA_B_PATH" not in os.environ:
            _log.info("CADHLLM_LORA_B_PATH not set, using default: %s", p)
        return p if Path(p).exists() else None
    return None


def _ensure_base_model():
    """載入 base model（只執行一次）。優先 unsloth，fallback transformers。"""
    global _base_model, _tokenizer
    if _base_model is not None:
        return

    base_id = os.environ.get(
        "CADHLLM_BASE_MODEL",
        "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    )
    if "CADHLLM_BASE_MODEL" not in os.environ:
        _log.info("CADHLLM_BASE_MODEL not set, using default: %s", base_id)

    try:
        from unsloth import FastLanguageModel
        _base_model, _tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_id,
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(_base_model)
        return
    except ImportError:
        pass

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    import torch

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    _tokenizer = AutoTokenizer.from_pretrained(base_id)
    _base_model = AutoModelForCausalLM.from_pretrained(
        base_id,
        quantization_config=bnb_config,
        device_map="auto",
    )
    _base_model.eval()


def _swap_adapter(name: str):
    """切換到指定的 LoRA adapter。"""
    global _current_adapter
    if _current_adapter == name:
        return

    path = _adapter_path(name)
    if path is None:
        raise FileNotFoundError(f"Adapter '{name}' 路徑不存在")

    from peft import PeftModel

    global _base_model
    if hasattr(_base_model, "disable_adapter"):
        _base_model.disable_adapter()

    if hasattr(_base_model, "load_adapter"):
        _base_model.load_adapter(path, adapter_name=name)
        _base_model.set_adapter(name)
    else:
        _base_model = PeftModel.from_pretrained(_base_model, path, adapter_name=name)

    _current_adapter = name


def _build_chat_prompt(system: str, user: str) -> str:
    """Llama 3.1 chat template — delegate 到 lib.tools SSOT。"""
    from .tools import build_llama31_chat_prompt
    return build_llama31_chat_prompt(system, user)


def generate(
    prompt: str,
    adapter: str = ADAPTER_LORA_A,
    max_new_tokens: int = 512,
    temperature: float = 0.3,
    min_p: float = 0.0,
) -> str:
    """使用指定 adapter 進行推論。優先 vLLM，fallback transformers。

    Parameters
    ----------
    prompt : str
        完整的 Llama 3.1 chat template prompt（含 system/user/assistant 標頭）
    adapter : str
        ADAPTER_LORA_A 或 ADAPTER_LORA_B
    max_new_tokens : int
        最大生成 token 數
    temperature : float
        取樣溫度
    min_p : float
        min-p sampling 閾值（0.0 = 不啟用；CAD-HLLM INFERENCE_PRESET 用 0.1）

    Returns
    -------
    str
        模型生成的文字（不含 prompt）
    """
    backend = os.environ.get("CADHLLM_BACKEND", "vllm")

    if backend in ("vllm", "auto"):
        try:
            from lib.vllm_client import is_vllm_available, vllm_generate
            if is_vllm_available():
                # adapter id 必須跟 /root/launch_vllm.sh 內 --lora-modules mount 名稱一致
                vllm_adapter = {
                    ADAPTER_LORA_A: "cadhllm_lora",
                    ADAPTER_LORA_B: "cadhllm_lora_b",
                }.get(adapter)
                return vllm_generate(
                    prompt,
                    max_tokens=max_new_tokens,
                    temperature=temperature,
                    min_p=min_p,
                    lora_adapter=vllm_adapter,
                )
            elif backend == "vllm":
                raise ConnectionError("CADHLLM_BACKEND=vllm 但 vLLM server 不可用")
        except (ImportError, ConnectionError):
            if backend == "vllm":
                raise

    with _lock:
        _ensure_base_model()
        _swap_adapter(adapter)

        inputs = _tokenizer(prompt, return_tensors="pt").to(_base_model.device)
        gen_kwargs = dict(
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
        )
        if min_p > 0 and temperature > 0:
            gen_kwargs["min_p"] = min_p
        outputs = _base_model.generate(**inputs, **gen_kwargs)
    response = _tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[1]:],
        skip_special_tokens=True,
    )
    if "<|eot_id|>" in response:
        response = response.split("<|eot_id|>")[0]
    return response.strip()


def _build_subsystem_context(bridge: dict, components: List[dict]) -> Dict[str, Any]:
    """彙整 Plan / Params 兩階段共用的子系統摘要與環境/外殼約束。"""
    from .specs import WEIGHT_G, THERMAL_MW, lookup_constant

    subsystems = []
    total_w = 0.0
    total_t = 0.0
    for c in components:
        ctype = c.get("type", "")
        _sentinel = object()
        w_val = lookup_constant(WEIGHT_G, ctype, _sentinel)
        if w_val is _sentinel:
            _log.warning(
                "WEIGHT_G: no entry for ctype=%r (alias-resolved key also missing); "
                "skipping weight contribution — validate component taxonomy",
                ctype,
            )
            w_val = 0.0
        w = float(w_val)
        t_val = lookup_constant(THERMAL_MW, ctype, _sentinel)
        if t_val is _sentinel:
            _log.warning(
                "THERMAL_MW: no entry for ctype=%r (alias-resolved key also missing); "
                "skipping thermal contribution — validate component taxonomy",
                ctype,
            )
            t_val = 0.0
        t = float(t_val)
        subsystems.append(f"{ctype}(weight={w}g, thermal={t}mW)")
        total_w += w
        total_t += t

    enc = bridge.get("enclosure_constraints", {}) or {}
    env = bridge.get("environment_constraints", {}) or {}

    return {
        "subsystems_list": subsystems,
        "subsystems_str": ", ".join(subsystems),
        "total_w": total_w,
        "total_t": total_t,
        "cat": bridge.get("project_category", "Smart_Home"),
        "name": bridge.get("project_name", "project"),
        "enclosure": enc,
        "env_scenario": env.get("environment", "indoor"),
        "env_waterproof": env.get("waterproof", False),
        "env_ip": env.get("ip_rating", "IP20"),
    }


_log = logging.getLogger(__name__)


def _safe_rag(builder_fn, *args, **kwargs) -> str:
    """嘗試呼叫 RAG context builder；失敗回空字串並 log（不靜默吞）。"""
    try:
        return builder_fn(*args, **kwargs) or ""
    except Exception as exc:
        _log.debug("RAG skipped: %s", exc)
        return ""


def _run_lora_b_stage(system_base: str, user_msg: str, rag_ctx: str) -> dict:
    """LoRA-B 兩階段推論共用尾段：拼 system_msg + 跑 inference + extract JSON。

    system_msg = system_base 加上 RAG context（若有）。
    Plan / Params 階段的 user_msg 結構不同，由 caller 自建後傳入。
    """
    system_msg = system_base + ("\n" + rag_ctx + "\n" if rag_ctx else "")
    response = generate(
        _build_chat_prompt(system_msg, user_msg),
        adapter=ADAPTER_LORA_B, max_new_tokens=1024,
        temperature=INFERENCE_PRESET["temperature"],
        min_p=INFERENCE_PRESET["min_p"],
    )
    return _extract_json(response) or {}


def _generate_plan_stage(bridge: dict, components: List[dict], ctx: Dict[str, Any]) -> dict:
    """CH3 Plan 階段（control token = plan）。RAG: lib.rag.build_phase4_context。"""
    from training.prompts import SYS_PLAN, build_plan_user_prompt

    try:
        from .rag import build_phase4_context
        rag_context = _safe_rag(build_phase4_context, bridge, components, top_k=3)
    except ImportError:
        rag_context = ""

    enc_max = ctx['enclosure'].get('max_dimension_mm', 150)
    enclosure_constraint = f"{ctx['enclosure'].get('target_size', 'compact')}（≤{enc_max}mm）"

    user_msg = build_plan_user_prompt(
        project_name=ctx['name'],
        category=ctx['cat'],
        subsystems=ctx['subsystems_list'],
        total_weight=ctx['total_w'],
        total_thermal=ctx['total_t'],
        env_name=ctx['env_scenario'],
        env_waterproof=ctx['env_waterproof'],
        env_ip=ctx['env_ip'],
        enclosure_constraint=enclosure_constraint,
    )
    return _run_lora_b_stage(SYS_PLAN, user_msg, rag_context)


def _generate_params_stage(
    bridge: dict,
    components: List[dict],
    plan_dict: dict,
    ctx: Dict[str, Any],
) -> dict:
    """CH3 Params 階段（control token = params）。RAG: lib.rag_ch3.phase4_params_context_builder。"""
    from training.prompts import SYS_PARAMS, build_params_user_prompt

    try:
        from .rag.rag_ch3 import phase4_params_context_builder
        params_rag_ctx = _safe_rag(phase4_params_context_builder, bridge, plan_dict, top_k=3)
    except ImportError:
        params_rag_ctx = ""

    user_msg = build_params_user_prompt(
        project_name=ctx['name'],
        category=ctx['cat'],
        plan=plan_dict,
    )
    return _run_lora_b_stage(SYS_PARAMS, user_msg, params_rag_ctx)




def _fallback_compile(plan_dict: dict, params_dict: dict) -> dict:
    """A2 hl_dsl 尚未上線時的 compile fallback：合併 plan/params 為單一 dict。

    保留既有 assembly_plan_dict 結構欄位（layout / thermal / joints / cable_routing），
    讓 phase4_handler._merge_lora_b_into_solver 仍能消化。
    """
    merged: dict = {}
    merged.update(plan_dict or {})
    # Params 覆蓋 / 補足坐標相關欄位（layout / cable_routing 通常在 Params 細化）
    for k, v in (params_dict or {}).items():
        if k in ("layout", "cable_routing") and v:
            merged[k] = v
        else:
            merged.setdefault(k, v)
    return merged


def infer_plan_params(bridge: dict, components: List[dict]) -> dict:
    """CH3 案：單 LoRA-B adapter，以 control token 切 Plan + Params 兩階段。

    流程：
      1. Plan 階段（`<|im_start|>plan`）→ plan_dict（含元素/接合/熱）。
      2. `lib.cad.hl_dsl.validate_plan(plan_dict)` 驗證；若 A2 尚未實作則略過。
      3. RAG：`lib.rag_ch3.phase4_params_context_builder(bridge, plan_dict)` →
         params_rag_ctx，作為 Params 階段 prompt 注入材料。
      4. Params 階段（`<|im_start|>params`）→ params_dict（含座標/旋轉/尺寸）。
      5. `validate_params(params_dict, plan_dict)` 驗證；A2 未上線時略過。
      6. `compile_to_solver_dict(plan_dict, params_dict, bridge)` 編譯為
         既有 assembly_solver 可消化的 dict；A2 未上線時走 `_fallback_compile`。

    Returns
    -------
    dict
        {"plan": plan_dict, "params": params_dict, "compiled": assembly_plan_dict,
         "source": "ch3_lora_b"}
        當任一階段失敗時：plan / params / compiled 可能為空 dict，
        caller 應檢查 `compiled` 是否為 truthy 再合併進 solver。
    """
    ctx = _build_subsystem_context(bridge, components)

    # 1) Plan 階段
    plan_dict = _generate_plan_stage(bridge, components, ctx)

    try:
        from .cad import hl_dsl as dsl  # type: ignore
    except (ImportError, Exception) as exc:
        _log.warning("hl_dsl import failed, plan validation/compile skipped: %s", exc)
        dsl = None

    # 2) validate plan（A2 尚未實作則略過）
    if dsl is not None and hasattr(dsl, "validate_plan"):
        try:
            dsl.validate_plan(plan_dict)
        except Exception as exc:
            # plan 驗證失敗：回空 result，caller 走 solver fallback
            return {
                "plan": plan_dict,
                "params": {},
                "compiled": {},
                "source": "ch3_lora_b",
                "error": f"validate_plan failed: {exc}",
            }

    # 3+4) RAG 已由 _generate_params_stage 內部呼叫；Params 階段
    params_dict = _generate_params_stage(bridge, components, plan_dict, ctx)

    # 5) validate params
    if dsl is not None and hasattr(dsl, "validate_params"):
        try:
            dsl.validate_params(params_dict, plan_dict)
        except Exception as exc:
            return {
                "plan": plan_dict,
                "params": params_dict,
                "compiled": {},
                "source": "ch3_lora_b",
                "error": f"validate_params failed: {exc}",
            }

    # 6) compile
    if dsl is not None and hasattr(dsl, "compile_to_solver_dict"):
        try:
            compiled = dsl.compile_to_solver_dict(plan_dict, params_dict, bridge)
        except ValueError:
            # component_type 缺 dims：資料問題，不應靜默降級，直接穿透讓 caller 感知
            raise
        except Exception as exc:
            compiled = _fallback_compile(plan_dict, params_dict)
            return {
                "plan": plan_dict,
                "params": params_dict,
                "compiled": compiled,
                "source": "ch3_lora_b",
                "error": f"compile_to_solver_dict failed, used fallback: {exc}",
            }
    else:
        compiled = _fallback_compile(plan_dict, params_dict)

    return {
        "plan": plan_dict,
        "params": params_dict,
        "compiled": compiled,
        "source": "ch3_lora_b",
    }


def translate_hitl_intent(text: str) -> Optional[dict]:
    """Phase VII：使用 LoRA-A 將自由文字轉譯為結構化 action/params。"""
    system_msg = (
        "你是 HITL 意圖轉譯器。將使用者的自由文字修改指令轉換為 JSON。\n"
        "可用 action：increase_wall_thickness / decrease_wall_thickness / "
        "change_material / resize_enclosure / add_component / replace_component / accept。\n"
        "只輸出 JSON 物件 {\"action\": \"...\", \"params\": {...}}，不要 Markdown。"
    )

    response = generate(
        _build_chat_prompt(system_msg, text),
        adapter=ADAPTER_LORA_A, max_new_tokens=256,
    )
    return _extract_json(response)


def get_status() -> Dict[str, Any]:
    """回傳目前 adapter 管理器狀態。"""
    return {
        "base_model_loaded": _base_model is not None,
        "current_adapter": _current_adapter,
        "lora_a_available": _adapter_path("lora_a") is not None,
        "lora_b_available": _adapter_path("lora_b") is not None,
    }
