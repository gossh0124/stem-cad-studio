// ═══════════════════════════════════════════
// config/stages-6e.js — 6E stage definitions
// STR5: extracted from shell.jsx
// ═══════════════════════════════════════════

(() => {
  window.STAGES_6E = [
    { id: 'engage',   label: 'Engage',   zh: '激發興趣', color: 'var(--6e-engage)',   views: ['idle'] },
    { id: 'explore',  label: 'Explore',  zh: '需求探索', color: 'var(--6e-explore)',  views: ['clarify', 'extract'] },
    { id: 'explain',  label: 'Explain',  zh: '原理釐清', color: 'var(--6e-explain)',  views: ['plan', 'schematic'] },
    { id: 'engineer', label: 'Engineer', zh: '工程實踐', color: 'var(--6e-engineer)', views: ['components-3d', 'assembly'] },
    { id: 'enrich',   label: 'Enrich',   zh: '延伸學習', color: 'var(--6e-enrich)',   views: ['code', 'bom', 'user-components'] },
    { id: 'evaluate', label: 'Evaluate', zh: '驗證改進', color: 'var(--6e-evaluate)', views: ['evaluate'] },
  ];
})();
