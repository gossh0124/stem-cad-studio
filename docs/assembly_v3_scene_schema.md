# Assembly V3 — SceneGraph JSON Schema

> Solver（Python 後端） ↔ Renderer（Three.js 前端）的唯一契約。
> 前端只讀此 JSON，不做任何業務邏輯計算。

---

## 1. TypeScript Interface 定義

```typescript
// ════════════════════════════════════════════
// Assembly V3 SceneGraph — 完整型別定義
// 座標系：Y-up (Three.js)，單位 mm，原點 enclosure base 底面中心
// ════════════════════════════════════════════

// ── 頂層 ──────────────────────────────────

interface SceneGraphV3 {
  version: "3.0";
  project_name: string;
  coordinate_system: {
    up: "Y";
    unit: "mm";
    origin: "enclosure_base_bottom_center";
  };

  enclosure: Enclosure;
  components: ComponentNode[];
  wires: Wire[];
  assembly_sequence: AssemblyStep[];
  overlays: OverlaySet;
  decisions: Decision[];

  /** solver 執行 metadata */
  _meta: {
    solver_version: string;
    generated_at: string;           // ISO 8601
    solve_duration_ms: number;
    component_count: number;
    wire_count: number;
  };
}

// ── 外殼 ──────────────────────────────────

interface Enclosure {
  inner_dimensions: [number, number, number];   // [L, W, H] mm
  wall_thickness: number;                        // mm
  material: string;                              // "PLA" | "PETG" | ...

  base: MeshRef;
  lid: MeshRef;

  /** 殼面開孔（感測器窗、通風柵、USB 口…） */
  cutouts: Cutout[];
}

interface MeshRef {
  /** 相對於 shells/ 目錄的路徑；null = 用 ghost box fallback */
  stl_path: string | null;
  glb_path: string | null;

  /** 場景內的 transform（相對原點） */
  position: Vec3;       // [x, y, z] mm
  rotation: Vec3;       // [rx, ry, rz] degrees, Euler XYZ
  scale: Vec3;          // 通常 [1, 1, 1]

  /** ghost box 尺寸（STL 載入前的佔位方塊）*/
  ghost_size: Vec3;     // [L, H, W] mm — Y-up 慣例: [x尺寸, y尺寸, z尺寸]

  /** 渲染屬性 */
  material_hint: {
    color: string;            // hex "#8899aa"
    opacity: number;          // 0-1
    roughness: number;
    metalness: number;
    side: "front" | "back" | "double";
  };
}

interface Cutout {
  face: Face;
  shape: "rect" | "circle" | "slot";
  center_uv: [number, number];   // 殼面 2D 座標 mm
  size: [number, number];         // [width, height] 或 [diameter, 0]
  purpose: string;                // "sensor_window" | "usb_port" | "vent_grill" | ...
}

// ── 元件節點 ─────────────────────────────

interface ComponentNode {
  id: string;                     // 唯一識別 "{type}_{index}" e.g. "Arduino-Uno-class_0"
  type: string;                   // registry class_name
  role: string;                   // "Brain" | "Sensor" | "Output" | "Control" | "Power" | ...
  label: string;                  // 人類可讀名稱

  enclosure_relation: EnclosureRelation;
  zone: string;                   // solver zone 分配結果

  /** 3D 定位（相對原點） */
  transform: {
    position: Vec3;               // [x, y, z] mm
    rotation: Vec3;               // [rx, ry, rz] degrees
  };

  /** 物理尺寸 */
  dimensions: Vec3;               // [L, W, H] mm
  weight_g: number;

  /** 3D 模型引用（按優先順序嘗試） */
  meshes: {
    pcb_body: MeshRef | null;     // PCB 3D 模型（GLB/STL）
    shell_base: MeshRef | null;   // 元件自身外殼
    shell_lid: MeshRef | null;
    mount: MeshRef | null;        // 安裝支架
  };

  /** 接口資訊（用於走線端點計算已由 solver 完成，前端僅供 tooltip） */
  ports: PortInfo[];

  /** 朝向 — 主要連接口面向的殼面 */
  face_out: Face;

  /** 熱屬性（前端 overlay 用） */
  thermal: {
    power_mw: number;
    estimated: boolean;
    estimation_source: string;    // "datasheet" | "V×I×η"
    surface_temp_c: number;       // solver 估算的穩態表面溫度
  };

  /** Panel 元件專屬（enclosure_relation == "panel" 時存在） */
  panel_info?: {
    face: Face;
    u: number;                    // 殼面 2D 座標 mm
    v: number;
  };

  /** External 元件專屬 */
  external_info?: {
    wire_exit_face: Face;
    wire_exit_u: number;
    wire_exit_v: number;
    wire_exit_diameter: number;   // mm
  };

  /** Embedded 元件專屬 */
  embedded_info?: {
    host_structure: string;       // "external_body" | "water_tank" | ...
  };
}

interface PortInfo {
  name: string;
  side: string;
  port_type: string;              // "USB" | "PWR" | "GPIO" | "I2C" | ...
  position_3d: Vec3;              // solver 計算的 pin 3D 座標
}

// ── 走線 ──────────────────────────────────

interface Wire {
  id: string;                     // "wire_{index}"
  from_component: string;         // ComponentNode.id
  to_component: string;
  from_pin: string;               // pin 名稱 "D2" | "VCC" | "A0"
  to_pin: string;

  signal: SignalType;
  color: string;                  // hex "#ff4444"
  style: string;                  // 插值風格 "catmull-rom" | "linear"

  /** 完整 3D polyline（pin-to-pin），solver 已計算 */
  path3d: Vec3[];                 // 每點 [x, y, z] mm
  layer_z: number;                // 走線層 Z 高度 mm

  routed_length_mm: number;

  /** 渲染提示 */
  render_hint: {
    tube_radius: number;          // mm，預設 0.5
    opacity: number;
    pulse_speed: number;          // 脈動動畫速度（0=關閉）
  };
}

// ── 組裝步驟序列 ─────────────────────────

/** solver `_build_assembly_sequence` 輸出的扁平步驟清單 */
interface AssemblyStep {
  step: number;                   // 0-based 序號
  action: AssemblyAction;         // 動作類型
  target: string;                 // ComponentNode.id | Wire.id | "enclosure"
}

type AssemblyAction =
  | "enclosure_base_appear"
  | "enclosure_lid_close"
  | "wire_route"
  | string;                       // 元件自訂步驟（來自 ComponentModule.assembly_steps）

// ── Overlay 資料 ─────────────────────────

interface OverlaySet {
  thermal: ThermalOverlay;
  airflow: AirflowOverlay;
  wiring: WiringOverlay;
}

/** Thermal overlay — 前端依此畫色溫 + 熱場 gradient */
interface ThermalOverlay {
  ambient_temp_c: number;                     // 環境溫度，預設 25
  heat_sources: ThermalSource[];
  total_power_mw: number;
  needs_venting: boolean;
  vent_placements: VentPlacement[];

  /** 場域離散溫度場（optional；大場景時 solver 預算格點溫度） */
  temperature_field?: TemperatureFieldPoint[];

  /** 色溫 LUT 定義（前端共用；solver 指定確保一致性） */
  color_lut: ThermalColorStop[];
}

interface ThermalSource {
  component_id: string;         // 對應 ComponentNode.id
  power_mw: number;
  estimated: boolean;
  estimation_source: string;
  surface_temp_c: number;
  /** 熱場影響半徑 mm（前端畫 gradient 用） */
  influence_radius_mm: number;
}

interface TemperatureFieldPoint {
  position: Vec3;
  temp_c: number;
}

interface ThermalColorStop {
  t: number;    // 0-1 正規化
  color: string; // hex
}

interface VentPlacement {
  face: string;
  area_mm2: number;
  position_uv?: [number, number];
}

/** Airflow overlay — 粒子系統參數 */
interface AirflowOverlay {
  enabled: boolean;
  particle_count: number;
  /** Boussinesq 模型參數 */
  boussinesq: {
    beta: number;               // 熱膨脹係數 1/K
    gravity: number;            // m/s²
    drag_coefficient: number;   // 每幀衰減
  };
  /** 風道向量場（optional；solver 預算離散向量） */
  vector_field?: AirflowVector[];
}

interface AirflowVector {
  position: Vec3;
  velocity: Vec3;               // mm/s
  temperature_c: number;
}

/** Wiring overlay — 走線顯示設定 */
interface WiringOverlay {
  /** 各 signal type 的顏色映射 */
  signal_colors: Record<SignalType, string>;
  /** 各 signal type 的 Z 層偏移 */
  layer_z_offsets: Record<SignalType, number>;
  /** 脈動動畫全域開關 */
  pulse_enabled: boolean;
  pulse_speed: number;
  /** pin marker 半徑 mm */
  pin_marker_radius: number;
}

// ── 決策紀錄 ─────────────────────────────

interface Decision {
  step: string;                   // "gravity_sort" | "thermal_classify" | ...
  principle: string;              // 設計原則
  description: string;            // 人類可讀說明
  formula: string;                // 計算公式
  six_e_stage: string;            // "engineer" | "explain" | ...
}

// ── 共用型別 ─────────────────────────────

type Vec3 = [number, number, number];

type Face = "top" | "bottom"
          | "side-front" | "side-back"
          | "side-left" | "side-right";

type EnclosureRelation = "internal" | "breadboard"
                        | "panel" | "external" | "embedded";

type SignalType = "power" | "gnd" | "digital" | "analog"
               | "i2c" | "spi" | "uart" | "pwm";
```

