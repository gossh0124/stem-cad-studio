"""phase_handlers/phase1_handler.py — Phase I Server-side 推論 Handler。

訓練完成後（Colab 或 RTX 5070 Ti 本地端），adapter 同步到 Server，此 Handler 載入做推論。
**自動依硬體與 VRAM 預算切換 4bit / bf16 / cpu 載入**。

  - CADHLLM_VRAM_LIMIT_GB 設定 VRAM 預算（預設 8）
  - VRAM 預算 ≥ 12GB + bf16 支援 → bf16
  - VRAM 預算 < 12GB → 4bit（~5GB VRAM）
  - 無 CUDA → cpu float16

不依賴 unsloth（訓練才需要）。
"""
from __future__ import annotations
import logging
import os
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .base import PhaseHandler
from ..shared.models import Job, PhaseID

# lib/tools 的 format_prompt / extract_json — 確保推論 prompt 與訓練資料格式完全一致
try:
    from lib.tools import format_prompt as _format_prompt, extract_json as _extract_json
except ImportError:
    import sys as _sys, pathlib as _pl
    _sys.path.insert(0, str(_pl.Path(__file__).parents[2] / "lib"))
    try:
        from tools import format_prompt as _format_prompt, extract_json as _extract_json
    except ImportError:
        _format_prompt = None
        _extract_json  = None

# PR3: 抽象/不可解析輸入的 graceful 例外 — pipeline 特判，只回友善引導不噴 traceback
class Phase1InputError(ValueError):
    """Phase I 模型輸出無法解析或無元件（通常是輸入太抽象）。"""


_INPUT_TOO_ABSTRACT_MSG = (
    "輸入描述太抽象，無法判斷需要哪些電子元件。"
    "請具體說明要「偵測或控制什麼物理現象」，例如："
    "「門被打開就響鈴」「土壤太乾就自動澆水」「天黑自動開燈」。"
)

# 延遲 import：只在 execute() 時才載入，避免 Gateway 啟動時佔用 VRAM
_model     = None
_tokenizer = None
_model_lock = threading.Lock()
_p1_log = logging.getLogger("cadhllm.phase1")


def _get_vram_budget_gb() -> float:
    """VRAM 預算（GB），由 CADHLLM_VRAM_LIMIT_GB 設定，預設 8。"""
    try:
        _raw = os.environ.get("CADHLLM_VRAM_LIMIT_GB", "8")
        _val = float(_raw)
        if "CADHLLM_VRAM_LIMIT_GB" not in os.environ:
            _p1_log.info("CADHLLM_VRAM_LIMIT_GB not set, using default: %s", _raw)
        return _val
    except ValueError:
        return 8.0


def _detect_inference_mode() -> str:
    """偵測推論模式：'bf16'、'4bit' 或 'cpu'。

    覆寫順序：
      1. 環境變數 CADHLLM_INFER_MODE 強制覆寫
      2. CUDA 不可用 → cpu
      3. VRAM 預算 ≥ 12GB + bf16 支援 → bf16（~14GB VRAM）
      4. 否則 → 4bit（~5GB VRAM）
    """
    forced = os.environ.get("CADHLLM_INFER_MODE", "").strip().lower()
    if forced in ("bf16", "4bit", "cpu"):
        return forced
    if "CADHLLM_INFER_MODE" not in os.environ:
        _p1_log.info("CADHLLM_INFER_MODE not set, auto-detecting")
    try:
        import torch
        if not torch.cuda.is_available():
            return "cpu"
        budget = _get_vram_budget_gb()
        if budget >= 12 and torch.cuda.is_bf16_supported():
            return "bf16"
    except Exception as _exc:
        import logging as _log_mod
        _log_mod.getLogger("cadhllm.phase1").warning("CUDA detection failed, defaulting to 4bit: %s", _exc)
    return "4bit"


