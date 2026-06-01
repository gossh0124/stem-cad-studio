// render_fidelity.test.js — VS-FE verdict 純函數單測（node:test，無需額外套件）
// 執行：node --test tests/render_fidelity.test.js
const { test } = require('node:test');
const assert = require('node:assert');
const { computeRenderFidelity } = require('../v6/engineer/render-fidelity.js');

test('全 mesh + pcbBody glb/stl → PASS', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }, { source: 'mesh' }],
    pcbBody: 'glb', errors: [],
  });
  assert.equal(r.verdict, 'PASS');
  assert.equal(r.counts.mesh, 2);
  assert.equal(r.n_degraded, 0);
});

test('procedural 也算正常 → PASS', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'procedural' }, { source: 'mesh' }],
    pcbBody: 'stl', errors: [],
  });
  assert.equal(r.verdict, 'PASS');
  assert.equal(r.counts.procedural, 1);
});

test('任一 port ghost → FAIL', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }, { source: 'ghost', shape: 'header' }],
    pcbBody: 'stl', errors: [],
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.counts.ghost, 1);
  assert.equal(r.n_degraded, 1);
});

test('pcbBody 退回 box → FAIL（即使 port 正常）', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'procedural' }],
    pcbBody: 'box', errors: [],
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.pcb_degraded, true);
});

test('procedural error → FAIL', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'ghost' }],
    pcbBody: 'box',
    errors: [{ source: 'procedural', shape: 'usb', error: 'builder threw' }],
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.n_error, 1);
});

test('完全沒渲染 → EMPTY', () => {
  const r = computeRenderFidelity({ ports: [], pcbBody: null, errors: [] });
  assert.equal(r.verdict, 'EMPTY');
});

test('未知來源視為降級 → FAIL', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'wat' }], pcbBody: 'stl', errors: [],
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.counts.other, 1);
});

test('空輸入不爆 → EMPTY', () => {
  assert.equal(computeRenderFidelity().verdict, 'EMPTY');
  assert.equal(computeRenderFidelity(null).verdict, 'EMPTY');
});

// ── color_diversity 追蹤（RF3 gate）──

test('colors 陣列計入 color_diversity', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }, { source: 'mesh' }],
    pcbBody: 'glb', errors: [],
    colors: ['#ff0000', '#00ff00', '#0000ff'],
  });
  assert.equal(r.verdict, 'PASS');
  assert.equal(r.color_diversity, 3);
});

test('重複色只算一次', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }],
    pcbBody: 'stl', errors: [],
    colors: ['#ff0000', '#ff0000', '#ff0000'],
  });
  assert.equal(r.color_diversity, 1);
});

test('colors 為空 → color_diversity = 0', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }], pcbBody: 'glb', errors: [], colors: [],
  });
  assert.equal(r.color_diversity, 0);
});

test('colors 未提供 → color_diversity = 0', () => {
  const r = computeRenderFidelity({
    ports: [{ source: 'mesh' }], pcbBody: 'glb', errors: [],
  });
  assert.equal(r.color_diversity, 0);
});

// ── emptyTelemetry / resetRenderTelemetry ──

const { emptyTelemetry, resetRenderTelemetry, GOOD_MESH, DEGRADED } =
  require('../v6/engineer/render-fidelity.js');

test('emptyTelemetry 結構含 colors 陣列', () => {
  const t = emptyTelemetry();
  assert.deepEqual(t, { ports: [], pcbBody: null, errors: [], colors: [] });
});

test('resetRenderTelemetry 回傳空結構', () => {
  const t = resetRenderTelemetry();
  assert.ok(Array.isArray(t.ports));
  assert.ok(Array.isArray(t.colors));
  assert.equal(t.pcbBody, null);
});

test('GOOD_MESH 含 mesh/glb/stl', () => {
  for (const s of ['mesh', 'glb', 'stl']) {
    assert.ok(GOOD_MESH.has(s), `GOOD_MESH missing '${s}'`);
  }
});

test('DEGRADED 含 ghost/box/fallback', () => {
  for (const s of ['ghost', 'box', 'fallback']) {
    assert.ok(DEGRADED.has(s), `DEGRADED missing '${s}'`);
  }
});
