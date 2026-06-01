// shapes-passive-mech.js — Three.js shape factory: passive components & mechanical parts
// Builder signature: (w, h, d, sc, color, opts) → THREE.Group, bottom at Y=0
(() => {
const T = window.THREE;

// ── Material helpers ──────────────────────────────────────────────────────────
const matPlastic  = c => new T.MeshStandardMaterial({ color: c, roughness: 0.75, metalness: 0.0 });
const matMetal    = c => new T.MeshStandardMaterial({ color: c, roughness: 0.3,  metalness: 0.7 });
const matCeramic  = c => new T.MeshStandardMaterial({ color: c, roughness: 0.6,  metalness: 0.1 });
const matMotor    = c => new T.MeshStandardMaterial({ color: c, roughness: 0.4,  metalness: 0.5 });
const matTransluc = (c, o = 0.75) =>
  new T.MeshStandardMaterial({ color: c, roughness: 0.3, metalness: 0.0, transparent: true, opacity: o });

// ── Geometry helpers ──────────────────────────────────────────────────────────
const box = (w, h, d)         => new T.BoxGeometry(w, h, d);
const cyl = (rt, rb, h, s=16) => new T.CylinderGeometry(rt, rb, h, s);
const mk  = (geo, mat)        => new T.Mesh(geo, mat);

// Wire-lead helper: N leads evenly spaced along X, hanging below Y=0
function addLeads(g, sc, n, spacing, len = 3) {
  const mat = matMetal('#aaaaaa'), half = ((n - 1) * spacing) / 2;
  for (let i = 0; i < n; i++) {
    const m = mk(cyl(0.3 * sc, 0.3 * sc, len * sc, 6), mat);
    m.position.set((i * spacing - half) * sc, -len * sc / 2, 0);
    g.add(m);
  }
}

// ── 1. Electrolytic capacitor ─────────────────────────────────────────────────
function buildCapElectrolytic(w, h, d, sc, color) {
  const g = new T.Group(), r = w / 2 * sc, ht = d * sc;
  const body = mk(cyl(r, r, ht, 24), matPlastic(color));
  body.position.y = ht / 2; g.add(body);
  // Polarity stripe
  const stripe = mk(new T.CylinderGeometry(r * 1.002, r * 1.002, ht * 0.85, 24, 1, true, -0.3, 0.6), matPlastic('#cccccc'));
  stripe.position.y = ht / 2; g.add(stripe);
  // Aluminum top + cross scoring
  const top = mk(cyl(r, r, 0.5 * sc, 24), matMetal('#b8b8b8'));
  top.position.y = ht + 0.25 * sc; g.add(top);
  for (let i = 0; i < 2; i++) {
    const s = mk(box(r * 1.6, 0.12 * sc, 0.08 * sc), matMetal('#888888'));
    s.position.set(0, ht + 0.5 * sc, 0); if (i) s.rotation.y = Math.PI / 2; g.add(s);
  }
  addLeads(g, sc, 2, 0.8, 3); return g;
}

// ── 2. Ceramic SMD capacitor ──────────────────────────────────────────────────
function buildCapCeramic(w, h, d, sc, _color) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matCeramic('#c4a035'));
  body.position.y = bh / 2; g.add(body);
  const pw = 0.45 * sc, pm = matMetal('#c0c0c0');
  for (const x of [-bw / 2 - pw / 2, bw / 2 + pw / 2]) {
    const p = mk(box(pw, bh * 0.9, bd), pm); p.position.set(x, bh / 2, 0); g.add(p);
  }
  return g;
}

// ── 3. SMD resistor ───────────────────────────────────────────────────────────
function buildResSmd(w, h, d, sc) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic('#333333'));
  body.position.y = bh / 2; g.add(body);
  const pw = 0.4 * sc, pm = matMetal('#c0c0c0');
  for (const x of [-bw / 2 - pw / 2, bw / 2 + pw / 2]) {
    const p = mk(box(pw, bh * 0.9, bd), pm); p.position.set(x, bh / 2, 0); g.add(p);
  }
  return g;
}

