// ═══════════════════════════════════════════
// views-user-components.jsx — U5: 用戶自填元件表單
// Sub-components: user-components/tag-pickers.jsx (INF1-S22)
// ═══════════════════════════════════════════

const COMPONENT_PRESETS = window.COMPONENT_PRESETS;
const Tip = window.Tip;
const Axis1Picker = window.Axis1Picker;
const Axis2Editor = window.Axis2Editor;
const PresetPicker = window.PresetPicker;
const TAG_AXIS2_PREFIXES = window.TAG_AXIS2_PREFIXES;

// ── List View ───────────────────────────────

function UserComponentsView() {
  const [components, setComponents] = React.useState({});
  const [loading, setLoading] = React.useState(true);
  const [showForm, setShowForm] = React.useState(false);
  const [editTarget, setEditTarget] = React.useState(null);

  const refresh = () => {
    setLoading(true);
    API.listUserComponents()
      .then(r => setComponents(r.components || {}))
      .catch(err => console.warn('[UserComponents] load failed:', err))
      .finally(() => setLoading(false));
  };

  React.useEffect(refresh, []);

  const handleDelete = (cn) => {
    if (!confirm(`確定刪除 ${cn}？`)) return;
    API.deleteUserComponent(cn).then(refresh);
  };

  const handleSaved = () => {
    setShowForm(false);
    setEditTarget(null);
    refresh();
  };

  const entries = Object.entries(components);

  return (
    <div key="user-components" style={{ position: 'absolute', inset: 0, animation: 'viewFadeIn 0.35s var(--ease-out) forwards' }}>
      <div style={{ position: 'absolute', inset: 0, overflow: 'auto' }}>
        <div style={{ maxWidth: 800, margin: '0 auto', padding: '36px 32px' }}>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
            <div>
              <Badge>U5</Badge>
              <h2 style={{ margin: '8px 0 4px', fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>
                我的元件
              </h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: 0 }}>
                Pipeline 未收錄的元件可在此登記，供後續專案使用
              </p>
            </div>
            <button
              onClick={() => { setEditTarget(null); setShowForm(true); }}
              style={{
                background: 'var(--accent)', color: '#fff', border: 'none',
                borderRadius: 'var(--r-sm)', padding: '8px 18px', fontSize: 13,
                fontWeight: 600, cursor: 'pointer',
              }}
            >+ 新增元件</button>
          </div>

          {loading && <p style={{ color: 'var(--text-secondary)' }}>載入中…</p>}

          {!loading && entries.length === 0 && (
            <Card style={{ padding: '32px 24px', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
                尚無自填元件。點擊 <strong>+ 新增元件</strong> 開始登記。
              </p>
            </Card>
          )}

          {entries.map(([cn, info]) => (
            <Card key={cn} style={{ padding: '16px 20px', marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <strong style={{ color: 'var(--text-primary)', fontSize: 14 }}>{info.name}</strong>
                  <span style={{ color: 'var(--text-secondary)', fontSize: 12, marginLeft: 8 }}>{cn}</span>
                  <div style={{ marginTop: 4, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {(info.tags || []).map(t => (
                      <Badge key={t} bg="var(--bg-3)" style={{ fontSize: 10 }}>{t}</Badge>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => handleDelete(cn)} style={{
                    background: 'none', border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--r-sm)', padding: '4px 10px', fontSize: 12,
                    color: 'var(--red)', cursor: 'pointer',
                  }}>刪除</button>
                </div>
              </div>
            </Card>
          ))}

          {showForm && (
            <UserComponentForm
              editTarget={editTarget}
              onSave={handleSaved}
              onCancel={() => { setShowForm(false); setEditTarget(null); }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Form styles (module-scope) ───────────────

const _formInputStyle = {
  background: 'var(--bg-3)', border: '1px solid var(--border-subtle)',
  borderRadius: 'var(--r-sm)', padding: '6px 10px', fontSize: 13,
  color: 'var(--text-primary)', outline: 'none', width: '100%',
};

const _formLabelStyle = { fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' };

// ── Form (Modal) ────────────────────────────

function UserComponentForm({ editTarget, onSave, onCancel }) {
  const [name, setName] = React.useState('');
  const [className, setClassName] = React.useState('');
  const [length, setLength] = React.useState('');
  const [width, setWidth] = React.useState('');
  const [height, setHeight] = React.useState('');
  const [voltage, setVoltage] = React.useState('5.0');
  const [current, setCurrent] = React.useState('50');
  const [axis1, setAxis1] = React.useState('');
  const [axis2Tags, setAxis2Tags] = React.useState([]);
  const [ports, setPorts] = React.useState([]);
  const [enclosureRelation, setEnclosureRelation] = React.useState('external');
  const [error, setError] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  const autoClassName = (n) => {
    const slug = n.trim().replace(/[^a-zA-Z0-9]+/g, '-').replace(/-+$/, '');
    return slug ? `User-${slug}-class` : '';
  };

  const handleNameChange = (v) => {
    setName(v);
    if (!editTarget) setClassName(autoClassName(v));
  };

  const applyPreset = (preset) => {
    setAxis1(preset.axis1);
    setAxis2Tags([...preset.axis2]);
    setVoltage(preset.voltage);
    setCurrent(preset.current);
  };

  const addPort = () => {
    setPorts([...ports, { label: '', side: 'face', x: 0, y: 0, w: 3, h: 3 }]);
  };

  const updatePort = (i, field, val) => {
    const next = [...ports];
    next[i] = { ...next[i], [field]: val };
    setPorts(next);
  };

  const removePort = (i) => {
    setPorts(ports.filter((_, idx) => idx !== i));
  };

  const handleSubmit = async () => {
    setError('');
    if (!name.trim()) return setError('名稱必填');
    if (!className.trim()) return setError('Class name 必填');
    const L = parseFloat(length), W = parseFloat(width), H = parseFloat(height);
    if (!(L > 0) || !(W > 0) || !(H > 0)) return setError('長 / 寬 / 高 必須 > 0');
    if (!axis1) return setError('請選擇一個介面類型');
    if (axis2Tags.length === 0) return setError('請至少加入一個功能標籤');

    const tags = [axis1, ...axis2Tags];

    setSaving(true);
    try {
      await API.addUserComponent({
        name: name.trim(),
        class_name: className.trim(),
        length_mm: L, width_mm: W, height_mm: H,
        voltage_v: parseFloat(voltage) || 5.0,
        current_ma: parseFloat(current) || 50,
        enclosure_relation: enclosureRelation,
        tags,
        connector_ports: ports.map(p => ({
          label: p.label, side: p.side,
          x: parseFloat(p.x) || 0, y: parseFloat(p.y) || 0,
          w: parseFloat(p.w) || 3, h: parseFloat(p.h) || 3,
        })),
      });
      onSave();
    } catch (e) {
      setError(e.detail || e.message);
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = _formInputStyle;
  const labelStyle = _formLabelStyle;

  const SIDE_LABELS = { left: '左', right: '右', top: '上', bottom: '下', face: '正面' };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <Card style={{ padding: '24px 28px', width: 580, maxHeight: '85vh', overflow: 'auto' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 17, color: 'var(--text-primary)' }}>
          {editTarget ? '編輯元件' : '新增元件'}
        </h3>

        {/* 快速預設 */}
        {!editTarget && <PresetPicker onApply={applyPreset} />}

        {/* 名稱 + Class Name */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>名稱 *</label>
            <input style={inputStyle} value={name} onChange={e => handleNameChange(e.target.value)} placeholder="例：BH1750 光感測器" />
          </div>
          <div>
            <label style={labelStyle}>Class Name <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>（自動產生）</span></label>
            <input
              style={{ ...inputStyle, background: 'var(--bg-2)', color: 'var(--text-tertiary)', cursor: 'default' }}
              value={className}
              readOnly
              tabIndex={-1}
            />
          </div>
        </div>

        {/* 尺寸 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 12 }}>
          <div>
            <label style={labelStyle}>長度 (mm) *</label>
            <input style={inputStyle} type="number" value={length} onChange={e => setLength(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>寬度 (mm) *</label>
            <input style={inputStyle} type="number" value={width} onChange={e => setWidth(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>高度 (mm) *</label>
            <input style={inputStyle} type="number" value={height} onChange={e => setHeight(e.target.value)} />
          </div>
        </div>

        {/* 電氣 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>電壓 (V)</label>
            <input style={inputStyle} type="number" value={voltage} onChange={e => setVoltage(e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>電流 (mA)</label>
            <input style={inputStyle} type="number" value={current} onChange={e => setCurrent(e.target.value)} />
          </div>
        </div>

        {/* Axis 1 介面 */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ ...labelStyle, marginBottom: 8 }}>介面類型 * <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>— 元件與主控板的連線方式（hover 看說明）</span></label>
          <Axis1Picker selected={axis1} onChange={setAxis1} />
        </div>

        {/* Axis 2 功能 */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ ...labelStyle, marginBottom: 8 }}>功能標籤 * <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>— 選擇分類後輸入具體功能</span></label>
          <Axis2Editor tags={axis2Tags} onChange={setAxis2Tags} />
        </div>

        {/* Connector Ports */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <label style={{ ...labelStyle, margin: 0 }}>接口定義</label>
            <button type="button" onClick={addPort} style={{
              background: 'var(--bg-3)', border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)', padding: '2px 10px', fontSize: 11,
              color: 'var(--text-secondary)', cursor: 'pointer',
            }}>+ 接口</button>
          </div>
          <div style={{ marginBottom: 8 }}>
            <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4, display: 'block' }}>外殼關係 (enclosure_relation)</label>
            <select style={{ ...inputStyle, width: 160 }} value={enclosureRelation} onChange={e => setEnclosureRelation(e.target.value)}>
              <option value="internal">internal — 完全包覆</option>
              <option value="breadboard">breadboard — 主板內嵌</option>
              <option value="panel">panel — 面板開窗</option>
              <option value="external">external — 外部連線</option>
              <option value="embedded">embedded — 結構嵌入</option>
            </select>
          </div>
          {ports.map((p, i) => (
            <div key={i} style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 6 }}>
              <input style={{ ...inputStyle, width: 70 }} placeholder="名稱" value={p.label} onChange={e => updatePort(i, 'label', e.target.value)} />
              <select style={{ ...inputStyle, width: 70 }} value={p.side} onChange={e => updatePort(i, 'side', e.target.value)}>
                {Object.entries(SIDE_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <input style={{ ...inputStyle, width: 44 }} type="number" placeholder="x" value={p.x} onChange={e => updatePort(i, 'x', e.target.value)} />
              <input style={{ ...inputStyle, width: 44 }} type="number" placeholder="y" value={p.y} onChange={e => updatePort(i, 'y', e.target.value)} />
              <input style={{ ...inputStyle, width: 44 }} type="number" placeholder="w" value={p.w} onChange={e => updatePort(i, 'w', e.target.value)} />
              <input style={{ ...inputStyle, width: 44 }} type="number" placeholder="h" value={p.h} onChange={e => updatePort(i, 'h', e.target.value)} />
              <button type="button" onClick={() => removePort(i)} style={{
                background: 'none', border: 'none', color: 'var(--red)',
                cursor: 'pointer', fontSize: 16, padding: '0 4px',
              }}>&times;</button>
            </div>
          ))}
        </div>

        {error && <p style={{ color: 'var(--red)', fontSize: 12, margin: '0 0 12px' }}>{error}</p>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" onClick={onCancel} style={{
            background: 'var(--bg-3)', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-sm)', padding: '8px 16px', fontSize: 13,
            color: 'var(--text-secondary)', cursor: 'pointer',
          }}>取消</button>
          <button type="button" onClick={handleSubmit} disabled={saving} style={{
            background: 'var(--accent)', color: '#fff', border: 'none',
            borderRadius: 'var(--r-sm)', padding: '8px 18px', fontSize: 13,
            fontWeight: 600, cursor: 'pointer', opacity: saving ? 0.6 : 1,
          }}>{saving ? '儲存中…' : '儲存'}</button>
        </div>
      </Card>
    </div>
  );
}

Object.assign(window, { UserComponentsView });
