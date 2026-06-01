# CADHLLM 專案計畫書

> 版本：v3.0 | 日期：2026-05-03  
> 自然語言 → 端到端 3D 列印 STEM 作品，遵循 6E 教育框架
>
> **本檔為設計期文件**：階段（phase）與架構的**權威現況**以 [ROADMAP.md](ROADMAP.md) 為準（對齊 `services/phase_handlers/` 實際 handler）。本檔保留供設計沿革參考。

---

## 一、專案定位

將自然語言需求轉換為**完整可列印的 STEM 產品**（外殼 + 電子選型 + 電氣接線 + 韌體 + 教育推理），區別於 CAD-HLLM 等純幾何生成研究。

**核心差異化：**
- 多元件組裝體（非單一零件）
- 電氣驗證 + Schematic 接線圖
- 元件殼跨專案可複用，組裝邏輯專案獨特
- STEM 6E 教育框架整合
- Human-in-the-Loop 閉環設計

---

## 二、Pipeline 架構總覽

```
用戶 prompt
  → Phase I    意圖理解 + 子系統規劃         [LoRA-A]
  → Phase II   方向確認 + 規格補全           [Clarify UI + REGISTRY]
  → Phase III  電氣工程                      [Pin 分配 + Wiring + Schematic]
  → Phase IV   機構工程                      [元件殼 + 組裝決策 + 物理引擎]
  → Phase V    輸出渲染                      [3D + Schematic SVG + Firmware]
  → Phase VI   驗證閉環                      [VLM + LoRA-A 修正]
  → Phase VII  人工修正                      [HITL + LoRA-A 意圖轉譯]
```

---

## 三、各 Phase 詳細定義

### Phase I — 意圖理解 + 子系統規劃

| 項目 | 內容 |
|------|------|
| 執行者 | LoRA-A（Llama 3.1 8B Instruct） |
| 輸入 | 用戶自然語言 prompt |
| 輸出 | bridge JSON（subsystems + components + enclosure_constraints） |
| 核心能力 | 語義理解、元件選型推理、中文教育推理生成 |

**輸出格式：**

```json
{
  "project_name": "auto_plant_waterer",
  "project_category": "Gardening",
  "cot_plan": {
    "high_level_plan": "設計 compact 尺寸的 Gardening 作品「自動澆花器」",
    "subsystems": [
      {"role": "主控板", "part": "Arduino Uno", "type": "Arduino-Uno-class",
       "reason": "採用 ATmega328P 微控制器...", "power_mw": 50, "pins": 0}
    ],
    "parameter_hints": {"enclosure_size": "compact", "material": "PLA",
                        "wall_thickness_mm": 2.0, "has_lid": true},
    "power_summary": {"total_mw": 505, "budget_mw": 500},
    "total_pins": 3
  },
  "components": [{"role": "Brain", "type": "Arduino-Uno-class", "qty": 1}],
  "enclosure_constraints": {"target_size": "compact", "max_dimension_mm": 150},
  "inventory_mentions": []
}
```

---

### Phase II — 方向確認 + 規格補全

| 項目 | 內容 |
|------|------|
| 執行者 | 前端 Clarify UI + COMPONENT_REGISTRY（確定性） |
| 輸入 | Phase I bridge JSON |
| 輸出 | 用戶確認的方向 + 精確物理規格（尺寸/電壓/電流/接口） |

**子步驟：**

```
Step 1: Clarify（前端 UI）
  用戶確認 Q1-Q3（使用場景/連線需求/電力來源）
  → 確認或調整 Phase I 的核心決策

Step 2: Registry Completion（確定性代碼）
  每個 component type → COMPONENT_REGISTRY 查詢
  補全：length_mm, width_mm, height_mm, voltage_v, current_ma,
        connector_ports[], mounting_holes[], price_ntd

Step 3: Extract View 呈現
  LLM 粗估值 vs REGISTRY 精確值 對比顯示
  差異標示警告（如功耗估計偏差 > 2x）
```

