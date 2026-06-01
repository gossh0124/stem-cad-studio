// schematic_fidelity.test.js — VS schematic 接線保真 verdict 純函數單測（node:test）
// 執行：node --test tests/schematic_fidelity.test.js
const { test } = require('node:test');
const assert = require('node:assert');
const { computeSchematicFidelity } = require('../v6/schematic/schematic-fidelity.js');

test('零棄繪 → PASS', () => {
  const r = computeSchematicFidelity({ dropped: [], routed: 12 });
  assert.equal(r.verdict, 'PASS');
  assert.equal(r.n_routed, 12);
});

test('任何棄繪 → FAIL（角位未接線）', () => {
  const r = computeSchematicFidelity({
    dropped: [{ comp: 'OLED', pin: 'SDA', mcu: 'A4' }], routed: 5,
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.n_dropped, 1);
});

test('多筆棄繪計數', () => {
  const r = computeSchematicFidelity({
    dropped: [{ comp: 'A', pin: 'X', mcu: 'D99' }, { comp: 'B', pin: 'Y', mcu: 'D88' }],
    routed: 3,
  });
  assert.equal(r.verdict, 'FAIL');
  assert.equal(r.n_dropped, 2);
});

test('空輸入不爆 → PASS', () => {
  assert.equal(computeSchematicFidelity().verdict, 'PASS');
  assert.equal(computeSchematicFidelity(null).verdict, 'PASS');
});
