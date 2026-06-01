// ═══════════════════════════════════════════
// explore/explore-panels.jsx — Sub-components: resolve, spec warnings, power gate, extract slot
// Depends on: explore-data.js (window._panelRowStyle, _panelBtnBase, _panelBtnStyle)
// ═══════════════════════════════════════════

function ResolveConfirmPanel({ resolve, compConfirms, setCompConfirms }) {
  const confirm = (key, payload) => () => setCompConfirms(p => ({ ...p, [key]: payload }));
  return (
    <Card style={{ marginTop: 20, padding: '20px 24px', animation: 'slideUp 0.5s var(--ease-out) 380ms both' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 16 }}>📋</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>元件確認</span>
        {resolve.n_resolved > 0 && (
          <span style={{ fontSize: 11, color: 'var(--green)', fontWeight: 600 }}>
            {resolve.n_resolved} 個已自動識別
          </span>
        )}
      </div>
      {(resolve.fuzzy_candidates || []).map((fc, i) => {
        const key = fc.original;
        const chosen = compConfirms[key]?.action;
        return (
          <div key={`fz-${i}`} style={_panelRowStyle}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              <span style={{ color: 'var(--accent)', fontWeight: 600 }}>⚠️ "{fc.original}"</span>
              <span style={{ color: 'var(--text-secondary)' }}> → 你是指 </span>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{fc.candidate?.replace(/-class$/, '')}</span>
              <span style={{ color: 'var(--text-tertiary)', fontSize: 11 }}> 嗎？</span>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={confirm(key, { action: 'accept_fuzzy', canonical: fc.candidate })}
                style={_panelBtnStyle(chosen === 'accept_fuzzy', 'accent-2')}>✓ 是</button>
              <button onClick={confirm(key, { action: 'skip' })}
                style={_panelBtnStyle(chosen === 'skip', 'red')}>✗ 不是，跳過</button>
            </div>
          </div>
        );
      })}
      {(resolve.unknowns || []).map((unk, i) => {
        const key = unk.original;
        const chosen = compConfirms[key]?.action;
        const eqList = unk.equivalent_candidates || [];
        return (
          <div key={`unk-${i}`} style={_panelRowStyle}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              <span style={{ color: 'var(--red)', fontWeight: 600 }}>❓ "{unk.original}"</span>
              <span style={{ color: 'var(--text-secondary)' }}> — 系統不認識此元件</span>
            </div>
            {eqList.length > 0 && (
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 8 }}>
                建議等效件：{eqList.map(e => e.replace(/-class$/, '')).join('、')}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {eqList.length > 0 && (
                <button onClick={confirm(key, { action: 'use_equivalent', canonical: eqList[0] })}
                  style={_panelBtnStyle(chosen === 'use_equivalent', '6e-explore')}>用等效件</button>
              )}
              <button onClick={confirm(key, { action: 'skip' })}
                style={_panelBtnStyle(chosen === 'skip', 'red')}>跳過</button>
            </div>
          </div>
        );
      })}
      {(resolve.missing_mentions || []).map((mm, i) => {
        const key = mm.mention;
        const chosen = compConfirms[key]?.action;
        const canonical = mm.resolve?.canonical;
        return (
          <div key={`mm-${i}`} style={_panelRowStyle}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>
              <span style={{ color: 'var(--6e-explore)', fontWeight: 600 }}>🔍 "{mm.mention}"</span>
              <span style={{ color: 'var(--text-secondary)' }}> — 你提到了此元件，但規劃中未包含</span>
            </div>
            {canonical && (
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 8 }}>
                可能是：{canonical.replace(/-class$/, '')}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              {canonical && (
                <button onClick={confirm(key, { action: 'add_missing', canonical, role: 'Sensor' })}
                  style={_panelBtnStyle(chosen === 'add_missing', '6e-explore')}>加入專案</button>
              )}
              <button onClick={confirm(key, { action: 'skip' })}
                style={_panelBtnStyle(chosen === 'skip', 'accent-2')}>不需要</button>
            </div>
          </div>
        );
      })}
    </Card>
  );
}

