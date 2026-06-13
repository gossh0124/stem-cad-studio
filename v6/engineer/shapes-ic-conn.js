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

function buildConnFpc(w, h, d, sc, color, opts = {}) {
  // FPC/FFC 軟排線 ZIF 翻蓋鎖扣連接器(CSI/DSI/E-Ink 排線用)
  // 幾何特徵:細長扁平絕緣座 + 後緣翻蓋 actuator + 排線插入槽口 + 槽內金色接觸列
  // opts:pins=接點數(預設 15)、pitch=接點間距 mm(預設 0.5,FPC 常見 0.5/1.0)
  //      flipUp=翻蓋是否處於開啟狀態(預設 false=已闔合鎖定)
  const pins   = opts.pins   || 15;     // 接點數;CSI 排線常 15、DSI 常 15/22
  const pitch  = opts.pitch  || 0.5;    // 接點間距 mm(0.5mm pitch 為典型)
  const flipUp = opts.flipUp || false;  // 翻蓋狀態,預設闔合
  const g = new T.Group();

  // 整體 footprint:w/h 若未給,依 pins×pitch 推算(座體比接點列略寬作裙邊)
  const slotSpan = pins * pitch;                       // 接點列總跨距(mm)
  const bW = (w || slotSpan + 2.5) * sc;               // 連接器寬(沿接點排列方向 X)
  const bD = (h || 4.5)            * sc;               // 連接器進深(排線插入方向 Z)
  const baseH = ((d || 1.2) * 0.6) * sc;               // 絕緣座本體高(低背 profile)

  // ── 1. 絕緣座本體(細長扁平,米白/深色塑膠) ──
  const baseColor = color || 0x2b2b2b;                 // ZIF 座常見深棕/黑色塑膠
  const base = mesh(new T.BoxGeometry(bW, baseH, bD), MAT_PLST(baseColor));
  base.position.set(0, baseH / 2, 0);
  g.add(base);

  // ── 2. 金色接觸列(槽口內一排金屬接點,沿 X 排列) ──
  const goldMat = MAT_GOLD();
  const contactW = pitch * 0.55 * sc;                  // 單一接點寬(略小於 pitch 留間隙)
  const contactD = bD * 0.45;                          // 接點沿 Z 向延伸長度
  for (let i = 0; i < pins; i++) {
    const px = (-((pins - 1) * pitch) / 2 + i * pitch) * sc;
    const contact = mesh(
      new T.BoxGeometry(contactW, 0.12 * sc, contactD),
      goldMat
    );
    // 接點置於座體頂面、偏向排線插入側(+Z),露出於槽口
    contact.position.set(px, baseH + 0.06 * sc, bD * 0.12);
    g.add(contact);
  }

  // ── 3. 翻蓋 actuator(後緣鉸接的鎖扣翻蓋,深色塑膠) ──
  // 闔合時平躺壓住接點;開啟時繞後緣(-Z)向上翻起約 80°
  const actW = bW * 0.96;                              // 翻蓋略窄於座體
  const actH = 0.45 * sc;                              // 翻蓋薄板厚
  const actD = bD * 0.5;                               // 翻蓋進深(覆蓋後半部)
  const actuator = mesh(new T.BoxGeometry(actW, actH, actD), MAT_PLST(baseColor));
  // 以後緣為旋轉樞紐:先建一個樞紐 group 對齊後緣(-Z 端、座頂高度)
  const hinge = new T.Group();
  hinge.position.set(0, baseH, -bD / 2);
  // 翻蓋幾何相對樞紐:沿 +Z 方向延伸、貼於座頂之上
  actuator.position.set(0, actH / 2, actD / 2);
  hinge.add(actuator);
  hinge.rotation.x = flipUp ? -(80 * Math.PI / 180) : 0;  // 開啟翻起 / 闔合平躺
  g.add(hinge);

  // ── 4. 兩端定位金屬耳片(boardlock,焊在 PCB 上固定座體) ──
  const tabMat = MAT_PIN();
  [-1, 1].forEach(side => {
    const tab = mesh(
      new T.BoxGeometry(0.6 * sc, baseH * 0.8, bD * 0.7),
      tabMat
    );
    tab.position.set(side * (bW / 2 - 0.3 * sc), baseH * 0.4, 0);
    g.add(tab);
  });

  return g;
}

