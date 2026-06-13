// datasheet-derive.js — 從 verified.json datasheet 衍生前端 dims/ports
// SSOT: data/component_datasheet_verified.json（後端透過 /api/v1/datasheet 提供）
// 對應後端腳本：scripts/derive_component_dimensions.py（兩邊邏輯必須一致）
(() => {
  // VS-DEDUP（鏡像 scripts/derive_component_dimensions.py）：判 stale extra_ports。
  // datasheet on_board_components 永遠勝;防 stale extra_ports 以舊手設座標蓋過 datasheet bbox。
  const _SOLID_BODY_SHAPES = new Set([
    'ic-soic', 'ic-qfp', 'ic-dip', 'ic-module',
    'box', 'heatsink', 'vreg-to220', 'display-panel',
    'toggle-switch', 'slide-switch',
    'crystal-hc49', 'res-smd', 'cap-electrolytic',
  ]);
  function _isSolidShape(shape) {
    return _SOLID_BODY_SHAPES.has(shape);
  }
  function _normLabel(s) {
    return String(s == null ? '' : s)
      .trim().toLowerCase()
      .replace(/_/g, ' ').replace(/-/g, ' ').replace(/\//g, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  function deriveDimsFromDatasheet(ds) {
    if (!ds || !ds.physical) return null;
    const ui = ds._ui_hints || {};  // nofallback-ok: _ui_hints 是 optional UI 區塊，缺席時所有 ui.* 均走空，不影響幾何計算
    const shapeMap = ui.frontend_shape || {};  // nofallback-ok: frontend_shape 缺席時 shapeMap[*] 均 undefined，L12 continue 安全略過
    const ports = [];
    for (const sub of (ds.on_board_components || [])) {
      const info = shapeMap[sub.label];
      if (!info) continue;
      const cx = sub.x_mm + sub.w_mm / 2;
      const cy = sub.y_mm + sub.h_mm / 2;
      const params = { bodyW: sub.w_mm, bodyD: sub.h_mm, ...(info.extra_params || {}) };  // nofallback-ok: extra_params 是可選 shape 修飾，非幾何必填
      ports.push({
        side: info.side || 'face', cx, cy,
        shape: info.shape, label: sub.label, color: info.color, params,
      });
    }
    // VS-DEDUP：on_board_components 衍生的 port（帶 cx/cy）為權威；stale extra_ports 跳過。
    const obcRendered = ports.slice();
    function _isStaleExtra(extra) {
      const ne = _normLabel(extra.label);
      const te = new Set(ne.split(' ').filter(t => t.length >= 2));
      const ex = extra.cx, ey = extra.cy;
      const eSolid = _isSolidShape(extra.shape || '');
      for (const p of obcRendered) {
        const npp = _normLabel(p.label);
        if (ne === npp) return true;
        if (ne.length >= 8 && npp.length >= 8 && (ne.startsWith(npp) || npp.startsWith(ne))) return true;
        const tp = new Set(npp.split(' ').filter(t => t.length >= 2));
        if (te.size && tp.size) {
          const teSubP = [...te].every(t => tp.has(t));
          const tpSubE = [...tp].every(t => te.has(t));
          if (teSubP || tpSubE) return true;
        }
        if (eSolid && _isSolidShape(p.shape || '') &&
            ex != null && ey != null &&
            Math.abs(ex - p.cx) <= 1.5 && Math.abs(ey - p.cy) <= 1.5) return true;
      }
      return false;
    }
    for (const extra of (ui.extra_ports || [])) {
      if (_isStaleExtra(extra)) continue;
      ports.push({
        side: extra.side, cx: extra.cx, cy: extra.cy,
        shape: extra.shape, label: extra.label, color: extra.color,
        params: extra.extra_params || {},  // nofallback-ok: extra_params 是 extra_ports 的可選 shape 修飾，非幾何必填，空物件安全
      });
    }
    // P5.8: 從 pin_layout.header_groups 衍生 ports（opt-in via _ui_hints.derive_from_pin_layout）
    if (ui.derive_from_pin_layout) {
      const existing = new Set(ports.map(p => p.label));
      for (const hg of (ds.pin_layout?.header_groups || [])) {
        const name = hg.name || '';
        if (!name || existing.has(name)) continue;
        const pins = hg.pins || [];
        if (!pins.length) continue;
        const cx = pins.reduce((s, p) => s + (p.x_mm || 0), 0) / pins.length;
        const cy = pins.reduce((s, p) => s + (p.y_mm || 0), 0) / pins.length;
        const info = shapeMap[name] || {};  // nofallback-ok: shapeMap[name] 缺席僅影響 shape/side/color UI 預設，幾何由 pin 座標推導
        // pitch：明示 pitch_mm 優先；否則從真實 pin 座標推導（SSOT，不以 2.54 頂替）
        let pitch = hg.pitch_mm;
        if (pitch === undefined || pitch === null) {
          const xs = pins.map(p => p.x_mm || 0), ys = pins.map(p => p.y_mm || 0);
          const span = Math.max(Math.max(...xs) - Math.min(...xs),
                                Math.max(...ys) - Math.min(...ys));
          if (pins.length < 2 || span <= 0) {
            throw new Error(`deriveDims: header '${name}' 缺 pitch_mm 且 pin 座標不足以推導 pitch（拒絕以 2.54 頂替）`);
          }
          pitch = Math.round((span / (pins.length - 1)) * 1000) / 1000;
        }
        const params = {
          pins: hg.pin_count ?? pins.length,
          pitch,
          rows: hg.rows ?? 1,  // nofallback-ok: 單排 header 的電氣正確預設值，缺席時回 1 不遮蓋幾何錯誤
          ...(info.extra_params || {}),  // nofallback-ok: extra_params 是可選 shape 修飾（shapeMap 缺席時 info={} 已在 L38 標注）
        };
        ports.push({
          side: info.side || hg.side || 'face',
          cx: Math.round(cx * 1000) / 1000,
          cy: Math.round(cy * 1000) / 1000,
          shape: info.shape || 'conn-header-male',
          label: name,
          color: info.color || '#c9b037',  // nofallback-ok: '#c9b037' 是 connector header UI 裝飾色，純視覺預設
          params,
        });
      }
    }
    return {
      l: ds.physical.length_mm,
      w: ds.physical.width_mm,
      h: ds.physical.height_mm,
      ports,
    };
  }

  window.deriveDimsFromDatasheet = deriveDimsFromDatasheet;
})();
