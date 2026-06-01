// shapes-ic-conn.js — Three.js shape factory: IC packages & connectors
// Builder signature: (w, h, d, sc, color, opts) → THREE.Group, bottom at Y=0
(() => {
const T = window.THREE;

// ─── shared material helpers ────────────────────────────────────────────────

function mat(color, roughness, metalness) {
  return new T.MeshStandardMaterial({ color, roughness, metalness });
}
const MAT_IC   = (c) => mat(c,    0.85, 0.0);
const MAT_PIN  = ()  => mat(0xc0c0c0, 0.3, 0.8);
const MAT_GOLD = ()  => mat(0xc9b037, 0.3, 0.7);
const MAT_CONN = ()  => mat(0xd4d4d4, 0.2, 0.85);
const MAT_SHLD = (c) => mat(c,    0.35, 0.7);
const MAT_PLST = (c) => mat(c,    0.7,  0.0);

function mesh(geo, material) {
  const m = new T.Mesh(geo, material);
  m.castShadow = true;
  return m;
}

// ─── 1. DIP ─────────────────────────────────────────────────────────────────

function buildIcDip(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 8;
  const pitch = opts.pitch || 2.54;
  const g = new T.Group();

  const bW = w * sc, bH = (d - 1) * sc, bD = h * sc;
  const body = mesh(new T.BoxGeometry(bW, bH, bD), MAT_IC(color));
  body.position.set(0, (1 + (d - 1) / 2) * sc, 0);
  g.add(body);

  // Pin-1 notch (small box indentation on -X end)
  const notch = mesh(new T.CylinderGeometry(0.5 * sc, 0.5 * sc, 0.1 * sc, 12), mat(0x333333, 0.9, 0));
  notch.rotation.x = Math.PI / 2;
  notch.position.set(-bW / 2 + 1.2 * sc, (1 + (d - 1)) * sc + 0.05 * sc, 0);
  g.add(notch);

  const perRow = Math.floor(pins / 2);
  const rowZ   = [h / 2 * sc, -h / 2 * sc];
  const pinMat = MAT_PIN();

  for (let row = 0; row < 2; row++) {
    for (let i = 0; i < perRow; i++) {
      const px = (-((perRow - 1) * pitch) / 2 + i * pitch) * sc;
      const pz = rowZ[row];
      const dir = row === 0 ? 1 : -1;

      // horizontal stub from body side
      const stub = mesh(new T.BoxGeometry(0.3 * sc, 0.3 * sc, 1.5 * sc), pinMat);
      stub.position.set(px, 0.9 * sc, pz + dir * (bD / 2 + 0.75 * sc));
      g.add(stub);

      // vertical leg going down to PCB
      const leg = mesh(new T.BoxGeometry(0.3 * sc, 3 * sc, 0.3 * sc), pinMat);
      leg.position.set(px, 1.5 * sc - 3 * sc / 2, pz + dir * (bD / 2 + 1.5 * sc));
      g.add(leg);
    }
  }
  return g;
}

// ─── 2. SOIC ────────────────────────────────────────────────────────────────

function buildIcSoic(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 8;
  const pitch = opts.pitch || 1.27;
  const g = new T.Group();

  const bW = w * sc, bH = d * sc, bD = h * sc;
  const body = mesh(new T.BoxGeometry(bW, bH, bD), MAT_IC(color));
  body.position.set(0, bH / 2, 0);
  g.add(body);

  const perRow = Math.floor(pins / 2);
  const pinMat = MAT_PIN();
  const rowZ   = [h / 2 * sc, -h / 2 * sc];

  for (let row = 0; row < 2; row++) {
    for (let i = 0; i < perRow; i++) {
      const px  = (-((perRow - 1) * pitch) / 2 + i * pitch) * sc;
      const dir = row === 0 ? 1 : -1;
      // gull-wing: horizontal piece extending 1mm from body
      const wing = mesh(new T.BoxGeometry(0.2 * sc, 0.15 * sc, 1.0 * sc), pinMat);
      wing.position.set(px, 0.15 * sc, rowZ[row] + dir * (bD / 2 + 0.5 * sc));
      g.add(wing);
    }
  }
  return g;
}

// ─── 3. QFP ─────────────────────────────────────────────────────────────────

function buildIcQfp(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 32;
  const pitch = opts.pitch || 0.8;
  const g = new T.Group();

  const bW = w * sc, bH = d * sc, bD = h * sc;
  const body = mesh(new T.BoxGeometry(bW, bH, bD), MAT_IC(color));
  body.position.set(0, bH / 2, 0);
  g.add(body);

  // Pin-1 dot
  const dot = mesh(new T.CylinderGeometry(0.4 * sc, 0.4 * sc, 0.05 * sc, 8), mat(0xffffff, 0.5, 0));
  dot.position.set(-bW / 2 + 1.0 * sc, bH + 0.03 * sc, -bD / 2 + 1.0 * sc);
  g.add(dot);

  const perSide = Math.floor(pins / 4);
  const pinMat  = MAT_PIN();
  const sides   = [
    { axis: 'x', sign: 1,  base: bD / 2, span: bW },
    { axis: 'x', sign: -1, base: bD / 2, span: bW },
    { axis: 'z', sign: 1,  base: bW / 2, span: bD },
    { axis: 'z', sign: -1, base: bW / 2, span: bD },
  ];

  sides.forEach(({ axis, sign, base, _span }) => {
    for (let i = 0; i < perSide; i++) {
      const t = (-((perSide - 1) * pitch) / 2 + i * pitch) * sc;
      const wing = mesh(new T.BoxGeometry(0.2 * sc, 0.15 * sc, 1.0 * sc), pinMat);
      if (axis === 'x') {
        wing.position.set(t, 0.15 * sc, sign * (base + 0.5 * sc));
      } else {
        wing.rotation.y = Math.PI / 2;
        wing.position.set(sign * (base + 0.5 * sc), 0.15 * sc, t);
      }
      g.add(wing);
    }
  });
  return g;
}

// ─── 4. Shielded Module (ESP32-WROOM style) ─────────────────────────────────

function buildIcModule(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const bW = w * sc, bH = d * sc, bD = h * sc;

  const antennaFrac = 0.30;
  const shieldW = bW * (1 - antennaFrac);
  const antW    = bW * antennaFrac;

  // Metal shield portion
  const shield = mesh(new T.BoxGeometry(shieldW, bH, bD), MAT_SHLD(color || 0x888888));
  shield.position.set(-antW / 2 * sc, bH / 2, 0);
  g.add(shield);

  // Antenna PCB area
  const ant = mesh(new T.BoxGeometry(antW, bH * 0.6, bD), mat(0x2d6a2d, 0.8, 0));
  ant.position.set(shieldW / 2, bH * 0.3, 0);
  g.add(ant);

  return g;
}

// ─── 5. Micro USB ────────────────────────────────────────────────────────────

function buildConnUsbMicro(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const bW = (w || 7.5) * sc, bH = (d || 2.7) * sc, bD = (h || 5.3) * sc;
  const shellMat = MAT_CONN();

  const shell = mesh(new T.BoxGeometry(bW, bH, bD), shellMat);
  shell.position.set(0, bH / 2, 0);
  g.add(shell);

  // Trapezoidal port void (approximated as dark box inset on front face)
  const portH = bH * 0.6, portW = bW * 0.55;
  const port = mesh(new T.BoxGeometry(portW, portH, 0.4 * sc), mat(0x0a0a0a, 1.0, 0));
  port.position.set(0, portH / 2 + bH * 0.1, bD / 2 + 0.1 * sc);
  g.add(port);

  // Side mounting tabs
  [-1, 1].forEach(side => {
    const tab = mesh(new T.BoxGeometry(1.0 * sc, 0.5 * sc, 2.0 * sc), shellMat.clone());
    tab.position.set(side * (bW / 2 + 0.5 * sc), 0.25 * sc, -bD / 4);
    g.add(tab);
  });

  return g;
}

// ─── 6. USB-C ───────────────────────────────────────────────────────────────

function buildConnUsbC(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const bW = (w || 8.9) * sc, bH = (d || 3.3) * sc, bD = (h || 7.3) * sc;
  const shellMat = MAT_CONN();

  // Rounded shell (approximate with box + rounded radius label)
  const shell = mesh(new T.BoxGeometry(bW, bH, bD), shellMat);
  shell.position.set(0, bH / 2, 0);
  g.add(shell);

  // Oval port opening approximated as ellipsoid-ish cylinder
  const portW = bW * 0.6, portH = bH * 0.5;
  const port = mesh(new T.CylinderGeometry(portH / 2, portH / 2, 0.5 * sc, 16), mat(0x0a0a0a, 1.0, 0));
  port.rotation.z = Math.PI / 2;
  port.scale.y = portW / portH;
  port.position.set(0, bH * 0.5, bD / 2 + 0.15 * sc);
  g.add(port);

  return g;
}

// ─── 7. Male Pin Header ──────────────────────────────────────────────────────

function buildConnHeaderMale(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 4;
  const rows  = opts.rows  || 1;
  const pitch = opts.pitch || 2.54;
  const g     = new T.Group();

  const cols   = Math.ceil(pins / rows);
  const bodyW  = (cols * pitch) * sc;
  const bodyD  = (rows * pitch) * sc;
  const bodyH  = 2.5 * sc;

  const housing = mesh(new T.BoxGeometry(bodyW, bodyH, bodyD), MAT_PLST(0x222222));
  housing.position.set(0, bodyH / 2, 0);
  g.add(housing);

  const pinMat   = MAT_GOLD();
  const pinTotal = 8.5 * sc;
  const pinR     = 0.3 * sc;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (r * cols + c >= pins) break;
      const px = (-((cols - 1) * pitch) / 2 + c * pitch) * sc;
      const pz = (-((rows - 1) * pitch) / 2 + r * pitch) * sc;
      const pin = mesh(new T.CylinderGeometry(pinR, pinR, pinTotal, 6), pinMat);
      pin.position.set(px, pinTotal / 2, pz);
      g.add(pin);
    }
  }
  return g;
}