---

### Phase III — 電氣工程

| 項目 | 內容 |
|------|------|
| 執行者 | 確定性代碼（規則引擎） |
| 輸入 | Phase II 精確規格 + components |
| 輸出 | pin_allocation + wiring + electrical_checks + schematic_svg |

**子步驟：**

```
Step 1: 功耗預算驗證
  total_current vs supply_capacity
  → 通過 / 警告（建議升級電源）/ 失敗（強制升級）

Step 2: IO 可行性
  所需 GPIO pins vs MCU 可用 pins
  → 通過 / 警告（建議 I2C expander）/ 失敗（升級 MCU）

Step 3: Pin 分配
  為每個元件分配具體 GPIO 腳位
  規則：
    - Analog pins → 類比感測器（土壤/光敏）
    - PWM pins → Motor/Buzzer/LED 調光
    - I2C (SDA/SCL) → Display/多感測器
    - Digital → 其餘數位信號
    - 避免衝突：D0/D1 保留 Serial，ESP32 GPIO6-11 禁用

Step 4: 接線解析
  生成元件間實際接線關係（信號線 + 電源線 + 地線）
  高電流路徑標示（需 Relay/MOSFET 中繼）

Step 5: 電氣規則驗證
  - 電壓相容（3.3V/5V level shift）
  - 單 GPIO 電流 ≤ 20mA（A000066 官方規格；+3.3V pin ≤ 50mA）
  - 去耦電容需求
  - 接地迴路完整性

Step 6: Schematic SVG 生成
  元件方塊圖 + 信號/電源 Net 連線 + 教育標註
```

**輸出格式：**

```json
{
  "pin_allocation": {
    "D2": {"component": "Sensor-PIR-class", "signal": "OUT", "type": "digital_in"},
    "A0": {"component": "Sensor-SoilMoisture-class", "signal": "SIG", "type": "analog_in"},
    "D5": {"component": "Relay-Module-class", "signal": "IN", "type": "digital_out"}
  },
  "wiring": [
    {"from": "Arduino:5V", "to": "Sensor-PIR:VCC", "net": "5V_RAIL", "color": "red"},
    {"from": "Arduino:D2", "to": "Sensor-PIR:OUT", "net": "PIR_SIG", "color": "blue"},
    {"from": "Arduino:D5", "to": "Relay:IN", "net": "PUMP_CTRL", "color": "green"},
    {"from": "Relay:NO", "to": "Pump:+", "net": "PUMP_PWR", "color": "orange"}
  ],
  "electrical_checks": {
    "voltage_ok": true,
    "current_ok": true,
    "pin_count_ok": true,
    "warnings": ["Pump 需透過 Relay 驅動（電流 400mA > GPIO 20mA 上限）"]
  },
  "power_budget": {
    "supply_v": 5.0,
    "total_ma": 101,
    "budget_ma": 500,
    "ok": true
  },
  "schematic_svg": "<svg>...</svg>"
}
```

---

### Phase IV — 機構工程

| 項目 | 內容 |
|------|------|
| 執行者 | Layer 1 確定性 + Layer 2 LoRA-B + Layer 3 確定性 |
| 輸入 | Phase III wiring + Phase II specs + enclosure_constraints |
| 輸出 | 組裝體 STEP/STL |

**三層架構：**

#### Layer 1：元件通用殼（確定性、可快取）

```
輸入：REGISTRY spec（長寬高 + 接口位置 + 固定孔位）
輸出：單元件容納殼 STEP
性質：100% 確定性，跨專案快取

快取策略：
  key = component_type（如 "Arduino-Uno-class"）
  首次生成後寫入 shells/ 目錄
  後續專案直接讀取，零重複計算

驗證（元件級）：
  - 壁厚 ≥ 1.5mm
  - 無自交面
  - FDM 可列印（無懸臂 > 45°）
  → 單個失敗不影響其他元件
```

