// ═══════════════════════════════════════════
// views-explain.jsx — v6: v4 ELK schematic + v5 visual polish
// ═══════════════════════════════════════════

// ─── Plan View ─────────────────

function PlanView({ onNavigate, store }) {
  const bom = store?.bom || [];
  const project = store?.project || {};
  const bullets = store?.planBullets || [];
  const engDec = store?.engineeringDecisions || [];
  const sizing = store?.enclosureSizing || null;
  const decLog = store?.decisionLog || [];
  const totalCurrent = bom.reduce((s, r) => s + (r.current_ma || 0), 0);

  const fixOpts = store?.fixChoiceOptions;
  const showGate = fixOpts && (fixOpts.phase === 2 || fixOpts.phase === 3);
  const supplyMa = fixOpts?.overbudgetDetail?.budget_ma
    || store?.powerBudget?.budget_ma
    || store?.powerBudget?.supply_ma
    || null;
  const overBudget = showGate || (supplyMa && totalCurrent > supplyMa);

  return (
    <div key="plan" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', height: '100%', minHeight: 0 }}>
          {/* Main content */}
          <div style={{ overflow: 'auto', padding: '28px 32px' }}>
            <div style={{ maxWidth: 720 }}>
              <div style={{ marginBottom: 24, animation: 'slideUp 0.4s var(--ease-out)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Badge color="var(--6e-explain)" bg="var(--green-dim)">Explain</Badge>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>原理釐清 · 系統架構</span>
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>{project.name || '專案規劃'}</h2>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{project.prompt || ''}</p>
                {project.plan && (
                  <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, lineHeight: 1.5 }}>
                    AI 規劃：{project.plan}
                  </p>
                )}
              </div>

              {/* 電氣超標 fix_choice 阻塞時，內嵌 swap panel；否則顯示靜態 power summary */}
              {showGate
                ? <PowerGatePanel store={store} />
                : (
                  <Card style={{
                    padding: '12px 16px', marginBottom: 20,
                    border: `1px solid ${overBudget ? 'var(--red)' : 'var(--border-subtle)'}`,
                    background: overBudget ? 'var(--red-dim)' : 'var(--bg-2)',
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 12, fontWeight: 600,
                        color: overBudget ? 'var(--red)' : 'var(--text-secondary)' }}>
                        {overBudget ? '⚠️ 電氣超標' : '⚡ 功率預算'}
                      </span>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)',
                        color: overBudget ? 'var(--red)' : 'var(--text-secondary)' }}>
                        {Math.round(totalCurrent)} / {supplyMa || '—'} mA
                      </span>
                    </div>
                    {overBudget && (
                      <button onClick={() => onNavigate('extract')} style={{
                        marginTop: 8, padding: '6px 12px', borderRadius: 'var(--r-sm)',
                        background: 'var(--red)', border: 'none', color: '#fff',
                        fontSize: 11, fontWeight: 700, cursor: 'pointer',
                      }}>← 回 Extract 替換元件</button>
                    )}
                  </Card>
                )
              }

              <SectionLabel color="var(--6e-explain)" style={{ marginBottom: 12 }}>架構與功率分配</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 28 }}>
                {bullets.map((b, i) => {
                  const rc = ROLE_COLOR[b.tag] || ROLE_COLOR.Housing;
                  // 從 bom 找對應元件 mA（依 type 匹配）
                  const bomRow = bom.find(r => r.type === b.text || (r.type || '').replace(/-class$/, '') === b.text);
                  return <PlanBulletRow key={i} b={b} rc={rc} delay={i * 50}
                    currentMa={bomRow?.current_ma} totalMa={totalCurrent} />;
                })}
              </div>

              {sizing && (
                <div style={{ marginBottom: 28, animation: 'slideUp 0.4s var(--ease-out) 300ms both' }}>
                  <SectionLabel color="var(--accent)" style={{ marginBottom: 12 }}>Enclosure Sizing</SectionLabel>
                  <Card style={{ padding: '18px 22px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
                      <span style={{
                        fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)',
                        color: 'var(--accent)',
                      }}>📐</span>
                      <div>
                        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                          {sizing.target_size === 'compact' ? '迷你' : sizing.target_size === 'medium' ? '一般' : '大型'}
                          <span style={{ fontSize: 12, fontWeight: 400, color: 'var(--text-tertiary)', marginLeft: 8 }}>
                            ≤ {sizing.max_dimension_mm}mm
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                          {sizing.component_count} 個元件 · 估算佈局面積 {sizing.estimated_area_mm2 || '—'} mm²
                        </div>
                      </div>
                    </div>
                    <div style={{
                      padding: '10px 14px', borderRadius: 'var(--r-sm)',
                      background: 'var(--bg-3)', fontSize: 12,
                      color: 'var(--text-secondary)', lineHeight: 1.6,
                    }}>
                      <span style={{ fontWeight: 600, color: 'var(--6e-explain)' }}>原理：</span>
                      {sizing.rationale}
                    </div>
                  </Card>
                </div>
              )}

              <SectionLabel style={{ marginBottom: 12 }}>Engineering Decisions</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 28 }}>
                {engDec.map((d, i) => (
                  <Card key={i} style={{
                    padding: '14px 18px', display: 'flex', gap: 12, alignItems: 'flex-start',
                    animation: `slideUp 0.35s var(--ease-out) ${400 + i * 80}ms both`,
                  }}>
                    <span style={{
                      flexShrink: 0, padding: '2px 8px', borderRadius: 'var(--r-sm)',
                      background: 'var(--bg-4)', fontSize: 10, fontWeight: 700,
                      color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
                    }}>P{d.phase}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>{d.description}</div>
                      <div style={{ fontSize: 11, color: 'var(--accent)', marginTop: 4 }}>STEM: {d.stem_concept}</div>
                    </div>
                  </Card>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => onNavigate('schematic')} style={{
                  padding: '12px 28px', borderRadius: 'var(--r-md)',
                  background: 'var(--accent)', border: 'none',
                  color: 'var(--text-inverse)', fontSize: 14, fontWeight: 700,
                  cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  transition: 'all 0.15s',
                }}>查看原理圖 →</button>
              </div>
            </div>
          </div>

          {/* Right sidebar - Telemetry */}
          <aside style={{
            borderLeft: '1px solid var(--border-subtle)',
            background: 'var(--bg-1)', overflow: 'auto', padding: '24px 18px',
            animation: 'slideUp 0.5s var(--ease-out) 200ms both',
          }}>
            <SectionLabel style={{ marginBottom: 12 }}>Power Budget</SectionLabel>
            <Card style={{ padding: '16px', marginBottom: 20 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
                <span style={{ fontSize: 28, fontWeight: 700, fontFamily: 'var(--font-mono)',
                  color: supplyMa && totalCurrent > supplyMa ? 'var(--red)' : 'var(--text-primary)' }}>
                  {totalCurrent.toFixed(0)}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>mA / {supplyMa || 500} mA</span>
              </div>
              <ProgressBar value={totalCurrent} max={supplyMa || 500} />
              <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
                各元件電流見左側架構列表
              </div>
            </Card>

            <SectionLabel style={{ marginBottom: 12 }}>Sleep / Battery</SectionLabel>
            <Card style={{ padding: '16px', marginBottom: 20 }}>
              {totalCurrent > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>Total active</div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>{totalCurrent} mA</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>Budget</div>
                    <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)', color: totalCurrent <= 500 ? 'var(--green)' : 'var(--red)' }}>
                      {totalCurrent <= 500 ? '✓ OK' : '✕ 超標'}
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>等待電氣數據…</div>
              )}
            </Card>

            <SectionLabel style={{ marginBottom: 12 }}>Decision Log</SectionLabel>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {decLog.map((d, i) => (
                <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, lineHeight: 1.5 }}>
                  <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontWeight: 600, flexShrink: 0 }}>{d.phase}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>{d.text}</span>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

function PlanBulletRow({ b, rc, delay, currentMa, totalMa }) {
  const [hovered, setHovered] = React.useState(false);
  const pct = (currentMa != null && totalMa) ? Math.round((currentMa / totalMa) * 100) : null;
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 14,
        padding: '12px 16px', borderRadius: 'var(--r-md)',
        background: hovered ? 'var(--bg-3)' : 'var(--bg-2)',
        border: `1px solid ${hovered ? 'var(--border-default)' : 'var(--border-subtle)'}`,
        transition: 'all 0.2s var(--ease-out)',
        animation: `slideUp 0.35s var(--ease-out) ${150 + delay}ms both`,
      }}
    >
      <Badge color={rc.c} bg={rc.bg} style={{ minWidth: 64, justifyContent: 'center' }}>{b.tag}</Badge>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>{b.text}</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{b.detail}</div>
        {b.edu && (
          <div style={{
            fontSize: 11, color: 'var(--6e-explain)', marginTop: 4,
            lineHeight: 1.5, display: 'flex', alignItems: 'flex-start', gap: 4,
          }}>
            <span style={{ flexShrink: 0 }}>💡</span>
            <span>{b.edu}</span>
          </div>
        )}
      </div>
      {currentMa != null && currentMa > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2, minWidth: 70 }}>
          <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: rc.c }}>
            {currentMa} mA
          </span>
          {pct != null && (
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              {pct}% of total
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Schematic View (ELK-powered from v4 + v5 sidebar enhancements) ─────────────────

function SchematicView({ onNavigate, store }) {
  const bom = store?.bom || [];
  const wiring = store?.wiring || [];
  // testCode auto-select：testCodes 載入後若尚未選元件，預設展示第一個
  const _selRef = React.useRef(null);
  const project = store?.project || {};

  const elk = ElkSchematic({ store });

  const RAIL_COLORS = { Brain: '#ef8354', Power: '#e8c547', Sensor: '#5ba4cf', Output: '#7cc47c', Comm: '#b392f0', Actuator: '#7cc47c' };

  const rails = React.useMemo(() => {
    if (!bom.length) return [];
    const groups = {};
    for (const b of bom) {
      const role = b.role || 'Other';
      if (role === 'Housing') continue;
      if (!groups[role]) groups[role] = { ma: 0, parts: [] };
      groups[role].ma += (b.current_ma || 0);
      if (!groups[role].parts.includes(b.type)) groups[role].parts.push(b.type);
    }
    return Object.entries(groups).map(([role, d]) => ({
      net: `${role} · ${d.parts.join(' + ')}`,
      ma: `${d.ma < 1 && d.ma > 0 ? d.ma.toFixed(1) : d.ma.toFixed(0)} mA`,
      color: RAIL_COLORS[role] || '#999',
    }));
  }, [bom]);

  const pinRows = React.useMemo(() => {
    return wiring.map(w => [w.from || '—', w.net || '—', w.to || '—']);
  }, [wiring]);

  // Bus Summary calculation (pre-JSX)
  const busSummary = React.useMemo(() => {
    const buses = {};
    for (const w of wiring) {
      const net = w.net || '';
      let bus = 'Other';
      if (/i2c|sda|scl/i.test(net)) bus = 'I²C';
      else if (/spi|mosi|miso|sck|cs/i.test(net)) bus = 'SPI';
      else if (/uart|tx|rx/i.test(net)) bus = 'UART';
      else if (/wifi|mqtt/i.test(net)) bus = 'WiFi';
      if (!buses[bus]) buses[bus] = { count: 0, color: bus === 'I²C' ? '#5ba4cf' : bus === 'SPI' ? '#7cc47c' : bus === 'WiFi' ? 'var(--accent-2)' : 'var(--text-tertiary)' };
      buses[bus].count++;
    }
    return Object.entries(buses);
  }, [wiring]);

  // testCode auto-select：testCodes 載入後若尚未選元件，預設展示第一個
  React.useEffect(() => {
    if (_selRef.current || elk.selectedComp) return;
    if (!elk.testCodes || Object.keys(elk.testCodes).length === 0) return;
    _selRef.current = true;
    elk.setSelectedComp(Object.keys(elk.testCodes)[0]);
  }, [elk.testCodes, elk.selectedComp]);

  const renderSchematic = () => {
    if (elk.error) {
      const isCanned = !!store?.isCanned;
      return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-tertiary)', fontSize: 13 }}>
          <div style={{ textAlign: 'center', maxWidth: 380, padding: 24 }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>{isCanned ? '🎯' : '⚠'}</div>
            <div style={{ fontSize: 14, color: isCanned ? 'var(--accent)' : 'var(--text-secondary)', marginBottom: 6 }}>
              {isCanned ? 'Demo 預覽：原理圖請 Fork 後實跑生成' : 'Schematic 載入失敗'}
            </div>
            {isCanned ? (
              <div style={{ fontSize: 11, opacity: 0.7, lineHeight: 1.6, marginBottom: 16 }}>
                範本未包含完整 wiring 資料；點右上「Fork 為新專案」後重跑 Phase III 即可生成可視化原理圖。
              </div>
            ) : (
              <div style={{ fontSize: 11, marginTop: 4, opacity: 0.6, marginBottom: 16 }}>{elk.error}</div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
              <button onClick={() => onNavigate('plan')} style={{
                padding: '8px 16px', borderRadius: 'var(--r-sm)',
                background: 'var(--bg-3)', border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer',
              }}>← Plan</button>
              <button onClick={() => onNavigate('components-3d')} style={{
                padding: '8px 16px', borderRadius: 'var(--r-sm)',
                background: 'var(--accent)', border: 'none',
                color: 'var(--text-inverse)', fontSize: 12, fontWeight: 700, cursor: 'pointer',
              }}>下一頁 · 元件殼 →</button>
            </div>
          </div>
        </div>
      );
    }
    if (elk.loading || !elk.layout) {
      return (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-tertiary)', fontSize: 13 }}>
          <div style={{ textAlign: 'center' }}>
            <Spinner size={28} />
            <div style={{ marginTop: 12 }}>ELK 佈局計算中⋯</div>
          </div>
        </div>
      );
    }
    return (
      <ElkSchematicSVG
        layout={elk.layout}
        testCodes={elk.testCodes}
        onSelectComp={elk.setSelectedComp}
        selectedComp={elk.selectedComp}
      />
    );
  };

  return (
    <div key="schematic" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: '1fr 280px' }}>
        {/* Main SVG area */}
        <div style={{ position: 'relative', overflow: 'hidden', background: 'var(--bg-0)' }}>
          {renderSchematic()}
          <div style={{
            position: 'absolute', top: 12, left: 12, right: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            pointerEvents: 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, pointerEvents: 'auto' }}>
              <Badge color="var(--6e-explain)" bg="var(--green-dim)">Explain</Badge>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>原理圖 · Schematic</span>
              <Badge>{wiring.length || '?'} nets</Badge>
              {/* VS-FE: 接線保真 verdict — 角位未接線從靜默變紅色可讀信號 */}
              {elk.layout && elk.fidelity && !elk.error && (
                elk.fidelity.verdict === 'PASS' ? (
                  <Badge color="var(--green)" bg="var(--green-dim)">接線 ✓ {elk.fidelity.n_routed}</Badge>
                ) : (
                  <span title={`角位未接線（pin 不在 MCU 白名單而被棄繪）：\n${(elk.fidelity.dropped || []).map(d => `${d.comp}.${d.pin} → ${d.mcu}`).join('\n')}`}>
                    <Badge color="var(--red)" bg="var(--red-dim)">⚠ {elk.fidelity.n_dropped} 未接線</Badge>
                  </span>
                )
              )}
            </div>
            <div style={{ display: 'flex', gap: 6, pointerEvents: 'auto' }}>
              <button onClick={() => onNavigate('plan')} style={{
                padding: '6px 12px', borderRadius: 'var(--r-sm)',
                background: 'var(--bg-glass)', border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)', fontSize: 11, cursor: 'pointer',
                fontFamily: 'var(--font-sans)', backdropFilter: 'blur(8px)',
                transition: 'all 0.15s',
              }}>← Plan</button>
              <button onClick={() => onNavigate('components-3d')} style={{
                padding: '6px 12px', borderRadius: 'var(--r-sm)',
                background: 'var(--bg-glass)', border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)', fontSize: 11, cursor: 'pointer',
                fontFamily: 'var(--font-sans)', backdropFilter: 'blur(8px)',
                transition: 'all 0.15s',
              }}>3D →</button>
            </div>
          </div>
          <div style={{
            position: 'absolute', bottom: 12, left: 12,
            background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-md)', padding: '10px 14px',
            backdropFilter: 'blur(8px)', fontSize: 11, pointerEvents: 'none',
          }}>
            <div style={{ display: 'flex', gap: 16, color: 'var(--text-secondary)' }}>
              <span><span style={{ color: 'var(--text-tertiary)' }}>PROJECT</span> {project.id || '—'}</span>
              <span><span style={{ color: 'var(--text-tertiary)' }}>ITER</span> {project.iteration || 'v1.0'}</span>
              <span><span style={{ color: 'var(--text-tertiary)' }}>PHASE</span> {store?.currentPhase || '?'}/7</span>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <aside style={{
          borderLeft: '1px solid var(--border-subtle)',
          background: 'var(--bg-1)', overflow: 'auto', padding: '18px 14px',
          display: 'flex', flexDirection: 'column', gap: 0,
          animation: 'slideUp 0.4s var(--ease-out) 200ms both',
        }}>
          {elk.selectedComp && (
            <div style={{ marginBottom: 16 }}>
              <TestCodePanel compKey={elk.selectedComp} testCodes={elk.testCodes} />
            </div>
          )}

          <SectionLabel style={{ marginBottom: 12 }}>Rails</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 20 }}>
            {(rails.length > 0 ? rails : [{ net: '等待電氣數據⋯', ma: '—', color: 'var(--text-tertiary)' }]).map((r, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 10px', borderRadius: 'var(--r-sm)',
                background: 'var(--bg-2)', fontSize: 11,
                transition: 'all 0.15s',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 3, background: r.color, borderRadius: 1 }} />
                  <span style={{ color: 'var(--text-secondary)' }}>{r.net}</span>
                </div>
                <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{r.ma}</span>
              </div>
            ))}
          </div>

          <SectionLabel style={{ marginBottom: 12 }}>Pin Allocation</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1, fontSize: 11, marginBottom: 20 }}>
            {(pinRows.length > 0 ? pinRows : [['—', '—', '等待接線分析']]).map(([pin, sig, target], i) => (
              <div key={i} style={{
                display: 'grid', gridTemplateColumns: '54px 64px 1fr', gap: 4,
                padding: '5px 8px', borderRadius: 3,
                background: i % 2 === 0 ? 'var(--bg-2)' : 'transparent',
              }}>
                <span style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{pin}</span>
                <span style={{ color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{sig}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{target}</span>
              </div>
            ))}
          </div>

          {/* Bus Summary (from v5) */}
          {wiring.length > 0 && busSummary.length > 0 && (
            <div>
              <SectionLabel style={{ marginBottom: 10 }}>Bus Summary</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {busSummary.map(([bus, d], i) => (
                  <div key={i} style={{
                    padding: '8px 10px', borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-2)', fontSize: 11,
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ width: 3, height: 12, borderRadius: 1, background: d.color }} />
                      <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{bus}</span>
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>×{d.count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

Object.assign(window, { PlanView, SchematicView });
