// ═══════════════════════════════════════════
// views-engineer-assembly.jsx — Assembly View (V3 SceneGraph renderer only)
// Layout mirrors ComponentsView (2-col grid + corner controls + 260px sidebar).
// Camera driven by use3DInteraction → renderAssemblyV3.applyView(rotY,rotX,zoom).
// ═══════════════════════════════════════════

const use3DInteraction = window.use3DInteraction;
const ViewCube         = window.ViewCube;
const ViewControls     = window.ViewControls;

// ─── shortLabel: same convention as Components view ──────────────────────────
function _shortLabel(type) {
  return (type || '').replace(/-class$/, '').replace(/_/g, ' ').split('-').slice(-2).join('-');
}

const _ROLE_COLOR = {
  Brain:   { c: '#7dd3fc' }, Power:   { c: '#facc15' },
  Control: { c: '#4ade80' }, Sensor:  { c: '#7dd3fc' },
  Output:  { c: '#b482ff' }, Actuator:{ c: '#b482ff' },
};

function AssemblyViewV3Wrapper({ onNavigate, store }) {
  const viewportRef = React.useRef(null);
  const threeRef    = React.useRef(null);
  const v3Ref       = React.useRef(null);

  // Camera state — same hook Components uses.
  const { rotY, rotX, dragging, autoRotate, setAutoRotate, onPointerDown, setView }
    = use3DInteraction(35, 25);   // iso default matches Components convention
  const [zoom, setZoom] = React.useState(1.0);
  const [overlay, setOverlay] = React.useState('clean');
  const [selectedId, setSelectedId] = React.useState(null);
  const [explosion, setExplosion] = React.useState(0);

  const sg = store?.sceneGraphV3;
  const modules  = sg?.modules || [];
  const wires    = sg?.wires || [];
  const holes    = sg?.enclosure?.holes || [];
  const cutouts  = sg?.enclosure?.face_cutouts || [];
  const inner    = sg?.enclosure?.inner || [0, 0, 0];
  const valid    = sg?.validation;

  // (Re)build the V3 scene whenever sceneGraph changes.
  React.useEffect(() => {
    if (!threeRef.current || !sg) return;
    if (v3Ref.current) v3Ref.current.dispose();
    v3Ref.current = window.renderAssemblyV3(threeRef.current, sg);
    return () => { if (v3Ref.current) { v3Ref.current.dispose(); v3Ref.current = null; } };
  }, [sg]);

  // Push camera updates each time interaction state changes.
  React.useEffect(() => {
    if (v3Ref.current?.applyView) v3Ref.current.applyView(rotY, rotX, zoom);
  }, [rotY, rotX, zoom]);

  // Overlay forwarded to controller.
  React.useEffect(() => {
    if (v3Ref.current?.setOverlay) v3Ref.current.setOverlay(overlay);
  }, [overlay]);

  // Explosion forwarded.
  React.useEffect(() => {
    if (v3Ref.current?.setExplosion) v3Ref.current.setExplosion(explosion);
  }, [explosion]);

  // Wheel-to-zoom on viewport.
  React.useEffect(() => {
    const el = viewportRef.current; if (!el) return;
    const h = (e) => { e.preventDefault();
      setZoom(z => Math.max(0.3, Math.min(4.0, z - e.deltaY * 0.002))); };
    el.addEventListener('wheel', h, { passive: false });
    return () => el.removeEventListener('wheel', h);
  }, []);

  // Auto-rotate ticker: spins rotY while autoRotate is on (Components uses the
  // hook's internal tick; we mirror it explicitly to avoid extra coupling).
  React.useEffect(() => {
    if (!autoRotate) return;
    const id = setInterval(() => { setView(((rotY + 0.6) % 360), rotX); }, 33);
    return () => clearInterval(id);
  }, [autoRotate, rotY, rotX, setView]);

  return (
    <div key="assembly" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '1fr 260px' }}>

        {/* ─── LEFT: viewport ─────────────────────────────────────────── */}
        <div ref={viewportRef} onPointerDown={onPointerDown} style={{
          position: 'relative', overflow: 'hidden',
          background: 'radial-gradient(ellipse at 50% 40%, rgba(20,15,40,0.5) 0%, var(--bg-0) 70%)',
          cursor: dragging ? 'grabbing' : 'grab', userSelect: 'none',
        }}>
          <div ref={threeRef} style={{ position: 'absolute', inset: 0 }} />

          {/* empty state */}
          {!sg && (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center', gap: 12, zIndex: 5 }}>
              <div style={{ fontSize: 14, color: 'var(--text-secondary)', fontWeight: 600 }}>Assembly View</div>
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', maxWidth: 320, textAlign: 'center', lineHeight: 1.6 }}>
                {store?.isCanned
                  ? `範本含 ${store?.components?.length || 0} 個元件,Fork 後執行 Phase IV 生成 3D 組裝場景圖。`
                  : '請先執行 Pipeline Phase IV 生成 Assembly SceneGraph(元件佈局+走線+熱力)。'}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button onClick={() => onNavigate('components-3d')} style={{
                  padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--bg-3)',
                  border: '1px solid var(--border-default)', color: 'var(--text-secondary)',
                  fontSize: 12, cursor: 'pointer' }}>← 元件殼</button>
                <button onClick={() => onNavigate('code')} style={{
                  padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--accent)',
                  border: 'none', color: 'var(--text-inverse)', fontSize: 12, fontWeight: 700,
                  cursor: 'pointer' }}>下一頁 · 韌體 →</button>
              </div>
            </div>
          )}

          {sg && <>
            {/* TOP-LEFT: badge + project name */}
            <div style={{ position: 'absolute', top: 12, left: 12, display: 'flex',
              alignItems: 'center', gap: 8, zIndex: 2 }}>
              <Badge color="var(--6e-engineer)" bg="rgba(180,130,255,0.12)">Engineer</Badge>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                Assembly · {store?.project?.name || _shortLabel(store?.templateId) || ''}
              </span>
            </div>

            {/* TOP-LEFT row 2: validation badge */}
            {valid && (
              <div style={{ position: 'absolute', top: 42, left: 12, zIndex: 3 }}>
                {valid.passed
                  ? <Badge color="var(--green)" bg="var(--green-dim)">驗證 ✓ {valid.checks_run}/{valid.checks_run}</Badge>
                  : <Badge color="var(--red)" bg="var(--red-dim)">⚠ {valid.issues?.length || 0} issues</Badge>}
              </div>
            )}

            {/* TOP-RIGHT: ViewControls (auto-rotate + θ display) */}
            <ViewControls rotY={rotY} rotX={rotX} autoRotate={autoRotate}
                          onAutoToggle={() => setAutoRotate(a => !a)} />

            {/* TOP-CENTER: overlay toggles (mirrors Components' layer toggles position) */}
            <div onPointerDown={e => e.stopPropagation()} style={{
              position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)',
              display: 'flex', gap: 4, zIndex: 2 }}>
              {[
                { id: 'thermal', label: '熱力', icon: '🔥' },
                { id: 'wiring',  label: '走線', icon: '⚡' },
                { id: 'clean',   label: '純淨', icon: '🧊' },
              ].map(m => {
                const active = overlay === m.id;
                return (
                  <button key={m.id} onClick={() => setOverlay(m.id)} style={{
                    padding: '5px 12px', borderRadius: 'var(--r-sm)',
                    background: active ? 'var(--accent-dim)' : 'var(--bg-glass)',
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border-subtle)'}`,
                    color: active ? 'var(--accent)' : 'var(--text-tertiary)',
                    fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                    backdropFilter: 'blur(8px)', transition: 'all 0.15s',
                  }}>{m.icon} {m.label}</button>
                );
              })}
            </div>

            {/* BOTTOM-LEFT: info box */}
            <div style={{ position: 'absolute', bottom: 12, left: 12, background: 'var(--bg-glass)',
              border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-md)',
              padding: '10px 14px', backdropFilter: 'blur(8px)', fontSize: 11, zIndex: 2 }}>
              <div style={{ color: 'var(--text-tertiary)', marginBottom: 4 }}>
                {modules.length} mods · {wires.length} wires · zoom {(zoom * 100).toFixed(0)}%
              </div>
              <div style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                inner: {inner[0]}×{inner[1]}×{inner[2]} mm
                {cutouts.length > 0 && <span style={{ color: 'var(--accent)' }}> · {cutouts.length} cutouts</span>}
                {holes.length > 0 && <span style={{ color: '#ffaa44' }}> · {holes.length} holes</span>}
              </div>
            </div>

            {/* BOTTOM-CENTER: explosion slider */}
            <div onPointerDown={e => e.stopPropagation()} style={{
              position: 'absolute', bottom: 56, left: '50%', transform: 'translateX(-50%)',
              display: 'flex', alignItems: 'center', gap: 10,
              background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)', padding: '8px 16px', backdropFilter: 'blur(8px)', zIndex: 2 }}>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Assembled</span>
              <input type="range" min="0" max="100" value={Math.round(explosion * 100)}
                     onChange={e => setExplosion(Number(e.target.value) / 100)}
                     style={{ width: 140, accentColor: 'var(--accent)' }} />
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>Exploded</span>
            </div>

            {/* BOTTOM-RIGHT: ViewCube (six-view) */}
            <ViewCube setView={setView} />
          </>}
        </div>

        {/* ─── RIGHT: sidebar ─────────────────────────────────────────── */}
        <aside style={{ borderLeft: '1px solid var(--border-subtle)', background: 'var(--bg-1)',
          overflow: 'auto', padding: '18px 14px', display: 'flex', flexDirection: 'column', gap: 6,
          animation: 'slideUp 0.4s var(--ease-out) 200ms both' }}>

          <SectionLabel style={{ marginBottom: 4 }}>Modules ({modules.length})</SectionLabel>
          {modules.map(m => {
            const role = m.role || '';
            const rc = _ROLE_COLOR[role] || {};
            const isSel = selectedId === m.id;
            const dims = m.dimensions || [0, 0, 0];
            return (
              <div key={m.id} onClick={() => setSelectedId(isSel ? null : m.id)} style={{
                padding: '10px 12px', borderRadius: 'var(--r-sm)',
                background: isSel ? 'var(--bg-active)' : 'var(--bg-2)',
                border: `1px solid ${isSel ? rc.c || 'var(--accent)' : 'var(--border-subtle)'}`,
                fontSize: 12, cursor: 'pointer', transition: 'all 0.15s',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 2,
                    background: rc.c || 'var(--text-tertiary)', flexShrink: 0 }} />
                  <span style={{ color: 'var(--text-primary)', fontWeight: 600, flex: 1 }}>
                    {_shortLabel(m.comp_type)}
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>{m.enclosure_relation}</span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)',
                  fontFamily: 'var(--font-mono)', marginTop: 2,
                  display: 'flex', justifyContent: 'space-between' }}>
                  <span>{role}</span>
                  <span>{dims[0]}×{dims[1]}×{dims[2]}mm</span>
                </div>
              </div>
            );
          })}
          {modules.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: '12px 0' }}>
              尚無模組(待 Phase IV)
            </div>
          )}

          {/* Holes + Cutouts summary */}
          {(holes.length > 0 || cutouts.length > 0) && <>
            <SectionLabel style={{ marginTop: 10 }}>Enclosure openings</SectionLabel>
            {holes.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '6px 10px',
                background: 'var(--bg-2)', borderRadius: 'var(--r-sm)' }}>
                ⓘ {holes.length} wall hole(s) — external wire pass-through
              </div>
            )}
            {cutouts.length > 0 && (
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '6px 10px',
                background: 'var(--bg-2)', borderRadius: 'var(--r-sm)' }}>
                ⓘ {cutouts.length} face cutout(s) — panel mount openings
              </div>
            )}
          </>}

          {/* Validation panel */}
          <ValidationPanel validation={valid} title="Assembly Validation" />
        </aside>
      </div>
    </div>
  );
}

function AssemblyView({ onNavigate, store }) {
  return <AssemblyViewV3Wrapper onNavigate={onNavigate} store={store} />;
}

Object.assign(window, { AssemblyView });
