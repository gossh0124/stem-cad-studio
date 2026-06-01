# FRONTEND_DESIGN.md — 前端設計要點

> 版本：v1.0 | 日期：2026-05-03  
> 對應後端版本：`services/gateway/main.py`（21 端點）  
> 閱讀前提：已讀 `PROJECT_PLAN.md` 第五章（V3 Variant B UI 狀態機）

---

## 一、UI 狀態機

### 1.1 狀態定義

來源：`services/shared/models.py` `JobStatus`

```
PENDING          初始，Job 剛建立尚未執行
RUNNING          Pipeline 執行中（Phase I-VI 連續）
WAITING_CLARIFY  Phase I 完成後等待用戶確認（Clarify Gate）
WAITING_HITL     Phase VII 等待人工修正指令（HITL Gate）
SUCCESS          所有 Phase 完成
FAILED           任一 Phase 拋出例外
CANCELLED        用戶主動取消
```

### 1.2 狀態轉移圖

```
建立 Job
   ↓
[PENDING]
   ↓  SSE event: start
[RUNNING] ─── Phase I 完成 ──→ [WAITING_CLARIFY]
   │                                  ↓ POST confirm_clarify
   │                            [RUNNING]（Phase II→）
   │
   ├── Phase I-V 連續完成
   │
   ↓  Phase VI 完成（VLM PASS 或 fix_choice 接受）
[RUNNING] ─── Phase VII 開始 ──→ [WAITING_HITL]
                                      ↓ POST hitl / 逾時 accept
                                [RUNNING]（Phase VII 應用修正）
                                      ↓
                              [SUCCESS] / [FAILED]

任意時刻 DELETE /api/v1/jobs/{job_id} → [CANCELLED]
```

### 1.3 前端對應 View 切換

SSE `phase_data` 事件的 `phase` 欄位決定顯示哪個 View：

| phase | 狀態 | 切換至 |
|-------|------|--------|
| 1 完成 | WAITING_CLARIFY | **Clarify View**（等待確認） |
| 2 完成 | RUNNING | **Extract View** |
| 3 完成 | RUNNING | **Plan View** + **Schematic View** |
| 4 完成 | RUNNING | **3D View** |
| 5 完成 | RUNNING | **Code View** + **BOM View** |
| 6 完成（fix_choice） | RUNNING | **Evaluate View**（選項卡片） |
| 7 完成 | SUCCESS | **Evaluate View**（HITL 歷史） |

---

## 二、通訊協議

### 2.1 SSE 串流（主通道）

**端點：** `GET /api/generate`

**查詢參數：**

| 參數 | 必填 | 說明 |
|------|------|------|
| `instruction` | ✅ | 用戶自然語言 prompt |
| `project` | 選填 | 專案名稱（預設自動命名） |
| `max_vlm_rounds` | 選填 | VLM 驗證最大輪數（預設 3） |

**連線：**
```javascript
const es = new EventSource(
  `/api/generate?instruction=${encodeURIComponent(text)}`
);
```

**SSE 事件類型一覽：**

#### `start`
```json
{ "event": "start", "job_id": "uuid-string" }
```
收到後儲存 `job_id`，後續所有 REST 呼叫均需帶入。

#### `progress`
```json
{ "event": "progress", "message": "[Phase I] LoRA-A 推論中..." }
```
用於進度條 / log 顯示，無需解析結構。

#### `heartbeat`
```json
{ "event": "heartbeat" }
```
保活用，忽略即可（不要在 console 輸出）。

#### `phase_data`（關鍵）

Phase 1–5 payload 結構：
```jsonc
{
  "event": "phase_data",
  "__phase_data__": true,
  "phase": 1,            // 1-7

  // Phase 1 特有
  "cot_plan": { "subsystems": [...], "parameter_hints": {...}, "power_summary": {...} },
  "components": [{ "type": "Arduino-Uno-class", "qty": 1, "role": "Brain" }],
  "project_name": "auto_plant_waterer",
  "project_category": "Gardening",

  // Phase 2 特有（覆蓋 components，補全物理規格）
  "components": [{ "type": "...", "dimensions": {...}, "connector_ports": [...] }],

  // Phase 3 特有
  "bom": [{ "role": "...", "type": "...", "qty": 1, "unit_ntd": 150, "source": "url" }],
  "power_budget": { "ok": true, "total_ma": 101, "budget_ma": 500 },
  "constraint_checks": [{ "cat": "power", "rule": "...", "status": "pass" }],

  // Phase 4 特有
  "stl_files": [{ "name": "bottom.stl", "label": "底座" }],
  "engine": "build123d",
  "job_id": "uuid"
}
```

