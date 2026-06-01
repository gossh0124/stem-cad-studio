# SSOT 區分：pin_layout vs _ui_hints.extra_ports

## A. 架構性區分

`data/component_datasheet_verified.json` 對每個元件保留兩個位置資料源：

| 欄位 | 用途 | 下游消費者 |
|---|---|---|
| `pin_layout.header_groups[].pins[].x_mm/y_mm` | **電氣 SSOT** — PCB 上 pad / through-hole 位置 | `lib/wiring/*`、drill exporter、phase 4 熱分析、`lib/pcb/*` SubComponent thermal 來源 |
| `_ui_hints.extra_ports[].cx/cy` | **視覺 SSOT** — 3D 渲染中可見 header housing 的位置 | `scripts/derive_component_dimensions.py` → `v6/data/component-dimensions.js` → `v6/engineer/scene-3d.js` |

**兩者位置可以不同為設計**：許多模組的 header pin 在 PCB 邊緣 pad，但 housing 凸出 PCB 邊外。`pin_layout` 紀錄電氣 pad、`extra_ports` 紀錄使用者看到的 housing 位置。

對「位置相同」的 class（純直插排針沿 PCB 邊），可在 `_ui_hints.derive_from_pin_layout: true` 啟用 opt-in 自動衍生（範例：[Remote-class](#)、Battery-AA-class、Pump-Water-class、Sensor-SoilMoisture-class）。

---

## B. Phase 6 審計記錄 — 24 個 DRIFT class

每個 class 都以官方 datasheet 為單一真值驗證：當前數值能不能從 datasheet 推得？兩者位置差異是否符合 datasheet 描述的物理特徵（pad vs housing）？

> 表格格式：class — header label — datasheet URL — pin_layout 真值（current → verified）— extra_ports 真值（current → verified）— 結論

### Batch 1：MCU 主板 + 顯示

| Class | Label | pin_layout 現值 | extra_ports 現值 | datasheet 來源 | 結論 |
|---|---|---|---|---|---|
| Arduino-Uno-class | POWER | (0, 34.29) | (1.25, 19.15) | _待 Wave 1 agent 填_ | _待填_ |
| Arduino-Uno-class | ANALOG | (0, 13.97) | (1.25, 39.4) | | |
| ESP32-class | — | — | — | | |
| Microbit-class | — | — | — | | |
| RaspberryPi-class | — | — | — | | |
| Display-OLED-class | I2C_HEADER | (8.89, 0) | (8.85, 26.95) | | |
| Display-LCD-class | I2C_HEADER | (6.35, 36.0) | (6.35, 0.75) | | |

### Batch 2：感測器

| Class | Label | pin_layout | extra_ports | datasheet | 結論 |
|---|---|---|---|---|---|
| Sensor-TempHumid-class | MAIN | (7.62, 0) | (7.55, 15.05) | | |
| Sensor-Ultrasonic-class | MAIN | (10.16, 20.0) | (10.15, 0.75) | | |
| Sensor-PIR-class | MAIN | (16.0, 0) | (16.0, 23.95) | | |
| Sensor-Light-class | HEADER | (12.54, 0) | (15.8, 11.75) | | |
| Sensor-IR-class | HEADER | (4.54, 0) | (4.5, 11.75) | | |
| Sensor-MSGEQ7-class | DIP-8 | (3.81, 3.81) | (4.55, 4.55) | | |

### Batch 3：顯示 + 致動器

| Class | Label | pin_layout | extra_ports | datasheet | 結論 |
|---|---|---|---|---|---|
| Display-EInk-class | SPI_HEADER | (10.89, 0) | (10.85, 37.95) | | |
| LED-Matrix-class | INPUT_HEADER | (7.08, 0) | (7.05, 31.95) | | |
| Speaker-class | WIRES | (18.0, 0) | (17.95, 35.95) | | |
| Motor-DC-class | TERMINALS | (11.0, 9.0) | (10.95, 12.95) | | |
| L298N-Driver-class | POWER | (7.08, 0) | (7.05, 42.95) | | |
| USB-5V-class | OUTPUT | (57.0, 16.27) | (56.95, 13.75) | | |

### Batch 4：照明 + 控制

| Class | Label | pin_layout | extra_ports | datasheet | 結論 |
|---|---|---|---|---|---|
| Lighting-LED-RGB-class | LEADS | (2.4, 0) | (2.65, 4.95) | | |
| Lighting-LED-PWM-class | LEADS | (2.25, 0) | (2.2, 4.95) | | |
| Lighting-LED-Strip-class | INPUT | (2.0, 3.5) | (1.95, 6.45) | | |
| Lighting-NeoPixel-class | INPUT | (0, 5.0) | (0.75, 4.95) | | |
| Mist-Atomizer-class | INPUT | (2.77, 0) | (2.75, 24.95) | | |
| Mist-Ultrasonic-class | INPUT | (3.27, 0) | (3.25, 34.95) | | |
| Potentiometer-class | TERMINALS | (8.0, 0) | (8.0, 16.0) | | |
| Joystick-class | HEADER | (7.08, 0) | (7.05, 25.95) | | |
| Buzzer-Passive-class | PINS | (6.0, 0) | (6.0, 12.0) | | |

---

## C. 真 MATCH class（路線 A 順手清）

下列 3 個 class 的 pin_layout 中心與 extra_ports 中心差 ≤ 0.5mm —— 真正的重複資料，遷移到 opt-in `derive_from_pin_layout: true`：

| Class | Label | pin/extra 中心差 | 動作 |
|---|---|---|---|
| Battery-AA-class | WIRES | (0.0, 0.0) | 加 `derive_from_pin_layout: true`，刪 extra_ports.WIRES |
| Pump-Water-class | WIRES | (0.0, 0.0) | 同上 |
| Sensor-SoilMoisture-class | MAIN-Header | (0.05, 0.0) | **延** — schema 複雜（on_board 與 extra_ports label 不同），需要更多時間判斷 |

完成標記：
- [x] Battery-AA-class — `derive_from_pin_layout: true` 已加，extra_ports.WIRES 已刪；drift gate 全綠
- [x] Pump-Water-class — 同上
- [ ] Sensor-SoilMoisture-class — 延後處理

---

## D. Phase 6 Wave 1 執行報告

**Wave 1（並行 datasheet 查證）狀態**：4 agents 並行跑，3/4 因無法 WebFetch 到實際 datasheet 機械圖、退化為「text-based fallback」reasoning。所有 fallback 提案的核心假設是「extra_ports.cy 應 = pin_layout.y」，**這直接違背架構性區分原則（pin 是 pad、housing 可在不同位置）**。

**結論**：Wave 1 agents 的「position fix」提案 **不採用**，避免破壞既有視覺。

需要 datasheet 機械圖 / 真實照片才能判定的 case（占 24 DRIFT 全部），改列入「**靠人工分批查證**」TODO，不在本輪自動化範圍。

**Phase 6 真正交付**：
1. ✅ Wave 0 — 架構性文件（本檔）+ CLAUDE.md 註記
2. ✅ 路線 A 部分：Battery-AA / Pump-Water MATCH 兩個遷移到 opt-in
3. ❌ Wave 1 自動 datasheet 查證：因 agents 無 web access，退化為推測 — 不採用
4. 後續工作（人工或更好工具支援後）：24 個 DRIFT class 逐一查實機 datasheet 機械圖

---

## E. Wave 1 agent 推測提案（**未採用**，供未來查證起點）

> ⚠️ 以下推測**未經官方 datasheet 機械圖驗證**，僅基於 agent 對 verified.json 文字描述的推理。**不應直接套用**。記錄於此給未來逐一查證時節省從零開始的時間。

**共同推理模式**：多數 agent 認為 `extra_ports.cy` 應對齊 `pin_layout` 的 pin 中心 y，理由是「extra_ports 是 housing 視覺，多數情況應在 pin pad 上方」。這假設與本檔 A 段「兩者可合理不同」的設計原則衝突 —— 需逐個 class 查 datasheet 仲裁。

**Agent proposed `extra_ports.cy → pin_layout y` 修法**（依信心度排序）：

| Class | Label | 現 extra_ports | agent 提案 | 推測依據 |
|---|---|---|---|---|
| Arduino-Uno-class | POWER | (1.25, 19.15) | cy → 34.29 | POWER 與 ANALOG cy 似乎被互換 |
| Arduino-Uno-class | ANALOG | (1.25, 39.4) | cy → 13.97 | 同上 |
| Display-LCD-class | I2C_HEADER | (6.35, 0.75) | cy → 36.0 | 180° 反向 |
| Display-OLED-class | I2C_HEADER | (8.85, 26.95) | cy → 0.0 | extra_ports 看似用整體高度 |
| Sensor-TempHumid-class | MAIN | (7.55, 15.05) | cy → 0.5 | DHT22 pin 在底邊 |
| Sensor-Ultrasonic-class | MAIN | (10.15, 0.75) | cy → 20.0 | HC-SR04 header 在 rear edge |
| Sensor-PIR-class | MAIN | (16.0, 23.95) | cy → 0.5 | HC-SR501 pin 在底邊 |
| Sensor-IR-class | HEADER | (4.5, 11.75) | cy → 0.5 | FC-51 pin 在底邊 |
| Sensor-MSGEQ7-class | DIP-8 | (4.55, 4.55) | (cx, cy) → (3.81, 3.81) | JEDEC DIP 中心 |
| Lighting-LED-RGB-class | LEADS | (2.65, 4.95) | cy → 0 | 直插 LED pins 在底邊 |
| Lighting-LED-PWM-class | LEADS | (2.2, 4.95) | cy → 0 | 同上 |
| Mist-Atomizer-class | INPUT | (2.65, 24.95) | cy → 0 | extra cy=24.95 超出 PCB（25mm）|
| Mist-Ultrasonic-class | INPUT | (3.27, 34.95) | cy → 0 | extra cy=34.95 超出 PCB（35mm）|

**Agent 認為「不需修」**：Sensor-Light（cy=11.75 可能是 UI offset）、Potentiometer / Joystick / Buzzer-Passive（panel-mount，housing offset 合理）

**Batch 3 agent 失敗**：6 個 class（Display-EInk / LED-Matrix / Speaker / Motor-DC / L298N-Driver / USB-5V）— agent 沒讀到 _ui_hints.extra_ports（schema 解析錯誤），輸出無效。

**Batch 4 認為「不需修」**：Potentiometer / Joystick / Buzzer-Passive — housing offset 合理對應實機

---

## F. 後續工作清單

對 24 個 DRIFT class，按以下步驟逐一處理（建議每個 ~3-5 分鐘）：

1. 開 verified.json `sources.url[0]` 對應的 datasheet PDF
2. 找 mechanical drawing 標出實際 header housing 位置
3. 對比 verified.json 當前 `pin_layout.pins.x_mm/y_mm` 與 `_ui_hints.extra_ports.cx/cy`
4. 若兩者都正確（pin pad ≠ housing 視覺位置，符合機械圖）→ 加 `notes` 註記為什麼不同
5. 若 extra_ports 錯 → 改 cx/cy；跑 `scripts/derive_component_dimensions.py --check`
6. 若 pin_layout 錯 → 改 pins 座標；額外跑 `pytest tests/test_eagle_parse.py tests/test_layout_export.py`
7. 更新本檔 B 段表格

---

## G. 第三層 SSOT 分歧：on_board_components vs extra_ports

進行 P1「33 個 frontend_shape 空的 class 接通 SSOT」工作時發現**第三層架構性分歧**：

`scripts/connect_frontend_shape.py` 自動掃描 22 個有 on_board + extra_ports 的 class，找到 **56 個 label 匹配但位置不對齊**的條目（差 5-50mm 不等）、**0 個自動可遷**。

代表性 case：
- ESP32-class `BTN-EN`: extra_ports (46.75, 22.75) vs on_board (6.00, 24.00) — dx=40.75mm
- RaspberryPi-class `BCM2711`: extra_ports (39.5, 26.5) vs on_board (25.70, 32.50) — diff ~14mm

**架構性結論**：與 pin_layout vs extra_ports 同理 ——
- `on_board_components` 是**物理 BOM SSOT**（從 PCB layout 抽出的部件實際座標）
- `_ui_hints.extra_ports` 是**前端視覺 SSOT**（3D 場景視覺擺位）
- `_ui_hints.frontend_shape` 是**兩者橋接器**（label-based 映射 on_board → 視覺 shape/color）

對「on_board 位置 == 視覺位置」的 class（如 Battery-AA / Pump-Water / Relay-Module / Sensor-SoilMoisture / ESP32 部分），用 frontend_shape 接通即可。
對「on_board 位置 ≠ 視覺位置」的 class，extra_ports 必須保留**或** datasheet 仲裁哪個對。

**P1.1 結論**：所有 22 個候選 class 都屬「位置不對齊」case，**無法自動化**接通，需要 datasheet 機械圖逐一驗證。歸類為「Phase 6 後續工作」一併處理。

**腳本資產**：`scripts/connect_frontend_shape.py`（read-only dry-run 工具）已留下，未來人工查證每個 class 後可手動遷移特定條目。
