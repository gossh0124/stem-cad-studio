# Snap-Fit 卡扣與外殼適配性審計報告

**日期**：2026-05-08
**對象**：`lib/cad/shell.py:build_pcb_two_piece()` 預設參數產出的 Arduino Uno R3 外殼
**方法**：純幾何重建 + 工程力學計算 + 列印工藝考量

> 結論：**目前的 snap-fit 設計可裝合但問題顯著**。7 項缺陷中 3 項嚴重（應力超標、lip 寬度 bug、無防誤插）需立即修正，4 項中度需後續優化。

---

## 適配性評分

| 項目 | 現況 | 評級 |
|------|------|------|
| 1. Lip ↔ Recess 幾何重疊 | Y=1.05mm / Z=1.0mm 重疊 | ✅ 可扣合 |
| 2. Lip 寬度 | 2.3mm（應為 0.8mm）—探出外壁 1.25mm | ❌ Bug |
| 3. 懸臂應力 | 5.0% 應變，超過 PETG yield (4%) 25% | ❌ 一插即 yield |
| 4. 插入總力 | 100 N（4 arms 同步） | ⚠️ 需工具 |
| 5. PCB Header vs Lid | 頂端 z=9.05，Lid 底 z=11.05，差 2.0mm | ⚠️ 杜邦線難插 |
| 6. Standoff 螺絲匹配 | ⌀2.5 底孔 → M3 self-tap OK，M2.5 不行 | ⚠️ 需文件註明 |
| 7. 防誤插（Anti-rotation） | 完全 X/Y 對稱，可裝反 180° | ❌ 缺特徵 |

---

## 詳細分析

### 1. Lip 寬度 Bug（最高優先修正）

**現況**：
```python
# lib/cad/shell.py:_build_two_piece_lid
bd.Box(snap_arm_w, snap_arm_t + snap_lip_d, snap_lip_h, mode=bd.Mode.ADD)
#                  ^^^^^^^^^^^^^^^^^^^^^^^^ 這裡是 2.3mm
```

**正確值**：lip Y 寬度應該等於 `snap_lip_d`（0.8mm）而非 `snap_arm_t + snap_lip_d`（2.3mm）。

**幾何後果**：
| 區段 | Y 範圍 | 結果 |
|------|--------|------|
| Arm 範圍 | [31.97, 33.47] | 1.5mm 厚 |
| Lip 實際範圍 | [30.42, 32.72] | 2.3mm 寬（多 1.5mm） |
| 外壁面 | y = 31.47 | — |
| Lip 探出外壁 | 32.72 - 31.47 = **1.25mm** | ⚠️ 浪費材料 + 外觀凸起 |
| Lip 進入 recess | 31.47 - 30.42 = 1.05mm | 比設計值 0.8 多 0.25mm |

**修正建議**：
```python
# 修正後的 lip 設計
lip_y_corrected = y_sign * (outer_w/2 + snap_gap - snap_lip_d/2)
# Y 寬度只取 snap_lip_d (0.8mm)
bd.Box(snap_arm_w, snap_lip_d, snap_lip_h, mode=bd.Mode.ADD)
```

修正後 lip 完全位於 arm 內側（[31.17, 31.97]），與 arm 共面相連，不會探出外壁。

### 2. 懸臂應力超標（最高優先修正）

**力學計算**（懸臂梁公式）：
```
慣性矩 I = w × t³ / 12 = 4 × 1.5³ / 12 = 1.125 mm⁴
最大應變 ε = 3 × t × y / (2 × L²)
            = 3 × 1.5 × 0.8 / (2 × 6²)
            = 0.05 = 5.0%
最大應力 σ = ε × E = 5% × 2000 MPa = 100 MPa
```

**材料利用率**：

| 材料 | Yield 應變 | 利用率 | 結論 |
|------|-----------|--------|------|
| PLA | 2-3% | **250%** | ❌ 一插就斷 |
| PETG | 4-5% | **125%** | ❌ 一插即永久變形 |
| ABS | 6-7% | 83% | ⚠️ 接近極限，反覆拆裝會疲勞 |
| TPU | 50%+ | <10% | 沒問題但太彈，扣不住 |

