# Canned 重 bake 幾何漂移分析（handoff 紀錄）

> 建立：2026-05-29（SSOT20 canned voltage/thermal 對齊 session 發現）
> 狀態：**未解** — enclosure/assembly 管線無法重現凍結 golden 幾何
> 範圍：與 SSOT20（voltage/weight/thermal）**正交**，屬獨立的 assembly 管線問題
> 關聯追蹤：problem.md `DBR` 條目；延伸 problem.md `DM2`

## TL;DR

`v6/canned/*.json` 的 `cad_output` 幾何（component_placements / enclosure spec / scene_graph_v3）是**凍結 golden**，內含 2026-05-25 為通過 `test_assembly_placement.py` 而做的 **OOB（out-of-bounds）人工/迭代修正**（DM2 記載：6 範本）。

用 `dataset-bake` skill（`bake_canned_bridges.py` + `bake_canned_full.py`）**重 bake 會重跑 solver，產出與 golden 不一致的幾何 → 回退 OOB 修正 → `test_assembly_placement.py` 回歸失敗**。

**結論：重 bake 不可用於「只想刷新 spec 值」的場景。** SSOT20 的 voltage/thermal 對齊改用 surgical patch（只改 leaf 值、不動幾何）。本檔記錄幾何漂移根因供後續修管線。

## 症狀

重 bake 全 16 canned 後，`pytest tests/test_assembly_placement.py` 從 **163 passed / 0 failed（HEAD golden）** 變成 **12 failed**：

| 測試類別 | 失敗範本 |
|---|---|
| `TestEnclosureBounds::test_all_within_bounds` | alarm_siren, auto_curtain, burglar_alarm, lightsaber, obstacle_car |
| `TestHeightClearance::test_height_fits` | auto_curtain |
| `TestPackingEfficiency::test_not_overpacked` | obstacle_car |
| `TestEnclosureSizing::test_enclosure_fits_bbox` | auto_curtain, obstacle_car |
| `TestWireShellBoundary::test_wires_within_shell` | auto_curtain, burglar_alarm, obstacle_car |

測試讀 baked `cad_output.component_placements`（`tests/test_assembly_placement.py:49-54`），**非重解 solver** → 失敗反映 baked 幾何本身漂移。

## 根因（多面向，非單一 bug）

### 1. enclosure 自動尺寸非確定/已漂移

`bake_canned_bridges.py:347-361` 用 `sqrt(area)*1.15` 算 enclosure_spec，再被 `bake_canned_full.py` 的 Phase IV **自動縮殼**覆寫。重 bake 後 `cad_output.spec.inner_length` 與 golden 差異**非單向**：

| 範本 | golden inner_L | 重bake inner_L | 變化 |
|---|---|---|---|
| obstacle_car | 266.3 | 73.58 | 縮 3.6x（FAIL） |
| burglar_alarm | 142.3 | 73.58 | 縮半（FAIL） |
| smart_nightlight | 104.9 | 73.58 | 縮 |
| talking_robot | 168.3 | 142.28 | 縮 |
| auto_curtain | 113.4 | 160.5 | **脹**（FAIL） |
| rc_car | 156.0 | 181.6 | 脹 |
| plant_monitor | 129.4 | 137.7 | 脹 |
| alarm_siren | 73.58 | 73.58 | **不變卻 FAIL** |

### 2. placements 與 enclosure spec 內部不一致

obstacle_car：`component_placements` 把 Motor-DC 擺在 x=74.6（assembly_solve 用 bridges 的 ~132mm 殼算的），但 Phase IV 把 `cad_output.spec.inner_length` 覆寫成 73.58 **卻沒重新擺位** → 元件/線突出殼外 23–31mm（wire shell breach）。

### 3. 元件尺寸也漂移（alarm_siren 同殼仍 FAIL）

alarm_siren enclosure 尺寸不變卻失敗 → placement/元件尺寸本身變了。對應 `8872dd0 fix(components+assembly)` 同時改了 `v6/data/component-dimensions.js`（Button/Switch/Remote）與 `lib/assembly_solver/enclosure_fit.py`（PackFn rotated bool）。