// ── 4. Trimmer potentiometer ──────────────────────────────────────────────────
function buildPotTrimmer(w, h, d, sc, _color) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic('#2563eb'));
  body.position.y = bh / 2; g.add(body);
  const sm = matPlastic('#e0e0e0');
  for (let i = 0; i < 2; i++) {
    const s = mk(box(bw * 0.5, 0.3 * sc, 0.1 * sc), sm);
    s.position.set(0, bh + 0.15 * sc, 0); if (i) s.rotation.y = Math.PI / 2; g.add(s);
  }
  addLeads(g, sc, 3, 2, 2.5); return g;
}

// ── 5. Panel-mount potentiometer with shaft ───────────────────────────────────
function buildPotShaft(w, h, d, sc) {
  const g = new T.Group(), r = w / 2 * sc, bh = d * sc;
  const body = mk(cyl(r, r, bh, 24), matPlastic('#1a1a1a'));
  body.position.y = bh / 2; g.add(body);
  const sh = 15 * sc, sr = 3 * sc;
  const shaft = mk(cyl(sr, sr, sh, 12), matMetal('#b0b0b0'));
  shaft.position.y = bh + sh / 2; g.add(shaft);
  addLeads(g, sc, 3, 5, 3); return g;
}

// ── 6. Relay ──────────────────────────────────────────────────────────────────
function buildRelay(w, h, d, sc) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic('#1e3a5f'));
  body.position.y = bh / 2; g.add(body);
  const lbl = mk(box(bw * 0.75, 0.1 * sc, bd * 0.6), matPlastic('#2a4a6f'));
  lbl.position.set(0, bh + 0.05 * sc, 0); g.add(lbl);
  const pm = matMetal('#aaaaaa'), ph = 2.5 * sc;
  [-2, -1, 0, 1, 2].forEach((i, idx) => {
    const p = mk(box(0.8 * sc, ph, 0.4 * sc), pm);
    p.position.set(i * 2.5 * sc, -ph / 2, (idx < 2 ? -1 : 1) * bd * 0.2); g.add(p);
  });
  return g;
}

// ── 7. HC-49 crystal oscillator ───────────────────────────────────────────────
function buildCrystalHc49(w, h, d, sc) {
  const g = new T.Group(), cw = w * sc, ch = d * sc, cd = h * sc;
  const can = mk(cyl(cw / 2, cw / 2, ch, 16), matMetal('#c0c0c0'));
  can.scale.set(1, 1, cd / cw); can.position.y = ch / 2; g.add(can);
  const base = mk(cyl(cw / 2, cw / 2, 0.4 * sc, 16), matMetal('#909090'));
  base.scale.set(1, 1, cd / cw); base.position.y = 0.2 * sc; g.add(base);
  addLeads(g, sc, 2, 0.6, 3); return g;
}

// ── 8. Tactile pushbutton ─────────────────────────────────────────────────────
function buildButtonTactile(w, h, d, sc, color) {
  const g = new T.Group(), bw = w * sc, bh = 3.5 * sc, bd = h * sc;
  const base = mk(box(bw, bh, bd), matPlastic('#333333'));
  base.position.y = bh / 2; g.add(base);
  const cap = mk(cyl(1.75 * sc, 1.75 * sc, 1.5 * sc, 12), matPlastic(color));
  cap.position.y = bh + 0.75 * sc; g.add(cap);
  const pm = matMetal('#aaaaaa'), ph = 2.5 * sc;
  [[-bw/2-sc, -bd*0.25], [-bw/2-sc, bd*0.25], [bw/2+sc, -bd*0.25], [bw/2+sc, bd*0.25]]
    .forEach(([x, z]) => {
      const p = mk(cyl(0.3 * sc, 0.3 * sc, ph, 6), pm);
      p.position.set(x, -ph / 2, z); g.add(p);
    });
  return g;
}

// ── 9. Piezo buzzer ───────────────────────────────────────────────────────────
function buildBuzzer(w, h, d, sc) {
  const g = new T.Group(), r = w / 2 * sc, ht = d * sc;
  const body = mk(cyl(r, r, ht, 24), matPlastic('#111111'));
  body.position.y = ht / 2; g.add(body);
  const hole = mk(cyl(r * 0.18, r * 0.18, 0.3 * sc, 12), matPlastic('#000000'));
  hole.position.y = ht + 0.1 * sc; g.add(hole);
  // (+) marking: horizontal bar
  const bar = mk(box(r * 0.8, 0.1 * sc, 0.15 * sc), matPlastic('#ffffff'));
  bar.position.set(r * 0.45, ht + 0.05 * sc, 0); g.add(bar);
  addLeads(g, sc, 2, 0.6, 2.5); return g;
}

