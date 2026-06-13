// tests/schematic/footprint-flip.test.js — P0.5 #8 修正驗證:非 MCU 2D footprint 垂直翻正。
//
// 背景(經 3-lens 對抗式驗證):COMPONENT_DIMENSIONS 的 cx/cy 原點為 PCB 左下角(y-up,見
// verified.json _meta.coordinate_origin)。SVG 為 y-down。修正前 _genericPortDecor.sy 不翻
// → 非 MCU 元件 footprint 相對 datasheet/3D 上下鏡像。修正:_compDecor 傳 flipY=true 翻正,
// _realProjection(MCU base)維持不翻(翻正歸其外層 matrix,避免 double-flip)。
//
// 本檔 headless 載入 port-resolver.js(mock React 錄製 createElement),斷言:
//   A. 合成單 port class:_realProjection 用無翻公式、_compDecor 用翻轉公式(精確、定方向)。
//   B. 真實非 MCU 多 port class:_compDecor 為 _realProjection 的「箱內垂直反射」(y 和=2Y+H)
//      且非退化(若 flip 被移除則兩者全等 → fail,mirror mutant 守門)。
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const X = 100, Y = 200, W = 60, H = 40;
const MCU_CLASSES = /Arduino|ESP32|Micro.?bit|Nano|Raspberry|RPi|Pico|STM32|Teensy/i;

// 載入 component-dimensions.js + port-resolver.js;port-resolver 用全域 React + window.PORT_W。
function loadFootprintEnv() {
  const window = { PORT_W: 6, COMPKEY_TO_CLASS: {} };
  // mock React:createElement 錄成樸素節點 {tag, props, children}(new Function 內 bare React → global)。
  global.React = { createElement: (tag, props, ...children) => ({ tag, props: props || {}, children }) };
  const c = { warn() {}, error() {}, info() {}, log() {} };
  for (const f of ['v6/data/component-dimensions.js', 'v6/schematic/port-resolver.js']) {
    // 安全說明:f 為硬編白名單的 repo 自有 v6 源碼檔(無插值/無外部輸入);src 作為 Function body
    // 整體傳入(非字串串接),window/console 以參數注入。v6 為 browser IIFE 模組,須此法 headless
    // 載入(同 tests/schematic/_harness.js)。非 code-injection 面(無 attacker-controlled 變數進 body)。
    const src = fs.readFileSync(path.join(ROOT, f), 'utf8');
    new Function('window', 'console', src)(window, c); // eslint-disable-line no-new-func
  }
  return window;
}

// 攤平 + 取每個 circle/rect 的 (xc, yc) 中心(_genericPortDecor 每 port 出 1-2 個 primitive)。
function shapeCenters(els) {
  const out = [];
  const walk = (node) => {
    if (Array.isArray(node)) { node.forEach(walk); return; }
    if (!node || typeof node !== 'object' || !node.props) return;
    const p = node.props;
    if (node.tag === 'circle' && typeof p.cx === 'number' && typeof p.cy === 'number') {
      out.push({ xc: p.cx, yc: p.cy });
    } else if (node.tag === 'rect' && typeof p.x === 'number' && typeof p.y === 'number') {
      out.push({ xc: p.x + (p.width || 0) / 2, yc: p.y + (p.height || 0) / 2 });
    }
    if (node.children) node.children.forEach(walk);
  };
  walk(els);
  return out;
}