Phase 6 `fix_choice` 特殊 payload（需用戶選擇）：
```jsonc
{
  "event": "phase_data",
  "__phase_data__": true,
  "phase": 6,
  "event_type": "fix_choice",
  "issues": ["wall integrity: score 0.62", "io_cutouts missing"],
  "options": [
    {
      "id": "A",
      "label": "加厚殼壁至 3mm",
      "changes": { "wall_thickness_mm": 3.0 },
      "stem_concept": "Engineering tradeoffs: strength vs weight"
    },
    {
      "id": "B",
      "label": "縮小外殼尺寸",
      "changes": { "max_dimension_mm": 120 },
      "stem_concept": "Design constraints: form factor"
    }
  ],
  "timeout_s": 60,
  "job_id": "uuid"
}
```
用戶選擇後呼叫 `POST /api/v1/jobs/{job_id}/fix-choice`，逾時後自動採用 option A。

#### `done`
```json
{
  "event": "done",
  "status": "success",
  "job_id": "uuid"
}
```
`status` 為 `"success"` / `"failed"` / `"cancelled"`。

---

### 2.2 REST 端點一覽

#### Job 生命週期

| Method | Path | 說明 | 回傳 |
|--------|------|------|------|
| POST | `/api/v1/jobs` | 建立 Job（不含 SSE）| `{job_id, status, bridge_path}` |
| GET | `/api/v1/jobs` | 列出所有 Jobs（可加 `?status=running`）| `[Job]` |
| GET | `/api/v1/jobs/{job_id}` | 取得單一 Job 詳情 | `Job.to_dict()` |
| DELETE | `/api/v1/jobs/{job_id}` | 取消 Job（限 RUNNING/WAITING）| 204 |

#### 互動閘門

| Method | Path | 說明 | Body |
|--------|------|------|------|
| POST | `/api/v1/jobs/{job_id}/confirm_clarify` | Phase I Clarify 確認 | `{"answers": {...}}` |
| POST | `/api/v1/jobs/{job_id}/hitl` | 單一 HITL 修正指令 | 見 §六 |
| POST | `/api/v1/jobs/{job_id}/hitl/batch` | 批次 HITL 指令 | `{"corrections": [...]}` |
| POST | `/api/v1/jobs/{job_id}/fix-choice` | Phase VI VLM 選項回應 | `{"choice_id": "A"}` |
| POST | `/api/v1/jobs/{job_id}/breakpoint` | Phase IV 教學斷點確認 | `{"breakpoint_id": "...", "accepted": true}` |
| POST | `/api/v1/jobs/{job_id}/resume` | HITL 斷線重連後恢復 | `{"message": "..."}` |

#### 資料讀取

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/jobs/{job_id}/bridge` | 取得完整最新 bridge JSON |
| GET | `/api/v1/jobs/{job_id}/trail` | 取得決策歷程（教育分析） |

#### Artifact 下載

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/stl/{job_id}/{filename}` | STL 檔（bottom.stl / lid.stl） |
| GET | `/api/artifact/{kind}?project_id={job_id}` | BOM CSV / 韌體 .ino / STEP |

