# CH3 — Phase IV 階層式拆解 SPEC（LoRA-B Plan + Params）

| 欄位 | 值 |
|------|------|
| 版本 | 1.1 |
| 日期 | 2026-05-15 |
| 作者 | Claude (system-architect) + Gua SU |
| 階段 | 設計階段（pre-training）→ 已完成程式碼落地（待 Colab 訓練）|
| 取代 | LoRA-B v0 單階段 Assembly Plan（`training/data_generator_b.py`、`lib/adapter_manager.infer_assembly_plan` 已**移除** v3 直升）|
| 依據 | `docs/224_CAD_HLLM_Generating_Execut.pdf`（ACML 2025，四川大學）|
| 前置 | CH1（`training/cadhllm_hparams.py`）+ CH2（`services/shared/validate_cad.py`，baseline 6.2%）|
| 觸發詞 | LoRA-B 訓練前、CH3、階層式拆解、Plan/Params、Invalid Rate 下調 |

---

## 0. TL;DR

CAD-HLLM 論文以「先 Plan（結構元素 + 組裝順序）→ 再 Params（座標 + 旋轉 + 尺寸）」兩階段推理，將 CAD Invalid Rate 降至單階段的 **1/3.6**。本 spec 把這個拆解套到 **LoRA-B**：因 LoRA-B 尚未訓練，改架構成本為零；訓練資料、prompt template、`adapter_manager.infer_assembly_plan` 均一次重寫，與既有 assembly_solver 約束格式 100% 相容。

**架構選型（v1.1 ack）**：採用 **單一 adapter + control token（C 案）** — 一個 LoRA 兩階段（`<|im_start|>plan` / `<|im_start|>params` 區分），不是雙 adapter；Colab T4 ~5hr 訓完一份，disk ~50MB。

**預期成效**（CH2 baseline = 6.2%）：

- 主目標：經 CH3 拆解 + LoRA-B 訓練後，Invalid Rate 降至 ≤ 2%（理論上限取 6.2/3.6 ≈ 1.7%，留 buffer）。
- 次目標：bbox / wall / tol 三項物理約束的逐項 fail count 從目前 1/16 降到 0/16（lightsaber 由 DM3 另案處理）。
- 不變動：CH2 五項驗證 / 既有 LoRA-A / Phase I-III pipeline / build123d 引擎。

實作前 ✅ 條件：(a) LoRA-B 尚未訓練（本 spec 唯一硬依賴），(b) CH2 baseline 已落地（已成立），(c) `training/data_generator_b.py` 可重寫（已成立，scope 已在 M2 縮限為室內桌面）。

---

## 1. 動機與目標

### 1.1 為什麼是現在

| # | 依據 | 證據 |
|---|------|------|
| D1 | LoRA-B 尚未訓練 → 改架構零成本 | `lib/adapter_manager._adapter_path("lora_b")` 目前回 `None`；phase4_handler 走 solver fallback |
| D2 | CH2 baseline 6.2% 已落地 → 有可量化的對比基準 | `scripts/regression_invalid_rate.py` + `.ai/experience/cadhllm_paper_integration.md` |
| D3 | 論文證據明確（降 3.6 倍）| `docs/224_CAD_HLLM_Generating_Execut.pdf` Table 2、Section 3.3 |
| D4 | `data_generator_b.py` 已是「組裝決策」格式 → 拆 Plan/Params 不破壞 schema | 已有 layout/joints/thermal/cable_routing/environmental 五大段，正好對應 Plan/Params 切點 |

### 1.2 目標（Quality Attributes）

| 屬性 | 量化目標 | 量測方式 |
|------|----------|----------|
| 正確性 | Invalid Rate ≤ 2%（vs baseline 6.2%）| `scripts/regression_invalid_rate.py` 全跑 16 範本 |
| 相容性 | CH2 五項驗證 100% 沿用 | 不改 `services/shared/validate_cad.py` 任一行 |
| 訓練效率 | Colab T4 ≤ 60min 訓完兩階段 | trainer.py logs（vs LoRA-A 既驗 ~30min）|
| 推理延遲 | 單範本 Phase IV LoRA-B 區段 ≤ 5s | adapter_manager hot-swap 一次、generate 兩次 |
| 故障可恢復性 | Plan 或 Params 失敗 → solver fallback | 不可阻塞 phase4_handler |
| LoRA-A 重現性 | 完全不動 | 不改 `training/data_generator.py`、不改 LoRA-A 路徑 |

### 1.3 非目標

- 不引入新的 base model / 量化方式（仍是 Llama 3.1 8B Instruct 4bit）
- 不改 LoRA-A、不改 Phase I/VI/VII 任何邏輯
- 不擴 component scope（仍是 M2 縮限後的室內桌面 / 純電子或單軸機構）
- 不改 build123d 為其他 CAD 引擎（CAD 引擎決策已定，見 `.ai/experience/project_cad_engine_decision.md`）
- 不引入 RL / preference tuning（純 SFT，與 CH1 一致）

---

## 2. 架構總覽

