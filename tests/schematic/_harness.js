// tests/schematic/_harness.js — P0.1 headless ELK 幾何 harness（DEC-H1）。
// 在 Node 載入 v6 前端模組(mock window)→ buildElkGraph → ELK.layout → 量 post-layout 幾何,
// 把「Chrome F5 目視」轉成可複現機器斷言。模式源自 .elkprobe（gitignore 拋棄式 probe）。
'use strict';
const fs = require('fs');
const path = require('path');
const M = require('elkjs');
const ELK = M.default || M;

const ROOT = path.join(__dirname, '..', '..'); // tests/schematic → repo root

// 依相依序載入(component-dimensions → mcu-ports → schematic-pins → comp-specs → elk-layout)
const MODULE_LOAD_ORDER = [
  'v6/data/component-dimensions.js',
  'v6/config/mcu-ports.js',
  'v6/data/schematic-pins.js',
  'v6/schematic/comp-specs.js',
  'v6/schematic/elk-layout.js',
];

function loadWindow() {
  const window = { __drops: [] };
  window.recordSchematicDrop = (...a) => window.__drops.push(a);
  window.recordSchematicRoute = () => {};
  window.resetSchematicTelemetry = () => { window.__drops.length = 0; };
  const c = { warn() {}, error() {}, info() {}, log() {} };
  for (const f of MODULE_LOAD_ORDER) {
    // 安全說明:src 為 repo 自有 v6 源碼檔(MODULE_LOAD_ORDER 為硬編白名單,無插值/無外部輸入),
    // 作為 Function body 整體傳入(非字串串接)。v6 為 browser IIFE 模組,須此法 headless 載入
    // (同 .elkprobe/probe.js)。非 code-injection 面(無 attacker-controlled 變數進 body)。
    const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
    new Function('window', 'console', src)(window, c); // eslint-disable-line no-new-func
  }
  return window;
}

// onEdge 容差(px)。probe 舊值 PORT_W+1≈7 過鬆(M4);收緊為具名常數:port marker 內緣須貼 node 邊。
const ON_EDGE_TOL_PX = 2;

// port marker 到其所屬邊的距離(複刻 SVG renderer 的 node-local clamp 後量測)。
function portEdgeDistance(port, node, PORT_W) {
  const side = port.properties && port.properties['port.side'];
  let mx = port.x + PORT_W / 2;
  let my = port.y + PORT_W / 2;
  if (side === 'NORTH') my = Math.max(my, 0);
  else if (side === 'SOUTH') my = Math.min(my, node.height);
  else if (side === 'WEST') mx = Math.max(mx, 0);
  else if (side === 'EAST') mx = Math.min(mx, node.width);
  if (side === 'NORTH') return my;
  if (side === 'SOUTH') return node.height - my;
  if (side === 'WEST') return mx;
  if (side === 'EAST') return node.width - mx;
  return Math.min(mx, node.width - mx, my, node.height - my); // side 未知 → 取最近邊
}

async function layoutDemo(demo) {
  const window = loadWindow();
  window.resetSchematicTelemetry();
  const graph = window.buildElkGraph('Arduino', demo.wiring, [], demo.nets);
  const PORT_W = window.PORT_W || 6;
  const res = await new ELK().layout(graph);
  return { window, res, PORT_W };
}

// ── demo fixtures（auto_waterer:控制端 + 繼電器隔離負載端）──────────────
const DEMOS = {
  auto_waterer: {
    wiring: {
      Pump: { pins: [
        { comp: 'GND', mcu: 'GND', comp_dir: 'gnd' },
        { comp: 'VCC', mcu: 'Relay.NO', comp_dir: 'power' },
      ] },
      Relay: { refdes: 'K1', pins: [
        { comp: 'VCC', mcu: '5V', comp_dir: 'power' },
        { comp: 'GND', mcu: 'GND', comp_dir: 'gnd' },
        { comp: 'IN', mcu: 'D2', comp_dir: 'digital_in' },
        { comp: 'COM', mcu: 'EXT-PWR', comp_dir: 'other' },
        { comp: 'NO', mcu: 'LOAD+', comp_dir: 'other' },
      ] },
      SoilMoisture: { pins: [
        { comp: 'VCC', mcu: '5V', comp_dir: 'power' },
        { comp: 'GND', mcu: 'GND', comp_dir: 'gnd' },
        { comp: 'AO', mcu: 'A0', comp_dir: 'analog_out' },
      ] },
      BatteryAA: { pins: [
        { comp: 'V+', mcu: 'EXT-PWR', comp_dir: 'power_source', _netRole: 'source' },
        { comp: 'GND', mcu: 'EXT-GND', comp_dir: 'gnd', _netRole: 'source' },
      ] },
    },
    nets: [
      { name: 'EXT-GND', nodes: [
        { ref: 'Pump', pin: 'GND', side: 'comp' },
        { ref: 'BatteryAA', pin: 'GND', side: 'source' },
      ] },
      { name: 'EXT-PWR', nodes: [] },
      { name: 'LOAD+', nodes: [] },
    ],
  },
};

module.exports = { loadWindow, layoutDemo, portEdgeDistance, ON_EDGE_TOL_PX, DEMOS };