#### Layer 2：組裝決策（LoRA-B）

```
輸入：
  - subsystems（角色/零件/質量/發熱量）
  - environment（室內/戶外/穿戴）
  - wiring pairs（Phase III 接線關係）
  - enclosure_constraints（尺寸/材料）

輸出：Assembly Plan JSON
  - placement：每個元件的位置區域/朝向/分區
  - thermal：散熱策略（通風柵位置/面積/型式）
  - environmental：防水等級/密封分區
  - joints：結合方式（螺絲/卡扣/銷孔）+ 位置
  - cable_routing：走線路徑規劃

決策因子：
  - 物理平衡（重心在底座支撐面內）
  - 熱源管理（發熱源遠離熱敏元件，通風路徑暢通）
  - 光照方向（光感/PIR 朝正確方向）
  - 結構強度（重元件靠近支撐點）
  - 線路最短（高頻/大電流走線越短越好）
  - 維護性（電池/USB 朝可開啟面）
```

**LoRA-B 輸出格式：**

```json
{
  "placement_rationale": "水泵最重(45g)且發熱高放底部中央...",
  "layout": [
    {"component": "Arduino-Uno-class", "zone": "mid-center",
     "face_out": "side-back", "reason": "USB 維護口朝後"},
    {"component": "Pump-Water-class", "zone": "bottom-center",
     "face_out": "bottom", "reason": "重心穩定+靠近水源"},
    {"component": "Sensor-SoilMoisture-class", "zone": "bottom-probe",
     "face_out": "bottom", "reason": "探針穿出底部接觸土壤"}
  ],
  "thermal": {
    "heat_sources": [{"type": "Pump-Water-class", "mw": 2000}],
    "strategy": "side_vent_passive",
    "vent_placement": "side_lower",
    "vent_area_mm2": 80,
    "min_distance_from_sensor_mm": 25
  },
  "environmental": {
    "waterproof": false,
    "ip_rating": "IP20",
    "sealed_zones": [],
    "exposed_zones": ["soil_probe"]
  },
  "joints": {
    "lid_method": "snap_fit_4x",
    "base_method": "screw_boss_4x_M3",
    "reason": "室內輕量使用，上蓋卡扣方便維護"
  },
  "cable_routing": [
    {"from": "Arduino-Uno-class", "to": "Relay-Module-class",
     "path": "channel_bottom", "current_ma": 20},
    {"from": "Relay-Module-class", "to": "Pump-Water-class",
     "path": "channel_isolated", "current_ma": 400}
  ]
}
```

#### Layer 3：物理引擎（確定性執行）

```
輸入：Layer 2 Assembly Plan + Layer 1 元件殼
執行：
  1. 重心驗證 → 質量×座標求解，確認 CoG 投影在底座內
  2. 熱場分析 → 依功耗計算所需通風面積，生成柵條幾何
  3. 結構生成 → 螺絲柱/卡扣/銷孔的精確幾何
  4. 走線通道 → 依 wiring pairs 在殼壁生成走線槽
  5. 密封結構 → IP 等級對應的 O-ring 槽 / 防塵唇
  6. 外殼合成 → 將所有結構整合為最終殼體

驗證（組裝級）：
  - 元件間無干涉（Boolean 碰撞檢測）
  - 重心穩定性 ✓
  - 通風路徑無遮擋 ✓
  - 最小壁厚 ≥ 1.5mm ✓
  - FDM 列印可行 ✓
  → 失敗僅重跑 Layer 2 + Layer 3（不重做元件殼）

輸出：底座 STL + 頂蓋 STL（或多件分件）
```

---

### Phase V — 輸出渲染

| 項目 | 內容 |
|------|------|
| 執行者 | 確定性代碼 |
| 輸入 | Phase III schematic_svg + Phase IV STL + Phase III wiring |
| 輸出 | 前端可顯示的所有視覺資料 |