function SpecWarningsPanel({ resolve, specConfirms, setSpecConfirms }) {
  const swBtnStyle = (active, color) => ({
    ..._panelBtnBase,
    background: active ? `var(--${color}-dim)` : 'var(--bg-3)',
    border: `1px solid ${active ? `var(--${color})` : 'var(--border-subtle)'}`,
    color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
    fontWeight: active ? 600 : 400,
  });
  const specConfirm = (compType, fieldName, action) => () =>
    setSpecConfirms(p => ({ ...p, [`${compType}::${fieldName}`]: action }));
  return (
    <Card style={{ marginTop: 20, padding: '20px 24px', animation: 'slideUp 0.5s var(--ease-out) 420ms both' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <span style={{ fontSize: 16 }}>📊</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>近似值互證</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          用戶元件數值 vs 同類元件統計
        </span>
      </div>
      {resolve.spec_warnings.map((sw, si) => (
        <div key={`sw-${si}`} style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>
            {sw.type.replace(/-class$/, '')}
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--text-tertiary)', marginLeft: 8 }}>
              ({sw.role})
            </span>
          </div>
          {sw.warnings.map((w, wi) => {
            const wKey = `${sw.type}::${w.field}`;
            const chosen = specConfirms[wKey];
            const isWarn = w.severity === 'warning';
            return (
              <div key={`sw-${si}-${wi}`} style={_panelRowStyle}>
                <div style={{ fontSize: 13, marginBottom: 8 }}>
                  <span style={{ color: isWarn ? 'var(--red)' : 'var(--accent)', fontWeight: 600 }}>
                    {isWarn ? '⚠️' : 'ℹ️'} {w.label}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {' '}你填 <strong>{w.user_value} {w.unit}</strong>，同類 {w.n_peers} 個元件中位數{' '}
                    <strong>{w.median} {w.unit}</strong>（σ={w.sigma}，範圍 {w.range_min}–{w.range_max}）
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={specConfirm(sw.type, w.field, 'accept')}
                    style={swBtnStyle(chosen === 'accept', 'accent-2')}>✓ 我確定這個值</button>
                  <button onClick={specConfirm(sw.type, w.field, 'use_median')}
                    style={swBtnStyle(chosen === 'use_median', '6e-explore')}>用中位數 {w.median}</button>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </Card>
  );
}

// ─── Power Gate Panel (inline swap selector for Phase II/III fix_choice) ─────────────────

function PowerGatePanel({ store }) {
  const fixOpts = store?.fixChoiceOptions;
  const jobId = store?.jobId;
  const [selected, setSelected] = React.useState({});
  const [submitting, setSubmitting] = React.useState(false);

  if (!fixOpts || (fixOpts.phase !== 2 && fixOpts.phase !== 3)) return null;
  const suggestions = fixOpts.swapSuggestions || [];
  const detail = fixOpts.overbudgetDetail || {};
  const powerFailed = detail.power_failed !== false;
  const total = detail.total_ma ?? 0;
  const budget = detail.budget_ma ?? 0;
  const failedCats = detail.failed_categories || [];

  const selectedIds = Object.keys(selected).filter(k => selected[k]);
  const projected = total - suggestions
    .filter(s => selected[s.id])
    .reduce((sum, s) => sum + (s.saving_ma || 0), 0);

  const submit = async () => {
    if (!jobId || !selectedIds.length) return;
    setSubmitting(true);
    try {
      await API.respondFixChoice(jobId, 'confirm_swaps', selectedIds);
      PipelineStore.dispatch({ type: 'HITL_SUBMIT' });
      setSelected({});
    } catch (err) { console.error('power-gate submit failed:', err); }
    setSubmitting(false);
  };

  const phaseLabel = fixOpts.phase === 2 ? 'Phase II 早期警示' : 'Phase III 約束檢查';
  return (
    <Card style={{
      overflow: 'hidden', marginBottom: 20,
      border: '1.5px solid var(--accent)', animation: 'slideUp 0.3s var(--ease-out)',
    }}>
      <div style={{
        padding: '12px 18px', background: 'var(--accent-dim)',
        borderBottom: '1px solid var(--accent)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>
            ⚡ {powerFailed ? '電氣超標' : '違反電氣約束'} — 需替換元件
          </span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 8 }}>
            {phaseLabel}
            {!powerFailed && failedCats.length > 0 && ` · ${failedCats.join('、')}`}
          </span>
        </div>
        {powerFailed && (
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>
            {total} / {budget} mA
          </span>
        )}
      </div>

      {fixOpts.issues?.length > 0 && (
        <div style={{ padding: '8px 18px', borderBottom: '1px solid var(--border-subtle)',
          fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {fixOpts.issues.map((iss, i) => <div key={i}>· {iss}</div>)}
        </div>
      )}

      {suggestions.length === 0 ? (
        <div style={{ padding: '16px 18px', fontSize: 12, color: 'var(--text-secondary)' }}>
          無自動替換方案。請手動調整元件清單或重新進入 clarify 修改場景。
        </div>
      ) : (
        <>
          <div style={{ padding: '10px 18px 4px', fontSize: 11, fontWeight: 600,
            color: 'var(--text-tertiary)', letterSpacing: '0.5px' }}>
            勾選要替換的元件以降低功耗：
          </div>
          <div style={{ padding: '0 14px 8px' }}>
            {suggestions.map(swap => {
              const checked = !!selected[swap.id];
              return (
                <div key={swap.id}
                  onClick={() => setSelected(s => ({ ...s, [swap.id]: !s[swap.id] }))}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10,
                    padding: '10px 12px', marginBottom: 6,
                    borderRadius: 'var(--r-sm)', cursor: 'pointer',
                    background: checked ? 'rgba(114,196,207,0.08)' : 'var(--bg-3)',
                    border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--border-subtle)'}`,
                  }}>
                  <div style={{
                    width: 18, height: 18, borderRadius: 4, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: checked ? 'var(--accent)' : 'var(--bg-2)',
                    border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--border-default)'}`,
                    color: '#fff', fontSize: 11, fontWeight: 700,
                  }}>{checked ? '✓' : ''}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 2 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                        {swap.current.type.replace('-class', '')}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>→</span>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                        {swap.alternative.label}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, marginBottom: 2 }}>
                      <span style={{ color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>{swap.current.ma} mA</span>
                      <span style={{ color: 'var(--text-tertiary)' }}>→</span>
                      <span style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>{swap.alternative.ma} mA</span>
                      <Badge color="var(--green)" bg="var(--green-dim)" style={{ fontSize: 9 }}>
                        省 {swap.saving_ma} mA
                      </Badge>
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{swap.trade_off}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ padding: '10px 18px 14px', borderTop: '1px solid var(--border-subtle)',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ fontSize: 12 }}>
              {selectedIds.length > 0 ? (
                <>
                  替換後預估：
                  <span style={{ fontWeight: 700, fontFamily: 'var(--font-mono)',
                    color: projected <= budget ? 'var(--green)' : 'var(--red)', marginLeft: 4 }}>
                    {Math.round(projected * 10) / 10} mA
                  </span>
                  {projected <= budget
                    ? <span style={{ color: 'var(--green)', marginLeft: 6 }}>✓ 合格</span>
                    : <span style={{ color: 'var(--red)', marginLeft: 6 }}>仍超標</span>}
                </>
              ) : (
                <span style={{ color: 'var(--text-tertiary)' }}>請勾選至少一項替換</span>
              )}
            </div>
            <button onClick={submit} disabled={submitting || !selectedIds.length} style={{
              padding: '8px 18px', borderRadius: 'var(--r-md)',
              background: selectedIds.length ? 'var(--accent)' : 'var(--bg-4)',
              border: 'none', color: 'var(--text-inverse)', fontSize: 12, fontWeight: 700,
              cursor: selectedIds.length ? 'pointer' : 'not-allowed',
              opacity: submitting ? 0.6 : 1,
            }}>確認替換 · 重跑驗證 →</button>
          </div>
        </>
      )}
    </Card>
  );
}

// ─── Extract Slot + ScoreRing ─────────────────

function ExtractSlot({ slot, readOnly, onSwap }) {
  const [showAll, setShowAll] = React.useState(false);
  const [expandedIdx, setExpandedIdx] = React.useState(null);
  const pickId = slot.pick.id;
  const hasOthers = slot.candidates.length > 1;

  const handleSelect = (candidateId) => {
    if (readOnly) return;
    if (candidateId === pickId) return;
    if (onSwap) onSwap(slot.label, candidateId);
  };

  return (
    <Card style={{ overflow: 'hidden' }}>
      <div
        onClick={() => hasOthers && setShowAll(s => !s)}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 20px',
          background: 'var(--bg-3)', borderBottom: '1px solid var(--border-subtle)',
          cursor: hasOthers ? 'pointer' : 'default',
        }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{slot.label}</span>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{slot.constraint}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {hasOthers && (
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              {showAll ? '▲ 收起' : '▼ 展開比較'}
            </span>
          )}
          <Badge color="var(--green)" bg="var(--green-dim)" style={{ fontSize: 10 }}>
            {slot.candidates.length} candidates
          </Badge>
        </div>
      </div>
      <div>
        {slot.candidates.map((c, ci) => {
          const isPick = c.id === pickId;
          if (!showAll && !isPick) return null;
          const isOpen = expandedIdx === ci;
          return (
            <React.Fragment key={ci}>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '44px 1fr 1.4fr auto auto',
                alignItems: 'center', gap: 12,
                padding: '12px 20px',
                borderBottom: isOpen ? 'none' : '1px solid var(--border-subtle)',
                background: isPick ? 'rgba(114,196,207,0.04)' : 'transparent',
                transition: 'background 0.15s',
              }}>
                <div style={{ textAlign: 'center' }}>
                  {isPick ? (
                    <span style={{
                      display: 'inline-block', padding: '2px 8px',
                      background: 'var(--green-dim)', color: 'var(--green)',
                      fontSize: 10, fontWeight: 700, borderRadius: 'var(--r-full)', letterSpacing: '0.5px',
                    }}>PICK</span>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>#{ci + 1}</span>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: isPick ? 'var(--text-primary)' : 'var(--text-secondary)' }}>{c.id.replace(/-class$/, '')}</div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {c.specs.map((s, si) => (
                    <span key={si} style={{
                      padding: '3px 8px', borderRadius: 'var(--r-sm)',
                      background: 'var(--bg-3)', fontSize: 11,
                      color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
                    }}>{typeof s === 'string' ? s.replace(/-class$/, '') : s}</span>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 4 }}>
                  {c.reason && (
                    <button
                      onClick={() => setExpandedIdx(isOpen ? null : ci)}
                      style={{
                        padding: '3px 8px', borderRadius: 'var(--r-sm)',
                        background: isOpen ? 'var(--accent-dim)' : 'var(--bg-3)',
                        border: `1px solid ${isOpen ? 'var(--accent)' : 'var(--border-subtle)'}`,
                        color: isOpen ? 'var(--accent)' : 'var(--text-tertiary)',
                        fontSize: 10, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                        transition: 'all 0.15s',
                      }}
                    >{isOpen ? '▾ 原理' : '▸ 原理'}</button>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 120, justifyContent: 'flex-end' }}>
                  <ScoreRing score={c.score} />
                  <button
                    onClick={() => handleSelect(c.id)}
                    disabled={readOnly && !isPick}
                    style={{
                      padding: '5px 12px', borderRadius: 'var(--r-sm)',
                      background: isPick ? 'var(--green-dim)' : 'var(--bg-3)',
                      border: `1px solid ${isPick ? 'var(--green)' : 'var(--border-subtle)'}`,
                      color: isPick ? 'var(--green)' : 'var(--text-tertiary)',
                      fontSize: 11, fontWeight: 600,
                      cursor: (isPick || readOnly) ? 'default' : 'pointer',
                      fontFamily: 'var(--font-sans)', letterSpacing: '0.5px',
                      transition: 'all 0.15s',
                      opacity: readOnly && !isPick ? 0.4 : 1,
                    }}>{isPick ? 'LOCK ✓' : '選擇'}</button>
                </div>
              </div>
              {isOpen && c.reason && (
                <div style={{
                  padding: '8px 20px 12px 76px',
                  borderBottom: '1px solid var(--border-subtle)',
                  background: 'var(--bg-2)',
                }}>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                    📖 {c.reason}
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
        {!showAll && hasOthers && (
          <div
            onClick={() => setShowAll(true)}
            style={{
              padding: '8px 20px', fontSize: 11, color: 'var(--accent)',
              textAlign: 'center', cursor: 'pointer',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-3)'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            + {slot.candidates.length - 1} 其他候選 · 點擊展開比較 ▼
          </div>
        )}
      </div>
    </Card>
  );
}

function ScoreRing({ score, size = 36 }) {
  const c = score > 80 ? 'var(--green)' : score > 60 ? 'var(--accent)' : 'var(--text-tertiary)';
  const r = (size - 4) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - score / 100);
  const tip = score > 80 ? '強推薦：最符合此專案需求'
            : score > 60 ? '可用：功能相容，但非最佳選擇'
            : '參考：功耗或功能與需求差距較大';
  return (
    <div style={{ position: 'relative', width: size, height: size, cursor: 'help' }}
         title={`適配度 ${score}/100 — ${tip}`}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bg-4)" strokeWidth="2.5" />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={c} strokeWidth="2.5"
          strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 0.6s var(--ease-out)' }} />
      </svg>
      <span style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 700, color: c,
      }}>{score}</span>
    </div>
  );
}

Object.assign(window, {
  ResolveConfirmPanel, SpecWarningsPanel, PowerGatePanel,
  ExtractSlot, ScoreRing,
});
