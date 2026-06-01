// ═══════════════════════════════════════════
// explore/explore-data.js — Static config & shared styles for Explore views
// ═══════════════════════════════════════════

// OPTION_HINTS — defined in config/option-hints.js
const OPTION_HINTS = window.OPTION_HINTS;

function _getHint(optionValue, question) {
  if (question?.hints?.[optionValue]) return question.hints[optionValue];
  const h = OPTION_HINTS[optionValue];
  if (!h) return null;
  return typeof h === 'string' ? { text: h } : h;
}

const CLARIFY_TIMEOUT_S = 600;

// ── Shared panel styles ──────────────────────
const _panelRowStyle = {
  padding: '12px 16px', marginBottom: 10, borderRadius: 'var(--r-sm)',
  background: 'var(--bg-2)', border: '1px solid var(--border-subtle)',
};
const _panelBtnBase = {
  padding: '6px 14px', borderRadius: 'var(--r-sm)', fontSize: 12,
  fontFamily: 'var(--font-sans)', cursor: 'pointer',
};
const _panelBtnStyle = (active, color) => ({
  ..._panelBtnBase,
  background: active ? `var(--${color}-dim)` : 'var(--bg-3)',
  border: `1px solid ${active ? `var(--${color})` : 'var(--border-subtle)'}`,
  color: active ? (color === 'red' ? 'var(--red)' : 'var(--text-primary)') : 'var(--text-secondary)',
  fontWeight: active ? 600 : 400,
});

Object.assign(window, {
  OPTION_HINTS, _getHint, CLARIFY_TIMEOUT_S,
  _panelRowStyle, _panelBtnBase, _panelBtnStyle,
});
