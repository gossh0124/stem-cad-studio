# 從 Arduino Uno 擴展到全 43 元件的分析

**現狀**：Phase A-C 完整 pipeline 只覆蓋 1 個元件（Arduino-Uno-class）。
**目標**：將 PCBSpec 權威座標 + build123d 殼體生成 + flanged-lid snap-fit 推廣到 43 個元件。

---

## 1. 元件分類（依複雜度）

依現有 `COMPONENT_REGISTRY`：

### Tier 1：完整 PCB 模組（4 個）— 需 EAGLE/KiCad/PDF 三來源

| Class | 尺寸 (mm) | 現狀 | 重點難度 |
|-------|-----------|------|---------|
| Arduino-Uno-class | 68.6×53.3×14 | ✅ DONE | — |
| ESP32-class | 51.5×28×12 | ⏳ ports 手填 | DOIT DevKit V1 無官方 EAGLE，需用社群 KiCad |
| RaspberryPi-class | 85.6×56.5×17 | ⏳ ports 手填 | RPi Foundation 提供 STEP，但無 EAGLE/KiCad |
| Microbit-class | 51.6×42×11.7 | ⏳ ports 手填 | Microbit Foundation 提供 KiCad source |

### Tier 2：模組板（14 個）— 需 vendor datasheet PDF

中型 PCB，通常無官方 EAGLE，需從 datasheet 量測 + 拍照交叉驗證。

| Class | 尺寸 (mm) | Pin 數 | 通用 chip |
|-------|-----------|--------|-----------|
| Sensor-Ultrasonic-class | 45×20×15 | 4 | HC-SR04 |
| Sensor-PIR-class | 32×24×25 | 3 | HC-SR501 |
| Sensor-TempHumid-class | 25×15×7.7 | 4 | DHT22 |
| Sensor-SoilMoisture-class | 98×23×3.5 | 3 | resistive prong |
| Sensor-Light-class | 30×15×7 | 4 | BH1750 / LDR |
| Sensor-IR-class | 32×14×10 | 4 | KY-022 |
| Display-OLED-class | 27×27×4 | 4 | SSD1306 0.96" |
| Display-LCD-class | 80×36×12 | 4 (I2C) / 16 | HD44780 |
| Display-EInk-class | 89×38×5 | 8 | Waveshare 2.13" |
| LED-Matrix-class | 32×32×13 | 5 | MAX7219 8×8 |
| Relay-Module-class | 50×26×19 | 6 | 1ch 5V relay |
| MP3-Module-class | 20×20×5 | 16 | DFPlayer Mini |
| Joystick-class | 34×26×32 | 5 | dual-axis + button |
| Buzzer-Active/Passive | 12×12×9 | 2-3 | piezo |

### Tier 3：分立元件（7 個）— 只需 datasheet 機械尺寸

通常焊在麵包板或主板上，**不需獨立殼體**（多半已標 `skip_enclosure=False` 但實務上不會印殼）。

| Class | 性質 |
|-------|------|
| Button-class | tactile switch 6×6 / 12×12 |
| Switch-class | toggle switch |
| Switch-Generic-class | 同上 |
| Potentiometer-class | 旋鈕式可變電阻 |
| Battery-LiPo-class | 軟包鋰電 |
| Battery-AA-class | 4×AA 電池盒 |
| USB-5V-class | 6V 變壓器 |

**建議**：這層直接設 `skip_enclosure=True`，跳過 CAD 流程，只保留 Phase 2/3 用的 ports/dimensions。

### Tier 4：機械致動器（5 個）— 非 PCB，需不同範式

不適合「box enclosure」模型。需要**支架 / 夾具 / 連接耳**這類機械接合件。

| Class | 性質 | 殼體類型 |
|-------|------|---------|
| Motor-Servo-class | SG90 標準伺服 | 標準伺服支架（鎖耳 + 主軸孔） |
| Motor-DC-class | 直流馬達 | 卡箍（hose clamp 式） |
| Motor-Stepper-class | NEMA 17 | NEMA 標準法蘭 |
| Pump-Water-class | 沉水馬達 | 防水套筒 |
| Speaker-class | 喇叭 | grill + 聲腔 |

**建議**：另開 `lib/cad/mounts.py` 處理這類「機械接合」需求，不走 PCB enclosure 流程。

### Tier 5：已標 skip_enclosure（10 個）

LEDs、Strip、NeoPixel、Adapter 等已正確標記，無需處理。

---

## 2. 現有架構的限制（必須改的部分）

`lib/pcb/arduino_uno_r3.py` 目前是 Arduino-specific：

```python
@dataclass(frozen=True)
class PCBSpec:
    pins_janalog: Tuple[NamedPin, ...]   # ← Arduino 名稱
    pins_jdigital: Tuple[NamedPin, ...]  # ← Arduino 名稱
    pins_icsp: Tuple[NamedPin, ...]      # ← Arduino 名稱
```

