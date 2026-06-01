// ═══════════════════════════════════════════
// adapters.jsx — Transform backend data → view shapes
// ═══════════════════════════════════════════

(() => {
  const TAG_MAP = {
    'Brain': 'BRAIN', 'Power': 'POWER', 'Control': 'CONTROL',
    'Sensor': 'SENSOR', 'Output': 'OUTPUT', 'Comm': 'COMM',
    'Housing': 'HOUSING', 'Actuator': 'OUTPUT',
  };

  const ICON_MAP = {
    BRAIN: '◆', POWER: '⚡', CONTROL: '◇', SENSOR: '◈',
    OUTPUT: '▣', COMM: '⌁', HOUSING: '⊞', ACTUATOR: '▣',
  };

  function _roleTag(role) { return TAG_MAP[role] || role?.toUpperCase() || '?'; }
  function _roleIcon(role) { return ICON_MAP[_roleTag(role)] || '●'; }

  window.Adapters = {

    toProject(data, jobId) {
      return {
        name: data.project_name || '未命名專案',
        id: jobId || '',
        category: data.project_category || '',
        prompt: '',
        plan: data.cot_plan?.high_level_plan || '',
        generatedAt: new Date().toLocaleString('zh-TW'),
        iteration: 'v1.0',
        phase: data.phase || 1,
        printability: 0,
      };
    },

    toClarifyQuestions(cotPlan, components, originalPrompt, componentResolve) {
      if (!cotPlan && !components) return [];

      const questions = [];
      const hints = cotPlan?.parameter_hints || {};

      const hasWifi = (components || []).some(c =>
        /wifi|esp32|esp8266/i.test(c.type || c.part || '')
      );
      const hasBattery = (components || []).some(c =>
        /battery|solar|lipo|18650/i.test(c.type || c.part || '')
      );

      questions.push({
        id: 'q_env',
        label: '使用場景',
        question: '這個作品會在什麼環境下使用？',
        options: ['室內', '戶外', '陽台/半戶外', '其他'],
        selected: hints.environment || null,
      });

      if (hasWifi) {
        questions.push({
          id: 'q_conn',
          label: '連線需求',
          question: '需要什麼連線方式？',
          options: ['WiFi + 手機 App', 'Bluetooth 近距離', 'LoRa 長距離', '離線記錄'],
          selected: hints.connectivity || null,
        });
      }

      if (hasBattery) {
        questions.push({
          id: 'q_power',
          label: '電力來源',
          question: '偏好的供電方式？',
          options: ['太陽能 + 鋰電池', 'USB 插電', 'AA 電池', '其他'],
          selected: hints.power_source || null,
        });
      }

      // S9：數量歧義確認
      const qtyAmb = componentResolve?.qty_ambiguities || [];
      for (const amb of qtyAmb) {
        const label = (amb.type || '').replace(/-class$/, '');
        questions.push({
          id: `q_qty_${amb.type}`,
          label: `${label} 數量確認`,
          question: `${label}（${amb.role}）目前設定 ${amb.current_qty} 個，${amb.reason}。請確認實際需要的數量：`,
          options: ['1', '2', '3', '4', '5', String(amb.current_qty)],
          selected: String(amb.current_qty),
          _qty_confirm_type: amb.type,
        });
      }

      return questions;
    },

    toExtractSlots(components, roleAlternatives) {
      if (!components || !components.length) return [];
      const alts = roleAlternatives || {};

      const grouped = {};
      for (const c of components) {
        const role = c.role || 'Other';
        if (!grouped[role]) grouped[role] = [];
        grouped[role].push(c);
      }

      return Object.entries(grouped).map(([role, parts]) => {
        const primary = parts[0];
        const typeName = primary.type || primary.part || role;

        // 已選元件（PICK）
        const candidates = parts.map((p, i) => ({
          id: p.type || p.part || `${role}-${i}`,
          specs: [
            p.type || p.part,
            p.power_mw != null ? `${p.power_mw}mW` : null,
            p.pins != null ? `${p.pins} pins` : null,
          ].filter(Boolean),
          tags: [],
          score: i === 0 ? 90 : Math.max(50, 90 - i * 15),
          match: i === 0 ? 'LOCK ✓' : 'COMPARE',
        }));

        // 從 role_alternatives 補充替代候選（排除已在 PICK 的元件）
        const pickIds = new Set(candidates.map(c => c.id));
        const roleAlts = alts[role] || [];
        roleAlts.forEach((alt, altIdx) => {
          const altId = alt.type || alt.name;
          if (pickIds.has(altId)) return;
          candidates.push({
            id: altId,
            specs: [
              alt.name || alt.type,
              alt.power_mw ? `${alt.power_mw}mW` : null,
              alt.current_ma ? `${alt.current_ma}mA` : null,
            ].filter(Boolean),
            tags: [],
            score: Math.max(40, 75 - altIdx * 10),
            match: 'ALT',
            reason: alt.reason || '',
          });
        });

        return {
          label: `${role} · ${typeName.replace(/-class$/, '')}`,
          constraint: primary.reason || `${role} 元件`,
          pick: { id: typeName, badge: 'PICK' },
          candidates,
        };
      });
    },

    toPlanBullets(components) {
      if (!components || !components.length) return [];

      return components.map(c => ({
        tag: _roleTag(c.role),
        text: (c.type || c.part || '').replace(/-class$/, ''),
        detail: c.reason || '',
        edu: c.educational_rationale || '',
        icon: _roleIcon(c.role),
      }));
    },

    toBom(bomEntries) {
      if (!bomEntries || !bomEntries.length) return [];

      return bomEntries.map((b, i) => ({
        id: b.ref || b.id || `C${i + 1}`,
        role: b.role || 'Other',
        type: b.component || b.type || b.part || '',
        qty: b.qty || 1,
        current_ma: b.current_ma ?? b.total_ma ?? b.unit_ma ?? 0,
        voltage: b.voltage ?? 0,
        price: b.total_ntd ?? b.unit_ntd ?? b.price ?? b.price_ntd ?? 0,
        note: b.note || b.spec || '',
      }));
    },

    toEstimatedBom(components, subsystems) {
      const subs = subsystems || [];
      const comps = components || [];
      const src = subs.length ? subs : comps;
      if (!src.length) return [];

      return src.map((c, i) => {
        const powerMw = c.power_mw ?? 0;
        return {
          id: c.type || c.part || `C${i + 1}`,
          role: c.role || 'Other',
          type: (c.type || c.part || '').replace(/-class$/, ''),
          qty: c.qty || 1,
          current_ma: Math.round(powerMw / 5) || 0,
          voltage: 5,
          price: 0,
          note: powerMw ? `~${powerMw}mW est.` : '',
        };
      });
    },

    toWiring(wiringData) {
      if (!wiringData) return [];

      if (Array.isArray(wiringData)) return wiringData;

      // Phase III nested pin-based format: { "LED_RGB": { pins: [{comp, mcu, color}] } }
      const firstVal = Object.values(wiringData)[0];
      if (firstVal && firstVal.pins) {
        const flat = [];
        for (const [comp, info] of Object.entries(wiringData)) {
          for (const pin of (info.pins || [])) {
            flat.push({ from: pin.mcu, to: `${comp}.${pin.comp}`, net: pin.comp, color: pin.color || '#5ba4cf' });
          }
        }
        return flat;
      }

      const connections = wiringData.connections || wiringData.wiring || [];
      return connections.map(w => ({
        from: w.from || w.src || '',
        to: w.to || w.dst || '',
        net: w.net || w.signal || '',
        color: w.color || '#5ba4cf',
      }));
    },

    toFirmware(firmwareData) {
      if (!firmwareData) return { code: '', files: [] };

      if (typeof firmwareData === 'string') {
        return { code: firmwareData, files: [{ name: 'main.ino', role: 'Brain', loc: firmwareData.split('\n').length, content: firmwareData }] };
      }

      // API 回傳 {firmware: {code, lang, ext}, test_codes: {}} — 解開巢狀
      // 也支援扁平格式 {code, lang, ext, tests}
      const fwObj = (typeof firmwareData.firmware === 'object' && firmwareData.firmware) ? firmwareData.firmware : null;
      const code = fwObj?.code
        || (typeof firmwareData.firmware === 'string' ? firmwareData.firmware : '')
        || firmwareData.code
        || '';
      const lang = fwObj?.lang || firmwareData.lang || 'cpp';
      const ext = fwObj?.ext || firmwareData.ext || (lang === 'python' ? '.py' : '.ino');
      const brain = firmwareData.brain || 'Arduino';
      const tests = firmwareData.tests || firmwareData.test_codes || {};
      const mainName = `main${ext}`;
      const files = [{ name: mainName, role: 'Brain', loc: code.split('\n').length, content: code }];

      for (const [name, testData] of Object.entries(tests)) {
        const tc = typeof testData === 'string' ? testData : (testData?.code || '');
        const tl = typeof testData === 'string' ? 'cpp' : (testData?.lang || lang);
        const te = tl === 'python' ? '.py' : '.ino';
        files.push({
          name: `test_${name}${te}`,
          role: name,
          loc: tc ? tc.split('\n').length : 0,
          content: tc,
        });
      }

      return { code, files, lang, brain };
    },

    toEngineeringDecisions(decisions) {
      if (!decisions || !decisions.length) return [];

      return decisions.map(d => ({
        phase: d.phase || d['6e_stage'] || 'IV',
        category: d.category || d.step || '',
        description: d.description || d.detail || '',
        stem_concept: d.stem_concept || d.concept || d.principle || '',
      }));
    },

    toDecisionLog(trail) {
      if (!trail || !trail.length) return [];

      return trail.map(t => ({
        phase: t.phase || t.event_type || '',
        text: t.details ? (typeof t.details === 'string' ? t.details : JSON.stringify(t.details)) : t.text || '',
      }));
    },

    toConstraintChecks(checks, vlmVerification) {
      const result = [];

      if (checks && checks.length) {
        for (const c of checks) {
          result.push({
            cat: c.cat || 'OTHER',
            rule: c.rule || '',
            detail: c.detail || c.msg || '',
            status: (c.status || 'PASS').toUpperCase(),
          });
        }
      }

      if (vlmVerification) {
        const vlmFields = ['wall_integrity', 'io_cutouts', 'mounting_holes', 'printability'];
        for (const field of vlmFields) {
          if (vlmVerification[field] != null) {
            result.push({
              cat: 'VLM',
              rule: field.replace(/_/g, ' '),
              detail: typeof vlmVerification[field] === 'object'
                ? vlmVerification[field].detail || ''
                : String(vlmVerification[field]),
              status: vlmVerification[field]?.ok !== false ? 'PASS' : 'WARN',
            });
          }
        }
      }

      return result;
    },
  };
})();
