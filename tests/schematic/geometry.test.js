// tests/schematic/geometry.test.js — P0.1a 幾何斷言(headless ELK,取代 Chrome F5 目視)。
// 對 demo 跑真實 buildElkGraph + ELK.layout,斷言:① 0 棄繪;② 每 port 貼 node 邊。
'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { layoutDemo, portEdgeDistance, ON_EDGE_TOL_PX, DEMOS } = require('./_harness');

for (const [name, demo] of Object.entries(DEMOS)) {
  test(`${name}: 0 棄繪(recordSchematicDrop=0)`, async () => {
    const { window } = await layoutDemo(demo);
    assert.strictEqual(
      window.__drops.length, 0,
      `有棄繪 edge(線端無法解析真孔): ${JSON.stringify(window.__drops)}`);
  });

  test(`${name}: 每 port 貼 node 邊(onEdge ≤ ${ON_EDGE_TOL_PX}px)`, async () => {
    const { res, PORT_W } = await layoutDemo(demo);
    const offenders = [];
    for (const n of res.children) {
      for (const port of (n.ports || [])) {
        const d = portEdgeDistance(port, n, PORT_W);
        if (Math.abs(d) > ON_EDGE_TOL_PX) {
          offenders.push(`${port.id} side=${port.properties?.['port.side']} d=${d.toFixed(1)}`);
        }
      }
    }
    assert.deepStrictEqual(offenders, [], `port 未貼邊:\n  ${offenders.join('\n  ')}`);
  });
}

// ── P0.1b(b):兩地軌 node-set 斷言(graph 拓樸,非座標;DEC-H8 圖面忠實)────
// 殺 mutant:若刪 elk-layout.js 的 EXT-GND 改道(mcuPin 留 'GND' 仍在 MCU 白名單),
// 0 棄繪 + onEdge 仍全綠,但圖面把負載地畫回 MCU 邏輯地、與機器隔離 verdict 矛盾。
// 隔離本體由 l1_isolation set 代數證(電氣);此處只鎖「render 圖忠實呈現該 verdict」。
test('auto_waterer: EXT-GND 域 pin 全接 rail_EXT-GND,絕不接 mcu_GND', async () => {
  const demo = DEMOS.auto_waterer;
  const { res } = await layoutDemo(demo);
  const edges = res.edges || [];
  const extNet = demo.nets.find(n => n.name === 'EXT-GND');
  assert.ok(extNet && extNet.nodes.length > 0, 'fixture 應有 EXT-GND net 成員');
  for (const nd of extNet.nodes) {
    const portId = `${nd.ref}_${nd.pin}`;
    const touching = edges.filter(e =>
      (e.sources || []).includes(portId) || (e.targets || []).includes(portId));
    assert.ok(touching.length > 0, `${portId} 無任何 edge(EXT-GND 域 pin 未繪)`);
    const toExtRail = touching.some(e =>
      (e.targets || []).includes('rail_EXT-GND') || (e.sources || []).includes('rail_EXT-GND'));
    assert.ok(toExtRail, `${portId} 未接 rail_EXT-GND(隔離改道失效)`);
    const toMcuGnd = touching.some(e =>
      (e.sources || []).includes('mcu_GND') || (e.targets || []).includes('mcu_GND'));
    assert.strictEqual(toMcuGnd, false,
      `${portId} 接到 mcu_GND — 圖面把負載地綁回邏輯地,違反隔離呈現`);
  }
});

// ── P3.2:active refdes 徽章 passthrough(wiring[comp].refdes → node._meta.refdes)──
// SVG 標籤消費 _meta.refdes(schematic-elk.jsx node label 前綴);_meta 過 ELK 不變,
// 此處鎖欄位本體 + 無 refdes 時空字串降級(store fallback 重建路徑不爆)。
test('auto_waterer: active refdes 序入 node._meta(缺失空字串降級)', async () => {
  const { res } = await layoutDemo(DEMOS.auto_waterer);
  const relay = res.children.find(n => n.id === 'Relay');
  const soil = res.children.find(n => n.id === 'SoilMoisture');
  assert.ok(relay && soil, 'fixture 應含 Relay 與 SoilMoisture 節點');
  assert.strictEqual(relay._meta.refdes, 'K1', 'Relay 應帶 fixture refdes K1');
  assert.strictEqual(soil._meta.refdes, '', '無 refdes 元件應空字串降級');
});