// ─── 13. microSD Card Socket (push-push) ────────────────────────────────────

function buildConnCardMicrosd(w, h, d, sc, color, _opts = {}) {
  const g = new T.Group();
  // 預設 footprint:扁長金屬殼,寬(X)≈15mm、深(Z)≈14.5mm、高(Y)≈1.8mm
  // (push-push microSD 卡座典型外形;w/h/d 缺省時用此規格)
  const bW = (w || 15)   * sc;   // 殼體寬度(沿 X,卡片插入方向的左右)
  const bH = (d || 1.8)  * sc;   // 殼體高度(沿 Y,扁平)
  const bD = (h || 14.5) * sc;   // 殼體深度(沿 Z,卡片插入深度)
  const shellMat = MAT_SHLD(color || 0x9a9a9a); // 金屬上蓋(不鏽鋼殼)

  // 1) 金屬上蓋:薄扁殼體,占整體厚度上半
  const lidH  = bH * 0.55;
  const lid = mesh(new T.BoxGeometry(bW, lidH, bD), shellMat);
  lid.position.set(0, bH - lidH / 2, 0);
  g.add(lid);

  // 2) 塑膠底座:承載彈片與接點,占下半厚度
  const baseH = bH - lidH;
  const base = mesh(new T.BoxGeometry(bW, baseH, bD), MAT_PLST(0x1c1c1c));
  base.position.set(0, baseH / 2, 0);
  g.add(base);

  // 3) 卡槽開口:前緣(+Z)一道深色細縫,卡片由此推入
  const slotW = bW * 0.82;       // 卡片寬度略小於殼寬
  const slot  = mesh(new T.BoxGeometry(slotW, bH * 0.5, 0.6 * sc), mat(0x050505, 1.0, 0));
  slot.position.set(0, bH * 0.45, bD / 2 + 0.1 * sc);
  g.add(slot);

  // 4) 金接點列:槽內可見的鍍金 pad(microSD 為 8 pin,沿 X 排列)
  const padMat = MAT_GOLD();
  const padN   = 8;
  const padPitch = (slotW * 0.9) / padN;
  for (let i = 0; i < padN; i++) {
    const px = (-((padN - 1) * padPitch) / 2 + i * padPitch);
    const pad = mesh(new T.BoxGeometry(padPitch * 0.5, 0.05 * sc, 1.2 * sc), padMat);
    pad.position.set(px, bH * 0.45, bD / 2 - 1.6 * sc);
    g.add(pad);
  }

  // 5) 側邊彈片/退片桿:沿一側(-X)外露的金屬彈臂(push-push 機構)
  const spring = mesh(new T.BoxGeometry(0.4 * sc, bH * 0.4, bD * 0.55), shellMat.clone());
  spring.position.set(-bW / 2 - 0.2 * sc, bH * 0.5, -bD * 0.05);
  g.add(spring);

  // 6) SMT 焊接耳片:兩側各一片貼板焊腳,固定殼體
  const tabMat = mat(0xaaaaaa, 0.4, 0.7);
  [-1, 1].forEach(side => {
    const tab = mesh(new T.BoxGeometry(1.2 * sc, 0.3 * sc, 2.0 * sc), tabMat);
    tab.position.set(side * (bW / 2 + 0.6 * sc), 0.15 * sc, -bD * 0.25);
    g.add(tab);
  });

  return g;
}