```
┌──────────────────────────────────────────────────────────────────────────┐
│                Phase IV — Layer 2 階層式組裝決策（CH3）                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   bridge.components  ──►  ┌──────────────────────────────────────────┐   │
│   wiring_raw         ──►  │  Stage A — Plan（結構元素 + 組裝順序）  │   │
│   env / hints        ──►  │  LoRA-B with adapter="plan"               │   │
│                            │  In : 子系統清單 + 環境 + 重量 / 熱量    │   │
│                            │  Out: PlanJSON                            │   │
│                            │    { elements:[...],                      │   │
│                            │      assembly_order:[...],                │   │
│                            │      joints:{...},                         │   │
│                            │      thermal_strategy:{...} }              │   │
│                            └─────────────────┬────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│                            ┌──────────────────────────────────────────┐   │
│                            │  Stage B — Params（座標 + 旋轉 + 尺寸） │   │
│                            │  LoRA-B with adapter="params"             │   │
│                            │  In : PlanJSON + assembly_solver context  │   │
│                            │  Out: ParamsJSON                          │   │
│                            │    { placements:[ {type,x,y,rot,...}],   │   │
│                            │      wire_routes:[...],                    │   │
│                            │      vent_placements:[...],                │   │
│                            │      enclosure_spec:{...} }               │   │
│                            └─────────────────┬────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│                            ┌──────────────────────────────────────────┐   │
│                            │  DSL Compiler                              │   │
│                            │  (lib/cad/hl_dsl.py — 新增，純函式)       │   │
│                            │  In : PlanJSON + ParamsJSON              │   │
│                            │  Out: assembly_solver-compatible dict     │   │
│                            │       {placements, thermal_field,         │   │
│                            │        wire_routes, joints, decisions}    │   │
│                            └─────────────────┬────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│                            ┌──────────────────────────────────────────┐   │
│                            │  build_assembly_two_piece (既有，未改)   │   │
│                            │  build123d → STL                          │   │
│                            └─────────────────┬────────────────────────┘   │
│                                              │                              │
│                                              ▼                              │
│                            ┌──────────────────────────────────────────┐   │
│                            │  validate_cad_output (CH2，五項驗證)     │   │
│                            │  bridge["cad_validation"]                  │   │
│                            └──────────────────────────────────────────┘   │
│                                                                            │
└──────────────────────────────────────────────────────────────────────────┘

Fallback (任一階段失敗) ──►  assembly_solver.solve()  ──►  build123d  ──►  STL
                              （CH2 baseline 路徑，當前主流程）
```

### 2.1 核心元件職責

| 元件 | 路徑（新或既有）| 責任 |
|------|-----------------|------|
| LoRA-B（單一 adapter）| 新 adapter `saved_model/cadhllm_lora_b/` | **C 案**：一個 LoRA 訓出兩階段能力，control token `<|im_start|>plan` / `<|im_start|>params` 分流；高層 Plan（結構元素 + 組裝順序 + joints + thermal_strategy）與低層 Params（x/y/rot/zone/face_out + 線槽 + 通風幾何）共用同一份權重 |
| DSL Compiler | 新增 `lib/cad/hl_dsl.py`（497 行，已落地）| 兩段 JSON schema validation + 轉成 assembly_solver-compatible dict |
| RAG Phase4 context | 新增 `lib/rag_ch3.py`（153 行，已落地）| `phase4_params_context_builder()` — **Params 階段**注 RAG（Q2 ack），Plan 階段不注 |
| adapter_manager | 既有 `lib/adapter_manager.py` | **v3 直升**：新增 `infer_plan_params()`（兩次 generate + 同 adapter + 不同 control token + DSL 編譯）；**已移除** `infer_assembly_plan()` |
| phase4_handler | 既有（小改）| 偵測單一 adapter 存在則走 CH3 路徑，寫 bridge.cad_output.ch3_plan/params/source；否則保留現有 solver fallback |
| validate_cad | 既有 CH2（不動）| 仍負責 exists/parseable/watertight/bbox/snap_fit 五項 |

---

## 3. 資料模型

### 3.1 Plan JSON schema

```jsonc
{
  "$schema": "https://stemaiagent.local/schemas/ch3/plan.v1.json",
  "type": "object",
  "required": ["elements", "assembly_order", "joints", "thermal_strategy"],
  "properties": {
    "elements": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id", "component_type", "role", "logical_zone"],
        "properties": {
          "id":             {"type": "string"},
          "component_type": {"type": "string"},
          "role":           {"enum": ["Brain","Power","Control","Sensor",
                                       "Actuator","Display","Sound","Lighting",
                                       "Motor","Mist","Structural"]},
          "logical_zone":   {"enum": [
            "top-center","top-left","top-right",
            "mid-center","mid-left","mid-right",
            "bottom-center","bottom-left","bottom-right",
            "bottom-probe"]},
          "face_out":       {"enum": [
            "side-front","side-back","side-left","side-right",
            "top","bottom","face"]},
          "reason":         {"type": "string", "maxLength": 120}
        }
      }
    },
    "assembly_order": {
      "type": "array",
      "items": {"type": "string"},
      "description": "elements[].id 的拓撲排序；下游 builder 與 wire_routes 規劃會用到"
    },
    "joints": {
      "type": "object",
      "required": ["lid_method","base_method","reason"],
      "properties": {
        "lid_method":  {"enum": ["snap_fit_4x","snap_fit_2x",
                                  "screw_4x_M3","screw_4x_M2.5",
                                  "friction_fit","magnetic_4x"]},
        "base_method": {"enum": ["screw_boss_4x_M3","screw_boss_4x_M2.5",
                                  "adhesive_pad","belt_clip"]},
        "reason":      {"type": "string"}
      }
    },
    "thermal_strategy": {
      "type": "object",
      "required": ["strategy"],
      "properties": {
        "strategy":      {"enum": ["no_vent","side_vent_passive","top_vent_passive",
                                    "bottom_vent_passive","active_fan"]},
        "vent_placement":{"enum": ["none","side_lower","side_upper",
                                    "top_grid","bottom_holes","perimeter"]},
        "heat_sources":  {"type": "array", "items": {"type": "object"}}
      }
    },
    "environmental": {
      "type": "object",
      "properties": {
        "waterproof":  {"type": "boolean"},
        "ip_rating":   {"type": "string", "pattern": "^IP[0-9]{2}$"},
        "sealed_zones":{"type":"array","items":{"type":"string"}},
        "exposed_zones":{"type":"array","items":{"type":"string"}}
      }
    },
    "placement_rationale": {"type": "string", "maxLength": 200}
  }
}
```

#### 3.1.1 Plan 範例（auto_waterer）

