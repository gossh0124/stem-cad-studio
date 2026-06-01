// ═══════════════════════════════════════════
// views-engineer-assembly-v3.jsx — Assembly V3 Pure Renderer
// Reads SceneGraph JSON from Python solver, renders 3D + step animation
// ═══════════════════════════════════════════

const THERMAL_LUT = [
  { t: 0, r: 0.15, g: 0.35, b: 0.85 }, { t: 0.25, r: 0.10, g: 0.75, b: 0.45 },
  { t: 0.5, r: 0.90, g: 0.85, b: 0.15 }, { t: 0.75, r: 0.95, g: 0.45, b: 0.10 },
  { t: 1, r: 0.90, g: 0.10, b: 0.10 },
];
function _lerpThermal(norm) {
  const n = Math.max(0, Math.min(1, norm));
  let lo = THERMAL_LUT[0], hi = THERMAL_LUT[4];
  for (let i = 0; i < 4; i++) {
    if (n >= THERMAL_LUT[i].t && n <= THERMAL_LUT[i + 1].t) { lo = THERMAL_LUT[i]; hi = THERMAL_LUT[i + 1]; break; }
  }
  const f = lo.t === hi.t ? 0 : (n - lo.t) / (hi.t - lo.t);
  return [lo.r + (hi.r - lo.r) * f, lo.g + (hi.g - lo.g) * f, lo.b + (hi.b - lo.b) * f];
}

const ROLE_COLORS = { Brain: [0.49,0.83,0.99], Power: [0.98,0.80,0.08], Control: [0.29,0.87,0.50], Sensor: [0.49,0.83,0.99], Output: [0.71,0.51,1.0] };
const SCALE = 0.04;

