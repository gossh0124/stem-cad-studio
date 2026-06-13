"""phase_handlers/phase2_handler.py — Phase II Component Registry Handler。

從 bridge.components 的 type 欄位查找元件規格，
補全 spec（dimensions, connector_ports, mounting_holes_count）。

單一 SSOT 架構：
- lib/registry.py::COMPONENT_REGISTRY 為唯一事實來源，使用 taxonomy 命名。
- self._registry 直接等於 SSOT，無靜態備援。
- 查詢失敗一律 raise ValueError，不靜默降級。
"""
from __future__ import annotations
import copy
import logging
import sys, os
from typing import Any, Callable, Dict, List, Optional, Tuple

_log = logging.getLogger("cadhllm.phase2")

from .base import PhaseHandler
from ..shared.models import Job, PhaseID
from lib.specs import (COMPONENT_SHORTHAND_ALIASES as _SHORTHAND_ALIASES,
                       POWER_BUDGET_MA as _POWER_BUDGET_MA,
                       USB_BUDGET_MA as _USB_BUDGET_MA,
                       POWER_MA as _POWER_MA,
                       lookup_constant as _lookup_constant)

try:
    from lib.wiring.template_gen import load_datasheet as _load_datasheet
except ImportError:
    def _load_datasheet(*_a, **_k):
        return {}

# ── 從 lib/registry.py 載入單一事實來源 ────────────────────────
def _load_registry_ssot() -> Dict[str, dict]:
    """將 COMPONENT_REGISTRY (ComponentSpec) 轉換為 phase2 期望的 dict 格式。

    使用 ComponentSpec.to_dict() 序列化（lib/registry.py），
    避免在此處手寫欄位轉換造成欄位漂移。
    """
    try:
        _lib_path = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
        if _lib_path not in sys.path:
            sys.path.insert(0, _lib_path)
        from registry import COMPONENT_REGISTRY  # type: ignore
        return {key: spec.to_dict() for key, spec in COMPONENT_REGISTRY.items()}
    except Exception as e:
        raise RuntimeError(
            f"lib/registry.py COMPONENT_REGISTRY 載入失敗：{e}\n"
            "請確認 lib/registry.py 存在且語法正確"
        ) from e




