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
  const outer = mk(box(caseW, caseH, caseD), matPlastic(color || /* nofallback-ok: UI 裝飾色預設，呼叫端 color 為 optional */ '#2a2a2a'));
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
  const body = mk(cyl(bodyR, bodyR, bodyH, 24), matPlastic(color || /* nofallback-ok: UI 裝飾色預設，pump 本體顏色 optional */ '#0288d1'));
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
  const body = mk(box(bw, bh, bd), matPlastic(color || /* nofallback-ok: UI 裝飾色預設，開關本體顏色 optional */ '#1a1a1a'));
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
// ── 22. Flat-panel display active area (OLED / LCD / E-Ink) ───────────────────
// 薄發光面板：深色窄邊框 + color 主動發光面 + 微凸玻璃蓋板
// opts: bezel(邊框比例,預設 0.06)、glassRise(玻璃微凸高度 mm,預設 0.4)
function buildDisplayPanel(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const pw = w * sc, pd = h * sc;                 // 板面 footprint：w=寬、h=深
  const ph = (d || 1.6) * sc;                     // 預設模組總高 1.6mm（薄面板）

  // 邊框比例：四周非顯示區佔板面的比例（預設 6%，符合 OLED/LCD 窄邊框投影）
  const bezel = (opts.bezel != null ? opts.bezel : 0.06);

  // ── 模組底座 / 邊框（深色塑料,撐起整個面板高度的主體）──────────────────
  const frame = mk(box(pw, ph, pd), matPlastic('#1a1a1a'));
  frame.position.y = ph / 2; g.add(frame);

  // ── 主動發光面（active area）：用 color 表面色,以高不透明 transLuc 讀作「發光」──
  // 內縮 bezel,薄薄一層貼在邊框頂面之下,留出玻璃蓋板空間
  const aw = pw * (1 - 2 * bezel), ad = pd * (1 - 2 * bezel);
  const activeH = 0.3 * sc;
  const active = mk(box(aw, activeH, ad), matTransluc(color, 0.92));
  active.position.y = ph - activeH / 2; g.add(active);

  // ── 微凸玻璃蓋板（cover glass）：略大於主動區、半透明,壓在最上層產生玻璃感 ──
  const glassRise = (opts.glassRise != null ? opts.glassRise : 0.4) * sc;
  const gw = pw * (1 - bezel), gd = pd * (1 - bezel);
  const glass = mk(box(gw, glassRise, gd), matTransluc('#dfe7ee', 0.28));
  glass.position.y = ph + glassRise / 2; g.add(glass);

  return g;
}

// ── 22. 8×8 LED 點陣顯示模組 (MAX7219 / 1088AS 型) ───────────────────────────
// 真實零件:深色底板 + cols×rows 顆小圓 LED 點陣,兩側出排針。
// 簽章 (w,h,d,sc,color,opts):w/h = 底板 footprint(mm,預設 32×32),d = 模組高(mm,預設 8)。
// opts.cols / opts.rows 預設 8;opts.dotShape='round'(預設) | 'square';color = LED 發光色。
function buildLedMatrix8x8(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const bw = (w || 32) * sc;            // 底板寬 (X)
  const bd = (h || 32) * sc;            // 底板深 (Z)
  const cols = opts.cols || 8;          // 行(沿 X)— 預設 8
  const rows = opts.rows || 8;          // 列(沿 Z)— 預設 8
  const square = opts.dotShape === 'square';
  const ledColor = color || /* nofallback-ok: UI 裝飾色預設,LED 發光色 optional */ '#d92020';

  // 底板高度:取模組高的一半當塑膠基座,LED 點再凸出於其上
  const baseH = (d ? d * 0.5 : 4) * sc;

  // 底板(深色 epoxy/塑膠)
  const base = mk(box(bw, baseH, bd), matPlastic('#1a1a1a'));
  base.position.y = baseH / 2; g.add(base);

  // 外圍細邊框(略高於底板,框住點陣區)
  const rimH = 0.6 * sc, rimT = 1.2 * sc;
  const rimMat = matPlastic('#0a0a0a');
  for (const [sx, sz, ww, dd] of [
    [0, -bd / 2 + rimT / 2, bw, rimT],   // 後緣
    [0,  bd / 2 - rimT / 2, bw, rimT],   // 前緣
    [-bw / 2 + rimT / 2, 0, rimT, bd],   // 左緣
    [ bw / 2 - rimT / 2, 0, rimT, bd],   // 右緣
  ]) {
    const rim = mk(box(ww, rimH, dd), rimMat);
    rim.position.set(sx, baseH + rimH / 2, sz); g.add(rim);
  }

  // 點陣排佈:在邊框內留邊距,等距鋪 cols×rows
  const margin = rimT + 1.0 * sc;                 // 框內邊距
  const areaW = bw - margin * 2, areaD = bd - margin * 2;
  const pitchX = cols > 1 ? areaW / (cols - 1) : 0;
  const pitchZ = rows > 1 ? areaD / (rows - 1) : 0;
  const x0 = -areaW / 2, z0 = -areaD / 2;
  // LED 點半徑取行/列間距的 ~0.32,避免相鄰碰撞
  const dotR = Math.max(0.3 * sc, Math.min(pitchX, pitchZ) * 0.32);
  const dotH = 0.8 * sc;                          // 凸出高度

  // LED 點材質:半透明發光色(沿用 matTransluc 助手)
  const dotMat = matTransluc(ledColor, 0.85);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const px = x0 + c * pitchX, pz = z0 + r * pitchZ;
      let dot;
      if (square) {
        dot = mk(box(dotR * 1.6, dotH, dotR * 1.6), dotMat);
        dot.position.set(px, baseH + dotH / 2, pz);
      } else {
        dot = mk(cyl(dotR, dotR, dotH, 10), dotMat);
        dot.position.set(px, baseH + dotH / 2, pz);
      }
      g.add(dot);
    }
  }

  // 兩側排針(左右各一排,沿 Z 等距),向下伸出 Y=0 之下
  const pinMat = matMetal('#aaaaaa'), pinH = 2.5 * sc, pinR = 0.3 * sc;
  const pinCount = Math.min(rows, 8);
  const pinPitch = areaD / Math.max(pinCount - 1, 1);
  const pz0 = -((pinCount - 1) * pinPitch) / 2;
  for (const sx of [-bw / 2 + rimT / 2, bw / 2 - rimT / 2]) {
    for (let i = 0; i < pinCount; i++) {
      const pin = mk(cyl(pinR, pinR, pinH, 6), pinMat);
      pin.position.set(sx, -pinH / 2, pz0 + i * pinPitch); g.add(pin);
    }
  }

  return g;
}

