// user-components/tag-pickers.jsx — INF1-S22: Tag data + picker sub-components
// Extracted from views-user-components.jsx for < 500 line compliance.

// ── Tag 語彙 + Hover 說明（B 方案）────────────

const TAG_AXIS1_GROUPS = [
  {
    label: '匯流排',
    hint: '多條訊號線的通訊協定，通常可共用線路接多個裝置',
    items: [
      { value: 'bus:i2c',   label: 'I²C',    tip: '只需 2 條線（SDA + SCL）即可接多個裝置，常見於感測器、OLED 螢幕、LCD。速度中等，接線最簡單' },
      { value: 'bus:spi',   label: 'SPI',     tip: '需 4 條線但速度快，適合 LED 矩陣、E-Ink 螢幕、SD 卡等需要大量資料傳輸的裝置' },
      { value: 'bus:uart',  label: 'UART',    tip: '序列通訊（TX + RX 兩條線），常見於 GPS 模組、藍牙模組、MP3 播放器' },
      { value: 'bus:1wire', label: '1-Wire',  tip: '只需 1 條資料線，常見於 DS18B20 溫度感測器。速度慢但接線極簡' },
      { value: 'bus:rf',    label: 'RF 無線',  tip: '射頻無線通訊模組（如 433MHz、LoRa），不需實體接線但需天線' },
      { value: 'bus:usb',   label: 'USB',     tip: 'USB 介面連接，常見於主控板本身（Arduino、ESP32）或 USB 裝置' },
    ],
  },
  {
    label: 'GPIO 控制',
    hint: '直接用主控板的接腳控制，每個裝置各佔一個 pin',
    items: [
      { value: 'gpio:digital', label: '數位',  tip: '只有 HIGH / LOW 兩種狀態。按鈕、繼電器、蜂鳴器、PIR 感測器等最常用此模式' },
      { value: 'gpio:pwm',     label: 'PWM',   tip: '脈衝寬度調變 — 可輸出「類似類比」的漸變值。控制 LED 亮度、馬達轉速、舵機角度' },
      { value: 'gpio:analog',  label: '類比',   tip: '讀取連續電壓值（0~3.3V）。光敏電阻、旋鈕（電位器）、搖桿、土壤濕度計' },
      { value: 'gpio:pulse',   label: '脈衝',   tip: '透過量測脈衝時間長度來取得資料。超音波測距（HC-SR04）是典型代表' },
    ],
  },
  {
    label: '其他',
    hint: '不需要主控板訊號的被動元件',
    items: [
      { value: 'iface:passive', label: '被動 / 無訊號', tip: '不需要 MCU 訊號線的元件：電池、電源供應器、車架底盤、被動喇叭等' },
    ],
  },
];

const TAG_AXIS2_PREFIXES = [
  { value: 'measure:',   label: '感測',       tip: '偵測環境數據：溫度、濕度、光線、距離、動作等' },
  { value: 'display:',   label: '顯示',       tip: '呈現文字或圖形：OLED、LCD、E-Ink、LED 矩陣' },
  { value: 'actuate:',   label: '機械輸出',   tip: '產生物理動作：馬達旋轉、水泵抽水、繼電器開關' },
  { value: 'light:',     label: '照明',       tip: '發光元件：單色 LED、RGB LED、LED 燈條' },
  { value: 'sound:',     label: '聲音',       tip: '發出聲音：蜂鳴器、喇叭、MP3 模組' },
  { value: 'control:',   label: '使用者輸入', tip: '接收人的操作：按鈕、開關、搖桿、旋鈕、遙控器' },
  { value: 'mcu:',       label: '主控板',     tip: '微控制器本身：Arduino、ESP32、Raspberry Pi' },
  { value: 'power:',     label: '電源',       tip: '供電元件：USB 電源、鋰電池、AC 變壓器' },
  { value: 'structure:', label: '結構件',     tip: '機械結構：車架底盤、穿戴綁帶、支架' },
];

// ── Tooltip Component ───────────────────────

function Tip({ text, children }) {
  const [show, setShow] = React.useState(false);
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span style={{
          position: 'absolute', bottom: '110%', left: '50%', transform: 'translateX(-50%)',
          background: 'var(--bg-1)', border: '1px solid var(--border-default)',
          borderRadius: 'var(--r-sm)', padding: '8px 12px', fontSize: 11,
          color: 'var(--text-secondary)', lineHeight: 1.5,
          width: 240, zIndex: 999, boxShadow: 'var(--shadow-md)',
          pointerEvents: 'none', whiteSpace: 'normal',
        }}>
          {text}
        </span>
      )}
    </span>
  );
}

// ── Axis1 chip styles (module-scope) ────────

const _chipBase = {
  padding: '5px 12px', fontSize: 12, borderRadius: 'var(--r-sm)',
  cursor: 'pointer', borderWidth: 1, borderStyle: 'solid', borderColor: 'var(--border-subtle)',
  transition: 'all 0.15s', fontFamily: 'var(--font-sans)',
};
const _chipOff = { ..._chipBase, background: 'var(--bg-3)', color: 'var(--text-secondary)' };
const _chipOn  = { ..._chipBase, background: 'var(--accent-2-dim, rgba(0,200,200,0.12))', color: 'var(--6e-explore, var(--accent))', borderColor: 'var(--6e-explore, var(--accent))' };

