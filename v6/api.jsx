// ═══════════════════════════════════════════
// api.jsx — CADHLLM API client layer
// ═══════════════════════════════════════════

(() => {
  const BASE = window.CADHLLM_API_BASE || window.location.origin;

  class ApiError extends Error {
    constructor(status, detail) {
      super(detail || `HTTP ${status}`);
      this.status = status;
      this.detail = detail;
    }
  }

  async function _fetch(path, opts = {}) {
    const url = `${BASE}${path}`;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    if (!res.ok) {
      let detail;
      try { detail = (await res.json()).detail; } catch (_) { detail = res.statusText; }
      throw new ApiError(res.status, detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function _qs(params) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') p.set(k, v);
    }
    return p.toString() ? `?${p}` : '';
  }

  // ── SSE Pipeline ──────────────────────────────────────────

  function startPipeline(project, instruction, { maxVlmRounds = 3, resumeJobId, resumeFrom } = {}) {
    const qs = _qs({
      project, instruction, max_vlm_rounds: maxVlmRounds,
      resume_job_id: resumeJobId || '', resume_from: resumeFrom || 0,
    });
    const url = `${BASE}/api/generate${qs}`;

    let es = null;
    let retries = 0;
    const MAX_RETRIES = 3;
    const callbacks = { onPhaseData: null, onProgress: null, onDone: null, onError: null, onStart: null };

    function connect() {
      es = new EventSource(url);

      es.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          const event = data.event;

          if (event === 'start' && callbacks.onStart) {
            callbacks.onStart(data);
          } else if (event === 'phase_data' && callbacks.onPhaseData) {
            callbacks.onPhaseData(data);
          } else if (event === 'progress' && callbacks.onProgress) {
            callbacks.onProgress(data.message);
          } else if (event === 'done') {
            if (callbacks.onDone) callbacks.onDone(data);
            es.close();
          }
        } catch (err) { console.warn('[SSE] parse error:', err, evt.data); }
      };

      es.onerror = () => {
        es.close();
        if (retries < MAX_RETRIES) {
          const delay = Math.pow(2, retries + 1) * 1000;
          retries++;
          // 重連時通知 store 同步 bridge 狀態
          if (callbacks.onReconnect) callbacks.onReconnect(retries);
          setTimeout(connect, delay);
        } else if (callbacks.onError) {
          callbacks.onError(new Error('SSE 連線失敗，已重試 3 次'));
        }
      };
    }

    connect();

    return {
      on(event, fn) { callbacks[event] = fn; return this; },
      close() { if (es) es.close(); },
      get source() { return es; },
    };
  }

  // ── REST endpoints ────────────────────────────────────────

  // shell mesh 載一次快取：key = `${compType}/${variant}` → Promise<ArrayBuffer|null>
  // 跨 view 重掛、同 type 多模組共用，避免重複 fetch（對齊「載一次」目標）。
  const _shellCache = new Map();
  // S5(b): manifest 快取 — 先查 meta.available_variants，避免對缺漏 variant 發 404 請求
  // key = compType → Promise<Set<string>|null>（null 代表 meta 不存在）
  const _manifestCache = new Map();
  // Phase 3C: datasheet 快取 — closure 綁定，避免呼叫端 destructure 後 this===undefined 炸
  // key = className → Promise<DatasheetSpec|null>
  const _datasheetCache = new Map();

  const API = {
    BASE,
    ApiError,
    startPipeline,

    createJob(projectName, instruction, opts = {}) {
      return _fetch('/api/v1/jobs', {
        method: 'POST',
        body: JSON.stringify({
          project_name: projectName,
          instruction,
          max_rounds: opts.maxRounds || 3,
          timeout_s: opts.timeoutS || 300,
        }),
      });
    },

    getJob(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}`);
    },

    listJobs(status, limit = 50, saved = undefined) {
      return _fetch(`/api/v1/jobs${_qs({ status, limit, saved })}`);
    },

    deleteJob(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}`, { method: 'DELETE' });
    },

    saveJob(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/save`, { method: 'POST' });
    },

    unsaveJob(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/save`, { method: 'DELETE' });
    },

    getBridge(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/bridge`);
    },

    getCheckpoint(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/checkpoint`);
    },

    confirmClarify(jobId, answers) {
      return _fetch(`/api/v1/jobs/${jobId}/confirm_clarify`, {
        method: 'POST',
        body: JSON.stringify({ answers }),
      });
    },

    sendHitl(jobId, action, params = {}, stepId) {
      return _fetch(`/api/v1/jobs/${jobId}/hitl`, {
        method: 'POST',
        body: JSON.stringify({ action, params, step_id: stepId }),
      });
    },

    sendHitlBatch(jobId, corrections) {
      return _fetch(`/api/v1/jobs/${jobId}/hitl/batch`, {
        method: 'POST',
        body: JSON.stringify({ corrections }),
      });
    },

    respondBreakpoint(jobId, breakpointId, value = '') {
      return _fetch(`/api/v1/jobs/${jobId}/breakpoint`, {
        method: 'POST',
        body: JSON.stringify({ breakpoint_id: breakpointId, value }),
      });
    },

    respondFixChoice(jobId, choiceId, selectedSwaps = []) {
      return _fetch(`/api/v1/jobs/${jobId}/fix-choice`, {
        method: 'POST',
        body: JSON.stringify({ choice_id: choiceId, selected_swaps: selectedSwaps }),
      });
    },

    resumeJob(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/resume`, { method: 'POST' });
    },

    getTrail(jobId) {
      return _fetch(`/api/v1/jobs/${jobId}/trail`);
    },

    getComponents() {
      return _fetch('/api/v1/components');
    },

    getWiring(brain, outputs = [], sensors = []) {
      return _fetch('/api/v1/wiring', {
        method: 'POST',
        body: JSON.stringify({ brain, outputs, sensors }),
      });
    },

    getSchematic(brain, power, outputs = [], sensors = []) {
      return _fetch('/api/v1/schematic', {
        method: 'POST',
        body: JSON.stringify({ brain, power, outputs, sensors }),
      });
    },

    getFirmware(brain, power, outputs = [], sensors = [], meta = {}) {
      return _fetch('/api/v1/firmware', {
        method: 'POST',
        body: JSON.stringify({
          brain, power, outputs, sensors,
          project_name: meta.project_name || '',
          plan: meta.plan || '',
        }),
      });
    },

    // ── User Components (U5) ────────────────────────────────

    listUserComponents() {
      return _fetch('/api/v1/user-components');
    },

    addUserComponent(spec) {
      return _fetch('/api/v1/user-components', {
        method: 'POST',
        body: JSON.stringify(spec),
      });
    },

    getUserComponent(className) {
      return _fetch(`/api/v1/user-components/${encodeURIComponent(className)}`);
    },

    deleteUserComponent(className) {
      return _fetch(`/api/v1/user-components/${encodeURIComponent(className)}`, {
        method: 'DELETE',
      });
    },

    // ── WebSocket ──────────────────────────────────────────

    connectWS(jobId) {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const host = new URL(BASE).host || window.location.host;
      const ws = new WebSocket(`${proto}://${host}/ws/${jobId}`);
      const cbs = {};
      let pingInterval = null;

      ws.onopen = () => {
        pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 25000);
      };

      ws.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.event && cbs[data.event]) cbs[data.event](data);
          if (cbs._any) cbs._any(data);
        } catch (err) { console.warn('[SSE] parse error:', err, evt.data); }
      };

      ws.onclose = () => { if (pingInterval) clearInterval(pingInterval); };

      return {
        ws,
        on(event, fn) { cbs[event] = fn; return this; },
        close() { ws.close(); },
      };
    },

    // ── URL builders ──────────────────────────────────────

    stlUrl(jobId, filename) {
      return `${BASE}/api/stl/${jobId}/${filename}`;
    },

    artifactUrl(kind, jobId) {
      return `${BASE}/api/artifact/${kind}${_qs({ project_id: jobId })}`;
    },

    // ── Shell API ────────────────────────────────────────

    getShellMeta(compType) {
      return _fetch(`/api/shells/${encodeURIComponent(compType)}/meta`).catch(() => null);
    },

    // ── Datasheet SSOT API（Phase 3C） ─────────────────────
    // data/component_datasheet_verified.json 為單一真值；runtime fetch 結構化資料
    // 衍生邏輯在 v6/data/datasheet-derive.js（window.deriveDimsFromDatasheet）
    // P5.1: cache 改 closure 綁定，呼叫端 destructure 也安全
    getDatasheet(className) {
      if (_datasheetCache.has(className)) return _datasheetCache.get(className);
      const p = _fetch(`/api/v1/datasheet/${encodeURIComponent(className)}`).catch(() => null);
      p.catch(() => _datasheetCache.delete(className));
      _datasheetCache.set(className, p);
      return p;
    },
    listDatasheetClasses() {
      return _fetch('/api/v1/datasheet').then(d => d?.classes || []).catch(() => []);
    },

    // S5(b): manifest 預檢 — 由 meta.available_variants 衍生 Set，缺漏 variant 不發 fetch
    _getShellManifest(compType) {
      if (_manifestCache.has(compType)) return _manifestCache.get(compType);
      const p = (async () => {
        const meta = await this.getShellMeta(compType);
        if (!meta || !Array.isArray(meta.available_variants)) return null;
        return new Set(meta.available_variants);
      })();
      p.catch(() => _manifestCache.delete(compType));
      _manifestCache.set(compType, p);
      return p;
    },

    getShellSTL(compType, variant) {
      const key = `${compType}/${variant || 'base'}`;
      if (_shellCache.has(key)) return _shellCache.get(key);
      const p = (async () => {
        // S5(b): 先查 manifest；variant 不在清單就直接回 null，避免 404
        const manifest = await this._getShellManifest(compType);
        const vname = variant || 'base';
        if (manifest && !manifest.has(vname)) return null;
        const q = variant ? `?variant=${variant}` : '';
        const r = await fetch(`${BASE}/api/shells/${encodeURIComponent(compType)}/stl${q}`);
        if (r.status === 404) return null;   // 此 variant 不存在 — 正常 N/A，回 null
        if (!r.ok) throw new ApiError(r.status, `getShellSTL: HTTP ${r.status}`); // 真錯仍拋（禁容錯）
        const buf = await r.arrayBuffer();
        // 標記格式：GLB 以 'glTF' magic (0x46546C67) 開頭
        const magic = new Uint32Array(buf.slice(0, 4))[0];
        buf._isGLB = (magic === 0x46546C67);
        return buf;
      })();
      // 失敗（真錯）即從快取移除，允許之後重試；不快取 rejection 卡死
      p.catch(() => _shellCache.delete(key));
      _shellCache.set(key, p);  // 快取 Promise → 併發去重 + 跨重掛重用
      return p;
    },

    async listShells() {
      const d = await _fetch('/api/shells').catch(() => null);
      return d?.shells || [];
    },
  };

  // ── Binary STL Parser ──────────────────────────────────

  function parseBinarySTL(buffer) {
    const dv = new DataView(buffer);
    // GLB magic 'glTF'(0x46546C67）→ 非 STL，明確報錯而非讓 DataView 讀爆界（VS-FE）
    if (buffer.byteLength >= 4 && dv.getUint32(0, true) === 0x46546C67)
      throw new Error('parseBinarySTL: buffer 是 GLB 非 binary STL（應走 parseGLB）');
    const triCountRaw = dv.getUint32(80, true);
    // bounds-check：header 宣稱三角數須與 buffer 大小相符；截斷/壞檔則夾到可容範圍，不讀爆界
    const triCount = Math.min(triCountRaw, Math.max(Math.floor((buffer.byteLength - 84) / 50), 0));
    const triangles = [];
    let offset = 84;
    for (let i = 0; i < triCount; i++) {
      const nx = dv.getFloat32(offset, true);
      const ny = dv.getFloat32(offset + 4, true);
      const nz = dv.getFloat32(offset + 8, true);
      const v = [];
      for (let j = 0; j < 3; j++) {
        const base = offset + 12 + j * 12;
        v.push([
          dv.getFloat32(base, true),
          dv.getFloat32(base + 4, true),
          dv.getFloat32(base + 8, true),
        ]);
      }
      triangles.push({ normal: [nx, ny, nz], vertices: v });
      offset += 50;
    }
    return triangles;
  }

  // ── GLB Parser（提取 per-mesh 頂點 + 顏色）─────────────
  // 回傳 [{ positions: Float32Array, indices: Uint16/32Array, color: [r,g,b,a] }, ...]
  function parseGLB(buffer) {
    const dv = new DataView(buffer);
    // GLB header: magic(4) + version(4) + length(4)
    const magic = dv.getUint32(0, true);
    if (magic !== 0x46546C67) throw new Error(`Not a GLB file (magic: 0x${magic.toString(16)})`);
    const jsonLen = dv.getUint32(12, true);  // chunk0 length
    const jsonBytes = new Uint8Array(buffer, 20, jsonLen);
    const json = JSON.parse(new TextDecoder().decode(jsonBytes));

    // chunk1: BIN
    const binOffset = 20 + jsonLen + 8; // +8 for chunk1 header
    const bin = buffer.slice(binOffset);

    const meshes = [];
    const accessors = json.accessors || [];
    const bufferViews = json.bufferViews || [];

    function getAccessorData(accIdx, Ctor) {
      const acc = accessors[accIdx];
      const bv = bufferViews[acc.bufferView];
      const byteOff = (bv.byteOffset || 0) + (acc.byteOffset || 0);
      return new Ctor(bin, byteOff, acc.count * (acc.type === 'VEC3' ? 3 : acc.type === 'VEC4' ? 4 : 1));
    }

    for (const mesh of (json.meshes || [])) {
      for (const prim of (mesh.primitives || [])) {
        const entry = {};
        // 位置
        if (prim.attributes?.POSITION !== undefined) {
          entry.positions = getAccessorData(prim.attributes.POSITION, Float32Array);
        }
        // 索引
        if (prim.indices !== undefined) {
          const idxAcc = accessors[prim.indices];
          const IdxCtor = idxAcc.componentType === 5125 ? Uint32Array : Uint16Array;
          entry.indices = getAccessorData(prim.indices, IdxCtor);
        }
        // 法線
        if (prim.attributes?.NORMAL !== undefined) {
          entry.normals = getAccessorData(prim.attributes.NORMAL, Float32Array);
        }
        // 材質顏色
        entry.color = [0, 84, 107, 255]; // default teal
        if (prim.material !== undefined) {
          const mat = (json.materials || [])[prim.material];
          const pbr = mat?.pbrMetallicRoughness;
          if (pbr?.baseColorFactor) {
            const [r, g, b, a] = pbr.baseColorFactor;
            entry.color = [Math.round(r*255), Math.round(g*255), Math.round(b*255), Math.round((a||1)*255)];
          }
        }
        // COLOR_0 頂點色（trimesh face_colors 匯出至此）
        if (prim.attributes?.COLOR_0 !== undefined) {
          try {
            const cAcc = accessors[prim.attributes.COLOR_0];
            const isFloat = cAcc.componentType === 5126;
            const Ctor = isFloat ? Float32Array : Uint8Array;
            const cData = getAccessorData(prim.attributes.COLOR_0, Ctor);
            const n = cAcc.type === 'VEC4' ? 4 : 3;
            if (cData.length >= n) {
              const sc = isFloat ? 255 : 1;
              entry.color = [
                Math.round(cData[0] * sc),
                Math.round(cData[1] * sc),
                Math.round(cData[2] * sc),
                n >= 4 ? Math.round(cData[3] * sc) : 255,
              ];
            }
          } catch (_) {}
        }
        if (entry.positions) meshes.push(entry);
      }
    }
    return meshes;
  }

  // ── Parsed geometry cache (shared between Components and Assembly views) ──
  // Caches parse results (GLB parts / STL triangles) by compType/variant key.
  // Both views consume the same parsed data, avoiding re-parse and ensuring
  // identical source data for consistent rendering.
  const _parsedGeoCache = new Map();

  function getParsedGeometry(compType, variant) {
    const key = `${compType}/${variant}`;
    if (_parsedGeoCache.has(key)) return _parsedGeoCache.get(key);
    const p = (async () => {
      const buf = await API.getShellSTL(compType, variant);
      if (!buf) return null;
      const magic = new Uint32Array(buf.slice(0, 4))[0];
      const isGLB = magic === 0x46546C67;
      if (isGLB) {
        const parts = parseGLB(buf);
        return parts?.length ? { isGLB: true, parts } : null;
      }
      const tris = parseBinarySTL(buf);
      return tris?.length ? { isGLB: false, triangles: tris } : null;
    })();
    p.catch(() => _parsedGeoCache.delete(key));
    _parsedGeoCache.set(key, p);
    return p;
  }

  window.API = API;
  window.parseBinarySTL = parseBinarySTL;
  window.parseGLB = parseGLB;
  window.getParsedGeometry = getParsedGeometry;
})();