**修正建議**（任一即可，組合更好）：
1. **加長懸臂** `snap_arm_h = 6 → 10mm`：應變降至 1.8%（PETG 利用率 45% ✅）
2. **減小撓曲** `snap_lip_d = 0.8 → 0.4mm`：應變降至 2.5%（PETG 利用率 63% ✅）
3. **加厚懸臂** ❌ 反而增加應變（t³ 在分母，t 在分子主導）— 不要做

最推薦：`snap_arm_h = 8mm` + `snap_lip_d = 0.5mm` → 應變 1.4%，PETG 利用率 35%，PLA 利用率 70%（也能用）。

### 3. 插入總力過大

**單 arm 插入力**：
```
F = 3 × E × I × y / L³ = 3 × 2000 × 1.125 × 0.8 / 6³ = 25 N
```

**4 個 arm 同步**：100 N（≈ 10 公斤力），雙手垂直按壓邊緣才能勉強扣上。

實際組裝時 4 個 arm 不會完全同步壓入（先有 1\~2 個先扣），但仍會卡得很緊。

**修正後（套用#2 修正）**：
- arm_h=8, lip_d=0.5 → F = 3 × 2000 × (4×1.5³/12) × 0.5 / 8³ = 6.6 N/arm
- 總力 26.4 N（≈2.7 公斤力），單手即可

### 4. PCB Pin Header 與 Lid Cutout 高度不匹配

**現況**：
```
PCB 表面 Z:  -2.45  (assembly)
Pin header 頂端 Z:  -2.45 + 11.5 = 9.05
Lid 底面 Z:  +11.05
Header 頂端到 Lid 底面: 2.00mm
```

Pin header 頂部低於 lid 底部 2mm，意思是：
- ❌ pin header 不會穿出 lid cutouts
- 從外面看 lid，可以從 cutouts 看見 header
- 但杜邦線必須穿過 cutout（4.54mm 寬槽）→ 探入殼內 2mm → 才能對到 pin

**杜邦母頭高度 ≈ 14mm**，若想插上後留住，cutout 邊緣必須能托住母頭外殼。當前設計：
- Cutout 寬度 4.54mm（夠杜邦母頭穿過）✅
- Cutout 邊緣與 header 頂端有 2mm 空隙 ⚠️

**修正建議**：
- 方案 A：減 `padding` 讓 inner_h 變小，讓 header 剛好穿出 lid
  - 設 inner_h = standoff_height + pcb_t + 11.5 - lid_h = 5 + 1.6 + 11.5 - 2 = 16.1
  - 對應 padding = 16.1 - (5 + 1.6 + max_component_h) ≈ -1.4 ❌ 不可行（需負 padding）
- 方案 B（**推薦**）：把 padding 從預設 `padding above tallest component`（2.5mm）改為「-2mm 嵌入式」設計，讓 header 主動戳入 lid cutout
  ```python
  inner_h = standoff_height + pcb_t + pin_header_height - lid_h - 2
  ```
- 方案 C：加參數 `header_protrude_mm = 2`，明確讓 header 突出 lid 上方 2mm，使用者能直接從外插杜邦線

### 5. Standoff 螺絲適配

**現況**：⌀5 外圓 / ⌀2.5 內孔

| 螺絲類型 | 軸徑 | 推薦底孔 | 我們 ⌀2.5 是否合用 |
|---------|------|---------|-------------------|
| **M3 self-tap (PETG)** | 3.0mm | 2.5mm | ✅ 完美 |
| **M2.5 self-tap (PETG)** | 2.5mm | 2.0mm | ❌ 太鬆，咬不住 |
| M2.5 機械螺紋 + heat-set insert | 2.5mm | 2.5mm | ✅（需熱嵌銅套） |
| M3 機械螺紋 + heat-set insert | 3.0mm | 2.7mm | ⚠️ 略小（需擴孔） |

**現有設計暗指 M3 self-tap**，但函式參數命名 `standoff_inner_d=2.5` 容易誤導為 M2.5。

**修正建議**：
1. 在 docstring 標註「⌀2.5 對應 M3 self-tap」
2. 或改成預設 `standoff_inner_d=2.0`（M2.5 self-tap，更小巧），讓使用者明確需要時改 2.5

