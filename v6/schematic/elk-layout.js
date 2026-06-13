// ═══════════════════════════════════════════
// elk-layout.js — ELK graph construction + layout algorithm interface
// Split from schematic-elk.jsx (INF1-S1)
// ═══════════════════════════════════════════

(() => {
  const MCU_PORTS = window.MCU_PORTS;
  const COMP_SPECS = window.COMP_SPECS;
  const COMP_DIMS = window.COMP_DIMS;

  const PORT_W = 6;

  // Convert normalized [0-1] coords to pixel position + side string
  function posToPort(nx, ny, w, h) {
    const px = nx <= 0 ? 0 : nx >= 1 ? w - PORT_W : nx * w - PORT_W / 2;
    const py = ny <= 0 ? 0 : ny >= 1 ? h - PORT_W : ny * h - PORT_W / 2;
    const side = nx <= 0 ? 'WEST' : nx >= 1 ? 'EAST' : ny <= 0 ? 'NORTH' : 'SOUTH';
    return { px, py, side };
  }

  // ── 擬真接線 Stage 1:真實 I/O 孔位（SCHEM_PINS = SSOT pin_layout 衍生）──
  // 每 pin 帶真實 {nx,ny,side}（nx=x_mm/L, ny=y_mm/W,side=header_group 所在邊）。
  // P4.2(2026-06-11):手猜 COMP_PINS 已 purge(SCHEM_PINS 覆蓋全 23 元件,drift-gated);
  // 查無真孔位的 pin 走顯式 unmapped 均佈(WEST spread),不再消費手填座標。
  // P6.3/no-silent-fallback(a):SCHEM_PINS 是 derive_schematic_pins.py 衍生的 SSOT 表;
  // 缺載入時以空表續跑會「全元件零真孔」靜默降級(假腳位圖)→ fail-before-render。
  if (!window.SCHEM_PINS) throw new Error('[schematic-elk] SCHEM_PINS 未載入(v6/data/schematic-pins.js 須先於 elk-layout.js)— 拒絕以空腳位表渲染');
  const SCHEM_PINS = window.SCHEM_PINS;
  // 殘留 wiring pin 名 → SSOT canonical 名(真相在 SSOT,此處只補別名橋接)
  const _PIN_ALIAS = {
    AO: 'AOUT', DO: 'DOUT', SIG: 'SIGNAL', DATA: 'DIN',
    'BAT+': 'V+', 'BAT-': 'GND', 'V-': 'GND', '+': 'SIGNAL', ANODE: 'SIGNAL',
  };
  function _realPin(realPins, comp) {
    if (!realPins) return null;
    const want = (comp || '').toUpperCase();
    let sp = realPins.find(p => (p.name || '').toUpperCase() === want);
    if (!sp) {
      const a = _PIN_ALIAS[want];
      if (a) sp = realPins.find(p => (p.name || '').toUpperCase() === a.toUpperCase());
    }
    return sp || null;
  }
  // 真實 pin → port on the real edge（位置沿邊用 nx[水平邊]或 ny[垂直邊]）
  function realPinToPort(sp, w, h) {
    let s = sp.side;
    if (!s) {  // SSOT group side 未對應（如 'top_end' 不在 _SIDE_MAP）→ 由真實 nx/ny 取最近邊,
      // 不靜默丟到節點內部(no-silent-fallback:仍用 datasheet 真座標,只補推斷哪一邊)
      const d = [['WEST', sp.nx], ['EAST', 1 - sp.nx], ['NORTH', sp.ny], ['SOUTH', 1 - sp.ny]];
      d.sort((a, b) => a[1] - b[1]);
      s = d[0][0];
    }
    let px, py;
    if (s === 'NORTH') { px = sp.nx * w - PORT_W / 2; py = 0; }
    else if (s === 'SOUTH') { px = sp.nx * w - PORT_W / 2; py = h - PORT_W; }
    else if (s === 'WEST') { px = 0; py = sp.ny * h - PORT_W / 2; }
    else if (s === 'EAST') { px = w - PORT_W; py = sp.ny * h - PORT_W / 2; }
    else { return posToPort(sp.nx, sp.ny, w, h); }  // side 未知 → 退 normalized
    return {
      px: Math.max(0, Math.min(px, w - PORT_W)),
      py: Math.max(0, Math.min(py, h - PORT_W)),
      side: s,
    };
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
      const found = all.find(p => p.startsWith(pin + '/') || p.startsWith(pin + '~') || p === pin || p.split(/[/~]/).includes(pin));
      return found || pin;
    };
  }

  function buildElkGraph(mcuType, wiringData, powerPassives, nets) {
    window.resetSchematicTelemetry?.();  // VS: 每次重建重置接線 telemetry
    const ports = MCU_PORTS[mcuType] || MCU_PORTS.Arduino;
    const norm = _normPin(mcuType);

    const usedPins = new Set();
    const compNodes = [];
    const mcuPowerCaps = [];  // B: MCU 電源軌去耦/穩壓電容（畫成 MCU 旁徽章,非節點）
    const edges = [];
    const deferredEdges = [];
    const railNodes = {};   // 擬真 Stage 2/3:外部負載軌節點（EXT-PWR/EXT-GND/LOAD+/M1/M2/SPK…）
    const railEdges = [];
    let edgeId = 0;

    // 真相在 lib/wiring build_netlist 的 nets;render 過去只讀 wiring（MCU 星狀）,故外部軌
    // (EXT-PWR/EXT-GND/LOAD/M…) 的接線被靜默 continue 丟、galvanic isolation 不可見。此處:
    //  (a) nets 有同名 net 的非 MCU 目標 → 建外部軌節點接上（非丟;非 nets 軌仍走 drop telemetry）;
    //  (b) nets 的 EXT-GND 成員（負載側 GND）→ 改接 EXT-GND 軌,使兩地網路可見分離。
    const netNames = new Set((nets || []).map(n => n && n.name).filter(Boolean));
    const extGndPins = new Set();  // "compkey.pin"（小寫）
    const _extGndNet = (nets || []).find(n => n && n.name === 'EXT-GND');
    if (_extGndNet) for (const nd of (_extGndNet.nodes || [])) {
      if (nd && nd.side === 'comp') extGndPins.add(`${nd.ref}.${nd.pin}`.toLowerCase());
    }

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
      const spec = COMP_SPECS[compKey] || { label: compKey, sub: '', note: '', color: '#888' };  // nofallback-ok: COMP_SPECS lookup — display-only label/color fallback; unknown component gets key as label, #888 grey
      const compPorts = [];
      const coveredReal = new Set();  // Q4:已被 wiring 覆蓋的 SCHEM_PINS 腳名(避免未接腳重複建 port)
      const dims = COMP_DIMS[compKey];
      const compW = dims ? dims[0] : 130;  // nofallback-ok: UI render size only; unknown component gets 130px default width, no pipeline geometry impact
      // 有真實 datasheet 孔位(SCHEM_PINS)→ 用真實長寬比,勿因腳數把高灌大破壞外型比例
      // (如 Relay 50×26 被 5 隻腳灌成 100×100 正方);無真孔位才退回腳數撐高(避免 WEST-stack 重疊)。
      const _hasRealPins = !!SCHEM_PINS[compKey];
      const compH = dims
        ? (_hasRealPins ? dims[1] : Math.max(dims[1], 40 + info.pins.length * 12))
        : 60 + (info.pins.length > 3 ? (info.pins.length - 3) * 12 : 0);

      const realPins = SCHEM_PINS[compKey];  // 擬真 Stage 1:真實 I/O 孔位(SSOT 唯一來源)
      const unmappedPins = info.pins.filter(p => {
        if (p.mcu?.includes('.')) return false;
        return !_realPin(realPins, p.comp);
      });
      let unmappedIdx = 0;
      if (unmappedPins.length) {
        // P4.2:查無 SCHEM_PINS 真孔位 → 顯式均佈 + 警告 surface(不靜默用手填座標)
        console.warn(`[schematic-elk] ${compKey} 腳位查無 SCHEM_PINS 真孔: ${unmappedPins.map(p => p.comp).join(', ')} — 以 unmapped 均佈呈現`);
      }

      for (const pin of info.pins) {
        const portId = `${compKey}_${pin.comp}`;
        const realPin = _realPin(realPins, pin.comp);
        if (realPin) coveredReal.add((realPin.name || '').toUpperCase());  // Q4:記錄已接的真腳
        const uc = (pin.comp || '').toUpperCase();
        const compDir = pin.comp_dir || '';
        const isVcc = compDir === 'power'
          || uc === 'VCC' || uc === '5V' || uc === '3V3' || uc === 'VIN';
        const isGnd = compDir === 'gnd' || uc === 'GND';
        let px, py, side;

        if (realPin) {
          ({ px, py, side } = realPinToPort(realPin, compW, compH));
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

        // Normal MCU pin（或外部負載軌）
        let mcuPin = norm(pin.mcu);
        // 擬真 Stage 3:負載側 GND（nets 判定屬 EXT-GND 域）→ 改接 EXT-GND 軌,離開 MCU 邏輯地
        if (extGndPins.has(`${compKey}.${pin.comp}`.toLowerCase())) mcuPin = 'EXT-GND';
        const allMcuPins = new Set([...ports.north, ...ports.south, ...ports.west, ...ports.east]);
        if (!allMcuPins.has(mcuPin)) {
          // 外部負載軌:nets（build_netlist SSOT）有同名 net → 建軌節點接上,不靜默丟棄。
          if (netNames.has(mcuPin)) {
            const railIsGnd = /GND/i.test(mcuPin);
            if (!railNodes[mcuPin]) railNodes[mcuPin] = {
              id: `rail_${mcuPin}`, width: 64, height: 30, ports: [],
              layoutOptions: { 'portConstraints': 'FREE' },
              _meta: { isRail: true, railName: mcuPin, label: mcuPin, color: railIsGnd ? '#888' : '#ff8800' },
            };
            railEdges.push({
              id: `e${edgeId++}`, sources: [portId], targets: [`rail_${mcuPin}`],
              _meta: {
                type: railIsGnd ? 'gnd' : (isVcc ? 'vcc_bus' : 'power_source'),
                color: pin.color || (railIsGnd ? '#888' : '#ff8800'),
                compPin: pin.comp, mcuPin,
                compDir: pin.comp_dir || '', voltageDomain: pin.mcu_vd || pin.comp_vd || '',
                note: pin.note || '', isExtRail: true,
              },
            });
            window.recordSchematicRoute?.();  // VS: 外部軌接線=成功繪出
            continue;
          }
          // 非 nets 已知軌的未解 pin → 維持 no-silent-fallback 棄繪 telemetry
          console.warn(`[schematic-elk] ${compKey}.${pin.comp} → ${mcuPin} 不在 ${mcuType} MCU 白名單且非 nets 軌,該接線未繪`);
          window.recordSchematicDrop?.(compKey, pin.comp, mcuPin);  // VS: 收集棄繪
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
            const _rp = _realPin(realPins, pinName);  // 真孔位優先(與一般腳一致)
            const { px: spx, py: spy, side: sps } = _rp
              ? realPinToPort(_rp, compW, compH)
              : { px: compW - PORT_W, py: compH * 0.5 - PORT_W / 2, side: 'EAST' };  // P4.2:無真孔 → 顯式 EAST 預設(原手填 COMP_PINS 已 purge)
            if (_rp) coveredReal.add((_rp.name || '').toUpperCase());
            compPorts.push({
              id: srcPortId, width: PORT_W, height: PORT_W,
              x: spx, y: spy,
              properties: { 'port.side': sps },
            });
          }
        }
      }

      // Q4(2026-06-08):畫滿 datasheet 全腳 — SCHEM_PINS 中未被 wiring 覆蓋的腳(如 Relay NC)
      // 也建 port(真座標、無 edge、_meta.used=false dim),符合實體連接器全腳。
      if (realPins) {
        for (const sp of realPins) {
          if (coveredReal.has((sp.name || '').toUpperCase())) continue;
          if (compPorts.find(p => p.id === `${compKey}_${sp.name}`)) continue;
          const { px: ux, py: uy, side: us } = realPinToPort(sp, compW, compH);
          compPorts.push({
            id: `${compKey}_${sp.name}`, width: PORT_W, height: PORT_W,
            x: ux, y: uy,
            properties: { 'port.side': us },
            _meta: { label: sp.name, used: false },  // 未接腳:dim 標示
          });
        }
      }

      compNodes.push({
        id: compKey,
        width: compW, height: compH,
        ports: compPorts,
        layoutOptions: { 'portConstraints': 'FIXED_POS' },
        _meta: { ...spec, compKey, refdes: info.refdes || '', passives: compDecoupCaps },  // B: 去耦電容徽章;P3.2: active refdes 徽章(缺失空字串降級)
      });
    }

    edges.push(...deferredEdges);
    edges.push(...railEdges);  // 擬真:外部負載軌接線（EXT-PWR/EXT-GND/LOAD/M…）

    // B: MCU 電源軌被動電容(bulk 穩壓 + MCU 去耦) — 不插節點/不切走線,收進 MCU 徽章
    // Phase2 step5: 透傳 refdes + location 供前端 location 切顯示
    for (let pi = 0; pi < (powerPassives || []).length; pi++) {
      const cap = powerPassives[pi];
      if (!cap || cap.kind !== 'C') continue;
      mcuPowerCaps.push({ value: cap.value, role: cap.topo === 'bulk' ? 'bulk' : 'decoupling', refdes: cap.refdes || '', location: cap.location || 'onboard' });
    }

    // Build MCU ports — FIXED_POS using PCB datasheet coordinates
    const MCU_MM = { Arduino: [68.6, 53.4], ESP32: [51.4, 28.0], Microbit: [51.8, 42.0], RPi: [85.0, 56.0] };
    const boardMM = MCU_MM[mcuType] || [68.58, 53.34];  // nofallback-ok: UI render size only; unknown mcuType gets Arduino-size default; no pipeline geometry impact
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
    const pinMap = PCB_PIN_X[mcuType] || {};  // nofallback-ok: PCB_PIN_X optional fine-positioning table; missing mcuType falls back

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
        ...Object.values(railNodes),  // 擬真:外部負載軌節點
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
        color: w.color || '#888',  // nofallback-ok: optional UI wire color; #888 grey is decorative default, not a spec value
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