// ── 22. Aluminum finned heatsink — base plate + N vertical fins (silver metal) ──
// 鋁質散熱片：底座板 + 數片垂直鰭片（沿 X 軸並列、面朝 ±Z），銀灰金屬
// w/h = 底座 footprint(mm)、d = 總高(mm)、sc = px/mm；幾何一律 × sc，bottom 對齊 Y=0
// opts: fins=鰭片數(預設 8)、finT=鰭片厚 mm(預設 1)、baseH=底座厚 mm(預設總高 20%)
function buildHeatsink(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  const baseW = (w || 30) * sc;          // 底座寬（X）
  const baseD = (h || 30) * sc;          // 底座深（Z）
  const totalH = (d || 25) * sc;         // 散熱片總高（Y）
  const fins = opts.fins || 8;           // 鰭片數量（預設 8 片）
  const finT = (opts.finT || 1) * sc;    // 單片鰭片厚度（預設 1mm）
  const baseH = (opts.baseH || (d || 25) * 0.2) * sc; // 底座厚（預設總高 20%）

  // 散熱片金屬色（銀灰鋁）—— color 為 optional，無則用陽極氧化鋁預設
  const finMat = matMetal(color || /* nofallback-ok: UI 裝飾色預設，散熱片本體顏色 optional */ '#b8bcc0');

  // 底座板（實心鋁塊）
  const base = mk(box(baseW, baseH, baseD), finMat);
  base.position.y = baseH / 2; g.add(base);

  // 垂直鰭片：沿 X 軸等距並列，鰭片板面朝 ±Z 方向延伸
  const finH = totalH - baseH;           // 鰭片高 = 總高 − 底座厚
  const finD = baseD * 0.96;             // 鰭片深略小於底座（露出底座邊緣）
  // 鰭片中心間距：把 fins 片均勻鋪滿底座寬（兩端留半個間距邊距）
  const pitch = baseW / fins;
  const xStart = -baseW / 2 + pitch / 2;
  for (let i = 0; i < fins; i++) {
    const fin = mk(box(finT, finH, finD), finMat);
    fin.position.set(xStart + i * pitch, baseH + finH / 2, 0);
    g.add(fin);
  }

  return g;
}