// ── 10. Through-hole LED (5mm) ────────────────────────────────────────────────
function buildLedTht(w, h, d, sc, color) {
  const g = new T.Group(), r = w / 2 * sc, bh = 1.5 * sc;
  const base = mk(cyl(r, r, bh, 16), matPlastic('#e8e8e8'));
  base.position.y = bh / 2; g.add(base);
  const dome = mk(new T.SphereGeometry(r, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2), matTransluc(color, 0.8));
  dome.position.y = bh; g.add(dome);
  // Flat cathode notch
  const notch = mk(box(0.2 * sc, bh * 0.7, r * 0.4), matPlastic('#cccccc'));
  notch.position.set(r - 0.1 * sc, bh / 2, 0); g.add(notch);
  addLeads(g, sc, 2, 0.7, 5); return g;
}

// ── 11. SMD LED (0805) ────────────────────────────────────────────────────────
function buildLedSmd(w, h, d, sc, color) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic('#e8e8e8'));
  body.position.y = bh / 2; g.add(body);
  const lens = mk(box(bw * 0.55, 0.1 * sc, bd * 0.7), matTransluc(color, 0.75));
  lens.position.set(0, bh + 0.05 * sc, 0); g.add(lens);
  const pw = 0.35 * sc, pm = matMetal('#c0c0c0');
  for (const x of [-bw / 2 - pw / 2, bw / 2 + pw / 2]) {
    const p = mk(box(pw, bh * 0.85, bd), pm); p.position.set(x, bh / 2, 0); g.add(p);
  }
  return g;
}

// ── 12. TO-220 voltage regulator ──────────────────────────────────────────────
function buildVregTo220(w, h, d, sc) {
  const g = new T.Group(), bw = w * sc, bh = d * 0.6 * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic('#1a1a1a'));
  body.position.y = bh / 2; g.add(body);
  // Metal heatsink tab behind body
  const th = d * sc, tt = 1.2 * sc;
  const tab = mk(box(bw, th, tt), matMetal('#b0b0b0'));
  tab.position.set(0, th / 2, -bd / 2 - tt / 2); g.add(tab);
  const mh = mk(cyl(1.5 * sc, 1.5 * sc, tt * 1.1, 10), matMetal('#888888'));
  mh.rotation.x = Math.PI / 2; mh.position.set(0, th * 0.75, -bd / 2 - tt / 2); g.add(mh);
  const pm = matMetal('#aaaaaa'), ph = 3 * sc;
  for (const x of [-2.5 * sc, 0, 2.5 * sc]) {
    const p = mk(box(0.6 * sc, ph, 0.4 * sc), pm); p.position.set(x, -ph / 2, 0); g.add(p);
  }
  return g;
}