// ─── 13. Card-Edge 金手指連接器 ──────────────────────────────────────────────
// 真實零件:板緣 card-edge 連接器,沿 X 板緣排佈一列扁平鍍金接觸墊,
// 直接貼平在板面上(極薄、金色)。支援兩型墊:
//   - large ring pad(大型環墊,如電源/接地,以矩形 + 鑽孔環表現)
//   - small rect pad(小型矩形訊號墊)
// opts.largePads / opts.smallPads:各型墊數量;opts.pitch:墊間距(mm)。
// 幾何極精簡:每片墊 1~2 個 primitive,全部貼平 Y≈0(板面),group bottom 對齊 Y=0。
function buildConnCardEdge(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();

  // ── opts 預設(無則合理預設,皆已註明)──
  const largePads = opts.largePads != null ? opts.largePads : 2;   // 預設 2 個大環墊
  const smallPads = opts.smallPads != null ? opts.smallPads : 8;   // 預設 8 個小矩墊
  const pitch     = opts.pitch     || 2.0;                          // 預設 2.0mm 墊間距
  const totalPads = largePads + smallPads;

  // ── 板基底:薄 PCB 條(深綠),做為金手指附著的板緣 ──
  // d = 板厚(高度方向);用很薄一層代表板緣本體,bottom 對齊 Y=0。
  const boardThick = (d || 1.6) * sc;                 // PCB 厚度,預設 1.6mm
  const boardW     = ((w || totalPads * pitch + 2)) * sc; // X 向板寬:涵蓋所有墊 + 邊距
  const boardD     = ((h || 6)) * sc;                 // Z 向板深,預設 6mm
  const base = mesh(new T.BoxGeometry(boardW, boardThick, boardD), MAT_PLST(color || 0x2d6a2d));
  base.position.set(0, boardThick / 2, 0);
  g.add(base);

  // 金手指略高於板面一點點,避免 z-fighting;墊朝板緣(+Z)排,根部留在板上。
  const padY     = boardThick + 0.02 * sc;            // 墊貼面高度(板面 + 微小偏移)
  const padDepth = boardD * 0.75;                     // 墊沿 Z 的長度(金手指延伸深度)
  const padFront = boardD / 2 * 0.05;                 // 墊中心相對板心稍偏向板緣(+Z)
  const goldMat  = MAT_GOLD();                        // 共用金色材質(鍍金)

  // ── 沿 X 板緣排佈所有墊:large 在前段、small 在後段 ──
  for (let i = 0; i < totalPads; i++) {
    const px = (-((totalPads - 1) * pitch) / 2 + i * pitch) * sc; // 沿 X 等距排佈
    const isLarge = i < largePads;                                 // 前 largePads 個為大環墊

    if (isLarge) {
      // 大型環墊:寬矩形貼片 + 中央鑽孔環(以扁平 RingGeometry 平躺表現環墊)
      const padW = pitch * 0.85 * sc;
      const slab = mesh(new T.BoxGeometry(padW, 0.04 * sc, padDepth), goldMat);
      slab.position.set(px, padY, padFront);
      g.add(slab);

      // 中央鑽孔環(平躺於 XZ 面,薄薄一圈金色,孔心朝下)
      const rHole = 0.5 * sc, rPad = pitch * 0.4 * sc;
      const ring = mesh(new T.RingGeometry(rHole, rPad, 20), goldMat);
      ring.rotation.x = -Math.PI / 2;                 // 平躺貼板面
      ring.position.set(px, padY + 0.03 * sc, padFront);
      g.add(ring);

      // 孔(深色)穿過板,表現 plated through-hole
      const hole = mesh(new T.CylinderGeometry(rHole, rHole, boardThick + 0.1 * sc, 12), mat(0x0a0a0a, 1.0, 0));
      hole.position.set(px, boardThick / 2, padFront);
      g.add(hole);
    } else {
      // 小型矩形訊號墊:單一扁平金色矩形,貼平板面、沿 Z 延伸到板緣
      const padW = pitch * 0.55 * sc;                 // 較窄
      const pad = mesh(new T.BoxGeometry(padW, 0.04 * sc, padDepth), goldMat);
      pad.position.set(px, padY, padFront);
      g.add(pad);
    }
  }

  return g;
}

// ─── 13. 3.5mm TRRS Audio Jack (horizontal sleeve + PCB base) ───────────────

