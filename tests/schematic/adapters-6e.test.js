// tests/schematic/adapters-6e.test.js — #28/#29 DEC-H8 前端資料契約 gate。
// 後端 Phase 3 把 isolation / 電源功率預算的機器 verdict 化為 engineering_decisions
// (帶 stem_concept,6E『Evaluate』教材);前端 views-explain.jsx:133 渲染 `STEM: {d.stem_concept}`。
// 中間經 window.Adapters.toEngineeringDecisions 轉形。本 gate 在 node 載入 adapters.jsx(browser
// IIFE,同 _harness.js 模式)斷言該轉形**保留 stem_concept / phase / category / description** ——
// 鎖住後端教材到視圖的資料契約(機器取代「F5 目視 Explain 視圖有沒有顯示 STEM」,DEC-H1)。
'use strict';
const assert = require('node:assert');
const { test } = require('node:test');
const fs = require('fs');
const path = require('path');

function loadAdapters() {
  const window = {};
  const src = fs.readFileSync(
    path.join(__dirname, '..', '..', 'v6', 'adapters.jsx'), 'utf8');
  // adapters.jsx 為 browser IIFE,設 window.Adapters;載入時不呼叫函式(僅定義)。
  // 安全:src 為 repo 自有源碼檔(硬編路徑,**無變數插值**進 function body),整體作為 body
  // 傳入 —— 同 tests/schematic/_harness.js 既有模式,非 code-injection 面(無 attacker-controlled
  // 輸入進 body)。browser IIFE 須此法 headless 載入。
  new Function('window', 'console', src)(window, console); // eslint-disable-line no-new-func
  return window.Adapters;
}

test('toEngineeringDecisions 保留 isolation 6E 教材的 stem_concept/phase/category/description', () => {
  const A = loadAdapters();
  assert.ok(A && typeof A.toEngineeringDecisions === 'function',
    'window.Adapters.toEngineeringDecisions 應存在');
  const out = A.toEngineeringDecisions([{
    phase: 'III', '6e_stage': 'evaluate', category: 'galvanic_isolation',
    description: '✅ 電氣隔離通過：控制地與負載地經繼電器乾接點分離 … V = L·di/dt 被侷限在負載迴路。',
    stem_concept: '電氣隔離 (galvanic isolation)：控制地與負載地分離',
  }]);
  assert.strictEqual(out.length, 1);
  assert.strictEqual(out[0].phase, 'III', 'phase 應為 III(前端徽章 PIII,非 Pevaluate)');
  assert.strictEqual(out[0].category, 'galvanic_isolation');
  assert.strictEqual(out[0].stem_concept, '電氣隔離 (galvanic isolation)：控制地與負載地分離',
    '6E stem_concept 須原樣存活到視圖形狀(views-explain:133 渲染)');
  assert.ok(out[0].description.includes('di/dt'), 'description 物理原理須保留');
});

test('toEngineeringDecisions fallback：6e_stage→phase、concept/principle→stem_concept', () => {
  const A = loadAdapters();
  // 無 phase 時退回 6e_stage;無 stem_concept 時退回 concept(防後端欄名變動靜默丟失 STEM)。
  const out = A.toEngineeringDecisions([
    { '6e_stage': 'evaluate', concept: '電源功率預算' },
    { phase: 'IV', principle: 'X' },
  ]);
  assert.strictEqual(out[0].phase, 'evaluate');
  assert.strictEqual(out[0].stem_concept, '電源功率預算');
  assert.strictEqual(out[1].stem_concept, 'X');
});

test('toEngineeringDecisions 空輸入不炸、缺欄位給空字串(不 undefined 滲漏到 UI)', () => {
  const A = loadAdapters();
  assert.deepStrictEqual(A.toEngineeringDecisions([]), []);
  const out = A.toEngineeringDecisions([{}]);
  assert.strictEqual(out[0].stem_concept, '');
  assert.strictEqual(out[0].description, '');
});
