// ═══════════════════════════════════════════
// schematic-elk.jsx — ELK-based interactive schematic (main React view)
// Depends on: schematic/comp-specs.js, schematic/elk-layout.js, schematic/port-resolver.js
// ═══════════════════════════════════════════

(() => {
  // ── Globals from split modules ──
  const _MCU_PORTS = window.MCU_PORTS;
  const COMP_SPECS = window.COMP_SPECS;
  const WIRE_STYLES = window.WIRE_STYLES;
  const _COMP_DIMS = window.COMP_DIMS;
  const PORT_W = window.PORT_W;
  const _pinClr = window._pinClr;
  const PIN_CLR = window.PIN_CLR;  // SWL5: pin 類型色碼（圖例用）
  const _flowDir = window._flowDir;
  const _compDecor = window._compDecor;
  const buildElkGraph = window.buildElkGraph;
  const _wiringFlatToNested = window._wiringFlatToNested;

  // ── MCU board renderers (PCB datasheet coordinates) ──

  function _mcuDecorShared(node, meta, nodeColor) {
    const x = node.x, y = node.y, w = node.width, h = node.height;
    const e = (tag, props, ...ch) => React.createElement(tag, props, ...ch);
    const els = [];
    els.push(e('rect', { x, y, width: w, height: h, rx: 4, fill: '#0c1a12', stroke: nodeColor, strokeWidth: 2 }));
    els.push(e('rect', { x: x+2, y: y+2, width: w-4, height: h-4, rx: 3, fill: 'none', stroke: nodeColor, strokeWidth: 0.3, opacity: 0.12 }));
    for (let i = 0; i < 3; i++) {
      const ty = y + h*0.3 + i*h*0.15;
      els.push(e('line', { x1: x+12, y1: ty, x2: x+w-12, y2: ty, stroke: nodeColor, strokeWidth: 0.2, opacity: 0.06 }));
    }
    return { x, y, w, h, cx: x+w/2, cy: y+h/2, e, els };
  }

  function _mcuHeaderStrips(node, x, y, w, e, els, nodeColor) {
    const leftPorts = (node.ports || []).filter(p => p.properties?.['port.side'] === 'WEST');
    const rightPorts = (node.ports || []).filter(p => p.properties?.['port.side'] === 'EAST');
    const drawHeaderStrip = (ports, side) => {
      if (ports.length < 2) return;
      const sorted = [...ports].sort((a, b) => a.y - b.y);
      const gaps = [];
      for (let i = 1; i < sorted.length; i++) gaps.push(sorted[i].y - sorted[i-1].y);
      const avgGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
      const groups = [[]];
      for (let i = 0; i < sorted.length; i++) {
        if (i > 0 && Math.abs(sorted[i].y - sorted[i-1].y) > avgGap * 1.8) groups.push([]);
        groups[groups.length-1].push(sorted[i]);
      }
      const finalGroups = groups.length === 1 && sorted.length > 6
        ? [sorted.slice(0, Math.ceil(sorted.length/2)), sorted.slice(Math.ceil(sorted.length/2))]
        : groups;
      for (const grp of finalGroups) {
        if (grp.length < 1) continue;
        const minY = Math.min(...grp.map(p => p.y));
        const maxY = Math.max(...grp.map(p => p.y));
        const hy1 = y + minY - 3, hy2 = y + maxY + PORT_W + 3;
        const hx = side === 'WEST' ? x + 1 : x + w - 8;
        els.push(e('rect', { x: hx, y: hy1, width: 7, height: hy2 - hy1, rx: 1,
          fill: '#1a1a1a', stroke: nodeColor, strokeWidth: 0.4, opacity: 0.2 }));
      }
    };
    drawHeaderStrip(leftPorts, 'WEST');
    drawHeaderStrip(rightPorts, 'EAST');
  }

  function _mcuLabels(cx, y, e, els, nodeColor, label, sub) {
    els.push(e('text', { x: cx, y: y + 16, textAnchor: 'middle',
      fill: nodeColor, fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)' }, label));
    els.push(e('text', { x: cx, y: y + 27, textAnchor: 'middle',
      fill: '#666', fontSize: 8, fontFamily: 'var(--font-mono)' }, sub));
  }

  // ── Arduino Uno R3 ──
  function _arduinoDecor(node, meta, nodeColor) {
    const s = _mcuDecorShared(node, meta, nodeColor);
    const { x, y, w, h, cx, _cy, e, els } = s;
    const BL = 68.58, BW = 53.34;
    const sx = (pcbY) => x + (BW - pcbY) / BW * w;
    const sy = (pcbX) => y + (BL - pcbX) / BL * h;
    const sc = (mm) => mm * w / BW;
    const scH = (mm) => mm * h / BL;
    const usbCx = sx(38.10), usbCy = sy(3.81), usbW = sc(16), usbH = scH(12);
    els.push(e('rect', { x: usbCx-usbW/2, y: usbCy-usbH/2, width: usbW, height: usbH, rx: 2, fill: '#1a1a2a', stroke: '#888', strokeWidth: 1.2 }));
    els.push(e('rect', { x: usbCx-usbW/2+3, y: usbCy-usbH/2+3, width: usbW-6, height: usbH-6, rx: 1, fill: '#222', stroke: '#555', strokeWidth: 0.5 }));
    els.push(e('text', { x: usbCx, y: usbCy-usbH/2-2, textAnchor: 'middle', fill: '#666', fontSize: 4, opacity: 0.4, fontFamily: 'var(--font-mono)' }, 'USB-B'));
    const dcCx = sx(8.382), dcCy = sy(5.334), dcW = sc(9), dcH = scH(14);
    els.push(e('rect', { x: dcCx-dcW/2, y: dcCy-dcH/2, width: dcW, height: dcH, rx: 1.5, fill: '#111', stroke: '#666', strokeWidth: 0.8 }));
    els.push(e('circle', { cx: dcCx, cy: dcCy, r: Math.min(dcW,dcH)*0.3, fill: '#1a1a1a', stroke: '#555', strokeWidth: 0.6 }));
    els.push(e('circle', { cx: dcCx, cy: dcCy, r: Math.min(dcW,dcH)*0.12, fill: '#333' }));
    const chipCx = sx(16.383), chipCy = sy(46.355), chipW = sc(7.62), chipH = scH(35.56);
    els.push(e('rect', { x: chipCx-chipW/2, y: chipCy-chipH/2, width: chipW, height: chipH, rx: 1.5, fill: '#0a0a1a', stroke: '#666', strokeWidth: 0.8 }));
    const notchR = Math.min(chipW*0.2, 3);
    els.push(e('path', { d: `M${chipCx-notchR},${chipCy-chipH/2} A${notchR},${notchR} 0 0,1 ${chipCx+notchR},${chipCy-chipH/2}`, fill: 'none', stroke: '#888', strokeWidth: 0.6 }));
    els.push(e('circle', { cx: chipCx-chipW/2+3, cy: chipCy-chipH/2+3, r: 1.2, fill: '#888', opacity: 0.3 }));
    for (let i = 0; i < 14; i++) {
      const py = chipCy-chipH/2+2+i*(chipH-4)/13;
      els.push(e('line', { x1: chipCx-chipW/2-3, y1: py, x2: chipCx-chipW/2, y2: py, stroke: '#888', strokeWidth: 0.5, opacity: 0.25 }));
      els.push(e('line', { x1: chipCx+chipW/2, y1: py, x2: chipCx+chipW/2+3, y2: py, stroke: '#888', strokeWidth: 0.5, opacity: 0.25 }));
    }
    els.push(e('text', { x: chipCx, y: chipCy+2, textAnchor: 'middle', fill: '#777', fontSize: 5, opacity: 0.35, fontFamily: 'var(--font-mono)', transform: `rotate(-90,${chipCx},${chipCy})` }, 'ATmega328P'));
    const u2Cx = sx(34.671), u2Cy = sy(19.939), u2S = sc(5);
    els.push(e('rect', { x: u2Cx-u2S/2, y: u2Cy-u2S/2, width: u2S, height: u2S, rx: 1, fill: '#0a0a1a', stroke: '#555', strokeWidth: 0.5 }));
    els.push(e('circle', { cx: u2Cx-u2S/2+2, cy: u2Cy-u2S/2+2, r: 1, fill: '#666', opacity: 0.3 }));
    const crCx = sx(26.162), crCy = sy(18.923), crW = sc(4.7), crH = scH(11.4);
    els.push(e('rect', { x: crCx-crW/2, y: crCy-crH/2, width: crW, height: crH, rx: 1, fill: '#1a1a2a', stroke: '#aaa', strokeWidth: 0.5, opacity: 0.4 }));
    const mhR = sc(1.6);
    [[13.97,2.54],[15.24,50.80],[66.04,7.62],[66.04,35.56]].forEach(([px,py]) => {
      const mx = sx(py), my = sy(px);
      els.push(e('circle', { cx: mx, cy: my, r: mhR, fill: '#0a0a0a', stroke: '#444', strokeWidth: 0.6, opacity: 0.35 }));
    });
    const rstCx = sx(24), rstCy = sy(51), rstR = sc(2);
    els.push(e('circle', { cx: rstCx, cy: rstCy, r: rstR, fill: '#222', stroke: '#777', strokeWidth: 0.8 }));
    els.push(e('circle', { cx: rstCx, cy: rstCy, r: rstR*0.5, fill: '#444', opacity: 0.5 }));
    els.push(e('circle', { cx: sx(31.75), cy: sy(7.62), r: sc(1.2), fill: '#44ff44', opacity: 0.5 }));
    els.push(e('circle', { cx: sx(36.83), cy: sy(22.09), r: sc(1), fill: '#ff4444', opacity: 0.4 }));
    els.push(e('circle', { cx: sx(39.37), cy: sy(22.09), r: sc(1), fill: '#44ff44', opacity: 0.4 }));
    const icspCx = sx(27.94), icspCy = sy(64.9), icspP = sc(2.54);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 2; c++)
      els.push(e('rect', { x: icspCx-icspP+c*icspP, y: icspCy-icspP*1.5+r*icspP, width: icspP*0.8, height: icspP*0.8, rx: 0.3, fill: '#c8a44e', opacity: 0.3 }));
    _mcuHeaderStrips(node, x, y, w, e, els, nodeColor);
    _mcuLabels(cx, y, e, els, nodeColor, meta.label || 'Arduino Uno', meta.sub || 'ATmega328P');
    return els;
  }

  // ── ESP32 DevKit V1 ──
  function _esp32Decor(node, meta, nodeColor) {
    const s = _mcuDecorShared(node, meta, nodeColor);
    const { x, y, w, h, cx, _cy, e, els } = s;
    const BL = 51.5, BW = 28.0;
    const sx = (pcbY) => x + (BW - pcbY) / BW * w;
    const sy = (pcbX) => y + (BL - pcbX) / BL * h;
    const sc = (mm) => mm * w / BW;
    const scH = (mm) => mm * h / BL;
    const modCx = sx(14.0), modCy = sy(43.0), modW = sc(25.5), modH = scH(18);
    els.push(e('rect', { x: modCx-modW/2, y: modCy-modH/2, width: modW, height: modH, rx: 2, fill: '#0a0a18', stroke: '#888', strokeWidth: 0.8 }));
    els.push(e('rect', { x: modCx-modW/2, y: modCy-modH/2, width: modW, height: modH*0.35, rx: 2, fill: 'none', stroke: '#aaa', strokeWidth: 0.4, strokeDasharray: '2,1', opacity: 0.3 }));
    els.push(e('text', { x: modCx, y: modCy+3, textAnchor: 'middle', fill: '#888', fontSize: 5, opacity: 0.35, fontFamily: 'var(--font-mono)' }, 'ESP32'));
    const usbCx = sx(14.0), usbCy = sy(2.5), usbW = sc(7.5), usbH = scH(5.6);
    els.push(e('rect', { x: usbCx-usbW/2, y: usbCy-usbH/2, width: usbW, height: usbH, rx: 1.5, fill: '#1a1a2a', stroke: '#888', strokeWidth: 1 }));
    els.push(e('rect', { x: usbCx-usbW/2+2, y: usbCy-usbH/2+2, width: usbW-4, height: usbH-4, rx: 0.5, fill: '#222', stroke: '#555', strokeWidth: 0.4 }));
    const ldoCx = sx(22.0), ldoCy = sy(15.0), ldoW = sc(3.5), ldoH = scH(6.5);
    els.push(e('rect', { x: ldoCx-ldoW/2, y: ldoCy-ldoH/2, width: ldoW, height: ldoH, rx: 0.5, fill: '#111', stroke: '#666', strokeWidth: 0.4, opacity: 0.4 }));
    const btnR = sc(1.5);
    els.push(e('circle', { cx: sx(8), cy: sy(12), r: btnR, fill: '#222', stroke: '#777', strokeWidth: 0.6 }));
    els.push(e('circle', { cx: sx(20), cy: sy(12), r: btnR, fill: '#222', stroke: '#777', strokeWidth: 0.6 }));
    els.push(e('circle', { cx: sx(14), cy: sy(5), r: sc(0.8), fill: '#ff4444', opacity: 0.4 }));
    _mcuHeaderStrips(node, x, y, w, e, els, nodeColor);
    _mcuLabels(cx, y, e, els, nodeColor, meta.label || 'ESP32', meta.sub || 'Xtensa LX6');
    return els;
  }

  // ── micro:bit V2 ──
  function _microbitDecor(node, meta, nodeColor) {
    const s = _mcuDecorShared(node, meta, nodeColor);
    const { x, y, w, h, cx, _cy, e, els } = s;
    const BL = 51.60, BW = 42.00;
    const sx = (pcbY) => x + (BW - pcbY) / BW * w;
    const sy = (pcbX) => y + (BL - pcbX) / BL * h;
    const sc = (mm) => mm * w / BW;
    const scH = (mm) => mm * h / BL;
    const ledCx = sx(25.80), ledCy = sy(25.8), ledW = sc(16), ledH = scH(20);
    els.push(e('rect', { x: ledCx-ledW/2, y: ledCy-ledH/2, width: ledW, height: ledH, rx: 1.5, fill: '#0a0a0a', stroke: '#555', strokeWidth: 0.5 }));
    for (let r = 0; r < 5; r++) for (let c = 0; c < 5; c++) {
      const lx = ledCx - ledW*0.35 + c * ledW*0.175;
      const ly = ledCy - ledH*0.35 + r * ledH*0.175;
      els.push(e('rect', { x: lx-1.5, y: ly-1.5, width: 3, height: 3, rx: 0.5, fill: '#ff2222', opacity: 0.25 }));
    }
    const usbCx = sx(41.5), usbCy = sy(17.8), usbW = sc(5.6), usbH = scH(7.5);
    els.push(e('rect', { x: usbCx-usbW/2, y: usbCy-usbH/2, width: usbW, height: usbH, rx: 1, fill: '#1a1a2a', stroke: '#888', strokeWidth: 0.8 }));
    const rstCx = sx(39.0), rstCy = sy(36.0), rstR = sc(2);
    els.push(e('circle', { cx: rstCx, cy: rstCy, r: rstR, fill: '#222', stroke: '#777', strokeWidth: 0.6 }));
    const spkCx = sx(18.0), spkCy = sy(42.0), spkR = sc(4);
    els.push(e('circle', { cx: spkCx, cy: spkCy, r: spkR, fill: '#111', stroke: '#666', strokeWidth: 0.5, opacity: 0.4 }));
    [[6.21,'P0'],[16.37,'P1'],[27.80,'P2'],[39.23,'3V'],[49.39,'GND']].forEach(([px, _lbl]) => {
      const ringCx = sx(3.5), ringCy = sy(px), ringR = sc(2);
      els.push(e('circle', { cx: ringCx, cy: ringCy, r: ringR, fill: '#c8a44e', stroke: '#a08030', strokeWidth: 0.6, opacity: 0.4 }));
      els.push(e('circle', { cx: ringCx, cy: ringCy, r: ringR*0.4, fill: '#0a0a0a' }));
    });
    _mcuHeaderStrips(node, x, y, w, e, els, nodeColor);
    _mcuLabels(cx, y, e, els, nodeColor, meta.label || 'micro:bit', meta.sub || 'nRF52833');
    return els;
  }

  // ── Raspberry Pi 4B ──
  function _rpiDecor(node, meta, nodeColor) {
    const s = _mcuDecorShared(node, meta, nodeColor);
    const { x, y, w, h, cx, _cy, e, els } = s;
    const BL = 85.0, BW = 56.0;
    const sx = (pcbY) => x + (BW - pcbY) / BW * w;
    const sy = (pcbX) => y + (BL - pcbX) / BL * h;
    const sc = (mm) => mm * w / BW;
    const scH = (mm) => mm * h / BL;
    const socCx = sx(32.5), socCy = sy(25.75), socS = sc(15);
    els.push(e('rect', { x: socCx-socS/2, y: socCy-socS/2, width: socS, height: socS, rx: 1.5, fill: '#0a0a18', stroke: '#888', strokeWidth: 0.8 }));
    els.push(e('text', { x: socCx, y: socCy+2, textAnchor: 'middle', fill: '#888', fontSize: 5, opacity: 0.35, fontFamily: 'var(--font-mono)' }, 'BCM2711'));
    const ramCx = sx(27.0), ramCy = sy(49.0), ramS = sc(10);
    els.push(e('rect', { x: ramCx-ramS/2, y: ramCy-ramS/2, width: ramS, height: ramS, rx: 1, fill: '#0a0a18', stroke: '#666', strokeWidth: 0.5 }));
    const pwrCx = sx(0), pwrCy = sy(15.1), pwrW = sc(7.5), pwrH = scH(8.9);
    els.push(e('rect', { x: pwrCx-pwrW/2, y: pwrCy-pwrH/2, width: pwrW, height: pwrH, rx: 1.5, fill: '#1a1a2a', stroke: '#888', strokeWidth: 0.8 }));
    [[29.0,'HDMI0'],[45.5,'HDMI1']].forEach(([px, _lbl]) => {
      const hCx = sx(0), hCy = sy(px), hW = sc(7), hH = scH(6.5);
      els.push(e('rect', { x: hCx-hW/2, y: hCy-hH/2, width: hW, height: hH, rx: 1, fill: '#111', stroke: '#666', strokeWidth: 0.6 }));
    });
    const ethCx = sx(45.75), ethCy = sy(85.0), ethW = sc(16), ethH = scH(21.3);
    els.push(e('rect', { x: ethCx-ethW/2, y: ethCy-ethH/2, width: ethW, height: ethH, rx: 1, fill: '#1a1a2a', stroke: '#888', strokeWidth: 0.8 }));
    [[27.0,'USB3'],[9.0,'USB2']].forEach(([py, _lbl]) => {
      const uCx = sx(py), uCy = sy(85.0), uW = sc(13.3), uH = scH(17.3);
      els.push(e('rect', { x: uCx-uW/2, y: uCy-uH/2, width: uW, height: uH, rx: 1, fill: '#1a1a2a', stroke: '#777', strokeWidth: 0.6 }));
      els.push(e('line', { x1: uCx-uW/2+2, y1: uCy, x2: uCx+uW/2-2, y2: uCy, stroke: '#555', strokeWidth: 0.4 }));
    });
    const gpioY1 = sx(53.77), gpioY2 = sx(51.23);
    const gpioX1 = sy(55.36), gpioX2 = sy(7.10);
    const gpioW = Math.abs(gpioY2 - gpioY1) + sc(2.54);
    const gpioH = Math.abs(gpioX2 - gpioX1) + scH(2.54);
    els.push(e('rect', { x: Math.min(gpioY1, gpioY2)-sc(1.27), y: Math.min(gpioX1, gpioX2)-scH(1.27), width: gpioW, height: gpioH, rx: 1, fill: '#1a1a1a', stroke: '#c8a44e', strokeWidth: 0.5, opacity: 0.3 }));
    for (let i = 0; i < 20; i++) for (let r = 0; r < 2; r++) {
      const dotX = sx(51.23 + r * 2.54), dotY = sy(7.10 + i * 2.54);
      els.push(e('circle', { cx: dotX, cy: dotY, r: sc(0.5), fill: '#c8a44e', opacity: 0.25 }));
    }
    [[3.5,3.5],[61.5,3.5],[3.5,52.5],[61.5,52.5]].forEach(([px,py]) => {
      const mx = sx(py), my = sy(px), mr = sc(1.35);
      els.push(e('circle', { cx: mx, cy: my, r: mr, fill: '#0a0a0a', stroke: '#444', strokeWidth: 0.5, opacity: 0.35 }));
    });
    els.push(e('circle', { cx: sx(8), cy: sy(2), r: sc(0.8), fill: '#ff4444', opacity: 0.4 }));
    els.push(e('circle', { cx: sx(12), cy: sy(2), r: sc(0.8), fill: '#44ff44', opacity: 0.4 }));
    _mcuHeaderStrips(node, x, y, w, e, els, nodeColor);
    _mcuLabels(cx, y, e, els, nodeColor, meta.label || 'Raspberry Pi', meta.sub || 'BCM2711');
    return els;
  }

  function _mcuDecor(node, meta, nodeColor) {
    const t = meta.mcuType || 'Arduino';
    if (t === 'ESP32') return _esp32Decor(node, meta, nodeColor);
    if (t === 'Microbit') return _microbitDecor(node, meta, nodeColor);
    if (t === 'RPi') return _rpiDecor(node, meta, nodeColor);
    return _arduinoDecor(node, meta, nodeColor);
  }

  // ── B(issue1): 被動元件「不截斷走線」表示（原先完整 IEC 符號樣式,但不插節點）──
  // R → 走線上疊加「引腳+IEC 矩形」並沿線段方向旋轉對齊;C → 元件/MCU 旁完整平行板電容徽章。
  // 兩者皆不加 ELK 節點 → MCU 與元件的佈局/走線完全不受影響。
  function _passiveSym(cx, cy, pas, angle) {
    // Phase2 step5: external→高亮實色; onboard→灰階低調
    const e = (tag, props, ...ch) => React.createElement(tag, props, ...ch);
    const FONT = 'var(--font-mono, Consolas)';
    const a = angle || 0;
    const isOnboard = (pas.location || 'external') === 'onboard';
    const col = pas.kind === 'C'
      ? (isOnboard ? '#4a7a8a' : '#5bc0de')
      : (isOnboard ? '#6b6040' : '#d0a050');
    const refLabel = pas.refdes ? `${pas.refdes} ` : '';
    let body;
    if (pas.kind === 'C') {
      const pw = 12, gap = 4, lead = 5;
      body = [
        e('line', { key: 'a', x1: -gap / 2 - lead, y1: 0, x2: -gap / 2, y2: 0, stroke: col, strokeWidth: 1.5 }),
        e('line', { key: 'p1', x1: -gap / 2, y1: -pw / 2, x2: -gap / 2, y2: pw / 2, stroke: col, strokeWidth: 2 }),
        e('line', { key: 'p2', x1: gap / 2, y1: -pw / 2, x2: gap / 2, y2: pw / 2, stroke: col, strokeWidth: 2 }),
        e('line', { key: 'b', x1: gap / 2, y1: 0, x2: gap / 2 + lead, y2: 0, stroke: col, strokeWidth: 1.5 }),
        e('text', { key: 't', x: 0, y: -pw / 2 - 3, textAnchor: 'middle', fill: col, fontSize: 8, fontFamily: FONT, transform: `rotate(${-a})` }, `${refLabel}${pas.value || ''}`),
      ];
    } else {
      const rw = 20, rh = 9, lead = 6;
      const labelText = isOnboard ? `${refLabel}${pas.value || ''} on-board` : `${refLabel}${pas.value || ''}`;
      body = [
        e('line', { key: 'l1', x1: -rw / 2 - lead, y1: 0, x2: -rw / 2, y2: 0, stroke: col, strokeWidth: 1.5 }),
        e('line', { key: 'l2', x1: rw / 2, y1: 0, x2: rw / 2 + lead, y2: 0, stroke: col, strokeWidth: 1.5 }),
        e('rect', { key: 'rb', x: -rw / 2, y: -rh / 2, width: rw, height: rh, rx: 1, fill: '#161616', stroke: col, strokeWidth: 1.5 }),
        e('text', { key: 't', x: 0, y: -rh / 2 - 3, textAnchor: 'middle', fill: col, fontSize: 8, fontFamily: FONT, transform: `rotate(${-a})` }, labelText),
      ];
    }
    return [e('g', { transform: `translate(${cx} ${cy}) rotate(${a})` }, ...body)];
  }

  // C 徽章：完整平行板電容符號(引腳+雙板)+值,畫在節點右側外緣垂直堆疊(不佔走線、不當節點)
  // Phase2 step5: 依 location 切顏色與標籤 — external→高亮實色; onboard→灰階+標 "on-board"
  function _capBadges(node) {
    const ps = (node._meta || {}).passives || [];
    if (!ps.length) return [];
    const e = (tag, props, ...ch) => React.createElement(tag, props, ...ch);
    const FONT = 'var(--font-mono, Consolas)';
    const bx = node.x + node.width + 12, by = node.y + 14;
    const els = [];
    ps.forEach((p, i) => {
      const isOnboard = (p.location || 'onboard') === 'onboard';
      const col = isOnboard ? '#4a7a8a' : '#5bc0de';
      const refLabel = p.refdes ? `${p.refdes} ` : '';
      const roleLabel = p.role === 'bulk' ? ' bulk' : '';
      const locLabel = isOnboard ? ' on-board' : '';
      const cy = by + i * 20, pw = 12, gap = 4, lead = 5;
      els.push(e('line', { key: `a${i}`, x1: bx, y1: cy - gap / 2 - lead, x2: bx, y2: cy - gap / 2, stroke: col, strokeWidth: 1.5 }));
      els.push(e('line', { key: `p1${i}`, x1: bx - pw / 2, y1: cy - gap / 2, x2: bx + pw / 2, y2: cy - gap / 2, stroke: col, strokeWidth: 2 }));
      els.push(e('line', { key: `p2${i}`, x1: bx - pw / 2, y1: cy + gap / 2, x2: bx + pw / 2, y2: cy + gap / 2, stroke: col, strokeWidth: 2 }));
      els.push(e('line', { key: `b${i}`, x1: bx, y1: cy + gap / 2, x2: bx, y2: cy + gap / 2 + lead, stroke: col, strokeWidth: 1.5 }));
      els.push(e('text', { key: `t${i}`, x: bx + pw / 2 + 4, y: cy + 3, textAnchor: 'start', fill: col, fontSize: 7.5, fontFamily: FONT },
        `${refLabel}${p.value}${roleLabel}${locLabel}`));
    });
    return els;
  }

  // ── SVG Renderer ──

  function ElkSchematicSVG({ layout, _testCodes, onSelectComp, selectedComp }) {
    const [hoverComp, setHoverComp] = React.useState(null);
    const [hoverEdge, setHoverEdge] = React.useState(null);
    const [zoom, setZoom] = React.useState(1);
    const [pan, setPan] = React.useState({ x: 0, y: 0 });
    const isPanning = React.useRef(false);
    const lastMouse = React.useRef({ x: 0, y: 0 });
    const svgRef = React.useRef(null);
    const controlsRef = React.useRef(null);

    if (!layout || !layout.children) {
      return React.createElement('div', {
        style: { display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-tertiary)', fontSize: 13 }
      }, '等待接線數據⋯');
    }

    const padding = 40;
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const node of layout.children) {
      minX = Math.min(minX, node.x); minY = Math.min(minY, node.y);
      maxX = Math.max(maxX, node.x + node.width); maxY = Math.max(maxY, node.y + node.height);
    }
    const baseW = maxX - minX + padding * 2, baseH = maxY - minY + padding * 2;
    const baseCx = minX - padding + baseW / 2, baseCy = minY - padding + baseH / 2;
    const vbW = baseW / zoom, vbH = baseH / zoom;
    const vbX = baseCx - vbW / 2 + pan.x, vbY = baseCy - vbH / 2 + pan.y;

    const handleWheel = (e) => { e.preventDefault(); setZoom(z => Math.max(0.2, Math.min(10, z * (e.deltaY < 0 ? 1.15 : 1/1.15)))); };
    const handlePointerDown = (e) => { if (e.button !== 0) return; if (controlsRef.current && controlsRef.current.contains(e.target)) return; let el = e.target; while (el && el !== e.currentTarget) { if (el.style && el.style.cursor === 'pointer') return; el = el.parentElement; } isPanning.current = true; lastMouse.current = { x: e.clientX, y: e.clientY }; e.currentTarget.setPointerCapture(e.pointerId); };
    const handlePointerMove = (e) => { if (!isPanning.current) return; const svg = svgRef.current; if (!svg) return; const rect = svg.getBoundingClientRect(); const dx = (e.clientX - lastMouse.current.x) * (vbW / rect.width); const dy = (e.clientY - lastMouse.current.y) * (vbH / rect.height); lastMouse.current = { x: e.clientX, y: e.clientY }; setPan(p => ({ x: p.x - dx, y: p.y - dy })); };
    const handlePointerUp = () => { isPanning.current = false; };
    const handleReset = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

    const activeComp = hoverComp || selectedComp;
    const activeEdges = activeComp ? (layout.edges || []).filter(e => e.targets[0]?.startsWith(`${activeComp}_`) || e.sources[0]?.startsWith(`${activeComp}_`)).map(e => e.id) : [];
    const zoomPct = Math.round(zoom * 100);

    return React.createElement('div', { style: { position: 'relative', width: '100%', height: '100%' } },
    React.createElement('svg', { ref: svgRef, viewBox: `${vbX} ${vbY} ${vbW} ${vbH}`, preserveAspectRatio: 'xMidYMid meet', style: { width: '100%', height: '100%', cursor: isPanning.current ? 'grabbing' : 'grab' }, xmlns: 'http://www.w3.org/2000/svg', onWheel: handleWheel, onPointerDown: handlePointerDown, onPointerMove: handlePointerMove, onPointerUp: handlePointerUp, onPointerLeave: handlePointerUp },
      React.createElement('defs', null,
        React.createElement('pattern', { id: 'elkGrid', width: 24, height: 24, patternUnits: 'userSpaceOnUse' }, React.createElement('path', { d: 'M 24 0 L 0 0 0 24', fill: 'none', stroke: 'rgba(255,255,255,0.03)', strokeWidth: 0.5 })),
        React.createElement('filter', { id: 'elkGlow' }, React.createElement('feGaussianBlur', { stdDeviation: '3', result: 'blur' }), React.createElement('feMerge', null, React.createElement('feMergeNode', { in: 'blur' }), React.createElement('feMergeNode', { in: 'SourceGraphic' }))),
        React.createElement('filter', { id: 'flowGlow' }, React.createElement('feGaussianBlur', { stdDeviation: '1.5', result: 'g' }), React.createElement('feMerge', null, React.createElement('feMergeNode', { in: 'g' }), React.createElement('feMergeNode', { in: 'SourceGraphic' }))),
        // SWL1-V: pin direction 箭頭（fill=context-stroke 繼承線色；auto-start-reverse 讓 marker-start 反向）
        React.createElement('marker', { id: 'wireArrow', viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse', markerUnits: 'userSpaceOnUse' },
          React.createElement('path', { d: 'M0,0 L10,5 L0,10 z', fill: 'context-stroke' })),
      ),
      React.createElement('rect', { x: vbX, y: vbY, width: vbW, height: vbH, fill: 'url(#elkGrid)', style: { cursor: 'default' }, onClick: () => onSelectComp?.(null) }),
      // Edges
      ...(() => { const _labelSlots = {}; const _PAD = 6; const _nodeBBs = layout.children.map(n => ({ x: n.x - _PAD, y: n.y - _PAD, r: n.x + n.width + _PAD, b: n.y + n.height + _PAD })); const _hitsNode = (tx, ty, tw, th) => _nodeBBs.some(n => tx < n.r && tx + tw > n.x && ty < n.b && ty + th > n.y);
      return (layout.edges || []).map(edge => { const meta = edge._meta || {}; const ws = WIRE_STYLES[meta.type] || WIRE_STYLES.signal; const color = ws.color || meta.color || '#888'; const isActive = activeEdges.includes(edge.id); const isHovered = hoverEdge === edge.id; const dim = activeComp && !isActive; const arrowDir = meta.type === 'signal' ? _flowDir(meta) : null; const sections = edge.sections || []; let pathD = ''; for (const sec of sections) { const pts = [sec.startPoint, ...(sec.bendPoints || []), sec.endPoint]; pathD += pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '); }
      return React.createElement('g', { key: edge.id },
        React.createElement('path', { d: pathD, fill: 'none', stroke: color, strokeWidth: isHovered ? ws.width + 1.5 : ws.width, strokeDasharray: ws.dash || (meta.type === 'signal' ? '6 3' : null), opacity: dim ? 0.15 : (isActive || isHovered) ? 1 : 0.6, strokeLinecap: 'round', strokeLinejoin: 'round', markerEnd: arrowDir === 'mcu2comp' ? 'url(#wireArrow)' : undefined, markerStart: arrowDir === 'comp2mcu' ? 'url(#wireArrow)' : undefined, style: { cursor: 'pointer', transition: 'opacity 0.2s, stroke-width 0.15s' }, onMouseEnter: () => setHoverEdge(edge.id), onMouseLeave: () => setHoverEdge(null) }),
        pathD && !dim && (() => { const dir = _flowDir(meta); const reverse = dir === 'comp2mcu'; const speed = meta.type === 'gnd' ? 3.5 : meta.type === 'signal' ? 2.5 : 2; const r = meta.type === 'signal' ? 2 : 2.5; const dots = meta.type === 'gnd' ? 1 : 2; return Array.from({ length: dots }, (_, di) => React.createElement('circle', { key: `flow_${edge.id}_${di}`, r, fill: color, opacity: 0.85, filter: 'url(#flowGlow)' }, React.createElement('animateMotion', { dur: `${speed}s`, repeatCount: 'indefinite', begin: `${di * (speed / dots)}s`, keyPoints: reverse ? '1;0' : '0;1', keyTimes: '0;1', calcMode: 'linear', path: pathD }))); })(),
        meta.type === 'signal' && sections.length > 0 && (() => { const sec = sections[0]; const pts = [sec.startPoint, ...(sec.bendPoints || []), sec.endPoint]; const TW = 44, TH = 14; let bestPt = null; for (let i = 1; i < pts.length; i++) { const mid = { x: (pts[i-1].x + pts[i].x) / 2, y: (pts[i-1].y + pts[i].y) / 2 }; if (!_hitsNode(mid.x - TW/2, mid.y - TH/2, TW, TH)) { bestPt = mid; break; } } if (!bestPt) bestPt = pts[Math.min(1, pts.length - 1)]; const slotKey = `${Math.round(bestPt.x / 14)}_${Math.round(bestPt.y / 14)}`; const oIdx = _labelSlots[slotKey] || 0; _labelSlots[slotKey] = oIdx + 1; const oY = oIdx * 17; let finalY = bestPt.y + oY; if (_hitsNode(bestPt.x - TW/2, finalY - TH/2, TW, TH)) finalY -= TH + _PAD + oIdx * 17; return React.createElement('g', { opacity: dim ? 0.2 : 0.85 }, React.createElement('rect', { x: bestPt.x - TW/2, y: finalY - TH/2, width: TW, height: TH, rx: 3, fill: color + '18', stroke: color + '44', strokeWidth: 0.5 }), React.createElement('text', { x: bestPt.x, y: finalY + 3, textAnchor: 'middle', fill: color, fontSize: 7.5, fontFamily: 'var(--font-mono, Consolas)' }, `${meta.compPin}→${meta.mcuPin}`)); })(),
        meta.passive && meta.passive.kind === 'R' && sections.length > 0 && (() => { const sec = sections[0]; const pts = [sec.startPoint, ...(sec.bendPoints || []), sec.endPoint]; let best = null, bestLen = -1, bestA = 0; for (let i = 1; i < pts.length; i++) { const ddx = pts[i].x - pts[i-1].x, ddy = pts[i].y - pts[i-1].y; const len = Math.hypot(ddx, ddy); if (len > bestLen) { bestLen = len; best = { x: (pts[i-1].x + pts[i].x) / 2, y: (pts[i-1].y + pts[i].y) / 2 }; bestA = Math.atan2(ddy, ddx) * 180 / Math.PI; } } if (!best) return null; if (bestA > 90) bestA -= 180; else if (bestA < -90) bestA += 180; return React.createElement('g', { opacity: dim ? 0.3 : 1 }, ..._passiveSym(best.x, best.y, meta.passive, bestA)); })(),
      ); }); })(),
      // Nodes
      ...layout.children.map(node => { const meta = node._meta || {};
      const isMcu = node.id === 'mcu'; const isActive = activeComp === node.id; const dim = activeComp && !isActive && !isMcu; const nodeColor = isMcu ? '#40e0d0' : (meta.color || '#888');
      return React.createElement('g', { key: node.id, style: { cursor: isMcu ? 'default' : 'pointer', transition: 'opacity 0.2s' }, opacity: dim ? 0.3 : 1, filter: isActive ? 'url(#elkGlow)' : undefined, onMouseEnter: isMcu ? undefined : () => setHoverComp(node.id), onMouseLeave: isMcu ? undefined : () => setHoverComp(null), onClick: isMcu ? undefined : () => onSelectComp?.(node.id === selectedComp ? null : node.id) },
        ...(isMcu ? _mcuDecor(node, meta, nodeColor) : [ React.createElement('rect', { x: node.x, y: node.y, width: node.width, height: node.height, rx: 4, fill: '#0e1018', stroke: nodeColor, strokeWidth: isActive ? 2.5 : 1.5 }), ..._compDecor(meta.compKey || node.id, node.x, node.y, node.width, node.height, nodeColor), React.createElement('text', { x: node.x + node.width / 2, y: node.y + node.height - 14, textAnchor: 'middle', fill: nodeColor, fontSize: 10, fontWeight: 600, fontFamily: 'var(--font-mono, Consolas)' }, meta.label || node.id), React.createElement('text', { x: node.x + node.width / 2, y: node.y + node.height - 4, textAnchor: 'middle', fill: '#666', fontSize: 7, fontFamily: 'var(--font-mono, Consolas)' }, meta.sub || '') ]),
        ...(node.ports || []).map(port => { if (!port.x && port.x !== 0) return null; const side = port.properties?.['port.side']; let px = node.x + port.x + port.width / 2; let py = node.y + port.y + port.height / 2; if (side === 'NORTH') py = Math.max(py, node.y); else if (side === 'SOUTH') py = Math.min(py, node.y + node.height); else if (side === 'WEST') px = Math.max(px, node.x); else if (side === 'EAST') px = Math.min(px, node.x + node.width); const pm = port._meta || {}; const isUsed = isMcu ? pm.used : true; const pinLabel = pm.label || port.id.split('_').pop(); const ptColor = isUsed ? _pinClr(pinLabel) : '#333';
        return React.createElement('g', { key: port.id }, (pinLabel === 'VCC' || pinLabel === '5V' || pinLabel === '3V3' || pinLabel === 'VIN' || pinLabel === 'IOREF' || pinLabel === 'GND' || pinLabel === 'GND_D' || pinLabel === 'GND2') ? React.createElement('rect', { x: px - 3, y: py - 3, width: 6, height: 6, rx: 1, fill: isUsed ? ptColor : '#333', opacity: isUsed ? 0.85 : 0.3 }) : React.createElement('circle', { cx: px, cy: py, r: isUsed ? 3.5 : 1.5, fill: isUsed ? ptColor : '#333', opacity: isUsed ? 0.85 : 0.3 }), isUsed && React.createElement('text', { x: px + (side === 'WEST' ? 8 : side === 'EAST' ? -8 : 0), y: py + (side === 'NORTH' ? -7 : side === 'SOUTH' ? 11 : 3), textAnchor: side === 'EAST' ? 'end' : side === 'WEST' ? 'start' : 'middle', fill: ptColor, fontSize: 7, fontFamily: 'var(--font-mono, Consolas)', opacity: 0.75, fontWeight: isMcu ? 400 : 500 }, pinLabel)); }),
        ..._capBadges(node),
      ); }),
    ),
    // SWL5: pin 角色色碼圖例（解碼「只靠色碼」— 配合 SWL1-V 箭頭表方向）
    React.createElement('div', { style: { position: 'absolute', bottom: 12, left: 12, display: 'flex', flexWrap: 'wrap', gap: '3px 9px', maxWidth: 250, background: 'rgba(10,10,20,0.85)', border: '1px solid #333', borderRadius: 6, padding: '6px 9px', fontSize: 9, fontFamily: 'var(--font-mono, Consolas)', pointerEvents: 'none', zIndex: 10 } },
      ...Object.entries(PIN_CLR || {}).filter(([k]) => k !== 'OTHER').map(([role, col]) =>
        React.createElement('span', { key: role, style: { display: 'inline-flex', alignItems: 'center', gap: 3, color: '#9aa' } },
          React.createElement('span', { style: { width: 8, height: 8, borderRadius: 2, background: col, display: 'inline-block', flexShrink: 0 } }),
          role))),
    React.createElement('div', { ref: controlsRef, style: { position: 'absolute', bottom: 12, right: 12, display: 'flex', alignItems: 'center', gap: 0, background: 'rgba(10,10,20,0.9)', border: '1px solid #333', borderRadius: 6, padding: '2px 4px', userSelect: 'none', zIndex: 10 } },
      React.createElement('button', { onClick: () => setZoom(z => Math.min(10, z * 1.3)), style: { width: 28, height: 26, background: 'transparent', border: 'none', color: '#aaa', fontSize: 14, cursor: 'pointer', fontFamily: 'var(--font-mono)' } }, '+'),
      React.createElement('button', { onClick: handleReset, style: { minWidth: 44, height: 26, background: 'transparent', border: 'none', color: '#888', fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-mono)' } }, `${zoomPct}%`),
      React.createElement('button', { onClick: () => setZoom(z => Math.max(0.2, z / 1.3)), style: { width: 28, height: 26, background: 'transparent', border: 'none', color: '#aaa', fontSize: 14, cursor: 'pointer', fontFamily: 'var(--font-mono)' } }, '−'),
    ));
  }

  // ── Test Code Panel ──

  function TestCodePanel({ compKey, testCodes }) {
    if (!compKey) return null;
    const spec = COMP_SPECS[compKey] || {};
    const tc = testCodes?.[compKey];
    const [copied, setCopied] = React.useState(false);
    const handleCopy = () => { if (tc?.code) { navigator.clipboard.writeText(tc.code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); }); } };
    return React.createElement('div', { style: { marginTop: 16, padding: '12px 0', borderTop: '1px solid var(--border-subtle)' } },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 } },
        React.createElement('div', { style: { fontSize: 11, fontWeight: 600, color: spec.color || '#888' } }, `${spec.label || compKey} 測試代碼`),
        tc && React.createElement('button', { onClick: handleCopy, style: { padding: '2px 8px', fontSize: 10, borderRadius: 4, background: copied ? 'var(--green-dim)' : 'var(--bg-2)', border: '1px solid var(--border-subtle)', color: copied ? 'var(--green)' : 'var(--text-tertiary)', cursor: 'pointer', fontFamily: 'var(--font-sans)' } }, copied ? 'Copied' : 'Copy'),
      ),
      tc ? React.createElement('pre', { style: { background: '#0a0a14', borderRadius: 6, padding: '10px 12px', fontSize: 10, lineHeight: 1.5, overflowX: 'auto', fontFamily: 'var(--font-mono, Consolas)', color: '#ccc', border: '1px solid var(--border-subtle)', maxHeight: 260, overflowY: 'auto' } }, _highlightCode(tc.code))
        : React.createElement('div', { style: { fontSize: 11, color: 'var(--text-tertiary)', padding: 8 } }, '此元件暫無測試模板'),
    );
  }

  function _highlightCode(code) {
    if (!code) return null;
    return code.split('\n').map((line, i) => {
      const parts = [];
      let rest = line;
      const commentIdx = rest.indexOf('//');
      let comment = '';
      if (commentIdx >= 0) { comment = rest.slice(commentIdx); rest = rest.slice(0, commentIdx); }
      const kw = /\b(void|int|float|bool|if|else|for|while|return|include|define|delay|pinMode|digitalWrite|digitalRead|analogRead|analogWrite|Serial|HIGH|LOW|INPUT|OUTPUT|true|false)\b/g;
      let lastIdx = 0, match;
      while ((match = kw.exec(rest)) !== null) { if (match.index > lastIdx) parts.push(rest.slice(lastIdx, match.index)); parts.push(React.createElement('span', { key: `k${i}_${match.index}`, style: { color: '#c792ea' } }, match[0])); lastIdx = kw.lastIndex; }
      if (lastIdx < rest.length) parts.push(rest.slice(lastIdx));
      if (comment) parts.push(React.createElement('span', { key: `c${i}`, style: { color: '#546e7a' } }, comment));
      return React.createElement('div', { key: i }, ...parts);
    });
  }

  // ── Main Schematic Controller ──

  function ElkSchematic({ store }) {
    const [layout, setLayout] = React.useState(null);
    const [testCodes, setTestCodes] = React.useState({});
    const [error, setError] = React.useState(null);
    const [loading, setLoading] = React.useState(false);
    const [fidelity, setFidelity] = React.useState(null);  // VS-FE: 接線保真 verdict
    const selectedComp = store?.selectedComponentId || null;
    const setSelectedComp = React.useCallback((id) => {
      PipelineStore.dispatch(id ? { type: 'SELECT_COMPONENT', payload: id } : { type: 'DESELECT_COMPONENT' });
    }, []);
    const components = store?.components || [];
    const wiring = store?.wiring || [];

    React.useEffect(() => {
      if (layout) return;
      if (components.length === 0) return;
      const brain = components.find(c => c.role === 'Brain');
      if (!brain) return;
      const brainType = (brain.type || brain.part || 'Arduino').replace(/-class$/, '').replace(/\s.*/,'');
      const mcuKey = brainType.includes('ESP') ? 'ESP32' : brainType.includes('Micro') ? 'Microbit' : brainType.includes('RPi') || brainType.includes('Raspberry') ? 'RPi' : 'Arduino';
      const _OUTPUT_ROLES = new Set(['Output', 'Actuator', 'Lighting', 'Display', 'Motor', 'Audio', 'Control', 'Sound', 'Mist', 'Chassis', 'Enclosure']);
      const _SENSOR_ROLES = new Set(['Sensor', 'Input']);
      const outputs = components.filter(c => _OUTPUT_ROLES.has(c.role)).map(c => (c.type || c.part || '').replace(/-class$/, ''));
      const sensors = components.filter(c => _SENSOR_ROLES.has(c.role)).map(c => (c.type || c.part || '').replace(/-class$/, ''));
      if ([...outputs, ...sensors].length === 0) return;
      setLoading(true); setError(null);
      const _POWER_TYPE_TO_COMP = { 'Battery-AA': 'BatteryAA', 'Battery-LiPo': 'BatteryLiPo', 'USB-5V': 'USB5V', 'AC-Adapter': 'USB5V', 'USB-Adapter': 'USB5V' };
      const powerComp = components.find(c => c.role === 'Power');
      const powerKey = powerComp ? _POWER_TYPE_TO_COMP[(powerComp.type || powerComp.part || '').replace(/-class$/, '')] || null : null;
      const _injectPower = (wiringObj) => {
        if (!powerKey) return wiringObj;
        const out = { ...wiringObj };
        const pinPlus = powerKey === 'USB5V' ? 'V+' : 'BAT+';
        const pinMinus = powerKey === 'USB5V' ? 'V-' : 'BAT-';
        const isBattery = powerKey === 'BatteryAA' || powerKey === 'BatteryLiPo';
        const mcuPlusPin = (mcuKey === 'Arduino' && isBattery) ? 'VIN' : '5V';
        const plusVd = mcuPlusPin === 'VIN' ? 'vin' : '5V';
        out[powerKey] = { label: powerComp.part || powerKey, pins: [
          { comp: pinPlus, mcu: mcuPlusPin, color: '#ff4444',
            comp_dir: 'power_source', mcu_dir: 'power',
            comp_vd: plusVd, mcu_vd: plusVd,
            note: isBattery ? '電池 → VIN 電軌' : 'USB 電源 → 5V 電軌',
            _netRole: 'source' },
          { comp: pinMinus, mcu: 'GND', color: '#333333',
            comp_dir: 'gnd', mcu_dir: 'gnd',
            comp_vd: 'n/a', mcu_vd: 'n/a',
            note: '電源 GND → GND 電軌',
            _netRole: 'source' },
        ] };
        return out;
      };

      API.getWiring(mcuKey, outputs, sensors).then(data => {
        const wiringObj = _injectPower(data.wiring || data);
        const graph = buildElkGraph(mcuKey, wiringObj, data.power_passives);  // SWL3: 電源軌被動元件
        setFidelity(window.verifySchematicFidelity?.() || null);  // VS-FE: buildElkGraph 後 telemetry 已填，立即取 verdict
        if (!window.ELK) { setError('ELK 佈局引擎未載入'); setLoading(false); return; }
        return new window.ELK().layout(graph).then(result => {
          setLayout(result); setLoading(false);
          if (data.wiring) { const flat = []; for (const [comp, info] of Object.entries(data.wiring)) { for (const pin of (info.pins || [])) { flat.push({ from: pin.mcu, to: `${comp}.${pin.comp}`, net: pin.comp, color: pin.color }); } } PipelineStore.dispatch({ type: 'SET_WIRING', payload: flat }); }
        });
      }).catch(err => {
        if (wiring.length > 0) {
          const nested = _wiringFlatToNested(wiring, store?.bom, components);
          if (Object.keys(nested).length > 0) {
            console.info('[ELK Schematic] API 不可用，使用 store 資料');
            const graph = buildElkGraph(mcuKey, _injectPower(nested), []);  // SWL3: store fallback 無電源軌被動元件
            setFidelity(window.verifySchematicFidelity?.() || null);  // VS-FE: fallback 路徑同步取 verdict
            if (window.ELK) { new window.ELK().layout(graph).then(result => { setLayout(result); setLoading(false); }).catch(() => { setError('ELK 佈局計算失敗'); setLoading(false); }); return; }
          }
        }
        console.error('[ELK Schematic]', err);
        setError(err.message || '載入失敗'); setLoading(false);
      });
      API.getFirmware(mcuKey, 'auto', outputs, sensors).then(data => { if (data.test_codes) setTestCodes(data.test_codes); }).catch(() => {});
    }, [components.length, wiring.length]);

    return { layout, testCodes, selectedComp, setSelectedComp, error, loading, fidelity };
  }

  // ── Exports ──
  window.ElkSchematic = ElkSchematic;
  window.ElkSchematicSVG = ElkSchematicSVG;
  window.TestCodePanel = TestCodePanel;
})();
