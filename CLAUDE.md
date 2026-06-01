# StemCAD Studio — Project Rules

## Rules

- 回覆一律使用**繁體中文**；程式碼變數 / 註解維持英文。
- Do what has been asked; nothing more, nothing less.
- 優先編輯既有檔案，非必要不新建檔；不主動新增文件檔（除非明確要求）。
- 工作檔 / 測試不放 root — 用 `/src`、`/tests`、`/docs`、`/scripts`。
- 編輯前先讀該檔。
- 不 commit secrets / 憑證 / `.env`。
- 檔案保持 < 500 行。
- 在系統邊界驗證輸入；不確定就先問再實作。
- 不做投機功能、不為單次使用做抽象、不加未被要求的「彈性」。
- 只動該動的，不順手「改善」相鄰程式碼，沿用既有風格。

## Build & Test

- 改完程式一律跑測試（`pytest`）。
- commit 前確認 build / server 可起。
- Python 一律用 `.venv`（避免系統 Python 的相容性問題）。

## 元件資料 SSOT

元件的尺寸 / 電氣 / pin layout / 座標**唯一真值**是 `data/component_datasheet_verified.json`
（EAGLE + KiCad + PDF 三來源交叉驗證）。前端視覺資料與後端 spec 皆**衍生自**此檔，**禁止手填**。

- 新增 / 修改任何 PCB 或元件視覺佈局前，先檢索 verified.json 取權威座標，不可憑記憶或目測。
- 座標慣例：verified.json 以 PCB 左下角為原點；前端 `cx/cy` 為中心，需換算。
- 改動後跑 drift gate 確認資料零漂移（見 `scripts/` 內 `test_dimensions_drift.py` /
  `derive_component_dimensions.py --check`）。

## CAD 引擎

統一使用 **build123d**（純 Python，可在 Colab 執行）；不使用 cadquery。

## Commit

採 conventional commit：`<type>(<scope>): <subject>`（subject < 72 字）。
commit body 簡述 before/after 與影響；git log 即 changelog。

## Scope

能產出符合專案且能 3D 列印 / 上傳的 CAD 全流程；不處理切片、進階 FEM 模擬、戶外密封、多軸機構。