#### 輔助端點

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/components` | 元件常數包（見 §五） |
| POST | `/api/v1/wiring` | Pin 分配預覽 |
| POST | `/api/v1/schematic` | Schematic SVG 產生 |
| POST | `/api/v1/firmware` | 韌體預覽 |

---

### 2.3 WebSocket（可選補充通道）

**端點：** `WS /ws/{job_id}`

用途：SSE 之外的即時通知（適合多分頁同步、HITL 狀態廣播）。

**伺服器推送事件：**

```jsonc
{ "event": "connected",         "job": { ...Job } }
{ "event": "hitl_sent",         "command": {...} }
{ "event": "hitl_batch_sent",   "count": 3 }
{ "event": "cancelled",         "job_id": "uuid" }
{ "event": "done",              "status": "success", "job_id": "uuid" }
{ "event": "pong" }
{ "event": "heartbeat" }
```

**客戶端發送：** 任意字串（ping 保活）。

> 建議：主流程使用 SSE，WebSocket 僅在需要多分頁同步時開啟。

---

## 三、各 View 設計要點

### 3.1 Clarify View（Phase I 完成後觸發）

**觸發條件：** `phase_data.phase == 1` → Job 狀態轉為 `WAITING_CLARIFY`

**讀取欄位：**
```
bridge.cot_plan.subsystems[]           元件清單（角色/零件/功耗/接腳）
bridge.cot_plan.parameter_hints        尺寸建議（compact/medium/large）
bridge.cot_plan.power_summary          功耗摘要（total_mw vs budget_mw）
bridge.project_name                    自動推導的專案名稱
bridge.project_category                類別（Gardening / Smart_Home / ...）
```

**互動：**
- 顯示 Phase I 推導出的子系統表（`subsystems[]`），讓用戶確認或補充
- 靜態 fallback Q1-Q3（使用場景 / 連線需求 / 電力來源）
- 用戶點擊確認後呼叫：
  ```javascript
  POST /api/v1/jobs/{job_id}/confirm_clarify
  { "answers": { "use_case": "室內", "power": "USB" } }
  ```
- 10 分鐘逾時（後端自動接受，繼續執行）

**空狀態：** subsystems 為空時顯示 fallback 三題問卷。

---

### 3.2 Extract View（Phase II 完成後觸發）

**觸發條件：** `phase_data.phase == 2`

**讀取欄位：**
```
bridge.components[]
  .type           元件 taxonomy（如 "Arduino-Uno-class"）
  .dimensions     { length_mm, width_mm, height_mm }
  .connector_ports[]  接口清單
  .mounting_holes_count  固定孔數
```

**顯示：** LLM 估計值 vs REGISTRY 精確值對比表，差異 > 2x 標紅警告。

**互動：** 唯讀，無按鈕。等待 Phase III SSE。

---

### 3.3 Plan View（Phase III 完成後觸發）

**觸發條件：** `phase_data.phase == 3`

**讀取欄位：**
```
bridge.cot_plan.subsystems[]           子系統表（中文角色/零件/功耗/接腳）
bridge.power_budget                    { ok, total_ma, budget_ma, source }
bridge.constraint_checks[]            電氣規則驗證結果
bridge.wiring.pin_allocation           { "D2": { component, signal, type } }
```

**顯示：**
- 子系統表：`#` / 角色 / 零件 / 功耗(mW) / 接腳 / 狀態
- 功耗進度條（`total_ma / budget_ma`），超出顯示紅色
- GPIO 使用量（`total_pins / available_pins`）
- 電氣規則驗證結果清單（✅ / ⚠️ / ❌）

---

### 3.4 Schematic View（Phase III，與 Plan View 同時顯示）

**觸發條件：** `phase_data.phase == 3`

**讀取欄位：**
```
bridge.wiring.wiring_paths[]    接線列表（from/to/net/color）
bridge.schematic_svg            後端產出的 SVG 字串（含動畫）
```

**顯示：**
```javascript
document.getElementById('schematic-container').innerHTML = bridge.schematic_svg;
```
後端已在 SVG 內嵌 CSS 動畫（信號流動效果），前端無需額外處理。

**互動：** 可點擊 Net 線段顯示 tooltip（從 `wiring_paths[].net` 取得標籤）。

---

### 3.5 3D View（Phase IV 完成後觸發）

**觸發條件：** `phase_data.phase == 4`

**讀取欄位：**
```
phase_data.stl_files[]          [{ name: "bottom.stl", label: "底座" }]
phase_data.engine               "build123d" / "cadquery"
phase_data.job_id               用於組 URL
bridge.cad_output.dimensions_mm [L, W, H]
bridge.cad_output.volume_cm3    體積
```

**STL 載入：**
```javascript
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';

const loader = new STLLoader();
loader.load(
  `/api/stl/${jobId}/${filename}`,
  (geometry) => { /* add to scene */ }
);
```

**建議 Three.js 配置：**
- `OrbitControls` 旋轉 + 縮放
- 環境光 + 平行光（模擬 3D 列印外觀）
- 底座 / 上蓋分色（`MeshLambertMaterial`）
- 顯示尺寸標籤（`L × W × H mm`）與體積

**互動：** 下載按鈕分別對應 bottom.stl / lid.stl。

---

### 3.6 Code View（Phase V 完成後觸發）

**觸發條件：** `phase_data.phase == 5`

**讀取欄位：**
```
bridge.cot_plan.subsystems[0].type     Brain 類型（決定語言）
bridge.firmware_code                   韌體原始碼字串
bridge.wiring.pin_allocation           用於核對 #define
```

**顯示：**
```javascript
// 使用 Prism.js 或 highlight.js 高亮 Arduino/C++ 語法
Prism.highlightElement(codeBlock);
```