class Phase2Handler(PhaseHandler):
    """Phase II: Component Registry — 補全元件規格。

    查詢順序：lib/registry.py SSOT（taxonomy 名）→ 模糊匹配（_fuzzy_lookup）→ ValueError。
    """

    phase_id = PhaseID.P2

    # ── 別名表：SSOT 在 lib/specs.py COMPONENT_SHORTHAND_ALIASES ──
    _ALIASES = _SHORTHAND_ALIASES

    def __init__(self):
        self._registry = _load_registry_ssot()

    # ── 三層模糊匹配 ──
    def _fuzzy_lookup(self, ctype: str):
        """Direct → strip 比對 → token 集合 → 別名表 → None"""
        import re
        _strip = lambda s: re.sub(r'[^a-z0-9]', '', s.replace("-class", "").lower())

        def _tokens(s):
            s2 = s.replace("-class", "")
            toks = set()
            for p in re.findall(r'[a-zA-Z0-9]+', s2):
                for w in re.findall(r'[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z][a-z]|$)', p):
                    toks.add(w.lower())
            return toks

        bare = _strip(ctype)
        src_toks = _tokens(ctype)

        # Tier 1: strip 比對
        for key, val in self._registry.items():
            if bare == _strip(key):
                return val

        # Tier 2: token 集合比對（詞序無關）
        if len(src_toks) > 1:
            for key, val in self._registry.items():
                if src_toks == _tokens(key):
                    return val

        # Tier 3: 別名表
        alias_key = self._ALIASES.get(bare)
        if alias_key:
            return self._registry.get(alias_key)

        # Tier 4: 從複合描述中提取核心元件詞（Phase I 可能產生
        # 'microcontroller-with-sufficient-GPIO' 之類的描述型名稱）
        _NOISE = {'with', 'for', 'and', 'the', 'a', 'an', 'to', 'of', 'in',
                  'on', 'or', 'sufficient', 'adequate', 'suitable', 'small',
                  'large', 'mini', 'compact', 'standard', 'basic', 'simple',
                  'generic', 'integrated', 'built', 'multiple', 'single',
                  'digital', 'analog', 'external', 'internal', 'additional'}
        for tok in src_toks - _NOISE:
            tok_stripped = re.sub(r'[^a-z0-9]', '', tok.lower())
            hit = self._ALIASES.get(tok_stripped)
            if hit:
                return self._registry.get(hit)

        return None

    # ── CAG Layer 1: datasheet 精確規格 ──
    def _datasheet_spec(self, ctype: str) -> dict | None:
        """從 verified datasheet 提取元件物理/電氣規格，格式與 registry spec 相容。"""
        # 'datasheet 不存在' 由 _load_datasheet 回傳 {}（見 load_datasheet）；
        # 此處不吞例外——verified datasheet 存在卻解析失敗（如 JSONDecodeError）
        # 是資料損毀，必須大聲失敗，不可靜默降級為 registry-only 規格。
        ds = _load_datasheet()
        if not ds:
            return None

        entry = ds.get(ctype)
        if not entry and not ctype.endswith("-class"):
            entry = ds.get(f"{ctype}-class")
        if not entry or not isinstance(entry, dict):
            return None

        phys = entry.get("physical", {})
        elec = entry.get("electrical", {})
        spec: dict = {}

        if "length_mm" in phys:
            spec["length_mm"] = phys["length_mm"]
            if "width_mm" not in phys:
                raise ValueError(
                    f"元件 '{ctype}' 在 verified datasheet 中有 length_mm "
                    f"但缺少 width_mm — 請補全 data/component_datasheet_verified.json"
                )
            if "height_mm" not in phys:
                raise ValueError(
                    f"元件 '{ctype}' 在 verified datasheet 中有 length_mm "
                    f"但缺少 height_mm — 請補全 data/component_datasheet_verified.json"
                )
            spec["width_mm"] = phys["width_mm"]
            spec["height_mm"] = phys["height_mm"]
        if "weight_g" in phys:
            spec["weight_g"] = phys["weight_g"]
        if "current_typ_ma" in elec:
            spec["power_ma"] = elec["current_typ_ma"]
        if "voltage_operating_v" in elec:
            spec["voltage_v"] = elec["voltage_operating_v"]

        pin_layout = entry.get("pin_layout", {})
        ports = []
        for group in pin_layout.get("header_groups", []):
            ports.append({
                "name": group.get("name", ""),
                "pin_count": group.get("pin_count", 0),
                "side": group.get("side", ""),
            })
        if ports:
            spec["connector_ports"] = ports

        return spec if spec.get("length_mm") else None

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, Dict[str, Any]]:
        components: List[dict] = bridge.get("components", [])
        if not components:
            self._log(progress_cb, "⚠️  bridge.components 為空，跳過規格補全")
            return bridge, {"filled": 0, "missing": []}

        filled = 0
        _ENCLOSURE_ROLES = {"enclosure", "housing", "case", "chassis", "shell", "box"}

        for comp in list(components):
            role_lower = (comp.get("role") or "").lower()
            ctype = comp.get("type", "")

            if role_lower in _ENCLOSURE_ROLES or ctype.lower() in _ENCLOSURE_ROLES:
                components.remove(comp)
                ec = bridge.setdefault("enclosure_constraints", {})
                if comp.get("size"):       ec.setdefault("target_size", comp["size"])
                if comp.get("material"):   ec.setdefault("material", comp["material"])
                if comp.get("wall_thickness_mm"): ec.setdefault("wall_thickness_mm", comp["wall_thickness_mm"])
                self._log(progress_cb, f"  ⏭️ {ctype}: enclosure 角色，移至 enclosure_constraints")
                continue

            if not ctype:
                continue

            existing_spec = comp.get("spec") or {}

            # 已有完整規格（含 length/width/height）則跳過
            if all(k in existing_spec for k in ("length_mm", "width_mm", "height_mm")):
                self._log(progress_cb, f"  {ctype}: 規格已完整，跳過")
                continue

            # CAG Layer 1: verified datasheet 精確製造商數據
            ds_spec = self._datasheet_spec(ctype)

            reg_spec = self._registry.get(ctype)
            if reg_spec is None:
                reg_spec = self._fuzzy_lookup(ctype)
                if reg_spec:
                    self._log(progress_cb, f"  {ctype}: 模糊匹配成功")

            # 合併策略：datasheet 物理/電氣數據覆寫 registry 通用值
            if ds_spec and reg_spec:
                merged_base = copy.deepcopy(reg_spec)
                merged_base.update(ds_spec)
                reg_spec = merged_base
                self._log(progress_cb, f"  {ctype}: CAG datasheet 精確數據已合併")
            elif ds_spec and not reg_spec:
                reg_spec = ds_spec
                self._log(progress_cb, f"  {ctype}: CAG datasheet 直接命中（registry 未收錄）")

            if reg_spec:
                merged = copy.deepcopy(reg_spec)
                merged.update(existing_spec)   # 現有欄位優先保留
                merged.pop("is_placeholder", None)
                comp["spec"] = merged
                filled += 1
                self._log(progress_cb,
                    f"  ✅ {ctype}: {merged['length_mm']}×{merged['width_mm']}×{merged['height_mm']} mm, "
                    f"{len(merged.get('connector_ports', []))} ports")
            else:
                raise ValueError(
                    f"元件 '{ctype}' 在 datasheet / COMPONENT_REGISTRY / 模糊匹配中均找不到規格。\n"
                    "請在 data/component_datasheet_verified.json 或 lib/registry.py 中新增此元件。"
                )

        bridge["components"] = components
        bridge["components_resolved"] = True

        # ── 動態教育說明（根據專題脈絡生成）───────────────────
        self._enrich_educational_rationale(bridge, components, progress_cb)

        self._save_bridge_safe(job, bridge, progress_cb)

        # ── 早期功率稽核（在 Phase 3 之前提前警示）─────────────
        power_budget_ma = self._check_power_early(components, progress_cb)
        # 寫入 bridge 供 pipeline_runner 的 P2 gate 讀取
        bridge["power_warning_phase2"] = power_budget_ma
        if power_budget_ma.get("warning"):
            self._save_bridge_safe(job, bridge, progress_cb)

        summary = f"規格補全：{filled} 個完整"
        self._log(progress_cb, summary)
        return bridge, {
            "filled": filled, "missing": [], "summary": summary,
            "power_warning": power_budget_ma.get("warning", False),
        }

    def _enrich_educational_rationale(
        self,
        bridge: dict,
        components: List[dict],
        progress_cb,
    ) -> None:
        """為每個元件生成情境式教育說明。

        優先以 LLM 根據 project_category 動態生成；
        API 不可用時回退至 EDUCATIONAL_RATIONALE_TEMPLATES 靜態模板。
        """
        try:
            _lib = os.path.join(os.path.dirname(__file__), "..", "..", "lib")
            if _lib not in sys.path:
                sys.path.insert(0, _lib)
            from config import EDUCATIONAL_RATIONALE_TEMPLATES
        except ImportError:
            EDUCATIONAL_RATIONALE_TEMPLATES = {}

        category = bridge.get("project_category", "Education")
        project_name = bridge.get("project_name", "")
        comp_summary = ", ".join(
            f"{c.get('role','?')}={c.get('type','?')}" for c in components
        )

        # 嘗試 LLM 動態生成
        rationale_map = self._llm_generate_rationale(
            category, project_name, comp_summary, components, progress_cb
        )

        for comp in components:
            ctype = comp.get("type", "")
            if ctype in rationale_map:
                comp["educational_rationale"] = rationale_map[ctype]
            elif ctype in EDUCATIONAL_RATIONALE_TEMPLATES:
                comp["educational_rationale"] = EDUCATIONAL_RATIONALE_TEMPLATES[ctype]

    @staticmethod
    def _llm_generate_rationale(
        category: str,
        project_name: str,
        comp_summary: str,
        components: List[dict],
        progress_cb,
    ) -> Dict[str, str]:
        """呼叫 LLM 批次生成情境式教育說明，回傳 {component_type: rationale}。"""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return {}

        comp_list = "\n".join(
            f"- {c.get('type','?')} (角色: {c.get('role','?')})"
            for c in components
        )
        prompt = (
            f"你是 STEM 教育專家。以下是一個「{category}」類別的學生專題「{project_name}」，"
            f"使用了這些元件：\n{comp_list}\n\n"
            f"請為每個元件寫一句繁體中文的教育說明（50字以內），"
            f"解釋為什麼這個元件適合此專題，結合物理原理與應用場景。\n"
            f"格式：每行一個，用 | 分隔：元件type|說明\n"
            f"不要加序號或其他格式。"
        )

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text if resp.content else ""
            result: Dict[str, str] = {}
            for line in text.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key and val:
                        result[key] = val[:80]
            if result and progress_cb:
                progress_cb(f"[Phase II] 🎓 動態教育說明已生成（{len(result)} 個元件）")
            return result
        except Exception as _exc:
            _log.warning("LLM rationale generation failed: %s", _exc)
            return {}

    def _check_power_early(self, components: list, progress_cb) -> dict:
        """Phase 2 提前功率稽核：找出超載組合並立即警示。"""
        # 元件耗電與電源供電上限皆讀穿 specs(verified.json 單一官方源，#20/B2)——早期警示
        # 與 Phase 3 BOM 同源。耗電用 POWER_MA(electrical.current_typ_ma，alias-aware via
        # lookup_constant);先前 _MA_FALLBACK 手刻副本(與 POWER_MA 漂移，如 Servo-SG90 250 vs
        # 官方 150)+ 冗餘 datasheet 覆寫迴圈已刪。未知元件預設 20mA(早期警示為軟估計，非 raise)。
        total_ma  = sum(_lookup_constant(_POWER_MA, c.get("type", ""), 20) * c.get("qty", 1)
                        for c in components)
        supply_ma = _USB_BUDGET_MA
        for c in components:
            t = str(c.get("type", ""))
            if t in _POWER_BUDGET_MA:
                supply_ma = _POWER_BUDGET_MA[t]
                break
        if total_ma > supply_ma:
            msg = (f"⚡ [Phase II 早期警示] 總功耗 {total_ma}mA > "
                   f"電源上限 {supply_ma}mA，建議升級至 USB-Buck-5V-class (2A)")
            self._log(progress_cb, msg)
            return {"warning": True, "total_ma": total_ma, "supply_ma": supply_ma}
        return {"warning": False, "total_ma": total_ma, "supply_ma": supply_ma}

    @staticmethod
    def _log(cb: Optional[Callable], msg: str):
        prefix = "[Phase II] "
        if cb:
            cb(prefix + msg)
        else:
            print(prefix + msg)