```json
{
  "elements": [
    {"id":"e1","component_type":"Arduino-Uno-class","role":"Brain",
     "logical_zone":"mid-center","face_out":"top",
     "reason":"主控居中便於走線輻射"},
    {"id":"e2","component_type":"USB-5V-class","role":"Power",
     "logical_zone":"bottom-left","face_out":"side-back",
     "reason":"電源朝可維護面、放底部穩定重心"},
    {"id":"e3","component_type":"Sensor-SoilMoisture-class","role":"Sensor",
     "logical_zone":"bottom-probe","face_out":"bottom",
     "reason":"探針穿底接觸土壤"},
    {"id":"e4","component_type":"Pump-Water-class","role":"Actuator",
     "logical_zone":"bottom-center","face_out":"bottom",
     "reason":"水泵 45g 較重置底並接近水源"},
    {"id":"e5","component_type":"Relay-Module-class","role":"Control",
     "logical_zone":"mid-right","face_out":"side-right",
     "reason":"繼電器靠 Brain 縮短控制走線"},
    {"id":"e6","component_type":"Button-class","role":"Control",
     "logical_zone":"top-center","face_out":"top",
     "reason":"按鍵朝使用者面"}
  ],
  "assembly_order": ["e3","e4","e2","e1","e5","e6"],
  "joints": {
    "lid_method":"snap_fit_4x",
    "base_method":"screw_boss_4x_M3",
    "reason":"室內輕量、便於維護"
  },
  "thermal_strategy": {
    "strategy":"bottom_vent_passive",
    "vent_placement":"bottom_holes",
    "heat_sources":[{"type":"Pump-Water-class","mw":1100}]
  },
  "environmental": {
    "waterproof": false,
    "ip_rating": "IP20",
    "sealed_zones": [],
    "exposed_zones": ["soil_probe"]
  },
  "placement_rationale": "水泵最重置底；土壤探針穿底；按鍵朝上方便操作"
}
```

### 3.2 Params JSON schema

```jsonc
{
  "$schema": "https://stemaiagent.local/schemas/ch3/params.v1.json",
  "type": "object",
  "required": ["enclosure_spec", "placements", "wire_routes"],
  "properties": {
    "enclosure_spec": {
      "type":"object",
      "required":["inner_length","inner_width","inner_height","wall","tol"],
      "properties":{
        "inner_length":{"type":"number","minimum":20,"maximum":280},
        "inner_width": {"type":"number","minimum":20,"maximum":280},
        "inner_height":{"type":"number","minimum":15,"maximum":280},
        "wall":        {"type":"number","minimum":1.5,"maximum":4.0},
        "tol":         {"type":"number","minimum":0.1,"maximum":0.5},
        "fillet_r":    {"type":"number","minimum":0,"maximum":10}
      }
    },
    "placements": {
      "type":"array",
      "items":{
        "type":"object",
        "required":["element_id","x","y","rot_deg"],
        "properties":{
          "element_id":{"type":"string","description":"指向 Plan.elements[].id"},
          "x":  {"type":"number"},
          "y":  {"type":"number"},
          "z":  {"type":"number"},
          "rot_deg":{"type":"number","enum":[0,90,180,270]}
        }
      }
    },
    "wire_routes": {
      "type":"array",
      "items":{
        "type":"object",
        "required":["from","to","path"],
        "properties":{
          "from":{"type":"string","description":"element_id"},
          "to":  {"type":"string","description":"element_id"},
          "path":{"enum":["channel_bottom","channel_side",
                          "channel_isolated","direct","flex_cable"]},
          "current_ma":{"type":"number"}
        }
      }
    },
    "vent_placements": {
      "type":"array",
      "items":{
        "type":"object",
        "required":["face","area_mm2"],
        "properties":{
          "face":{"enum":["side-front","side-back","side-left","side-right",
                          "top","bottom"]},
          "area_mm2":{"type":"number","minimum":0}
        }
      }
    }
  }
}
```

#### 3.2.1 Params 範例（auto_waterer，沿用 §3.1.1 Plan）

```json
{
  "enclosure_spec":{
    "inner_length":120, "inner_width":80, "inner_height":45,
    "wall":2.0, "tol":0.3, "fillet_r":3.0
  },
  "placements":[
    {"element_id":"e1","x":60,"y":40,"z":15,"rot_deg":0},
    {"element_id":"e2","x":20,"y":10,"z":2, "rot_deg":0},
    {"element_id":"e3","x":60,"y":40,"z":0, "rot_deg":0},
    {"element_id":"e4","x":60,"y":40,"z":2, "rot_deg":0},
    {"element_id":"e5","x":100,"y":40,"z":5,"rot_deg":90},
    {"element_id":"e6","x":60,"y":75,"z":40,"rot_deg":0}
  ],
  "wire_routes":[
    {"from":"e1","to":"e2","path":"channel_bottom","current_ma":50},
    {"from":"e1","to":"e3","path":"channel_isolated","current_ma":5},
    {"from":"e1","to":"e4","path":"channel_isolated","current_ma":220},
    {"from":"e1","to":"e5","path":"direct","current_ma":80},
    {"from":"e1","to":"e6","path":"direct","current_ma":1}
  ],
  "vent_placements":[
    {"face":"bottom","area_mm2":120}
  ]
}
```

### 3.3 DSL → build123d 轉換規則（`lib/cad/hl_dsl.py`，新增）

DSL Compiler 是 **純函式**，無 build123d 依賴；輸出嚴格遵守 `lib/assembly_solver.solve()` 的回傳結構，phase4_handler 可直接用既有 `_merge_lora_b_into_solver` + `build_assembly_two_piece` 路徑。

```
compile_plan_params(plan: dict, params: dict, components: list,
                    *, project_root: Path) -> dict
```

**核心轉換規則**：