// ── 13. PIR / sensor dome ─────────────────────────────────────────────────────
function buildSensorDome(w, h, d, sc) {
  const g = new T.Group(), r = w / 2 * sc, bh = 2 * sc;
  const base = mk(cyl(r * 1.05, r * 1.05, bh, 24), matPlastic('#1a2a1a'));
  base.position.y = bh / 2; g.add(base);
  const dome = mk(
    new T.SphereGeometry(r, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
    new T.MeshStandardMaterial({ color: '#e8e8e8', roughness: 0.25, transparent: true, opacity: 0.7 })
  );
  dome.position.y = bh; g.add(dome); return g;
}

// ── 14. DC motor (FA-130, shaft along +X) ─────────────────────────────────────
function buildMotorDc(w, h, d, sc, color) {
  const g = new T.Group(), r = h / 2 * sc, bl = w * sc;
  const body = mk(cyl(r, r, bl, 24), matMotor(color));
  body.rotation.z = Math.PI / 2; body.position.set(0, r, 0); g.add(body);
  const sl = 8 * sc, sr = 1 * sc;
  const shaft = mk(cyl(sr, sr, sl, 10), matMetal('#b0b0b0'));
  shaft.rotation.z = Math.PI / 2; shaft.position.set(bl / 2 + sl / 2, r, 0); g.add(shaft);
  const tm = matMetal('#c0c0c0');
  for (const z of [-r * 0.3, r * 0.3]) {
    const t = mk(box(1.5 * sc, 4 * sc, 0.5 * sc), tm);
    t.position.set(-bl / 2 - 0.75 * sc, r, z); g.add(t);
  }
  return g;
}

// ── 15. Servo motor (SG90 / MG996R) ──────────────────────────────────────────
function buildMotorServo(w, h, d, sc, color) {
  const g = new T.Group(), bw = w * sc, bh = d * sc, bd = h * sc;
  const body = mk(box(bw, bh, bd), matPlastic(color));
  body.position.y = bh / 2; g.add(body);
  // Mounting ears
  const ew = 4 * sc, eh = bh * 0.4, ed = bd + 2.5 * sc;
  for (const x of [-bw / 2 - ew / 2, bw / 2 + ew / 2]) {
    const ear = mk(box(ew, eh, ed), matPlastic(color)); ear.position.set(x, bh * 0.8, 0); g.add(ear);
    const mh = mk(cyl(1.5 * sc, 1.5 * sc, ew * 1.1, 8), matPlastic('#111111'));
    mh.rotation.x = Math.PI / 2; mh.position.set(x, bh * 0.8, 0); g.add(mh);
  }
  // Output shaft + horn
  const sr = 3 * sc, sh = 4 * sc;
  const shaft = mk(cyl(sr, sr, sh, 12), matMetal('#d0d0d0'));
  shaft.position.y = bh + sh / 2; g.add(shaft);
  for (let i = 0; i < 2; i++) {
    const arm = mk(box(10 * sc, 1 * sc, 2 * sc), matPlastic('#f0f0f0'));
    arm.position.set(0, bh + sh + 0.5 * sc, 0); if (i) arm.rotation.y = Math.PI / 2; g.add(arm);
  }
  // Wire block
  const wire = mk(box(3 * sc, 4 * sc, 4 * sc), matPlastic('#888888'));
  wire.position.set(-bw / 2 - 1.5 * sc, bh * 0.3, 0); g.add(wire);
  return g;
}

// ── 16. 28BYJ-48 stepper motor ───────────────────────────────────────────────
function buildMotorStepper(w, h, d, sc) {
  const g = new T.Group(), r = w / 2 * sc, ht = d * sc;
  const body = mk(cyl(r, r, ht, 24), matPlastic('#2563eb'));
  body.position.y = ht / 2; g.add(body);
  // Mounting ears
  const ew = 8 * sc, eh = 4 * sc, ed = 4 * sc;
  for (const x of [-r - ew / 2, r + ew / 2]) {
    const ear = mk(box(ew, eh, ed), matPlastic('#2563eb')); ear.position.set(x, ht * 0.6, 0); g.add(ear);
    const mh = mk(cyl(1.5 * sc, 1.5 * sc, ed * 1.1, 8), matPlastic('#111111'));
    mh.rotation.x = Math.PI / 2; mh.position.set(x, ht * 0.6, 0); g.add(mh);
  }
  // 5-wire connector (front)
  const conn = mk(box(12 * sc, 5 * sc, 4 * sc), matPlastic('#f0f0f0'));
  conn.position.set(0, ht * 0.2, r + 2 * sc); g.add(conn);
  // Output shaft (rear, along Z)
  const sr = 2.5 * sc, sl = 6 * sc;
  const shaft = mk(cyl(sr, sr, sl, 10), matMetal('#b0b0b0'));
  shaft.rotation.x = Math.PI / 2; shaft.position.set(0, ht / 2, -r - sl / 2); g.add(shaft);
  return g;
}

// ── 17. Generic box — registered procedural shape (not ghost fallback) ────────
function buildBox(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const bw = (opts.bodyW || w) * sc;
  const bd = (opts.bodyD || h) * sc;
  const bh = (opts.bodyH || d || Math.min(bw / sc, bd / sc) * 0.4) * sc;
  const body = mk(box(bw, bh, bd), matPlastic(color));
  body.position.y = bh / 2; g.add(body);
  return g;
}

// ── 18. AA battery holder — plastic case + 2 cells side-by-side + +/- terminals ──
// S3: 真實 2×AA holder（auto_waterer 用此規格）—— 雙電池筒、可見正負極、金屬接點
function buildBatteryHolderAa(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const caseW = (w || 55) * sc, caseD = (h || 28) * sc, caseH = (d || 14) * sc;
  const cellCount = opts.cellCount || 2;  // 預設 2 顆 AA

  // Outer case
  const outer = mk(box(caseW, caseH, caseD), matPlastic(color || '#2a2a2a'));
  outer.position.y = caseH / 2; g.add(outer);

  // 2 個獨立電池槽（平行於 X 軸，沿 Z 並列）
  const cellR = 7 * sc, cellL = 48 * sc;
  const slotPitch = 15 * sc;  // AA 直徑 14.5mm + 隔牆
  const slotZStart = -(cellCount - 1) * slotPitch / 2;
  for (let i = 0; i < cellCount; i++) {
    const z = slotZStart + i * slotPitch;
    // 電池槽凹陷
    const cavW = 50.5 * sc, cavD = 14.5 * sc, cavH = 5 * sc;
    const cavity = mk(box(cavW, cavH, cavD), matPlastic('#0a0a0a'));
    cavity.position.set(0, caseH - cavH / 2 + 0.05 * sc, z); g.add(cavity);

    // AA cell body（金屬殼）— 交替方向（真實 holder 是 +/- 反接）
    const cellDir = (i % 2 === 0) ? 1 : -1;
    const cell = mk(cyl(cellR, cellR, cellL, 16), matMetal('#c8c8c8'));
    cell.rotation.z = Math.PI / 2;
    cell.position.set(0, caseH - cavH / 2, z); g.add(cell);

    // 正極凸點（金色銅）+ 標籤（+）
    const nubR = 2.0 * sc, nubL = 1.5 * sc;
    const nub = mk(cyl(nubR, nubR, nubL, 12), matMetal('#d4a040'));
    nub.rotation.z = Math.PI / 2;
    nub.position.set(cellDir * (cellL / 2 + nubL / 2), caseH - cavH / 2, z); g.add(nub);

    // 負極端（平面 + 彈簧接點）
    const springR = 3.5 * sc, springL = 3 * sc;
    const spring = mk(cyl(springR, springR * 0.7, springL, 10), matMetal('#a0a0a0'));
    spring.rotation.z = Math.PI / 2;
    spring.position.set(-cellDir * (cellL / 2 + springL / 2), caseH - cavH / 2, z); g.add(spring);

    // Label band（電池標籤條）
    const bandL = cellL * 0.6;
    const band = mk(cyl(cellR * 1.005, cellR * 1.005, bandL, 16), matPlastic('#1a4a8c'));
    band.rotation.z = Math.PI / 2;
    band.position.set(0, caseH - cavH / 2, z); g.add(band);
  }

  // 隔牆（cells 之間）
  if (cellCount > 1) {
    for (let i = 1; i < cellCount; i++) {
      const z = slotZStart + (i - 0.5) * slotPitch;
      const wall = mk(box(caseW * 0.9, caseH * 0.7, 0.8 * sc), matPlastic('#222'));
      wall.position.set(0, caseH * 0.5, z); g.add(wall);
    }
  }

  // 外側肋條紋理
  for (const zSide of [-1, 1]) {
    const rib = mk(box(caseW * 0.9, caseH * 0.6, 0.5 * sc), matPlastic('#222'));
    rib.position.set(0, caseH * 0.4, zSide * (caseD / 2 + 0.2 * sc)); g.add(rib);
  }

  return g;
}

// ── 18b. Mini submersible water pump (R385, 3-5V) — motor body + bottom screen ──
// SSOT: data/component_datasheet_verified.json:4002 — 45×30×25mm, outlet 8mm 由 dims.js 獨立 port 提供
function buildPumpWater(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const bodyR = ((opts.bodyW || w || 24) / 2) * sc;
  const bodyH = (opts.bodyH || d || 25) * sc;  // SSOT height_mm = 25

  // 馬達本體（藍色塑料圓柱）
  const body = mk(cyl(bodyR, bodyR, bodyH, 24), matPlastic(color || '#0288d1'));
  body.position.y = bodyH / 2; g.add(body);

  // 底部進水濾網（深色 + 放射狀槽紋）
  const screenR = bodyR * 0.95, screenH = 2 * sc;
  const screen = mk(cyl(screenR, screenR * 0.85, screenH, 24), matPlastic('#1a1a1a'));
  screen.position.y = screenH / 2; g.add(screen);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const slot = mk(box(screenR * 0.4, screenH * 0.6, 0.5 * sc), matPlastic('#000'));
    slot.position.set(Math.cos(a) * screenR * 0.4, screenH / 2, Math.sin(a) * screenR * 0.4);
    slot.rotation.y = a; g.add(slot);
  }

  // 兩條引線（紅黑，從側面出來；OUTLET 由 dims.js 獨立 cylinder port 渲染）
  for (let i = 0; i < 2; i++) {
    const wireColor = i === 0 ? '#c62828' : '#212121';
    const wireR = 0.6 * sc, wireL = 8 * sc;
    const wire = mk(cyl(wireR, wireR, wireL, 8), matPlastic(wireColor));
    wire.rotation.x = Math.PI / 2;
    wire.position.set((i === 0 ? -2 : 2) * sc, bodyH * 0.3, bodyR + wireL / 2);
    g.add(wire);
  }

  return g;
}

