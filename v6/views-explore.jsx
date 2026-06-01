// ═══════════════════════════════════════════
// views-explore.jsx — v6: ClarifyView + ExtractView orchestrators
// Depends on: explore/explore-data.js, explore/explore-panels.jsx
// ═══════════════════════════════════════════

// ─── Clarify View ─────────────────

function ClarifyView({ onNavigate, store }) {
  const questions = store?.clarifyQuestions || [];
  const resolve = store?.componentResolve;
  const project = store?.project;
  const jobId = store?.jobId;
  const [answers, setAnswers] = React.useState({});
  const [compConfirms, setCompConfirms] = React.useState({});
  const [specConfirms, setSpecConfirms] = React.useState({});
  const [confirming, setConfirming] = React.useState(false);
  const [timeLeft, setTimeLeft] = React.useState(null);

  React.useEffect(() => {
    if (store?.status !== 'waiting_clarify') { setTimeLeft(null); return; }
    setTimeLeft(CLARIFY_TIMEOUT_S);
    const id = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) { clearInterval(id); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [store?.status]);

  React.useEffect(() => {
    const m = {};
    questions.forEach(q => { if (q.selected) m[q.id] = q.selected; });
    setAnswers(m);
  }, [questions.length]);

  const allAnswered = questions.every(q => answers[q.id]);

  const handleConfirm = async () => {
    if (!jobId || store?.status !== 'waiting_clarify') {
      onNavigate('extract');
      return;
    }
    setConfirming(true);
    try {
      const merged = { ...answers };
      if (Object.keys(compConfirms).length) {
        merged._component_confirms = compConfirms;
      }
      if (Object.keys(specConfirms).length) {
        merged._spec_confirms = specConfirms;
      }
      // S9: quantity confirm answers
      const qtyConfirms = {};
      for (const q of questions) {
        if (q._qty_confirm_type && answers[q.id]) {
          qtyConfirms[q._qty_confirm_type] = answers[q.id];
        }
      }
      if (Object.keys(qtyConfirms).length) {
        merged._qty_confirms = qtyConfirms;
      }
      await API.confirmClarify(jobId, merged);
      PipelineStore.dispatch({ type: 'CLARIFY_CONFIRMED' });
    } catch (err) {
      console.error('confirmClarify failed:', err);
      onNavigate('extract');
    }
    setConfirming(false);
  };

  const promptText = project?.prompt || '';

  if (!questions.length) {
    return (
      <div key="clarify" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <Spinner size={24} />
            <div style={{ fontSize: 14, marginTop: 12 }}>Phase I 分析中，請稍候</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div key="clarify" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '36px 32px' }}>
          {/* Header */}
          <div style={{ marginBottom: 32, animation: 'slideUp 0.4s var(--ease-out)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Badge color="var(--6e-explore)" bg="var(--accent-2-dim)">Explore</Badge>
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>需求探索 · Step 1/2</span>
            </div>
            <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>確認設計方向</h2>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              根據你的描述，請確認以下關鍵決策，幫助 AI 做出更好的元件選擇。
            </p>
          </div>

          {/* Prompt echo */}
          {promptText && (
            <div style={{
              padding: '14px 18px', marginBottom: 24,
              background: 'var(--bg-2)', border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-md)', borderLeft: '3px solid var(--accent)',
              animation: 'slideUp 0.45s var(--ease-out)',
            }}>
              <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '1.2px', color: 'var(--text-tertiary)', marginBottom: 4 }}>USER PROMPT</div>
              <div style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6 }}>「{promptText}」</div>
            </div>
          )}

          {/* Demo read-only hint */}
          {store?.isCanned && (
            <div style={{
              padding: '10px 14px', marginBottom: 20,
              background: 'var(--accent-dim)', border: '1px solid var(--accent)',
              borderRadius: 'var(--r-sm)', fontSize: 12, color: 'var(--accent)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span>🎯</span>
              <span>Demo 預覽 — 此範本為檢視模式，要修改答案請先點右上「Fork 為新專案」</span>
            </div>
          )}

          {/* Countdown bar */}
          {timeLeft != null && timeLeft > 0 && (
            <div style={{
              marginBottom: 16, padding: '8px 14px',
              background: timeLeft <= 30 ? 'var(--red-dim)' : 'var(--bg-3)',
              border: `1px solid ${timeLeft <= 30 ? 'var(--red)' : 'var(--border-subtle)'}`,
              borderRadius: 'var(--r-sm)',
              display: 'flex', alignItems: 'center', gap: 10,
              transition: 'all 0.3s',
              animation: timeLeft <= 30 ? 'pulse 1s infinite' : 'none',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{
                  height: 3, borderRadius: 2, background: 'var(--bg-4)', overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%', borderRadius: 2,
                    width: `${(timeLeft / CLARIFY_TIMEOUT_S) * 100}%`,
                    background: timeLeft <= 30 ? 'var(--red)' : timeLeft <= 60 ? 'var(--accent)' : 'var(--green)',
                    transition: 'width 1s linear, background 0.3s',
                  }} />
                </div>
              </div>
              <span style={{
                fontSize: 11, fontWeight: 600, fontFamily: 'var(--font-mono)',
                color: timeLeft <= 30 ? 'var(--red)' : 'var(--text-tertiary)',
              }}>
                {Math.floor(timeLeft / 60)}:{String(timeLeft % 60).padStart(2, '0')}
              </span>
              {timeLeft <= 30 && (
                <span style={{ fontSize: 11, color: 'var(--red)', fontWeight: 600 }}>
                  逾時將自動使用推薦設定
                </span>
              )}
            </div>
          )}

          {/* Questions */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {questions.map((q, qi) => (
              <Card key={q.id} style={{
                padding: '20px 24px',
                animation: `slideUp 0.4s var(--ease-out) ${100 + qi * 80}ms both`,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                  <span style={{
                    width: 24, height: 24, borderRadius: 'var(--r-full)',
                    background: answers[q.id] ? 'var(--accent-2-dim)' : 'var(--bg-4)',
                    color: answers[q.id] ? 'var(--6e-explore)' : 'var(--text-tertiary)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: answers[q.id] ? 11 : 12, fontWeight: 700,
                    transition: 'all 0.25s var(--ease-out)',
                  }}>{answers[q.id] ? '✓' : qi + 1}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: '1px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>{q.label}</span>
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 14 }}>{q.question}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {q.options.map(opt => {
                      const sel = answers[q.id] === opt;
                      const readOnly = !!store?.isCanned;
                      return (
                        <button key={opt}
                          onClick={readOnly ? undefined : () => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                          disabled={readOnly && !sel}
                          style={{
                            padding: '10px 18px', borderRadius: 'var(--r-md)',
                            background: sel ? 'var(--accent-2-dim)' : 'var(--bg-3)',
                            border: `1.5px solid ${sel ? 'var(--6e-explore)' : 'var(--border-subtle)'}`,
                            color: sel ? 'var(--text-primary)' : 'var(--text-secondary)',
                            fontSize: 13, fontWeight: sel ? 600 : 400,
                            cursor: readOnly ? 'default' : 'pointer',
                            fontFamily: 'var(--font-sans)',
                            transition: 'all 0.2s var(--ease-out)',
                            transform: sel ? 'scale(1.02)' : 'scale(1)',
                            opacity: readOnly && !sel ? 0.4 : 1,
                          }}
                        >{opt}</button>
                      );
                    })}
                  </div>
                  {answers[q.id] && (() => {
                    const hint = _getHint(answers[q.id], q);
                    if (!hint) return null;
                    return (
                      <div style={{
                        fontSize: 12, color: 'var(--6e-explore)', lineHeight: 1.5,
                        padding: '6px 12px', background: 'var(--accent-2-dim)',
                        borderRadius: 'var(--r-sm)', animation: 'slideUp 0.2s var(--ease-out)',
                      }}>
                        <div>💡 {hint.text}</div>
                        {(hint.pro || hint.con) && (
                          <div style={{ marginTop: 4, fontSize: 11, color: 'var(--text-secondary)' }}>
                            {hint.pro && <span style={{ marginRight: 12 }}>✅ {hint.pro}</span>}
                            {hint.con && hint.con !== '無' && <span>⚠️ {hint.con}</span>}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </Card>
            ))}
          </div>

          {/* Auto-sized enclosure info */}
          {store?.enclosureSizing && (
            <div style={{
              marginTop: 16, padding: '12px 16px',
              background: 'var(--bg-2)', border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)', fontSize: 12, color: 'var(--text-secondary)',
              animation: 'slideUp 0.5s var(--ease-out) 350ms both',
            }}>
              <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>📐 外殼尺寸（自動）</span>
              {'　' + store.enclosureSizing.rationale}
            </div>
          )}

          {/* Component resolve confirmation */}
          {resolve && (resolve.fuzzy_candidates?.length > 0 || resolve.unknowns?.length > 0 || resolve.missing_mentions?.length > 0) && (
            <ResolveConfirmPanel
              resolve={resolve}
              compConfirms={compConfirms}
              setCompConfirms={setCompConfirms}
            />
          )}

          {/* Spec cross-validation warnings (U6 Phase 2) */}
          {resolve?.spec_warnings?.length > 0 && (
            <SpecWarningsPanel
              resolve={resolve}
              specConfirms={specConfirms}
              setSpecConfirms={setSpecConfirms}
            />
          )}

          {/* Action */}
          <div style={{
            display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 28,
            animation: 'slideUp 0.5s var(--ease-out) 400ms both',
          }}>
            <button
              onClick={handleConfirm}
              disabled={confirming}
              style={{
                padding: '12px 28px', borderRadius: 'var(--r-md)',
                background: confirming ? 'var(--bg-4)' : allAnswered ? 'var(--accent)' : 'var(--bg-4)',
                border: 'none',
                color: allAnswered && !confirming ? 'var(--text-inverse)' : 'var(--text-tertiary)',
                fontSize: 14, fontWeight: 700,
                cursor: confirming ? 'wait' : allAnswered ? 'pointer' : 'default',
                fontFamily: 'var(--font-sans)',
                transition: 'all 0.2s',
                opacity: confirming ? 0.7 : 1,
              }}
            >{confirming ? '確認中⋯' : '確認方向 · 進入選型 →'}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Extract View ─────────────────

function ExtractView({ onNavigate, store }) {
  const slots = store?.extractSlots || [];
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (slots.length > 0) setLoading(false);
    else {
      const t = setTimeout(() => setLoading(false), 1200);
      return () => clearTimeout(t);
    }
  }, [slots.length]);

  if (!slots.length && !loading) {
    return (
      <div key="extract" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <Spinner size={24} />
            <div style={{ fontSize: 14, marginTop: 12 }}>Phase II 元件解析中，請稍候</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div key="extract" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
        <div style={{ maxWidth: 1000, margin: '0 auto', padding: '32px 32px' }}>
          {/* Power Gate (Phase II/III fix_choice at top) */}
          <PowerGatePanel store={store} />
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, animation: 'slideUp 0.4s var(--ease-out)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <Badge color="var(--6e-explore)" bg="var(--accent-2-dim)">Explore</Badge>
                <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>元件選型 · Step 2/2</span>
              </div>
              <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>最佳選型 · Extract</h2>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                SLOTS · {slots.length} &nbsp;|&nbsp; SOURCES · {slots.reduce((s, sl) => s + sl.candidates.length, 0)}
              </p>
              <div style={{ display: 'flex', gap: 14, marginTop: 6, fontSize: 11, color: 'var(--text-tertiary)' }}>
                <span>適配度：</span>
                <span style={{ color: 'var(--green)' }}>● 80+ 強推薦</span>
                <span style={{ color: 'var(--accent)' }}>● 60-79 可用</span>
                <span>● &lt;60 參考</span>
              </div>
            </div>
          </div>

          {/* Slots */}
          {loading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {[0,1,2].map(i => (
                <Card key={i} style={{ padding: '20px', animation: `slideUp 0.3s var(--ease-out) ${i * 100}ms both` }}>
                  <Skeleton width={180} height={14} style={{ marginBottom: 12 }} />
                  <Skeleton height={48} style={{ marginBottom: 8 }} />
                  <Skeleton width="60%" height={12} />
                </Card>
              ))}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {slots.map((slot, si) => (
                <div key={si} style={{ animation: `slideUp 0.35s var(--ease-out) ${si * 80}ms both` }}>
                  <ExtractSlot slot={slot} readOnly={!!store?.isCanned} onSwap={(label, id) => {
                    PipelineStore.dispatch({ type: 'SWAP_EXTRACT_PICK', slotLabel: label, candidateId: id });
                  }} />
                </div>
              ))}
            </div>
          )}

          {/* Action */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 28, animation: 'slideUp 0.5s var(--ease-out) 300ms both' }}>
            <button onClick={() => onNavigate('clarify')} style={{
              padding: '10px 20px', borderRadius: 'var(--r-md)',
              background: 'transparent', border: '1px solid var(--border-default)',
              color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-sans)',
              transition: 'all 0.15s',
            }}>← 回到確認</button>
            <button onClick={() => onNavigate('plan')} style={{
              padding: '12px 28px', borderRadius: 'var(--r-md)',
              background: 'var(--accent)', border: 'none',
              color: 'var(--text-inverse)', fontSize: 14, fontWeight: 700,
              cursor: 'pointer', fontFamily: 'var(--font-sans)',
              transition: 'all 0.15s',
            }}>鎖定選型 · 進入規劃 →</button>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ClarifyView, ExtractView });