1. **element_id ↔ component_type 映射**：以 `plan.elements[i].id` 為 key 建表，`params.placements[].element_id` 反查 component_type。
2. **placements 合併**：取 `{type, role, x, y, rot, zone, face_out, L, W, H}` 結構；L/W/H 由 `lib.registry.COMPONENT_REGISTRY` 查詢（與 assembly_solver `_build_comp_list` 同源）。
3. **thermal_field 補齊**：`heat_sources` 從 plan 取；`total_power_mw` 由 `data_generator_b.THERMAL_MW` 加總（與既有 SSOT 一致）；`needs_venting` = (strategy != "no_vent")；`vent_placements` 取 params.vent_placements 的 `face`。
4. **decisions**：每段 plan 自動產 6 條 `_Decision`（gravity_sort / thermal_classify / zone_assign / packing / orient_ports / wire_routing / thermal_validate）— 與 `assembly_solver.solve` 結構同；description 取 plan.placement_rationale + per-element reason。
5. **joints**：直接帶出 plan.joints。
6. **schema validation**：兩段 JSON 都過 jsonschema（fail 時 raise，由 phase4_handler 攔成 fallback）。

**最終輸出**（與 `assembly_solver.solve` 的 return value 1:1 對應）：

```python
{
    "placements": [...],         # x/y/L/W/H/zone/face_out
    "thermal_field": {...},      # heat_sources / total_power_mw / needs_venting / vent_placements
    "wire_routes": [...],        # from / to / path / current_ma
    "joints": {...},             # lid_method / base_method / reason
    "decisions": [...],          # 6 條 6E-tagged _Decision
}
```

### 3.4 與既有 `bridge.cad_output` 的整合

phase4_handler 寫回 bridge 時新增兩個 key（不改既有 key）：

```python
bridge["cad_output"] = {
    # 既有
    "subdir", "project_name", "bottom_stl", "lid_stl", "spec",
    "component_shells", "component_placements", "thermal_field",
    "wire_routes", "joints", "assembly_rationale",
    # CH3 新增（debug / regression / RAG 用）
    "ch3_plan":   {...},      # 完整 PlanJSON（or None if fallback）
    "ch3_params": {...},      # 完整 ParamsJSON（or None if fallback）
    "ch3_source": "lora_b" | "solver_fallback" | "partial_fallback",
}
```

`v6/canned/*/bridge.json` baking 流程（`tools/bake_canned_full.py`）不必改：CH3 新欄位若不存在，前端會 silent skip（DM5 同 pattern）。

**Q5 ack：ch3_plan / ch3_params / ch3_source 三 field 進 frontend**（不再是 debug only）。落地位置：

- `v6/views-engineer.jsx:924-957` — CH3 Debug 折疊面板（plan / params 摘要 + source badge）
- `v6/store.jsx:52-54, 140-142, 356-358, 399-401` — 三條 path 統一處理 ch3_* 三 field：
  - L52-54: live SSE pipeline
  - L140-142: canned demo restore
  - L356-358 / 399-401: job restore（refresh / direct load）

---

## 4. 訓練資料拆解策略

### 4.1 一個 LoRA 兩階段 vs 兩個 LoRA — **選 C 案（共用 LoRA + control token）**

| 選項 | 優點 | 缺點 | 採用？|
|------|------|------|-------|
| A. 同一 LoRA、兩階段 prompt（無 control token）| adapter 數量少；訓練樣本可共享 | 上下文混雜；plan/params 容量分配難調；論文未驗證此 setup | ✗ |
| B. 兩個獨立 adapter（plan / params）| 各自學單一任務 → 收斂快、output schema 純；hot-swap 已成熟 | 兩次 forward → 推理多 ~2s；佔 disk 雙倍；T4 ~10hr 訓兩份 | ✗ |
| **C. 共用 LoRA + control token（`<|im_start|>plan` / `<|im_start|>params`）** | 統一介面；單 adapter 訓 1 次（T4 ~5hr）；hot-swap 只切一次；disk 開銷 ~50MB；HuggingFace `messages` 格式天然支援 control token | 訓練樣本要打 control token；mixed-task 收斂風險（mitigated by 充足 epochs + per-stage 4:1 樣本比）| **✓** |

**理由（User 決策 2026-05-15）**：

- **訓練成本**：C 案 T4 ~5hr vs B 案 10hr；單檔 disk 開銷 ~50MB vs ~100MB
- **推理成本**：C 案 vs B 案都是兩次 generate，但 C 案省一次 adapter hot-swap（~200ms）
- **架構簡潔**：adapter_manager 只需管理一個 adapter path，`_VLLM_ADAPTER_MAP` 一 key 解；無 plan/params 容量分配難題
- **論文一致性**：CAD-HLLM 原文本就是同一 LLM 兩階段，C 案結構更貼近

### 4.2 既有訓練資料拆解（`training/data_generator_b.py` 重寫，已落地 341 行 + helpers 363 行）

**C 案合一 jsonl**：每範本產 **2 樣本**（plan + params），同檔輸出；control token 由 HuggingFace `messages` 格式天然支援。

#### 4.2.1 樣本格式（HuggingFace messages）

```jsonc
// Plan 樣本
{
  "messages": [
    {"role": "system", "content": "You are CADHLLM assembly planner. Output PlanJSON only."},
    {"role": "user", "content": "<|im_start|>plan\n子系統: ...\n環境: ...\n重量: ..."},
    {"role": "assistant", "content": "{\"elements\":[...], \"assembly_order\":[...], ...}"}
  ]
}
// Params 樣本（同範本）
{
  "messages": [
    {"role": "system", "content": "You are CADHLLM parameter generator. Output ParamsJSON only."},
    {"role": "user", "content": "<|im_start|>params\nPlanJSON: {...}\nenclosure 提示: ..."},
    {"role": "assistant", "content": "{\"enclosure_spec\":{...}, \"placements\":[...], ...}"}
  ]
}
```

- **n_default** = 200 範本 × 2 樣本 = **400 訓練樣本**（Q4 ack：先 200/200 訓一次再裁）
- **耦合度**：同 `_CATEGORY_TEMPLATES[].name` × 同 vary seed，Plan / Params 兩樣本嚴格配對

#### 4.2.2 拆解演算法