**輸出項目：**

| 輸出 | 格式 | 前端 View |
|------|------|-----------|
| 3D 外殼預覽 | STL → Three.js | 3D View |
| Schematic 接線圖 | SVG（含動畫） | Schematic View |
| 韌體代碼 | .ino / .py | Code View |
| BOM 清單 | JSON → 表格 | BOM View |
| 工程摘要 | JSON | Plan View |

**韌體生成規則：**
- 依 Brain type 選擇語言（Arduino → .ino，Microbit → .py，ESP32 → .ino + WiFi）
- 依 wiring 生成 `#define PIN_xxx` 對應 pin_allocation
- 依 components 生成初始化 + 主迴圈邏輯
- 附帶中文註解（STEM 教育用途）

---

### Phase VI — 驗證閉環

| 項目 | 內容 |
|------|------|
| 執行者 | 外部 VLM（GPT-4o）+ LoRA-A 修正指令 |
| 輸入 | Phase V 多視圖渲染 + 原始需求 |
| 輸出 | 驗證報告 + 修正指令（如需） |

**流程：**

```
Step 1: VLM 多視圖驗證（≤3 輪）
  將 3D 渲染 + Schematic 送入 VLM
  VLM 判斷：外殼合理性 / 元件可見性 / 整體美觀度
  → PASS：進入 Phase VII
  → FAIL：生成問題描述

Step 2: LoRA-A 修正指令生成（如 FAIL）
  VLM 問題描述 → LoRA-A 轉為結構化修改 JSON
  → 回饋至對應 Phase 重新執行

修正指令格式：
  {"action": "modify_enclosure", "field": "max_dimension_mm",
   "old_value": 80, "new_value": 95,
   "reason": "PIR 感測器高度超出原設計空間"}
```

---

### Phase VII — 人工修正

| 項目 | 內容 |
|------|------|
| 執行者 | 用戶 UI 輸入 + LoRA-A 意圖轉譯 |
| 輸入 | 用戶自由文字修改請求 |
| 輸出 | 結構化修改指令 → 回饋至對應 Phase |

**範例：**

```
用戶：「把水泵移到左邊，USB 口朝前面」
  → LoRA-A 轉譯：
    [
      {"action": "modify_placement", "component": "Pump-Water-class",
       "field": "zone", "new_value": "bottom-left"},
      {"action": "modify_placement", "component": "Arduino-Uno-class",
       "field": "face_out", "new_value": "side-front"}
    ]
  → 重跑 Phase IV-B Layer 2+3
```

---

## 四、LLM 規格

### 共用 Base Model

| 項目 | 規格 |
|------|------|
| 模型 | Llama 3.1 8B Instruct |
| 量化 | 4bit bnb-nf4 |
| 推論 VRAM | ~5GB |
| 訓練環境 | Google Colab（T4 / A100） |
| 推論環境 | 待定（本地開發 / 雲端生產） |
| Adapter 切換 | Hot-swap，base 常駐 VRAM |

### LoRA-A：意圖理解 + 規劃 + 修正

| 項目 | 規格 |
|------|------|
| 使用階段 | Phase I / Phase VI / Phase VII |
| 任務 | 自然語言 → 結構化 JSON |
| 訓練資料 | 1200+ 筆（TAXONOMY 組合生成 + 修正指令格式） |
| LoRA 參數 | r=16, alpha=32, target: q/k/v/o/gate/up/down |
| Prompt 格式 | Llama 3.1 chat template |
| Completion | JSON + `<\|eot_id\|>` |

### LoRA-B：空間推理 + 組裝決策

| 項目 | 規格 |
|------|------|
| 使用階段 | Phase IV Layer 2 |
| 任務 | subsystems + 環境 → Assembly Plan JSON |
| 訓練資料 | 50~200 筆（GPT-4o 生成 + 人工審核） |
| LoRA 參數 | 同 LoRA-A |
| 前置條件 | Phase A 驗證通過後開始 |

