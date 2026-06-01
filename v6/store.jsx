// ════════════════════��══════════════════════
// store.jsx — Pipeline state management
// ══════════════════���════════════════════════

(() => {
  const INITIAL_STATE = {
    status: 'idle',
    jobId: null,
    error: null,
    currentPhase: 0,
    sseStatus: 'idle',
    phaseMessages: [],

    project: null,
    clarifyQuestions: [],
    componentResolve: null,
    components: [],

    extractSlots: [],

    planBullets: [],
    bom: [],
    powerBudget: null,
    constraintChecks: [],

    stlFiles: [],
    cadEngine: null,
    engineeringDecisions: [],
    enclosureSizing: null,
    roleAlternatives: {},
    componentPlacements: [],
    panelPlacements: [],      // v2 enclosure_relation=panel：殼面元件
    externalRefs: [],         // v2 enclosure_relation=external：殼外元件 + 線孔
    embeddedRefs: [],         // v2 enclosure_relation=embedded：沉入 host_structure
    thermalField: null,
    wireRoutes: [],
    enclosureSpec: null,
    sceneGraphV3: null,
    selectedComponentId: null,   // ADR-7 cross-view selection sync

    firmware: null,
    files: [],
    lang: 'cpp',
    brain: 'Arduino',
    wiring: [],
    decisionLog: [],

    hitlHistory: [],
    fixChoiceOptions: null,
    reflection: null,
    reflections: {},

    isCanned: false,        // 範本 canned demo mode（唯讀預覽）
    templateId: null,
    componentShells: [],

    // CH3 雙階段推理 debug 資訊（user 決策 2026-05-15：frontend 顯示）
    ch3_plan: null,         // 高層決策（layout / proportions / features）
    ch3_params: null,       // 低層決策（具體數值參數）
    ch3_source: null,       // 來源標記（'ch3_lora' / 'fallback' / 'planner_v2' 等）
  };

  let state = { ...INITIAL_STATE };
  const listeners = new Set();
  let _pipeline = null;

  function getState() { return state; }

  function _notify() {
    for (const fn of listeners) fn();
  }

  function _update(patch) {
    state = { ...state, ...patch };
    _notify();
  }

  // ── SSE event handlers ────────────────────────────────────

  function _handlePhaseData(data) {
    const phase = data.phase;
    const patch = { currentPhase: Math.max(state.currentPhase, phase) };

    if (phase === 1) {
      const newProject = Adapters.toProject(data, state.jobId);
      // 保留用戶原始輸入作為 prompt，AI 計畫文字存在 project.plan
      newProject.prompt = state.project?.prompt || newProject.prompt;
      // 從 parameter_hints + enclosure_sizing 組合 enclosure_constraints
      const hints = data.cot_plan?.parameter_hints || {};
      const sizing = data.enclosure_sizing || {};
      if (hints.material || sizing.max_dimension_mm) {
        newProject.enclosure_constraints = {
          material: hints.material || 'PLA',
          wall_thickness_mm: hints.wall_thickness_mm || 2.0,
          max_dimension_mm: sizing.max_dimension_mm || 150,
          target_size: sizing.target_size || hints.enclosure_size || 'compact',
          has_lid: hints.has_lid !== false,
        };
      }
      patch.project = newProject;
      patch.clarifyQuestions = Adapters.toClarifyQuestions(
        data.cot_plan, data.components, state.project?.prompt,
        data.component_resolve
      );
      patch.components = data.components || [];
      patch.planBullets = Adapters.toPlanBullets(data.components || []);
      patch.bom = Adapters.toEstimatedBom(
        data.components, data.cot_plan?.subsystems
      );
      if (data.enclosure_sizing) patch.enclosureSizing = data.enclosure_sizing;
      if (data.role_alternatives) patch.roleAlternatives = data.role_alternatives;
      if (data.component_resolve) patch.componentResolve = data.component_resolve;
      patch.status = 'waiting_clarify';
    }

    else if (phase === 2) {
      patch.components = data.components || state.components;
      patch.extractSlots = Adapters.toExtractSlots(
        data.components || [], state.roleAlternatives);
      patch.planBullets = Adapters.toPlanBullets(data.components || []);
      patch.status = 'running';
    }

    else if (phase === 3) {
      patch.bom = Adapters.toBom(data.bom || []);
      patch.powerBudget = data.power_budget || null;
      patch.components = data.components || state.components;
      if (data.constraint_checks) {
        patch.constraintChecks = Adapters.toConstraintChecks(data.constraint_checks, data.vlm_verification);
      }
      if (data.wiring) {
        patch.wiring = Adapters.toWiring(data.wiring);
      }
      patch.status = 'running';
    }

    else if (phase === 4) {
      patch.stlFiles = data.stl_files || [];
      patch.cadEngine = data.engine || null;
      if (data.job_id) patch.jobId = data.job_id;
      if (data.component_placements) patch.componentPlacements = data.component_placements;
      if (data.panel_placements) patch.panelPlacements = data.panel_placements;
      if (data.external_refs) patch.externalRefs = data.external_refs;
      if (data.embedded_refs) patch.embeddedRefs = data.embedded_refs;
      if (data.thermal_field) patch.thermalField = data.thermal_field;
      if (data.wire_routes) patch.wireRoutes = data.wire_routes;
      if (data.spec) patch.enclosureSpec = data.spec;
      // CH3 雙階段推理 debug 三欄（backend bridge.cad_output.ch3_*）
      if (data.ch3_plan !== undefined) patch.ch3_plan = data.ch3_plan;
      if (data.ch3_params !== undefined) patch.ch3_params = data.ch3_params;
      if (data.ch3_source !== undefined) patch.ch3_source = data.ch3_source;
      patch.status = 'running';
    }

    else if (phase === 6 && data.event_type === 'fix_choice') {
      patch.fixChoiceOptions = {
        phase,
        issues: data.issues || [],
        options: data.options || [],
        timeoutS: data.timeout_s != null ? data.timeout_s : 60,
        swapSuggestions: data.swap_suggestions || [],
        overbudgetDetail: data.overbudget_detail || null,
      };
      patch.status = 'waiting_hitl';
    }

    _update(patch);
  }

  function _handleProgress(message) {
    const patch = { phaseMessages: [...state.phaseMessages, message] };
    // 從 progress 訊息解析 phase number，即時更新 currentPhase
    const m = message.match(/\[Phase\s+(\d+|[IVX]+)\]/i);
    if (m) {
      const roman = { I: 1, II: 2, III: 3, IV: 4, V: 5, VI: 6, VII: 7 };
      const p = roman[m[1].toUpperCase()] || parseInt(m[1], 10) || 0;
      if (p > 0) patch.currentPhase = Math.max(state.currentPhase, p);
    }
    _update(patch);
  }

  function _handleDone(data) {
    const s = data.status;
    if (s === 'success') {
      _update({ status: 'done', error: null, sseStatus: 'idle' });
    } else if (s === 'waiting_clarify') {
      _update({ status: 'waiting_clarify', sseStatus: 'idle' });
    } else if (s === 'waiting_hitl' || s === 'waiting') {
      _update({ status: 'waiting_hitl', sseStatus: 'idle' });
    } else {
      _update({
        status: 'error',
        error: data.error || `Pipeline 結束，狀態：${s || 'unknown'}`,
        sseStatus: 'idle',
      });
    }
    _pipeline = null;
  }

  function _handleSSEError(err) {
    _update({
      status: 'error',
      error: err?.message || 'SSE 連線中斷',
      sseStatus: 'disconnected',
    });
    _pipeline = null;
  }

  // ── Dispatch ──────���───────────────────────────────────────

  function dispatch(action) {
    switch (action.type) {

      case 'RESUME_PIPELINE':
      case 'START_PIPELINE': {
        if (_pipeline) _pipeline.close();
        const isResume = action.type === 'RESUME_PIPELINE';

        if (isResume) {
          _update({ status: 'connecting', sseStatus: 'connecting', error: null, currentPhase: (action.resumeFrom || 1) - 1 });
        } else {
          const { project, instruction } = action;
          _update({ ...INITIAL_STATE, status: 'connecting', sseStatus: 'connecting', project: { prompt: instruction, name: project || instruction.slice(0, 30) } });
        }

        const pipeOpts = isResume
          ? { resumeJobId: action.jobId, resumeFrom: action.resumeFrom }
          : (action.opts || {});
        _pipeline = API.startPipeline(
          isResume ? (state.project?.name || 'resume') : action.project,
          isResume ? (state.project?.prompt || '') : action.instruction,
          pipeOpts,
        );
        _pipeline
          .on('onStart', (d) => _update({ jobId: d.job_id, status: 'running', sseStatus: 'connected' }))
          .on('onPhaseData', _handlePhaseData)
          .on('onProgress', _handleProgress)
          .on('onDone', _handleDone)
          .on('onError', _handleSSEError)
          .on('onReconnect', () => {
            _update({ sseStatus: 'reconnecting' });
            if (state.jobId) {
              API.getBridge(state.jobId).then(bridge => {
                if (bridge) dispatch({ type: 'RESTORE_FROM_JOB', payload: { job_id: state.jobId, status: state.status, current_phase: state.currentPhase }, bridge });
                _update({ sseStatus: 'connected' });
              }).catch(() => _update({ sseStatus: 'connected' }));
            }
          });

        _saveSession();
        break;
      }

      case 'SSE_PHASE_DATA':
        _handlePhaseData(action.payload);
        break;

      case 'SSE_PROGRESS':
        _handleProgress(action.payload);
        break;

      case 'SSE_DONE':
        _handleDone(action.payload);
        break;

      case 'SSE_ERROR':
        _handleSSEError(action.payload);
        break;

      case 'CLARIFY_CONFIRMED':
        _update({ status: 'running' });
        break;

      case 'HITL_SUBMIT':
        _update({ fixChoiceOptions: null });
        break;

      case 'SET_FIRMWARE':
        _update({
          firmware: action.payload.code || action.payload,
          files: action.payload.files || state.files,
          lang: action.payload.lang || state.lang,
          brain: action.payload.brain || state.brain,
        });
        break;

      case 'SET_WIRING':
        _update({ wiring: Adapters.toWiring(action.payload) });
        break;

      case 'SET_TRAIL':
        _update({ decisionLog: Adapters.toDecisionLog(action.payload) });
        break;

      case 'SET_ENGINEERING_DECISIONS':
        _update({ engineeringDecisions: Adapters.toEngineeringDecisions(action.payload) });
        break;

      case 'SWAP_EXTRACT_PICK': {
        const { slotLabel, candidateId } = action;
        const newSlots = state.extractSlots.map(s => {
          if (s.label !== slotLabel) return s;
          const newPick = s.candidates.find(c => c.id === candidateId);
          return newPick ? { ...s, pick: newPick } : s;
        });
        const newComponents = state.components.map(c => {
          if (c.role !== slotLabel) return c;
          return { ...c, type: candidateId, part: candidateId.replace(/-class$/, '') };
        });
        _update({ extractSlots: newSlots, components: newComponents, planBullets: Adapters.toPlanBullets(newComponents) });
        break;
      }

      case 'LOAD_CANNED': {
        // 範本 canned demo：載入 v6/canned/{id}.json 至 store，唯讀
        const bridge = action.bridge || {};
        const tplId = action.templateId || null;
        const patch = {
          jobId: null,
          status: 'done',
          currentPhase: bridge.checkpoint_phase || 5,
          error: null,
          isCanned: true,
          templateId: tplId,
          phaseMessages: [],
          fixChoiceOptions: null,
        };
        if (bridge.project_name) {
          patch.project = Adapters.toProject({
            project_name: bridge.project_name,
            project_category: bridge.project_category,
            cot_plan: bridge.cot_plan,
            components: bridge.components,
          }, null);
          patch.project.prompt = bridge._instruction || patch.project.prompt;
        }
        if (bridge.components) {
          patch.components = bridge.components;
          patch.planBullets = Adapters.toPlanBullets(bridge.components);
          patch.extractSlots = Adapters.toExtractSlots(bridge.components, bridge.role_alternatives || {});
          patch.roleAlternatives = bridge.role_alternatives || {};
        }
        // Clarify 預選答案（從 cot_plan.parameter_hints 推導）
        patch.clarifyQuestions = Adapters.toClarifyQuestions(
          bridge.cot_plan, bridge.components,
          bridge._instruction || '', null,
        );
        if (bridge.bom) patch.bom = Adapters.toBom(bridge.bom);
        if (bridge.power_budget) patch.powerBudget = bridge.power_budget;
        if (bridge.enclosure_sizing) patch.enclosureSizing = bridge.enclosure_sizing;
        if (bridge.wiring) patch.wiring = Adapters.toWiring(bridge.wiring);
        // Phase IV CAD output（case + assembly）
        if (bridge.cad_output) {
          const co = bridge.cad_output;
          patch.stlFiles = [];
          if (co.bottom_stl) patch.stlFiles.push({ name: co.bottom_stl.split('/').pop(), label: '底座', url: co.bottom_stl });
          if (co.lid_stl) patch.stlFiles.push({ name: co.lid_stl.split('/').pop(), label: '頂蓋', url: co.lid_stl });
          patch.cadEngine = co.engine || 'build123d';
          if (co.component_placements) patch.componentPlacements = co.component_placements;
          if (co.panel_placements) patch.panelPlacements = co.panel_placements;
          if (co.external_refs) patch.externalRefs = co.external_refs;
          if (co.embedded_refs) patch.embeddedRefs = co.embedded_refs;
          if (co.thermal_field) patch.thermalField = co.thermal_field;
          if (co.wire_routes) patch.wireRoutes = co.wire_routes;
          if (co.spec) patch.enclosureSpec = co.spec;
          if (co.component_shells) patch.componentShells = co.component_shells;
          // CH3 雙階段 debug（canned demo 也含）
          if (co.ch3_plan !== undefined) patch.ch3_plan = co.ch3_plan;
          if (co.ch3_params !== undefined) patch.ch3_params = co.ch3_params;
          if (co.ch3_source !== undefined) patch.ch3_source = co.ch3_source;
          // Assembly V3 SceneGraph
          if (co.scene_graph_v3) patch.sceneGraphV3 = co.scene_graph_v3;
          // Engineering Notebook decisions (canned bridges store them here)
          if (co.decisions) patch.engineeringDecisions = Adapters.toEngineeringDecisions(co.decisions);
        }
        _update(patch);
        break;
      }

      case 'RESTORE_FROM_JOB': {
        const job = action.payload;
        const bridge = action.bridge || {};
        const patch = {
          jobId: job.job_id,
          status: _mapJobStatus(job.status),
          currentPhase: job.current_phase || 0,
          error: job.error || null,
        };
        if (bridge.project_name) {
          patch.project = Adapters.toProject({
            project_name: bridge.project_name,
            project_category: bridge.project_category,
            cot_plan: bridge.cot_plan,
            components: bridge.components,
          }, job.job_id);
        }
        if (bridge.components) {
          patch.components = bridge.components;
          patch.planBullets = Adapters.toPlanBullets(bridge.components);
          patch.extractSlots = Adapters.toExtractSlots(bridge.components);
        }
        if (bridge.bom) patch.bom = Adapters.toBom(bridge.bom);
        if (bridge.power_budget) patch.powerBudget = bridge.power_budget;
        if (bridge.cad_output) {
          const co = bridge.cad_output;
          patch.stlFiles = [];
          if (co.bottom_stl) patch.stlFiles.push({ name: co.bottom_stl.split('/').pop(), label: '底座' });
          if (co.lid_stl) patch.stlFiles.push({ name: co.lid_stl.split('/').pop(), label: '頂蓋' });
          patch.cadEngine = co.engine || null;
          if (co.component_placements) patch.componentPlacements = co.component_placements;
          if (co.panel_placements) patch.panelPlacements = co.panel_placements;
          if (co.external_refs) patch.externalRefs = co.external_refs;
          if (co.embedded_refs) patch.embeddedRefs = co.embedded_refs;
          if (co.thermal_field) patch.thermalField = co.thermal_field;
          if (co.wire_routes) patch.wireRoutes = co.wire_routes;
          if (co.spec) patch.enclosureSpec = co.spec;
          // CH3 雙階段 debug（resume / reconnect 時保留）
          if (co.ch3_plan !== undefined) patch.ch3_plan = co.ch3_plan;
          if (co.ch3_params !== undefined) patch.ch3_params = co.ch3_params;
          if (co.ch3_source !== undefined) patch.ch3_source = co.ch3_source;
          if (co.scene_graph_v3) patch.sceneGraphV3 = co.scene_graph_v3;
        }
        if (bridge.engineering_decisions) {
          patch.engineeringDecisions = Adapters.toEngineeringDecisions(bridge.engineering_decisions);
        }
        _update(patch);
        break;
      }

      case 'SET_REFLECTION': {
        const r = { ...(state.reflections || {}), [action.key]: action.value };
        _update({ reflections: r });
        break;
      }

      // ADR-7: cross-view component selection
      case 'SELECT_COMPONENT':
        _update({ selectedComponentId: action.payload });
        break;

      case 'DESELECT_COMPONENT':
        _update({ selectedComponentId: null });
        break;

      case 'RESET':
        if (_pipeline) _pipeline.close();
        _pipeline = null;
        _update({ ...INITIAL_STATE });
        _clearSession();
        break;
    }
  }

  const _JOB_STATUS = { pending: 'connecting', running: 'running', waiting_clarify: 'waiting_clarify', waiting_hitl: 'waiting_hitl', success: 'done', failed: 'error', cancelled: 'error' };
  function _mapJobStatus(s) { return _JOB_STATUS[s] || 'idle'; }

  // ── Session persistence ───────────────────────────────────
  const SESSION_KEY = 'cadhllm_session';
  function _saveSession() { try { if (state.jobId) localStorage.setItem(SESSION_KEY, JSON.stringify({ jobId: state.jobId })); } catch (_) {} }
  function _clearSession() { try { localStorage.removeItem(SESSION_KEY); } catch (_) {} }

  function restoreSession() {
    try {
      const raw = localStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      const { jobId } = JSON.parse(raw);
      if (!jobId) return null;
      return API.getJob(jobId).then((job) => {
        if (!job || job.status === 'cancelled') { _clearSession(); return null; }
        return API.getBridge(jobId).then((bridge) => {
          dispatch({ type: 'RESTORE_FROM_JOB', payload: job, bridge: bridge || {} });
          return job;
        });
      }).catch(() => { _clearSession(); return null; });
    } catch (_) { return null; }
  }

  // ── React hook + Exports ──────────────────────────────────
  function subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); }
  function usePipelineStore(selector) { const sel = selector || getState; return React.useSyncExternalStore(subscribe, () => sel(getState())); }

  window.INITIAL_STATE = INITIAL_STATE;
  window.PipelineStore = { getState, dispatch, subscribe, restoreSession };
  window.usePipelineStore = usePipelineStore;
})();