---

## 2. 範例 JSON — 自動澆花器

以 Arduino-Uno + Sensor-SoilMoisture + Pump-Water + Relay-Module + Battery-AA(external) 為例。

```json
{
  "version": "3.0",
  "project_name": "auto_waterer_demo",
  "coordinate_system": {
    "up": "Y",
    "unit": "mm",
    "origin": "enclosure_base_bottom_center"
  },

  "enclosure": {
    "inner_dimensions": [139.2, 132.0, 27.0],
    "wall_thickness": 2.0,
    "material": "PLA",
    "base": {
      "stl_path": "shells/Arduino-Uno-class/base_stl.stl",
      "glb_path": null,
      "position": [0, 0, 0],
      "rotation": [0, 0, 0],
      "scale": [1, 1, 1],
      "ghost_size": [143.2, 29.0, 136.0],
      "material_hint": {
        "color": "#8899aa",
        "opacity": 0.12,
        "roughness": 0.4,
        "metalness": 0.0,
        "side": "double"
      }
    },
    "lid": {
      "stl_path": "shells/Arduino-Uno-class/lid_stl.stl",
      "glb_path": null,
      "position": [0, 31.0, 0],
      "rotation": [0, 0, 0],
      "scale": [1, 1, 1],
      "ghost_size": [143.2, 4.0, 136.0],
      "material_hint": {
        "color": "#6699bb",
        "opacity": 0.10,
        "roughness": 0.4,
        "metalness": 0.0,
        "side": "double"
      }
    },
    "cutouts": [
      {
        "face": "side-back",
        "shape": "circle",
        "center_uv": [69.6, 13.5],
        "size": [6.0, 0],
        "purpose": "wire_exit_battery"
      }
    ]
  },

  "components": [
    {
      "id": "Arduino-Uno-class_0",
      "type": "Arduino-Uno-class",
      "role": "Brain",
      "label": "Arduino Uno R3",
      "enclosure_relation": "internal",
      "zone": "center",
      "transform": {
        "position": [-33.3, 16.0, [-31.66]],
        "rotation": [0, 0, 0]
      },
      "dimensions": [68.58, 53.34, 14.0],
      "weight_g": 25,
      "meshes": {
        "pcb_body": {
          "stl_path": "shells/Arduino-Uno-class/pcb_body.stl",
          "glb_path": "shells/Arduino-Uno-class/pcb_body.glb",
          "position": [-33.3, 16.0, -31.66],
          "rotation": [0, 0, 0],
          "scale": [1, 1, 1],
          "ghost_size": [68.58, 14.0, 53.34],
          "material_hint": {
            "color": "#005668",
            "opacity": 0.9,
            "roughness": 0.35,
            "metalness": 0.05,
            "side": "front"
          }
        },
        "shell_base": null,
        "shell_lid": null,
        "mount": null
      },
      "ports": [
        { "name": "USB-B", "side": "face", "port_type": "USB", "position_3d": [-33.3, 16.0, -58.0] },
        { "name": "DC-Jack", "side": "face", "port_type": "PWR", "position_3d": [-20.0, 16.0, -58.0] }
      ],
      "face_out": "side-front",
      "thermal": {
        "power_mw": 250,
        "estimated": false,
        "estimation_source": "datasheet",
        "surface_temp_c": 35.0
      }
    },
    {
      "id": "Sensor-SoilMoisture-class_0",
      "type": "Sensor-SoilMoisture-class",
      "role": "Sensor",
      "label": "Capacitive Soil Moisture Sensor v1.2",
      "enclosure_relation": "internal",
      "zone": "face-edge",
      "transform": {
        "position": [6.5, 4.5, -31.66],
        "rotation": [0, 0, 0]
      },
      "dimensions": [23.0, 98.0, 3.5],
      "weight_g": 8,
      "meshes": {
        "pcb_body": {
          "stl_path": "shells/Sensor-SoilMoisture-class/pcb_body.stl",
          "glb_path": "shells/Sensor-SoilMoisture-class/pcb_body.glb",
          "position": [6.5, 4.5, -31.66],
          "rotation": [0, 0, 0],
          "scale": [1, 1, 1],
          "ghost_size": [23.0, 3.5, 98.0],
          "material_hint": {
            "color": "#2a7a3a",
            "opacity": 0.9,
            "roughness": 0.4,
            "metalness": 0.0,
            "side": "front"
          }
        },
        "shell_base": null,
        "shell_lid": null,
        "mount": null
      },
      "ports": [
        { "name": "AO", "side": "top", "port_type": "GPIO", "position_3d": [15.0, 4.5, 17.3] }
      ],
      "face_out": "top",
      "thermal": {
        "power_mw": 25,
        "estimated": false,
        "estimation_source": "datasheet",
        "surface_temp_c": 26.0
      }
    },
    {
      "id": "Pump-Water-class_0",
      "type": "Pump-Water-class",
      "role": "Output",
      "label": "Mini Submersible Water Pump 3-5V",
      "enclosure_relation": "internal",
      "zone": "bottom-edge",
      "transform": {
        "position": [28.0, 14.5, -31.66],
        "rotation": [0, 0, 0]
      },
      "dimensions": [30.0, 45.0, 25.0],
      "weight_g": 45,
      "meshes": {
        "pcb_body": null,
        "shell_base": null,
        "shell_lid": null,
        "mount": {
          "stl_path": "shells/Pump-Water-class/mount_stl.stl",
          "glb_path": null,
          "position": [28.0, 14.5, -31.66],
          "rotation": [0, 0, 0],
          "scale": [1, 1, 1],
          "ghost_size": [30.0, 25.0, 45.0],
          "material_hint": {
            "color": "#446688",
            "opacity": 0.85,
            "roughness": 0.5,
            "metalness": 0.1,
            "side": "front"
          }
        }
      },
      "ports": [
        { "name": "VCC", "side": "top", "port_type": "PWR", "position_3d": [28.0, 27.0, -31.66] },
        { "name": "GND", "side": "top", "port_type": "PWR", "position_3d": [32.0, 27.0, -31.66] }
      ],
      "face_out": "side-front",
      "thermal": {
        "power_mw": 1100,
        "estimated": false,
        "estimation_source": "datasheet",
        "surface_temp_c": 69.0
      }
    },
    {
      "id": "Relay-Module-class_0",
      "type": "Relay-Module-class",
      "role": "Control",
      "label": "5V Single Channel Relay Module",
      "enclosure_relation": "internal",
      "zone": "center",
      "transform": {
        "position": [-33.3, 11.5, 38.0],
        "rotation": [0, 0, 0]
      },
      "dimensions": [50.0, 26.0, 19.0],
      "weight_g": 15,
      "meshes": {
        "pcb_body": {
          "stl_path": "shells/Relay-Module-class/pcb_body.stl",
          "glb_path": "shells/Relay-Module-class/pcb_body.glb",
          "position": [-33.3, 11.5, 38.0],
          "rotation": [0, 0, 0],
          "scale": [1, 1, 1],
          "ghost_size": [50.0, 19.0, 26.0],
          "material_hint": {
            "color": "#2255aa",
            "opacity": 0.9,
            "roughness": 0.4,
            "metalness": 0.0,
            "side": "front"
          }
        },
        "shell_base": null,
        "shell_lid": null,
        "mount": null
      },
      "ports": [
        { "name": "IN", "side": "face", "port_type": "GPIO", "position_3d": [-33.3, 11.5, 25.0] },
        { "name": "COM", "side": "face", "port_type": "OTHER", "position_3d": [-20.0, 11.5, 25.0] }
      ],
      "face_out": "side-back",
      "thermal": {
        "power_mw": 400,
        "estimated": false,
        "estimation_source": "datasheet",
        "surface_temp_c": 41.0
      }
    },
    {
      "id": "Battery-AA-class_0",
      "type": "Battery-AA-class",
      "role": "Power",
      "label": "2xAA Battery Holder",
      "enclosure_relation": "external",
      "zone": "external-back",
      "transform": {
        "position": [0, 13.5, 70.0],
        "rotation": [0, 0, 0]
      },
      "dimensions": [59.0, 32.0, 15.0],
      "weight_g": 30,
      "meshes": {
        "pcb_body": null,
        "shell_base": null,
        "shell_lid": null,
        "mount": null
      },
      "ports": [],
      "face_out": "side-back",
      "thermal": {
        "power_mw": 0,
        "estimated": false,
        "estimation_source": "datasheet",
        "surface_temp_c": 25.0
      },
      "external_info": {
        "wire_exit_face": "side-back",
        "wire_exit_u": 69.6,
        "wire_exit_v": 0.0,
        "wire_exit_diameter": 6.0
      }
    }
  ],

  "wires": [
    {
      "id": "wire_0",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Sensor-SoilMoisture-class_0",
      "from_pin": "A0",
      "to_pin": "AO",
      "signal": "analog",
      "color": "#ffaa00",
      "style": "catmull-rom",
      "path3d": [
        [-33.3, 16.0, -37.3],
        [-32.6, 15.0, -37.0],
        [-32.6, 15.0, -15.0],
        [14.5, 15.0, -15.0],
        [15.0, 4.5, 17.3]
      ],
      "layer_z": 22.0,
      "routed_length_mm": 69.9,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_1",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Relay-Module-class_0",
      "from_pin": "D2",
      "to_pin": "IN",
      "signal": "digital",
      "color": "#44cc44",
      "style": "catmull-rom",
      "path3d": [
        [-33.3, 16.0, -37.3],
        [-32.6, 21.0, -37.0],
        [-42.6, 21.0, -37.0],
        [-42.6, 21.0, 51.0],
        [-33.3, 11.5, 25.0]
      ],
      "layer_z": 21.0,
      "routed_length_mm": 98.8,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_2",
      "from_component": "Relay-Module-class_0",
      "to_component": "Pump-Water-class_0",
      "from_pin": "COM",
      "to_pin": "VCC",
      "signal": "power",
      "color": "#ff4444",
      "style": "catmull-rom",
      "path3d": [
        [-20.0, 11.5, 25.0],
        [-20.0, 16.0, 25.0],
        [28.0, 16.0, 25.0],
        [28.0, 27.0, -31.66]
      ],
      "layer_z": 16.0,
      "routed_length_mm": 108.2,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_3",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Sensor-SoilMoisture-class_0",
      "from_pin": "5V",
      "to_pin": "VCC",
      "signal": "power",
      "color": "#ff4444",
      "style": "catmull-rom",
      "path3d": [
        [-10.0, 16.0, -57.3],
        [-10.0, 16.0, -40.0],
        [6.5, 16.0, -40.0],
        [6.5, 4.5, -31.66]
      ],
      "layer_z": 16.0,
      "routed_length_mm": 52.1,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_4",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Sensor-SoilMoisture-class_0",
      "from_pin": "GND",
      "to_pin": "GND",
      "signal": "gnd",
      "color": "#333333",
      "style": "catmull-rom",
      "path3d": [
        [-15.0, 16.0, -57.3],
        [-15.0, 18.0, -45.0],
        [10.0, 18.0, -45.0],
        [10.0, 4.5, -31.66]
      ],
      "layer_z": 18.0,
      "routed_length_mm": 48.3,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_5",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Relay-Module-class_0",
      "from_pin": "5V",
      "to_pin": "VCC",
      "signal": "power",
      "color": "#ff4444",
      "style": "catmull-rom",
      "path3d": [
        [-10.0, 16.0, -57.3],
        [-10.0, 16.0, 38.0],
        [-33.3, 16.0, 38.0]
      ],
      "layer_z": 16.0,
      "routed_length_mm": 119.3,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    },
    {
      "id": "wire_6",
      "from_component": "Arduino-Uno-class_0",
      "to_component": "Relay-Module-class_0",
      "from_pin": "GND",
      "to_pin": "GND",
      "signal": "gnd",
      "color": "#333333",
      "style": "catmull-rom",
      "path3d": [
        [-15.0, 18.0, -57.3],
        [-15.0, 18.0, 38.0],
        [-33.3, 18.0, 38.0]
      ],
      "layer_z": 18.0,
      "routed_length_mm": 119.3,
      "render_hint": {
        "tube_radius": 0.5,
        "opacity": 0.6,
        "pulse_speed": 1.0
      }
    }
  ],

  "assembly_sequence": [
    { "step": 0, "action": "enclosure_base_appear", "target": "enclosure" },
    { "step": 1, "action": "place_component", "target": "pump-water-0" },
    { "step": 2, "action": "place_component", "target": "arduino-uno-0" },
    { "step": 3, "action": "place_component", "target": "relay-module-0" },
    { "step": 4, "action": "place_component", "target": "sensor-soilmoisture-0" },
    { "step": 5, "action": "wire_route", "target": "w0" },
    { "step": 6, "action": "wire_route", "target": "w1" },
    { "step": 7, "action": "wire_route", "target": "w2" },
    { "step": 8, "action": "wire_route", "target": "w3" },
    { "step": 9, "action": "wire_route", "target": "w4" },
    { "step": 10, "action": "wire_route", "target": "w5" },
    { "step": 11, "action": "wire_route", "target": "w6" },
    { "step": 12, "action": "enclosure_lid_close", "target": "enclosure" }
  ],

  "overlays": {
    "thermal": {
      "ambient_temp_c": 25,
      "heat_sources": [
        {
          "component_id": "Pump-Water-class_0",
          "power_mw": 1100,
          "estimated": false,
          "estimation_source": "datasheet",
          "surface_temp_c": 69.0,
          "influence_radius_mm": 35.0
        },
        {
          "component_id": "Relay-Module-class_0",
          "power_mw": 400,
          "estimated": false,
          "estimation_source": "datasheet",
          "surface_temp_c": 41.0,
          "influence_radius_mm": 20.0
        },
        {
          "component_id": "Arduino-Uno-class_0",
          "power_mw": 250,
          "estimated": false,
          "estimation_source": "datasheet",
          "surface_temp_c": 35.0,
          "influence_radius_mm": 15.0
        },
        {
          "component_id": "Sensor-SoilMoisture-class_0",
          "power_mw": 25,
          "estimated": false,
          "estimation_source": "datasheet",
          "surface_temp_c": 26.0,
          "influence_radius_mm": 5.0
        }
      ],
      "total_power_mw": 1775,
      "needs_venting": false,
      "vent_placements": [],
      "color_lut": [
        { "t": 0.00, "color": "#2659d9" },
        { "t": 0.25, "color": "#19bf73" },
        { "t": 0.50, "color": "#e6d926" },
        { "t": 0.75, "color": "#f27319" },
        { "t": 1.00, "color": "#e61a1a" }
      ]
    },
    "airflow": {
      "enabled": true,
      "particle_count": 150,
      "boussinesq": {
        "beta": 0.0034,
        "gravity": 9.81,
        "drag_coefficient": 0.96
      }
    },
    "wiring": {
      "signal_colors": {
        "power": "#ff4444",
        "gnd": "#333333",
        "analog": "#ffaa00",
        "digital": "#44cc44",
        "i2c": "#44ddff",
        "spi": "#dd44ff",
        "pwm": "#44cc44",
        "uart": "#44ddff"
      },
      "layer_z_offsets": {
        "power": 2.0,
        "gnd": 4.0,
        "digital": 6.0,
        "pwm": 6.0,
        "analog": 8.0,
        "uart": 8.0,
        "i2c": 10.0,
        "spi": 10.0
      },
      "pulse_enabled": true,
      "pulse_speed": 0.003,
      "pin_marker_radius": 0.8
    }
  },

  "decisions": [
    {
      "step": "enclosure_partition",
      "principle": "殼體關係分流",
      "description": "依 enclosure_relation 分流 5 元件：pack(internal+breadboard)=4, panel=0, external=1, embedded=0。",
      "formula": "bucket = ComponentSpec.enclosure_relation",
      "six_e_stage": "engineer"
    },
    {
      "step": "gravity_sort",
      "principle": "重心穩定",
      "description": "依重量排序 4 個元件（總重 93g）。最重：Pump-Water (45g)，優先放置於底部。",
      "formula": "placement_priority = sorted(components, key=weight_g, desc)",
      "six_e_stage": "engineer"
    },
    {
      "step": "thermal_classify",
      "principle": "熱源隔離",
      "description": "功耗 > 500mW 的熱源：Pump-Water(1100mW)。需與 1 個感測器保持距離。",
      "formula": "hot_threshold = 500 mW",
      "six_e_stage": "engineer"
    },
    {
      "step": "zone_assign",
      "principle": "功能分區",
      "description": "Brain 居中便於走線輻射，感測器靠外壁便於開窗，熱源置底利用自然對流散熱。",
      "formula": "zone = f(role, is_hot)",
      "six_e_stage": "engineer"
    },
    {
      "step": "shelf_pack",
      "principle": "空間最佳化",
      "description": "FFD shelf packing：4 元件排入 139x132mm 空間，面積利用率 47%。",
      "formula": "utilization = 8644 / 18349 = 47%",
      "six_e_stage": "engineer"
    },
    {
      "step": "collision_check",
      "principle": "干涉防護（PV2）",
      "description": "無碰撞：4 個元件 AABB 無重疊。",
      "formula": "",
      "six_e_stage": "engineer"
    },
    {
      "step": "wire_route",
      "principle": "多層 3D 走線",
      "description": "A* 完成 7 條走線，分佈於 3 層 Z 平面，總長度 616mm。",
      "formula": "path = A*(pin_pos, obstacles); z = f(signal)",
      "six_e_stage": "explain"
    },
    {
      "step": "thermal_validate",
      "principle": "散熱設計",
      "description": "總熱功率 1775mW，密閉殼估算溫升 dT~25.4C，低於 2000mW 閾值，自然散熱即可。",
      "formula": "dT = P/(h*A_shell) = 1.775/(7.0*0.01) = 25.4C",
      "six_e_stage": "explain"
    }
  ],

  "_meta": {
    "solver_version": "3.0.0",
    "generated_at": "2026-05-16T14:30:00+08:00",
    "solve_duration_ms": 42,
    "component_count": 5,
    "wire_count": 7
  }
}
```

