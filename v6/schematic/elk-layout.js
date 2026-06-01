// ═══════════════════════════════════════════
// elk-layout.js — ELK graph construction + layout algorithm interface
// Split from schematic-elk.jsx (INF1-S1)
// ═══════════════════════════════════════════

(() => {
  const MCU_PORTS = window.MCU_PORTS;
  const COMP_SPECS = window.COMP_SPECS;
  const COMP_PINS = window.COMP_PINS;
  const COMP_DIMS = window.COMP_DIMS;

  const PORT_W = 6;

  // Convert normalized [0-1] coords to pixel position + side string
  function posToPort(nx, ny, w, h) {
    const px = nx <= 0 ? 0 : nx >= 1 ? w - PORT_W : nx * w - PORT_W / 2;
    const py = ny <= 0 ? 0 : ny >= 1 ? h - PORT_W : ny * h - PORT_W / 2;
    const side = nx <= 0 ? 'WEST' : nx >= 1 ? 'EAST' : ny <= 0 ? 'NORTH' : 'SOUTH';
    return { px, py, side };
  }

  // B(issue1): 被動元件不再當節點插入切斷走線 — 改為「走線上標註」(R) 與「元件/MCU 旁徽章」(C)。
  // 串聯/上拉/分壓 R → 在對應 edge 的 _meta.passive 標註,走線維持連續單邊;
  // 去耦/電源 C → 收進元件/MCU 的 _meta.passives 畫徽章。netlist 不變。

  function _normPin(mcu) {
    return (pin) => {
      const ports = MCU_PORTS[mcu];
      if (!ports) return pin;
      const all = [...ports.north, ...ports.south, ...ports.west, ...ports.east];
      if (all.includes(pin)) return pin;
      const found = all.find(p => p.startsWith(pin + '/') || p.startsWith(pin + '~') || p === pin);
      return found || pin;
    };
  }

  function buildElkGraph(mcuType, wiringData, powerPassives) {
    window.resetSchematicTelemetry?.();  // VS: 每次重建重置接線 telemetry
    const ports = MCU_PORTS[mcuType] || MCU_PORTS.Arduino;
    const norm = _normPin(mcuType);

    const usedPins = new Set();
    const compNodes = [];
    const mcuPowerCaps = [];  // B: MCU 電源軌去耦/穩壓電容（畫成 MCU 旁徽章,非節點）
    const edges = [];
    const deferredEdges = [];
    let edgeId = 0;

    // First pass: detect inter-component source ports
    const interCompSrcPorts = new Set();
    for (const [_compKey, info] of Object.entries(wiringData)) {
      for (const pin of info.pins) {
        if (pin.mcu && pin.mcu.includes('.')) {
          const [srcRaw, srcPin] = pin.mcu.split('.');
          const srcComp = Object.keys(wiringData).find(k =>
            k === srcRaw || k.toLowerCase() === srcRaw.toLowerCase()
          ) || srcRaw;
          interCompSrcPorts.add(`${srcComp}_${srcPin}`);
        }
      }
    }

    for (const [compKey, info] of Object.entries(wiringData)) {
      const spec = COMP_SPECS[compKey] || { label: compKey, sub: '', note: '', color: '#888' };
      const compPorts = [];
      const dims = COMP_DIMS[compKey];
      const compW = dims ? dims[0] : 130;
      const compH = dims ? Math.max(dims[1], 40 + info.pins.length * 12) : 60 + (info.pins.length > 3 ? (info.pins.length - 3) * 12 : 0);

      const unmappedPins = info.pins.filter(p => {
        if (p.mcu?.includes('.')) return false;
        return !COMP_PINS[compKey]?.[p.comp];
      });
      let unmappedIdx = 0;

      for (const pin of info.pins) {
        const portId = `${compKey}_${pin.comp}`;
        const pinPos = COMP_PINS[compKey]?.[pin.comp];
        const uc = (pin.comp || '').toUpperCase();
        const compDir = pin.comp_dir || '';
        const isVcc = compDir === 'power'
          || uc === 'VCC' || uc === '5V' || uc === '3V3' || uc === 'VIN';
        const isGnd = compDir === 'gnd' || uc === 'GND';
        let px, py, side;

        if (pinPos) {
          ({ px, py, side } = posToPort(pinPos[0], pinPos[1], compW, compH));
        } else {
          const spc = compH / (unmappedPins.length + 1);
          px = 0; py = spc * (unmappedIdx + 1) - PORT_W / 2; side = 'WEST';
          unmappedIdx++;
        }

        compPorts.push({
          id: portId, width: PORT_W, height: PORT_W,
          x: px, y: py,
          properties: { 'port.side': side },
        });

        // Inter-component wire
        if (pin.mcu && pin.mcu.includes('.')) {
          const [srcRaw, srcPin] = pin.mcu.split('.');
          const srcComp = Object.keys(wiringData).find(k =>
            k === srcRaw || k.toLowerCase() === srcRaw.toLowerCase()
          ) || srcRaw;
          deferredEdges.push({
            id: `e${edgeId++}`,
            sources: [`${srcComp}_${srcPin}`],
            targets: [portId],
            _meta: {
              type: 'signal',
              color: pin.color || spec.color,
              compPin: pin.comp,
              mcuPin: pin.mcu,
              note: pin.note || '',
            },
          });
          continue;
        }

        // Normal MCU pin
        const mcuPin = norm(pin.mcu);
        const allMcuPins = new Set([...ports.north, ...ports.south, ...ports.west, ...ports.east]);
        if (!allMcuPins.has(mcuPin)) {
          const VIRTUAL_TERMINALS = new Set(['LOAD', 'SPK', 'SPK-', 'PUMP+', 'PUMP-']);
          if (!VIRTUAL_TERMINALS.has(mcuPin) && !mcuPin.startsWith('EXT')) {
            console.warn(`[schematic-elk] ${compKey}.${pin.comp} → ${mcuPin} 不在 ${mcuType} MCU 白名單,該接線未繪`);
            window.recordSchematicDrop?.(compKey, pin.comp, mcuPin);  // VS: 收集棄繪（角位未接線）
          }
          continue;
        }
        usedPins.add(mcuPin);
        window.recordSchematicRoute?.();  // VS: 計數成功繪出的接線

        const _vd = (pin.mcu_vd || pin.comp_vd || '').toUpperCase();
        const isPowerSource = (pin._netRole === 'source');
        const wireType = isGnd ? 'gnd'
          : isVcc ? 'vcc_bus'
          : isPowerSource ? 'power_source'
          : 'signal';
        const baseMeta = {
          type: wireType, color: pin.color || spec.color,
          compPin: pin.comp, mcuPin: pin.mcu,
          compDir: pin.comp_dir || '', mcuDir: pin.mcu_dir || '',
          voltageDomain: pin.mcu_vd || pin.comp_vd || '', note: pin.note || '',
        };
        if (isPowerSource) {
          baseMeta.isPowerSource = true;
          baseMeta.netRole = 'source';
        }
        const pas = pin.passive;
        if (pas && pas.kind === 'R' && pas.topo === 'series') {
          // B: 串聯電阻 — 單一連續走線 MCU→元件,R 以 _meta.passive 標在走線中點(不切斷)
          edges.push({ id: `e${edgeId++}`, sources: [`mcu_${mcuPin}`], targets: [portId], _meta: { ...baseMeta, passive: pas } });
        } else if (pas && pas.kind === 'R' && pas.topo === 'pullup') {
          // B: 上拉電阻 — 主訊號線連續;R 標在「往 5V 細支線」上(非節點)
          usedPins.add('5V');
          edges.push({ id: `e${edgeId++}`, sources: [`mcu_${mcuPin}`], targets: [portId], _meta: baseMeta });
          edges.push({ id: `e${edgeId++}`, sources: [portId], targets: ['mcu_5V'], _meta: { type: 'vcc_bus', color: '#ff4444', compPin: pas.value, mcuPin: '5V', note: '上拉至 VCC', passive: pas } });
        } else if (pas && pas.kind === 'R' && pas.topo === 'divider') {
          // B: 分壓電阻 — 主訊號線連續;R 標在「往 GND 細支線」上(非節點)
          usedPins.add('GND');
          edges.push({ id: `e${edgeId++}`, sources: [`mcu_${mcuPin}`], targets: [portId], _meta: baseMeta });
          edges.push({ id: `e${edgeId++}`, sources: [portId], targets: ['mcu_GND'], _meta: { type: 'gnd', color: '#333333', compPin: pas.value, mcuPin: 'GND', note: '分壓至 GND', passive: pas } });
        } else {
          edges.push({ id: `e${edgeId++}`, sources: [`mcu_${mcuPin}`], targets: [portId], _meta: baseMeta });
        }
      }

      // B: 元件去耦電容(VCC-GND) — 不插節點/不切走線,收進元件徽章
      // Phase2 step5: 透傳 refdes + location 供前端 location 切顯示
      const compDecoupCaps = (info.decoupling || [])
        .filter(c => c && c.kind === 'C')
        .map(c => ({ value: c.value, role: 'decoupling', refdes: c.refdes || '', location: c.location || 'onboard' }));

      // Add output ports for inter-component sources
      for (const srcPortId of interCompSrcPorts) {
        if (srcPortId.startsWith(compKey + '_')) {
          const pinName = srcPortId.slice(compKey.length + 1);
          if (!compPorts.find(p => p.id === srcPortId)) {
            const pos = COMP_PINS[compKey]?.[pinName];
            const { px: spx, py: spy, side: sps } = pos
              ? posToPort(pos[0], pos[1], compW, compH)
              : { px: compW - PORT_W, py: compH * 0.5 - PORT_W / 2, side: 'EAST' };
            compPorts.push({
              id: srcPortId, width: PORT_W, height: PORT_W,
              x: spx, y: spy,
              properties: { 'port.side': sps },
            });
          }
        }
      }

      compNodes.push({
        id: compKey,
        width: compW, height: compH,
        ports: compPorts,
        layoutOptions: { 'portConstraints': 'FIXED_POS' },
        _meta: { ...spec, compKey, passives: compDecoupCaps },  // B: 去耦電容徽章
      });
    }

    edges.push(...deferredEdges);

    // B: MCU 電源軌被動電容(bulk 穩壓 + MCU 去耦) — 不插節點/不切走線,收進 MCU 徽章
    // Phase2 step5: 透傳 refdes + location 供前端 location 切顯示
    for (let pi = 0; pi < (powerPassives || []).length; pi++) {
      const cap = powerPassives[pi];
      if (!cap || cap.kind !== 'C') continue;
      mcuPowerCaps.push({ value: cap.value, role: cap.topo === 'bulk' ? 'bulk' : 'decoupling', refdes: cap.refdes || '', location: cap.location || 'onboard' });
    }

    // Build MCU ports — FIXED_POS using PCB datasheet coordinates
    const MCU_MM = { Arduino: [68.6, 53.4], ESP32: [51.4, 28.0], Microbit: [51.8, 42.0], RPi: [85.0, 56.0] };
    const boardMM = MCU_MM[mcuType] || [68.58, 53.34];
    const MCU_PX_MM = 3.8;
    const mcuW = Math.round(boardMM[1] * MCU_PX_MM);
    const pinMinH = (Math.max(ports.west.length, ports.east.length)) * 13 + 50;
    const mcuH = Math.max(Math.round(boardMM[0] * MCU_PX_MM), pinMinH);

    const PCB_PIN_X = {
      Arduino: {
        'D0/RX': 63.500, 'D1/TX': 60.960, 'D2': 58.420, 'D3': 55.880,
        'D4': 53.340, 'D5~': 50.800, 'D6~': 48.260, 'D7': 45.720,
        'D8': 41.656, 'D9~': 39.116, 'D10~': 36.576, 'D11~': 34.036,
        'D12': 31.496, 'D13': 28.956, 'GND_D': 26.416, 'AREF': 23.876,
        'IOREF': 30.480, 'RESET': 33.020, '3V3': 35.560, '5V': 38.100,
        'GND': 40.640, 'GND2': 43.180, 'VIN': 45.720,
        'A0': 50.800, 'A1': 53.340, 'A2': 55.880, 'A3': 58.420,
        'A4/SDA': 60.960, 'A5/SCL': 63.500,
      },
      ESP32: {
        '3V3': 6.35, 'D4': 13.97, 'D5': 21.59,
        'D16': 16.51, 'D17': 19.05, 'D18': 24.13, 'D19': 26.67,
        'D21/SDA': 29.21, 'D22/SCL': 36.83,
        '5V/VIN': 1.27, 'GND': 3.81,
        'D25': 19.05, 'D26': 21.59, 'D27': 24.13,
        'D32': 13.97, 'D33': 16.51, 'D34': 8.89, 'D35': 11.43,
        'D36': 3.81, 'D39': 6.35,
      },
      Microbit: {
        '3V': 39.23, 'GND': 49.39, 'P0': 6.21, 'P1': 16.37, 'P2': 27.80,
        'P8': 14.37, 'P12': 19.45, 'P16': 24.53,
        'P19/SCL': 28.34, 'P20/SDA': 29.61,
      },
      RPi: {
        '3V3': 7.10, '5V': 7.10, 'GND': 12.18,
        'GP4': 14.72, 'GP17': 19.80, 'GP27': 22.34, 'GP22': 24.88,
        'GP12': 45.20, 'GP13': 47.74, 'GP18': 19.80, 'GP19': 50.28,
        'GP23': 24.88, 'GP24': 27.42, 'GP25': 32.50,
        'GP2/SDA': 9.64, 'GP3/SCL': 12.18,
      },
    };
    const BL = boardMM[0];
    const pinMap = PCB_PIN_X[mcuType] || {};

    const buildMcuPorts = (pins, side) => {
      const n = pins.length;
      const isVert = side === 'NORTH' || side === 'SOUTH';
      return pins.map((p, i) => {
        let px, py;
        if (isVert) {
          py = side === 'NORTH' ? 0 : mcuH - PORT_W;
          px = n === 1 ? mcuW / 2 - PORT_W / 2 : 30 + i * ((mcuW - 60) / Math.max(n - 1, 1)) - PORT_W / 2;
        } else {
          px = side === 'WEST' ? 0 : mcuW - PORT_W;
          const pcbX = pinMap[p];
          if (pcbX !== undefined) {
            py = (BL - pcbX) / BL * mcuH - PORT_W / 2;
          } else {
            const margin = 30, avail = mcuH - margin - 20;
            py = margin + (n === 1 ? avail / 2 : i * (avail / Math.max(n - 1, 1))) - PORT_W / 2;
          }
        }
        return {
          id: `mcu_${p}`, width: PORT_W, height: PORT_W,
          x: px, y: py,
          properties: { 'port.side': side },
          _meta: { label: p, used: usedPins.has(p) },
        };
      });
    };

    const mcuPorts = [
      ...buildMcuPorts(ports.north, 'NORTH'),
      ...buildMcuPorts(ports.south, 'SOUTH'),
      ...buildMcuPorts(ports.west, 'WEST'),
      ...buildMcuPorts(ports.east, 'EAST'),
    ];

    return {
      id: 'root',
      layoutOptions: {
        'elk.algorithm': 'layered',
        'elk.direction': 'RIGHT',
        'elk.spacing.nodeNode': '45',
        'elk.spacing.edgeEdge': '10',
        'elk.spacing.edgeNode': '20',
        'elk.layered.spacing.nodeNodeBetweenLayers': '90',
        'elk.layered.spacing.edgeNodeBetweenLayers': '25',
        'elk.edgeRouting': 'ORTHOGONAL',
      },
      children: [
        {
          id: 'mcu',
          width: mcuW, height: mcuH,
          ports: mcuPorts,
          layoutOptions: { 'portConstraints': 'FIXED_POS' },
          _meta: { label: ports.label, sub: ports.sub, mcuType, passives: mcuPowerCaps },  // B: 電源電容徽章
        },
        ...compNodes,
      ],
      edges,
    };
  }

  // ── Flat→Nested wiring converter (for store fallback) ──
  function _wiringFlatToNested(flatWiring, bom, _components) {
    const refToSpec = {};
    if (bom && bom.length) {
      for (const b of bom) {
        const ref = b.id || b.ref || '';
        const compType = (b.type || '').replace(/-class$/, '').replace(/\s+/g, '');
        const specKey = Object.keys(COMP_SPECS).find(k =>
          k.toLowerCase() === compType.toLowerCase() ||
          compType.toLowerCase().includes(k.toLowerCase()) ||
          k.toLowerCase().includes(compType.toLowerCase().split(' ')[0])
        );
        if (specKey) refToSpec[ref] = specKey;
      }
    }

    const resolveRef = (raw) => COMP_SPECS[raw] ? raw : (refToSpec[raw] || raw);

    const nested = {};
    for (const w of flatWiring) {
      const parts = (w.to || '').split('.');
      if (parts.length < 2) continue;
      const rawKey = parts[0];
      const pinName = parts.slice(1).join('.');
      const compKey = resolveRef(rawKey);
      if (!nested[compKey]) nested[compKey] = { pins: [] };

      let mcuVal = w.from || '';
      if (mcuVal.includes('.')) {
        const [srcRef, srcPin] = mcuVal.split('.');
        const srcKey = resolveRef(srcRef);
        mcuVal = `${srcKey}.${srcPin}`;
      }

      nested[compKey].pins.push({
        mcu: mcuVal,
        comp: pinName,
        color: w.color || '#888',
        note: w.note || '',
      });
    }
    return nested;
  }

  // ── Exports ──
  window.PORT_W = PORT_W;
  window.buildElkGraph = buildElkGraph;
  window._wiringFlatToNested = _wiringFlatToNested;
})();