// ─── Scene Setup ─────────────────────────────────────
function _setupScene(st, containerOrId) {
  const T = window.THREE;
  const el = typeof containerOrId === 'string' ? document.getElementById(containerOrId) : containerOrId;
  if (!el || !T) return;
  const w = el.clientWidth || 800, h = el.clientHeight || 500;
  st.renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
  st.renderer.setSize(w, h);
  st.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  st.renderer.shadowMap.enabled = true;
  el.style.position = 'relative';
  el.appendChild(st.renderer.domElement);
  st.scene = new T.Scene();
  st.camera = new T.PerspectiveCamera(45, w / h, 0.1, 200);
  st.camera.position.set(4, 3, 5);
  if (T.OrbitControls) {
    st.controls = new T.OrbitControls(st.camera, st.renderer.domElement);
    st.controls.enableDamping = true; st.controls.dampingFactor = 0.08;
  }
  st.scene.add(new T.HemisphereLight(0xddeeff, 0x445566, 0.5));
  const dir = new T.DirectionalLight(0xffffff, 0.9);
  dir.position.set(3, 5, 4); dir.castShadow = true; st.scene.add(dir);
  const ground = new T.Mesh(new T.PlaneGeometry(20, 20), new T.ShadowMaterial({ opacity: 0.12 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.01; ground.receiveShadow = true;
  st.scene.add(ground);
  const ro = new ResizeObserver(() => {
    const nw = el.clientWidth, nh = el.clientHeight; if (!nw || !nh) return;
    st.renderer.setSize(nw, nh); st.camera.aspect = nw / nh; st.camera.updateProjectionMatrix();
  });
  ro.observe(el); st._ro = ro; st._container = el;
}

// ─── Enclosure Renderer ──────────────────────────────
function _renderEnclosure(st, enc) {
  if (!enc) return;
  const T = window.THREE, [L, W, H] = enc.inner, wall = enc.wall || 2.5;
  const oL = (L + 2 * wall) * SCALE, oW = (W + 2 * wall) * SCALE, oH = (H + 2 * wall) * SCALE;
  const ghostMat = (c, op) => new T.MeshPhysicalMaterial({ color: c, transparent: true, opacity: op, roughness: 0.4, side: T.DoubleSide, depthWrite: false });
  st.enclosure.base = new T.Mesh(new T.BoxGeometry(oL, oH * 0.75, oW), ghostMat(0x8899aa, 0.12));
  st.enclosure.base.position.y = oH * 0.75 / 2; st.scene.add(st.enclosure.base);
  const lidH = oH * 0.25;
  st.enclosure.lid = new T.Mesh(new T.BoxGeometry(oL, lidH, oW), ghostMat(0x6699bb, 0.10));
  st.enclosure.lid.position.y = oH * 0.75 + lidH / 2; st.scene.add(st.enclosure.lid);
  st._encDims = { oL, oW, oH };
  _frameCamera(st);   // centre + auto-distance once enclosure dims are known
}

// Centre the camera on the enclosure mid-height and back off enough that the
// whole bounding box fits the viewport (auto distance from max dim + FOV).
function _frameCamera(st, dirX = 1, dirY = 0.6, dirZ = 1) {
  if (!st.camera || !st._encDims) return;
  const { oL, oW, oH } = st._encDims;
  const cy = oH / 2;
  const maxDim = Math.max(oL, oW, oH);
  const fov = (st.camera.fov || 45) * Math.PI / 180;
  const d = (maxDim / Math.tan(fov / 2)) * 0.9;
  const n = Math.hypot(dirX, dirY, dirZ) || 1;
  st.camera.position.set(dirX / n * d, cy + dirY / n * d, dirZ / n * d);
  if (st.controls) { st.controls.target.set(0, cy, 0); st.controls.update(); }
  else st.camera.lookAt(0, cy, 0);
}

// ─── Wall holes (external wiring pass-through) ───────────
function _renderHoles(st, holes) {
  st.holes = [];
  if (!holes?.length) return;
  const T = window.THREE;
  for (const h of holes) {
    const r = (h.diameter / 2) * SCALE;
    const ring = new T.Mesh(
      new T.TorusGeometry(r, Math.max(r * 0.18, 0.01), 8, 20),
      new T.MeshBasicMaterial({ color: 0xffaa44, transparent: true, opacity: 0.9 }));
    const [cx, cy, cz] = h.center;
    ring.position.set(cx * SCALE, cy * SCALE, cz * SCALE);
    if (h.face === 'x+' || h.face === 'x-') ring.rotation.y = Math.PI / 2;  // axis -> X
    else if (h.face === 'top') ring.rotation.x = Math.PI / 2;               // axis -> Y
    // y+/y-: torus axis already along Z (scene depth) — no rotation
    ring.userData = { kind: 'hole', comp_type: h.comp_type };
    st.scene.add(ring); st.holes.push(ring);
  }
}

// ─── Panel face cutouts (mount openings on the lid) ──────
function _renderCutouts(st, cutouts) {
  st.cutouts = [];
  if (!cutouts?.length) return;
  const T = window.THREE;
  const col = 0x44ddff;
  for (const c of cutouts) {
    const [cx, cy, cz] = c.center;
    let mesh;
    if (c.shape === 'round') {
      const r = (c.diameter / 2) * SCALE;
      mesh = new T.Mesh(
        new T.TorusGeometry(r, Math.max(r * 0.14, 0.006), 8, 24),
        new T.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.9 }));
      mesh.rotation.x = Math.PI / 2;  // lay flat on the lid
    } else {
      const eg = new T.EdgesGeometry(
        new T.PlaneGeometry((c.width || 4) * SCALE, (c.height || 4) * SCALE));
      mesh = new T.LineSegments(eg,
        new T.LineBasicMaterial({ color: col, transparent: true, opacity: 0.95 }));
      mesh.rotation.x = -Math.PI / 2;  // plane XY -> lid XZ
    }
    mesh.position.set(cx * SCALE, cy * SCALE, cz * SCALE);
    mesh.userData = { kind: 'cutout', comp_type: c.comp_type, mount: c.mount };
    st.scene.add(mesh); st.cutouts.push(mesh);
  }
}

// ─── Geometry Builders ───────────────────────────────
function _buildSTLGeo(T, tris) {
  const pos = new Float32Array(tris.length * 9);
  for (let i = 0; i < tris.length; i++) for (let v = 0; v < 3; v++) {
    const [x, y, z] = tris[i].vertices[v];
    pos[i * 9 + v * 3] = x; pos[i * 9 + v * 3 + 1] = y; pos[i * 9 + v * 3 + 2] = z;
  }
  const geo = new T.BufferGeometry();
  geo.setAttribute('position', new T.BufferAttribute(pos, 3)); geo.computeVertexNormals(); return geo;
}

// ─── Module Renderer ─────────────────────────────────
// Backend position convention:
//   internal/breadboard/external/embedded → position[1] = 0 (BOTTOM at floor)
//   panel → position[1] = ih - H/2 (already CENTRE, sits flush under lid)
// Three.js BoxGeometry is centre-based, so non-panel needs +H/2 to put its
// bottom on the floor (was straddling y=0, half sinking below the enclosure).
function _moduleCenterY(mod, dH) {
  return (mod.enclosure_relation === 'panel') ? mod.position[1] : mod.position[1] + dH / 2;
}

function _renderModules(st, modules) {
  if (!modules?.length) return;
  const T = window.THREE;
  const loadPromises = [];
  for (const mod of modules) {
    const [px, , pz] = mod.position, [dL, dW, dH] = mod.dimensions;
    const cy = _moduleCenterY(mod, dH);
    const rc = ROLE_COLORS[mod.role] || [0.6, 0.6, 0.7];
    const mat = new T.MeshPhysicalMaterial({ color: new T.Color(...rc), transparent: true, opacity: 0.88, roughness: 0.35, metalness: 0.05, clearcoat: 0.3 });
    const boxGeo = new T.BoxGeometry(dL * SCALE, dH * SCALE, dW * SCALE);
    const box = new T.Mesh(boxGeo, mat);
    box.position.set(px * SCALE, cy * SCALE, pz * SCALE); box.castShadow = true;
    box.userData = { id: mod.id, role: mod.role, thermal: mod.thermal, isFallback: true };
    st.scene.add(box);
    const fallbackEdge = new T.LineSegments(
      new T.EdgesGeometry(boxGeo), new T.LineBasicMaterial({ color: 0xff3333, opacity: 0.7, transparent: true }));
    fallbackEdge.position.copy(box.position);
    fallbackEdge.name = `fallback_edge_${mod.id}`;
    st.scene.add(fallbackEdge);
    const entry = { mesh: box, meshParts: {}, box, data: mod };
    st.modules[mod.id] = entry;
    loadPromises.push(_loadModuleMesh(st, T, mod, entry));
  }
  Promise.allSettled(loadPromises).then(() => {
    st._verdict = _buildFidelityVerdict(st);
    window.__assemblyV3Verdict = st._verdict;
  });
}

function _buildFidelityVerdict(st) {
  const entries = Object.entries(st.modules);
  const fbIds = entries.filter(([, e]) => e.box?.userData?.isFallback).map(([id]) => id);
  const n = entries.length;
  const loaded = n - fbIds.length;

  const colorSet = new Set();
  for (const [, e] of entries) {
    if (e.box?.userData?.isFallback) continue;
    e.box?.traverse(child => {
      if (child.isMesh && child.material?.color) {
        colorSet.add(child.material.color.getHexString());
      }
    });
  }
  const colorDiverse = colorSet.size >= 3 || loaded <= 3;

  return { timestamp: Date.now(), total: n, loaded,
    fallback: fbIds.length, fallback_ids: fbIds,
    coverage: n ? loaded / n : 1,
    unique_colors: colorSet.size, color_diverse: colorDiverse,
    pass: fbIds.length === 0 && colorDiverse };
}

// Components view (scene-3d.js) renders a GLB as multi-colour: each sub-part
// is a separate mesh carrying its own colour (IC red, pin gold, LED blue, ...).
// V3 used to merge everything into one BufferGeometry with a hard-coded dark
// teal — that's why Arduino looked dull/uniform here while it looked vivid in
// Components view. Mirror Components: per-part meshes with per-part PBR.
const ROLE_RGB_FALLBACK = {
  Brain:   [125, 211, 252],  Power:   [250, 204, 21],
  Control: [74, 222, 128],   Sensor:  [125, 211, 252],
  Output:  [180, 130, 255],  Actuator:[180, 130, 255],
};
const PCB_STL_RGB = [0, 84, 107];   // matches Components dark-teal PCB
function _isMetallicColor(r, g, b) {
  return (r > 150 && g > 150 && b > 150) || (r > 180 && g > 130 && b < 60);
}
function _pbrMaterial(T, rgb, sidedouble = true) {
  const [r, g, b] = rgb;
  const metallic = _isMetallicColor(r, g, b);
  return new T.MeshPhysicalMaterial({
    color: new T.Color(r / 255, g / 255, b / 255),
    roughness: metallic ? 0.25 : 0.40,
    metalness: metallic ? 0.70 : 0.04,
    clearcoat: metallic ? 0   : 0.40,
    clearcoatRoughness: 0.10,
    side: sidedouble ? T.DoubleSide : T.FrontSide,
  });
}

async function _loadModuleMesh(st, T, moduleData, entry) {
  if (!window.getParsedGeometry && !window.API?.getShellSTL) return;
  // Phase 1: load every variant via shared parsed-geometry cache (getParsedGeometry).
  // Cache is populated by whichever view (Components or Assembly) loads first,
  // ensuring identical parse results and avoiding redundant parse work.
  const items = [];
  for (const variant of ['pcb_body', 'base', 'lid', 'mount']) {
    try {
      const parsed = window.getParsedGeometry
        ? await window.getParsedGeometry(moduleData.comp_type, variant)
        : null;
      if (parsed === null) continue;
      if (parsed.isGLB) {
        items.push({ variant, isGLB: true, parts: parsed.parts });
      } else {
        items.push({ variant, isGLB: false, stlGeo: _buildSTLGeo(T, parsed.triangles) });
      }
    } catch (e) {
      window.recordRender?.('module', 'load_error', { comp_type: moduleData.comp_type, variant, err: String(e) });
    }
  }
  if (!items.length) {
    console.error('[Assembly-V3] fallback ghost box for "' + moduleData.comp_type + '" (' + moduleData.id + '): no geometry loaded from any variant (pcb_body/base/lid/mount)');
    window.recordRender?.('module', 'ghost', { comp_type: moduleData.comp_type });
    return;
  }

  // Phase 2: flatten into per-part geometries, all in Y-up shared frame.
  // RF1: GLB 後端已 Y-up (pcb_common._export_glb)，僅 STL 需 ROT。
  const ROT = new T.Matrix4().makeRotationX(-Math.PI / 2);
  const tile = [];  // {variant, geo, rgb}
  for (const it of items) {
    const roleRGB = ROLE_RGB_FALLBACK[moduleData.role] || [136, 153, 170];
    const stlRGB = it.variant === 'pcb_body' ? PCB_STL_RGB : roleRGB;
    if (it.isGLB) {
      for (const part of it.parts) {
        if (!part.positions?.length) continue;
        const g = new T.BufferGeometry();
        g.setAttribute('position', new T.BufferAttribute(new Float32Array(part.positions), 3));
        if (part.normals) g.setAttribute('normal', new T.BufferAttribute(new Float32Array(part.normals), 3));
        if (part.indices) g.setIndex(new T.BufferAttribute(new Uint32Array(part.indices), 1));
        if (!part.normals) g.computeVertexNormals();
        tile.push({ variant: it.variant, geo: g, rgb: part.color || stlRGB });
      }
    } else {
      it.stlGeo.applyMatrix4(ROT);
      tile.push({ variant: it.variant, geo: it.stlGeo, rgb: stlRGB });
    }
  }
  if (!tile.length) return;

  // Phase 3: ONE shared centre + ONE shared scale across ALL parts of this module.
  // Keeps the module rigid (pcb/base/lid stay in their native relative position)
  // and fits the whole assembly to the backend's dimensions[].
  const union = new T.Box3();
  for (const t of tile) { t.geo.computeBoundingBox(); if (t.geo.boundingBox) union.union(t.geo.boundingBox); }
  if (union.isEmpty()) return;
  const ctr = new T.Vector3(); union.getCenter(ctr);
  const sz  = new T.Vector3(); union.getSize(sz);
  const [dL, dW, dH] = entry.data.dimensions;
  const s = Math.min((dL * SCALE) / (sz.x || 0.001),
                     (dH * SCALE) / (sz.y || 0.001),
                     (dW * SCALE) / (sz.z || 0.001));
  for (const t of tile) { t.geo.translate(-ctr.x, -ctr.y, -ctr.z); t.geo.scale(s, s, s); }

  // Phase 4: per-part meshes with per-part PBR — matches Components view exactly.
  let primary = null;
  for (const t of tile) {
    const mesh = new T.Mesh(t.geo, _pbrMaterial(T, t.rgb));
    mesh.position.copy(entry.box.position);
    mesh.visible = entry.box.visible;
    mesh.castShadow = true;
    st.scene.add(mesh);
    const key = `${t.variant}_${entry.meshParts.__n = (entry.meshParts.__n || 0) + 1}`;
    entry.meshParts[key] = mesh;
    if (t.variant === 'pcb_body' && !primary) primary = mesh;
    else if (!primary) primary = mesh;
  }
  entry.mesh = primary;
  entry.box.visible = false;
  entry.box.userData.isFallback = false;
  const fallbackEdge = st.scene.getObjectByName('fallback_edge_' + moduleData.id);
  if (fallbackEdge) fallbackEdge.visible = false;

  // bbox vs dimensions cross-check (data-driven, not visual)
  const actualBbox = new T.Box3();
  Object.values(entry.meshParts).forEach(m => { if (m.visible) actualBbox.expandByObject(m); });
  if (!actualBbox.isEmpty()) {
    const as = new T.Vector3(); actualBbox.getSize(as);
    const [eL, eW, eH] = [dL * SCALE, dW * SCALE, dH * SCALE];
    const tol = 0.3 * SCALE;
    if (Math.abs(as.x - eL) > tol || Math.abs(as.y - eH) > tol || Math.abs(as.z - eW) > tol) {
      console.warn('[Assembly-V3] bbox mismatch for "' + moduleData.comp_type + '": actual [' +
        as.x.toFixed(3) + ',' + as.y.toFixed(3) + ',' + as.z.toFixed(3) + '] vs expected [' +
        eL.toFixed(3) + ',' + eH.toFixed(3) + ',' + eW.toFixed(3) + ']');
    }
  }
  window.recordRender?.('module', 'mesh', { comp_type: moduleData.comp_type, parts: tile.length });
}

// ─── Wire Renderer ───────────────────────────────────
function _renderWires(st, wires) {
  if (!wires?.length) return;
  const T = window.THREE;
  for (const wire of wires) {
    if (!wire.path3d?.length || wire.path3d.length < 2) continue;
    const pts = wire.path3d.map(([x, y, z]) => new T.Vector3(x * SCALE, y * SCALE, z * SCALE));
    const curve = new T.CatmullRomCurve3(pts, false, wire.style || 'catmullrom', 0.25);
    const tubeGeo = new T.TubeGeometry(curve, Math.max(24, pts.length * 8), 0.015, 6, false);
    const color = wire.color ? new T.Color(wire.color) : new T.Color(0x44cc44);
    const mesh = new T.Mesh(tubeGeo, new T.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 }));
    mesh.userData = { wireId: wire.id, signal: wire.signal }; st.scene.add(mesh);
    st.wires[wire.id] = { mesh, tubeGeo, totalVerts: tubeGeo.attributes.position.count };
  }
}