**語言對應：**
- `Arduino-Uno-class` / `ESP32-class` → `.ino`（C++）
- `Microbit-class` → `.py`（MicroPython）

**互動：**
- 複製按鈕（`navigator.clipboard.writeText`）
- 下載 `.ino` 按鈕（`GET /api/artifact/ino?project_id={jobId}`）

---

### 3.7 BOM View（Phase III + VII 後顯示）

**觸發條件：** `phase_data.phase == 3`（首次顯示）；Phase VII 完成後更新

**讀取欄位：**
```
bridge.bom[]
  .role          功能角色
  .type          taxonomy 類型
  .label         中文顯示名
  .qty           數量
  .unit_ntd      台幣單價
  .source        採購 URL（LCSC / 露天）
bridge.engineering_decisions[]
  .description   工程決策說明
  .stem_concept  STEM 能力向度
```

**顯示：**
- 物料表（含小計金額）
- 採購連結（`target="_blank"`）
- 工程決策卡片（6E Evaluate 教育呈現）

---

### 3.8 Evaluate View（Phase VI + VII）

#### Phase VI — VLM 驗證結果

**觸發條件：** `phase_data.phase == 6`，`event_type != "fix_choice"`

**讀取欄位：**
```
bridge.vlm_verification
  .passed              boolean
  .rounds              已驗證輪數
  .checks.wall_thickness   { score, pass, feedback }
  .checks.io_feasibility   { score, pass, feedback }
  .checks.mounting         { score, pass, feedback }
  .checks.printability     { score, pass, feedback }
  .checks.education_value  { score, pass, feedback }
```

**顯示：** 雷達圖或評分卡（5 項）+ 各項 feedback 文字。

#### Phase VI — VLM fix_choice 互動

**觸發條件：** `event_type == "fix_choice"`

**UI 流程：**
1. 渲染 `options[]` 選項卡片（含 `stem_concept` 教育說明）
2. 顯示 `timeout_s` 倒數計時（預設 60 秒）
3. 用戶點選後立即送出：
   ```javascript
   POST /api/v1/jobs/{job_id}/fix-choice
   { "choice_id": "A" }
   ```
4. 逾時後自動選 option[0]（前端主動呼叫）

#### Phase VII — HITL 修正歷史

**觸發條件：** Job 狀態 `WAITING_HITL`

**讀取欄位：**
```
bridge.hitl_history[]
  .timestamp    修正時間
  .action       動作類型
  .new_value    新值
  .score_delta  驗證分數變化
```

**互動：** 見 §六 HITL 互動設計。

---

## 四、Bridge JSON 前端消費規範

### 4.1 唯讀原則

前端**不得**直接修改 bridge JSON，所有更新須透過指定 API：

| 修改意圖 | 正確 API |
|---------|---------|
| 確認 Clarify 問答 | `POST confirm_clarify` |
| 修改殼壁厚度 | `POST hitl` + `action: increase_wall_thickness` |
| 替換元件 | `POST hitl` + `action: swap_component` |
| 接受 VLM 選項 | `POST fix-choice` |

### 4.2 關鍵欄位速查

```
bridge.project_name                    專案名
bridge.project_category                類別
bridge.cot_plan.subsystems[]           子系統清單（Phase I 後可用）
bridge.cot_plan.power_summary          功耗摘要
bridge.components[]                    元件規格（Phase II 後補全物理尺寸）
bridge.wiring.pin_allocation           腳位分配（Phase III 後可用）
bridge.wiring.wiring_paths[]           接線列表
bridge.schematic_svg                   SVG 字串
bridge.bom[]                           物料表
bridge.cad_output.bottom_stl           底座 STL 絕對路徑（Phase IV）
bridge.cad_output.lid_stl              上蓋 STL 絕對路徑
bridge.cad_output.dimensions_mm        [L, W, H]
bridge.vlm_verification                VLM 驗證結果（Phase VI）
bridge.hitl_history[]                  HITL 修正歷史（Phase VII）
```

### 4.3 何時使用 GET /bridge

- SSE 斷線重連後，需要同步最新狀態
- 用戶重新整理頁面恢復進度
- 多分頁同步（搭配 WebSocket `done` 事件）

```javascript
const bridge = await fetch(`/api/v1/jobs/${jobId}/bridge`).then(r => r.json());
```

---

## 五、元件常數 API

**端點：** `GET /api/v1/components`

前端啟動後應呼叫一次並快取，用於即時功耗計算與 UI 呈現。