function buildConnAudioJack(w, h, d, sc, color, opts = {}) {
  const g = new T.Group();

  // 板面 footprint 與高度(mm)→ 像素;預設貼近 PJ-320A 類 3.5mm 母座外形:
  //   w = 沿 X 寬度(基座寬)、h = 沿 Z 深度(基座 + 套筒長度方向)、d = 整體高度
  const bW = (w || 6.0)  * sc;   // 基座寬(X)
  const bD = (h || 12.0) * sc;   // 基座 + 套筒方向深度(Z)
  const bH = (d || 5.0)  * sc;   // 整體高度(Y)

  // opts:套筒外徑 / 內孔徑 / 套筒突出長度(mm);無則合理預設(3.5mm 規格)
  const sleeveOuterR = ((opts.sleeveDia   || 5.0) / 2) * sc;  // 金屬套筒外半徑,預設 Ø5.0
  const sleeveBoreR  = ((opts.boreDia      || 3.5) / 2) * sc; // 插孔內半徑,預設 Ø3.5(對應 3.5mm 插頭)
  const sleeveLen    = (opts.sleeveLen     || 7.0) * sc;      // 套筒沿 Z 突出長度,預設 7.0

  // 套筒中心高度:取整體高度約略中段,讓圓筒「坐」在基座上方
  const axisY = bH * 0.55;

  // ── 1. 塑膠基座(承載焊腳的本體),坐在 Y=0 ───────────────────────────
  const base = mesh(new T.BoxGeometry(bW, bH, bD), MAT_PLST(color || 0x111111));
  base.position.set(0, bH / 2, 0);
  g.add(base);

  // ── 2. 金屬套筒(水平圓筒,軸向沿 Z;插頭由 +Z 前緣插入) ──────────────
  // CylinderGeometry 預設軸向為 Y,旋轉 90° 使其躺平沿 Z 方向。
  const sleeveMat = MAT_CONN();
  const sleeve = mesh(
    new T.CylinderGeometry(sleeveOuterR, sleeveOuterR, sleeveLen, 20),
    sleeveMat
  );
  sleeve.rotation.x = Math.PI / 2;
  // 圓筒中心放在基座前半段,前端略突出於基座前緣(+Z)
  sleeve.position.set(0, axisY, bD / 2 - sleeveLen / 2 + 0.5 * sc);
  g.add(sleeve);

  // ── 3. 插孔內膛(深色凹孔,模擬可插入 3.5mm 插頭的開口) ────────────────
  const bore = mesh(
    new T.CylinderGeometry(sleeveBoreR, sleeveBoreR, sleeveLen + 0.2 * sc, 16),
    mat(0x050505, 1.0, 0)
  );
  bore.rotation.x = Math.PI / 2;
  bore.position.set(0, axisY, bD / 2 - sleeveLen / 2 + 0.6 * sc);
  g.add(bore);

  // ── 4. 套筒前緣倒角環(金屬亮邊,凸顯開口輪廓) ──────────────────────────
  const lip = mesh(
    new T.CylinderGeometry(sleeveOuterR * 1.05, sleeveOuterR * 1.05, 0.8 * sc, 20),
    sleeveMat.clone()
  );
  lip.rotation.x = Math.PI / 2;
  lip.position.set(0, axisY, bD / 2 + 0.1 * sc);
  g.add(lip);

  // ── 5. 焊腳 / 接點(底部金屬接腳,模擬 SMT/THT 端子) ──────────────────
  // 預設 5 腳(TRRS 為 4 訊號 + 1 偵測/接地,合理近似),分布於基座後半底緣。
  const pins = opts.pins || 5;
  const pinMat = MAT_PIN();
  for (let i = 0; i < pins; i++) {
    const px = (-((pins - 1) / 2) + i) * (bW / (pins)) ;
    const pinX = px;
    // 後半段(-Z)排列的彎折接腳
    const leg = mesh(new T.BoxGeometry(0.4 * sc, 1.6 * sc, 0.5 * sc), pinMat);
    leg.position.set(pinX, -0.8 * sc, -bD / 2 + 1.2 * sc);
    g.add(leg);
  }

  return g;
}

// ─── new shapes (Stage A) ───
window.__IC_CONN_SHAPES = {
  'conn-fpc':            buildConnFpc,
  'conn-card-microsd':   buildConnCardMicrosd,
  'conn-card-edge':      buildConnCardEdge,
  'conn-audio-jack':     buildConnAudioJack,
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