### 6. 防誤插缺失

**對稱性分析**：
- 4 個 snap arm 在 X 軸完全對稱：±0.30 × outer_l
- 4 個 snap arm 在 Y 軸完全對稱：±(outer_w/2 + ...)
- 4 個 lid header cutouts 接近對稱（除 ICSP 不對稱）

**問題**：使用者拿到 lid 後可能旋轉 180° 安裝，外觀完全合理，但 USB-B / DC-Jack 切口會出現在「該是」digital headers 的方向。

**修正建議**（防呆設計）：
1. **角落圓角不對稱**：base 一個角落用 R3 大圓角，lid 對應角也 R3，其他三角 R1
2. **Lid 邊緣標記凹槽**：在 USB 那一側 lid 邊緣加一個 2×2mm 凹缺口，組裝錯方向會看到凹缺口在錯邊
3. **Snap arm 位置不對稱**：4 個 arm 中 1 個位置略偏 5mm，組裝錯方向則該 arm 對不到 recess
4. **長/短邊用不同 snap recess 尺寸** (但已經是 4 都同一尺寸，需重設計)

最簡單：方案 1（圓角差異化）。

### 7. 列印方向需在說明書註明

| 件 | 推薦方向 | 理由 |
|----|---------|------|
| Base | 底面朝下（standoffs 朝上）| 自然，無支撐 |
| **Lid** | **頂面朝下（snap arms 朝上）** | 必要！arms 朝下印會層間剝離斷裂 |

當前 STL 檔輸出時，build123d 直接以「組裝座標」匯出，使用者切片時會習慣性「平躺最大面」，可能直接把 lid 平面朝下放（如此 arms 朝上，**剛好正確**）。但若使用者把 lid 翻過來（arms 朝下），就會出問題。

**修正建議**：
- 輸出 STL 前先做「lid.mirror(z=lid_h/2)」讓默認朝向就是 print-ready
- 或在腳本印出明顯警告

---

## 修正優先級

### 🔴 P0：必修（影響功能）

```python
# lib/cad/shell.py:_build_two_piece_lid，修 lip 寬度 bug
bd.Box(snap_arm_w, snap_lip_d, snap_lip_h, mode=bd.Mode.ADD)
#                  ^^^^^^^^^^^ 從 snap_arm_t + snap_lip_d 改回 snap_lip_d
```

```python
# build_pcb_two_piece 修預設應力參數（PETG 安全區）
snap_arm_h: float = 8.0,    # 6.0 → 8.0
snap_lip_d: float = 0.5,    # 0.8 → 0.5
```

### 🟡 P1：建議修

```python
# 加 PCB header 突出 lid 控制
header_protrude_mm: float = 2.0,
# inner_h 改為 = standoff + pcb + pin_header - lid - header_protrude
```

```python
# Lid 防誤插：左前角加大圓角
def _add_keyed_corner(lid_part, position='-X-Y'):
    # base 對應角同步加大圓角，組裝錯方向則對不齊
```

### 🟢 P2：可選

```python
# Docstring 註明
"""
standoff_inner_d=2.5 對應 M3 self-tap（PETG）。
M2.5 self-tap 需改用 standoff_inner_d=2.0。
列印方向：base 底面朝下，lid 頂面朝下（snap arms 朝上）。
"""
```

---

## 修正後預期

套用 P0+P1 後：

| 指標 | 修正前 | 修正後 |
|------|--------|--------|
| PETG 應變利用率 | 125% ❌ | 35% ✅ |
| 4-arm 總插入力 | 100 N | 26 N |
| Lip 探出外壁 | 1.25mm | 0mm |
| Header 至 Lid 距離 | 2.0mm | -2.0mm（突出） |
| 防誤插 | 無 | 圓角差異化 |

是否要直接動手修正？建議路線：

1. **立刻修 P0**（lip bug + 應力參數）— 5 分鐘
2. **重跑驗證腳本** 看修正後幾何
3. **再做 P1 防誤插**（圓角差異）— 15 分鐘
4. **更新 changelog + experience**