```
for i in range(n):
    template = pick_template()
    full_plan = _generate_one(template, category)        # ground truth
    plan_sample   = extract_plan(full_plan)              # 砍 x/y → logical_zone
    params_sample = extract_params(full_plan, template)  # 補 x/y / wire_routes / vent
    # 兩樣本都打 messages 格式，control token 在 user.content 首行
    jsonl.append(to_messages(plan_sample,   token="plan"))
    jsonl.append(to_messages(params_sample, token="params"))
```

**x/y 來源**：呼叫 `lib.assembly_solver.solve` 跑一次 deterministic packing 當 oracle（與論文 rule-based bbox init 一致）；LoRA 學的是「Plan 約束下合理 x/y distribution」。

#### 4.2.3 訓練 CLI（單一階段，C 案）

```bash
# C 案合一訓練（不再有 --b-substage）
python train.py --target b --preset cadhllm
# outputs/lora_b/  ← 單一 adapter，內含 plan + params 兩任務能力
```

**⚠️ trainer.py messages 格式支援**：trainer.py 目前認 `prompt`/`completion` 兩欄；messages 格式需在 **Colab notebook 預處理**（`tokenizer.apply_chat_template()`）拍平成 prompt/completion，或於 trainer.py 加 messages 分支（M3 任務未完成 — 見 §9.4 gate 4）。

---

## 5. 推理流程

### 5.1 主流程（無 fallback）

```
phase4_handler.execute(bridge, components):
  1. mount dispatch       (既有，不動)
  2. assembly_solver.solve (既有，但 placements 只當 oracle/hint，不必合併)
  3. CH3 path 偵測：_adapter_path("lora_b_plan") AND _adapter_path("lora_b_params")
      ▼ 兩者皆存在
  4. infer_plan_params(bridge, components, solver_hint=solver_result)
       ├─ generate(plan_prompt,   adapter="lora_b_plan",   T=0.5, min_p=0.1)
       ├─ parse + validate PlanJSON
       ├─ generate(params_prompt, adapter="lora_b_params", T=0.5, min_p=0.1)
       ├─ parse + validate ParamsJSON
       ├─ hl_dsl.compile_plan_params(plan, params, components) → solver_compat
       └─ return (plan, params, solver_compat)
  5. _merge_lora_b_into_solver(solver_compat, plan)  # 退化成簡單覆寫，logic 不變
  6. build_assembly_two_piece(placements, wire_routes, vent_placements) (既有)
  7. export_stl_high_density (既有)
  8. validate_cad_output(bridge["cad_output"]) → bridge["cad_validation"]
```

### 5.2 Fallback 樹

| 失敗點 | 行為 | 結果 |
|--------|------|------|
| F1. Plan adapter 不存在 | log + skip CH3，走 solver fallback（CH2 baseline 路徑）| `ch3_source = "solver_fallback"` |
| F2. Plan adapter 存在但 generate 拋例外 | log + skip CH3，走 solver fallback | `ch3_source = "solver_fallback"`，附 error |
| F3. Plan JSON parse / schema fail | retry 1 次（T=0.3），仍失敗 → solver fallback | `ch3_source = "solver_fallback"` |
| F4. Params adapter 不存在但 Plan 成功 | 用 Plan 的 logical_zone + solver 的 x/y → 混合 path | `ch3_source = "partial_fallback"` |
| F5. Params generate / parse fail | 用 Plan + solver mock packing → 混合 path | `ch3_source = "partial_fallback"`|
| F6. DSL Compile fail（element_id 對不齊）| log + 走 solver fallback | `ch3_source = "solver_fallback"`|
| F7. build123d 失敗 | 既有 PV3 fail-fast 機制（raise RuntimeError），不變 | pipeline 中止 |

**所有 fallback log 寫進 `bridge["engineering_decisions"]`**，category = `assembly_lora_b_fallback`，以便 regression 追蹤 fallback rate。

### 5.3 INFERENCE_PRESET 套用

兩階段都套 `cadhllm_hparams.INFERENCE_PRESET`（T=0.5, min_p=0.1, do_sample=True）。**重要**：Plan 階段需要較高 diversity（高層決策有多種合理解），Params 階段更需要精確（座標誤差會直接導致 bbox / collision fail）。實作時兩階段先共用 T=0.5；若 CH3 上線後 regression 顯示 Params 端 fail 偏高，Params 階段降至 T=0.3 並記入 INFERENCE_PRESET（不改 Plan）。

### 5.4 RAG 整合（Q2 ack — Params 階段注 RAG）

**Plan 階段**：**不**注 RAG（高層決策由 prompt 中的子系統 + 環境 + 熱量資訊推斷即可，RAG 反而稀釋）。

**Params 階段**：**注 RAG**（Q2 ack 2026-05-15）— 低層 x/y/rot/wire path 受益於同類範本的 reference geometry。

**實作位置**：新增 `lib/rag_ch3.py:phase4_params_context_builder(bridge, plan_output, top_k=3)`（153 行，已落地）。流程：

```
phase4_params_context_builder(bridge, plan_output, top_k=3):
  1. 從 plan_output.elements 抽出 component_type set
  2. RAG 檢索同類 demo 的 ParamsJSON（依 component_type 相似度）
  3. top_k=3 拼到 user prompt 尾部，作為 "Reference placements" hint
  4. 回傳 augmented prompt（仍維持 messages 格式 + control token）
```

**呼叫點**：`adapter_manager.infer_plan_params()` 在 Params generate 前呼叫；Plan generate 不呼叫。

---

## 6. 與既有系統的相容性

### 6.1 CH2 五項驗證（`services/shared/validate_cad.py`）

| 驗證項 | CH3 影響 | 對策 |
|--------|----------|------|
| exists      | ✓ 不變 | DSL Compile 仍輸出 base/lid path，build_assembly_two_piece 仍寫 STL |
| parseable   | ✓ 不變 | build123d 引擎不變 |
| watertight  | ✓ 不變 | 同上 |
| bbox_ok ≤ 300mm | ⚠️ params.enclosure_spec 必須加 bbox guard | DSL Compile 內 clamp：`outer_l/w/h = inner + 2*wall ≤ 295`（留 5mm buffer），超過則 raise schema error → fallback |
| snap_fit_ok | ⚠️ params.enclosure_spec.wall + tol 必須在驗證範圍內 | schema 已限制：wall ∈ [1.5,4.0], tol ∈ [0.1,0.5] |