---

## 3. 設計決策說明

### 3.1 單一 JSON 文件作為唯一契約

**為什麼不分多個檔案？** Solver 一次性輸出完整場景狀態，renderer 只需讀一次 JSON 即可完全重建 3D 場景。避免前端需要多次 fetch 或拼接多個來源的資料，也避免版本不一致的問題。

### 3.2 元件以 `ComponentNode[]` 扁平陣列統一五桶

現有 solver 將元件分成 `placements` / `panel_placements` / `external_refs` / `embedded_refs` 四個獨立陣列，前端需要分別處理四種不同格式。V3 統一為單一 `components[]` 陣列，透過 `enclosure_relation` 欄位區分，各桶專屬欄位以 optional 的 `panel_info` / `external_info` / `embedded_info` 攜帶。

好處：
- 前端只需一個 `components.forEach()` 迴圈
- 動畫系統可以用統一的 `target_id` 引用任何元件
- wire 的 `from_component` / `to_component` 用同一個 namespace

### 3.3 走線攜帶完整 pin 資訊

現有 solver 的 wire_routes 只有 `from` / `to`（class name），同一對元件如果有多條線就無法區分。V3 每條 wire 攜帶 `from_pin` + `to_pin`，並用 `wire_{index}` 作為唯一 id，動畫系統可以依序逐條顯示。