// ─── 8. Female Pin Header ────────────────────────────────────────────────────

function buildConnHeaderFemale(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 4;
  const rows  = opts.rows  || 1;
  const pitch = opts.pitch || 2.54;
  const g     = new T.Group();

  const cols  = Math.ceil(pins / rows);
  const bodyW = (cols * pitch) * sc;
  const bodyD = (rows * pitch) * sc;
  const bodyH = 8.5 * sc;

  const housing = mesh(new T.BoxGeometry(bodyW, bodyH, bodyD), MAT_PLST(0x111111));
  housing.position.set(0, bodyH / 2, 0);
  g.add(housing);

  const holeMat = mat(0x050505, 1.0, 0);
  const holeR   = 0.5 * sc;
  const holeD   = 3.0 * sc;

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (r * cols + c >= pins) break;
      const px = (-((cols - 1) * pitch) / 2 + c * pitch) * sc;
      const pz = (-((rows - 1) * pitch) / 2 + r * pitch) * sc;
      const hole = mesh(new T.CylinderGeometry(holeR, holeR, holeD, 8), holeMat);
      hole.position.set(px, bodyH - holeD / 2, pz);
      g.add(hole);
    }
  }
  return g;
}

// ─── 9. Screw Terminal ───────────────────────────────────────────────────────