// ─── Overlay (React owns UI; controller exposes setOverlay) ──────────────
function _applyOverlay(st, mode) {
  st.overlay = mode;
  const _T = window.THREE, maxP = Math.max(...Object.values(st.modules).map(e => e.data.thermal?.power_mw || 0), 1);
  Object.values(st.modules).forEach(entry => {
    const mesh = entry.mesh, norm = (entry.data.thermal?.power_mw || 0) / maxP;
    if (mode === 'thermal') {
      const [r, g, b] = _lerpThermal(norm);
      mesh.material.color.setRGB(r, g, b); mesh.material.emissiveIntensity = 0.2 + 0.6 * norm; mesh.material.opacity = 0.9;
    } else if (mode === 'wiring') { mesh.material.opacity = 0.3; mesh.material.emissiveIntensity = 0;
    } else { const rc = ROLE_COLORS[entry.data.role] || [0.6,0.6,0.7]; mesh.material.color.setRGB(...rc); mesh.material.emissiveIntensity = 0; mesh.material.opacity = 0.88; }
  });
  Object.values(st.wires).forEach(w => { w.mesh.material.opacity = mode === 'wiring' ? 0.85 : 0.5; });
}

// ─── Camera orbit (React owns rotY/rotX/zoom via use3DInteraction) ───
// applyView positions the camera on a sphere around the enclosure mid-height,
// distance = auto-D / zoom. This is the canonical camera API for React to drive.
function applyView(st, rotY, rotX, zoom) {
  if (!st.camera || !st._encDims) return;
  const { oL, oW, oH } = st._encDims;
  const cy = oH / 2;
  const maxDim = Math.max(oL, oW, oH);
  const fov = (st.camera.fov || 45) * Math.PI / 180;
  const baseD = (maxDim / Math.tan(fov / 2)) * 0.9;
  const d = baseD / Math.max(zoom || 1, 0.1);
  const ry = (rotY * Math.PI) / 180;
  const rx = (rotX * Math.PI) / 180;
  const absRx = Math.abs(rotX);
  st.camera.position.set(
    d * Math.sin(ry) * Math.cos(rx),
    cy + d * Math.sin(rx),
    d * Math.cos(ry) * Math.cos(rx),
  );
  // Top/bottom gimbal-lock: up vector must not align with view direction.
  if (absRx > 85) st.camera.up.set(0, 0, rotX > 0 ? -1 : 1);
  else st.camera.up.set(0, 1, 0);
  st.camera.lookAt(0, cy, 0);
}

