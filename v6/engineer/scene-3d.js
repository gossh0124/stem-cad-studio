// ═══════════════════════════════════════════
// scene-3d.js — Three.js 3D scene construction for Components-3D view
// GLB/STL loading, PCB body rendering, opacity controls, ghost box fallback
// Split from views-engineer.jsx (INF1-S3)
// ═══════════════════════════════════════════

(() => {
  // ─── 角色 → 固定 RGB（用於 mesh 材質 fill） ─────────────────

  const ROLE_RGB = {
    Brain:   [125, 211, 252],  // sky blue
    Power:   [250, 204, 21],   // amber
    Control: [74, 222, 128],   // green
    Sensor:  [125, 211, 252],  // sky blue
    Output:  [180, 130, 255],  // purple
  };

  // ─── Model mesh cache (for pre-built GLB/mesh models) ─────────────
  // Registry loaded by HTML init; mesh cache populated on demand
  // Render priority: cached mesh → procedural builder → ghost box
  window.__MODEL_MESHES = window.__MODEL_MESHES || {};

  function _modelKey(shape, params) {
    if (!shape) return null;
    const p = params || {};
    return [shape, p.pins || '', p.pitch || '', p.rows || ''].join(':');
  }

  // ── VS-AXIS: PCB↔Three.js 座標轉換（純函式，往返一致性測試 tests/axis_roundtrip.test.js）──
  // PCB 平面(mm, 左下原點) → scene(x,z)(板中心原點 × scale sc)。port 擺放與其反函式共用此公式，
  // 避免「手寫轉換錯 → 前端重疊/錯位但後端綠」。
  function _pcbToScene(cx, cy, boardL, boardW, sc) {
    return { x: (cx - boardL / 2) * sc, z: -(cy - boardW / 2) * sc };
  }
  function _sceneToPcb(x, z, boardL, boardW, sc) {
    return { cx: x / sc + boardL / 2, cy: -z / sc + boardW / 2 };
  }
  // Z-up(STL/OCP) → Y-up(Three) 軸向慣例：three.y←z、three.z←-y（writeXform 採此）
  function _zUpToYUp(x, y, z) { return { x: x, y: z, z: -y }; }
  function _yUpToZUp(x, y, z) { return { x: x, y: -z, z: y }; }

  // ═══════════════════════════════════════════
  // useComponentScene — PBR material + sharp edges + ground shadow
  // Wraps useThreeBase with component-shell-specific geometry management
  // ═══════════════════════════════════════════

  function useComponentScene(containerRef, triangles, rotY, rotX, zoom, cx, cy, cz, maxExtent, roleRGB, baseOpacity, lidOpacity, pcbBody) {
    const useThreeBase = window.useThreeBase;

    // STR3: init delegated to shared hook (scene/camera/renderer/lights/ground/resize)
    const stateRef = useThreeBase(containerRef, {
      frust: 1.3, hemiSkyInt: 0.75, enableRimLight: true, rimInt: 0.4,
      dirInt: 1.0, groundY: -1.5, groundSize: 10, shadowOpacity: 0.18,
    });

    // VS-FE: 圖層可見性 inspector — 回傳每個 named mesh 的 visible/opacity 真值。
    // 半透明殼體疊圖目測無法可靠判斷 toggle 是否真隱藏（曾誤判成功），須讀真值。
    window.inspectLayers = () => {
      const sc = stateRef.current?.scene; if (!sc) return null;
      const pick = (n) => { const o = sc.getObjectByName(n); return o ? { visible: o.visible, opacity: o.material?.opacity ?? null } : null; };
      return { base: pick('stlMesh'), baseEdges: pick('stlEdges'), lid: pick('stlMeshLid'), lidEdges: pick('stlEdgesLid'), pcb: pick('pcbBody') };
    };

    // ── Geometry update (triangles / roleRGB change) ──
    React.useEffect(() => {
      const st = stateRef.current;
      if (!st) return;
      const T = window.THREE;

      // Clear old meshes (base + lid + edges all dispose)
      ['stlMesh', 'stlMeshLid', 'stlEdges', 'stlEdgesLid'].forEach(name => {
        const old = st.scene.getObjectByName(name);
        if (old) { st.scene.remove(old); old.geometry.dispose(); old.material.dispose(); }
      });

      // Clear old PCB body + port overlays
      ['pcbBody', 'pcbUsb', 'pcbHeaders', 'pcbEdges', 'pcbPorts'].forEach(name => {
        const old = st.scene.getObjectByName(name);
        if (old) {
          st.scene.remove(old);
          if (old.geometry) old.geometry.dispose();
          if (old.material) old.material.dispose();
          old.children?.forEach(c => { c.geometry?.dispose(); c.material?.dispose(); });
        }
      });

      if (!triangles?.length && !pcbBody) return;

      // VS-FE: 每次重渲染重置渲染來源 telemetry
      window.resetRenderTelemetry?.();

      const s = 2.0 / maxExtent;
      const baseLen = triangles?._hasLid ? triangles._baseLen : (triangles?.length || 0);

      const _buildSubMesh = (startIdx, count, name, opacity) => {
        if (count <= 0) return null;
        const pos = new Float32Array(count * 9);
        const nrm = new Float32Array(count * 9);
        for (let i = 0; i < count; i++) {
          const t = triangles[startIdx + i];
          const [nx, ny, nz] = t.normal;
          for (let j = 0; j < 3; j++) {
            const [vx, vy, vz] = t.vertices[j];
            const idx = i * 9 + j * 3;
            pos[idx] = (vx - cx) * s; pos[idx+1] = (vz - cz) * s; pos[idx+2] = -(vy - cy) * s;
            nrm[idx] = nx;             nrm[idx+1] = nz;            nrm[idx+2] = -ny;
          }
        }
        const geo = new T.BufferGeometry();
        geo.setAttribute('position', new T.BufferAttribute(pos, 3));
        geo.setAttribute('normal', new T.BufferAttribute(nrm, 3));
        const [r, g, b] = roleRGB;
        const mat = new T.MeshPhysicalMaterial({
          color: new T.Color(r / 255, g / 255, b / 255),
          transparent: true, opacity,
          roughness: 0.12, metalness: 0.0,
          clearcoat: 1.0, clearcoatRoughness: 0.04,
          side: T.DoubleSide, depthWrite: false,
        });
        const shown = opacity > 0;  // VS-FE: opacity 0 = 圖層關閉 → mesh/邊框/陰影一併隱藏
        const mesh = new T.Mesh(geo, mat);
        mesh.name = name;
        mesh.renderOrder = name === 'stlMesh' ? 1 : 2;
        mesh.castShadow = shown;
        mesh.visible = shown;
        st.scene.add(mesh);
        // Edge lines
        const edgeGeo = new T.EdgesGeometry(geo, 30);
        const edgeMat = new T.LineBasicMaterial({
          color: new T.Color(r / 500, g / 500, b / 500),
          transparent: true, opacity: shown ? Math.max(opacity * 0.5, 0.15) : 0,
        });
        const edges = new T.LineSegments(edgeGeo, edgeMat);
        edges.name = name === 'stlMesh' ? 'stlEdges' : 'stlEdgesLid';
        edges.visible = shown;
        st.scene.add(edges);
        return mesh;
      };

      // VS-FE: 用「當前 base/lid opacity」建 mesh（非硬編 0.82）。否則 geometry 重建會把
      // toggle 關掉的圖層以 0.82 重新顯示 —— 這是「人為旋轉/auto-rotate 後回復初始全顯示」主因。
      const baseMesh = _buildSubMesh(0, baseLen, 'stlMesh', baseOpacity ?? 0.82);
      if (triangles?._hasLid) {
        _buildSubMesh(baseLen, triangles.length - baseLen, 'stlMeshLid', lidOpacity ?? 0.82);
      }

      // PCB body: GLB (multi-color) → STL (single-color) → fallback box
      if (pcbBody) {
        const pOff = pcbBody.pcbBottomZ || 0;
        // RF1: GLB 後端已轉 Y-up (pcb_common._export_glb)，前端只做平移+縮放。
        // STL 仍 Z-up（_buildSubMesh 自帶 rotation），故 cx/cy/cz 為 Z-up 中心，
        // GLB 中心 = (cx, cz, -cy)，pOff (原 Z 方向 offset) → 新 Y 方向。
        const writeXform = (out, idx, x, y, z) => {
          out[idx]     = (x - cx) * s;
          out[idx + 1] = (y + pOff - cz) * s;
          out[idx + 2] = (z + cy) * s;
        };
        const isMetallicColor = (r, g, b) =>
          (r > 150 && g > 150 && b > 150) || (r > 180 && g > 130 && b < 60);

        if (pcbBody.glbMeshes && pcbBody.glbMeshes.length > 0) {
          // ── GLB multi-color render (IC/pin/LED individual colors) ──
          const group = new T.Group();
          group.name = 'pcbBody';

          for (const m of pcbBody.glbMeshes) {
            const geo = new T.BufferGeometry();
            const p = m.positions;
            const transformed = new Float32Array(p.length);
            for (let i = 0; i < p.length; i += 3) {
              writeXform(transformed, i, p[i], p[i+1], p[i+2]);
            }
            geo.setAttribute('position', new T.BufferAttribute(transformed, 3));
            if (m.normals) {
              // RF1: GLB 後端已 Y-up，normal 直接複製不再 swap。
              geo.setAttribute('normal',
                new T.BufferAttribute(new Float32Array(m.normals), 3));
            } else {
              geo.computeVertexNormals();
            }
            if (m.indices) geo.setIndex(new T.BufferAttribute(m.indices, 1));

            const [cr, cg, cb] = m.color;
            const metallic = isMetallicColor(cr, cg, cb);
            const mat = new T.MeshPhysicalMaterial({
              color: new T.Color(cr/255, cg/255, cb/255),
              roughness: metallic ? 0.25 : 0.50,
              metalness: metallic ? 0.70 : 0.03,
              clearcoat: metallic ? 0.0 : 0.2,
              side: T.DoubleSide,
            });
            const mesh = new T.Mesh(geo, mat);
            mesh.castShadow = true;
            group.add(mesh);
          }
          group.renderOrder = 0;
          st.scene.add(group);
          window.recordRender?.('pcbBody', 'glb');
        } else if (pcbBody.triangles && pcbBody.triangles.length > 0) {
          // ── STL single-color fallback ──
          const pcbTris = pcbBody.triangles;
          const pos = new Float32Array(pcbTris.length * 9);
          const nrm = new Float32Array(pcbTris.length * 9);
          for (let i = 0; i < pcbTris.length; i++) {
            const t = pcbTris[i];
            const [nx, ny, nz] = t.normal;
            for (let j = 0; j < 3; j++) {
              const [vx, vy, vz] = t.vertices[j];
              const idx = i * 9 + j * 3;
              writeXform(pos, idx, vx, vy, vz);
              nrm[idx] = nx; nrm[idx+1] = nz; nrm[idx+2] = -ny;
            }
          }
          const geo = new T.BufferGeometry();
          geo.setAttribute('position', new T.BufferAttribute(pos, 3));
          geo.setAttribute('normal', new T.BufferAttribute(nrm, 3));
          const mat = new T.MeshPhysicalMaterial({
            color: new T.Color(0.00, 0.33, 0.42),
            roughness: 0.50, metalness: 0.02, clearcoat: 0.25, side: T.DoubleSide,
          });
          const pcbMesh = new T.Mesh(geo, mat);
          pcbMesh.name = 'pcbBody';
          pcbMesh.castShadow = true;
          st.scene.add(pcbMesh);
          window.recordRender?.('pcbBody', 'stl');
        } else {
          // ── Fallback: PCB box (with edges) ──
          const { length: pl, width: pw, height: ph } = pcbBody;
          const pcbW = pl * s * 0.90, pcbD = pw * s * 0.90, pcbH = (ph || 1.6) * s;
          const plateGeo = new T.BoxGeometry(pcbW, pcbH, pcbD);
          const plateMat = new T.MeshPhysicalMaterial({
            color: new T.Color(0.02, 0.32, 0.18),
            roughness: 0.50, metalness: 0.03, clearcoat: 0.25, side: T.DoubleSide,
          });
          const plate = new T.Mesh(plateGeo, plateMat);
          const baseMeshRef = st.scene.getObjectByName('stlMesh');
          if (baseMeshRef) {
            const bb = new T.Box3().setFromObject(baseMeshRef);
            plate.position.set(0, bb.min.y + 2 * s + pcbH / 2, 0);
          } else {
            plate.position.set(0, 0, 0);
          }
          plate.castShadow = true;
          plate.name = 'pcbBody';
          st.scene.add(plate);
          window.recordRender?.('pcbBody', 'box');
          const pcbEdgeGeo = new T.EdgesGeometry(plateGeo, 30);
          const pcbEdgeMat = new T.LineBasicMaterial({ color: 0x003322, transparent: true, opacity: 0.6 });
          const pcbEdges = new T.LineSegments(pcbEdgeGeo, pcbEdgeMat);
          pcbEdges.position.copy(plate.position);
          pcbEdges.name = 'pcbEdges';
          st.scene.add(pcbEdges);
        }

        // ── Port overlays (STL / box only; GLB 已含 IC/LED/pin 子 mesh，疊加會重複) ──
        const ports = pcbBody.ports;
        const SHAPES = { ...(window.__IC_CONN_SHAPES || {}), ...(window.__PASSIVE_MECH_SHAPES || {}) };
        if (ports && ports.length && !(pcbBody.glbMeshes?.length)) {
          const group = new T.Group();
          group.name = 'pcbPorts';
          const mmL = pcbBody.length, mmW = pcbBody.width;
          const sc = s * 0.90;
          const pcbW = mmL * sc, pcbD = mmW * sc;
          const pcbH = (pcbBody.height || 1.6) * s;
          const pcbObj = st.scene.getObjectByName('pcbBody');
          const py = pcbObj ? new T.Box3().setFromObject(pcbObj).getCenter(new T.Vector3()).y : 0;
          for (const p of ports) {
            let portGroup = null;

            // Priority 1: Pre-loaded mesh model (OCP tessellation → mesh.json)
            const mKey = _modelKey(p.shape, p.params || { pins: p.pins, pitch: p.pitch, rows: p.rows });
            const meshData = mKey && window.__MODEL_MESHES[mKey];
            if (meshData && meshData.parts) {
              portGroup = new T.Group();
              for (const part of meshData.parts) {
                const geo = new T.BufferGeometry();
                const srcV = part.vertices, vLen = srcV.length;
                const verts = new Float32Array(vLen);
                for (let vi = 0; vi < vLen; vi += 3) {
                  verts[vi] = srcV[vi]; verts[vi+1] = srcV[vi+2]; verts[vi+2] = -srcV[vi+1];
                }
                geo.setAttribute('position', new T.BufferAttribute(verts, 3));
                if (part.normals) {
                  const srcN = part.normals;
                  const nrms = new Float32Array(srcN.length);
                  for (let ni = 0; ni < srcN.length; ni += 3) {
                    nrms[ni] = srcN[ni]; nrms[ni+1] = srcN[ni+2]; nrms[ni+2] = -srcN[ni+1];
                  }
                  geo.setAttribute('normal', new T.BufferAttribute(nrms, 3));
                } else {
                  geo.computeVertexNormals();
                }
                if (part.indices) geo.setIndex(new T.BufferAttribute(new Uint32Array(part.indices), 1));
                const [cr, cg, cb] = part.color || [128, 128, 128];
                const mt = new T.MeshPhysicalMaterial({
                  color: new T.Color(cr / 255, cg / 255, cb / 255),
                  roughness: part.roughness ?? 0.5, metalness: part.metalness ?? 0.1,
                  side: T.DoubleSide,
                });
                const m = new T.Mesh(geo, mt); m.castShadow = true;
                m.scale.set(sc, sc, sc);
                portGroup.add(m);
              }
              window.recordRender?.('port', 'mesh', { shape: p.shape });
            }

            // Priority 2: Procedural shape builder (current rendering path)
            if (!portGroup && p.shape) {
              const builder = SHAPES[p.shape];
              if (builder) {
                try {
                  if (p.params) {
                    const pr = p.params;
                    const bw = pr.bodyW || pr.diameter || 4;
                    const bh = pr.bodyD || pr.rowSpacing || bw;
                    const bd = pr.bodyH || pr.height || Math.min(bw, bh) * 0.4;
                    portGroup = builder(bw, bh, bd, sc, p.color || '#888', pr);
                  } else {
                    const pw = p.w || 4, ph = p.h || pw;
                    const pd = p.d || Math.min(pw, ph) * 0.4;
                    portGroup = builder(pw, ph, pd, sc, p.color || '#888',
                      { pins: p.pins, pitch: p.pitch, rows: p.rows });
                  }
                } catch (e) {
                  portGroup = null;
                  window.recordRender?.('error', 'procedural', { shape: p.shape, error: String(e) });
                }
                if (portGroup) window.recordRender?.('port', 'procedural', { shape: p.shape });
              }
            }

            // Priority 3: Ghost box fallback — unregistered shape, always an error
            if (!portGroup) {
              let bw, bd, bh;
              if (p.params) {
                bw = (p.params.bodyW || p.params.diameter || 4) * sc;
                bd = (p.params.bodyD || p.params.bodyW || 4) * sc;
                bh = (p.params.bodyH || 2) * sc;
              } else {
                const pw = p.w || 4, ph = p.h || pw;
                bw = pw * sc; bd = ph * sc;
                bh = (p.d || Math.min(pw, ph) * 0.4) * sc;
              }
              const geo = new T.BoxGeometry(bw, bh, bd);
              const mt = new T.MeshStandardMaterial({
                color: new T.Color(p.color || '#888'), roughness: 0.6, metalness: 0.1,
              });
              const m = new T.Mesh(geo, mt);
              m.position.y = bh / 2; m.castShadow = true;
              portGroup = new T.Group(); portGroup.add(m);
              console.error('[scene-3d] render degraded: shape "' + (p.shape || 'undefined') + '" (label: ' + (p.label || '?') + ') has no procedural builder — fell back to ghost box');
              window.recordRender?.('port', 'ghost', { shape: p.shape });
            }

            if (p.rot) portGroup.rotation.y = p.rot * Math.PI / 180;

            let cx3, cz3;
            if (p.cx !== undefined) {
              ({ x: cx3, z: cz3 } = _pcbToScene(p.cx, p.cy, mmL, mmW, sc));
            } else {
              const pw = p.w || 4, ph = p.h || pw;
              ({ x: cx3, z: cz3 } = _pcbToScene(p.x + pw / 2, p.y + ph / 2, mmL, mmW, sc));
            }

            if (p.side === 'face' || !p.side) {
              portGroup.position.set(cx3, py + pcbH / 2, cz3);
            } else if (p.side === 'bottom') {
              portGroup.position.set(cx3, py - pcbH / 2, cz3);
              portGroup.rotation.x = Math.PI;
            } else if (p.side === 'left') {
              portGroup.position.set(-pcbW / 2, py, cz3);
              portGroup.rotation.z = Math.PI / 2;
            } else if (p.side === 'right') {
              portGroup.position.set(pcbW / 2, py, cz3);
              portGroup.rotation.z = -Math.PI / 2;
            } else if (p.side === 'top') {
              portGroup.position.set(cx3, py, -pcbD / 2);
              portGroup.rotation.x = -Math.PI / 2;
            } else if (p.side === 'back') {
              portGroup.position.set(cx3, py, pcbD / 2);
              portGroup.rotation.x = Math.PI / 2;
            }
            group.add(portGroup);
          }
          st.scene.add(group);
        }
      }

      // Ground alignment
      if (baseMesh) {
        const bbox = new T.Box3().setFromObject(baseMesh);
        st.ground.position.y = bbox.min.y - 0.02;
      } else {
        const pcbRef = st.scene.getObjectByName('pcbBody');
        if (pcbRef) {
          const bbox = new T.Box3().setFromObject(pcbRef);
          st.ground.position.y = bbox.min.y - 0.02;
        }
      }
      // Render immediately after mesh rebuild
      st.renderer.render(st.scene, st.camera);
    }, [triangles, cx, cy, cz, maxExtent, roleRGB, pcbBody]);

    // ── Opacity update (toggle only changes material, no geometry rebuild) ──
    React.useEffect(() => {
      const st = stateRef.current;
      if (!st) return;
      const _updateOp = (name, op) => {
        const obj = st.scene.getObjectByName(name);
        if (!obj) return;
        const shown = op > 0;  // VS-FE: 關閉圖層須整個隱藏(連邊框/陰影),非僅 opacity→0.15 殘影
        obj.visible = shown;
        obj.castShadow = shown;
        if (obj.material) { obj.material.opacity = op; obj.material.transparent = true; obj.material.needsUpdate = true; }
        const edgeName = name === 'stlMesh' ? 'stlEdges' : 'stlEdgesLid';
        const edge = st.scene.getObjectByName(edgeName);
        if (edge) {
          edge.visible = shown;
          if (edge.material) { edge.material.opacity = shown ? Math.max(op * 0.5, 0.15) : 0; edge.material.needsUpdate = true; }
        }
      };
      _updateOp('stlMesh', baseOpacity ?? 0.82);
      _updateOp('stlMeshLid', lidOpacity ?? 0.82);
      st.renderer.render(st.scene, st.camera);
    }, [baseOpacity, lidOpacity]);

    // ── Per-frame render (camera update) ──
    React.useEffect(() => {
      const st = stateRef.current;
      if (!st) return;

      const ry = (rotY * Math.PI) / 180;
      const rx = (rotX * Math.PI) / 180;
      const d = 5;
      st.camera.position.set(
        d * Math.sin(ry) * Math.cos(rx),
        d * Math.sin(rx),
        d * Math.cos(ry) * Math.cos(rx)
      );
      // Handle top/bottom gimbal lock: up vector must not be parallel to view
      const absRx = Math.abs(rotX);
      if (absRx > 85) {
        st.camera.up.set(0, 0, rotX > 0 ? -1 : 1);
      } else {
        st.camera.up.set(0, 1, 0);
      }
      st.camera.lookAt(0, 0, 0);

      // Zoom → adjust orthographic projection range
      const f = st.frust / zoom;
      const el = st.renderer.domElement.parentNode;
      const a = (el?.clientWidth || 1) / (el?.clientHeight || 1);
      st.camera.left = -f * a; st.camera.right = f * a;
      st.camera.top = f; st.camera.bottom = -f;
      st.camera.updateProjectionMatrix();

      // Main light follows camera offset
      st.dir.position.set(
        st.camera.position.x + 2,
        st.camera.position.y + 4,
        st.camera.position.z + 2
      );

      st.renderer.render(st.scene, st.camera);
    }, [rotY, rotX, zoom]);
  }

  // ─── Export to window ─────────────────
  Object.assign(window, {
    ROLE_RGB,
    useComponentScene,
    __axisTransform: {  // VS-AXIS: 供 tests/axis_roundtrip.test.js 往返驗
      pcbToScene: _pcbToScene, sceneToPcb: _sceneToPcb,
      zUpToYUp: _zUpToYUp, yUpToZUp: _yUpToZUp,
    },
  });
})();
