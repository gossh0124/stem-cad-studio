# CAD 引擎 / 套件 記憶（重建用）

> 這份檔案是 2026-05-08 大清空後唯一保留的 3D CAD 知識索引。
> 所有實際 3D CAD 程式碼都已刪除，等 Phase A 拿到權威數據後重建。

---

## 主用 B-rep 建模引擎

| 套件 | 角色 | pip 安裝 | 備註 |
|------|------|---------|------|
| **build123d** | 主引擎（OCCT B-rep） | `pip install build123d` | 統一引擎，輸出 STEP + STL；CLAUDE.md 指定不再用 cadquery |
| **OCP** | OCCT Python binding（build123d 依賴） | 自動安裝 | Open Cascade 7.7+ 核心 |

## 備援 / 降級鏈

| 套件 | 角色 | 觸發條件 |
|------|------|---------|
| **manifold3d** | mesh boolean 後援 | OCCT boolean 失敗時 |
| **trimesh** | STL 載入 / 量測 / 修復 | 預設 STL 處理 |
| **numpy-stl** | binary STL 低階讀寫 | 無依賴解析 STL header |

## 視覺化 / 渲染

| 套件 | 用途 |
|------|------|
| **matplotlib** | 2D 多視圖 + Poly3DCollection 3D 線框（粗渲染） |
| **pyvista** | 高品質 3D 互動 viewer（VTK backend） |
| **trimesh.viewer** | 快速 STL 預覽（pyglet） |
| **three.js** | 瀏覽器端 STL/STEP 互動檢視 |

## EDA / PCB 解析

| 套件 | 用途 |
|------|------|
| **kiutils** | KiCad `.kicad_pcb` / `.kicad_mod` parser（推薦，比手寫 regex 穩） |
| **PyMuPDF (fitz)** | A000066 PDF 機械圖向量提取 |
| **pcbnew** (KiCad Python API) | 直接讀 KiCad PCB（需安裝 KiCad） |
| **pdfplumber** | PDF 文字 / 表格抽取 |

## EAGLE 解析（Arduino 官方檔）

EAGLE `.brd` 是 XML 格式（v6+），可用：
- 標準 `xml.etree.ElementTree`（內建，足夠）
- **eagle-py**（pypi，較舊但能用）
- 直接 KiCad 匯入後用 kiutils 解析（推薦路線）

## 列印製造 / 驗證

| 套件 | 角色 |
|------|------|
| **trimesh** | 流形檢查 / 體積 / 重心 |
| **manifold3d** | bool 運算 + watertight 驗證 |
| **scipy.spatial** | 凸包 / KDTree / Voronoi |

---

## 重建後的目錄結構（規劃）

```
lib/
├── pcb/                       ← 新增：PCB 資料層（Phase A 產物）
│   ├── arduino_uno_r3.py     ← NamedPin + footprint 精確座標（從 3 來源交叉驗證）
│   ├── eagle_parser.py       ← .brd → NamedPin
│   ├── kicad_parser.py       ← .kicad_pcb → NamedPin（新建）
│   └── datasheet_parser.py   ← A000066 PDF → MountingHole + 機械尺寸
├── cad/                       ← 新增：3D CAD 生成層（Phase B）
│   ├── shell.py              ← build123d 殼體建構（取代 cad_engine.py + cad_builder.py）
│   ├── projection.py         ← SubComponent → 外殼開孔投影
│   └── tessellation.py       ← STL export 高密度 tessellation（取代預設 100 tris）
└── render/                    ← 新增：視覺化層
    ├── views_2d.py           ← matplotlib 多視圖
    ├── pcb_overlay.py        ← 官方 pinout 圖 overlay 比對
    └── viewer_3d.py          ← pyvista 互動 viewer
```

## 重建原則

1. **資料來源優先級**：EAGLE > KiCad > PDF（EAGLE 是 Arduino 官方原始檔）
2. **每根 pin 顯式命名**：不用 pin1+pitch 推導，直接 `NamedPin(name='NC', x=..., y=...)`
3. **三來源交叉驗證**：任何座標必須三個來源都同意（容差 ±0.1mm），否則標記不確定
4. **STL 高密度 tessellation**：build123d export 加 `linear_deflection=0.05`，從 100 tris → ~5000+
5. **Overlay 視覺驗證**：產出的座標必須能與官方 pinout 圖逐 pin 對齊