### 升級路徑

```
現階段：Llama 3.1 8B Instruct
若不足：Phi-4 14B（推理強）或 Llama 4 Scout 17B（MoE 高效）
升級方式：只需重訓 adapter，架構不變
```

---

## 五、前端呈現（V3 Variant B）

### UI 狀態機

```
idle → clarify → extract → plan → schematic → 3d → code → bom → evaluate
```

### 各 View 資料來源

| View | 資料來源 Phase | 關鍵資料 |
|------|---------------|---------|
| Clarify | I | clarify_questions / fallback Q1-Q3 |
| Extract | I + II | subsystems + REGISTRY spec 對比 |
| Plan | I | subsystems 表（中文角色/功耗/接腳） |
| Schematic | III | schematic_svg + wiring + pin_allocation |
| 3D | IV | STL files → Three.js |
| Code | V | firmware .ino/.py |
| BOM | II + III | components + price + qty |
| Evaluate | VI | VLM report + checks |

### 設計原則

- 前端是**純 render 層**，零語義分析
- 所有決策由 LLM 或確定性代碼完成
- SSE 逐步推送，用戶感知等待 < 10 秒

---

## 六、技術約束

1. **模型**：Llama 3.1 8B Instruct，LoRA r=16 alpha=32
2. **訓練**：Google Colab，4bit 路徑
3. **核心角色**：Brain / Power / Control（不可增減）
4. **元件命名**：canonical name 後綴 `-class`
5. **inventory_mentions**：Phase I 永遠為 `[]`
6. **CAD 引擎**：CadQuery / build123d，降級鏈：manifold3d → struct STL
7. **TRL 格式**：Llama 3.1 chat template，completion 結尾 `<|eot_id|>`
8. **bridge JSON**：各 Phase 只能新增欄位，不可刪除或改寫上游
9. **合法 category（6 個，2026-05-08 移除 Wearables）**：Smart_Home / Robotics / Interactive_Art / Gardening / Security / Education
10. **元件殼快取**：同 type 跨專案複用，不重複生成
11. **LoRA 切換**：同 base model，adapter hot-swap
12. **電氣規則**：GPIO ≤ 20mA（A000066 官方規格）、+3.3V pin ≤ 50mA、5V rail ≤ 500mA、3.3V/5V level shift

---

## 七、交付時程

### Phase A：核心鏈驗證（現在 → 2 週）

| 任務 | 驗證條件 |
|------|---------|
| LoRA-A 訓練完成 | Colab 訓練無報錯 |
| Phase I 推論品質 | 10 test prompts，JSON 合法率 > 95% |
| 前端 Clarify→Extract→Plan | 中文子系統表 + 功耗條正確顯示 |
| Phase II REGISTRY 補全 | bridge JSON 精確規格欄位完整 |
| Phase III 電氣工程 | Pin 分配合法 + Schematic SVG 生成 |

### Phase B：CAD 最小可行（2-4 週）

| 任務 | 驗證條件 |
|------|---------|
| Layer 1：10 個高頻元件殼 | 各殼 STL 通過壁厚/列印性 |
| Layer 3：基礎組裝 | bbox 排列 + 螺絲柱，無干涉 |
| Phase IV→V 端對端 | 5 案例生成可列印 STL + 3D 預覽 |
| Phase V 韌體生成 | 生成可編譯的 .ino 代碼 |

### Phase C：智慧組裝（4-8 週）

| 任務 | 驗證條件 |
|------|---------|
| LoRA-B 訓練資料 50+ 筆 | GPT-4o 生成 + 人工審核 |
| LoRA-B 推論驗證 | 佈局合理率 > 80% |
| Layer 3 完整 | 通風柵/卡扣/走線槽/密封 |
| Phase VI VLM 閉環 | 3 輪後通過率 > 80% |

