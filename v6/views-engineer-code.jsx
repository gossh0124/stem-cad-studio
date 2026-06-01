// views-engineer-code.jsx — CodeView + BomView (extracted from views-engineer.jsx)
// INF1 split: keeps views-engineer.jsx under 500 lines

const _highlight = window._highlight;
const ROLE_COLOR = window.ROLE_COLOR;

// ─── Code View ─────────────────

function CodeView({ _onNavigate, store }) {
  const firmware = store?.firmware || '';
  const files = store?.files || [];
  const jobId = store?.jobId;
  const lang = store?.lang || 'cpp';
  const brain = store?.brain || 'Arduino';
  const [activeFile, setActiveFile] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [copied, setCopied] = React.useState(false);
  const [showGuide, setShowGuide] = React.useState(false);

  React.useEffect(() => { if (files.length && !activeFile) setActiveFile(files[0].name); }, [files.length]);

  const activeContent = React.useMemo(() => {
    if (!files.length) return firmware;
    const file = files.find(x => x.name === activeFile);
    return file?.content || firmware;
  }, [activeFile, firmware, files]);
  const lines = (activeContent || '').split('\n');

  React.useEffect(() => {
    if (!firmware && store?.components?.length && (jobId || store?.isCanned)) {
      setLoading(true);
      const brainC = store.components.find(c => c.role === 'Brain');
      const power = store.components.find(c => c.role === 'Power');
      const outputs = store.components.filter(c => c.role === 'Output').map(c => c.type || c.part);
      const sensors = store.components.filter(c => c.role === 'Sensor').map(c => c.type || c.part);
      const meta = { project_name: store?.project?.name || '', plan: store?.project?.plan || '' };
      API.getFirmware(brainC?.type || brainC?.part || 'Arduino', power?.type || power?.part || 'USB-5V', outputs, sensors, meta)
        .then(data => { PipelineStore.dispatch({ type: 'SET_FIRMWARE', payload: Adapters.toFirmware(data) }); })
        .catch(() => {}).finally(() => setLoading(false));
    }
  }, [!!firmware, jobId]);

  const copyToClipboard = () => {
    if (!activeContent) return;
    navigator.clipboard.writeText(activeContent).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); }).catch(() => {});
  };
  const downloadFile = () => {
    if (!activeContent) return;
    const blob = new Blob([activeContent], { type: 'text/plain' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = activeFile || 'main.ino'; a.click(); URL.revokeObjectURL(a.href);
  };

  const COMPILE_GUIDES = {
    Arduino: { ide: 'Arduino IDE 2.x', steps: ['Board: Arduino Uno', 'Port: COMx / /dev/ttyACMx', 'Upload (Ctrl+U)'] },
    ESP32:   { ide: 'Arduino IDE + ESP32 Board Package', steps: ['Board Manager: esp32 by Espressif', 'Board: ESP32 Dev Module', 'Upload (Ctrl+U)'] },
    RPi:     { ide: 'Thonny / VS Code', steps: ['SSH or direct', 'python3 main.py', 'Ctrl+C to stop'] },
    Microbit:{ ide: 'Mu Editor / MakeCode', steps: ['Connect via USB', 'Flash via Mu Editor', 'Or drag .hex to MICROBIT drive'] },
  };
  const guide = COMPILE_GUIDES[brain] || COMPILE_GUIDES.Arduino;
  const mainFiles = files.filter(f => !f.name.startsWith('test_'));
  const testFiles = files.filter(f => f.name.startsWith('test_'));

  return (
    <div key="code" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '210px 1fr' }}>
        {/* Sidebar */}
        <div style={{ borderRight: '1px solid var(--border-subtle)', background: 'var(--bg-1)', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '14px 16px 8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <Badge color="var(--6e-engineer)" bg="rgba(180,130,255,0.12)">Engineer</Badge>
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{brain}</span>
            </div>
            <SectionLabel style={{ marginBottom: 8 }}>Firmware</SectionLabel>
          </div>
          {mainFiles.map(f => (
            <button key={f.name} onClick={() => setActiveFile(f.name)} style={{ padding: '10px 16px', textAlign: 'left', background: activeFile === f.name ? 'var(--bg-active)' : 'transparent', border: 'none', borderLeft: `2px solid ${activeFile === f.name ? 'var(--accent)' : 'transparent'}`, color: activeFile === f.name ? 'var(--text-primary)' : 'var(--text-secondary)', fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-sans)', display: 'flex', flexDirection: 'column', gap: 2, transition: 'all 0.12s' }}>
              <span style={{ fontWeight: activeFile === f.name ? 600 : 400 }}>{f.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{f.role} · {f.loc} LOC</span>
            </button>
          ))}
          {testFiles.length > 0 && (
            <>
              <SectionLabel style={{ padding: '12px 16px 4px' }}>Test Sketches</SectionLabel>
              {testFiles.map(f => (
                <button key={f.name} onClick={() => setActiveFile(f.name)} style={{ padding: '8px 16px', textAlign: 'left', background: activeFile === f.name ? 'var(--bg-active)' : 'transparent', border: 'none', borderLeft: `2px solid ${activeFile === f.name ? 'var(--6e-engineer)' : 'transparent'}`, color: activeFile === f.name ? 'var(--text-primary)' : 'var(--text-tertiary)', fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)', display: 'flex', flexDirection: 'column', gap: 2, transition: 'all 0.12s' }}>
                  <span style={{ fontWeight: activeFile === f.name ? 600 : 400 }}>{f.name}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{f.role} · {f.loc} LOC</span>
                </button>
              ))}
            </>
          )}
          <div style={{ marginTop: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button onClick={() => setShowGuide(!showGuide)} style={{ width: '100%', padding: '7px 10px', borderRadius: 'var(--r-sm)', background: showGuide ? 'rgba(180,130,255,0.12)' : 'var(--bg-2)', border: `1px solid ${showGuide ? 'var(--6e-engineer)' : 'var(--border-default)'}`, color: 'var(--text-secondary)', fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-sans)', transition: 'all 0.15s' }}>{showGuide ? '▾' : '▸'} Upload Guide</button>
            <button onClick={downloadFile} style={{ width: '100%', padding: '7px 10px', borderRadius: 'var(--r-sm)', background: activeContent ? 'var(--bg-3)' : 'var(--bg-2)', border: '1px solid var(--border-default)', color: activeContent ? 'var(--text-secondary)' : 'var(--text-tertiary)', fontSize: 11, cursor: activeContent ? 'pointer' : 'default', fontFamily: 'var(--font-sans)', opacity: activeContent ? 1 : 0.5, transition: 'all 0.15s' }}>Download {activeFile}</button>
          </div>
        </div>

        {/* Code panel */}
        <div style={{ background: '#0d1117', overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 0, borderBottom: '1px solid rgba(255,255,255,0.06)', position: 'sticky', top: 0, background: '#161b22', zIndex: 2 }}>
            {files.map(f => (
              <button key={f.name} onClick={() => setActiveFile(f.name)} style={{ padding: '8px 14px', fontSize: 12, fontFamily: 'var(--font-mono)', background: activeFile === f.name ? '#0d1117' : 'transparent', borderBottom: activeFile === f.name ? '2px solid var(--accent)' : '2px solid transparent', border: 'none', borderTop: 'none', color: activeFile === f.name ? '#e6edf3' : '#8b949e', cursor: 'pointer', transition: 'all 0.1s', whiteSpace: 'nowrap' }}>{f.name}</button>
            ))}
            <div style={{ flex: 1 }} />
            <button onClick={copyToClipboard} style={{ padding: '6px 12px', marginRight: 8, fontSize: 11, background: copied ? 'rgba(46,160,67,0.2)' : 'rgba(255,255,255,0.06)', border: `1px solid ${copied ? 'rgba(46,160,67,0.4)' : 'rgba(255,255,255,0.1)'}`, borderRadius: 'var(--r-sm)', color: copied ? '#3fb950' : '#8b949e', cursor: 'pointer', fontFamily: 'var(--font-sans)', transition: 'all 0.15s' }}>{copied ? 'Copied!' : 'Copy'}</button>
            <span style={{ fontSize: 11, color: '#484f58', paddingRight: 14 }}>{lines.length} lines</span>
          </div>

          {showGuide && (
            <div style={{ padding: '12px 16px', background: 'rgba(180,130,255,0.06)', borderBottom: '1px solid rgba(180,130,255,0.15)', fontSize: 12, color: '#c9d1d9', lineHeight: 1.6 }}>
              <div style={{ fontWeight: 600, marginBottom: 6, color: 'var(--6e-engineer)' }}>{guide.ide}</div>
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                {guide.steps.map((s, i) => <li key={i} style={{ marginBottom: 2 }}>{s}</li>)}
              </ol>
              <div style={{ marginTop: 6, fontSize: 11, color: '#8b949e' }}>GPIO max: 20mA/pin (A000066)</div>
            </div>
          )}

          {loading ? (
            <div style={{ padding: 20 }}>{[0,1,2,3,4].map(i => <Skeleton key={i} height={18} style={{ marginBottom: 6 }} />)}</div>
          ) : !activeContent ? (
            <div style={{ padding: 40, textAlign: 'center', color: '#484f58', fontSize: 13 }}>No firmware generated yet</div>
          ) : (
            <pre style={{ fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.7, margin: 0, padding: '8px 0', flex: 1 }}>
              {lines.map((l, i) => (
                <div key={i} style={{ display: 'flex', minHeight: 22, paddingRight: 16 }}>
                  <span style={{ width: 48, textAlign: 'right', color: 'rgba(255,255,255,0.15)', userSelect: 'none', fontSize: 12, paddingRight: 16, flexShrink: 0 }}>{i + 1}</span>
                  <span style={{ color: '#8b949e' }} dangerouslySetInnerHTML={{ __html: _highlight(l, lang) || ' ' }} />
                </div>
              ))}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── BOM View ─────────────────
const bomTd = { padding: '10px 14px', fontSize: 13, color: 'var(--text-secondary)', verticalAlign: 'middle' };
const bomTdMono = { ...bomTd, fontFamily: 'var(--font-mono)' };
const bomTh = { padding: '12px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, letterSpacing: '0.5px', color: 'var(--text-tertiary)', borderBottom: '1px solid var(--border-default)', background: 'var(--bg-3)' };

function BomView({ _onNavigate, store }) {
  const bom = store?.bom || [];
  const jobId = store?.jobId;
  const totalCurrent = bom.reduce((s, r) => s + (r.current_ma || 0), 0);
  const totalPrice = bom.reduce((s, r) => s + (r.price || 0) * (r.qty || 1), 0);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => { if (bom.length > 0) setLoading(false); else { const t = setTimeout(() => setLoading(false), 600); return () => clearTimeout(t); } }, [bom.length]);

  return (
    <div key="bom" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
        <div style={{ maxWidth: 920, margin: '0 auto', padding: '28px 32px' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, animation: 'slideUp 0.4s var(--ease-out)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Badge color="var(--6e-enrich)" bg="var(--accent-dim)">Enrich</Badge>
                <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>延伸學習 · 物料清單</span>
              </div>
              <h2 style={{ fontSize: 24, fontWeight: 700 }}>Bill of Materials</h2>
            </div>
            <button style={{ padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--bg-3)', border: '1px solid var(--border-default)', color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)' }} onClick={() => { if (jobId) window.open(API.artifactUrl('csv', jobId)); }}>⬇ CSV</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
            {[{ label: 'Total Parts', value: bom.length }, { label: 'Est. Cost', value: `NT$${totalPrice}`, color: 'var(--accent)' }, { label: 'Active Draw', value: `${totalCurrent.toFixed(0)} mA`, bar: true }].map((s, i) => (
              <Card key={i} style={{ padding: '16px 20px', animation: `slideUp 0.35s var(--ease-out) ${i * 80}ms both` }}>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)', color: s.color || 'var(--text-primary)' }}>{s.value}</div>
                {s.bar && <ProgressBar value={totalCurrent} max={500} style={{ marginTop: 8 }} />}
              </Card>
            ))}
          </div>
          {loading ? (
            <Card style={{ padding: 20 }}>{[0,1,2,3,4].map(i => <Skeleton key={i} height={40} style={{ marginBottom: 8 }} />)}</Card>
          ) : (
            <Card style={{ overflow: 'hidden', animation: 'scaleIn 0.3s var(--ease-out)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead><tr>{['ID','Role','Component','Qty','V','mA','Price','Note'].map(h => <th key={h} style={bomTh}>{h}</th>)}</tr></thead>
                <tbody>
                  {bom.map((r, i) => { const rc = ROLE_COLOR[r.role] || {}; return (
                    <tr key={r.id} style={{ borderBottom: '1px solid var(--border-subtle)', animation: `slideUp 0.25s var(--ease-out) ${i * 40}ms both` }}>
                      <td style={bomTd}><code style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{r.id}</code></td>
                      <td style={bomTd}><Badge color={rc.c} bg={rc.bg}>{r.role}</Badge></td>
                      <td style={{ ...bomTd, fontWeight: 500, color: 'var(--text-primary)' }}>{r.type}</td>
                      <td style={bomTd}>{r.qty}</td>
                      <td style={bomTdMono}>{r.voltage || '—'}</td>
                      <td style={{ ...bomTdMono, color: r.current_ma > 100 ? 'var(--accent)' : 'var(--text-secondary)' }}>{r.current_ma || '—'}</td>
                      <td style={bomTdMono}>NT${r.price}</td>
                      <td style={{ ...bomTd, color: 'var(--text-tertiary)', fontSize: 12 }}>{r.note}</td>
                    </tr>); })}
                  <tr style={{ background: 'var(--bg-3)' }}>
                    <td colSpan="5" style={{ ...bomTd, fontWeight: 600, letterSpacing: '0.5px' }}>TOTAL</td>
                    <td style={{ ...bomTdMono, fontWeight: 700, color: 'var(--accent)' }}>{totalCurrent.toFixed(0)}</td>
                    <td style={{ ...bomTdMono, fontWeight: 700, color: 'var(--accent)' }}>NT${totalPrice}</td>
                    <td style={bomTd}></td>
                  </tr>
                </tbody>
              </table>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { CodeView, BomView });
