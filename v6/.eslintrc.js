// ESLint config for v6 frontend
// Pattern: IIFE + window globals, no bundler, React/THREE via CDN globals
// ESLint 8.x (legacy config format — not flat config)
// INF2 (2): extends plugin:react/recommended + plugin:react-hooks/recommended

module.exports = {
  env: { browser: true, es2021: true },
  parserOptions: { ecmaVersion: 2021, ecmaFeatures: { jsx: true } },
  extends: ["plugin:react/recommended", "plugin:react-hooks/recommended"],
  plugins: ["react", "react-hooks"],
  globals: {
    // CDN globals — loaded before any v6 script
    React: "readonly", ReactDOM: "readonly", THREE: "readonly",
    // Project-level globals (window.* writes in store/api/adapters/etc.)
    Adapters: "readonly", SectionLabel: "readonly", shortLabel: "readonly",
    API: "readonly", PipelineStore: "readonly", ROLE_COLOR: "readonly",
    ElkSchematic: "readonly", ElkSchematicSVG: "readonly",
    CLARIFY_TIMEOUT_S: "readonly", parseBinarySTL: "readonly",
    COMPONENT_PRESETS: "readonly",
    // UI primitives (ui-primitives.jsx + evaluate-cards.jsx + tweaks-panel.jsx)
    Card: "readonly", Badge: "readonly", Spinner: "readonly",
    Skeleton: "readonly", ProgressBar: "readonly", ExtractSlot: "readonly",
    NoSwapFixCard: "readonly", PowerBudgetBar: "readonly",
    PowerGatePanel: "readonly", ResolveConfirmPanel: "readonly",
    ResumePhaseCard: "readonly", SpecWarningsPanel: "readonly",
    SwapFixCard: "readonly", TestCodePanel: "readonly",
    ValidationPanel: "readonly", VlmFixCard: "readonly",
    // Cross-IIFE shared helpers
    _panelBtnStyle: "readonly", _panelRowStyle: "readonly",
    _panelBtnBase: "readonly", _renderIssueItem: "readonly",
    _getHint: "readonly",
  },
  rules: {
    "no-unused-vars": ["warn", { "varsIgnorePattern": "^_", "argsIgnorePattern": "^_" }],
    "no-undef": "warn",
    // React global from CDN — no import needed
    "react/react-in-jsx-scope": "off",
    // No prop-types in this project
    "react/prop-types": "off",
    // IIFEs assigned to window need no displayName
    "react/display-name": "off",
    // " in JSX text — style preference, allow with warning
    "react/no-unescaped-entities": "warn",
    "react-hooks/rules-of-hooks": "error",
    "react-hooks/exhaustive-deps": "warn",
    "no-redeclare": "warn",
    "no-console": "off",
    "semi": ["warn", "always"],
  },
  settings: { react: { version: "18" } },
  overrides: [
    { files: ["hooks/use-three-renderer.js", "schematic-elk.jsx", "views-engage.jsx", "views-engineer-assembly.jsx", "views-engineer-assembly-v3.jsx"],
      rules: { "react-hooks/rules-of-hooks": "warn" } },
    { files: [".eslintrc.js", "**/*-fidelity.js"], env: { node: true } },
  ],
  ignorePatterns: ["node_modules/", "models/", "scripts/"],
};