### Phase D：論文就緒（8-12 週）

| 任務 | 驗證條件 |
|------|---------|
| 7 category 全覆蓋 | 每 category 3+ 成功案例 |
| 對比實驗 | 規則 vs LoRA-B 量化比較 |
| 用戶研究 | STEM 教育成效 |
| 論文撰寫 | 投稿目標確認 |

---

## 八、風險與緩解

| 風險 | 等級 | 緩解策略 |
|------|------|---------|
| LoRA-A 中文推理品質不足 | 低 | json_repair fallback + Phase II 修正 |
| LoRA-B 訓練資料不足 | 中 | 規則引擎兜底 80%，LoRA-B 做增強 |
| CadQuery 布爾運算失敗 | 低 | 降級鏈 + 簡化幾何 |
| VLM API 不可用 | 低 | Phase VI 可 skip，HITL 替代 |
| 8B 空間推理天花板 | 中 | 預留 Phi-4 14B 升級路徑 |
| Schematic 接線複雜度 | 低 | MCU 限制（Arduino 最多 ~14 GPIO）天然限制規模 |

---

## 九、檔案結構

```
StemAiAgent/
├── services/              ← FastAPI 服務層（主源）
│   ├── gateway/main.py
│   ├── pipeline_runner.py
│   ├── phase_handlers/
│   │   ├── phase1_handler.py   ← LoRA-A 推論
│   │   ├── phase2_handler.py   ← REGISTRY 補全
│   │   ├── phase3_handler.py   ← 電氣工程（Pin/Wiring/Schematic）
│   │   ├── phase4_handler.py   ← 機構工程（Layer 1+2+3）
│   │   ├── phase5_handler.py   ← 渲染 + 韌體
│   │   ├── phase6_handler.py   ← VLM 驗證
│   │   └── phase7_handler.py   ← HITL
│   └── shared/
├── lib/                   ← 核心函式庫
│   ├── config.py          ← TAXONOMY_CONFIG SSOT
│   ├── registry.py        ← COMPONENT_REGISTRY（spec 唯一來源）
│   ├── tools.py           ← Phase I 推論工具
│   ├── wiring.py          ← Pin 分配 + 接線解析
│   ├── schematic.py       ← Schematic SVG 生成
│   ├── firmware.py        ← 韌體代碼合成
│   ├── cad_builder.py     ← Layer 1 元件殼 + Layer 3 物理引擎
│   ├── validator.py       ← Schema 驗證
│   └── validator_p3.py    ← 列印可行性驗證
├── training/              ← 獨立訓練包（Colab 執行）
│   ├── train.py
│   ├── config.py
│   ├── data_generator.py  ← LoRA-A 資料
│   └── trainer.py
├── saved_model/
│   ├── lora_a/            ← Phase I / VI / VII
│   └── lora_b/            ← Phase IV Layer 2（未來）
├── shells/                ← 元件通用殼快取（未來）
├── v3/variants/b/         ← V3 Variant B 前端
├── notebooks/             ← Colab 同步目標
└── docs/
    └── PROJECT_PLAN.md    ← 本文件
```

---

## 十、STEM 6E 對應

| 6E 階段 | Pipeline Phase | UI View | 教育目標 |
|---------|---------------|---------|---------|
| Engage | — | Idle | 激發興趣，一句話描述想法 |
| Explore | Phase I + II | Clarify + Extract | 探索可能性，理解元件選擇 |
| Explain | Phase III | Plan + Schematic | 解釋電氣原理，理解接線邏輯 |
| Engineer | Phase IV + V | 3D + Code | 工程實踐，理解結構設計 |
| Enrich | Phase V | Code + BOM | 延伸學習，韌體撰寫 |
| Evaluate | Phase VI + VII | Evaluate | 反思改進，驗證設計 |