### 4. golden 含人工 OOB 修正（smoking gun）

problem.md DM2：「2026-05-25 ... OOB 修正 6 template（alarm_siren/auto_waterer/lightsaber/plant_monitor/rc_car/smart_nightlight）」讓測試通過。**這些修正存在 baked JSON，不在 solver 邏輯內** → 任何重 bake 都會抹掉。

## 為何與 SSOT20 無關

enclosure sizing 只吃元件 length×width（area）；placement priority 吃 weight_g（order，不影響殼尺寸）。voltage_v / thermal_mw **完全不參與幾何**。重 bake 不論有無 SSOT20 改動都會觸發此漂移。

## 嫌疑程式（後續 session 起點）

- `lib/assembly_solver/enclosure_fit.py` — enclosure 擬合（`8872dd0` 改過 PackFn rotated）
- `lib/assembly_solver/packing.py` — MaxRects（bake 時噴大量 `MaxRects overflow for Arduino-Uno-class`）
- `lib/assembly_solver/assembly_solver_v3.py` — `solve_v3`（scene_graph_v3）
- `bake_canned_full.py` 的 Phase IV 自動縮殼路徑（覆寫 `cad_output.spec` 卻不同步 placements）
- golden bake 後改過 assembly 的 commits：`f2a61f9`(AV3-4 clearance)、`9505cef`、`8872dd0`

## 重現

```powershell
# 注意：bake_canned_bridges.py 有 sys.path bug（import tools 撞 lib/tools.py），須用 -m
.venv\Scripts\python.exe -m tools.bake_canned_bridges
.venv\Scripts\python.exe -m tools.bake_canned_full
.venv\Scripts\python.exe -m pytest tests\test_assembly_placement.py -q   # → 12 failed
```

## 修復方向（擇一，待後續 session 評估）

1. **Phase IV 縮殼後重擺位**：自動縮殼 (`cad_output.spec`) 後重跑 placement，確保 placements 在新殼內。治本但牽動 Phase IV。
2. **enclosure_fit / packing 回歸修正**：找 `8872dd0`/`f2a61f9` 造成的縮殼/旋轉變化，恢復可重現 golden 的 sizing。
3. **解耦幾何與 spec**：讓 bake 只刷新 spec（voltage/thermal/power/bom），**不重生幾何**；幾何視為真正凍結 artifact（需 OOB 修正時才手動重解+人工校正）。← 與本 session 的 surgical 思路一致，最省、最安全。

## 不要做

- **不要為了刷新 spec 值而重 bake 整份 canned** — 會回退 OOB 修正、回歸 assembly gate。
- spec（voltage/thermal/weight）漂移請用 surgical patch：只改 baked JSON 的 leaf 值，不碰 `component_placements`/`scene_graph_v3` 座標。對賬用 `scripts/_verify_canned_specs.py`。

## 連帶：surgical 的 thermal 限制（SSOT24 A1）

2026-05-29 SSOT20 對齊用 surgical patch 修了 `scene_graph_v3.modules`/`panel_placements` 的 `thermal_mw`，但 **`thermal_field.heat_sources` + `thermal_overlay` + `total_power_mw`/`thermal_tier`/`needs_venting` 仍 golden-incomplete**：golden bake 時 thermal=0 的元件（Buzzer/LED-RGB/Sensor-Light/LED-PWM）未列入 heat_sources，surgical（只改既有 leaf 值）補不了「清單成員」與「聚合值」。例：alarm_siren `total_power_mw` 仍 250（漏 Buzzer 150 + LED-RGB 100）。

**完整修 thermal_field 有兩條路**：(a) 擴充 surgical — 依 registry 補齊 heat_sources 成員並重算 aggregates/thermal_overlay 溫度（不碰幾何）；(b) 修好本 DBR 讓 re-bake 可重現 golden，則重 bake 一次性同時解幾何 + thermal_field。追蹤於 problem.md SSOT24 (A1)。