// Data-driven verification surface: per-module dims/position + ortho projected
// footprints + enclosure openings. Numbers only — for parameterised checks, never
// screenshot judgement (see feedback_no_visual_without_quantifiable_data).
function _sceneMetrics(sceneData) {
  const enc = sceneData.enclosure || {};
  const wires = sceneData.wires || [];
  const modules = (sceneData.modules || []).map(m => {
    const [L, W, H] = m.dimensions;
    return {
      id: m.id, comp_type: m.comp_type, relation: m.enclosure_relation,
      position: m.position, dimensions: m.dimensions,
      footprint: { top: [L, W], front: [L, H], side: [W, H] },
    };
  });
  return {
    enclosure_inner: enc.inner, wall: enc.wall,
    holes: (enc.holes || []).length,
    cutouts: (enc.face_cutouts || []).length,
    n_modules: modules.length,
    n_wires: wires.length,
    crosses_wall: wires.filter(w => w.crosses_wall).length,
    validation: sceneData.validation,
    modules,
  };
}

function _crossViewCheck(st) {
  const cache = window._parsedGeoCache;
  const rows = Object.entries(st.modules).map(([id, e]) => {
    const ct = e.data.comp_type, loaded = !e.box?.userData?.isFallback;
    return { id, comp_type: ct, asm: loaded, cache: cache ? cache.has(ct + '/pcb_body') : false };
  });
  const mm = rows.filter(r => !r.asm && r.cache);
  return { total: rows.length, pass: mm.length === 0,
    both: rows.filter(r => r.asm && r.cache).length,
    mismatches: mm.map(r => r.comp_type), details: rows };
}