// ── 19. Slide switch (SPDT toggle) ────────────────────────────────────────────
function buildSlideSwitch(w, h, d, sc, color) {
  const g = new T.Group();
  const bw = (w || 11) * sc, bd = (h || 7) * sc, bh = (d || 4) * sc;

  // Switch body
  const body = mk(box(bw, bh, bd), matPlastic(color || '#1a1a1a'));
  body.position.y = bh / 2; g.add(body);

  // Slider track (recessed groove on top)
  const trackW = bw * 0.7, trackH = 0.6 * sc, trackD = bd * 0.4;
  const track = mk(box(trackW, trackH, trackD), matPlastic('#0a0a0a'));
  track.position.set(0, bh + trackH / 2 - 0.3 * sc, 0); g.add(track);

  // Slider knob (metal, offset to one side = ON position)
  const knobW = bw * 0.25, knobH = 2 * sc, knobD = bd * 0.35;
  const knob = mk(box(knobW, knobH, knobD), matMetal('#d0d0d0'));
  knob.position.set(bw * 0.15, bh + knobH / 2, 0); g.add(knob);

  // Three solder pins underneath
  const pinMat = matMetal('#aaaaaa'), pinH = 2.5 * sc;
  for (let i = -1; i <= 1; i++) {
    const pin = mk(cyl(0.3 * sc, 0.3 * sc, pinH, 6), pinMat);
    pin.position.set(i * 2.54 * sc, -pinH / 2, 0); g.add(pin);
  }

  return g;
}