function buildConnScrewTerminal(w, h, d, sc, color, opts = {}) {
  const pins  = opts.pins  || 3;
  const pitch = opts.pitch || 5.08;
  const g     = new T.Group();

  const bodyW = (pins * pitch) * sc;
  const bodyH = (d || 10) * sc;
  const bodyD = (h || 7) * sc;
  const bodyColor = color || 0x2266aa;

  const body = mesh(new T.BoxGeometry(bodyW, bodyH, bodyD), MAT_PLST(bodyColor));
  body.position.set(0, bodyH / 2, 0);
  g.add(body);

  const screwMat = mat(0xc0c0c0, 0.2, 0.8);
  const wireMat  = mat(0x1a1a1a, 0.9, 0);

  for (let i = 0; i < pins; i++) {
    const px = (-((pins - 1) * pitch) / 2 + i * pitch) * sc;

    // Screw cylinder on top
    const screw = mesh(new T.CylinderGeometry(1.2 * sc, 1.2 * sc, 1.5 * sc, 12), screwMat);
    screw.position.set(px, bodyH + 0.5 * sc, 0);
    g.add(screw);

    // Slotted head detail
    const slot = mesh(new T.BoxGeometry(2.0 * sc, 0.25 * sc, 0.3 * sc), mat(0x444444, 0.6, 0));
    slot.position.set(px, bodyH + 1.3 * sc, 0);
    g.add(slot);

    // Wire entry hole on front
    const hole = mesh(new T.CylinderGeometry(0.8 * sc, 0.8 * sc, 1.0 * sc, 8), wireMat);
    hole.rotation.x = Math.PI / 2;
    hole.position.set(px, bodyH * 0.35, bodyD / 2 + 0.1 * sc);
    g.add(hole);
  }
  return g;
}

// ─── 10. USB Type-B (Arduino Uno style) ─────────────────────────────────────