// ─── Explosion Control ───────────────────────────────
function _applyExplosion(st, factor) {
  st.explosionFactor = factor;
  Object.values(st.modules).sort((a, b) => a.data.position[1] - b.data.position[1]).forEach((entry, i) => {
    const y = entry.data.position[1] * SCALE + factor * (i + 1) * 0.4;
    entry.box.position.y = y; if (entry.mesh !== entry.box) entry.mesh.position.y = y;
    Object.values(entry.meshParts).forEach(m => { m.position.y = y; });
  });
  if (st.enclosure.lid) st.enclosure.lid.position.y = (st._encDims?.oH * 0.875 || 1) + factor * 0.8;
  if (st.enclosure.base) st.enclosure.base.material.opacity = 0.12 * (1 - factor * 0.5);
}

// ─── Render Loop ─────────────────────────────────────
function _animate(st) {
  (function loop() {
    st._animId = requestAnimationFrame(loop);
    if (st.controls) st.controls.update();
    st.renderer.render(st.scene, st.camera);
  })();
}

// ─── Main Entry ──────────────────────────────────────
function renderAssemblyV3(containerOrId, sceneData) {
  if (!sceneData || sceneData.version !== '3.0') { console.warn('[Assembly-V3] Invalid sceneData'); return null; }
  const st = { scene: null, camera: null, renderer: null, controls: null,
    modules: {}, wires: {}, enclosure: { base: null, lid: null },
    overlay: 'clean', explosionFactor: 0,
    _animId: null, _container: null, _encDims: null };
  _setupScene(st, containerOrId); if (!st.scene) return null;
  _renderEnclosure(st, sceneData.enclosure);
  _renderHoles(st, sceneData.enclosure?.holes);
  _renderCutouts(st, sceneData.enclosure?.face_cutouts);
  _renderModules(st, sceneData.modules);
  _renderWires(st, sceneData.wires);
  _animate(st);
  st._sceneData = sceneData;
  // Data-driven verification surface (numbers, not pixels) — see _sceneMetrics.
  window.__assemblyV3Metrics = () => _sceneMetrics(sceneData);
  window.__crossViewCheck = () => _crossViewCheck(st);
  return {
    setOverlay: (m) => _applyOverlay(st, m),
    setExplosion: (f) => _applyExplosion(st, f),
    applyView: (ry, rx, z) => applyView(st, ry, rx, z),
    metrics: () => _sceneMetrics(sceneData),
    verdict: () => st._verdict || null,
    crossViewCheck: () => _crossViewCheck(st),
    cameraInfo: () => ({
      position: st.camera ? st.camera.position.toArray().map(x => +x.toFixed(3)) : null,
      target: st.controls ? st.controls.target.toArray().map(x => +x.toFixed(3)) : null,
      encDims: st._encDims || null,
    }),
    debugState: () => ({
      modules: Object.entries(st.modules).map(([id, e]) => ({
        id,
        box_visible: e.box?.visible,
        is_fallback: !!e.box?.userData?.isFallback,
        primary_mesh_is_box: e.mesh === e.box,
        meshParts: Object.entries(e.meshParts || {}).map(([v, m]) => ({
          variant: v, visible: m.visible,
          vertex_count: m.geometry?.attributes?.position?.count || 0,
        })),
      })),
      fallback_count: Object.values(st.modules).filter(e => e.box?.userData?.isFallback).length,
      wires_count: Object.keys(st.wires).length,
      scene_children: st.scene?.children.length || 0,
    }),
    dispose: () => {
      if (st._animId) cancelAnimationFrame(st._animId); st._ro?.disconnect();
      if (window.__assemblyV3Metrics) delete window.__assemblyV3Metrics;
      if (window.__crossViewCheck) delete window.__crossViewCheck;
      // Traverse scene and dispose all geometry/material to prevent memory leaks
      if (st.scene) {
        st.scene.traverse(obj => {
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) {
            if (Array.isArray(obj.material)) {
              obj.material.forEach(m => m.dispose());
            } else {
              obj.material.dispose();
            }
          }
        });
      }
      // Dispose OrbitControls
      if (st.controls) st.controls.dispose();
      st.renderer?.dispose(); st.renderer?.domElement?.remove();
    },
  };
}
window.renderAssemblyV3 = renderAssemblyV3;