test('A. 合成單 port:_realProjection 不翻、_compDecor 翻正(精確,定方向)', () => {
  const window = loadFootprintEnv();
  // 注入單一 box port(box → 單 rect 正中於 (px,py),無 body 偏移雜訊)。cy=8 偏向板「上方」(y-up)。
  window.COMPONENT_DIMENSIONS.__TEST_FLIP__ = {
    l: 10, w: 10, h: 3,
    ports: [{ side: 'face', cx: 5, cy: 8, shape: 'box', label: 'P', color: '#abcabc',
      params: { bodyW: 2, bodyD: 2 } }],
  };
  const plain = shapeCenters(window._realProjection('__TEST_FLIP__', X, Y, W, H));
  const flipped = shapeCenters(window._compDecor('__TEST_FLIP__', X, Y, W, H, '#888'));
  assert.strictEqual(plain.length, 1, 'box 應只出 1 個 rect');
  assert.strictEqual(flipped.length, 1);
  // 無翻基準:py = Y + (cy/Wmm)*H = 200 + 0.8*40 = 232(cy 大 → py 大,SVG 下方)。
  assert.ok(Math.abs(plain[0].yc - (Y + 0.8 * H)) < 1e-6, `_realProjection 無翻 py 應=${Y + 0.8 * H}, got ${plain[0].yc}`);
  // 翻正:py = Y + H - (cy/Wmm)*H = 200 + 40 - 32 = 208(cy 大=datasheet 頂部 → py 小,SVG 上方)。
  assert.ok(Math.abs(flipped[0].yc - (Y + H - 0.8 * H)) < 1e-6, `_compDecor 翻正 py 應=${Y + H - 0.8 * H}, got ${flipped[0].yc}`);
  // x 不受翻轉影響。
  assert.ok(Math.abs(flipped[0].xc - plain[0].xc) < 1e-6, 'x 中心不應因翻轉改變');
});

test('B. 真實非 MCU 多 port:_compDecor 對 _realProjection 為垂直翻轉(y 強負相關)且非退化', () => {
  const window = loadFootprintEnv();
  const dims = window.COMPONENT_DIMENSIONS;
  assert.ok(dims && Object.keys(dims).length, 'COMPONENT_DIMENSIONS 未載入');

  // 找一個非 MCU、≥2 distinct cy 的多 port class(真實生產資料)。
  let chosen = null;
  for (const cls of Object.keys(dims)) {
    if (MCU_CLASSES.test(cls)) continue;
    const d = dims[cls];
    if (!d || !Array.isArray(d.ports) || !d.l || !d.w) continue;
    const cys = new Set(d.ports.filter((p) => p.cy != null).map((p) => p.cy));
    if (cys.size >= 2) { chosen = cls; break; }
  }
  assert.ok(chosen, '找不到可測的非 MCU 多 port class');

  const flipped = shapeCenters(window._compDecor(chosen, X, Y, W, H, '#888'));
  const plain = shapeCenters(window._realProjection(chosen, X, Y, W, H));
  assert.ok(flipped.length >= 2, `_compDecor 應出 ≥2 primitive (class=${chosen}, got ${flipped.length})`);
  assert.strictEqual(flipped.length, plain.length, '翻轉前後 primitive 數應相同(結構僅 y 值不同)');

  // x 不受翻轉影響;非退化守門(移除 flip → flipped===plain → 無相異 → fail)。
  let sawDistinct = false;
  for (let i = 0; i < flipped.length; i++) {
    assert.ok(Math.abs(flipped[i].xc - plain[i].xc) < 1e-6, `x 中心不應變 (i=${i}, class=${chosen})`);
    if (Math.abs(flipped[i].yc - plain[i].yc) > 1e-6) sawDistinct = true;
  }
  assert.ok(sawDistinct, `翻轉退化(_compDecor 與 _realProjection y 全等 → flip 未生效, class=${chosen})`);

  // 垂直翻轉 = plain.yc 與 flipped.yc 強負相關(純中心反射=-1;ic dimple 等子 primitive 偏移
  // 對兩者同向位移,仍保強負相關)。Pearson r:no-flip mutant 給 +1,翻轉給 ≈-1。
  const py = plain.map((s) => s.yc), fy = flipped.map((s) => s.yc);
  const mean = (a) => a.reduce((s, v) => s + v, 0) / a.length;
  const mp = mean(py), mf = mean(fy);
  let num = 0, dp = 0, df = 0;
  for (let i = 0; i < py.length; i++) {
    num += (py[i] - mp) * (fy[i] - mf);
    dp += (py[i] - mp) ** 2;
    df += (fy[i] - mf) ** 2;
  }
  assert.ok(dp > 0 && df > 0, 'y 中心無變異(class 選取失準?)');
  const r = num / Math.sqrt(dp * df);
  assert.ok(r < -0.9, `plain/flipped y 應強負相關(垂直翻轉),got r=${r.toFixed(4)} (class=${chosen})`);
});