function buildConnUsbB(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const bW = (w || 12) * sc, bH = (d || 11) * sc, bD = (h || 16) * sc;
  const shellMat = MAT_CONN();

  const shell = mesh(new T.BoxGeometry(bW, bH, bD), shellMat);
  shell.position.set(0, bH / 2, 0);
  g.add(shell);

  // Square port opening on front face
  const portW = bW * 0.55, portH = bH * 0.55;
  const port = mesh(new T.BoxGeometry(portW, portH, 0.5 * sc), mat(0x0a0a0a, 1.0, 0));
  port.position.set(0, bH * 0.5, bD / 2 + 0.15 * sc);
  g.add(port);

  // Inner square tube (approximated)
  const inner = mesh(new T.BoxGeometry(portW * 0.5, portH * 0.5, 0.6 * sc), mat(0xffffff, 0.3, 0.6));
  inner.position.set(0, bH * 0.5, bD / 2 + 0.1 * sc);
  g.add(inner);

  // Side shield tabs
  [-1, 1].forEach(side => {
    const tab = mesh(new T.BoxGeometry(1.5 * sc, 0.8 * sc, 3.0 * sc), shellMat.clone());
    tab.position.set(side * (bW / 2 + 0.75 * sc), 0.4 * sc, -bD / 4);
    g.add(tab);
  });

  // Four through-hole mounting legs
  const legMat = mat(0xaaaaaa, 0.4, 0.7);
  [[-1, -1], [-1, 1], [1, -1], [1, 1]].forEach(([sx, sz]) => {
    const leg = mesh(new T.CylinderGeometry(0.4 * sc, 0.4 * sc, 3.5 * sc, 6), legMat);
    leg.position.set(sx * bW * 0.35, -1.75 * sc, sz * bD * 0.35);
    g.add(leg);
  });

  return g;
}

// ─── 11. Mounting Hole ──────────────────────────────────────────────────────

function buildMountingHole(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const holeDia = (w || 3.2);
  const padDia  = (h || holeDia * 2);
  const rHole = holeDia / 2 * sc;
  const rPad  = padDia / 2 * sc;
  const thick = 1.6 * sc;

  // Copper annular ring
  const ring = mesh(
    new T.RingGeometry(rHole, rPad, 24),
    mat(0xc9b037, 0.35, 0.6)
  );
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.05 * sc;
  g.add(ring);

  // Dark hole center
  const hole = mesh(
    new T.CylinderGeometry(rHole, rHole, thick + 0.1 * sc, 16),
    mat(0x0a0a0a, 1.0, 0)
  );
  hole.position.y = -thick / 2;
  g.add(hole);

  return g;
}

// ─── 12. DC Barrel Jack ─────────────────────────────────────────────────────

function buildConnBarrelJack(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  const bW = (w || 9)  * sc;
  const bH = (d || 11) * sc;
  const bD = (h || 14) * sc;

  const body = mesh(new T.BoxGeometry(bW, bH, bD), MAT_PLST(color || 0x1a1a1a));
  body.position.set(0, bH / 2, 0);
  g.add(body);

  // Outer barrel ring
  const shellMat = MAT_CONN();
  const outer = mesh(new T.CylinderGeometry(3.5 * sc, 3.5 * sc, 1.5 * sc, 16), shellMat);
  outer.rotation.x = Math.PI / 2;
  outer.position.set(0, bH * 0.55, bD / 2 + 0.5 * sc);
  g.add(outer);

  // Inner barrel (dark void)
  const inner = mesh(new T.CylinderGeometry(1.2 * sc, 1.2 * sc, 1.6 * sc, 12), mat(0x050505, 1.0, 0));
  inner.rotation.x = Math.PI / 2;
  inner.position.set(0, bH * 0.55, bD / 2 + 0.55 * sc);
  g.add(inner);

  // Three mounting legs underneath
  const legMat = mat(0xaaaaaa, 0.4, 0.7);
  [-1, 0, 1].forEach((off, idx) => {
    const leg = mesh(new T.BoxGeometry(1.0 * sc, 3.0 * sc, 0.5 * sc), legMat);
    const lx = off * 3.0 * sc;
    const lz = (idx === 1 ? 1 : -1) * 4.0 * sc;
    leg.position.set(lx, -1.5 * sc, lz);
    g.add(leg);
  });

  return g;
}

// ─── Lookup Map ──────────────────────────────────────────────────────────────

window.__IC_CONN_SHAPES = {
  'ic-dip':              buildIcDip,
  'ic-soic':             buildIcSoic,
  'ic-qfp':              buildIcQfp,
  'ic-module':           buildIcModule,
  'conn-usb-micro':      buildConnUsbMicro,
  'conn-usb-c':          buildConnUsbC,
  'conn-usb-b':          buildConnUsbB,
  'conn-header-male':    buildConnHeaderMale,
  'conn-header-female':  buildConnHeaderFemale,
  'conn-screw-terminal': buildConnScrewTerminal,
  'conn-barrel-jack':    buildConnBarrelJack,
  'mounting-hole':       buildMountingHole,
};
})();