### 3.4 `MeshRef` 統一 3D 模型引用

不管是外殼、元件 PCB body、mount，都用同一個 `MeshRef` 結構。每個 ref 同時提供 `stl_path` 和 `glb_path`，前端依載入優先順序嘗試（GLB 優先因為內含材質資訊，STL fallback），全部 null 時用 `ghost_size` 畫 box placeholder。

### 3.5 組裝步驟序列（assembly_sequence）

`assembly_sequence` 是一個扁平的步驟清單，由 solver 的 `_build_assembly_sequence` 產生。步驟順序隱含相依性：
- Step 0：外殼底座出現
- Step 1-N：依重量排序安裝各元件（重的先放，確保重心穩定）
- 接著：逐條走線 `wire_route`
- 最後：合蓋 `enclosure_lid_close`

前端依序播放即可，也可依 `action` 類型分群並行渲染同類步驟。

### 3.6 Overlay 資料預算在 solver 端

所有 overlay 參數（熱場色溫 LUT、Boussinesq 係數、走線顏色映射、Z 層偏移）都由 solver 放入 JSON。原因：
- **一致性**：solver 和 renderer 看到同樣的 signal color 定義，不會因為前端硬編碼與後端不同步
- **可調性**：不同專案可能有不同的 thermal LUT（例如高功耗專案需要更寬的溫度範圍）
- **前端零邏輯**：renderer 只做 `color = overlays.wiring.signal_colors[wire.signal]`，不需要自己維護映射表