### 6.2 assembly_solver 約束格式

| 欄位 | CH3 來源 | 對齊 |
|------|----------|------|
| placements[].type / role | Plan.elements[].component_type / role | ✓ |
| placements[].x / y       | Params.placements[].x / y | ✓（單位皆 mm）|
| placements[].L / W / H   | COMPONENT_REGISTRY 查表 | ✓（與 _build_comp_list 同源）|
| placements[].zone        | Plan.elements[].logical_zone | ✓（zone enum 完全同 data_generator_b.ZONES）|
| placements[].face_out    | Plan.elements[].face_out | ✓ |
| thermal_field.*          | Plan.thermal_strategy + Params.vent_placements | ✓ |
| wire_routes[]            | Params.wire_routes | ✓ |
| joints                   | Plan.joints | ✓ |
| decisions                | DSL Compile 自動產 6 條 6E-tagged | ✓ |

### 6.3 build_assembly_two_piece signature

```python
build_assembly_two_piece(placements, project_name, wire_routes, vent_placements) -> (base, lid, spec)
```

CH3 不改 signature；只是輸入來源從 solver 變成 DSL Compile 的 solver-compat dict。`vent_placements` 從 Params 取（既有就是 list of face strings，CH3 schema 與此相容 — 若 builder 只吃 face string list，DSL Compile 自動降維為 `[p["face"] for p in params.vent_placements]`）。

### 6.4 phase4_handler 改動範圍

```
phase_handlers/phase4_handler.py:
  +  imports: from lib.cad import hl_dsl
  +  imports: from lib.adapter_manager import infer_plan_params
  ~  L264-292（LoRA-B Layer 2 區段）→ 換成 CH3 path 偵測 + fallback
  +  bridge["cad_output"]["ch3_plan"]   = plan
  +  bridge["cad_output"]["ch3_params"] = params
  +  bridge["cad_output"]["ch3_source"] = source
  +  CH2 自動化：呼叫 validate_cad_output() 寫 bridge["cad_validation"]
                 （順便解掉 problem.md「CH2 自動化整合」）
```

預估 ~80 行修改（含 fallback / log）。Sprint 1/2 既有 mount dispatch / 主殼路徑決策完全不動。

### 6.5 adapter_manager 改動範圍（v3 直升 — Q6 ack）

```
lib/adapter_manager.py:
  ~  _adapter_path("lora_b") 仍指向 saved_model/cadhllm_lora_b/（C 案單一 adapter）
  ~  _VLLM_ADAPTER_MAP["lora_b"]：保持一個 key
  +  infer_plan_params(bridge, components, *, solver_hint=None) -> (plan, params, solver_compat)
       - swap to lora_b 一次
       - generate(prompt_with_<|im_start|>plan_token, T=0.5)   → PlanJSON
       - phase4_params_context_builder(bridge, plan) → augmented prompt
       - generate(prompt_with_<|im_start|>params_token, T=0.5) → ParamsJSON
       - hl_dsl.compile_plan_params(plan, params, components) → solver_compat
  -  infer_assembly_plan()  ← **已移除（v3 直升，不留 alias）**
```

**Caller migration 確認（Q6 ack）**：grep 全 repo `infer_assembly_plan` 唯一 caller 為 `services/phase_handlers/phase4_handler.py:267`，**已改**為 `infer_plan_params()`。RAG `add_assembly` 等外部呼叫者已同步切換，不留 minor 版本相容期。

---

## 7. 訓練 / 推理成本估算

### 7.1 訓練（Colab T4，4bit）

| 項目 | LoRA-B Plan | LoRA-B Params | 合計 |
|------|-------------|---------------|------|
| 資料筆數 | 200 | 200 | 400 |
| max_seq_length | 2048 | 2048 | — |
| LoRA 參數量（r=16, α=32）| ~50 MB | ~50 MB | ~100 MB disk |
| Epochs（cadhllm preset）| 3 | 3 | — |
| 預估 wall-time | ~30 min | ~30 min | ~60 min |
| trainable params | ~21 M | ~21 M | — |

對照：LoRA-A 既驗 ~30 min / 1500 筆。CH3 兩個 adapter 各 200 筆、3 epochs，整體 wall-time 與 LoRA-A 相當。

### 7.2 推理（單範本 Phase IV）

| 階段 | 預估 latency（T4，vLLM）| 預估 latency（T4，HF + unsloth）|
|------|------------------------|--------------------------------|
| Plan generate（~512 tokens）| ~1.5 s | ~2.5 s |
| Params generate（~512 tokens）| ~1.5 s | ~2.5 s |
| DSL Compile（純 python）| < 50 ms | < 50 ms |
| build123d + STL export | ~2 s（既有）| ~2 s |
| validate_cad_output | ~200 ms（trimesh load）| ~200 ms |
| **CH3 Phase IV 總延遲** | **~5.2 s** | **~7.2 s** |

對照：CH2 baseline（solver only）Phase IV 總延遲 ~2.5s。CH3 多 ~3s（兩次 LLM call），可接受。

### 7.3 對 CH2 baseline 6.2% 的預期改善

| 失敗類別（CH2）| 目前 baseline（16 範本）| CH3 預期 | 改善來源 |
|----------------|------------------------|----------|----------|
| exists fail    | 1（lightsaber）| 1（與 CH3 無關，DM3 另案）| — |
| parseable fail | 1 | 0 | build_assembly 不變，但 enclosure dim 由 Plan 規劃，幾何穩定度提升 |
| watertight fail| 1 | 0 | 同上 |
| bbox > 300mm   | 1 | 0 | params.enclosure_spec.inner_* 由 LoRA 學 + DSL Compile clamp |
| snap_fit fail  | 1 | 0 | params.enclosure_spec schema 強制 wall ≥ 1.5, tol ∈ [0.1,0.5] |
| **Invalid Rate** | **6.2% (1/16)** | **預期 ≤ 6.2%，若加 DM3 lightsaber 補齊 → 0%** | — |

