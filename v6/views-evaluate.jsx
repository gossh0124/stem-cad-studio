// ═══════════════════════════════════════════
// views-evaluate.jsx — v6: v4 HITL backend + v5 visual polish
// Depends on: evaluate-cards.jsx, evaluate-fix-cards.jsx
// ═══════════════════════════════════════════

function EvaluateView({ _onNavigate, onResumePipeline, store }) {
  const project = store?.project || {};
  const constraintChecks = store?.constraintChecks || [];
  const hitlHistory = store?.hitlHistory || [];
  const fixOpts = store?.fixChoiceOptions;
  const jobId = store?.jobId;
  const [hitlAction, setHitlAction] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [countdown, setCountdown] = React.useState(null);
  const [swapConfirm, setSwapConfirm] = React.useState(null);
  const [extensions, setExtensions] = React.useState(0);
  const [revealIdx, setRevealIdx] = React.useState(0);
  const [savedToProjects, setSavedToProjects] = React.useState(false);
  const [savingProject, setSavingProject] = React.useState(false);

  // fix_choice countdown
  React.useEffect(() => {
    if (!fixOpts?.timeoutS) { setCountdown(null); return; }
    setCountdown(fixOpts.timeoutS);
    setExtensions(0);
    const id = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) { clearInterval(id); return 0; }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [fixOpts?.timeoutS]);

  const checkGroups = React.useMemo(() => {
    if (!constraintChecks.length) return [];
    const grouped = {};
    for (const c of constraintChecks) {
      const cat = c.cat || 'OTHER';
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push({
        label: c.rule || '—',
        status: (c.status || 'PASS').toLowerCase(),
        detail: c.detail || '',
      });
    }
    return Object.entries(grouped).map(([category, items]) => ({ category, items }));
  }, [constraintChecks]);

  const totalChecks = React.useMemo(
    () => checkGroups.reduce((s, g) => s + g.items.length, 0),
    [checkGroups]
  );

  // Sequential reveal animation (v5)
  React.useEffect(() => { setRevealIdx(0); }, [constraintChecks]);

  React.useEffect(() => {
    if (revealIdx >= totalChecks) return;
    const t = setTimeout(() => setRevealIdx(i => i + 1), 150);
    return () => clearTimeout(t);
  }, [revealIdx, totalChecks]);

  const rubrics = store?.stemRubrics || [];

  const handleAccept = async () => {
    if (!jobId) return;
    setSubmitting(true);
    try {
      await API.sendHitl(jobId, 'accept', {});
      PipelineStore.dispatch({ type: 'HITL_SUBMIT' });
    } catch (err) { console.error('HITL accept failed:', err); }
    setSubmitting(false);
  };

  const [selectedSwaps, setSelectedSwaps] = React.useState({});

  const toggleSwap = (swapId) => {
    setSelectedSwaps(prev => ({ ...prev, [swapId]: !prev[swapId] }));
  };

  const selectedSwapIds = Object.keys(selectedSwaps).filter(k => selectedSwaps[k]);

  const projectedTotal = React.useMemo(() => {
    if (!fixOpts?.overbudgetDetail) return null;
    const base = fixOpts.overbudgetDetail.total_ma;
    const saving = (fixOpts.swapSuggestions || [])
      .filter(s => selectedSwaps[s.id])
      .reduce((sum, s) => sum + s.saving_ma, 0);
    return Math.round((base - saving) * 10) / 10;
  }, [fixOpts, selectedSwaps]);

  const budgetMa = fixOpts?.overbudgetDetail?.budget_ma ?? 500;

  const fixCardType = !fixOpts ? null
    : fixOpts.swapSuggestions?.length > 0 ? 'swap'
    : fixOpts.overbudgetDetail ? 'no_swap'
    : fixOpts.options?.length > 0 ? 'vlm'
    : null;

  const handleFixChoice = async (choiceId) => {
    if (!jobId) return;
    setSubmitting(true);
    try {
      await API.respondFixChoice(jobId, choiceId, selectedSwapIds);
      PipelineStore.dispatch({ type: 'HITL_SUBMIT' });
      setSelectedSwaps({});
    } catch (err) { console.error('fix-choice failed:', err); }
    setSubmitting(false);
  };

  const handleHitlSend = async () => {
    if (!jobId || !hitlAction.trim()) return;
    const action = hitlAction.trim();
    if (/swap/i.test(action)) {
      setSwapConfirm({ action, msg: `替換元件將重新執行 Phase II～VI，確定繼續？` });
      return;
    }
    setSubmitting(true);
    try {
      await API.sendHitl(jobId, action, {});
      PipelineStore.dispatch({ type: 'HITL_SUBMIT' });
      setHitlAction('');
    } catch (err) { console.error('HITL send failed:', err); }
    setSubmitting(false);
  };

  // 載入時讀取 job 的 saved 狀態
  React.useEffect(() => {
    if (!jobId) return;
    API.getJob(jobId)
      .then(j => setSavedToProjects(!!j.saved))
      .catch(() => {});
  }, [jobId]);

  const handleSaveProject = async () => {
    if (!jobId || savedToProjects) return;
    setSavingProject(true);
    try {
      await API.saveJob(jobId);
      setSavedToProjects(true);
    } catch (err) {
      console.error('save project failed:', err);
      alert(`儲存失敗：${err.message || err}`);
    }
    setSavingProject(false);
  };

  const handleSwapConfirmed = async () => {
    if (!swapConfirm || !jobId) return;
    setSubmitting(true);
    try {
      await API.sendHitl(jobId, swapConfirm.action, {});
      PipelineStore.dispatch({ type: 'HITL_SUBMIT' });
      setHitlAction('');
    } catch (err) { console.error('swap failed:', err); }
    setSwapConfirm(null);
    setSubmitting(false);
  };

  // Score ring values
  const scoreValue = project.printability ? Math.round(project.printability * 100) : null;
  const scoreFraction = scoreValue != null ? scoreValue / 100 : 0;
  const circumference = 2 * Math.PI * 36;
  const isDone = store?.status === 'done';
  const ringColor = isDone ? 'var(--green)' : 'var(--accent)';

  return (
    <div key="evaluate" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
        <div style={{ maxWidth: 920, margin: '0 auto', padding: '28px 32px' }}>
          {/* Header */}
          <div style={{ marginBottom: 28, animation: 'slideUp 0.4s var(--ease-out)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Badge color="var(--6e-evaluate)" bg="var(--red-dim)">Evaluate</Badge>
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>驗證改進 · Phase VI/VII</span>
            </div>
            <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 4 }}>設計驗證報告</h2>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              {project.name || '—'} · {project.iteration || 'v1.0'}
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 20 }}>
            {/* Left column — checks + fix cards + HITL */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {checkGroups.map((group, gi) => (
                <Card key={gi} style={{ overflow: 'hidden', animation: `slideUp 0.35s var(--ease-out) ${gi * 100}ms both` }}>
                  <div style={{
                    padding: '12px 18px', background: 'var(--bg-3)',
                    borderBottom: '1px solid var(--border-subtle)',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}>
                    <span style={{ fontSize: 13, fontWeight: 700 }}>{group.category}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                      {group.items.filter(i => i.status === 'pass').length}/{group.items.length} passed
                    </span>
                  </div>
                  {group.items.map((item, ii) => {
                    const myIdx = checkGroups.slice(0, gi).reduce((s, g) => s + g.items.length, 0) + ii;
                    const revealed = myIdx < revealIdx;
                    return (
                      <div key={ii} style={{
                        display: 'flex', alignItems: 'center', gap: 12,
                        padding: '12px 18px', borderBottom: '1px solid var(--border-subtle)',
                        opacity: revealed ? 1 : 0.3,
                        transition: 'opacity 0.3s var(--ease-out)',
                      }}>
                        <span style={{
                          width: 22, height: 22, borderRadius: 'var(--r-full)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 700, flexShrink: 0,
                          background: !revealed ? 'var(--bg-4)' : item.status === 'pass' ? 'var(--green-dim)' : item.status === 'warn' ? 'var(--accent-dim)' : 'var(--red-dim)',
                          color: !revealed ? 'var(--text-tertiary)' : item.status === 'pass' ? 'var(--green)' : item.status === 'warn' ? 'var(--accent)' : 'var(--red)',
                          transition: 'all 0.3s var(--ease-out)',
                          transform: revealed ? 'scale(1)' : 'scale(0.8)',
                        }}>
                          {revealed ? (item.status === 'pass' ? '✓' : item.status === 'warn' ? '!' : '✕') : '·'}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>{item.label}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>{item.detail}</div>
                        </div>
                      </div>
                    );
                  })}
                </Card>
              ))}

              {fixCardType === 'swap' && (
                <SwapFixCard
                  fixOpts={fixOpts}
                  submitting={submitting}
                  selectedSwaps={selectedSwaps}
                  selectedSwapIds={selectedSwapIds}
                  projectedTotal={projectedTotal}
                  budgetMa={budgetMa}
                  onToggleSwap={toggleSwap}
                  onConfirm={handleFixChoice}
                />
              )}

              {fixCardType === 'no_swap' && (
                <NoSwapFixCard fixOpts={fixOpts} submitting={submitting} onConfirm={handleFixChoice} />
              )}

              {fixCardType === 'vlm' && (
                <VlmFixCard
                  fixOpts={fixOpts}
                  submitting={submitting}
                  countdown={countdown}
                  extensions={extensions}
                  onConfirm={handleFixChoice}
                  onExtend={() => { setCountdown(prev => prev + 60); setExtensions(prev => prev + 1); }}
                />
              )}

              {/* HITL structured actions + free text */}
              {store?.status === 'waiting_hitl' && !fixOpts && (
                <Card style={{ overflow: 'hidden', animation: 'slideUp 0.4s var(--ease-out) 300ms both' }}>
                  <div style={{ padding: '12px 18px', background: 'var(--bg-3)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <SectionLabel>Human-in-the-Loop · 修正操作</SectionLabel>
                    <button onClick={handleAccept} disabled={submitting} style={{
                      padding: '6px 14px', borderRadius: 'var(--r-sm)',
                      background: 'var(--green)', border: 'none',
                      color: '#fff', fontSize: 11, fontWeight: 700,
                      cursor: 'pointer', fontFamily: 'var(--font-sans)',
                    }}>Accept ✓ 接受現狀</button>
                  </div>
                  <div style={{ padding: '14px 18px' }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
                      {[
                        { id: 'increase_wall_thickness', icon: '🧱', label: '加厚殼壁', desc: '+0.5mm' },
                        { id: 'decrease_wall_thickness', icon: '📏', label: '減薄殼壁', desc: '-0.5mm' },
                        { id: 'change_material', icon: '🔄', label: '換材料', desc: 'PLA↔PETG' },
                        { id: 'resize_enclosure', icon: '📐', label: '調整尺寸', desc: '外殼大小' },
                        { id: 'add_component', icon: '➕', label: '加入元件', desc: '新感測器' },
                        { id: 'replace_component', icon: '🔀', label: '替換元件', desc: '換型號' },
                      ].map(act => {
                        const sel = hitlAction === act.id;
                        return (
                          <button key={act.id}
                            onClick={() => setHitlAction(sel ? '' : act.id)}
                            style={{
                              padding: '10px 14px', borderRadius: 'var(--r-sm)',
                              background: sel ? 'var(--accent-dim)' : 'var(--bg-2)',
                              border: `1.5px solid ${sel ? 'var(--accent)' : 'var(--border-subtle)'}`,
                              color: sel ? 'var(--accent)' : 'var(--text-secondary)',
                              fontSize: 12, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                              minWidth: 90, transition: 'all 0.15s',
                            }}
                          >
                            <span style={{ fontSize: 18 }}>{act.icon}</span>
                            <span style={{ fontWeight: 600 }}>{act.label}</span>
                            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{act.desc}</span>
                          </button>
                        );
                      })}
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <input
                        value={hitlAction}
                        onChange={e => setHitlAction(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') handleHitlSend(); }}
                        placeholder="或輸入自訂指令⋯"
                        style={{
                          flex: 1, padding: '10px 14px', borderRadius: 'var(--r-sm)',
                          background: 'var(--bg-3)', border: '1px solid var(--border-default)',
                          color: 'var(--text-primary)', fontSize: 13, fontFamily: 'var(--font-sans)',
                          outline: 'none',
                        }}
                      />
                      <button onClick={handleHitlSend} disabled={submitting || !hitlAction.trim()} style={{
                        padding: '10px 20px', borderRadius: 'var(--r-sm)',
                        background: hitlAction.trim() ? 'var(--accent)' : 'var(--bg-4)',
                        border: 'none',
                        color: hitlAction.trim() ? 'var(--text-inverse)' : 'var(--text-tertiary)',
                        fontSize: 13, fontWeight: 600,
                        cursor: hitlAction.trim() ? 'pointer' : 'default',
                        fontFamily: 'var(--font-sans)', transition: 'all 0.15s',
                      }}>送出修正 →</button>
                    </div>
                  </div>
                </Card>
              )}
            </div>

            {/* Right column */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {/* Overall score — SVG ring (v5) with dynamic data (v4) */}
              <Card style={{ padding: '20px', textAlign: 'center', animation: 'scaleIn 0.4s var(--ease-out) 600ms both' }}>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>OVERALL SCORE</div>
                <div style={{ position: 'relative', width: 80, height: 80, margin: '0 auto 12px' }}>
                  <svg width="80" height="80" style={{ transform: 'rotate(-90deg)' }}>
                    <circle cx="40" cy="40" r="36" fill="none" stroke="var(--bg-4)" strokeWidth="4" />
                    <circle cx="40" cy="40" r="36" fill="none" stroke={ringColor} strokeWidth="4"
                      strokeDasharray={`${circumference}`}
                      strokeDashoffset={`${circumference * (1 - scoreFraction)}`}
                      strokeLinecap="round"
                      style={{ transition: 'stroke-dashoffset 1s var(--ease-out) 0.8s' }}
                    />
                  </svg>
                  <span style={{
                    position: 'absolute', inset: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 26, fontWeight: 700, color: ringColor, fontFamily: 'var(--font-mono)',
                  }}>{scoreValue ?? '—'}</span>
                </div>
                <div style={{
                  fontSize: 12, fontWeight: 600,
                  color: isDone ? 'var(--green)' : 'var(--text-secondary)',
                }}>{isDone ? 'PASS · Ready to print' : 'Evaluating...'}</div>

                {/* 儲存到專案 — 僅 SUCCESS 顯示 */}
                {isDone && jobId && (
                  <button
                    onClick={handleSaveProject}
                    disabled={savedToProjects || savingProject}
                    style={{
                      marginTop: 14, width: '100%',
                      padding: '10px 16px', borderRadius: 'var(--r-sm)',
                      background: savedToProjects ? 'var(--green-dim)' : 'var(--accent)',
                      border: 'none',
                      color: savedToProjects ? 'var(--green)' : '#0a0a0a',
                      fontSize: 13, fontWeight: 700,
                      cursor: savedToProjects ? 'default' : 'pointer',
                      fontFamily: 'var(--font-sans)',
                      transition: 'all 0.2s var(--ease-out)',
                    }}
                  >
                    {savedToProjects ? '✓ 已儲存到專案' : savingProject ? '儲存中…' : '💾 儲存到專案'}
                  </button>
                )}
              </Card>

              {/* Resume from Phase — only when done, not canned, has jobId */}
              {isDone && jobId && !store?.isCanned && onResumePipeline && (
                <ResumePhaseCard jobId={jobId} currentPhase={store?.currentPhase || 5} onResume={onResumePipeline} />
              )}

              {/* STEM Rubrics */}
              <Card style={{ padding: '16px 18px', animation: 'slideUp 0.4s var(--ease-out) 700ms both' }}>
                <SectionLabel style={{ marginBottom: 12 }}>STEM Capability</SectionLabel>
                {rubrics.length > 0 ? rubrics.map((r, i) => (
                  <div key={i} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                      <span style={{ color: 'var(--text-secondary)' }}>{r.name}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary)', fontWeight: 600 }}>{r.score}</span>
                    </div>
                    <ProgressBar value={r.score} max={r.max} color="var(--accent-2)" />
                  </div>
                )) : (
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>完成 Pipeline 後自動評分</div>
                )}
              </Card>

              {/* ED3: Student Self-Reflection */}
              <Card style={{ padding: '16px 18px', animation: 'slideUp 0.4s var(--ease-out) 750ms both' }}>
                <SectionLabel style={{ marginBottom: 12 }}>學生反思 · Self-Reflection</SectionLabel>
                {[
                  { key: 'what_learned', prompt: '我在這個專案中學到了什麼？', placeholder: '例：我學會了如何用感測器偵測環境變化…' },
                  { key: 'what_improve', prompt: '如果重做一次，我會怎麼改進？', placeholder: '例：我會選擇更省電的元件…' },
                  { key: 'real_world', prompt: '這個設計在真實世界可以怎麼應用？', placeholder: '例：可以用在教室自動澆花…' },
                ].map((q, i) => (
                  <div key={q.key} style={{ marginBottom: i < 2 ? 12 : 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>{q.prompt}</div>
                    <textarea
                      rows={2}
                      placeholder={q.placeholder}
                      onChange={e => {
                        const val = e.target.value;
                        PipelineStore.dispatch({ type: 'SET_REFLECTION', key: q.key, value: val });
                      }}
                      defaultValue={(store?.reflections || {})[q.key] || ''}
                      style={{
                        width: '100%', padding: '8px 10px', borderRadius: 'var(--r-sm)',
                        background: 'var(--bg-3)', border: '1px solid var(--border-default)',
                        color: 'var(--text-primary)', fontSize: 12, fontFamily: 'var(--font-sans)',
                        resize: 'vertical', outline: 'none', lineHeight: 1.5,
                      }}
                    />
                  </div>
                ))}
              </Card>

              {/* Iteration history */}
              <Card style={{ padding: '16px 18px', animation: 'slideUp 0.4s var(--ease-out) 800ms both' }}>
                <SectionLabel style={{ marginBottom: 12 }}>Iteration History</SectionLabel>
                {hitlHistory.length > 0 ? hitlHistory.map((h, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 0', borderBottom: i < hitlHistory.length - 1 ? '1px solid var(--border-subtle)' : 'none',
                  }}>
                    <span style={{
                      fontSize: 11, fontWeight: 700, fontFamily: 'var(--font-mono)',
                      color: 'var(--text-tertiary)', minWidth: 36,
                    }}>v{i + 1}.0</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{h.action || h.note || JSON.stringify(h)}</div>
                    </div>
                  </div>
                )) : (
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>尚無迭代記錄</div>
                )}
              </Card>
            </div>
          </div>

          {/* Swap confirmation dialog */}
          {swapConfirm && (
            <div style={{
              position: 'fixed', inset: 0, zIndex: 2000,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
            }}>
              <Card style={{ maxWidth: 420, padding: '28px 32px', textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 12, color: 'var(--accent)' }}>⚠ 元件替換確認</div>
                <div style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 24 }}>{swapConfirm.msg}</div>
                <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
                  <button onClick={() => setSwapConfirm(null)} style={{
                    padding: '10px 24px', borderRadius: 'var(--r-sm)',
                    background: 'var(--bg-3)', border: '1px solid var(--border-default)',
                    color: 'var(--text-secondary)', fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  }}>取消</button>
                  <button onClick={handleSwapConfirmed} disabled={submitting} style={{
                    padding: '10px 24px', borderRadius: 'var(--r-sm)',
                    background: 'var(--red)', border: 'none',
                    color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-sans)',
                  }}>確認替換</button>
                </div>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { EvaluateView });