// ── Axis1 Button Picker (with tooltips) ─────

function Axis1Picker({ selected, onChange }) {
  const toggle = (val) => {
    onChange(selected === val ? '' : val);
  };

  return (
    <div>
      {TAG_AXIS1_GROUPS.map(group => (
        <div key={group.label} style={{ marginBottom: 8 }}>
          <Tip text={group.hint}>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginRight: 8, borderBottom: '1px dotted var(--text-tertiary)', cursor: 'help' }}>{group.label}</span>
          </Tip>
          <div style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
            {group.items.map(item => (
              <Tip key={item.value} text={item.tip}>
                <button
                  type="button"
                  onClick={() => toggle(item.value)}
                  style={selected === item.value ? _chipOn : _chipOff}
                >
                  {item.label}
                </button>
              </Tip>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Axis2 Multi-Tag Editor (with tooltips) ──

function Axis2Editor({ tags, onChange }) {
  const [prefix, setPrefix] = React.useState(TAG_AXIS2_PREFIXES[0].value);
  const [suffix, setSuffix] = React.useState('');

  const currentPrefixInfo = TAG_AXIS2_PREFIXES.find(p => p.value === prefix);

  const add = () => {
    const s = suffix.trim().replace(/\s+/g, '_');
    if (!s) return;
    const tag = `${prefix}${s}`;
    if (!tags.includes(tag)) onChange([...tags, tag]);
    setSuffix('');
  };

  const remove = (tag) => onChange(tags.filter(t => t !== tag));

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') { e.preventDefault(); add(); }
  };

  const inputStyle = {
    background: 'var(--bg-3)', border: '1px solid var(--border-subtle)',
    borderRadius: 'var(--r-sm)', padding: '6px 10px', fontSize: 13,
    color: 'var(--text-primary)', outline: 'none',
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 4 }}>
        <select
          style={{ ...inputStyle, width: 160 }}
          value={prefix}
          onChange={e => setPrefix(e.target.value)}
        >
          {TAG_AXIS2_PREFIXES.map(p => (
            <option key={p.value} value={p.value}>{p.label}（{p.value.slice(0, -1)}）</option>
          ))}
        </select>
        <input
          style={{ ...inputStyle, flex: 1 }}
          value={suffix}
          onChange={e => setSuffix(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="例：temperature、rotation_position"
        />
        <button
          type="button"
          onClick={add}
          style={{
            background: 'var(--bg-3)', border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--r-sm)', padding: '5px 12px', fontSize: 12,
            color: 'var(--text-secondary)', cursor: 'pointer',
          }}
        >加入</button>
      </div>
      {currentPrefixInfo && (
        <p style={{ color: 'var(--text-tertiary)', fontSize: 11, margin: '0 0 8px', fontStyle: 'italic' }}>
          {currentPrefixInfo.tip}
        </p>
      )}
      {tags.length === 0 && (
        <p style={{ color: 'var(--text-tertiary)', fontSize: 11, margin: '0 0 4px', fontStyle: 'italic' }}>
          請至少加入一個功能標籤
        </p>
      )}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {tags.map(t => (
          <Badge key={t} bg="var(--bg-3)" style={{ fontSize: 11, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
            {t}
            <span
              onClick={() => remove(t)}
              style={{ cursor: 'pointer', color: 'var(--red)', fontSize: 14, lineHeight: 1, marginLeft: 2 }}
            >&times;</span>
          </Badge>
        ))}
      </div>
    </div>
  );
}

// ── Preset Picker ───────────────────────────

function PresetPicker({ onApply }) {
  const [hoveredLabel, setHoveredLabel] = React.useState(null);

  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, display: 'block' }}>
        快速選擇 <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>— 點選後自動帶入介面、功能與電氣參數，再填入名稱和尺寸即可</span>
      </label>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {COMPONENT_PRESETS.map(p => {
          const hov = hoveredLabel === p.label;
          return (
            <button
              key={p.label}
              type="button"
              onClick={() => onApply(p)}
              onMouseEnter={() => setHoveredLabel(p.label)}
              onMouseLeave={() => setHoveredLabel(null)}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '6px 14px', fontSize: 12, borderRadius: 'var(--r-sm)',
                cursor: 'pointer', borderWidth: 1, borderStyle: 'solid',
                borderColor: hov ? 'var(--accent)' : 'var(--border-subtle)',
                background: 'var(--bg-3)',
                color: hov ? 'var(--text-primary)' : 'var(--text-secondary)',
                transition: 'all 0.15s', fontFamily: 'var(--font-sans)',
              }}
            >
              <span style={{ fontSize: 15 }}>{p.icon}</span>
              {p.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, { Tip, Axis1Picker, Axis2Editor, PresetPicker, TAG_AXIS1_GROUPS, TAG_AXIS2_PREFIXES });
