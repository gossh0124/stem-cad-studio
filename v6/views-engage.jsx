// ═══════════════════════════════════════════
// views-engage.jsx — v6: Category Explorer + Challenge Preview
// ═══════════════════════════════════════════

function IdleView({ onNavigate, _onSubmit, onStartPipeline, _store }) {
  const [prompt, setPrompt] = React.useState('');
  const [inputFocused, setInputFocused] = React.useState(false);
  const [recentProjects, setRecentProjects] = React.useState([]);
  const [backendOk, setBackendOk] = React.useState(null);
  const [selectedCat, setSelectedCat] = React.useState(null);
  const [selectedTpl, setSelectedTpl] = React.useState(null);
  const [freeInput, setFreeInput] = React.useState(false);

  const catalog = window.CHALLENGE_CATALOG || {};
  const catKeys = Object.keys(catalog);

  React.useEffect(() => {
    API.getComponents()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
    API.listJobs(null, 5, true)
      .then(jobs => {
        if (Array.isArray(jobs)) {
          setRecentProjects(jobs.slice(0, 3).map(j => ({
            name: j.project_name || '未命名',
            id: j.job_id?.slice(0, 12) || '',
            status: 'done',
            phase: 'SAVED',
            pct: 100,
            date: j.updated_at ? new Date(j.updated_at * 1000).toLocaleDateString('zh-TW', { month: '2-digit', day: '2-digit' }) : '',
          })));
        }
      })
      .catch(() => {});
  }, []);

  const handleGo = (text) => {
    const v = text || prompt;
    if (!v.trim()) return;
    if (onStartPipeline) onStartPipeline(v.slice(0, 30), v);
  };

  const handleSelectCat = (key) => {
    setSelectedCat(selectedCat === key ? null : key);
    setSelectedTpl(null);
  };

  const handleSelectTpl = (tpl) => {
    setSelectedTpl(selectedTpl === tpl ? null : tpl);
  };

  const handleTplGo = async (tpl) => {
    // 範本若有 canned_bridge → 載入 demo 模式（不跑 LLM）
    if (tpl.canned_bridge) {
      try {
        const resp = await fetch(`/canned/${tpl.canned_bridge}.json`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const bridge = await resp.json();
        PipelineStore.dispatch({
          type: 'LOAD_CANNED', bridge, templateId: tpl.canned_bridge,
        });
        // 從 6E 第一個內容階段（Clarify）開始，讓用戶逐步瀏覽各階段選擇
        if (onNavigate) onNavigate('clarify');
        return;
      } catch (err) {
        console.error('canned bridge 載入失敗:', err);
        document.dispatchEvent(new CustomEvent('cadhllm:toast',
          { detail: `Demo 模式載入失敗：${err.message}，改用即時 pipeline` }));
      }
    }
    handleGo(tpl.prompt);
  };

  const showCatalog = !freeInput;

  return (
    <div key="idle" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{
        position: 'absolute', inset: 0, overflow: 'auto',
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        padding: '48px 40px 40px',
      }}>
        {/* Hero */}
        <div style={{ textAlign: 'center', maxWidth: 680, marginBottom: 32, animation: 'slideUp 0.5s var(--ease-out)' }}>
          <div style={{
            fontSize: 11, fontWeight: 600, letterSpacing: '3px', color: 'var(--accent)',
            marginBottom: 14, textTransform: 'uppercase',
          }}>
            · Atelier ·
          </div>
          <h1 style={{
            fontSize: 36, fontWeight: 700, lineHeight: 1.35,
            color: 'var(--text-primary)', marginBottom: 14,
            textWrap: 'balance',
          }}>
            用一句話，把想法<br />變成 3D 列印作品。
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            選擇一個主題探索工程挑戰，或直接描述你的想法
          </p>
          {backendOk === false && (
            <div style={{ marginTop: 12, padding: '8px 16px', borderRadius: 'var(--r-sm)', background: 'var(--red-dim)', color: 'var(--red)', fontSize: 12 }}>
              Backend 無法連線 · 請確認伺服器已啟動
            </div>
          )}
        </div>

        {/* Mode toggle */}
        <div style={{
          display: 'flex', gap: 16, marginBottom: 24, animation: 'slideUp 0.55s var(--ease-out)',
        }}>
          <ModeTab active={showCatalog} onClick={() => { setFreeInput(false); }}>探索主題</ModeTab>
          <ModeTab active={freeInput} onClick={() => { setFreeInput(true); setSelectedCat(null); setSelectedTpl(null); }}>自由輸入</ModeTab>
        </div>

        {/* Free input mode */}
        {freeInput && (
          <div style={{ width: '100%', maxWidth: 620, marginBottom: 40, animation: 'slideUp 0.3s var(--ease-out)' }}>
            <div style={{
              background: 'var(--bg-2)',
              border: `1px solid ${inputFocused ? 'var(--border-strong)' : 'var(--border-default)'}`,
              borderRadius: 'var(--r-lg)', padding: '4px 4px 4px 20px',
              display: 'flex', alignItems: 'center', gap: 8,
              boxShadow: inputFocused ? '0 0 0 4px rgba(255,255,255,0.03), var(--shadow-md)' : 'var(--shadow-md)',
              transition: 'border-color 0.2s, box-shadow 0.2s',
            }}>
              <input
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleGo(); }}
                onFocus={() => setInputFocused(true)}
                onBlur={() => setInputFocused(false)}
                placeholder="描述你想做的硬體專案⋯"
                autoFocus
                style={{
                  flex: 1, background: 'transparent', border: 'none', outline: 'none',
                  color: 'var(--text-primary)', fontSize: 15, fontFamily: 'var(--font-sans)',
                  padding: '14px 0',
                }}
              />
              <button
                onClick={() => handleGo()}
                style={{
                  padding: '12px 24px', borderRadius: 'var(--r-md)',
                  background: prompt.trim() ? 'var(--accent)' : 'var(--bg-4)',
                  border: 'none',
                  color: prompt.trim() ? 'var(--text-inverse)' : 'var(--text-tertiary)',
                  fontSize: 14, fontWeight: 700, cursor: prompt.trim() ? 'pointer' : 'default',
                  fontFamily: 'var(--font-sans)', flexShrink: 0,
                  transition: 'all 0.2s var(--ease-out)',
                }}
              >開始設計 →</button>
            </div>
          </div>
        )}

        {/* Category Explorer */}
        {showCatalog && (
          <div style={{ maxWidth: 760, width: '100%', animation: 'slideUp 0.6s var(--ease-out)' }}>
            {/* Category Grid — 3 cols × 2 rows for 6 categories（2026-05-08 改 4-2 → 3-3 對稱） */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 10, marginBottom: 24,
            }}>
              {catKeys.map((key, i) => {
                const cat = catalog[key];
                const active = selectedCat === key;
                return (
                  <CategoryCard
                    key={key}
                    icon={cat.icon}
                    label={cat.label}
                    count={cat.templates.length}
                    active={active}
                    delay={i * 40}
                    onClick={() => handleSelectCat(key)}
                  />
                );
              })}
            </div>

            {/* Template Cards (expanded category) */}
            {selectedCat && catalog[selectedCat] && (
              <div style={{ marginBottom: 24, animation: 'slideUp 0.25s var(--ease-out)' }}>
                <SectionLabel style={{ marginBottom: 12 }}>
                  {catalog[selectedCat].icon} {catalog[selectedCat].label} — 專案範本
                </SectionLabel>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 10 }}>
                  {catalog[selectedCat].templates.map((tpl, i) => (
                    <TemplateCard
                      key={i}
                      tpl={tpl}
                      active={selectedTpl === tpl}
                      onClick={() => handleSelectTpl(tpl)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Challenge Preview (selected template) */}
            {selectedTpl && (
              <div style={{ marginBottom: 32, animation: 'slideUp 0.25s var(--ease-out)' }}>
                <SectionLabel style={{ marginBottom: 12 }}>
                  工程挑戰預覽 — {selectedTpl.name}
                </SectionLabel>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
                  {selectedTpl.challenges.map((ch, i) => (
                    <ChallengeCard key={i} ch={ch} delay={i * 60} />
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <button
                    onClick={() => handleTplGo(selectedTpl)}
                    style={{
                      padding: '12px 28px', borderRadius: 'var(--r-md)',
                      background: 'var(--accent)', border: 'none',
                      color: 'var(--text-inverse)', fontSize: 14, fontWeight: 700,
                      cursor: 'pointer', fontFamily: 'var(--font-sans)',
                      transition: 'all 0.2s var(--ease-out)',
                    }}
                  >{selectedTpl.canned_bridge ? '檢視範本' : '開始設計'}「{selectedTpl.name}」→</button>
                  <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
                    {selectedTpl.components} 個元件 · 難度 {'★'.repeat(selectedTpl.difficulty)}{'☆'.repeat(3 - selectedTpl.difficulty)}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Recent projects */}
        {recentProjects.length > 0 && (
          <div style={{ maxWidth: 720, width: '100%', marginTop: 16, animation: 'slideUp 0.75s var(--ease-out)' }}>
            <SectionLabel style={{ marginBottom: 12 }}>近期專案</SectionLabel>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {recentProjects.map((p, i) => (
                <Card key={i} hover onClick={() => {
                  const phaseNum = parseInt((p.phase || '').replace('P', ''));
                  const viewByPhase = { 1: 'clarify', 2: 'extract', 3: 'plan', 4: 'components-3d', 5: 'code', 6: 'evaluate', 7: 'evaluate' };
                  const target = p.status === 'done' ? 'evaluate' : p.status === 'error' ? 'idle' : viewByPhase[phaseNum] || 'plan';
                  onNavigate(target);
                }} style={{ padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{p.id}</span>
                    <Badge color={p.status === 'wip' ? 'var(--accent)' : p.status === 'done' ? 'var(--green)' : 'var(--text-tertiary)'}
                      bg={p.status === 'wip' ? 'var(--accent-dim)' : p.status === 'done' ? 'var(--green-dim)' : 'var(--bg-3)'}>
                      {p.phase}
                    </Badge>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{p.name}</div>
                  <ProgressBar value={p.pct} max={100} color={p.status === 'done' ? 'var(--green)' : 'var(--accent)'} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{p.date}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>{p.pct}%</span>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function ModeTab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 20px', borderRadius: 'var(--r-md)',
        background: active ? 'var(--accent-dim)' : 'transparent',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border-subtle)'}`,
        color: active ? 'var(--accent)' : 'var(--text-secondary)',
        fontSize: 13, fontWeight: 600, cursor: 'pointer',
        fontFamily: 'var(--font-sans)',
        transition: 'all 0.2s var(--ease-out)',
      }}
    >{children}</button>
  );
}

function CategoryCard({ icon, label, count, active, delay, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
        padding: '20px 12px', borderRadius: 'var(--r-md)',
        background: active ? 'var(--accent-dim)' : 'var(--bg-2)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border-subtle)'}`,
        cursor: 'pointer', fontFamily: 'var(--font-sans)',
        transition: 'all 0.2s var(--ease-out)',
        animation: `chipStagger 0.4s var(--ease-out) ${delay}ms both`,
      }}
    >
      <span style={{ fontSize: 28 }}>{icon}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text-primary)' }}>{label}</span>
      <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{count} 個範本</span>
    </button>
  );
}

function TemplateCard({ tpl, active, onClick }) {
  const isLayer4 = tpl.scope === 'layer4';
  return (
    <button
      onClick={onClick}
      title={isLayer4 ? `Layer 4 預覽：${tpl.scope_note || '超出當前 CAD 生成 scope，可能降級執行'}` : ''}
      style={{
        textAlign: 'left', padding: '16px 18px', borderRadius: 'var(--r-md)',
        background: active ? 'var(--accent-dim)' : 'var(--bg-2)',
        border: `1px solid ${active ? 'var(--accent)' : 'var(--border-subtle)'}`,
        cursor: 'pointer', fontFamily: 'var(--font-sans)',
        transition: 'all 0.2s var(--ease-out)',
        opacity: isLayer4 ? 0.72 : 1,
        position: 'relative',
      }}
    >
      {isLayer4 && (
        <span style={{
          position: 'absolute', top: 6, right: 6,
          fontSize: 9, padding: '1px 6px', borderRadius: 'var(--r-sm)',
          background: 'rgba(255,170,0,0.18)', color: '#ffaa00',
          fontWeight: 700, letterSpacing: 0.3,
          border: '1px solid rgba(255,170,0,0.35)',
        }}>L4 預覽</span>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 14, fontWeight: 600, color: active ? 'var(--accent)' : 'var(--text-primary)' }}>{tpl.name}</span>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
          {'★'.repeat(tpl.difficulty)}{'☆'.repeat(3 - tpl.difficulty)}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {tpl.challenges.map((ch, i) => (
          <span key={i} style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 'var(--r-sm)',
            background: 'var(--bg-4)', color: 'var(--text-secondary)',
          }}>{ch.icon} {ch.label}</span>
        ))}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8 }}>
        {tpl.components} 個元件
      </div>
    </button>
  );
}

function ChallengeCard({ ch, delay }) {
  return (
    <div
      style={{
        padding: '16px 18px', borderRadius: 'var(--r-md)',
        background: 'var(--bg-2)',
        border: '1px solid var(--border-subtle)',
        transition: 'all 0.2s var(--ease-out)',
        animation: `chipStagger 0.35s var(--ease-out) ${delay}ms both`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 20 }}>{ch.icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{ch.label}</span>
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>{ch.preview}</p>
    </div>
  );
}

Object.assign(window, { IdleView });