def _load_model(adapter_path: str, load_4bit: Optional[bool] = None):
    """載入 base model + LoRA adapter（單例，避免重複載入）。

    - load_4bit=None：自動偵測（預設）
    - load_4bit=True：強制 4bit
    - load_4bit=False：強制 bf16（VRAM 不足會 OOM）
    """
    global _model, _tokenizer
    with _model_lock:
        if _model is not None:
            return _model, _tokenizer

        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel

        if load_4bit is None:
            mode = _detect_inference_mode()
        else:
            mode = "4bit" if load_4bit else "bf16"

        BASE_MODEL = os.environ.get(
            "CADHLLM_BASE_MODEL_BF16", "meta-llama/Meta-Llama-3.1-8B-Instruct"
        )
        if "CADHLLM_BASE_MODEL_BF16" not in os.environ:
            _p1_log.info("CADHLLM_BASE_MODEL_BF16 not set, using default: %s", BASE_MODEL)

        budget_gb = _get_vram_budget_gb()

        if mode == "4bit":
            BASE_MODEL = os.environ.get(
                "CADHLLM_BASE_MODEL_4BIT", "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit"
            )
            if "CADHLLM_BASE_MODEL_4BIT" not in os.environ:
                _p1_log.info("CADHLLM_BASE_MODEL_4BIT not set, using default: %s", BASE_MODEL)
            print(f"[Phase I] 載入 base model（4bit, VRAM budget {budget_gb}GB）: {BASE_MODEL}")
            from transformers import BitsAndBytesConfig
            compute_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
            bnb_cfg = BitsAndBytesConfig(
                load_in_4bit              = True,
                bnb_4bit_compute_dtype    = compute_dtype,
                bnb_4bit_use_double_quant = True,
                bnb_4bit_quant_type       = "nf4",
            )
            max_mem = {0: f"{int(budget_gb)}GiB", "cpu": "24GiB"}
            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                quantization_config = bnb_cfg,
                device_map          = "auto",
                max_memory           = max_mem,
                torch_dtype         = compute_dtype,
            )
        elif mode == "cpu":
            print(f"[Phase I] 載入 base model（CPU float16）: {BASE_MODEL}")
            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype = torch.float16,
                device_map  = "cpu",
            )
        else:
            print(f"[Phase I] 載入 base model（bf16）: {BASE_MODEL}")
            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                torch_dtype = torch.bfloat16,
                device_map  = "cuda",
                attn_implementation = "sdpa",
            )

        _tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        if _tokenizer.pad_token is None:
            _tokenizer.pad_token = _tokenizer.eos_token

        _model = PeftModel.from_pretrained(base, adapter_path)
        _model.eval()
        print(f"[Phase I] 模型載入完成（mode={mode}, adapter: {adapter_path}）")
        return _model, _tokenizer


def unload_model():
    """Pipeline 結束後釋放 VRAM / RAM。"""
    global _model, _tokenizer
    import gc, torch
    with _model_lock:
        _model = _tokenizer = None
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("[Phase I] 模型記憶體已釋放")



def _infer_role_from_type(ctype: str, taxonomy: dict) -> str:
    """從 component type 反查所屬 role。"""
    for role, types in taxonomy.items():
        if ctype in types:
            return role
    return "Output"


