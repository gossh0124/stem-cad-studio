// ═══════════════════════════════════════════
// config/component-presets.js — Quick-fill presets for user component form
// STR5: extracted from views-user-components.jsx
// ═══════════════════════════════════════════

(() => {
  window.COMPONENT_PRESETS = [
    { icon: '🌡', label: '溫濕度感測器', axis1: 'gpio:digital', axis2: ['measure:temperature', 'measure:humidity'], voltage: '5.0', current: '50' },
    { icon: '💡', label: '光感測器',     axis1: 'gpio:analog',  axis2: ['measure:light'], voltage: '3.3', current: '1' },
    { icon: '📏', label: '距離感測器',   axis1: 'gpio:pulse',   axis2: ['measure:distance'], voltage: '5.0', current: '50' },
    { icon: '👋', label: '人體感測器',   axis1: 'gpio:digital', axis2: ['measure:motion'], voltage: '5.0', current: '50' },
    { icon: '🔘', label: '按鈕 / 開關',  axis1: 'gpio:digital', axis2: ['control:button'], voltage: '5.0', current: '1' },
    { icon: '🕹', label: '搖桿 / 旋鈕',  axis1: 'gpio:analog',  axis2: ['control:joystick'], voltage: '5.0', current: '5' },
    { icon: '💡', label: 'LED 燈',       axis1: 'gpio:pwm',     axis2: ['light:rgb'], voltage: '3.3', current: '20' },
    { icon: '🖥', label: '顯示螢幕',     axis1: 'bus:i2c',      axis2: ['display:graphics'], voltage: '5.0', current: '50' },
    { icon: '⚙', label: '馬達 / 舵機',  axis1: 'gpio:pwm',     axis2: ['actuate:rotation_position'], voltage: '5.0', current: '200' },
    { icon: '🔔', label: '蜂鳴器',       axis1: 'gpio:digital', axis2: ['sound:tone_simple'], voltage: '5.0', current: '30' },
  ];
})();
