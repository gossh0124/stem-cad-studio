// viewport_controls.test.js — _highlight 語法上色 + VIEW_PRESETS 資料驗證（node:test）
// 執行：node --test tests/viewport_controls.test.js
// viewport-controls.js 含 JSX（Node 無法解析），故用 vm + 源碼預處理提取純函數。
const { test } = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const src = fs.readFileSync(
  path.join(__dirname, '..', 'v6', 'engineer', 'viewport-controls.js'), 'utf-8');

const patched = src
  .replace(/function ViewCube\([^)]*\)\s*\{[\s\S]*?\n  \}/, 'function ViewCube() {}')
  .replace(/function ViewControls\([^)]*\)\s*\{[\s\S]*?\n  \}/, 'function ViewControls() {}');

const sandbox = { window: {}, console };
vm.createContext(sandbox);
vm.runInContext(patched, sandbox);

const _highlight = sandbox.window._highlight;
const VIEW_PRESETS = sandbox.window.VIEW_PRESETS;

// ── VIEW_PRESETS 資料驗證 ──

test('VIEW_PRESETS 匯出且為陣列', () => {
  assert.ok(Array.isArray(VIEW_PRESETS), 'VIEW_PRESETS 未匯出');
  assert.ok(VIEW_PRESETS.length >= 6, `只有 ${VIEW_PRESETS.length} 個 preset`);
});

test('每個 preset 有 id/label/ry/rx', () => {
  for (const p of VIEW_PRESETS) {
    assert.ok(p.id, 'preset missing id');
    assert.ok(p.label, `${p.id} missing label`);
    assert.equal(typeof p.ry, 'number', `${p.id} ry not number`);
    assert.equal(typeof p.rx, 'number', `${p.id} rx not number`);
  }
});

test('六面 id 都存在：front/back/left/right/top/bottom', () => {
  const ids = new Set(VIEW_PRESETS.map(p => p.id));
  for (const face of ['front', 'back', 'left', 'right', 'top', 'bottom']) {
    assert.ok(ids.has(face), `missing preset '${face}'`);
  }
});

// ── _highlight 語法上色 ──

test('_highlight 匯出且為函式', () => {
  assert.equal(typeof _highlight, 'function');
});

test('Python 關鍵字上色', () => {
  const html = _highlight('import os', 'python');
  assert.ok(html.includes('<span'), 'import 未上色');
  assert.ok(html.includes('import'), '關鍵字文字不見');
});

test('Python 字串上色', () => {
  const html = _highlight('x = "hello"', 'python');
  assert.ok(html.includes('<span'), '字串未上色');
});

test('Python 註解上色', () => {
  const html = _highlight('x = 1  # comment', 'python');
  assert.ok(html.includes('font-style:italic'), '註解未斜體');
});

test('C++ 關鍵字上色', () => {
  const html = _highlight('void setup() {', 'cpp');
  assert.ok(html.includes('<span'), 'void 未上色');
  assert.ok(html.includes('setup'), 'setup 文字不見');
});

test('C++ 註解上色', () => {
  const html = _highlight('int x; // comment', 'cpp');
  assert.ok(html.includes('font-style:italic'), '註解未斜體');
});

test('HTML 實體跳脫', () => {
  const html = _highlight('x < 3 && y > 0', 'python');
  assert.ok(!html.includes(' < '), '< 未跳脫');
  assert.ok(html.includes('&lt;'), '缺 &lt;');
  assert.ok(html.includes('&gt;'), '缺 &gt;');
  assert.ok(html.includes('&amp;'), '缺 &amp;');
});

test('空字串不爆', () => {
  assert.equal(_highlight('', 'python'), '');
  assert.equal(_highlight('', 'cpp'), '');
});
