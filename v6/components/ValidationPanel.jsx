// ValidationPanel — IC-level assembly validation results display
// Extracted from views-engineer-assembly.jsx

function ValidationPanel({ validation, floating, title }) {
  if (!validation) return null;
  const { passed, checks_run, checks_passed, issues } = validation;
  const errors = (issues || []).filter(i => i.severity === 'error');
  const warnings = (issues || []).filter(i => i.severity === 'warning');

  const baseStyle = floating ? {
    position: 'absolute', top: 12, right: 12, zIndex: 20,
    width: 260, maxHeight: 300, overflow: 'auto',
    background: 'var(--bg-1)', borderRadius: 'var(--r-md)',
    border: `1px solid ${passed ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)'}`,
    padding: '12px 14px', fontSize: 11,
    boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
  } : {
    padding: '14px', borderRadius: 'var(--r-md)',
    background: 'var(--bg-2)', fontSize: 11,
    border: `1px solid ${passed ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)'}`,
  };

  return (
    <div style={baseStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: passed ? 'var(--success, #22c55e)' : 'var(--danger, #ef4444)',
          flexShrink: 0,
        }} />
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
          {title || 'Validation'} {passed ? 'Passed' : 'Failed'}
        </span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {checks_passed}/{checks_run}
        </span>
      </div>
      {errors.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {errors.slice(0, 8).map((iss, i) => (
            <div key={i} style={{
              padding: '4px 6px', borderRadius: 4,
              background: 'rgba(239,68,68,0.1)', color: 'var(--danger, #ef4444)',
            }}>
              <span style={{ fontWeight: 600 }}>{iss.component}</span>: {iss.message}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <details style={{ marginTop: errors.length ? 6 : 0 }}>
          <summary style={{ cursor: 'pointer', color: 'var(--text-tertiary)' }}>
            {warnings.length} warning{warnings.length > 1 ? 's' : ''}
          </summary>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, marginTop: 4 }}>
            {warnings.slice(0, 8).map((iss, i) => (
              <div key={i} style={{
                padding: '3px 6px', borderRadius: 4,
                background: 'rgba(234,179,8,0.1)', color: 'var(--warning, #eab308)',
                fontSize: 10,
              }}>
                <span style={{ fontWeight: 600 }}>{iss.component}</span>: {iss.message}
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

window.ValidationPanel = ValidationPanel;
