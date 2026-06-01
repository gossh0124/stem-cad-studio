// ═══════════════════════════════════════════
// shell.jsx — v6: navigation shell + composer
// UI primitives (Badge/Card/etc.) in ui-primitives.jsx
// ═══════════════════════════════════════════

// ─── 6E Stage Definitions — defined in config/stages-6e.js ───

const STAGES_6E = window.STAGES_6E;

const VIEW_META = {
  idle:      { label: 'Workbench', stage: 'engage' },
  clarify:   { label: 'Clarify',   stage: 'explore' },
  extract:   { label: 'Extract',   stage: 'explore' },
  plan:      { label: 'Plan',      stage: 'explain' },
  schematic: { label: 'Schematic', stage: 'explain' },
  'components-3d': { label: 'Components', stage: 'engineer' },
  assembly:        { label: 'Assembly',   stage: 'engineer' },
  code:            { label: 'Code',       stage: 'enrich' },
  bom:       { label: 'BOM',       stage: 'enrich' },
  'user-components': { label: 'My Parts', stage: 'enrich' },
  evaluate:  { label: 'Evaluate',  stage: 'evaluate' },
};

// ─── Top Navigation Bar (v4 props + v5 visuals) ─────────────────

const STAGE_UNLOCK_PHASE = { engage: 0, explore: 1, explain: 3, engineer: 4, enrich: 5, evaluate: 6 };
const PHASE_LABELS = { 1: 'P1 Intent', 2: 'P2 Spec', 3: 'P3 EE', 4: 'P4 Mech', 5: 'P5 Render', 6: 'P6 Verify', 7: 'P7 HITL' };

