# StemCAD Studio

**文字 → 可製造的 STEM 硬體專題。** 學生用一句話描述想做的專題（例如「我想做一台自動澆花器」），系統端到端產出：元件清單 (BOM)、電路圖、可 3D 列印的外殼 STL、可上傳 Arduino 的韌體程式碼 — 全部基於**真實元件 datasheet**，並包進 **6E 教學流程**（Engage → Explore → Explain → Engineer → Evaluate → Extend）。

> 內部代號：CADHLLM（CAD Hierarchical LLM）。

---

## 它做什麼（7 階段 pipeline → 6E）

| 階段 | 產物 |
|------|------|
| Phase I 意圖理解 | 專題分類 + BOM 草案 |
| Phase II 釐清提問 | 人機問答補足規格 (HITL) |
| Phase III 元件解析 | 真實型號確認（Arduino / ESP32 / micro:bit / 感測器）+ 約束驗證 |
| Phase IV 規劃設計 | 子系統分配 + 功率預算 |
| Phase V 電路圖 | ELK 佈局 schematic + 接線分配 |
| Phase VI 3D 模型 | 外殼 + PCB + 元件配置 → 可列印 STL |
| Phase VII 程式碼 | Arduino 韌體合成 + 組裝 SOP |

各階段共用一份逐步累積的 **Bridge JSON**。內建 16 個 demo 範本（自動澆花器 / 紅外避障車 / 電子琴 / 門禁 …）。

---

## 快速開始

```bash
# Python 一律用 venv（不要用系統 Python）
python -m venv .venv
.venv/Scripts/pip install -r services/requirements.txt   # Windows
# 或 .venv/bin/pip install -r services/requirements.txt   # macOS/Linux

# 啟動 gateway
.venv/Scripts/python run_server.py --port 8000
```

開啟 `http://localhost:8000/` 進入前端（`v6/`）。

---

## 技術棧

| 層 | 技術 |
|----|------|
| 後端 | FastAPI（async、SSE 串流） |
| 前端 | React 18（JSX, no-build）+ Three.js 3D 檢視 |
| CAD 引擎 | build123d（純 Python，可在 Colab 跑） |
| LLM | Llama 3.1 8B + LoRA（cadhllm，驅動 Phase I–III）|
| 檢索 | RAG 向量庫（元件案例） |

---

## 專案結構

| 目錄 | 內容 |
|------|------|
| `lib/` | 核心庫（cad / pcb / assembly_solver / wiring / firmware / rag / registry / 元件 SSOT）|
| `services/` | FastAPI gateway + 7 個 phase handlers |
| `v6/` | React 前端（6E 分頁 / schematic / 3D viewer）+ 16 canned 範本 |
| `training/` | LoRA-A / LoRA-B 訓練（cadhllm）|
| `data/` | 元件 SSOT（`component_datasheet_verified.json`）|
| `scripts/` | regression、SSOT 驗證、`scripts/builders/`（canned bake / RAG index / prompt 對齊）|
| `tests/` | 產品回歸測試 |
| `docs/` | 設計 SPEC / 技術匯報 / roadmap |

---

## 元件 datasheet 與 RAG 索引（需自行取得 / 重建）

為尊重第三方版權，本 repo **不附帶**原廠 datasheet / reference design 二進位（Arduino / ESP32 / micro:bit / Raspberry Pi 的 PDF / EAGLE / KiCad 檔）。元件權威座標/尺寸已萃取進 `data/component_datasheet_verified.json`（SSOT）；若要重跑 PCB 抽取 pipeline，請自官方來源取得原始檔：

| 元件 | 官方來源 |
|------|---------|
| Arduino UNO R3 | https://docs.arduino.cc/hardware/uno-rev3/ （datasheet A000066 + reference design）|
| ESP32 DevKit v1 | https://www.espressif.com/en/products/socs/esp32 （ESP32 / ESP-WROOM-32 datasheet）|
| BBC micro:bit V2 | https://tech.microbit.org/hardware/ （schematic / mechanical）|
| Raspberry Pi 4B | https://www.raspberrypi.com/products/raspberry-pi-4-model-b/ （mechanical / product brief）|

放回 `data/pcb_sources/<元件>/` 後即可跑抽取腳本。

**RAG 向量庫** `data/rag_db/` 未隨 repo 散布；重建：

```bash
.venv/Scripts/python scripts/builders/build_rag_index.py
```

---

## Scope

**做**：把 STEM 專題想法產出符合需求且**能列印 / 能上傳**的 CAD 全流程。

**不做**（scope 外）：切片器整合、進階 FEM 模擬、戶外 IP 密封、多軸機構。

---

## 設定

服務端設定見 `services/server.env.example`（複製為 `services/server.env` 並填值）。
production 必設 `CADHLLM_JWT_SECRET`（dev fallback 為不安全預設，僅供本機開發）。
