// ═══════════════════════════════════════════
// evaluate-cards.jsx — shared sub-components for EvaluateView
// ═══════════════════════════════════════════

function PowerBudgetBar({ total, budget, projectedTotal, selectedSwapIds }) {
  const barMax = Math.max(total, budget) * 1.1;
  const budgetPct = (budget / barMax) * 100;
  const currentPct = (total / barMax) * 100;
  const projPct = projectedTotal != null ? (projectedTotal / barMax) * 100 : null;
  const projOk = projectedTotal != null && projectedTotal <= budget;
  return (
    <div style={{ position: 'relative', height: 22, background: 'var(--bg-2)', borderRadius: 'var(--r-sm)', overflow: 'hidden' }}>
      {projPct != null && selectedSwapIds.length > 0 && (
        <div style={{
          position: 'absolute', left: 0, top: 0, bottom: 0,
          width: `${Math.min(projPct, 100)}%`,
          background: projOk ? 'var(--green)' : 'var(--accent)',
          opacity: 0.5, transition: 'width 0.3s',
        }} />
      )}
      <div style={{
        position: 'absolute', left: 0, top: 0, bottom: 0,
        width: `${Math.min(currentPct, 100)}%`,
        background: 'var(--red)', opacity: selectedSwapIds.length > 0 ? 0.25 : 0.5,
        transition: 'opacity 0.3s',
      }} />
      <div style={{
        position: 'absolute', left: `${budgetPct}%`, top: 0, bottom: 0,
        width: 2, background: 'var(--text-primary)', opacity: 0.6,
      }} />
      <div style={{
        position: 'absolute', left: `${budgetPct}%`, top: '50%', transform: 'translate(4px, -50%)',
        fontSize: 9, fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap',
      }}>{budget} mA</div>
    </div>
  );
}

function _renderIssueItem(iss, i) {
  return (
    <div key={i} style={{ marginBottom: 2 }}>
      • {typeof iss === 'string' ? iss : iss.detail || JSON.stringify(iss)}
    </div>
  );
}

function ResumePhaseCard({ jobId, currentPhase, onResume }) {
  const [selected, setSelected] = React.useState(1);
  const [confirming, setConfirming] = React.useState(false);
  const phases = [];
  for (let i = 1; i <= Math.min(currentPhase, 5); i++) {
    const labels = { 1: 'Planning', 2: 'Extract', 3: 'Schematic', 4: 'CAD', 5: 'Firmware' };
    phases.push({ n: i, label: labels[i] || `Phase ${i}` });
  }
  return (
    <Card style={{ padding: '16px 18px', animation: 'slideUp 0.4s var(--ease-out) 650ms both' }}>
      <SectionLabel style={{ marginBottom: 10 }}>Re-run from Phase</SectionLabel>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
        {phases.map(p => (
          <button key={p.n} onClick={() => { setSelected(p.n); setConfirming(false); }} style={{
            padding: '5px 10px', borderRadius: 'var(--r-sm)', fontSize: 11, fontWeight: 600,
            background: selected === p.n ? 'var(--accent-dim)' : 'var(--bg-3)',
            border: `1.5px solid ${selected === p.n ? 'var(--accent)' : 'var(--border-subtle)'}`,
            color: selected === p.n ? 'var(--accent)' : 'var(--text-secondary)',
            cursor: 'pointer', fontFamily: 'var(--font-sans)', transition: 'all 0.15s',
          }}>{p.n}. {p.label}</button>
        ))}
      </div>
      {!confirming ? (
        <button onClick={() => setConfirming(true)} style={{
          width: '100%', padding: '8px 14px', borderRadius: 'var(--r-sm)',
          background: 'var(--bg-3)', border: '1px solid var(--border-default)',
          color: 'var(--text-secondary)', fontSize: 12, cursor: 'pointer',
          fontFamily: 'var(--font-sans)', transition: 'all 0.15s',
        }}>Phase {selected} 重跑</button>
      ) : (
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={() => setConfirming(false)} style={{
            flex: 1, padding: '8px 10px', borderRadius: 'var(--r-sm)',
            background: 'var(--bg-3)', border: '1px solid var(--border-default)',
            color: 'var(--text-tertiary)', fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>取消</button>
          <button onClick={() => { setConfirming(false); onResume(jobId, selected); }} style={{
            flex: 2, padding: '8px 10px', borderRadius: 'var(--r-sm)',
            background: 'var(--accent)', border: 'none',
            color: '#0a0a0a', fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>確認重跑 Phase {selected}+</button>
        </div>
      )}
    </Card>
  );
}

Object.assign(window, { PowerBudgetBar, _renderIssueItem, ResumePhaseCard });