**改造**：合併為單一 `pins: Tuple[NamedPin, ...]` + `pin_groups: Dict[str, Tuple[int, ...]]`。

```python
@dataclass(frozen=True)
class PCBSpec:
    pins: Tuple[NamedPin, ...]                    # 所有 pin 統一列
    pin_groups: Dict[str, Tuple[int, ...]] = ...  # 邏輯分組（Arduino 用 'JANALOG'/'JDIGITAL'/'ICSP'）
    mounting_holes: Tuple[MountingHole, ...]
    sub_components: Tuple[SubComponent, ...]
    header_groups: Tuple[HeaderGroup, ...]        # 切口用群組（保留）
```

`pin_index_map()` 不變（已經把所有 pin 合併過）。`derive_connector_port_specs()` 已用 header_groups 不依賴具體名稱，OK。

---

## 3. 三來源資料的可獲取性

**Tier 1（4 個 MCU）**：

| Board | EAGLE | KiCad | PDF | 備註 |
|-------|-------|-------|-----|------|
| Arduino Uno R3 | ✅ 官方 | ✅ kicad-footprints | ✅ A000066 | DONE |
| ESP32 DevKit V1 | ❌ | ✅ Espressif/社群 | ✅ ESP32 datasheet | 多廠 layout 略異 |
| Raspberry Pi 4B | ❌ | ⚠️ 社群 | ✅ RPi 官方 | 官方提供 STEP file 可解析 |
| Microbit V2 | ❌ | ✅ microbit-foundation/microbit-v2-hardware | ✅ tech-spec PDF | 社群 KiCad 完整 |

**Tier 2（14 個模組）**：

模組板的 datasheet 通常只有 **「機械圖 + pin 表」** 兩頁。KiCad 社群庫（kicad-symbols）有部分覆蓋：
- HC-SR04: kicad-footprints/Sensor.pretty
- DHT22: 有
- SSD1306 OLED: 有
- DFPlayer Mini: 有

沒有的（PIR、土壤感測器等）需從 vendor PDF + 實物拍照測量。

**Tier 3-4**：純 datasheet 機械圖，不複雜。

---

## 4. 殼體適用性分析

並非所有元件都需要「Arduino-Uno 式 base+lid+snap-fit」殼體：

| Tier | 殼體型態 | 需重設計 lib/cad/ 嗎？ |
|------|---------|----------------------|
| Tier 1 | 同 Arduino，PCBSpec → build_pcb_two_piece | 直接複用，零改動 |
| Tier 2 | 多半需小型開口殼 + snap-fit | 同樣複用 build_pcb_two_piece 但 standoffs 量會少 |
| Tier 3 | 不需殼，焊麵包板 | 設 skip_enclosure=True |
| Tier 4 | 完全不同範式（夾具/支架） | **需新模組 lib/cad/mounts.py** |

**lib/cad/shell.py 不需大改**，主要改 lib/pcb 的資料結構讓多元件共用。

---

## 5. 工作量估算

依「Phase A 收集 + Phase B 接接 + Phase C 殼體」的細粒度：

| 階段 | 單元件耗時 | Arduino 實際 | Tier 1 預估 (3 個) | Tier 2 預估 (14 個) |
|------|-----------|-------------|--------------------|---------------------|
| A1 抓 EAGLE | 5 min | ✅ | N/A（無官方檔） | N/A |
| A2 抓 KiCad | 5 min | ✅ | 15 min | 70 min |
| A3 抓 PDF | 5 min | ✅ | 15 min | 70 min |
| 解析 + 交叉驗證 | 30 min | ✅ | 90 min | 7 hr (簡化) |
| 寫 lib/pcb/{name}.py | 60 min | ✅ | 180 min | 3.5 hr/件 |
| 接 registry | 5 min | ✅ | 15 min | 70 min |
| 視覺驗證 + 修 | 30 min | ✅ | 90 min | 7 hr |
| **小計** | **~140 min/件** | — | **6.7 hr** | **22.6 hr** |

Tier 3-4 要看是否真的需要殼體。如果 Tier 3 全標 skip_enclosure，Tier 4 另開 mounts 模組（~10 hr 設計時間），總計：

**全套件擴展總工時：≈ 40 小時**（不含 Tier 4 的機械接合件設計）。

---

## 6. 自動化機會

降低人工成本的工具：

### A. KiCad 批次解析

寫 `scripts/kicad_to_pcbspec.py`：
- 讀 `.kicad_mod` footprint
- 自動推導 NamedPin（從 pad 名稱）
- 推導 SubComponent 本體（從 fp_text 標籤 + 3D model 連結）
- 輸出 lib/pcb/{name}.py 草稿

