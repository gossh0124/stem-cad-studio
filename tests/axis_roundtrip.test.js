// axis_roundtrip.test.js — VS-AXIS: PCB↔Three.js 座標往返一致性（node:test，無需額外套件）
// 執行：node --test tests/axis_roundtrip.test.js
// scene-3d.js 是 IIFE（assign window），故先設 global.window 再 require 取 __axisTransform。
const { test } = require('node:test');
const assert = require('node:assert');

global.window = global.window || {};
require('../v6/engineer/scene-3d.js');
const AX = global.window.__axisTransform;

const L = 68.6, W = 53.4, SC = (2.0 / 68.6) * 0.9;  // Arduino-Uno 範例

test('__axisTransform 已 export 四函式', () => {
  assert.ok(AX, '__axisTransform 未匯出');
  for (const fn of ['pcbToScene', 'sceneToPcb', 'zUpToYUp', 'yUpToZUp']) {
    assert.equal(typeof AX[fn], 'function', `${fn} 缺失`);
  }
});

test('pcbToScene → sceneToPcb 往返 = 原值', () => {
  for (const [cx, cy] of [[0, 0], [10, 20], [68.6, 53.4], [34.3, 26.7], [1.53, 38.1]]) {
    const s = AX.pcbToScene(cx, cy, L, W, SC);
    const back = AX.sceneToPcb(s.x, s.z, L, W, SC);
    assert.ok(Math.abs(back.cx - cx) < 1e-9, `cx ${back.cx} != ${cx}`);
    assert.ok(Math.abs(back.cy - cy) < 1e-9, `cy ${back.cy} != ${cy}`);
  }
});

test('PCB 板中心 → scene 原點', () => {
  const s = AX.pcbToScene(L / 2, W / 2, L, W, SC);
  assert.ok(Math.abs(s.x) < 1e-9 && Math.abs(s.z) < 1e-9, `中心應 →(0,0)，得 (${s.x},${s.z})`);
});

test('軸向慣例：cx 增→scene.x 增；cy 增→scene.z 減（Y 翻轉）', () => {
  const a = AX.pcbToScene(10, 10, L, W, SC);
  const b = AX.pcbToScene(20, 10, L, W, SC);  // cx +10
  const c = AX.pcbToScene(10, 20, L, W, SC);  // cy +10
  assert.ok(b.x > a.x, 'cx 增 → scene.x 應增');
  assert.equal(a.z, b.z);                     // cx 不影響 z
  assert.ok(c.z < a.z, 'cy 增 → scene.z 應減（Y-up 翻轉）');
  assert.equal(a.x, c.x);                     // cy 不影響 x
});

test('zUpToYUp → yUpToZUp 往返 = 原值', () => {
  for (const [x, y, z] of [[1, 2, 3], [-5, 0, 7], [0, 0, 0]]) {
    const u = AX.zUpToYUp(x, y, z);
    const back = AX.yUpToZUp(u.x, u.y, u.z);
    assert.deepEqual(back, { x, y, z });
  }
});

test('zUpToYUp 軸向：(x,y,z)→(x, z, -y)', () => {
  assert.deepEqual(AX.zUpToYUp(1, 2, 3), { x: 1, y: 3, z: -2 });
});
