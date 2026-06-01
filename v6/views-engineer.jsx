// views-engineer.jsx — v6 React UI panels (Engineer phase)
// Scene logic: engineer/scene-3d.js | Viewport: engineer/viewport-controls.js (INF1-S3)
// Sub-components: views-engineer-code.jsx (CodeView, BomView)

const use3DInteraction    = window.use3DInteraction;
const _COMPONENT_DIM_TABLE = window.COMPONENT_DIMENSIONS;
const getComponentDim     = window.getDimByClass;
const ViewCube            = window.ViewCube;
const ViewControls        = window.ViewControls;
const useComponentScene   = window.useComponentScene;
const ROLE_RGB            = window.ROLE_RGB;

function shortLabel(type) {
  return (type || '').replace(/-class$/, '').replace(/_/g, ' ').split('-').slice(-2).join('-');
}
function _isModuleBoard(type) {
  if (!type) return false;
  return /Module|OLED|LCD|Display|E-Ink|Fingerprint/i.test(type) ||
    /^Sensor-|DHT|BME|SHT|Soil/i.test(type) || /L298N|NRF|MSGEQ7|MPPT/i.test(type);
}

// ─── Components 3D View（單元件 STL viewer + 右側列表切換） ─────────────────

function ComponentsView({ onNavigate, store }) {
  const components = (store?.components || []).filter(c => !(c.spec?.skip_enclosure));
  const { rotY, rotX, dragging, autoRotate, setAutoRotate, onPointerDown, setView } = use3DInteraction();
  const [selected, setSelected] = React.useState(0);
  const [zoom, setZoom] = React.useState(1.0);
  const [stlCache, setStlCache] = React.useState({});
  const [metaCache, setMetaCache] = React.useState({});
  const [visibleLayers, setVisibleLayers] = React.useState(new Set(['base', 'lid', 'pcb']));
  const [renderVerdict, setRenderVerdict] = React.useState(null);  // VS-FE: 3D 渲染保真 verdict
  const viewportRef = React.useRef(null);
  const threeRef = React.useRef(null);

  const selectedComp = components[selected] || components[0];
  const selectedType = selectedComp?.type || '';

  // Fetch STL when selected changes
  React.useEffect(() => {
    if (!selectedType) return;
    const cached = stlCache[selectedType];
    if (Array.isArray(cached) || cached === 'loading') return;
    setStlCache(prev => ({ ...prev, [selectedType]: 'loading' }));
    const cannedShell = (store?.componentShells || []).find(s => s.class === selectedType);
    const _attachPcb = (tagged, pcbBuf, parsedCache) => {
      if (parsedCache) {
        if (parsedCache.isGLB) { tagged._pcbGLB = parsedCache.parts; tagged._pcbTris = []; }
        else { tagged._pcbTris = parsedCache.triangles; }
        return;
      }
      if (!pcbBuf) return;
      if (pcbBuf._isGLB) { tagged._pcbGLB = window.parseGLB(pcbBuf); tagged._pcbTris = []; }
      else { tagged._pcbTris = parseBinarySTL(pcbBuf); }
    };
    // VS-FE: 殼體 base/lid 也可能是 GLB（端點 GLB-first，見 routes_design）；GLB→tris
    // （殼體均勻色，轉三角即可走既有渲染）。不處理 → GLB 被當 STL 解析爆界、卡 loading、退 box。
    // RF1: GLB 後端已轉 Y-up；殼體 tris 需 Z-up（_buildSubMesh 做 Z→Y swap）。
    // 故此處 Y-up→Z-up: (x,y,z)→(x,-z,y)，法線由轉換後頂點重算。
    const _glbToTris = (meshes) => {
      const tris = [];
      for (const m of (meshes || [])) {
        const pos = m.positions; if (!pos) continue;
        const idx = m.indices, n = idx ? idx.length : Math.floor(pos.length / 3);
        for (let i = 0; i + 2 < n; i += 3) {
          const ia = idx ? idx[i] : i, ib = idx ? idx[i + 1] : i + 1, ic = idx ? idx[i + 2] : i + 2;
          // Y-up→Z-up: (gx, gy, gz) → (gx, -gz, gy)
          const a = [pos[ia * 3], -pos[ia * 3 + 2], pos[ia * 3 + 1]];
          const b = [pos[ib * 3], -pos[ib * 3 + 2], pos[ib * 3 + 1]];
          const c = [pos[ic * 3], -pos[ic * 3 + 2], pos[ic * 3 + 1]];
          let nx = (b[1] - a[1]) * (c[2] - a[2]) - (b[2] - a[2]) * (c[1] - a[1]);
          let ny = (b[2] - a[2]) * (c[0] - a[0]) - (b[0] - a[0]) * (c[2] - a[2]);
          let nz = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
          const L = Math.hypot(nx, ny, nz) || 1;
          tris.push({ normal: [nx / L, ny / L, nz / L], vertices: [a, b, c] });
        }
      }
      return tris;
    };
    const _parseShell = (buf) => buf._isGLB ? _glbToTris(window.parseGLB(buf)) : parseBinarySTL(buf);
    Promise.all([
      API.getShellSTL(selectedType, 'base').catch(() => null),
      API.getShellSTL(selectedType, 'lid').catch(() => null),
      (window.getParsedGeometry
        ? window.getParsedGeometry(selectedType, 'pcb_body')
        : API.getShellSTL(selectedType, 'pcb_body')
      ).catch(() => null),
      API.getShellMeta(selectedType).catch(() => null),
    ]).then(([baseBuf, lidBuf, pcbData, meta]) => {
      const pcbParsed = pcbData && typeof pcbData === 'object' && 'isGLB' in pcbData ? pcbData : null;
      const pcbBuf = pcbParsed ? null : pcbData;
      if (meta) setMetaCache(prev => ({ ...prev, [selectedType]: meta }));
      try {
        if (baseBuf) {
          const baseTris = _parseShell(baseBuf);
          const lidTris = lidBuf ? _parseShell(lidBuf) : [];
          let lidShifted = [];
          if (lidTris.length) {
            let baseMaxZ = -Infinity, lidMaxZ = -Infinity;
            for (const t of baseTris) for (const v of t.vertices) { if (v[2] > baseMaxZ) baseMaxZ = v[2]; }
            for (const t of lidTris) for (const v of t.vertices) { if (v[2] > lidMaxZ) lidMaxZ = v[2]; }
            lidShifted = lidTris.map(t => ({ normal: t.normal, vertices: t.vertices.map(([x, y, z]) => [x, y, z + baseMaxZ + lidMaxZ]) }));
          }
          const tagged = [...baseTris, ...lidShifted];
          tagged._baseLen = baseTris.length; tagged._hasLid = lidShifted.length > 0;
          _attachPcb(tagged, pcbBuf, pcbParsed);
          setStlCache(prev => ({ ...prev, [selectedType]: tagged })); return;
        }
        if (pcbBuf || pcbParsed) {
          const tagged = []; tagged._baseLen = 0; tagged._hasLid = false; tagged._pcbOnly = true;
          _attachPcb(tagged, pcbBuf, pcbParsed);
          setStlCache(prev => ({ ...prev, [selectedType]: tagged })); return;
        }
      } catch (e) {
        // 殼體解析失敗（壞檔/格式不符）→ 明確 error 狀態，不留 'loading' 卡死（VS-FE）
        console.error('[ComponentsView] 殼體解析失敗', selectedType, e);
        setStlCache(prev => ({ ...prev, [selectedType]: store?.isCanned ? 'flat' : 'error' })); return;
      }
      let demoUrl = cannedShell?.stl;
      if (!demoUrl && selectedComp?.role === 'Brain') {
        const bottom = (store?.stlFiles || []).find(f => f.label === '底座' || /bottom/i.test(f.name));
        demoUrl = bottom?.url;
      }
      if (demoUrl) {
        fetch(demoUrl).then(r => r.ok ? r.arrayBuffer() : Promise.reject())
          .then(buf2 => setStlCache(prev => ({ ...prev, [selectedType]: parseBinarySTL(buf2) })))
          .catch(() => setStlCache(prev => ({ ...prev, [selectedType]: 'error' }))); return;
      }
      setStlCache(prev => ({ ...prev, [selectedType]: store?.isCanned ? 'flat' : 'error' }));
    });
  }, [selectedType, store?.componentShells]);

  // Non-passive wheel listener for zoom
  React.useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const handler = (e) => { e.preventDefault(); setZoom(z => Math.max(0.3, Math.min(4.0, z - e.deltaY * 0.002))); };
    el.addEventListener('wheel', handler, { passive: false });
    return () => el.removeEventListener('wheel', handler);
  }, []);

  const stlData = stlCache[selectedType];
  const isLoading = stlData === 'loading';
  const isError = stlData === 'error';
  const isFlat = stlData === 'flat';
  const triangles = Array.isArray(stlData) ? stlData : null;
  const isPcbOnly = triangles?._pcbOnly === true;

  const { cx, cy, cz, maxExtent } = React.useMemo(() => {
    const _gMax = () => { let g = 1; for (const c of components) { const s2 = c.spec || {}; g = Math.max(g, s2.length_mm || 0, s2.width_mm || 0, s2.height_mm || 0); } return g; };
    if (!triangles || !triangles.length) {
      if (isFlat || isPcbOnly) { const cs = selectedComp?.spec || {}; return { cx: 0, cy: 0, cz: 0, maxExtent: Math.max(_gMax(), cs.length_mm || 30, cs.width_mm || 20) }; }
      return { cx: 0, cy: 0, cz: 0, maxExtent: 1 };
    }
    let minX = Infinity, minY = Infinity, minZ = Infinity, maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    for (const t of triangles) for (const [x, y, z] of t.vertices) { if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y; if (z < minZ) minZ = z; if (z > maxZ) maxZ = z; }
    const refMax = Math.max(_gMax(), maxX - minX, maxY - minY, maxZ - minZ, 1);
    return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, cz: (minZ + maxZ) / 2, maxExtent: refMax };
  }, [triangles, components.length, isFlat, selectedType]);

  const roleRGB = ROLE_RGB[selectedComp?.role] || [125, 211, 252];

  // ─── Layer visibility → opacity ───
  const vBase = visibleLayers.has('base');
  const vLid  = visibleLayers.has('lid');
  const vPcb  = visibleLayers.has('pcb') || isFlat || isPcbOnly;
  const soloCount = (vBase?1:0) + (vLid?1:0) + (vPcb?1:0);
  const shellOp = soloCount === 1 ? 0.88 : (vPcb ? 0.22 : 0.50);
  const baseOp = (isFlat || isPcbOnly) ? 0.0 : (vBase ? shellOp : 0.0);
  const lidOp  = (isFlat || isPcbOnly) ? 0.0 : (vLid  ? shellOp : 0.0);

  const isBrain = selectedComp?.role === 'Brain';
  const sp = selectedComp?.spec || {};
  const hasPcbGLB = triangles?._pcbGLB?.length > 0;
  const hasPcbStl = triangles?._pcbTris?.length > 0;
  const hasPcb = hasPcbGLB || hasPcbStl;
  const showPcb = vPcb && (isBrain || hasPcb || isFlat || isPcbOnly);
  const metaSpec = metaCache[selectedType]?.meta?.spec_dict || {};
  const pcbBottomZ = isPcbOnly ? 0 : metaSpec.base_h ? (-metaSpec.base_h / 2 + (metaSpec.wall || 2) + 5.0) : 0;

  // 穩定化:getDimByClass 每次回傳新物件(spread),不 memo 會使 pcbBody useMemo 每幀重算
  // → geometry effect 每幀重建 → 蓋掉 toggle/旋轉重置全顯示(VS-FE churn 根因)
  const dimEntry = React.useMemo(() => getComponentDim(selectedComp), [selectedType]);
  const pcbBody = React.useMemo(() => showPcb ? {
    glbMeshes: hasPcbGLB ? triangles._pcbGLB : null,
    triangles: hasPcbStl ? triangles._pcbTris : null,
    length: sp.length_mm || dimEntry?.l || 70,
    width: sp.width_mm || dimEntry?.w || 55,
    height: (isFlat || isPcbOnly) ? 3.0 : 1.6, pcbBottomZ,
    ports: dimEntry?.ports || [],
  } : null, [showPcb, hasPcbGLB, hasPcbStl, triangles, sp.length_mm, sp.width_mm, isFlat, isPcbOnly, pcbBottomZ, dimEntry]);

  useComponentScene(threeRef, (isFlat || isPcbOnly) ? [] : triangles, rotY, rotX, zoom, cx, cy, cz, maxExtent, roleRGB, baseOp, lidOp, pcbBody);

  // VS-FE: 渲染後讀 verdict。deps 必須用穩定 primitive（triangles 數 / pcbBody 有無）—
  // 不可用 triangles/pcbBody 物件 identity，否則 auto-rotate 每幀重渲染會讓此 effect 反覆
  // 執行、verdict 永遠不 commit（badge 不顯示）。scene effect 先跑已同步埋好 telemetry，直接讀。
  const _triN = triangles ? triangles.length : 0;
  const _hasPcb = pcbBody ? 1 : 0;
  React.useEffect(() => {
    if (isError) { setRenderVerdict(null); return; }
    // 不以 isLoading 抑制：Brain/PCB 在 STL 載入中即已渲染（可能 box 降級），
    // verdict 非 EMPTY（有東西渲染）就顯示，讓「方塊降級」可見而非被 loading 蓋掉。
    const v = window.verifyRenderFidelity?.();
    setRenderVerdict(v && v.verdict !== 'EMPTY' ? v : null);
  }, [selectedType, isLoading, isError, _triN, _hasPcb]);

  const shellMeta = metaCache[selectedType];
  const shellDims = shellMeta?.['shell.meta'] || shellMeta?.['shell_meta'] || {};

  return (
    <div key="components-3d" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '1fr 260px' }}>
        {/* 3D Viewport */}
        <div ref={viewportRef} onPointerDown={onPointerDown} style={{
          position: 'relative', overflow: 'hidden',
          background: 'radial-gradient(ellipse at 50% 40%, rgba(40,35,55,0.4) 0%, var(--bg-0) 70%)',
          cursor: dragging ? 'grabbing' : 'grab', userSelect: 'none',
        }}>
          <div ref={threeRef} style={{ position: 'absolute', inset: 0 }} />

          {isLoading && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 5 }}>
              <span style={{ fontSize: 13, color: 'var(--text-tertiary)', animation: 'dotPulse 1.5s ease infinite' }}>載入 STL 中…</span>
            </div>
          )}

          {isError && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 5, flexDirection: 'column', gap: 8 }}>
              <div style={{ fontSize: 32 }}>{store?.isCanned ? '🎯' : '⚠'}</div>
              <div style={{ fontSize: 14, color: 'var(--accent)', fontWeight: 600 }}>
                {store?.isCanned ? 'Demo 預覽：元件殼待 Fork 後生成' : 'Shell 不存在'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{selectedType}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', maxWidth: 320, textAlign: 'center', lineHeight: 1.5 }}>
                {store?.isCanned
                  ? '範本未含 STL 檔案；點右上「Fork 為新專案」後執行 Phase IV (build123d) 即可生成可旋轉檢視的元件殼。'
                  : '此元件尚未建立 3D 殼模型。請先執行 Pipeline Phase IV 生成元件殼，或確認 shells/ 目錄包含此元件。'}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                <button onClick={() => onNavigate('schematic')} style={{ padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--bg-3)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer' }}>← Schematic</button>
                <button onClick={() => onNavigate('assembly')} style={{ padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--accent)', border: 'none', color: 'var(--text-inverse)', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}>下一頁 · 組裝預覽 →</button>
              </div>
            </div>
          )}

          {/* Header */}
          <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex', alignItems: 'center', gap: 8, zIndex: 2 }}>
            <Badge color="var(--6e-engineer)" bg="rgba(180,130,255,0.12)">Engineer</Badge>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Component Shell · {shortLabel(selectedType)}</span>
          </div>
          {/* VS-FE: 渲染保真 verdict — 獨立一列（top:42）避開中央 layer toggles 遮擋；ghost/box 降級→紅色可讀信號 */}
          {renderVerdict && (
            <div style={{ position: 'absolute', top: 42, left: 12, zIndex: 3 }}>
              {renderVerdict.verdict === 'PASS'
                ? <Badge color="var(--green)" bg="var(--green-dim)">渲染 ✓</Badge>
                : <span title={`渲染降級：${renderVerdict.n_degraded} 占位方塊 / ${renderVerdict.n_error} 錯誤${renderVerdict.pcb_degraded ? '；PCB 本體降級' : ''}`}>
                    <Badge color="var(--red)" bg="var(--red-dim)">⚠ {renderVerdict.verdict === 'EMPTY' ? '空畫面' : `渲染降級 ${renderVerdict.n_degraded}`}</Badge>
                  </span>}
            </div>
          )}

          <ViewControls rotY={rotY} rotX={rotX} autoRotate={autoRotate} onAutoToggle={() => setAutoRotate(a => !a)} />

          {/* Layer toggle buttons */}
          {!isFlat && (triangles?._hasLid || hasPcb || isBrain) && (
            <div onPointerDown={e => e.stopPropagation()} style={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', display: 'flex', gap: 4, zIndex: 2 }}>
              {[
                { id: 'base', label: '底座', icon: '🔻' },
                ...(triangles?._hasLid ? [{ id: 'lid', label: '頂蓋', icon: '🔺' }] : []),
                ...((hasPcb || isBrain) ? [{ id: 'pcb', label: 'PCB', icon: '🔵' }] : []),
              ].map(m => {
                const active = visibleLayers.has(m.id);
                return (
                  <button key={m.id} onClick={() => setVisibleLayers(prev => {
                    const next = new Set(prev);
                    if (next.has(m.id)) { if (next.size > 1) next.delete(m.id); } else next.add(m.id);
                    return next;
                  })} style={{
                    padding: '5px 12px', borderRadius: 'var(--r-sm)',
                    background: active ? 'var(--accent-dim)' : 'var(--bg-glass)',
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border-subtle)'}`,
                    color: active ? 'var(--accent)' : 'var(--text-tertiary)',
                    fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                    backdropFilter: 'blur(8px)', transition: 'all 0.15s', opacity: active ? 1.0 : 0.5,
                  }}>
                    {m.icon} {m.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Bottom info */}
          <div style={{ position: 'absolute', bottom: 12, left: 12, background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)', padding: '10px 14px', backdropFilter: 'blur(8px)', fontSize: 11, zIndex: 2 }}>
            <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>
              {triangles && triangles.length > 0 ? `${triangles.length} faces` : isFlat ? 'PCB module' : '—'} · Three.js · zoom {(zoom * 100).toFixed(0)}%
            </div>
            {shellDims.ol != null && (
              <div style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                殼: {shellDims.ol}×{shellDims.ow}×{shellDims.oh} mm
                {shellDims.cutouts > 0 && <span style={{ color: 'var(--accent)' }}> · {shellDims.cutouts} cutouts</span>}
              </div>
            )}
          </div>

          <ViewCube setView={setView} />
        </div>

        {/* Right panel: component list */}
        <aside style={{ borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-1)', overflow: 'auto', padding: '18px 14px', display: 'flex', flexDirection: 'column', gap: 6, animation: 'slideUp 0.4s var(--ease-out) 200ms both' }}>
          <SectionLabel style={{ marginBottom: 4 }}>Components ({components.length})</SectionLabel>
          {components.map((c, i) => {
            const rc = ROLE_COLOR[c.role] || {};
            const isSel = selected === i;
            const cached = stlCache[c.type];
            const hasShell = Array.isArray(cached);
            const shellErr = cached === 'error';
            return (
              <div key={i} onClick={() => setSelected(i)} style={{ padding: '10px 12px', borderRadius: 'var(--r-sm)', background: isSel ? 'var(--bg-active)' : 'var(--bg-2)', border: `1px solid ${isSel ? rc.c || 'var(--accent)' : 'var(--border-subtle)'}`, fontSize: 12, cursor: 'pointer', transition: 'all 0.15s' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2, background: rc.c || 'var(--text-tertiary)', flexShrink: 0 }} />
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600, flex: 1 }}>{shortLabel(c.type)}</span>
                  {hasShell && <span style={{ fontSize: 9, color: 'var(--green)' }}>✓</span>}
                  {shellErr && <span style={{ fontSize: 9, color: 'var(--accent)' }}>⚠</span>}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', marginTop: 2, display: 'flex', justifyContent: 'space-between' }}>
                  <span>{c.role}</span>
                  <span>{c.type}</span>
                </div>
              </div>
            );
          })}
          {components.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: '12px 0' }}>尚未選定元件</div>
          )}

          {/* CH3 debug panel */}
          {store?.ch3_source && (
            <details className="ch3-debug-panel" style={{ marginTop: 12, padding: '10px 12px', background: 'var(--bg-2)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: 11 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)', fontWeight: 600, fontFamily: 'var(--font-mono)', userSelect: 'none' }}>
                CH3 雙階段推理 · <span style={{ color: 'var(--accent)' }}>{store.ch3_source}</span>
              </summary>
              <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: 10, marginBottom: 4, fontFamily: 'var(--font-mono)' }}>PLAN · 高層決策</div>
                  <pre style={{ margin: 0, padding: 8, background: 'var(--bg-0)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{store.ch3_plan ? JSON.stringify(store.ch3_plan, null, 2) : '— (no plan)'}</pre>
                </div>
                <div>
                  <div style={{ color: 'var(--text-tertiary)', fontSize: 10, marginBottom: 4, fontFamily: 'var(--font-mono)' }}>PARAMS · 低層決策</div>
                  <pre style={{ margin: 0, padding: 8, background: 'var(--bg-0)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', fontSize: 10, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{store.ch3_params ? JSON.stringify(store.ch3_params, null, 2) : '— (no params)'}</pre>
                </div>
              </div>
            </details>
          )}
        </aside>
      </div>
    </div>
  );
}

// CodeView + BomView: extracted to views-engineer-code.jsx (INF1 split)
const CodeView = window.CodeView;
const BomView = window.BomView;

Object.assign(window, { ComponentsView });
