# StemCAD Studio — 開發路線圖

> 本檔為 **canonical 路線來源**。階段命名與內容以 `services/phase_handlers/` 實際 handler 為準；
> 設計沿革細節見 [PROJECT_PLAN.md](PROJECT_PLAN.md)（v3.0 設計期文件）。

---

## 一、產品定位

把一句自然語言的 STEM 專題需求，端到端轉成**可製造**的成品：BOM、電路圖、可 3D 列印外殼 STL、可上傳的 Arduino 韌體，全部基於真實元件 datasheet，並包進 6E 教學流程。

區別於純幾何生成研究：多元件**組裝體**、電氣驗證 + schematic、元件殼跨專案複用、6E 教育整合、Human-in-the-Loop 閉環。

---

## 二、Pipeline 現況（權威階段對照）

| 階段 | Handler | 內容 | 狀態 |
|------|---------|------|------|
| Phase I 意圖理解 | `phase1_handler` | LoRA-A 推論：專題分類 + 子系統規劃 + BOM 草案 | ✅ |
| Phase II 規格補全 | `phase2_handler` | Component Registry（SSOT）補全 spec / 尺寸 / port / 鎖孔 | ✅ |
| Phase III 電氣工程 | `phase3_handler` | 功率預算 + IO 衝突驗證 + 接線分配 + ELK schematic + BOM.md | ✅ |
| Phase IV 機構工程 | `phase4_handler` | assembly_solver 佈局 + 外殼幾何 + 多元件組裝 → STL | ✅ |
| Phase V 輸出渲染 | `phase5_handler` | 多視圖 PNG + Three.js 3D 檢視 + Arduino 韌體合成 | ✅ |
| Phase VI 驗證閉環 | （併入 V / QA） | VLM / contract 驗證，無獨立 handler，整合於輸出與 QA gate | 🔶 部分 |
| Phase VII 人工修正 | `phase7_handler` | HITL 人機互動修正（lock-file 非同步閉環） | ✅ |

> 注意：歷史文件曾出現「7 個獨立 phase（含獨立 Phase VI）」與「意圖／釐清／元件／規劃／電路圖／3D／程式碼」兩種早期命名，皆與目前 handler 不符，已於本檔統一。

---

## 三、里程碑

### Milestone v3 — 標準化資料零誤差 + CI 可證明（當前焦點）

驗收門檻：所有標準化資料（元件 SSOT、衍生視覺資料）**零漂移**，且由 CI 自動證明。

- [x] 元件 SSOT 單一真相鏈：`data/component_datasheet_verified.json` → specs cache → registry → 前端
- [x] 兩個 drift gate 全綠：`scripts/derive_component_dimensions.py --check`（43 元件 position-strict）、`scripts/test_dimensions_drift.py`（核心三元件 tol=0.1mm）
- [x] 產品回歸測試套件（5,300+ 通過；幾何 / PCB / wiring / firmware / phase handler）
- [x] CI 工作流（drift gate + 產品 pytest）：見 `.github/workflows/ci.yml`
- [ ] 公開化前最終檢查（見下節）

### Milestone — 公開化（private → public）

- [ ] 產品 CI 在 GitHub Actions 上跑綠（fresh clone 可獨立 build）
- [ ] commit author 身分檢視
- [ ] README / 授權 / 第三方 datasheet 散布說明定稿

### 規劃中（未排程）

- [ ] build123d 列為 CI 選用層（目前 CAD 引擎相關測試在精簡 CI 中 skip）
- [ ] 擴充 demo 範本與元件覆蓋
- [ ] Phase VI 驗證閉環獨立化（目前併入輸出 / QA）
- [ ] 切片器 / 進階模擬 — **scope 外**，暫不納入

---

## 四、Scope

**做**：把 STEM 專題想法產出符合需求且能列印 / 能上傳的 CAD 全流程。

**不做**（scope 外）：切片器整合、進階 FEM 模擬、戶外 IP 密封、多軸機構。

---

## 五、問題追蹤

公開議題（bug / 功能請求 / 文件）走 **GitHub Issues**，以 `P0`–`P3` label 標優先級，關閉即歸檔，跨引用 commit / PR。Issue 模板見 `.github/ISSUE_TEMPLATE/`。
