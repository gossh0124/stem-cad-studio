// ═══════════════════════════════════════════
// schematic-fidelity.js — VS schematic 接線保真（對稱 render-fidelity.js）
//
// 問題：elk-layout.js 在 comp pin → MCU pin 不在白名單時靜默 continue（該接線
// 未繪），只留一個沒人看的 console.warn → 「角位未接線」無從偵測。
//
// 解法：drop 時呼叫 recordSchematicDrop() 收集到 window.__SCHEMATIC_TELEMETRY；
// computeSchematicFidelity() 算 verdict——任何 dropped wire → FAIL，讓「角位
// 未接線」變成可讀信號。
//
// UMD：瀏覽器掛 window.*，Node 可 require 做純函數單測。
// ═══════════════════════════════════════════
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') {
    window.recordSchematicDrop = api.recordSchematicDrop;
    window.recordSchematicRoute = api.recordSchematicRoute;
    window.resetSchematicTelemetry = api.resetSchematicTelemetry;
    window.computeSchematicFidelity = api.computeSchematicFidelity;
    window.verifySchematicFidelity = function () {
      return api.computeSchematicFidelity(window.__SCHEMATIC_TELEMETRY);
    };
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function emptyTelemetry() {
    return { dropped: [], routed: 0 };
  }

  function resetSchematicTelemetry() {
    const t = emptyTelemetry();
    if (typeof window !== 'undefined') window.__SCHEMATIC_TELEMETRY = t;
    return t;
  }

  // elk-layout 在某 pin 不在 MCU 白名單而棄繪時呼叫
  function recordSchematicDrop(comp, pin, mcu) {
    if (typeof window === 'undefined') return;
    const t = window.__SCHEMATIC_TELEMETRY || (window.__SCHEMATIC_TELEMETRY = emptyTelemetry());
    t.dropped.push({ comp: comp, pin: pin, mcu: mcu });
  }

  // 成功繪出一條接線時呼叫
  function recordSchematicRoute() {
    if (typeof window === 'undefined') return;
    const t = window.__SCHEMATIC_TELEMETRY || (window.__SCHEMATIC_TELEMETRY = emptyTelemetry());
    t.routed += 1;
  }

  // PASS：零棄繪；FAIL：任何 comp pin 未繪（角位未接線）
  function computeSchematicFidelity(telemetry) {
    const t = telemetry || emptyTelemetry();
    const dropped = t.dropped || [];
    return {
      verdict: dropped.length === 0 ? 'PASS' : 'FAIL',
      n_dropped: dropped.length,
      n_routed: t.routed || 0,
      dropped: dropped.slice(0, 12),
    };
  }

  return {
    emptyTelemetry: emptyTelemetry,
    resetSchematicTelemetry: resetSchematicTelemetry,
    recordSchematicDrop: recordSchematicDrop,
    recordSchematicRoute: recordSchematicRoute,
    computeSchematicFidelity: computeSchematicFidelity,
  };
});