function TopNav({ currentView, onNavigate, pipelinePhase, pipelineStatus, navStyle, sseStatus, isCanned, templateId, onFork }) {
  const currentStage = VIEW_META[currentView]?.stage || 'engage';
  const currentStageIdx = STAGES_6E.findIndex(s => s.id === currentStage);
  const isCompact = navStyle === 'compact';
  const pipelineActive = pipelineStatus === 'running';

  return (
    <header style={{
      height: 54, flexShrink: 0,
      display: 'flex', alignItems: 'center', gap: 0,
      background: 'var(--bg-1)',
      borderBottom: '1px solid var(--border-subtle)',
      padding: '0 16px',
      zIndex: 100,
    }}>
      {/* Logo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginRight: 24, flexShrink: 0 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 'var(--r-sm)',
          background: 'linear-gradient(135deg, var(--accent) 0%, oklch(0.60 0.14 55) 100%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, color: 'var(--text-inverse)',
        }}>C</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.5px', lineHeight: 1.2 }}>CADHLLM</div>
          <div style={{ fontSize: 9, color: 'var(--text-tertiary)', letterSpacing: '1px', lineHeight: 1 }}>STEM 6E AI</div>
        </div>
      </div>

      <div style={{ width: 1, height: 28, background: 'var(--border-default)', marginRight: 16, flexShrink: 0 }} />

      {/* 6E Pipeline Nav with progress connectors */}
      <nav style={{ display: 'flex', alignItems: 'center', height: '100%', flex: 1, minWidth: 0 }}>
        {STAGES_6E.map((stage, idx) => {
          const isActive = stage.id === currentStage;
          const isReached = idx <= currentStageIdx || pipelinePhase >= (STAGE_UNLOCK_PHASE[stage.id] || 0);
          const isPast = idx < currentStageIdx;
          return (
            <React.Fragment key={stage.id}>
              {idx > 0 && (
                <div style={{
                  width: 24, height: 2, flexShrink: 0,
                  background: isPast ? stage.color : 'var(--bg-4)',
                  borderRadius: 1,
                  transition: 'background 0.4s var(--ease-out)',
                  position: 'relative',
                  overflow: 'hidden',
                }}>
                  {isPast && (
                    <div style={{
                      position: 'absolute', inset: 0,
                      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent)',
                      animation: 'progressSweep 2s ease infinite',
                    }} />
                  )}
                </div>
              )}
              <StageTab
                stage={stage}
                index={idx}
                isActive={isActive}
                isReached={isReached}
                isPast={isPast}
                isLocked={!isCanned && pipelinePhase > 0 && pipelinePhase < (STAGE_UNLOCK_PHASE[stage.id] || 0)}
                currentView={currentView}
                onNavigate={onNavigate}
                isCompact={isCompact}
                pipelineActive={pipelineActive && isActive}
                pipelinePhase={pipelinePhase}
                isCanned={isCanned}
              />
            </React.Fragment>
          );
        })}
      </nav>

      {/* Right actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 16, flexShrink: 0 }}>
        {isCanned && (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '4px 10px', borderRadius: 'var(--r-full)',
              background: 'var(--accent-dim)', color: 'var(--accent)',
              fontSize: 10, fontWeight: 700, letterSpacing: '0.5px',
            }}>
              <span style={{ fontSize: 10 }}>🎯</span>DEMO {templateId ? `· ${templateId}` : ''}
            </div>
            {onFork && (
              <button onClick={onFork} style={{
                padding: '6px 14px', borderRadius: 'var(--r-sm)',
                background: 'var(--green-dim)', border: '1px solid var(--green)',
                color: 'var(--green)', fontSize: 12, fontWeight: 700,
                cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}>Fork 為新專案 →</button>
            )}
          </>
        )}
        {sseStatus && sseStatus !== 'idle' && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 5,
            padding: '4px 10px', borderRadius: 'var(--r-full)',
            background: sseStatus === 'connected' ? 'var(--green-dim)' : sseStatus === 'reconnecting' ? 'var(--accent-dim)' : 'var(--red-dim)',
            fontSize: 10, fontWeight: 600, letterSpacing: '0.3px',
            color: sseStatus === 'connected' ? 'var(--green)' : sseStatus === 'reconnecting' ? 'var(--accent)' : 'var(--red)',
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: '50%',
              background: 'currentColor',
              animation: sseStatus === 'reconnecting' ? 'pulse 1s infinite' : sseStatus === 'connecting' ? 'pulse 1.5s infinite' : 'none',
            }} />
            {sseStatus === 'connected' ? 'LIVE' : sseStatus === 'reconnecting' ? '重連中⋯' : sseStatus === 'connecting' ? '連線中⋯' : '已斷線'}
          </div>
        )}
        <button onClick={() => document.dispatchEvent(new CustomEvent('cadhllm:toast', { detail: '⌘K Quick Navigation 開發中' }))} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 12px', borderRadius: 'var(--r-sm)',
          background: 'var(--bg-3)', border: '1px solid var(--border-default)',
          color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer',
          fontFamily: 'var(--font-sans)', transition: 'all 0.15s',
        }}>
          <span style={{ fontSize: 11, opacity: 0.6 }}>⌘K</span>
        </button>
        <button onClick={() => document.dispatchEvent(new CustomEvent('cadhllm:toast', { detail: 'Export 功能開發中' }))} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '6px 14px', borderRadius: 'var(--r-sm)',
          background: 'var(--accent)', border: 'none',
          color: 'var(--text-inverse)', fontSize: 12, fontWeight: 600,
          cursor: 'pointer', fontFamily: 'var(--font-sans)',
          transition: 'transform 0.12s, box-shadow 0.12s',
        }}
        onMouseDown={e => e.currentTarget.style.transform = 'scale(0.97)'}
        onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
        >Export ↓</button>
      </div>
    </header>
  );
}

function StageTab({ stage, index, isActive, isReached, isPast, isLocked, currentView, onNavigate, isCompact, pipelineActive, pipelinePhase, isCanned }) {
  const [expanded, setExpanded] = React.useState(false);
  const visibleViews = React.useMemo(
    () => isCanned ? stage.views.filter(v => v !== 'user-components') : stage.views,
    [stage.views, isCanned]
  );
  const hasMultipleViews = visibleViews.length > 1;
  const defaultView = visibleViews[0];
  const wrapRef = React.useRef(null);

  React.useEffect(() => {
    if (!expanded) return;
    const close = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setExpanded(false); };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [expanded]);

  const handleClick = () => {
    if (isLocked) return;
    if (hasMultipleViews && 'ontouchstart' in window) { setExpanded(e => !e); }
    else { onNavigate(defaultView); }
  };

  return (
    <div
      ref={wrapRef}
      style={{ position: 'relative', display: 'flex', alignItems: 'stretch' }}
      onMouseEnter={() => hasMultipleViews && !isLocked && setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <button
        onClick={handleClick}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '0 12px', height: '100%',
          background: 'transparent', border: 'none',
          borderBottom: `2px solid ${isActive ? stage.color : 'transparent'}`,
          color: isLocked ? 'var(--text-disabled, var(--text-tertiary))' : isActive ? 'var(--text-primary)' : isReached ? 'var(--text-secondary)' : 'var(--text-tertiary)',
          fontSize: 12, fontWeight: isActive ? 600 : 500,
          cursor: isLocked ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
          fontFamily: 'var(--font-sans)',
          transition: 'color 0.2s, border-color 0.2s',
          opacity: isLocked ? 0.45 : 1,
        }}
      >
        <span style={{
          width: 20, height: 20, borderRadius: 'var(--r-full)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 10, fontWeight: 700, flexShrink: 0,
          background: isLocked ? 'var(--bg-3)' : isActive ? stage.color : isPast ? 'rgba(255,255,255,0.08)' : isReached ? 'var(--bg-4)' : 'var(--bg-3)',
          color: isLocked ? 'var(--text-tertiary)' : isActive ? 'var(--text-inverse)' : isPast ? stage.color : isReached ? 'var(--text-secondary)' : 'var(--text-tertiary)',
          transition: 'all 0.25s var(--ease-out)',
          position: 'relative',
        }}>
          {isLocked ? index + 1 : isPast ? '✓' : index + 1}
          {pipelineActive && (
            <span style={{
              position: 'absolute', inset: -3,
              borderRadius: '50%', border: `2px solid ${stage.color}`,
              animation: 'pulseGlow 1.5s ease-in-out infinite',
              opacity: 0.6,
            }} />
          )}
        </span>
        {!isCompact && <span>{stage.label}</span>}
        {isActive && pipelinePhase > 0 && PHASE_LABELS[pipelinePhase] && (
          <span style={{ fontSize: 9, opacity: 0.7, color: 'var(--accent)', fontWeight: 600 }}>{PHASE_LABELS[pipelinePhase]}</span>
        )}
        {hasMultipleViews && !isLocked && <span style={{ fontSize: 9, opacity: 0.5, marginLeft: -2, transition: 'transform 0.2s', transform: expanded ? 'rotate(180deg)' : 'none' }}>{'▾'}</span>}
      </button>

      {expanded && hasMultipleViews && !isLocked && (
        <div style={{
          position: 'absolute', top: '100%', left: 0,
          background: 'var(--bg-2)', border: '1px solid var(--border-default)',
          borderRadius: 'var(--r-sm)', padding: 4, minWidth: 150,
          boxShadow: 'var(--shadow-md)', zIndex: 200,
          animation: 'slideDown 0.15s var(--ease-out)',
        }}>
          {visibleViews.map(v => {
            const isCurrent = currentView === v;
            return (
              <button
                key={v}
                onClick={(e) => { e.stopPropagation(); onNavigate(v); setExpanded(false); }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  width: '100%', padding: '8px 12px',
                  background: isCurrent ? 'var(--bg-active)' : 'transparent',
                  border: 'none', borderRadius: 4, textAlign: 'left',
                  color: isCurrent ? 'var(--text-primary)' : 'var(--text-secondary)',
                  fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  transition: 'background 0.12s',
                }}
                onMouseEnter={e => !isCurrent && (e.currentTarget.style.background = 'var(--bg-hover)')}
                onMouseLeave={e => !isCurrent && (e.currentTarget.style.background = 'transparent')}
              >
                {isCurrent && <span style={{ width: 4, height: 4, borderRadius: '50%', background: stage.color }} />}
                {VIEW_META[v]?.label || v}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Composer Bar (v4 props + v5 visual enhancements) ─────────────────

const COMPOSER_HINTS = {
  idle:     { placeholder: '描述你想做的硬體專案⋯',            action: '開始設計 ↗' },
  clarify:  { placeholder: '補充說明或調整問卷答案⋯',           action: '確認 ↵' },
  evaluate: { placeholder: '輸入修改指令，例如：加厚殼壁⋯',      action: 'HITL ↗' },
  _default: { placeholder: '補充指令、加入感測器、或要求修改設計⋯', action: 'Dispatch ↗' },
};

function Composer({ onSubmit, currentView, pipelineStatus }) {
  const [value, setValue] = React.useState('');
  const [focused, setFocused] = React.useState(false);
  const hint = COMPOSER_HINTS[currentView] || COMPOSER_HINTS._default;
  const stage6e = VIEW_META[currentView]?.stage || 'engage';
  const stageData = STAGES_6E.find(s => s.id === stage6e);
  const isProcessing = pipelineStatus === 'running' || pipelineStatus === 'connecting';

  const statusColor = pipelineStatus === 'running' || pipelineStatus === 'done' ? 'var(--green)'
    : pipelineStatus === 'connecting' ? 'var(--accent)'
    : pipelineStatus === 'error' ? 'var(--red)'
    : 'var(--text-tertiary)';
  const statusText = pipelineStatus === 'running' ? 'Running'
    : pipelineStatus === 'done' ? 'Done'
    : pipelineStatus === 'connecting' ? 'Connecting'
    : pipelineStatus === 'error' ? 'Error'
    : pipelineStatus === 'waiting_clarify' || pipelineStatus === 'waiting_hitl' ? 'Waiting'
    : 'Ready';

  const handleSubmit = () => {
    if (value.trim() && !isProcessing) { onSubmit(value); setValue(''); }
  };

  return (
    <footer style={{
      height: 58, flexShrink: 0,
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '0 16px',
      background: 'var(--bg-1)',
      borderTop: '1px solid var(--border-subtle)',
    }}>
      {/* Stage indicator */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '5px 12px', borderRadius: 'var(--r-full)',
        background: 'var(--bg-3)', flexShrink: 0,
        transition: 'all 0.2s',
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: stageData?.color || 'var(--accent)',
          transition: 'background 0.3s',
        }} />
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', letterSpacing: '0.5px' }}>
          {stageData?.label?.toUpperCase() || 'ENGAGE'}
        </span>
      </div>

      {/* Input */}
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center',
        background: 'var(--bg-2)',
        border: `1px solid ${focused ? 'var(--border-strong)' : 'var(--border-default)'}`,
        borderRadius: 'var(--r-md)', padding: '0 14px', height: 40,
        transition: 'border-color 0.2s, box-shadow 0.2s',
        boxShadow: focused ? '0 0 0 3px rgba(255,255,255,0.03)' : 'none',
      }}>
        <input
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit(); }}}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={hint.placeholder}
          disabled={isProcessing}
          style={{
            flex: 1, background: 'transparent', border: 'none', outline: 'none',
            color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-sans)',
            opacity: isProcessing ? 0.5 : 1,
          }}
        />
        {isProcessing ? (
          <Spinner size={14} />
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
            ↵ Send
          </span>
        )}
      </div>

      {/* Status */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        fontSize: 11, color: 'var(--text-tertiary)', flexShrink: 0,
      }}>
        <span style={{
          width: 6, height: 6, borderRadius: '50%',
          background: statusColor,
          animation: isProcessing ? 'dotPulse 1s ease infinite' : 'none',
        }} />
        <span className="mono">{statusText}</span>
      </div>

      {/* Dispatch */}
      <button
        onClick={handleSubmit}
        disabled={isProcessing || !value.trim()}
        style={{
          padding: '9px 20px', borderRadius: 'var(--r-sm)',
          background: isProcessing || !value.trim() ? 'var(--bg-4)' : 'var(--accent)',
          border: 'none',
          color: isProcessing || !value.trim() ? 'var(--text-tertiary)' : 'var(--text-inverse)',
          fontSize: 12, fontWeight: 700,
          cursor: isProcessing || !value.trim() ? 'not-allowed' : 'pointer',
          fontFamily: 'var(--font-sans)',
          letterSpacing: '0.5px', flexShrink: 0,
          transition: 'all 0.15s',
        }}
        onMouseDown={e => { if (!isProcessing && value.trim()) e.currentTarget.style.transform = 'scale(0.97)'; }}
        onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
      >{hint.action}</button>
    </footer>
  );
}

Object.assign(window, {
  VIEW_META, STAGE_UNLOCK_PHASE, PHASE_LABELS, TopNav, Composer,
});