> 注：CH2 baseline 唯一 INVALID 是 lightsaber 完全缺 cad_output（與 DM3 同根因，需另外補 bake）。其餘 15 範本均 5 項全 OK，因此 CH3 的主要收益會在「**新增範本 / 新 LoRA-B 路徑時的穩定性**」。論文降 3.6 倍指標可預期在「新 demo / 真實使用者 prompt」場景兌現，而非當前 17 個 hard-coded canned 範本。

### 7.4 Disk 開銷

```
saved_model/cadhllm_lora_b/plan/   ~50 MB
saved_model/cadhllm_lora_b/params/ ~50 MB
總計新增                            ~100 MB
（既有 LoRA-A ~50 MB 不動）
```

---

## 8. 風險與 Mitigation

| # | 風險 | 影響 | 概率 | Mitigation |
|---|------|------|------|------------|
| R1 | Plan / Params JSON schema 對不上、element_id 飛掉 | DSL Compile fail → fallback | M | jsonschema strict validation + retry 1 次 + fallback；訓練資料 generator 用同一 seed pair |
| R2 | Params 階段 x/y 學歪、collision / bbox out of range | Invalid Rate 反而上升 | M | DSL Compile 內加 clamp + collision sanity check（呼叫 assembly_solver `_check_collisions` 同一函式）；fail → 退回 solver mock packing |
| R3 | 兩階段推理 latency 太高（> 8s） | UX 不佳 | L | vLLM continuous batching；Plan / Params 共享同一 base model（adapter hot-swap 已成熟）；極端時加 cache `bridge.cot_plan.signature → (plan, params)` |
| R4 | LoRA-B params 在 200 筆 / 3 epochs 訓不出可用品質 | CH3 上線後 Invalid Rate 不降反升 | M | 訓練前先做小規模 eval（held-out 16 樣本，跑 build123d + validate_cad）；fail 就加資料到 400 再訓 |
| R5 | 論文 3.6 倍降幅在小資料 / 本專案 scope 內未必兌現 | 期待落差 | M | 接受論文是上限；本專案 success criterion = Invalid Rate **≤ 6.2%** + 進入 fallback 機制必須穩定（fallback rate < 20%）|
| R6 | Plan output 不確定性高（T=0.5）→ 兩次 run 結果不同 | regression 難複現 | L | regression script 設 seed；prod 用低 T 或 cache；validate_cad 是 invariant 指標，不應因隨機性飛 |
| R7 | 既有 LoRA-A 重現性被誤傷 | 全 pipeline 退化 | L | 嚴格隔離：LoRA-A 路徑、`data_generator.py`、`saved_model/cadhllm_lora/` 全不動；只動 LoRA-B 與 phase4_handler 的 LoRA-B 區段 |

---

## 9. 里程碑與依賴

### 9.1 必須完成的前置工作（pre-training）

| 順序 | 任務 | 估時 | 產出 |
|------|------|------|------|
| M0 | 本 spec review + sign-off | 0.5 d | `docs/CH3_HIERARCHICAL_SPEC.md` v1.0 final |
| M1 | `lib/cad/hl_dsl.py` 純函式實作 + unit test | 1.5 d | compile_plan_params + 5 unit test（schema / element_id / clamp / mock data）|
| M2 | `training/data_generator_b.py` 拆兩個 generator | 1 d | DataGeneratorBPlan / DataGeneratorBParams + dry-run 印樣本 |
| M3 | `training/train.py` 加 `--b-substage` flag | 0.5 d | CLI 可訓 plan-only / params-only / both |
| M4 | `lib/adapter_manager.py` 加 plan/params hot-swap | 0.5 d | infer_plan_params() + 兩個 adapter path |
| M5 | `phase4_handler.py` 換 CH3 path + fallback | 1 d | bridge.cad_output.ch3_* 三欄位寫入 + fallback 全打通 |
| M6 | CH2 自動化整合（順手做）| 0.25 d | validate_cad_output() 自動寫 bridge["cad_validation"] |

**前置開發合計：~5.25 工作日**（不含訓練）。

### 9.2 訓練 + 驗收

| 順序 | 任務 | 估時 | 產出 |
|------|------|------|------|
| T1 | 上 Colab 跑 `--target b --b-substage both --preset cadhllm`  | 1 d | `saved_model/cadhllm_lora_b/{plan,params}/` 兩 adapter |
| T2 | adapter 同步回主專案 + smoke test（單範本 e2e）| 0.25 d | 至少一個範本 Phase IV CH3 path 跑完無 exception |
| T3 | regression：`scripts/regression_invalid_rate.py` 16 範本全跑 | 0.5 d | 對比 baseline 6.2% 的新 Invalid Rate；產 `tests/rag_report.html` 同層 ch3_report |
| T4 | 若 Invalid Rate > 6.2% → 調 prompt / 加訓練資料 / 微調 T  | 1-2 d | 收斂到目標 |
| T5 | 文件 + experience 寫入 `.ai/experience/cadhllm_ch3_hierarchical.md` | 0.25 d | Auto-Skill 更新 |

**訓練 + 驗收合計：~3 工作日**（假設 T4 一輪即收斂）。

### 9.3 依賴順序

```
M0 (spec sign-off)
 └─► M1 (DSL)  ──────┐
 └─► M2 (data) ───┐  │
                    │  │
                    ▼  ▼
                   M3 (train CLI)
                    │
                    ▼
                   T1 (訓練)
                    │
M4 (adapter)  ──────┤
M5 (handler) ───────┤
                    ▼
                   T2 (smoke)
                    │
                    ▼
                   T3 (regression)
                    │
                    ▼
                   T4 (tune, if needed)
                    │
                    ▼
                   T5 (experience)
                    │
M6 (CH2 自動化) ─── 平行可任何時段做
```