### 3.7 座標轉換策略

Solver 內部使用「殼底左後角為原點的 XY 平面」（Z 為高度）。SceneGraph 輸出轉為 Three.js 的 Y-up 座標系，原點移至殼底中心。轉換公式：

```
scene_x = solver_x - inner_L/2
scene_y = wall_thickness + solver_z    (solver 的 Z 高度 → Three.js 的 Y)
scene_z = solver_y - inner_W/2         (solver 的 Y → Three.js 的 Z)
```

這個轉換由 solver 在輸出時完成，前端拿到的座標可以直接 `mesh.position.set(x, y, z)`。

### 3.8 向後相容考量

`version: "3.0"` 欄位讓前端可以判斷 JSON 版本。V3 renderer 如果遇到缺少 `version` 欄位的舊格式，可以 fallback 到 V2 渲染邏輯。新增的 optional 欄位（`temperature_field`、`vector_field`）不存在時前端自動退化為簡化模式。

### 3.9 render_hint 與 material_hint 分離

Mesh 的靜態材質屬性放在 `material_hint`（color, opacity, roughness...），走線的動態渲染屬性放在 `render_hint`（pulse_speed, tube_radius...）。前端可以直接映射到 Three.js 的 `MeshPhysicalMaterial` 和 `TubeGeometry` 參數，不需要額外計算。
