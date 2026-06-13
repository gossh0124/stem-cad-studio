// port-resolver.js — Component & MCU visual renderers (top-view decorations)
// Split from schematic-elk.jsx (INF1-S1)
(() => {
  const _PORT_W = window.PORT_W;

  // ── Component Top-View Renderer Registry ──
  const COMP_RENDERERS = {
    Relay(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, _cy = y+h/2;
      const bx = x+6, by = y+5, bw = w-12, bh = h-10;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+4, by+4, 1.8);
      H.hole(els, e, bx+bw-4, by+4, 1.8);
      const rw = bw*0.42, rh = bh*0.65;
      const rx = bx+bw*0.35, ry = by+(bh-rh)/2;
      els.push(e('rect', { x: rx, y: ry, width: rw, height: rh, rx: 2,
        fill: '#06061a', stroke: '#5577cc', strokeWidth: 1.2, opacity: 0.85 }));
      els.push(e('text', { x: rx+rw/2, y: ry+rh/2+2, textAnchor: 'middle',
        fill: '#6688cc', fontSize: 6, opacity: 0.7, fontFamily: 'var(--font-mono)' }, 'SRD'));
      els.push(e('circle', { cx: bx+10, cy: by+bh-6, r: 2, fill: '#ff2222', opacity: 0.6 }));
      for (let i = 0; i < 3; i++) {
        const ty = by + 6 + i * (bh-12)/2;
        els.push(e('rect', { x: bx+bw-12, y: ty-3, width: 9, height: 6, rx: 1,
          fill: '#1a3a5a', stroke: '#5577cc', strokeWidth: 0.7, opacity: 0.7 }));
        els.push(e('circle', { cx: bx+bw-7.5, cy: ty, r: 1.5, fill: '#1a1a1a', stroke: '#888', strokeWidth: 0.5 }));
      }
      H.pinRow(els, e, bx+3, by+bh*0.2, 3, bh*0.3);
      return els;
    },

    SoilMoisture(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+5, by = y+4, bw = w-10, bh = h-8;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+bw*0.15, by+bh*0.25, 1.5);
      H.ic(els, e, bx+5, cy-5, 10, 10, 4, '555');
      els.push(e('rect', { x: bx+18, y: cy-3, width: 5, height: 5, rx: 0.5,
        fill: '#0a0a14', stroke: '#777', strokeWidth: 0.5, opacity: 0.6 }));
      const tx = bx + bw*0.22, tw = bw*0.72;
      for (let i = 0; i < 8; i++) {
        const ty = cy - 8 + i * (bh*0.55/7);
        const fromLeft = i % 2 === 0;
        els.push(e('line', {
          x1: fromLeft ? tx : tx+3, y1: ty,
          x2: fromLeft ? tx+tw-3 : tx+tw, y2: ty,
          stroke: '#d4a84e', strokeWidth: 0.8, opacity: 0.4 + (i%2)*0.1 }));
      }
      els.push(e('line', { x1: bx+bw*0.2, y1: by+1, x2: bx+bw*0.2, y2: by+bh-1,
        stroke: c, strokeWidth: 0.5, opacity: 0.2, strokeDasharray: '2 2' }));
      H.pinRow(els, e, bx+3, by+bh*0.15, 3, bh*0.35);
      return els;
    },

    Pump(x, y, w, h, c, e, H) {
      // RC3(2026-06-13):原置中圓形葉輪 glyph 與真 port(SOUTH nx0.3/0.41)脫鉤 → 改 DC 馬達式
      // 表示(submersible DC pump = DC 馬達 + 葉輪/泵頭),比照 DCMotor Q1 修法:端子不硬畫,
      // 由 SOUTH SCHEM_PINS port marker 畫(對齊真孔位);馬達本體靠左,真腳落其正下方。
      const els = [], cy = y+h/2;
      const bx = x+3, by = y+5, bw = w-6, bh = h-10;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      // DC 馬達本體(左半):繞組 + M
      const mw = bw*0.5, mh = bh*0.7, mxx = bx+3, myy = cy-mh/2;
      els.push(e('rect', { x: mxx, y: myy, width: mw, height: mh, rx: 3, fill: '#1a1a1a', stroke: '#888', strokeWidth: 0.8, opacity: 0.7 }));
      for (let i = 0; i < 5; i++) els.push(e('line', { x1: mxx+2, y1: myy+3+i*(mh-6)/4, x2: mxx+mw-2, y2: myy+3+i*(mh-6)/4, stroke: '#666', strokeWidth: 0.4, opacity: 0.5 }));
      els.push(e('text', { x: mxx+mw/2, y: cy+3, textAnchor: 'middle', fill: c, fontSize: 8, fontWeight: 700, opacity: 0.5, fontFamily: 'var(--font-mono)' }, 'M'));
      // 葉輪/泵頭(右):圓 + 出水口
      const pr = Math.min(bw*0.18, bh*0.4);
      const pcx = bx+bw*0.74, pcy = cy;
      els.push(e('circle', { cx: pcx, cy: pcy, r: pr, fill: '#06142a', stroke: c, strokeWidth: 1, opacity: 0.8 }));
      for (let a = 0; a < 360; a += 60) {
        const rad = a * Math.PI / 180;
        els.push(e('line', { x1: pcx, y1: pcy, x2: pcx + Math.cos(rad)*pr*0.7, y2: pcy + Math.sin(rad)*pr*0.7, stroke: c, strokeWidth: 0.7, opacity: 0.4 }));
      }
      els.push(e('rect', { x: x+w-7, y: cy-3, width: 7, height: 6, rx: 1.5, fill: '#0a1a2a', stroke: c, strokeWidth: 0.7, opacity: 0.55 }));  // 出水口
      return els;
    },

    Ultrasonic(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, _cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const tr = Math.min(bw*0.16, bh*0.35);
      const tcy = by + bh/2;
      els.push(e('circle', { cx: bx+bw*0.22, cy: tcy, r: tr, fill: '#1a1a2a', stroke: '#aaaacc', strokeWidth: 1.2, opacity: 0.8 }));
      els.push(e('circle', { cx: bx+bw*0.22, cy: tcy, r: tr*0.6, fill: '#222', stroke: '#888', strokeWidth: 0.5, opacity: 0.6 }));
      els.push(e('circle', { cx: bx+bw*0.78, cy: tcy, r: tr, fill: '#1a1a2a', stroke: '#aaaacc', strokeWidth: 1.2, opacity: 0.8 }));
      els.push(e('circle', { cx: bx+bw*0.78, cy: tcy, r: tr*0.6, fill: '#222', stroke: '#888', strokeWidth: 0.5, opacity: 0.6 }));
      els.push(e('rect', { x: cx-5, y: tcy-3, width: 10, height: 6, rx: 1, fill: '#222', stroke: '#888', strokeWidth: 0.4, opacity: 0.7 }));
      H.pinRow(els, e, bx+bw*0.25, by+bh-4, 4, (bw*0.5)/3);
      return els;
    },

    PIR(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, _cy = y+h/2;
      const bx = x+6, by = y+5, bw = w-12, bh = h-10;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const dr = Math.min(bw, bh) * 0.42;
      const dcx = bx+bw/2, dcy = by+bh*0.45;
      els.push(e('circle', { cx: dcx, cy: dcy, r: dr, fill: 'rgba(255,255,255,0.1)', stroke: 'rgba(255,255,255,0.35)', strokeWidth: 1.2 }));
      for (let i = 1; i <= 3; i++)
        els.push(e('circle', { cx: dcx, cy: dcy, r: dr*i/4, fill: 'none', stroke: 'rgba(255,255,255,0.15)', strokeWidth: 0.5 }));
      els.push(e('ellipse', { cx: dcx-3, cy: dcy-4, rx: dr*0.25, ry: dr*0.15, fill: 'rgba(255,255,255,0.1)' }));
      els.push(e('circle', { cx: bx+bw*0.2, cy: by+bh*0.78, r: 3, fill: 'none', stroke: '#ff8800', strokeWidth: 0.6, opacity: 0.55 }));
      els.push(e('circle', { cx: bx+bw*0.8, cy: by+bh*0.78, r: 3, fill: 'none', stroke: '#ff8800', strokeWidth: 0.6, opacity: 0.55 }));
      H.pinRow(els, e, bx+bw*0.35, by+bh-4, 3, bw*0.1);
      return els;
    },

    TempHumid(x, y, w, h, c, e, _H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bw2 = w*0.7, bh2 = h*0.75;
      const bx2 = cx - bw2/2, by2 = cy - bh2/2;
      els.push(e('rect', { x: bx2, y: by2, width: bw2, height: bh2, rx: 3,
        fill: 'rgba(255,255,255,0.12)', stroke: c, strokeWidth: 1 }));
      const slotCount = Math.max(3, Math.round(bh2*0.5/5));
      const slotGap = (bh2*0.55) / slotCount;
      for (let i = 0; i < slotCount; i++)
        els.push(e('line', { x1: bx2+bw2*0.15, y1: by2+bh2*0.1+i*slotGap, x2: bx2+bw2*0.85, y2: by2+bh2*0.1+i*slotGap,
          stroke: c, strokeWidth: 0.5, opacity: 0.4 }));
      els.push(e('rect', { x: cx-bw2*0.18, y: by2+bh2*0.2, width: bw2*0.36, height: bh2*0.22, rx: 1,
        fill: '#222', stroke: '#666', strokeWidth: 0.3, opacity: 0.55 }));
      const pinSpacing = bw2*0.18, pinStartX = cx - 1.5*pinSpacing;
      for (let i = 0; i < 4; i++) {
        const pc = i === 2 ? '#333' : '#c8a44e';
        els.push(e('line', { x1: pinStartX+i*pinSpacing, y1: by2+bh2, x2: pinStartX+i*pinSpacing, y2: by2+bh2+7,
          stroke: pc, strokeWidth: 0.8, opacity: 0.6 }));
      }
      els.push(e('text', { x: cx, y: by2+bh2-bh2*0.08, textAnchor: 'middle',
        fill: c, fontSize: 5, opacity: 0.55, fontFamily: 'var(--font-mono)' }, 'DHT22'));
      return els;
    },

    Servo(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bw = w*0.7, bh = h*0.45;
      const bx2 = cx - bw/2, by2 = cy - bh/2 + 2;
      els.push(e('rect', { x: bx2, y: by2, width: bw, height: bh, rx: 2,
        fill: '#1a2a4a', stroke: c, strokeWidth: 1, opacity: 0.8 }));
      const tabY = by2 + bh*0.5;
      els.push(e('rect', { x: bx2-5, y: tabY-2, width: bw+10, height: 4, rx: 1,
        fill: '#1a2a4a', stroke: c, strokeWidth: 0.5, opacity: 0.55 }));
      H.hole(els, e, bx2+bw*0.1-3, tabY, 1.2);
      H.hole(els, e, bx2+bw*0.9+3, tabY, 1.2);
      const gx = bx2 + bw*0.28, gy = by2 - 4;
      els.push(e('circle', { cx: gx, cy: gy, r: 8, fill: '#1a2a4a', stroke: c, strokeWidth: 0.8, opacity: 0.7 }));
      els.push(e('circle', { cx: gx, cy: gy, r: 3, fill: '#222', stroke: '#888', strokeWidth: 0.5, opacity: 0.7 }));
      for (let a = 0; a < 360; a += 30) {
        const rad = a * Math.PI / 180;
        els.push(e('line', { x1: gx+Math.cos(rad)*3.5, y1: gy+Math.sin(rad)*3.5,
          x2: gx+Math.cos(rad)*5, y2: gy+Math.sin(rad)*5,
          stroke: '#888', strokeWidth: 0.4, opacity: 0.5 }));
      }
      const wy = by2+bh, wx = bx2 + bw*0.2;
      els.push(e('line', { x1: wx, y1: wy, x2: wx, y2: wy+8, stroke: '#8B4513', strokeWidth: 1.2, opacity: 0.6 }));
      els.push(e('line', { x1: wx+4, y1: wy, x2: wx+4, y2: wy+8, stroke: '#ff3333', strokeWidth: 1.2, opacity: 0.6 }));
      els.push(e('line', { x1: wx+8, y1: wy, x2: wx+8, y2: wy+8, stroke: '#ff8800', strokeWidth: 1.2, opacity: 0.6 }));
      return els;
    },

    OLED(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, _cy = y+h/2;
      const bx = x+8, by = y+8, bw = w-16, bh = h-16;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+bw*0.09, by+bh*0.09, 1.5);
      H.hole(els, e, bx+bw*0.91, by+bh*0.09, 1.5);
      H.hole(els, e, bx+bw*0.09, by+bh*0.91, 1.5);
      H.hole(els, e, bx+bw*0.91, by+bh*0.91, 1.5);
      const sw = bw*0.82, sh = bh*0.41;
      const sx = bx+(bw-sw)/2, sy = by+bh*0.38;
      els.push(e('rect', { x: sx, y: sy, width: sw, height: sh, rx: 1,
        fill: '#050510', stroke: '#334', strokeWidth: 0.8 }));
      els.push(e('rect', { x: sx+3, y: sy+2, width: sw-6, height: sh-4, rx: 0,
        fill: 'none', stroke: c, strokeWidth: 0.3, opacity: 0.35 }));
      for (let row = 0; row < 3; row++) for (let col = 0; col < 8; col++)
        els.push(e('rect', { x: sx+5+col*((sw-10)/8), y: sy+4+row*((sh-8)/3),
          width: 1.5, height: 1.5, fill: c, opacity: 0.18 }));
      H.pinRow(els, e, bx+bw*0.19, by+bh-4, 4, bw*0.09);
      els.push(e('text', { x: cx, y: by+bh*0.22, textAnchor: 'middle',
        fill: '#666', fontSize: 4.5, opacity: 0.55, fontFamily: 'var(--font-mono)' }, 'SSD1306'));
      return els;
    },

    NeoPixel(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+4, bw = w-16, bh = h-8;
      H.pcb(els, e, bx, by, bw, bh, 1, c);
      const ledCount = 8, ledW = 5, ledH = 5;
      const gap = (bw - 12) / ledCount;
      const rainbow = ['#ff0000','#ff4400','#ff8800','#ffff00','#00ff44','#00aaff','#4400ff','#ff00ff'];
      for (let i = 0; i < ledCount; i++) {
        const lx = bx + 6 + i * gap;
        els.push(e('rect', { x: lx, y: cy-ledH/2, width: ledW, height: ledH, rx: 0.5,
          fill: '#222', stroke: '#555', strokeWidth: 0.4 }));
        els.push(e('rect', { x: lx+1, y: cy-ledH/2+1, width: ledW-2, height: ledH-2, rx: 0.3,
          fill: rainbow[i], opacity: 0.55 }));
      }
      els.push(e('path', { d: `M${bx+bw-8},${by+2} L${bx+bw-4},${by+2}`, stroke: c, strokeWidth: 0.5, opacity: 0.5 }));
      els.push(e('path', { d: `M${bx+bw-5},${by+1} L${bx+bw-4},${by+2} L${bx+bw-5},${by+3}`, fill: c, opacity: 0.5 }));
      return els;
    },

    Buzzer(x, y, w, h, c, e, _H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const r = Math.min(w, h) * 0.46;  // W1.5:圓形蜂鳴器填滿 footprint(原 0.32 縮在中央→接點懸空)
      els.push(e('circle', { cx, cy, r, fill: '#0a0a0a', stroke: c, strokeWidth: 1.2, opacity: 0.75 }));
      els.push(e('circle', { cx, cy, r: r*0.65, fill: 'none', stroke: c, strokeWidth: 0.5, opacity: 0.4 }));
      els.push(e('circle', { cx, cy, r: r*0.35, fill: 'none', stroke: c, strokeWidth: 0.5, opacity: 0.3 }));
      els.push(e('circle', { cx, cy, r: r*0.12, fill: '#222', stroke: '#666', strokeWidth: 0.4, opacity: 0.7 }));
      els.push(e('text', { x: cx-r*0.5, y: cy-r*0.3, fill: c, fontSize: 7, opacity: 0.6, fontWeight: 700 }, '+'));
      els.push(e('line', { x1: cx-3, y1: cy+r, x2: cx-3, y2: cy+r+6, stroke: '#c8a44e', strokeWidth: 0.8, opacity: 0.6 }));
      els.push(e('line', { x1: cx+3, y1: cy+r, x2: cx+3, y2: cy+r+6, stroke: '#c8a44e', strokeWidth: 0.8, opacity: 0.6 }));
      return els;
    },

    LED_Single(x, y, w, h, c, e, H) {
      return COMP_RENDERERS._led(x, y, w, h, c, e, H, false);
    },
    LED_RGB(x, y, w, h, c, e, H) {
      return COMP_RENDERERS._led(x, y, w, h, c, e, H, true);
    },
    _led(x, y, w, h, c, e, H, isRgb) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const r = Math.min(w, h) * 0.28;
      const ledColor = isRgb ? '#ffffff' : c;
      els.push(e('circle', { cx, cy, r, fill: ledColor, opacity: 0.15, stroke: ledColor, strokeWidth: 1.2 }));
      els.push(e('circle', { cx, cy, r: r*0.6, fill: ledColor, opacity: 0.22 }));
      els.push(e('line', { x1: cx-r*0.7, y1: cy+r*0.7, x2: cx+r*0.3, y2: cy+r*0.7,
        stroke: ledColor, strokeWidth: 1.5, opacity: 0.5 }));
      const leads = isRgb ? ['#ff3333','#33ff33','#3333ff','#888'] : [ledColor, '#888'];
      const lw = (r*1.4) / leads.length;
      for (let i = 0; i < leads.length; i++) {
        const lx = cx - r*0.7 + i*lw + lw/2;
        els.push(e('line', { x1: lx, y1: cy+r, x2: lx, y2: cy+r+8,
          stroke: leads[i], strokeWidth: 0.8, opacity: 0.6 }));
      }
      return els;
    },

    DCMotor(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+6, by = y+6, bw = w*0.55, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const hx = bx+4, hy = by+4, hw = bw*0.4, hh = bh-8;
      els.push(e('rect', { x: hx, y: hy, width: hw, height: hh, rx: 1,
        fill: '#1a1a1a', stroke: '#888', strokeWidth: 0.8, opacity: 0.7 }));
      for (let i = 0; i < 5; i++)
        els.push(e('line', { x1: hx+2, y1: hy+3+i*(hh-6)/4, x2: hx+hw-2, y2: hy+3+i*(hh-6)/4,
          stroke: '#666', strokeWidth: 0.4, opacity: 0.5 }));
      // Q1(2026-06-08):移除硬編端子裝飾(M+/M- 真腳由 SOUTH port marker 畫,見 SCHEM_PINS)。
      const mr = Math.min(w*0.18, h*0.3);
      const mcx = x+w-mr-8, mcy = cy;
      els.push(e('circle', { cx: mcx, cy: mcy, r: mr, fill: '#1a1a2a', stroke: c, strokeWidth: 1, opacity: 0.75 }));
      els.push(e('text', { x: mcx, y: mcy+3, textAnchor: 'middle', fill: c, fontSize: 9, fontWeight: 700, opacity: 0.55 }, 'M'));
      els.push(e('circle', { cx: mcx, cy: mcy, r: 2, fill: '#888', opacity: 0.6 }));
      return els;
    },

    Stepper(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+6, by = y+6, bw = w-12, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+4, by+4, 1.8);
      H.hole(els, e, bx+bw-4, by+4, 1.8);
      const mr = Math.min(bw, bh) * 0.32;
      const mcx2 = bx+bw*0.6, mcy2 = cy;
      els.push(e('circle', { cx: mcx2, cy: mcy2, r: mr, fill: '#1a1a2a', stroke: c, strokeWidth: 1.2, opacity: 0.75 }));
      els.push(e('circle', { cx: mcx2, cy: mcy2, r: mr*0.6, fill: 'none', stroke: c, strokeWidth: 0.5, opacity: 0.35 }));
      els.push(e('circle', { cx: mcx2, cy: mcy2, r: 2.5, fill: '#888', opacity: 0.6 }));
      for (let a = 0; a < 360; a += 45) {
        const rad = a * Math.PI / 180;
        els.push(e('line', { x1: mcx2+Math.cos(rad)*3.5, y1: mcy2+Math.sin(rad)*3.5,
          x2: mcx2+Math.cos(rad)*mr*0.55, y2: mcy2+Math.sin(rad)*mr*0.55,
          stroke: '#888', strokeWidth: 0.5, opacity: 0.4 }));
      }
      const dw = bw*0.28, dh = bh*0.7;
      const dx = bx+4, dy = cy-dh/2;
      els.push(e('rect', { x: dx, y: dy, width: dw, height: dh, rx: 1.5,
        fill: '#0a1a2a', stroke: '#4466aa', strokeWidth: 0.8, opacity: 0.7 }));
      H.ic(els, e, dx+2, dy+2, dw-4, dh-4, 4, 'ULN');
      H.pinRow(els, e, bx+3, by+bh*0.15, 4, bh*0.22);
      return els;
    },

    Light(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const lr = Math.min(bw, bh) * 0.28;
      els.push(e('circle', { cx: bx+bw*0.35, cy: cy, r: lr, fill: '#2a1a0a', stroke: '#c8664e', strokeWidth: 1, opacity: 0.7 }));
      els.push(e('path', {
        d: `M${bx+bw*0.35-lr*0.5},${cy} L${bx+bw*0.35-lr*0.2},${cy-lr*0.35} L${bx+bw*0.35+lr*0.2},${cy+lr*0.35} L${bx+bw*0.35+lr*0.5},${cy}`,
        stroke: '#c8664e', fill: 'none', strokeWidth: 0.7, opacity: 0.55 }));
      els.push(e('circle', { cx: bx+bw*0.72, cy: cy, r: 5, fill: 'none', stroke: '#4499ff', strokeWidth: 0.7, opacity: 0.6 }));
      els.push(e('line', { x1: bx+bw*0.72, y1: cy-2, x2: bx+bw*0.72+2, y2: cy+2,
        stroke: '#4499ff', strokeWidth: 0.7, opacity: 0.6 }));
      H.pinRow(els, e, bx+3, by+bh*0.2, 4, bh*0.2);
      return els;
    },

    Speaker(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+8, bw = w-16, bh = h-16;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.ic(els, e, bx+bw*0.15, cy-8, 18, 16, 5, '');
      els.push(e('rect', { x: bx+bw-22, y: cy-8, width: 18, height: 16, rx: 1.5,
        fill: '#1a1a2a', stroke: '#aaa', strokeWidth: 0.7, opacity: 0.7 }));
      els.push(e('rect', { x: bx+bw-20, y: cy-5, width: 12, height: 10, rx: 1,
        fill: '#222', stroke: '#888', strokeWidth: 0.4, opacity: 0.6 }));
      els.push(e('text', { x: bx+bw-14, y: cy+2, textAnchor: 'middle',
        fill: '#888', fontSize: 4, opacity: 0.55 }, 'SD'));
      H.pinRow(els, e, bx+2, by+3, 8, (bh-6)/7);
      H.pinRow(els, e, bx+bw-4, by+3, 8, (bh-6)/7);
      return els;
    },

    LCD(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, _cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+bw*0.03, by+bh*0.07, 1.8);
      H.hole(els, e, bx+bw*0.97, by+bh*0.07, 1.8);
      H.hole(els, e, bx+bw*0.03, by+bh*0.93, 1.8);
      H.hole(els, e, bx+bw*0.97, by+bh*0.93, 1.8);
      const sw = bw*0.8, sh = bh*0.39;
      const sx = bx+(bw-sw)/2, sy = by+bh*0.3;
      els.push(e('rect', { x: sx, y: sy, width: sw, height: sh, rx: 2,
        fill: '#1a2a0a', stroke: '#4a6a2a', strokeWidth: 0.8 }));
      for (let row = 0; row < 2; row++) for (let col = 0; col < 16; col++)
        els.push(e('rect', { x: sx+3+col*((sw-6)/16), y: sy+3+row*((sh-6)/2),
          width: (sw-6)/16-1, height: (sh-6)/2-1, rx: 0.3, fill: '#3a5a1a', opacity: 0.3 }));
      const ix = bx+bw*0.02, iy = by+bh-10, iw = bw*0.25, ih = 8;
      els.push(e('rect', { x: ix, y: iy, width: iw, height: ih, rx: 1,
        fill: '#0a1a3a', stroke: '#4466aa', strokeWidth: 0.5, opacity: 0.6 }));
      els.push(e('text', { x: ix+iw/2, y: iy+ih-2, textAnchor: 'middle',
        fill: '#4466aa', fontSize: 4, opacity: 0.55, fontFamily: 'var(--font-mono)' }, 'I2C'));
      H.pinRow(els, e, bx+3, by+bh*0.15, 4, bh*0.2);
      return els;
    },

    MSGEQ7(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const iw = bw*0.7, ih = bh*0.6;
      const ix = cx-iw/2, iy = cy-ih/2;
      H.ic(els, e, ix, iy, iw, ih, 4, 'MSGEQ7');
      els.push(e('path', { d: `M${ix+iw/2-3},${iy} a3,3 0 0,1 6,0`,
        fill: 'none', stroke: '#667', strokeWidth: 0.6, opacity: 0.6 }));
      H.pinRow(els, e, ix-2, iy+2, 4, (ih-4)/3);
      H.pinRow(els, e, ix+iw+2, iy+2, 4, (ih-4)/3);
      els.push(e('rect', { x: ix-8, y: iy+2, width: 4, height: 6, rx: 0.5,
        fill: '#3a2a0a', stroke: '#aa8844', strokeWidth: 0.4, opacity: 0.6 }));
      return els;
    },

    Button(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      const sw = Math.min(bw, bh) * 0.55;
      els.push(e('rect', { x: cx-sw/2, y: cy-sw/2, width: sw, height: sw, rx: 1.5,
        fill: '#1a1a1a', stroke: '#888', strokeWidth: 0.8, opacity: 0.8 }));
      els.push(e('circle', { cx, cy, r: sw*0.28, fill: '#333', stroke: '#aaa', strokeWidth: 0.6, opacity: 0.7 }));
      const pd = sw*0.35;
      [[-1,-1],[1,-1],[-1,1],[1,1]].forEach(([dx,dy]) => {
        els.push(e('rect', { x: cx+dx*pd-1.5, y: cy+dy*pd-1.5, width: 3, height: 3, rx: 0.3,
          fill: '#c8a44e', opacity: 0.55 }));
      });
      return els;
    },

    Switch(x, y, w, h, c, e, H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, cx, cy-bh*0.1, bh*0.18);
      const sw2 = bw*0.5, sh2 = bh*0.4;
      els.push(e('rect', { x: cx-sw2/2, y: cy-sh2/2-2, width: sw2, height: sh2, rx: 2,
        fill: '#2a2a2a', stroke: '#aaa', strokeWidth: 0.8, opacity: 0.75 }));
      const levY = cy - sh2/2 - 2;
      els.push(e('line', { x1: cx, y1: levY, x2: cx+sw2*0.25, y2: levY-bh*0.2,
        stroke: '#ccc', strokeWidth: 2, opacity: 0.7, strokeLinecap: 'round' }));
      els.push(e('circle', { cx: cx+sw2*0.25, cy: levY-bh*0.2, r: 2, fill: '#ddd', opacity: 0.65 }));
      const tSpacing = bw*0.14;
      for (let i = 0; i < 3; i++)
        els.push(e('rect', { x: cx-tSpacing+i*tSpacing-2, y: cy+sh2/2+2, width: 4, height: 4, rx: 0.5,
          fill: '#c8a44e', opacity: 0.6 }));
      return els;
    },

    BatteryAA(x, y, w, h, c, e, H) {
      // W1.5(2026-06-08):2×AA 座填滿 footprint bbox(=真 1:1 投影);真 port marker 畫腳。
      const els = [];
      const bx2 = x+3, by2 = y+4, bw = w-6, bh = h-8;
      els.push(e('rect', { x: bx2, y: by2, width: bw, height: bh, rx: 4,
        fill: '#0a0a08', stroke: c, strokeWidth: 1.3, opacity: 0.85 }));
      H.hole(els, e, bx2+bw*0.05, by2+bh*0.12, 1.4);
      H.hole(els, e, bx2+bw*0.95, by2+bh*0.88, 1.4);
      const cellW = (bw-12)/2, cellH = bh-10;
      for (let i = 0; i < 2; i++) {
        const cx2 = bx2+4+i*(cellW+4), cy2 = by2+5;
        els.push(e('rect', { x: cx2, y: cy2, width: cellW, height: cellH, rx: 2,
          fill: '#1a1a14', stroke: '#888', strokeWidth: 0.6, opacity: 0.6 }));
        els.push(e('rect', { x: cx2+cellW/2-2, y: cy2-1, width: 4, height: 3, rx: 1,
          fill: '#d4a84e', opacity: 0.65 }));
        els.push(e('line', { x1: cx2+2, y1: cy2+cellH, x2: cx2+cellW-2, y2: cy2+cellH,
          stroke: '#d4a84e', strokeWidth: 1.5, opacity: 0.5 }));
        els.push(e('text', { x: cx2+cellW/2, y: cy2+6, textAnchor: 'middle',
          fill: c, fontSize: 7, opacity: 0.55, fontWeight: 700 }, '+'));
        els.push(e('text', { x: cx2+cellW/2, y: cy2+cellH-2, textAnchor: 'middle',
          fill: '#aaa', fontSize: 7, opacity: 0.5, fontWeight: 700 }, '−'));
      }
      // Q1(2026-06-08):移除硬編 +/− 飛線裝飾(與真 SOUTH port 脫鉤);腳由真 port marker 畫。
      return els;
    },

    BatteryLiPo(x, y, w, h, c, e, _H) {
      const els = [], cx = x+w/2, cy = y+h/2;
      const bw = w*0.6, bh = h*0.65;
      const bx2 = cx - bw/2, by2 = cy - bh/2;
      els.push(e('rect', { x: bx2, y: by2, width: bw, height: bh, rx: 4,
        fill: '#0a1a3a', stroke: '#4466aa', strokeWidth: 1, opacity: 0.75 }));
      els.push(e('text', { x: cx, y: cy-2, textAnchor: 'middle',
        fill: '#4466aa', fontSize: 7, opacity: 0.6, fontFamily: 'var(--font-mono)' }, 'LiPo'));
      els.push(e('text', { x: cx, y: cy+7, textAnchor: 'middle',
        fill: '#4466aa', fontSize: 6, opacity: 0.45, fontFamily: 'var(--font-mono)' }, '3.7V'));
      els.push(e('rect', { x: cx-8, y: by2-3, width: 5, height: 5, rx: 0.5,
        fill: '#c8a44e', opacity: 0.6 }));
      els.push(e('rect', { x: cx+3, y: by2-3, width: 5, height: 5, rx: 0.5,
        fill: '#c8a44e', opacity: 0.6 }));
      els.push(e('rect', { x: bx2+bw-2, y: cy-4, width: 8, height: 8, rx: 1,
        fill: '#eee', stroke: '#999', strokeWidth: 0.5, opacity: 0.6 }));
      return els;
    },

    USB5V(x, y, w, h, c, e, H) {
      const els = [], _cx = x+w/2, cy = y+h/2;
      const bx = x+8, by = y+6, bw = w-16, bh = h-12;
      H.pcb(els, e, bx, by, bw, bh, 2, c);
      H.hole(els, e, bx+4, by+4, 1.5);
      H.hole(els, e, bx+bw-4, by+bh-4, 1.5);

      // USB-A connector (left side)
      const usbX = bx + 3, usbCy = cy, usbW = 14, usbH = 10;
      els.push(e('rect', { x: usbX, y: usbCy-usbH/2, width: usbW, height: usbH, rx: 1.5,
        fill: '#111', stroke: '#aaa', strokeWidth: 1, opacity: 0.85 }));
      els.push(e('rect', { x: usbX+2, y: usbCy-usbH/2+2, width: usbW-4, height: usbH-4, rx: 0.5,
        fill: '#222', stroke: '#666', strokeWidth: 0.3, opacity: 0.8 }));
      // USB pins (4 gold contacts)
      for (let i = 0; i < 4; i++)
        els.push(e('rect', { x: usbX+4+i*2.5, y: usbCy-1.5, width: 1.5, height: 3, rx: 0.2,
          fill: '#c8a44e', opacity: 0.75 }));

      // Voltage regulator chip (center-right)
      const vrX = bx+bw*0.42, vrY = by+bh*0.25, vrW = bw*0.32, vrH = bh*0.5;
      els.push(e('rect', { x: vrX, y: vrY, width: vrW, height: vrH, rx: 1.5,
        fill: '#0a0a18', stroke: '#666', strokeWidth: 0.8, opacity: 0.75 }));
      els.push(e('circle', { cx: vrX+3, cy: vrY+3, r: 1, fill: '#888', opacity: 0.5 }));
      // Tiny IC pin stubs
      for (let i = 0; i < 3; i++) {
        const py = vrY + 4 + i * (vrH-8)/2;
        els.push(e('line', { x1: vrX-3, y1: py, x2: vrX, y2: py, stroke: '#888', strokeWidth: 0.5, opacity: 0.4 }));
        els.push(e('line', { x1: vrX+vrW, y1: py, x2: vrX+vrW+3, y2: py, stroke: '#888', strokeWidth: 0.5, opacity: 0.4 }));
      }

      // "5V" label (prominent, schematic standard)
      els.push(e('text', { x: bx+bw*0.78, y: cy-3, textAnchor: 'middle',
        fill: c, fontSize: 11, fontWeight: 800, fontFamily: 'var(--font-mono)', opacity: 0.9 }, '5V'));

      // ⚡ lightning bolt (SVG path) — schematic power symbol
      const boltCx = bx+bw*0.78, boltY = cy+6;
      els.push(e('path', {
        d: `M${boltCx-2},${boltY} L${boltCx+1},${boltY+5} L${boltCx},${boltY+5} L${boltCx+2},${boltY+10} L${boltCx-1},${boltY+5} L${boltCx},${boltY+5} Z`,
        fill: c, opacity: 0.75 }));

      // Output screw terminals (right side)
      const tW = 6, tH = 5;
      [['V+', '#ff4444', cy-6], ['GND', '#555', cy+4]].forEach(([_lbl, col, ty]) => {
        els.push(e('rect', { x: bx+bw-8, y: ty, width: tW, height: tH, rx: 0.5,
          fill: '#1a2a1a', stroke: col, strokeWidth: 0.7, opacity: 0.7 }));
        els.push(e('circle', { cx: bx+bw-5, cy: ty+tH/2, r: 1.2, fill: '#0a0a0a', stroke: '#888', strokeWidth: 0.4 }));
      });

      // Power indicator LED (green dot)
      els.push(e('circle', { cx: bx+bw*0.25, cy: by+bh*0.18, r: 2.5,
        fill: '#00cc44', opacity: 0.6, stroke: '#00aa33', strokeWidth: 0.5 }));

      return els;
    },

  }; // end COMP_RENDERERS

  // ── Dispatcher: _compDecor with helpers ──
  function _compDecor(compKey, x, y, w, h, c) {
    const e = (tag, props, ...ch) => React.createElement(tag, props, ...ch);
    const H = {
      pcb(els, el, bx, by, bw, bh, rx, col) {
        els.push(el('rect', { x: bx, y: by, width: bw, height: bh, rx: rx||3,
          fill: '#0a2210', stroke: col, strokeWidth: 1, opacity: 0.7 }));
        els.push(el('rect', { x: bx+1.5, y: by+1.5, width: bw-3, height: bh-3, rx: (rx||3)-1,
          fill: 'none', stroke: col, strokeWidth: 0.4, opacity: 0.2 }));
      },
      hole(els, el, hx, hy, r) {
        els.push(el('circle', { cx: hx, cy: hy, r: r||2, fill: '#0a0a0a', stroke: '#777', strokeWidth: 0.6, opacity: 0.6 }));
      },
      pinRow(_els, _el, _px, _py, _count, _spacing) {
        // Q1(2026-06-08):元件腳統一由 SVG 真 port marker 畫(SCHEM_PINS 單一真相)。
        // glyph 不再自繪 pin header 裝飾腳(原硬編座標與真 port 脫鉤 → 線接不到畫出的腳)。
        // 保留簽名相容所有呼叫端;no-op。
      },
      ic(els, el, ix, iy, iw, ih, pins, label) {
        els.push(el('rect', { x: ix, y: iy, width: iw, height: ih, rx: 1.5,
          fill: '#0a0a14', stroke: '#777', strokeWidth: 0.8 }));
        els.push(el('circle', { cx: ix+3, cy: iy+3, r: 1.2, fill: '#aaa', opacity: 0.6 }));
        const pCount = pins || 4;
        for (let i = 0; i < pCount; i++) {
          const py = iy + 3 + i * ((ih-6) / Math.max(pCount-1, 1));
          els.push(el('line', { x1: ix-2, y1: py, x2: ix, y2: py, stroke: '#aaa', strokeWidth: 0.6, opacity: 0.5 }));
          els.push(el('line', { x1: ix+iw, y1: py, x2: ix+iw+2, y2: py, stroke: '#aaa', strokeWidth: 0.6, opacity: 0.5 }));
        }
        if (label) els.push(el('text', { x: ix+iw/2, y: iy+ih/2+3, textAnchor: 'middle',
          fill: '#ccc', fontSize: 5, opacity: 0.55, fontFamily: 'var(--font-mono)' }, label));
      },
    };

    // W-Render-Real(2026-06-08):資料驅動「真實原件投影」為主 —— 從 SSOT 子元件幾何
    // (COMPONENT_DIMENSIONS[<class>].ports:cx/cy/shape/bodyW,1:1)畫真實外觀。compKey→class
    // 橋接由 window.COMPKEY_TO_CLASS(schematic-pins.js 輸出,鏡像後端 SHORT_TO_CLASS)。
    // 手刻 stylized glyph(COMP_RENDERERS)退為「該 class 無子元件投影資料」時的 fallback。
    const cls = (window.COMPKEY_TO_CLASS && window.COMPKEY_TO_CLASS[compKey]) || compKey;
    const real = _genericPortDecor(cls, x, y, w, h, e, true);  // flipY:非 MCU footprint 翻正對 datasheet/3D(P0.5 #8)
    if (real && real.length) return real;
    // fallback:無 class 子元件資料 → 暫用手刻 glyph(逐步退役,見「手刻普查 + 預防閘」TODO)
    // 手刻 glyph(COMP_RENDERERS)以 SVG y-down 自繪、非資料驅動 → 不套 flipY(本就正立)。
    const renderer = COMP_RENDERERS[compKey];
    if (renderer) return renderer(x, y, w, h, c, e, H);
    return _genericPortDecor(compKey, x, y, w, h, e, true);  // flipY:資料驅動路徑同樣翻正
  }

  // 從 component-dimensions.js 的 ports(cx/cy mm + shape + params.bodyW/bodyD)畫 2D 子元件。
  // no-fallback:未知 shape → 醒目洋紅虛線標記(不靜默畫成普通方塊);無資料 → 回 []。
  function _genericPortDecor(compKey, x, y, w, h, e, flipY) {
    const dims = window.COMPONENT_DIMENSIONS && window.COMPONENT_DIMENSIONS[compKey];
    if (!dims || !Array.isArray(dims.ports) || !dims.l || !dims.w) return [];
    const Lmm = dims.l, Wmm = dims.w, els = [];
    const sx = (cx) => x + (cx / Lmm) * w;
    // flipY:SSOT cx/cy 原點為 PCB 左下角(y-up,見 verified.json _meta.coordinate_origin);
    // SVG 為 y-down。flipY=true 把 cy 翻成 top-view,與 3D scene-3d 的 z=-(cy-W/2) 及 datasheet
    // silkscreen 同向。非 MCU footprint(_compDecor)傳 true 修正鏡像;MCU(_realProjection)用
    // 預設 false,其翻正由外層 matrix(0,-1,-1,0,…)處理,於此再翻會 double-flip(P0.5 #8)。
    const sy = (cy) => flipY ? (y + h - (cy / Wmm) * h) : (y + (cy / Wmm) * h);
    const szx = (mm) => Math.max(mm * w / Lmm, 1.2);
    const szy = (mm) => Math.max(mm * h / Wmm, 1.2);
    for (const p of dims.ports) {
      if (p.cx == null || p.cy == null) continue;
      const px = sx(p.cx), py = sy(p.cy);
      const pr = (p.params && p.params.bodyW) || 2, pd = (p.params && p.params.bodyD) || 2;
      const bw = szx(pr), bh = szy(pd), col = p.color || '#888', shp = String(p.shape || '');  // nofallback-ok: port 裝飾 UI 色(b 類),灰色=未指定;幾何 bw/bh 由 szx/szy 真值算
      if (shp.indexOf('led') === 0) {
        els.push(e('circle', { cx: px, cy: py, r: Math.max(Math.min(bw, bh) / 2, 1.2),
          fill: col, opacity: 0.75, stroke: '#000', strokeWidth: 0.3 }));
      } else if (shp.indexOf('ic') === 0) {
        els.push(e('rect', { x: px - bw / 2, y: py - bh / 2, width: bw, height: bh, rx: 0.5,
          fill: '#0a0a14', stroke: '#888', strokeWidth: 0.5 }));
        els.push(e('circle', { cx: px - bw / 2 + 1.2, cy: py - bh / 2 + 1.2, r: 0.7, fill: '#aaa', opacity: 0.6 }));
      } else if (shp.indexOf('mount') === 0 || shp.indexOf('hole') >= 0) {
        // mounting hole → 鍍通孔環(非實心方塊,符合真實外觀)
        const _hr = Math.max(Math.min(bw, bh) / 2, 1);
        els.push(e('circle', { cx: px, cy: py, r: _hr, fill: '#0a0a0a', stroke: '#777', strokeWidth: 0.5, opacity: 0.5 }));
      } else if (/^(conn|display|pcb|sensor|relay|motor|battery|cap|res|crystal|button|buzzer|pot|heatsink|toggle|vreg|cylinder|box|dome|pump|slide)/.test(shp)) {
        els.push(e('rect', { x: px - bw / 2, y: py - bh / 2, width: bw, height: bh, rx: 0.5,
          fill: col, opacity: 0.5, stroke: '#000', strokeWidth: 0.3 }));
      } else {
        // no-fallback:渲染器/2D-map 未知的 shape → 醒目標記,絕不靜默頂替
        els.push(e('rect', { x: px - bw / 2, y: py - bh / 2, width: Math.max(bw, 2), height: Math.max(bh, 2),
          fill: 'none', stroke: '#ff00ff', strokeWidth: 0.8, strokeDasharray: '2 1' }));
        els.push(e('text', { x: px, y: py - bh / 2 - 1, textAnchor: 'middle',
          fill: '#ff00ff', fontSize: 3, fontFamily: 'var(--font-mono)' }, '?' + shp));
      }
    }
    return els;
  }

  // W-Render-Real:供 MCU(schematic-elk._mcuDecor)等以 class 直接取資料驅動真投影子元件。
  function _realProjection(classKey, x, y, w, h) {
    const e = (tag, props, ...ch) => React.createElement(tag, props, ...ch);
    return _genericPortDecor(classKey, x, y, w, h, e);
  }
  window._realProjection = _realProjection;
  window._compDecor = _compDecor;
})();