// ── 20. Generic cylinder ──────────────────────────────────────────────────────
function buildCylinder(w, h, d, sc, color) {
  const g = new T.Group(), r = w / 2 * sc, ht = d * sc;
  const body = mk(cyl(r, r, ht, 24), matPlastic(color));
  body.position.y = ht / 2; g.add(body);
  return g;
}

// ── 21. Dome (half-sphere on short cylinder base) ─────────────────────────────
function buildDome(w, h, d, sc, color) {
  const g = new T.Group(), r = w / 2 * sc, bh = 2 * sc;
  const base = mk(cyl(r, r, bh, 24), matPlastic(color));
  base.position.y = bh / 2; g.add(base);
  const dome = mk(
    new T.SphereGeometry(r, 16, 8, 0, Math.PI * 2, 0, Math.PI / 2),
    matTransluc(color, 0.75)
  );
  dome.position.y = bh; g.add(dome);
  return g;
}

// ── Lookup map ────────────────────────────────────────────────────────────────
window.__PASSIVE_MECH_SHAPES = {
  'cap-electrolytic': buildCapElectrolytic,
  'cap-ceramic':      buildCapCeramic,
  'res-smd':          buildResSmd,
  'pot-trimmer':      buildPotTrimmer,
  'pot-shaft':        buildPotShaft,
  'relay':            buildRelay,
  'crystal-hc49':     buildCrystalHc49,
  'button-tactile':   buildButtonTactile,
  'buzzer':           buildBuzzer,
  'led-tht':          buildLedTht,
  'led-smd':          buildLedSmd,
  'vreg-to220':       buildVregTo220,
  'sensor-dome':      buildSensorDome,
  'motor-dc':         buildMotorDc,
  'motor-servo':      buildMotorServo,
  'motor-stepper':    buildMotorStepper,
  'box':              buildBox,
  'battery-holder-aa': buildBatteryHolderAa,
  'pump-water':       buildPumpWater,
  'slide-switch':     buildSlideSwitch,
  'cylinder':         buildCylinder,
  'dome':             buildDome,
};
})();