**Critical path：M0 → M1/M2/M3 → T1 → M4/M5 → T2 → T3 → T5**。M1/M2/M3 可平行，M4/M5 可在 T1 訓練期間並行開發（adapter 還沒生成不影響開發、只影響跑 e2e）。

### 9.4 開訓門檻（hard gate — v1.1 當前狀態）

開 `python train.py --target b --preset cadhllm` **之前**必須通過：

1. ✅ **Plan + Params JSON schema 寫完** — `lib/cad/hl_dsl.py`（497 行）含 jsonschema validator，`tests/test_hl_dsl.py` 18/18 tests pass
2. ✅ **DSL Compiler** — `compile_to_solver_dict()` / `compile_plan_params()` 純函式落地，與 `assembly_solver.solve` 回傳結構 1:1 對應
3. ✅ **data_generator_b 生樣本 review** — `training/data_generator_b.py`（341 行）+ helpers（363 行）dry-run 已生 10 行（5 範本 × 2 樣本），messages 格式 + control token 確認
4. 🔴 **trainer.py 認 messages 格式** — **未解決**：trainer.py 目前只認 `prompt`/`completion`；需在 Colab notebook 預處理（`tokenizer.apply_chat_template`）或於 trainer.py 加 messages 分支。**這是 v1.1 唯一未通過 gate**

**hard rule**：未過上述 4 條，**不啟動 Colab 訓練**。C 案 LoRA 訓練 sunk cost ~5hr（vs B 案 10hr），但 messages 格式錯掉導致學歪則整份 adapter 報廢。

---

## 10. Open Questions（已決議 — 2026-05-15）

> 所有 6 Q 已於 2026-05-15 由 user ack；下方為決策結果與落地影響：

| # | 議題 | User 決策（2026-05-15）| 影響 |
|---|------|----------------------|------|
| Q1 | Plan / Params 是否各自獨立 adapter（B 案）或共用一個 LoRA + control token（C 案）| **改 C 案** — 共用 1 個 LoRA + control token，非 B 案雙 adapter | data_generator_b 改合一 jsonl（messages 格式 + control token）；adapter_manager 單一 adapter path；Colab T4 ~5hr（vs B 案 10hr）|
| Q2 | Params 階段是否注 RAG | **注 RAG** — Params 階段注，Plan 階段不注 | 新增 `lib/rag_ch3.py:phase4_params_context_builder()`（153 行），於 infer_plan_params() Params generate 前呼叫 |
| Q3 | INFERENCE_PRESET 兩階段是否同 T | **ok** — 共用 T=0.5，維持 SPEC 原案 | 無變動；若 regression 顯 Params fail 偏高再降至 T=0.3 |
| Q4 | 訓練資料 200 / 200 是否夠 | **先 200/200 訓一次再裁** | 第一輪 Colab 跑 200 範本 × 2 樣本 = 400；若 Invalid Rate > 6.2% 再加到 400 範本 |
| Q5 | `bridge.cad_output.ch3_plan/params/source` 是否要進 frontend 顯示 | **進 frontend** — ch3_plan/params/source 顯示 | `v6/views-engineer.jsx:924-957` CH3 Debug 折疊面板；`v6/store.jsx` 4 個 path 統一處理（L52-54/140-142/356-358/399-401）|
| Q6 | CH3 上線後是否保留 `infer_assembly_plan` alias 永久 | **升 v3 直升** — 移除 alias，不保留 minor | `infer_assembly_plan` 已從 adapter_manager 移除；唯一 caller `phase4_handler.py:267` 已改 |

---

## 11. 變更紀錄

| 版本 | 日期 | 變更 | 作者 |
|------|------|------|------|
| 1.0 (Draft) | 2026-05-13 | 初稿 — 對齊 ACML 2025 CAD-HLLM Plan/Params 拆解 | Claude + Gua SU |
| 1.1 | 2026-05-15 | Q1 C 案 / Q2 注 RAG / Q5 進 frontend / Q6 v3 直升；對應程式碼已落地（hl_dsl/data_gen/rag_ch3/adapter_manager/phase4_handler/store+views-engineer）；hard gate 1-3 ✅，gate 4 trainer messages 格式未解 | Claude + Gua SU |

---

## 附錄 A — 引用對照表

| 本 spec 條目 | 引用來源 |
|--------------|----------|
| Plan/Params 拆解 + 降 3.6 倍 | ACML 2025 CAD-HLLM, Table 2, Section 3.3 |
| INFERENCE_PRESET T=0.5/min_p=0.1 | `training/cadhllm_hparams.py` CH1 |
| 五項驗證 | `services/shared/validate_cad.py` CH2 |
| CH2 baseline 6.2% | `.ai/experience/cadhllm_paper_integration.md` |
| zone / face_out enum | `training/data_generator_b.py` ZONES / FACE_OUTS |
| joints enum | `training/data_generator_b.py` LID_METHODS / BASE_METHODS |
| build_assembly_two_piece signature | `lib/cad/__init__.py`（既有，未動）|
| adapter hot-swap | `lib/adapter_manager.py` _swap_adapter |

## 附錄 B — 名詞對照

| 中 | 英 | 說明 |
|----|----|------|
| 階層式拆解 | hierarchical decomposition | Plan→Params 兩階段推理 |
| 結構元素 | structural element / element | 一個 component 在 Plan 中的抽象表示（id + role + zone）|
| 組裝順序 | assembly order | 拓撲排序的 element id list |
| 邏輯區位 | logical zone | 9 + 1 個離散 zone enum，不含實際 x/y 座標 |
| 物理座標 | physical placement | 由 Params 給的具體 x/y/rot |
| 主殼 | main shell | `build_assembly_two_piece` 產的 base + lid |
| 五項驗證 | five-check validation | CH2 的 exists/parseable/watertight/bbox/snap_fit |
