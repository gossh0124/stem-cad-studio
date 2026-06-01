// ═══════════════════════════════════════════
// comp-specs.js — Component visual definitions, port positions, render configs
// Split from schematic-elk.jsx (INF1-S1)
// ═══════════════════════════════════════════

(() => {
  // ── MCU Pin Layouts — defined in config/mcu-ports.js ──
  const _MCU_PORTS = window.MCU_PORTS;

  // ── Component visual specs ──
  const COMP_SPECS = {
    NeoPixel:     { label: 'NeoPixel',      sub: 'WS2812B',          note: '300Ω 串聯電阻',  color: '#00ff88' },
    LED_Single:   { label: 'LED',           sub: '單色指示燈',        note: '220Ω 串聯',      color: '#ff4444' },
    LED_RGB:      { label: 'RGB LED',       sub: '4-pin 共陰',       note: '220Ω × 3',      color: '#ff88cc' },
    Speaker:      { label: 'DFPlayer',      sub: 'Mini MP3',         note: 'SoftwareSerial', color: '#b392f0' },
    Buzzer:       { label: '蜂鳴器',         sub: '被動式',           note: 'PWM tone()',     color: '#ff8800' },
    OLED:         { label: 'OLED 0.96"',    sub: 'SSD1306 128×64',   note: 'I2C 0x3C',      color: '#ffaa00' },
    LCD:          { label: 'LCD 1602',      sub: 'I2C 背板',         note: 'I2C 0x27',      color: '#ffaa00' },
    Servo:        { label: 'SG90 伺服',      sub: '180° · 9g',       note: 'PWM 50Hz',      color: '#7cc47c' },
    DCMotor:      { label: 'DC 馬達',        sub: 'L298N 驅動',      note: 'PWM + 方向',     color: '#ef8354' },
    Relay:        { label: '繼電器',         sub: '5V 單路',          note: 'Active-LOW',    color: '#7cc47c' },
    Pump:         { label: '水泵',           sub: '沈水馬達 DC',     note: '5V DC',          color: '#5ba4cf' },
    TempHumid:    { label: 'DHT22',         sub: '溫濕度感測',       note: '4.7kΩ 上拉',     color: '#5ba4cf' },
    Ultrasonic:   { label: 'HC-SR04',       sub: '超音波測距',       note: 'TRIG+ECHO',     color: '#5ba4cf' },
    PIR:          { label: 'PIR',           sub: 'HC-SR501',         note: '偵測距離 7m',    color: '#44cc44' },
    SoilMoisture: { label: '土壤濕度',       sub: '電容式',           note: 'Analog 0-1023', color: '#5ba4cf' },
    Light:        { label: 'LDR',           sub: '光敏電阻',         note: '10kΩ 分壓',     color: '#ff88cc' },
    MSGEQ7:       { label: 'MSGEQ7',       sub: '7 頻段分析',       note: 'Analog Out',    color: '#b392f0' },
    Button:       { label: '按鈕',          sub: '微動開關',          note: 'INPUT_PULLUP',  color: '#44cc44' },
    Switch:       { label: '開關',          sub: '撥動式',            note: 'ON/OFF',        color: '#44cc44' },
    Stepper:      { label: '步進馬達',        sub: '28BYJ-48',          note: 'ULN2003 驅動',  color: '#ef8354' },
    BatteryAA:    { label: '電池盒',         sub: 'AA × 2 (3V)',       note: '可換式',        color: '#e8c547' },
    BatteryLiPo:  { label: '鋁電池',         sub: '1S 1000mAh',        note: '3.7V',          color: '#e8c547' },
    USB5V:        { label: 'USB 5V',         sub: '電源模組',           note: '穩壓 5V',       color: '#ff8800' },
  };

  const WIRE_STYLES = {
    vcc5:         { color: '#ff4444', width: 2,   dash: null,   label: '5V' },
    vcc33:        { color: '#ff8800', width: 2,   dash: null,   label: '3.3V' },
    vcc_bus:      { color: '#ff4444', width: 2,   dash: null,   label: 'VCC' },
    power_source: { color: '#ff4444', width: 2.5, dash: null,   label: 'PWR' },
    gnd:          { color: '#555555', width: 2,   dash: '4 2',  label: 'GND' },
    signal:       { color: null,      width: 1.8, dash: '6 3',  label: null },
  };

  // ── Pin positions (normalized 0-1, derived from lib/registry.py physical ports) ──
  const COMP_PINS = {
    SoilMoisture: { VCC:[0,.2], AO:[0,.5], AOUT:[0,.5], GND:[0,.8] },
    Relay:        { VCC:[0,.12], GND:[0,.3], IN:[0,.5], COM:[1,.25], NO:[1,.5], NC:[1,.75] },
    Pump:         { VCC:[0,.2], GND:[0,.8] },
    Ultrasonic:   { VCC:[0,.12], TRIG:[0,.35], ECHO:[0,.58], GND:[0,.82] },
    PIR:          { VCC:[0,.2], OUT:[0,.5], GND:[0,.8] },
    TempHumid:    { VCC:[0,.2], DATA:[0,.5], GND:[0,.8] },
    Servo:        { GND:[0,.2], VCC:[0,.5], SIGNAL:[0,.8], SIG:[0,.8] },
    DCMotor:      { VCC:[0,.1], GND:[0,.25], ENA:[0,.42], IN1:[0,.58], IN2:[0,.75], '+12V':[0,.9], 'M+':[1,.35], 'M-':[1,.65] },
    OLED:         { GND:[0,.12], VCC:[0,.35], SCL:[0,.58], SDA:[0,.82] },
    LCD:          { GND:[0,.12], VCC:[0,.35], SDA:[0,.58], SCL:[0,.82] },
    NeoPixel:     { DIN:[0,.2], DATA:[0,.2], VCC:[0,.5], GND:[0,.8] },
    Buzzer:       { '+':[0,.35], SIG:[0,.35], I:[0,.35], GND:[0,.65] },
    LED_Single:   { '+':[0,.35], Anode:[0,.35], SIG:[0,.35], GND:[0,.65] },
    LED_RGB:      { R:[0,.12], GND:[0,.35], G:[0,.58], B:[0,.82] },
    Speaker:      { VCC:[0,.25], GND:[0,.75], RX:[1,.35], TX:[1,.65] },
    Light:        { LDR:[0,.12], AOUT:[0,.12], AO:[0,.12], DOUT:[0,.35], DO:[0,.35], VCC:[0,.58], GND:[0,.82] },
    MSGEQ7:       { OUT:[0,.15], STROBE:[0,.4], RESET:[0,.65], VCC:[0,.85], GND:[0,.95] },
    Button:       { SIG:[0,.3], VCC:[0,.6], GND:[0,.85] },
    Switch:       { SIG:[0,.3], VCC:[0,.6], GND:[0,.85] },
    Stepper:      { IN1:[0,.15], IN2:[0,.38], IN3:[0,.62], IN4:[0,.85], VCC:[0,.05], GND:[0,.95] },
    BatteryAA:    { 'BAT+':[1,.3], VCC:[1,.3], 'BAT-':[1,.7], GND:[1,.7] },
    BatteryLiPo:  { 'BAT+':[1,.3], VCC:[1,.3], 'BAT-':[1,.7], GND:[1,.7] },
    USB5V:        { 'V+':[1,.3], VCC:[1,.3], 'V-':[1,.7], GND:[1,.7] },
  };

  // ── Component physical dimensions (SSOT: data/component-dimensions.js) ──
  const REGISTRY_MM = window.REGISTRY_MM;
  const SCALE_PX_PER_MM = 2.0;
  const MIN_READABLE_PX = 44;

  function _calcDims(mm) {
    return [
      Math.max(Math.round(mm[0] * SCALE_PX_PER_MM), MIN_READABLE_PX),
      Math.max(Math.round(mm[1] * SCALE_PX_PER_MM), MIN_READABLE_PX),
    ];
  }

  const COMP_DIMS = {};
  for (const [k, mm] of Object.entries(REGISTRY_MM)) {
    COMP_DIMS[k] = _calcDims(mm);
  }

  // ── Pin type colors ──
  const PIN_CLR = { PWR: '#ff4444', GND: '#666', GPIO: '#44dd88', ANALOG: '#ffaa00', I2C: '#4499ff', UART: '#b070ff', OTHER: '#999' };
  function _pinClr(name) {
    if (!name) return '#888';
    const p = name.toUpperCase();
    if (p === 'VCC' || p === '5V' || p === '3V3' || p === '3.3V' || p === 'VIN' || p === 'IOREF') return PIN_CLR.PWR;
    if (p === 'GND' || p === 'GND_D' || p === 'GND2' || p === 'GND_PWR') return PIN_CLR.GND;
    if (p === 'AREF' || p === 'RESET') return PIN_CLR.OTHER;
    if (p === 'SDA' || p === 'SCL') return PIN_CLR.I2C;
    if (p === 'TX' || p === 'RX') return PIN_CLR.UART;
    if (p.startsWith('A') && p.length <= 3 && /\d/.test(p)) return PIN_CLR.ANALOG;
    if (p === 'COM' || p === 'NO' || p === 'NC' || p === '+' || p === '-') return PIN_CLR.OTHER;
    return PIN_CLR.GPIO;
  }

  // ── Current flow direction resolver ──
  function _flowDir(meta) {
    const t = meta.type;
    if (t === 'vcc5' || t === 'vcc33' || t === 'vcc_bus' || t === 'power_source') return 'mcu2comp';
    if (t === 'gnd') return 'comp2mcu';
    const cd = (meta.compDir || '').toLowerCase();
    if (cd.includes('_in') || cd === 'digital_in' || cd === 'pwm_in') return 'mcu2comp';
    if (cd.includes('_out') || cd === 'digital_out' || cd === 'analog_out') return 'comp2mcu';
    if (cd === 'i2c_bidir' || cd === 'digital_bidir') return 'mcu2comp';
    return 'mcu2comp';
  }

  // ── Exports ──
  window.COMP_SPECS = COMP_SPECS;
  window.WIRE_STYLES = WIRE_STYLES;
  window.COMP_PINS = COMP_PINS;
  window.COMP_DIMS = COMP_DIMS;
  window.PIN_CLR = PIN_CLR;
  window._pinClr = _pinClr;
  window._flowDir = _flowDir;
})();
