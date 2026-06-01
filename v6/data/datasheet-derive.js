// datasheet-derive.js — 從 verified.json datasheet 衍生前端 dims/ports
// SSOT: data/component_datasheet_verified.json（後端透過 /api/v1/datasheet 提供）
// 對應後端腳本：scripts/derive_component_dimensions.py（兩邊邏輯必須一致）
(() => {
  function deriveDimsFromDatasheet(ds) {
    if (!ds || !ds.physical) return null;
    const ui = ds._ui_hints || {};
    const shapeMap = ui.frontend_shape || {};
    const ports = [];
    for (const sub of (ds.on_board_components || [])) {
      const info = shapeMap[sub.label];
      if (!info) continue;
      const cx = sub.x_mm + sub.w_mm / 2;
      const cy = sub.y_mm + sub.h_mm / 2;
      const params = { bodyW: sub.w_mm, bodyD: sub.h_mm, ...(info.extra_params || {}) };
      ports.push({
        side: info.side || 'face', cx, cy,
        shape: info.shape, label: sub.label, color: info.color, params,
      });
    }
    for (const extra of (ui.extra_ports || [])) {
      ports.push({
        side: extra.side, cx: extra.cx, cy: extra.cy,
        shape: extra.shape, label: extra.label, color: extra.color,
        params: extra.extra_params || {},
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
        const info = shapeMap[name] || {};
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
          rows: hg.rows ?? 1,
          ...(info.extra_params || {}),
        };
        ports.push({
          side: info.side || hg.side || 'face',
          cx: Math.round(cx * 1000) / 1000,
          cy: Math.round(cy * 1000) / 1000,
          shape: info.shape || 'conn-header-male',
          label: name,
          color: info.color || '#c9b037',
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