// ── 22. Breathable sensor grid / vent panel (DHT22 進氣柵) ────────────────────
// 真實零件:濕度/氣體感測器的透氣網孔面板 —— 一塊薄塑料面板 + 規則排列的進氣孔。
// 幾何策略:面板本體用一塊薄 box;孔洞用「深色凹槽 box」陣列近似(primitive 模擬鑽孔,
//          避免 CSG 布林運算),四週留邊框,維持精簡(面板 + N×M 孔)。
// opts:
//   cols / rows  — 孔洞列數/行數(預設 4×8,貼近 DHT22 正面柵格)
//   margin       — 面板四週留邊(mm,預設 1.2)
//   round        — true 用圓孔(cyl),false 用方孔(box);預設 false(方形柵格)
//   panelColor   — 面板顏色;預設沿用呼叫端 color,無則白色塑料(DHT22 外殼白)
// 尺寸:w/h = 面板 footprint(mm),d = 面板厚度(mm,薄板);bottom 對齊 Y=0。
function buildSensorGrid(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();

  const cols   = opts.cols   || 4;    // 預設 4 行孔(沿 X)
  const rows   = opts.rows   || 8;    // 預設 8 列孔(沿 Z)
  const margin = (opts.margin != null ? opts.margin : 1.2) * sc;  // 預設邊框 1.2mm
  const round  = opts.round || false; // 預設方形柵格(DHT22 風格)

  const panelW = (w || 14) * sc;      // 預設 14mm 寬(DHT22 ~15.1mm)
  const panelD = (h || 20) * sc;      // 預設 20mm 深(DHT22 ~25mm)
  const panelH = (d || 1.5) * sc;     // 預設 1.5mm 薄面板厚度

  // 面板本體(白色塑料,DHT22 外殼)
  const panel = mk(box(panelW, panelH, panelD),
    matPlastic(color || /* nofallback-ok: UI 裝飾色預設,面板顏色 optional */ '#f0f0f0'));
  panel.position.y = panelH / 2; g.add(panel);

  // 孔洞陣列:在 margin 內側均勻鋪排;孔=深色凹槽,自面板頂面略凹下
  const gridW = panelW - margin * 2;  // 可用鋪孔區域
  const gridD = panelD - margin * 2;
  const cellW = gridW / cols;         // 單孔格寬
  const cellD = gridD / rows;
  const holeW = cellW * 0.6;          // 孔徑佔格 60%,留出格柵肋條
  const holeD = cellD * 0.6;
  const holeR = Math.min(holeW, holeD) / 2;        // 圓孔半徑
  const holeDepth = panelH * 0.7;                  // 凹槽深度(不貫穿,保留底膜)
  const holeY = panelH - holeDepth / 2;            // 凹槽中心(貼頂面)
  const holeMat = matPlastic('#0a0a0a');           // 深色孔內壁

  for (let c = 0; c < cols; c++) {
    for (let r = 0; r < rows; r++) {
      // 格中心座標(對稱置中)
      const x = -gridW / 2 + cellW * (c + 0.5);
      const z = -gridD / 2 + cellD * (r + 0.5);
      let hole;
      if (round) {
        hole = mk(cyl(holeR, holeR, holeDepth, 8), holeMat);  // 圓進氣孔
      } else {
        hole = mk(box(holeW, holeDepth, holeD), holeMat);     // 方形柵格孔
      }
      hole.position.set(x, holeY, z); g.add(hole);
    }
  }

  return g;
}

// ── 22. Toggle switch (SPDT bat-handle) — metal base + threaded bushing + 斜插 bat 撥桿 ──
// 真實零件:MTS-102 類 SPDT 撥動/搖頭開關。footprint w×h = 金屬底座(mm),d = 含撥桿總高(mm)。
// opts.pins 焊腳數(SPDT 預設 3:common + 2 throw)、opts.tilt 撥桿傾角(rad,預設 ~22°,表示撥到一側的 ON 位)。
function buildToggleSwitch(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  // 板面 footprint 與總高;無 opts 時用常見 mini toggle 尺寸(底座 ~13×8mm、總高 ~23mm)合理預設
  const baseW = (w || 13) * sc;          // 底座 X 寬
  const baseD = (h || 8)  * sc;          // 底座 Z 深
  const totalH = (d || 23) * sc;         // 含撥桿的整體高度(用來推算撥桿長度)
  const pinCount = opts.pins || 3;       // SPDT = 3 腳(common + 2 throw),預設 3
  const tilt = opts.tilt != null ? opts.tilt : 0.38;  // 撥桿傾角(rad)≈ 22°,預設搖到 +X 側 ON

  // ── 金屬底座(矮方塊,開關殼體)──
  const baseH = 4 * sc;
  const base = mk(box(baseW, baseH, baseD),
    matMetal(color || /* nofallback-ok: UI 裝飾色預設,開關金屬殼顏色為 optional */ '#b8b8b8'));
  base.position.y = baseH / 2; g.add(base);

  // ── 螺紋安裝襯套(底座上的圓柱凸出,面板鎖固用)──
  const bushR = Math.min(baseW, baseD) * 0.32, bushH = 4 * sc;
  const bushing = mk(cyl(bushR, bushR, bushH, 16), matMetal('#c8c8c8'));
  bushing.position.y = baseH + bushH / 2; g.add(bushing);

  // ── 六角固定螺帽(襯套頂端,略大於襯套的扁六角)──
  const nutR = bushR * 1.25, nutH = 1.6 * sc;
  const nut = mk(cyl(nutR, nutR, nutH, 6), matMetal('#9a9a9a'));
  nut.position.y = baseH + bushH - nutH / 2; g.add(nut);

  // ── 斜插的 bat 撥桿(本零件的決定性特徵:金屬細桿,從襯套頂端以 tilt 角斜伸)──
  // 撥桿長度 = 總高扣掉底座+襯套,再給點冗餘讓尖端略超出 totalH
  const pivotY = baseH + bushH;                              // 撥桿樞紐點(襯套頂)
  const leverLen = Math.max(totalH - pivotY, 8 * sc) + 2 * sc;
  const leverR = bushR * 0.4;
  // 桿身(沿 +Y 細圓柱),先在 group 內繞 Z 軸傾斜成搖到 +X 側
  const lever = new T.Group();
  const stem = mk(cyl(leverR, leverR * 1.15, leverLen, 12), matMetal('#cfcfcf'));
  stem.position.y = leverLen / 2; lever.add(stem);
  // 桿頂圓球握頭(bat tip)
  const tip = mk(new T.SphereGeometry(leverR * 1.6, 12, 8), matMetal('#dcdcdc'));
  tip.position.y = leverLen; lever.add(tip);
  lever.position.y = pivotY;
  lever.rotation.z = -tilt;   // 負號 = 撥桿倒向 +X(ON 一側),呈斜插姿態
  g.add(lever);

  // ── 焊腳(SPDT 線性排列於底座下方,2.54mm pitch)──
  const pinMat = matMetal('#aaaaaa'), pinH = 3 * sc, pitch = 2.54 * sc;
  const pinStart = -(pinCount - 1) * pitch / 2;
  for (let i = 0; i < pinCount; i++) {
    const pin = mk(box(0.6 * sc, pinH, 0.6 * sc), pinMat);
    pin.position.set(pinStart + i * pitch, -pinH / 2, 0); g.add(pin);
  }

  return g;
}