**回傳結構：**
```jsonc
{
  "comp_ma": {
    "Arduino": 50, "ESP32": 240, "RPi": 600, "Microbit": 90,
    "NeoPixel": 300, "LED_Single": 20, "Speaker": 500, "Servo": 250,
    "Pump": 400, "TempHumid": 3, "Ultrasonic": 15, "PIR": 50
  },
  "comp_alt": {
    "Speaker":  { "alt": "Buzzer",   "label": "被動蜂鳴器" },
    "NeoPixel": { "alt": "LED_RGB",  "label": "RGB LED" },
    "DCMotor":  { "alt": "Servo",    "label": "伺服馬達" },
    "Pump":     { "alt": "Relay",    "label": "繼電器" }
  },
  "power_budgets": {
    "USB-5V": 500, "Battery-9V": 600, "LiPo-3.7V": 1500
  },
  "role_color": {
    "Brain": "#4da6ff", "Power": "#ffcc00",
    "Sensor": "#66ff66", "Actuator": "#ff8c66",
    "Output": "#cc88ff"
  }
}
```

### 5.1 即時功耗計算邏輯

用戶在 Clarify View 調整元件選擇時，前端即時更新功耗條：

```javascript
function calcTotalMa(components, compMa) {
  return components.reduce((sum, c) => sum + (compMa[c.key] ?? 0) * c.qty, 0);
}

function updatePowerBar(totalMa, budgetMa) {
  const ratio = totalMa / budgetMa;
  bar.style.width = `${Math.min(ratio * 100, 100)}%`;
  bar.className = ratio > 1 ? 'bar-danger' : ratio > 0.8 ? 'bar-warn' : 'bar-ok';
}
```

### 5.2 超載警告顯示規則

| 條件 | UI 行為 |
|------|---------|
| `total_ma > budget_ma` | 功耗條轉紅，顯示「超出預算，建議升級電源或替換元件」 |
| `total_ma > budget_ma * 0.8` | 功耗條轉黃，顯示「接近上限」 |
| 元件有 `comp_alt` 替代方案 | 在超載時顯示替換建議（如 Speaker → Buzzer） |

---

## 六、HITL 互動設計（Phase VII）

### 6.1 可用 action 與參數範圍

**端點：** `POST /api/v1/jobs/{job_id}/hitl`

```jsonc
{
  "action": "increase_wall_thickness",
  "params": { "wall_thickness_mm": 3.5 },   // 1.2 ~ 5.0
  "step_id": "optional-idempotency-key"
}
```

| action | params | 範圍 |
|--------|--------|------|
| `increase_wall_thickness` | `wall_thickness_mm` | 1.2 – 5.0 mm |
| `decrease_wall_thickness` | `wall_thickness_mm` | 1.2 – 5.0 mm |
| `resize_enclosure` | `max_dimension_mm` | 50 – 300 mm |
| `adjust_padding` | `internal_padding_mm` | 1.0 – 8.0 mm |
| `add_chamfer` | `chamfer_mm` | 0.0 – 3.0 mm |
| `change_material` | `material` | `"PLA"` / `"PETG"` / `"ABS"` |
| `swap_component` | `{ index, new_type }` | index 為 components[] 索引 |
| `accept_as_is` | `{}` | — |
| `request_remake` | `{}` | 重跑整個 Pipeline |

### 6.2 `swap_component` 特殊處理

`swap_component` 會觸發 `_needs_rerun_from_phase = 2`，重跑 Phase II → VI。
前端收到後應：
1. 顯示「元件替換中，Pipeline 從 Phase II 重新執行...」
2. 清空 Phase III-VI 的顯示內容
3. 繼續監聽 SSE（`phase_data.phase` 將從 2 重新遞增）

### 6.3 批次指令

```jsonc
POST /api/v1/jobs/{job_id}/hitl/batch
{
  "corrections": [
    { "action": "increase_wall_thickness", "params": { "wall_thickness_mm": 3.0 } },
    { "action": "add_chamfer",             "params": { "chamfer_mm": 1.5 } }
  ]
}
```

### 6.4 冪等性 `step_id`

前端生成 UUID 作為 `step_id`，防止因網路重送造成重複執行：

```javascript
const stepId = crypto.randomUUID();
await fetch(`/api/v1/jobs/${jobId}/hitl`, {
  method: 'POST',
  body: JSON.stringify({ action, params, step_id: stepId })
});
```

---

## 七、VLM 修正選項（Phase VI fix_choice）

### 7.1 倒數計時 UI

