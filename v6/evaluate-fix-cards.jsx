// ═══════════════════════════════════════════
// evaluate-fix-cards.jsx — fix-choice card sub-components for EvaluateView
// Depends on: evaluate-cards.jsx (PowerBudgetBar, _renderIssueItem)
// ═══════════════════════════════════════════

function SwapFixCard({ fixOpts, submitting, selectedSwaps, selectedSwapIds, projectedTotal, budgetMa, onToggleSwap, onConfirm }) {
  return (
    <Card style={{ overflow: 'hidden', border: '1.5px solid var(--red)', animation: 'slideUp 0.4s var(--ease-out) 200ms both' }}>
      {/* Header: overbudget bar */}
      <div style={{ padding: '14px 18px', background: 'var(--red-dim)', borderBottom: '1px solid var(--red)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--red)' }}>⚡ 電氣超標</span>
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--red)' }}>
            {fixOpts.overbudgetDetail?.total_ma ?? '—'} / {fixOpts.overbudgetDetail?.budget_ma ?? '—'} mA（+{fixOpts.overbudgetDetail?.over_pct ?? 0}%）
          </span>
        </div>
        <PowerBudgetBar
          total={fixOpts.overbudgetDetail?.total_ma || 0}
          budget={budgetMa}
          projectedTotal={projectedTotal}
          selectedSwapIds={selectedSwapIds}
        />
      </div>

      {/* Issues */}
      {fixOpts.issues?.length > 0 && (
        <div style={{ padding: '10px 18px', borderBottom: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--text-secondary)' }}>
          {fixOpts.issues.map(_renderIssueItem)}
        </div>
      )}

      {/* Swap suggestions */}
      <div style={{ padding: '12px 18px 4px' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-tertiary)', marginBottom: 10, letterSpacing: '0.5px' }}>
          選擇要替換的元件以降低功耗：
        </div>
        {fixOpts.swapSuggestions.map(swap => {
          const checked = !!selectedSwaps[swap.id];
          return (
            <div key={swap.id}
              onClick={() => onToggleSwap(swap.id)}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '12px 14px', marginBottom: 8,
                borderRadius: 'var(--r-sm)', cursor: 'pointer',
                background: checked ? 'rgba(114,196,207,0.08)' : 'var(--bg-3)',
                border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--border-subtle)'}`,
                transition: 'all 0.15s',
              }}
            >
              <div style={{
                width: 20, height: 20, borderRadius: 4, flexShrink: 0, marginTop: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: checked ? 'var(--accent)' : 'var(--bg-2)',
                border: `1.5px solid ${checked ? 'var(--accent)' : 'var(--border-default)'}`,
                color: '#fff', fontSize: 12, fontWeight: 700,
              }}>{checked ? '✓' : ''}</div>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                    {swap.current.type.replace('-class', '')}
                  </span>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>→</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>
                    {swap.alternative.label}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontSize: 12 }}>
                  <span style={{ color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>{swap.current.ma} mA</span>
                  <span style={{ color: 'var(--text-tertiary)' }}>→</span>
                  <span style={{ color: 'var(--green)', fontFamily: 'var(--font-mono)' }}>{swap.alternative.ma} mA</span>
                  <Badge color="var(--green)" bg="var(--green-dim)" style={{ fontSize: 10 }}>
                    省 {swap.saving_ma} mA
                  </Badge>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{swap.trade_off}</div>
                <div style={{ fontSize: 10, color: 'var(--accent)', marginTop: 3 }}>💡 {swap.stem_concept}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Projected total + confirm button */}
      <div style={{ padding: '12px 18px 16px', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontSize: 13 }}>
          {selectedSwapIds.length > 0 ? (
            <span>
              替換後預估：
              <span style={{
                fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: projectedTotal <= budgetMa ? 'var(--green)' : 'var(--red)',
              }}>
                {projectedTotal} mA
              </span>
              <span style={{ color: 'var(--text-tertiary)' }}> / {fixOpts.overbudgetDetail?.budget_ma ?? budgetMa} mA</span>
              {projectedTotal <= budgetMa
                ? <span style={{ color: 'var(--green)', marginLeft: 6 }}>✓ 合格</span>
                : <span style={{ color: 'var(--red)', marginLeft: 6 }}>仍超標</span>}
            </span>
          ) : (
            <span style={{ color: 'var(--text-tertiary)' }}>請勾選至少一項替換</span>
          )}
        </div>
        <button
          onClick={() => onConfirm('confirm_swaps')}
          disabled={submitting || selectedSwapIds.length === 0}
          style={{
            padding: '10px 22px', borderRadius: 'var(--r-md)',
            background: selectedSwapIds.length > 0 ? 'var(--accent)' : 'var(--bg-4)',
            border: 'none', color: 'var(--text-inverse)', fontSize: 13,
            fontWeight: 700, cursor: selectedSwapIds.length > 0 ? 'pointer' : 'not-allowed',
            fontFamily: 'var(--font-sans)', opacity: submitting ? 0.6 : 1,
          }}
        >確認替換 · 退回驗證 →</button>
      </div>
    </Card>
  );
}

function NoSwapFixCard({ fixOpts, submitting, onConfirm }) {
  return (
    <Card style={{ overflow: 'hidden', border: '1.5px solid var(--accent)', animation: 'slideUp 0.4s var(--ease-out) 200ms both' }}>
      <div style={{ padding: '14px 18px', background: 'var(--accent-dim)', borderBottom: '1px solid var(--accent)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--accent)' }}>⚡ 電氣超標 — 無自動替換方案</span>
          <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent)' }}>
            {fixOpts.overbudgetDetail.total_ma ?? '—'} / {fixOpts.overbudgetDetail.budget_ma ?? '—'} mA
          </span>
        </div>
      </div>
      {fixOpts.issues?.length > 0 && (
        <div style={{ padding: '10px 18px', borderBottom: '1px solid var(--border-subtle)', fontSize: 12, color: 'var(--text-secondary)' }}>
          {fixOpts.issues.map(_renderIssueItem)}
        </div>
      )}
      <div style={{ padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          目前超標元件無預設低功耗替代品，可忽略超標繼續或返回修改設計。
        </span>
        <button onClick={() => onConfirm('skip_gate')} disabled={submitting} style={{
          padding: '10px 20px', borderRadius: 'var(--r-md)',
          background: 'var(--accent)', border: 'none',
          color: 'var(--text-inverse)', fontSize: 13, fontWeight: 700,
          cursor: 'pointer', fontFamily: 'var(--font-sans)',
          whiteSpace: 'nowrap', opacity: submitting ? 0.6 : 1,
        }}>忽略超標 · 繼續 →</button>
      </div>
    </Card>
  );
}

function VlmFixCard({ fixOpts, submitting, countdown, extensions, onConfirm, onExtend }) {
  return (
    <Card style={{ overflow: 'hidden', border: '1px solid var(--accent)', animation: 'slideUp 0.4s var(--ease-out) 200ms both' }}>
      <div style={{ padding: '12px 18px', background: 'var(--accent-dim)', borderBottom: '1px solid var(--accent)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>VLM 修正選項</span>
        {countdown != null && countdown > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700,
              color: countdown <= 30 ? 'var(--red)' : 'var(--accent)',
              animation: countdown <= 30 ? 'pulse 1s infinite' : 'none',
            }}>{countdown}s</span>
            {countdown <= 30 && (
              <span style={{ fontSize: 10, color: 'var(--red)' }}>即將逾時</span>
            )}
            {extensions < 2 && (
              <button onClick={(e) => { e.stopPropagation(); onExtend(); }} style={{
                padding: '2px 8px', borderRadius: 'var(--r-sm)',
                background: 'var(--bg-3)', border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)', fontSize: 10, cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}>+60s ({2 - extensions})</button>
            )}
          </div>
        )}
        {countdown === 0 && (
          <span style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600 }}>已逾時 · 自動選取 A</span>
        )}
      </div>
      <div style={{ padding: '12px 18px' }}>
        {fixOpts.issues?.length > 0 && (
          <div style={{ marginBottom: 12, fontSize: 12, color: 'var(--text-secondary)' }}>
            {fixOpts.issues.map(_renderIssueItem)}
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {fixOpts.options.map((opt) => (
            <button key={opt.id} onClick={() => onConfirm(opt.id)} disabled={submitting} style={{
              padding: '10px 16px', borderRadius: 'var(--r-sm)',
              background: 'var(--bg-3)', border: '1px solid var(--border-default)',
              color: 'var(--text-primary)', fontSize: 13, cursor: 'pointer',
              fontFamily: 'var(--font-sans)', textAlign: 'left',
              transition: 'border-color 0.15s',
            }}>
              <span style={{ fontWeight: 600 }}>[{opt.id}]</span> {opt.label || opt.description || ''}
            </button>
          ))}
        </div>
      </div>
    </Card>
  );
}

Object.assign(window, { SwapFixCard, NoSwapFixCard, VlmFixCard });