對於 KiCad 庫覆蓋的元件，可省 ~50% 人工。

### B. PDF 機械圖 OCR

對 Tier 2 模組：
- PyMuPDF 抓 page → 套 OCR / 物件偵測
- 識別 「⌀」、「mm」 標註自動抽尺寸
- 雛形可達 70% 準確，剩 30% 人工校對

### C. 從 STEP 反推

RPi 官方提供 STEP file。寫 `scripts/step_to_pcbspec.py`：
- trimesh / OCCT 解析 STEP
- 自動提取 mounting holes（識別圓柱孔）
- 自動提取 connector bbox（找突出 PCB 邊緣的實體）

這對 Tier 1 的 RPi 特別有用。

### D. 三來源交叉驗證自動化

現在三來源比對是手動跑 script。可寫 `lib/pcb/cross_validate.py`：
- 輸入 EAGLE pads + KiCad pads + PDF assertions
- 自動判定哪個來源「最常見」（majority vote）
- 標記 outlier 給人工 review

---

## 7. 推薦執行順序

**Phase α：架構通用化（必須先做，2-3 hr）**

1. `lib/pcb/__init__.py` 抽出 `PCBSpec` 通用基類（移除 `pins_janalog/jdigital/icsp` 三個 Arduino 專屬欄位）
2. 改成 `pins: Tuple[NamedPin, ...]` + `pin_groups: Dict[str, Tuple[int, ...]]`
3. Arduino-Uno 改成符合新基類（向後相容測試）
4. 補 `find_pin()` / `pin_index_map()` 等共用方法

**Phase β：Tier 1 三個 MCU（6-8 hr）**

優先序建議：
1. **ESP32-class** — 用得最多，社群 KiCad 完整
2. **Microbit-class** — 教育場域常用，官方 KiCad 完整
3. **RaspberryPi 4B** — 較複雜（USB-C / HDMI / Audio jack 多側突出），需新增 right/top/bottom 側壁 cutout 支援

**Phase γ：Tier 2 模組（分批）**

依 Phase 2/3 wiring 使用頻率排序：
- 必裝（用例 80%+）：HC-SR04、DHT22、OLED、Servo（雖 Tier 4）、Buzzer
- 常用：Relay、PIR、Soil、LCD、LED-Matrix
- 偶用：MP3、E-Ink、Joystick、IR、Light

每批 3-4 個一起做，共用工具腳本。

**Phase δ：Tier 4 機械件（單獨 sprint）**

需要：
- `lib/cad/mounts.py` 新模組
- ServoBracketSpec / DCMotorClampSpec / NEMA17FlangeSpec / SpeakerGrillSpec / WaterPumpSleeveSpec
- 共用 build123d，但生成邏輯完全不同（不是 box enclosure）

**Phase ε：Tier 3 跳過**

直接 `skip_enclosure=True`，註明「焊麵包板使用」即可。

---

## 8. 風險與不確定性

| 風險 | 影響 | 緩解 |
|------|------|------|
| Tier 1 ESP32 多廠 layout 不一致 | DOIT vs WROOM vs LOLIN32 變體差 ~3mm | 選最常見 DOIT V1 為基準，其他變體標 alias |
| Tier 2 modules 沒有 KiCad/EAGLE | 每件需手測 | 自動化 OCR + 實物校對 |
| 手測誤差累積 | pin 位置 ±1mm | 強制 Phase D overlay 視覺驗證 |
| Tier 4 規範不一 | servo/motor 廠牌差異大 | 以最常見規格（SG90、NEMA17）為基準 |
| 殼體 lib/cad 假設 left-only protrudes | RPi 有 4 側突出 | 擴 `_apply_side_cutouts` 支援 right/top/bottom |

---

## 9. 結論與建議

**現階段不適合一次推全 43 件。** 建議分三階段：

| 階段 | 件數 | 工時 | 產出 |
|------|------|------|------|
| **立即（2 週內）**：Phase α + Tier 1 三件 | +3 | ~10 hr | 4 主流 MCU 全覆蓋 |
| **中期（1 個月）**：Tier 2 高頻模組 | +6 | ~12 hr | 80% Phase 3 wiring 用例覆蓋 |
| **長期（依需求）**：Tier 2 剩餘 + Tier 4 | +13 | ~25 hr | 全套件覆蓋 |

**最高 ROI 第一步**：做 **Phase α 通用化重構**（2-3 hr），讓現有架構不再寫死 Arduino。完成後新增任何 PCB 元件都是「填表格」工作。

要我先動 Phase α 嗎？單元件層 + registry 接接介面不會破壞，只是把 `pins_janalog/jdigital/icsp` 收攏成 `pins` + `pin_groups`。