```javascript
let remaining = data.timeout_s;  // 通常 60 秒
const timer = setInterval(() => {
  remaining -= 1;
  timerEl.textContent = `${remaining}s`;
  if (remaining <= 0) {
    clearInterval(timer);
    autoAccept(data.options[0].id);  // 逾時選 A
  }
}, 1000);
```

### 7.2 選項卡片設計要點

每張卡片顯示：
- `options[].label`（主標題）
- `options[].changes`（具體數值變更，格式化顯示）
- `options[].stem_concept`（STEM 教育說明，斜體小字）

用戶點選後：
```javascript
await fetch(`/api/v1/jobs/${jobId}/fix-choice`, {
  method: 'POST',
  body: JSON.stringify({ choice_id: selectedId })
});
clearInterval(timer);
showMessage('修正中，等待重新驗證...');
```

---

## 八、技術選型建議

| 功能 | 建議方案 | 理由 |
|------|---------|------|
| 3D 預覽 | Three.js + STLLoader + OrbitControls | 輕量、無依賴，後端 STL 可直接 serve |
| Schematic | innerHTML 注入後端 SVG | 後端已處理繪圖邏輯，前端零成本 |
| 韌體語法高亮 | Prism.js（language-cpp） | 支援 Arduino 語法，CDN 可用 |
| SSE 接收 | 原生 `EventSource` | 瀏覽器原生，無額外依賴 |
| 狀態管理 | 局部 DOM 更新 + `currentPhase` 變數 | Pipeline 為線性流，無需複雜狀態管理 |
| 功耗計算 | 純 JS 計算，`comp_ma` 常數快取 | 無需後端，即時反應 |

### 8.1 Three.js STL 載入範例

```javascript
import * as THREE from 'three';
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

function loadSTL(jobId, filename, container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(container.clientWidth, container.clientHeight);
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.add(new THREE.AmbientLight(0xffffff, 0.6));
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(1, 2, 3);
  scene.add(dirLight);

  const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
  camera.position.set(100, 100, 200);

  const controls = new OrbitControls(camera, renderer.domElement);

  new STLLoader().load(`/api/stl/${jobId}/${filename}`, (geometry) => {
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(geometry, new THREE.MeshLambertMaterial({ color: 0x88aacc }));
    scene.add(mesh);
    geometry.computeBoundingBox();
    const center = new THREE.Vector3();
    geometry.boundingBox.getCenter(center);
    mesh.position.sub(center);
  });

  (function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  })();
}
```

---

## 九、錯誤與降級處理

### 9.1 Phase 失敗

SSE `done.status == "failed"` 時：
1. 顯示錯誤提示（「Pipeline 執行失敗，請重試或修改描述」）
2. 呼叫 `GET /api/v1/jobs/{job_id}` 取得詳細錯誤訊息

### 9.2 SSE 斷線重連

`EventSource` 預設自動重連，但需處理重連後的狀態同步：

```javascript
es.onerror = async () => {
  const job = await fetch(`/api/v1/jobs/${jobId}`).then(r => r.json());
  if (job.status === 'success' || job.status === 'failed') {
    es.close();
    renderFinalState(job.status);
  }
  // 若仍在執行，EventSource 會自動重連並繼續收事件
};
```

### 9.3 Job 取消

```javascript
async function cancelJob(jobId) {
  await fetch(`/api/v1/jobs/${jobId}`, { method: 'DELETE' });
  es.close();
  showMessage('已取消');
}
```

### 9.4 Clarify Gate 逾時

Phase I 完成後 10 分鐘內若未呼叫 `confirm_clarify`，後端自動繼續執行。
前端可在 Clarify View 顯示倒數計時（可選），邏輯與 fix_choice timer 相同。

---

## 十、決策歷程（Learning Analytics）

**端點：** `GET /api/v1/jobs/{job_id}/trail`

```jsonc
[
  { "timestamp": "...", "event": "job_created",     "data": { "instruction": "..." } },
  { "timestamp": "...", "event": "phase_complete",   "data": { "phase": 1, "duration_s": 15.2 } },
  { "timestamp": "...", "event": "clarify_confirmed","data": { "had_answers": true } },
  { "timestamp": "...", "event": "hitl_command",     "data": { "action": "increase_wall_thickness" } },
  { "timestamp": "...", "event": "pipeline_complete","data": { "total_phases": 7 } }
]
```

在 BOM View 或 Evaluate View 的底部可顯示此歷程，對應 6E 框架的 **Evaluate** 階段教育目標：讓學生看到自己的設計決策軌跡。