class Phase1Handler(PhaseHandler):
    phase_id = PhaseID.P1

    def __init__(
        self,
        adapter_path: Optional[str] = None,
        load_4bit:    Optional[bool] = None,   # None = 自動偵測
        max_new_tokens: int         = 1536,
        temperature:    float       = 0.1,
    ):
        self.adapter_path   = adapter_path or os.environ.get(
            "CADHLLM_ADAPTER_PATH",
            self._detect_adapter_path(),
        )
        self.load_4bit      = load_4bit
        self.max_new_tokens = max_new_tokens
        self.temperature    = temperature

    @staticmethod
    def _has_adapter_weights(p: Path) -> bool:
        """檢查目錄是否包含有效的 adapter 權重檔。"""
        return (
            (p / "adapter_model.safetensors").exists()
            or (p / "adapter_model.bin").exists()
        )

    @staticmethod
    def _detect_adapter_path() -> str:
        """自動偵測 LoRA adapter 路徑：主 repo → worktree 本地 → Colab Drive。"""
        local = Path(__file__).parents[2] / "saved_model" / "cadhllm_lora"

        # worktree 中 safetensors 被 .gitignore 排除，需要找到主 repo 的 adapter
        if local.exists() and Phase1Handler._has_adapter_weights(local):
            return str(local)

        # 嘗試從 worktree 回溯到主 repo
        project_root = Path(__file__).parents[2]
        # worktree 路徑格式：.claude/worktrees/<name>/ → 主 repo 在 parents[3] 或更上層
        for ancestor in project_root.parents:
            candidate = ancestor / "saved_model" / "cadhllm_lora"
            if candidate.exists() and Phase1Handler._has_adapter_weights(candidate):
                return str(candidate)
            if (ancestor / "run_server.py").exists():
                break

        colab = Path("/data/cadhllm/saved_model")
        if colab.exists():
            return str(colab)
        drive = Path("/content/drive/MyDrive/CADHLLM/saved_model")
        if drive.exists():
            return str(drive)
        return str(local)

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, Dict[str, Any]]:
        instruction = bridge.get("_instruction", job.instruction)
        prompt = self._build_prompt_with_rag(instruction, progress_cb)

        # 嘗試 vLLM（WSL2）→ fallback 到 transformers 本地推論
        raw, elapsed, backend = self._infer(prompt, progress_cb)

        self._log(progress_cb, f"推論完成（{elapsed}s, {backend}）")

        # 解析 JSON — 保留使用者初始提供的 enclosure_constraints 值
        p1_output = self._parse_output(raw)
        bridge["_p1_raw"] = raw[:500]  # PR3: 失敗時也保留原始輸出供除錯
        if not p1_output:
            self._log(progress_cb, "⚠️ Phase I 輸出無法解析（輸入可能太抽象）")
            raise Phase1InputError(_INPUT_TOO_ABSTRACT_MSG)
        user_enc = bridge.get("enclosure_constraints", {})
        model_enc = p1_output.get("enclosure_constraints", {})
        merged_enc = {**model_enc, **{k: v for k, v in user_enc.items() if v}}

        components = p1_output.get("components", [])
        if not components:
            self._log(progress_cb, "⚠️ Phase I 未產生任何元件（輸入可能太抽象）")
            raise Phase1InputError(_INPUT_TOO_ABSTRACT_MSG)
        components = self._ensure_control(components, progress_cb)

        bridge.update({
            "project_name":       p1_output.get("project_name", job.project_name),
            "project_category":   p1_output.get("project_category", "Education"),
            "cot_plan":           p1_output.get("cot_plan", {}),
            "components":         components,
            "enclosure_constraints": merged_enc,
            "inventory_mentions": [],
            "_p1_raw":            raw[:500],
        })

        # Phase I 後可行性檢查（能力誤用 / 能量續航 / 電壓相容）。
        # advisory 層：問題附在 bridge["feasibility_issues"] 供前端顯示，
        # 不硬擋 pipeline（避免誤報中斷流程）；檢查本身例外則記錄、不靜默吞。
        try:
            from lib.feasibility import check_feasibility
            issues = check_feasibility(bridge)
            if issues:
                bridge["feasibility_issues"] = issues
                n_err = sum(1 for i in issues if i.get("severity") == "error")
                self._log(progress_cb,
                          f"可行性檢查：{len(issues)} 個問題（error={n_err}）")
        except Exception as exc:
            self._log(progress_cb, f"⚠️  可行性檢查失敗（不影響產出）：{exc}")

        if backend == "transformers":
            unload_model()
        self._save_bridge_safe(job, bridge, progress_cb)

        return bridge, {"elapsed_s": elapsed, "backend": backend}

    def _infer(
        self,
        prompt: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[str, float, str]:
        """推論：優先 vLLM，fallback transformers。回傳 (raw_text, elapsed_s, backend)。"""
        # ── 嘗試 vLLM（預設優先） ──
        use_vllm = os.environ.get("CADHLLM_BACKEND", "auto")
        if use_vllm in ("vllm", "auto"):
            try:
                from lib.vllm_client import is_vllm_available, vllm_generate
                if is_vllm_available():
                    self._log(progress_cb, "使用 vLLM 推論引擎")
                    t0 = time.time()
                    raw = vllm_generate(
                        prompt,
                        max_tokens=self.max_new_tokens,
                        temperature=self.temperature,
                        lora_adapter="cadhllm_lora",
                    )
                    elapsed = round(time.time() - t0, 1)
                    return raw, elapsed, "vllm"
                elif use_vllm == "vllm":
                    raise ConnectionError("CADHLLM_BACKEND=vllm 但 vLLM server 不可用")
            except ImportError:
                if use_vllm == "vllm":
                    raise
            except ConnectionError:
                if use_vllm == "vllm":
                    raise
                self._log(progress_cb, "vLLM 不可用，fallback to transformers")

        # ── Fallback: transformers 本地推論 ──
        self._log(progress_cb, f"adapter: {self.adapter_path}")
        if not Path(self.adapter_path).exists():
            raise FileNotFoundError(
                f"LoRA adapter 不存在：{self.adapter_path}\n"
                "請先執行訓練：.venv/Scripts/python.exe tools/train_phase1.py"
            )
        model, tokenizer = _load_model(self.adapter_path, self.load_4bit)
        self._log(progress_cb, "推論中...")

        import torch
        t0 = time.time()
        with torch.inference_mode():
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            input_len = inputs["input_ids"].shape[1]
            outputs = model.generate(
                **inputs,
                max_new_tokens  = self.max_new_tokens,
                temperature     = self.temperature,
                do_sample       = self.temperature > 0,
                pad_token_id    = tokenizer.eos_token_id,
            )
        elapsed = round(time.time() - t0, 1)
        raw = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)
        return raw, elapsed, "transformers"

    # ── 內部輔助 ──────────────────────────────────────────
    _MAX_INSTRUCTION_CHARS = 800

    def _build_prompt_with_rag(
        self,
        instruction: str,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> str:
        """建構含 RAG context 的 Phase I prompt。

        RAG context 注入 system prompt 尾部，保留訓練格式核心不變。
        RAG 不可用或失敗時 graceful fallback 到無 RAG prompt。
        """
        if len(instruction) > self._MAX_INSTRUCTION_CHARS:
            self._log(progress_cb,
                      f"輸入過長（{len(instruction)} chars），截斷至 {self._MAX_INSTRUCTION_CHARS}")
            instruction = instruction[:self._MAX_INSTRUCTION_CHARS]
        rag_context = ""
        try:
            from lib.rag import build_phase1_context
            rag_context = build_phase1_context(instruction, top_k=3)
            if rag_context:
                self._log(progress_cb, f"RAG context 注入（{len(rag_context)} chars）")
        except ImportError:
            pass
        except Exception as exc:
            self._log(progress_cb, f"⚠️  RAG 查詢失敗，fallback 無 RAG: {exc}")

        if _format_prompt is not None:
            return _format_prompt(instruction, rag_context=rag_context)

        from training.prompts import SYS_PHASE1
        system_msg = SYS_PHASE1
        if rag_context:
            system_msg = system_msg + "\n" + rag_context + "\n"
        return (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_msg}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{instruction}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    @staticmethod
    def _parse_output(raw: str) -> dict:
        """使用 lib/tools.extract_json（含 json_repair fallback）解析模型輸出，
        並做 post-repair schema 驗證確保結構完整。"""
        if _extract_json is None:
            # 基礎設施失敗(lib.tools / lib/tools fallback 皆 import 失敗),
            # 並非「輸入太抽象」。不可回傳 {} 讓 execute() 誤報成 Phase1InputError。
            raise RuntimeError(
                "lib.tools.extract_json 無法載入,Phase I 輸出解析依賴缺失;"
                "這是基礎設施錯誤,並非使用者輸入太抽象。"
            )
        result = _extract_json(raw)
        if isinstance(result, dict):
            return Phase1Handler._validate_p1_schema(result)
        return {}

    @staticmethod
    def _validate_p1_schema(obj: dict) -> dict:
        """Post-repair schema validation — 修正常見 LLM 輸出缺陷。

        確保 components 為 list[dict]，每個 dict 含 role + type；
        project_category 為合法值；缺失欄位補預設。
        回傳修正後的 dict，結構不可救則回傳空 dict。
        """
        try:
            from lib.config import TAXONOMY_CONFIG
        except ImportError as exc:
            # 驗證模組無法載入 → 不可靜默放行未驗證的 LLM 輸出（always-green-gate）。
            # 無法驗證就必須失敗,讓幻覺/非法元件類型不會繞過 post-repair guard。
            raise RuntimeError(
                "lib.config.TAXONOMY_CONFIG 無法載入,Phase I schema 驗證無法執行;"
                "拒絕回傳未驗證的模型輸出。"
            ) from exc

        comps = obj.get("components")
        if not isinstance(comps, list) or len(comps) == 0:
            return {}

        valid_types = TAXONOMY_CONFIG.get("all_valid_types", set())
        alias_map = TAXONOMY_CONFIG.get("alias_mapping", {})
        valid_roles = set(TAXONOMY_CONFIG.get("component_taxonomy", {}).keys())

        cleaned = []
        for c in comps:
            if not isinstance(c, dict):
                continue
            role = c.get("role", "")
            ctype = c.get("type", "")
            if not role or not ctype:
                continue
            ctype = alias_map.get(ctype, ctype)
            if ctype not in valid_types:
                continue
            if role not in valid_roles:
                role = _infer_role_from_type(ctype, TAXONOMY_CONFIG.get("component_taxonomy", {}))
            cleaned.append({**c, "role": role, "type": ctype, "qty": c.get("qty", 1)})

        if not cleaned:
            return {}

        cat = obj.get("project_category", "")
        valid_cats = TAXONOMY_CONFIG.get("project_categories", [])
        if cat not in valid_cats:
            obj["project_category"] = "Education"

        obj["components"] = cleaned
        return obj

    @staticmethod
    def _ensure_control(components: list, progress_cb) -> list:
        """若 components 中不含 Control 角色，發出 warning（不自動注入）。"""
        roles = {c.get("role") for c in components if isinstance(c, dict)}
        if "Control" not in roles:
            Phase1Handler._log(progress_cb,
                "[WARN] 模型未輸出 Control 元件（按鈕/旋鈕/開關），"
                "請在 CLARIFY 階段補充或由 Phase VII HITL 手動加入。")
        return components

    @staticmethod
    def _log(cb, msg: str):
        if cb:
            cb(f"[Phase I] {msg}")
        else:
            print(f"[Phase I] {msg}")
