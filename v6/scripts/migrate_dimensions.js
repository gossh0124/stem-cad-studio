#!/usr/bin/env node
// migrate_dimensions.js — Convert component-dimensions.js from legacy (x/y/w/h) to new (cx/cy/params)
// Run: node v6/scripts/migrate_dimensions.js
// Output: overwrites v6/data/component-dimensions.js with new format
'use strict';
const fs   = require('fs');
const path = require('path');

// ── Mock window for loading the legacy file ──
const window = {};
const _srcPath = path.join(__dirname, '../data/component-dimensions.js');
if (!fs.existsSync(_srcPath)) {
  console.error(`[migrate_dimensions] 來源檔案不存在：${_srcPath}`);
  process.exit(1);
}
eval(fs.readFileSync(_srcPath, 'utf8'));

const oldDims = window.COMPONENT_DIMENSIONS;
const regMM   = window.REGISTRY_MM;
const newDims = {};

// ── Shape-specific param mapping rules ──
// Each shape maps old (w, h, d, pins, pitch, rows) → params object
const SHAPE_RULES = {
  'ic-dip':         (p) => ({ pins: p.pins, pitch: p.pitch, rows: p.rows || 2, bodyW: p.w, rowSpacing: p.h, bodyH: p.d }),
  'ic-soic':        (p) => ({ pins: p.pins, pitch: p.pitch, bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'ic-qfp':         (p) => ({ pins: p.pins, pitch: p.pitch, bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'ic-module':      (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'conn-header-male':   (p) => ({ pins: p.pins, pitch: p.pitch || 2.54, rows: p.rows || 1 }),
  'conn-header-female': (p) => ({ pins: p.pins, pitch: p.pitch || 2.54, rows: p.rows || 1 }),
  'conn-usb-micro':     (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'conn-usb-c':         (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'conn-usb-b':         (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'conn-barrel-jack':   (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'conn-screw-terminal':(p) => ({ pins: p.pins, pitch: p.pitch || 5.08, bodyD: p.h, bodyH: p.d }),
  'relay':          (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'button-tactile': (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'pot-trimmer':    (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'pot-shaft':      (p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'led-tht':        (p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'led-smd':        (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'cap-electrolytic':(p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'cap-ceramic':    (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'res-smd':        (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'crystal-hc49':   (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'buzzer':         (p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'motor-dc':       (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'motor-servo':    (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
  'motor-stepper':  (p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'sensor-dome':    (p) => ({ diameter: p.w, bodyD: p.h, bodyH: p.d }),
  'mounting-hole':  (p) => ({ diameter: p.w, padDia: p.h }),
  'vreg-to220':     (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d }),
};

// Generic fallback
const GENERIC_RULE = (p) => ({ bodyW: p.w, bodyD: p.h, bodyH: p.d });

// ── Transform each entry ──
for (const [key, entry] of Object.entries(oldDims)) {
  const newEntry = { l: entry.l, w: entry.w, h: entry.h, ports: [] };
  for (const p of (entry.ports || [])) {
    // Calculate center coordinates from top-left x/y
    const pw = p.w || 4;
    const ph = p.h || pw;
    const cx = round(p.x + pw / 2);
    const cy = round(p.y + ph / 2);

    const newPort = { side: p.side || 'face', cx, cy };
    if (p.rot) newPort.rot = p.rot;
    newPort.shape = p.shape || 'box';
    newPort.label = p.label;
    newPort.color = p.color;

    // Build params from shape-specific rules
    const rule = SHAPE_RULES[p.shape] || GENERIC_RULE;
    const raw  = rule(p);
    // Remove undefined/null values
    const params = {};
    for (const [k, v] of Object.entries(raw)) {
      if (v !== undefined && v !== null) params[k] = v;
    }
    if (Object.keys(params).length > 0) newPort.params = params;

    newEntry.ports.push(newPort);
  }
  newDims[key] = newEntry;
}

function round(v) { return Math.round(v * 100) / 100; }

// ── Generate output file ──
const lines = [];
lines.push(`// ─── component-dimensions.js ──────────────────────────────────────────────
// STR2: SSOT for 3D component dimensions & port positions
// Format v2: cx/cy center coordinates + params object (2026-05-19 migration)
//
// Port format:
//   { side, cx, cy, rot?, shape, label, color, params: { shape-specific } }
//   cx/cy = center coordinate in mm (origin = PCB top-left corner)
//   params = shape-specific dimensions (bodyW, bodyD, bodyH, pins, pitch, rows, diameter...)
//
// SSOT: data/component_datasheet_verified.json (2026-05-19 aligned)
// ──────────────────────────────────────────────────────────────────────────

// ── 3D port dimension table (key = -class suffix matching canned template component.type) ──
window.COMPONENT_DIMENSIONS = {`);

// Group entries by category (detect from comments in original)
const categories = detectCategories();
let lastCat = '';

for (const [key, entry] of Object.entries(newDims)) {
  const cat = categories[key] || '';
  if (cat && cat !== lastCat) {
    lines.push(`\n  // ── ${cat} ──`);
    lastCat = cat;
  }
  lines.push(`  ${JSON.stringify(key)}: ${formatEntry(entry)},`);
}
lines.push(`};`);

// Append REGISTRY_MM unchanged
lines.push(`
// ── Schematic dimension table (original REGISTRY_MM, key = schematic compKey) ──
window.REGISTRY_MM = ${JSON.stringify(regMM, null, 2).replace(/^/gm, '').trim()};`);

// Append lookup function
lines.push(`
// ── Lookup helper ─────────────────────────────────────────────────────────
window.getDimByClass = function(c) {
  const t = c?.type || '';
  if (window.COMPONENT_DIMENSIONS[t]) return { ...window.COMPONENT_DIMENSIONS[t], known: true };
  const stem = t.replace(/-class$/, '').split('-').slice(0, 2).join('-') + '-class';
  if (window.COMPONENT_DIMENSIONS[stem]) return { ...window.COMPONENT_DIMENSIONS[stem], known: true };
  return { l: 30, w: 20, h: 10, ports: [], known: false };
};`);

const output = lines.join('\n') + '\n';
const outPath = path.join(__dirname, '../data/component-dimensions.js');
fs.writeFileSync(outPath, output, 'utf8');

const entryCount = Object.keys(newDims).length;
let portCount = 0;
for (const e of Object.values(newDims)) portCount += (e.ports || []).length;
console.log(`Migrated ${entryCount} entries, ${portCount} ports → ${outPath}`);

// ── Helpers ──

function detectCategories() {
  // Read original file to extract category comments
  const _catPath = path.join(__dirname, '../data/component-dimensions.js');
  if (!fs.existsSync(_catPath)) {
    console.error(`[migrate_dimensions] 來源檔案不存在：${_catPath}`);
    process.exit(1);
  }
  const src = fs.readFileSync(_catPath, 'utf8');
  const cats = {};
  let currentCat = '';
  for (const line of src.split('\n')) {
    const catMatch = line.match(/\/\/\s*──\s*(.+?)\s*──/);
    if (catMatch) { currentCat = catMatch[1].trim(); continue; }
    const keyMatch = line.match(/'([^']+)':\s*\{/);
    if (keyMatch && currentCat) cats[keyMatch[1]] = currentCat;
  }
  return cats;
}

function formatEntry(entry) {
  const parts = [`{ l: ${entry.l}, w: ${entry.w}, h: ${entry.h}, ports: [`];
  for (let i = 0; i < entry.ports.length; i++) {
    const p = entry.ports[i];
    const comma = i < entry.ports.length - 1 ? ',' : '';
    parts.push(`    ${formatPort(p)}${comma}`);
  }
  parts.push(`  ] }`);
  return parts.join('\n');
}

function formatPort(p) {
  const fields = [];
  fields.push(`side: '${p.side}'`);
  fields.push(`cx: ${p.cx}`);
  fields.push(`cy: ${p.cy}`);
  if (p.rot) fields.push(`rot: ${p.rot}`);
  fields.push(`shape: '${p.shape}'`);
  fields.push(`label: '${p.label}'`);
  fields.push(`color: '${p.color}'`);
  if (p.params) {
    const pParts = [];
    for (const [k, v] of Object.entries(p.params)) {
      pParts.push(`${k}: ${typeof v === 'string' ? `'${v}'` : v}`);
    }
    fields.push(`params: { ${pParts.join(', ')} }`);
  }
  return `{ ${fields.join(', ')} }`;
}
