// ═══════════════════════════════════════════
// ui-primitives.jsx — Shared UI building blocks
// Split from shell.jsx (INF1: files under 500 lines)
// ═══════════════════════════════════════════

function Badge({ children, color, bg, style }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 11, fontWeight: 600, letterSpacing: '0.5px',
      padding: '2px 8px', borderRadius: 'var(--r-full)',
      color: color || 'var(--text-secondary)',
      background: bg || 'var(--bg-3)',
      ...style,
    }}>{children}</span>
  );
}

function Card({ children, style, hover, onClick, _className }) {
  const [hovered, setHovered] = React.useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: 'var(--bg-2)',
        border: `1px solid ${hovered && hover ? 'var(--border-strong)' : 'var(--border-subtle)'}`,
        borderRadius: 'var(--r-md)',
        transition: 'border-color 0.2s, box-shadow 0.2s, transform 0.2s',
        cursor: onClick ? 'pointer' : 'default',
        boxShadow: hovered && hover ? 'var(--shadow-sm)' : 'none',
        transform: hovered && onClick ? 'translateY(-1px)' : 'none',
        ...style,
      }}
    >{children}</div>
  );
}

function SectionLabel({ children, color, style }) {
  return (
    <div style={{
      fontSize: 11, fontWeight: 600, letterSpacing: '1.5px',
      textTransform: 'uppercase', color: color || 'var(--text-tertiary)',
      ...style,
    }}>{children}</div>
  );
}

function ProgressBar({ value, max, color, style, animated }) {
  const pct = Math.min(100, (value / max) * 100);
  const warn = pct > 90;
  return (
    <div style={{ height: 4, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden', position: 'relative', ...style }}>
      <div style={{
        width: `${pct}%`, height: '100%',
        background: warn ? 'var(--red)' : (color || 'var(--accent)'),
        borderRadius: 2, transition: 'width 0.6s var(--ease-out)',
      }} />
      {animated && (
        <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', borderRadius: 2 }}>
          <div style={{
            width: '40%', height: '100%',
            background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)',
            animation: 'progressSweep 1.8s ease infinite',
          }} />
        </div>
      )}
    </div>
  );
}

function IconBtn({ children, active, onClick, title, style }) {
  const [h, setH] = React.useState(false);
  return (
    <button
      title={title} onClick={onClick}
      onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: 32, height: 32, borderRadius: 'var(--r-sm)',
        background: active ? 'var(--bg-active)' : h ? 'var(--bg-hover)' : 'transparent',
        border: 'none', color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
        cursor: 'pointer', fontSize: 15, transition: 'all 0.15s',
        ...style,
      }}
    >{children}</button>
  );
}

function Spinner({ size = 16, color = 'var(--accent)' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" style={{ animation: 'spin 0.8s linear infinite' }}>
      <circle cx="8" cy="8" r="6" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round"
        strokeDasharray="28" strokeDashoffset="8" opacity="0.8" />
    </svg>
  );
}

function Skeleton({ width, height = 16, radius = 4, style }) {
  return (
    <div style={{
      width: width || '100%', height, borderRadius: radius,
      background: 'linear-gradient(90deg, var(--bg-3) 25%, var(--bg-4) 50%, var(--bg-3) 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s ease infinite',
      ...style,
    }} />
  );
}

Object.assign(window, {
  Badge, Card, SectionLabel, ProgressBar, IconBtn, Spinner, Skeleton,
});
