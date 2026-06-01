// ═══════════════════════════════════════════
// utils/thermal-helpers.js — STR4: 熱力視覺化工具函式
// 抽自 views-engineer-assembly.jsx，掛載到 window 供全域使用
// ═══════════════════════════════════════════

// ─── 熱力色溫 LUT ─────────────────

const _THERMAL_LUT = [
  { t: 0.00, r: 0.15, g: 0.35, b: 0.85 },  // 冷 — 藍
  { t: 0.25, r: 0.10, g: 0.75, b: 0.45 },  // 低 — 綠
  { t: 0.50, r: 0.90, g: 0.85, b: 0.15 },  // 中 — 黃
  { t: 0.75, r: 0.95, g: 0.45, b: 0.10 },  // 高 — 橙
  { t: 1.00, r: 0.90, g: 0.10, b: 0.10 },  // 熱 — 紅
];

// lerpThermalColor(norm) → [r, g, b]  (norm 0–1)
window.lerpThermalColor = function lerpThermalColor(norm) {
  const n = Math.max(0, Math.min(1, norm));
  let lo = _THERMAL_LUT[0], hi = _THERMAL_LUT[_THERMAL_LUT.length - 1];
  for (let i = 0; i < _THERMAL_LUT.length - 1; i++) {
    if (n >= _THERMAL_LUT[i].t && n <= _THERMAL_LUT[i + 1].t) {
      lo = _THERMAL_LUT[i]; hi = _THERMAL_LUT[i + 1];
      break;
    }
  }
  const f = lo.t === hi.t ? 0 : (n - lo.t) / (hi.t - lo.t);
  return [
    lo.r + (hi.r - lo.r) * f,
    lo.g + (hi.g - lo.g) * f,
    lo.b + (hi.b - lo.b) * f,
  ];
};

// estimateSurfaceTemp(power_mw, ambientC) → °C
window.estimateSurfaceTemp = function estimateSurfaceTemp(power_mw, ambientC = 25) {
  const R_THERMAL = 0.04; // °C/mW (PLA 封閉殼經驗值)
  return ambientC + power_mw * R_THERMAL;
};

// probeTemperature(worldX, worldZ, heatSources, ambientC) → °C at arbitrary XZ point
window.probeTemperature = function probeTemperature(worldX, worldZ, heatSources, ambientC = 25) {
  if (!heatSources?.length) return ambientC;
  let temp = ambientC;
  for (let i = 0; i < heatSources.length; i++) {
    const src = heatSources[i];
    const mw = src.thermal_mw || src.power_mw || 0;
    if (mw <= 0) continue;
    const sx = src.position?.[0] ?? 0;
    const sy = src.position?.[1] ?? 0;
    const dx = worldX - sx, dy = worldZ - sy;
    const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
    const radius = src.influence_radius_mm || 20;
    const falloff = Math.exp(-(dist * dist) / (2 * (radius * 0.5) * (radius * 0.5)));
    temp += (mw * 0.04) * falloff;
  }
  return temp;
};
