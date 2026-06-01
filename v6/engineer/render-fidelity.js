// ═══════════════════════════════════════════
// render-fidelity.js — VS-FE 前端渲染保真 verdict（Verification Spine 橫向層）
//
// 問題：scene-3d.js 三層 fallback（GLB→STL→box / mesh→procedural→ghost）
// 在資料對不上時靜默降級成方塊，使用者看到方塊以為是模型，截圖驗證測不到。
//
// 解法：渲染端用 recordRender() 記錄每個物件的「渲染來源」到 window.__RENDER_TELEMETRY；
// computeRenderFidelity() 把 telemetry 算成 verdict——任何 ghost/box 降級或
// procedural error 都讓 verdict ≠ PASS，讓「畫面有方塊」變成可讀的失敗信號。
//
// UMD：瀏覽器掛 window.*，Node 可 require 做純函數單測。
// ═══════════════════════════════════════════
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') {
    window.computeRenderFidelity = api.computeRenderFidelity;
    window.recordRender = api.recordRender;
    window.resetRenderTelemetry = api.resetRenderTelemetry;
    window.verifyRenderFidelity = function () {
      return api.computeRenderFidelity(window.__RENDER_TELEMETRY);
    };
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // 正常來源（真實幾何或程序化幾何）vs 降級來源（占位方塊）
  const GOOD_MESH = new Set(['mesh', 'glb', 'stl']);
  const DEGRADED = new Set(['ghost', 'box', 'fallback']);

  function emptyTelemetry() {
    return { ports: [], pcbBody: null, errors: [], colors: [] };
  }

  // 渲染端呼叫：記錄一筆來源。kind = 'port' | 'pcbBody' | 'error'
  // meta.color (optional): hex string e.g. '#ff0000' for color diversity tracking
  function recordRender(kind, source, meta) {
    if (typeof window === 'undefined') return;
    const t = window.__RENDER_TELEMETRY || (window.__RENDER_TELEMETRY = emptyTelemetry());
    if (kind === 'pcbBody') {
      t.pcbBody = source;
    } else if (kind === 'error') {
      t.errors.push(Object.assign({ source: source }, meta || {}));
    } else {
      t.ports.push(Object.assign({ source: source }, meta || {}));
    }
    if (meta && meta.color) t.colors.push(meta.color);
  }

  function resetRenderTelemetry() {
    const t = emptyTelemetry();
    if (typeof window !== 'undefined') window.__RENDER_TELEMETRY = t;
    return t;
  }

  // 把 telemetry 算成 verdict（純函數，可單測）。
  // PASS  : 有渲染且全部正常來源、零 error、pcbBody 非降級
  // FAIL  : 任何 ghost/box 降級 或 procedural error
  // EMPTY : 完全沒有渲染任何東西（畫面空 → 視為失敗級）
  function computeRenderFidelity(telemetry) {
    const t = telemetry || emptyTelemetry();
    const ports = t.ports || [];
    const errors = t.errors || [];
    const counts = { mesh: 0, procedural: 0, ghost: 0, other: 0 };

    for (const p of ports) {
      const s = p && p.source;
      if (GOOD_MESH.has(s)) counts.mesh++;
      else if (s === 'procedural') counts.procedural++;
      else if (DEGRADED.has(s)) counts.ghost++;
      else counts.other++;
    }

    const pcbDegraded = t.pcbBody != null && DEGRADED.has(t.pcbBody);
    const nDegraded = counts.ghost + counts.other + (pcbDegraded ? 1 : 0);
    const nError = errors.length;

    let verdict;
    if (ports.length === 0 && t.pcbBody == null) {
      verdict = 'EMPTY';
    } else if (nError > 0 || nDegraded > 0) {
      verdict = 'FAIL';
    } else {
      verdict = 'PASS';
    }

    const uniqueColors = new Set(t.colors || []).size;

    return {
      verdict: verdict,
      total_ports: ports.length,
      counts: counts,
      pcb_body: t.pcbBody,
      pcb_degraded: pcbDegraded,
      n_degraded: nDegraded,
      n_error: nError,
      errors: errors.slice(0, 10),
      color_diversity: uniqueColors,
    };
  }

  return {
    computeRenderFidelity: computeRenderFidelity,
    recordRender: recordRender,
    resetRenderTelemetry: resetRenderTelemetry,
    emptyTelemetry: emptyTelemetry,
    GOOD_MESH: GOOD_MESH,
    DEGRADED: DEGRADED,
  };
});