// ── 22. PCB region — 平貼板面的著色矩形平面特徵 ───────────────────────────────
// 通用於 天線 keep-out / 銅箔極板 / 驅動子板輪廓。極薄 bodyH≈0.3mm,可半透明。
// w/h = 板面 footprint(mm)、d = 高(mm,預設極薄)、sc = px/mm。
// opts.alpha 透明度(0~1,預設 0.55 半透明;設 1 即不透明實心著色)。
function buildPcbRegion(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();
  // 板面尺寸:w→X、h→Z(footprint);高度極薄,預設 0.3mm 貼合板面
  const rw = (opts.bodyW || w) * sc;
  const rd = (opts.bodyD || h) * sc;
  const rh = (opts.bodyH || d || 0.3) * sc;  // 預設 bodyH=0.3mm(薄銅箔/輪廓特徵)
  const alpha = (opts.alpha != null) ? opts.alpha : 0.55;  // 預設半透明 0.55

  // 主體:極薄著色矩形,bottom 對齊 Y=0
  // 沿用本檔 matTransluc() 助手(透明可調),opacity=1 時即實心著色
  const slab = mk(box(rw, rh, rd), matTransluc(color || /* nofallback-ok: UI 著色預設,呼叫端 color 為 optional */ '#2d8a4e', alpha));
  slab.position.y = rh / 2;
  g.add(slab);

  // 邊框輪廓:沿四邊放細條,凸顯 keep-out / 極板邊界(較不透明以增辨識度)
  const edgeMat = matTransluc(color || '#2d8a4e', Math.min(1, alpha + 0.3));  // nofallback-ok: 端子台外殼 UI 色(b 類分類色),非電氣/幾何值
  const ew = 0.25 * sc;                 // 邊框寬度 0.25mm
  const ey = rh + 0.02 * sc;            // 略高於板面避免 z-fighting
  // 上下兩條(沿 X 方向)
  for (const z of [-rd / 2 + ew / 2, rd / 2 - ew / 2]) {
    const e = mk(box(rw, 0.04 * sc, ew), edgeMat);
    e.position.set(0, ey, z); g.add(e);
  }
  // 左右兩條(沿 Z 方向)
  for (const x of [-rw / 2 + ew / 2, rw / 2 - ew / 2]) {
    const e = mk(box(ew, 0.04 * sc, rd), edgeMat);
    e.position.set(x, ey, 0); g.add(e);
  }

  return g;
}

// ─── new shapes (Stage A) ───
window.__PASSIVE_MECH_SHAPES = {
  'display-panel':    buildDisplayPanel,
  'led-matrix-8x8':   buildLedMatrix8x8,
  'heatsink':         buildHeatsink,
  'sensor-grid':      buildSensorGrid,
  'toggle-switch':     buildToggleSwitch,
  'pcb-region':       buildPcbRegion,
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
