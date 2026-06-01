// ═══════════════════════════════════════════
// viewport-controls.js — Camera orbit presets, ViewCube, ViewControls
// Split from views-engineer.jsx (INF1-S3)
// ═══════════════════════════════════════════

(() => {
  // ─── 投影立方體共用工具 ─────────────────

  function buildBoxFaces(cx, cy, cz, l, w, h, project) {
    const hw = l / 2, hh = h / 2, hd = w / 2;
    const verts = [
      [cx-hw, cy-hh, cz-hd], [cx+hw, cy-hh, cz-hd], [cx+hw, cy-hh, cz+hd], [cx-hw, cy-hh, cz+hd],
      [cx-hw, cy+hh, cz-hd], [cx+hw, cy+hh, cz-hd], [cx+hw, cy+hh, cz+hd], [cx-hw, cy+hh, cz+hd],
    ];
    const projected = verts.map(([x, y, z]) => project(x, y, z));
    const faceDef = [
      { v: [0,1,2,3], label: 'Bottom', n: 'b' },
      { v: [4,5,6,7], label: 'Top', n: 't' },
      { v: [0,1,5,4], label: 'Front', n: 'f' },
      { v: [2,3,7,6], label: 'Back', n: 'k' },
      { v: [0,3,7,4], label: 'Left', n: 'l' },
      { v: [1,2,6,5], label: 'Right', n: 'r' },
    ];
    const faces = faceDef.map(f => {
      const pts = f.v.map(i => projected[i]);
      const ax = pts[1][0]-pts[0][0], ay = pts[1][1]-pts[0][1];
      const bx = pts[2][0]-pts[0][0], by = pts[2][1]-pts[0][1];
      const visible = (ax*by - ay*bx) > 0;
      const avgZ = f.v.reduce((s,i) => s + verts[i][2], 0) / 4;
      return { ...f, pts, visible, avgZ };
    }).filter(f => f.visible).sort((a, b) => a.avgZ - b.avgZ);
    return { verts, projected, faces };
  }

  // ─── 六視圖 ViewCube（Fusion 360 風格） ─────────────────

  const VIEW_PRESETS = [
    { id: 'front',  label: '前', ry: 0,   rx: 0   },
    { id: 'back',   label: '後', ry: 180, rx: 0   },
    { id: 'left',   label: '左', ry: -90, rx: 0   },
    { id: 'right',  label: '右', ry: 90,  rx: 0   },
    { id: 'top',    label: '上', ry: 0,   rx: 90  },
    { id: 'bottom', label: '下', ry: 0,   rx: -90 },
    { id: 'iso',    label: '3D', ry: 35,  rx: 25  },
  ];

  function ViewCube({ setView }) {
    return (
      <div
        onPointerDown={e => e.stopPropagation()}
        style={{
          position: 'absolute', bottom: 12, right: 12,
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 3,
          background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)', padding: 6,
          backdropFilter: 'blur(8px)', zIndex: 2,
        }}
      >
        {VIEW_PRESETS.map(v => (
          <button
            key={v.id}
            onClick={() => setView(v.ry, v.rx)}
            title={v.id}
            style={{
              width: 32, height: 28, borderRadius: 'var(--r-xs)',
              background: 'var(--bg-2)', border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)', fontSize: 11, fontWeight: 600,
              cursor: 'pointer', fontFamily: 'var(--font-sans)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.12s',
            }}
            onMouseEnter={e => { e.target.style.background = 'var(--accent-dim)'; e.target.style.color = 'var(--accent)'; }}
            onMouseLeave={e => { e.target.style.background = 'var(--bg-2)'; e.target.style.color = 'var(--text-secondary)'; }}
          >
            {v.label}
          </button>
        ))}
      </div>
    );
  }

  // ─── 控制按鈕 / 角度顯示 ─────────────────

  function ViewControls({ rotY, rotX, autoRotate, onAutoToggle, extra }) {
    return (
      // stopPropagation: 否則按鈕 pointerdown 冒泡到 viewport onPointerDown→setAutoRotate(false),
      // 接著 onClick !false=true → Auto 按了等於沒關(ViewCube 已有此防護,此處原本缺)
      <div onPointerDown={e => e.stopPropagation()} style={{ position: 'absolute', top: 12, right: 12, display: 'flex', gap: 6, zIndex: 2 }}>
        {extra}
        <button onClick={onAutoToggle} style={{
          padding: '6px 12px', borderRadius: 'var(--r-sm)',
          background: 'var(--bg-glass)', border: '1px solid var(--border-default)',
          color: autoRotate ? 'var(--green)' : 'var(--text-tertiary)',
          fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-sans)',
          backdropFilter: 'blur(8px)', transition: 'all 0.15s',
        }}>{autoRotate ? '⏸ Auto' : '▶ Auto'}</button>
        <div style={{
          padding: '6px 10px', borderRadius: 'var(--r-sm)',
          background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)',
          fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)',
          backdropFilter: 'blur(8px)',
        }}>θ {Math.round(rotY % 360)}° / {Math.round(rotX)}°</div>
      </div>
    );
  }

  // ─── Code syntax highlighting utilities ─────────────────

  function _escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function _highlight(line, lang) {
    let s = _escapeHtml(line);
    const slots = [];
    const stash = (html) => { slots.push(html); return '⎇' + (slots.length - 1) + '⎇'; };
    if (lang === 'python') {
      s = s.replace(/(#.*)$/g, m => stash(`<span style="color:#5c6e80;font-style:italic">${m}</span>`));
      s = s.replace(/(&#39;[^&#]*&#39;|'[^']*')/g, m => stash(`<span style="color:#f8b878">${m}</span>`));
      s = s.replace(/(&quot;[^&]*&quot;|"[^"]*")/g, m => stash(`<span style="color:#f8b878">${m}</span>`));
      s = s.replace(/\b(import|from|def|class|if|elif|else|while|for|return|try|except|with|as|in|not|and|or|True|False|None)\b/g,
        m => stash(`<span style="color:#f97583">${m}</span>`));
      s = s.replace(/\b(print|sleep|range|len|int|float|str|list|dict)\b/g,
        m => stash(`<span style="color:#b3f0ff">${m}</span>`));
    } else {
      s = s.replace(/(\/\/.*)$/g, m => stash(`<span style="color:#5c6e80;font-style:italic">${m}</span>`));
      s = s.replace(/(&quot;[^&]*&quot;|"[^"]*")/g, m => stash(`<span style="color:#f8b878">${m}</span>`));
      s = s.replace(/(#include|#define)/g, m => stash(`<span style="color:#f97583">${m}</span>`));
      s = s.replace(/\b(void|float|char|int|unsigned|long|const|bool|byte|String|boolean)\b/g,
        m => stash(`<span style="color:#79b8ff">${m}</span>`));
      s = s.replace(/\b(setup|loop|begin|publish|snprintf|delay|millis|readTemperature|readHumidity|readLightLevel|updateDisplay|connect|setServer|esp_deep_sleep|Serial|pinMode|digitalWrite|digitalRead|analogRead|analogWrite|tone|noTone|attachInterrupt)\b/g,
        m => stash(`<span style="color:#b3f0ff">${m}</span>`));
    }
    return s.replace(/⎇(\d+)⎇/g, (_, i) => slots[+i]);
  }

  // ─── Export to window ─────────────────
  Object.assign(window, {
    VIEW_PRESETS,
    ViewCube,
    ViewControls,
    _highlight,
  });
})();
