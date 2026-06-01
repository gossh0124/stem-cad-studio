// ─── use-three-renderer.js ─────────────────────────────────────────────────
// STR3: Three.js 初始化 hook（scene / camera / renderer / lights / ground）
// 抽自 views-engineer.jsx useThreeRenderer 初始化 effect
//      + views-engineer-assembly.jsx useAssemblyRenderer 初始化 effect
// window.useThreeBase 掛載，供 Babel standalone 環境的所有 JSX 使用
// ──────────────────────────────────────────────────────────────────────────

/**
 * window.useThreeBase — 初始化共用的 Three.js 場景
 *
 * @param {React.RefObject} containerRef  掛載目標 DOM
 * @param {object}          opts
 * @param {number}  opts.frust            正交投影半高（預設 1.3）
 * @param {number}  opts.hemiSkyInt       半球光強度（預設 0.75）
 * @param {boolean} opts.enableRimLight   是否加背面 rim light（預設 true）
 * @param {number}  opts.rimInt           rim light 強度（預設 0.4）
 * @param {number}  opts.dirInt           主方向光強度（預設 1.0）
 * @param {number}  opts.groundY          地面初始 Y 位置（預設 -1.5）
 * @param {number}  opts.groundSize       地面 PlaneGeometry 大小（預設 10）
 * @param {number}  opts.shadowOpacity    地面陰影不透明度（預設 0.18）
 * @returns {React.RefObject}  stateRef — { renderer, scene, camera, ground, dir, frust, ro }
 */
window.useThreeBase = function useThreeBase(containerRef, {
  frust = 1.3,
  hemiSkyInt = 0.75,
  enableRimLight = true,
  rimInt = 0.4,
  dirInt = 1.0,
  groundY = -1.5,
  groundSize = 10,
  shadowOpacity = 0.18,
} = {}) {
  const stateRef = React.useRef(null);

  React.useEffect(() => {
    const el = containerRef.current;
    if (!el || !window.THREE) return;
    const T = window.THREE;

    const w = el.clientWidth || 500;
    const h = el.clientHeight || 400;
    const aspect = w / h;

    // Renderer
    const renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = T.PCFSoftShadowMap;
    el.appendChild(renderer.domElement);
    Object.assign(renderer.domElement.style, {
      pointerEvents: 'none', position: 'absolute', inset: '0',
    });

    // Scene + Camera
    const scene = new T.Scene();
    const camera = new T.OrthographicCamera(
      -frust * aspect, frust * aspect, frust, -frust, 0.01, 100
    );
    camera.position.set(0, 0, 5);

    // 半球光（sky/ground 漸變）
    scene.add(new T.HemisphereLight(0xddeeff, 0x445566, hemiSkyInt));

    // 背面 rim light（凸顯透明殼體邊緣輪廓）
    if (enableRimLight) {
      const rim = new T.DirectionalLight(0xaaccff, rimInt);
      rim.position.set(-3, 2, -4);
      scene.add(rim);
    }

    // 主方向光（帶陰影）
    const dir = new T.DirectionalLight(0xffffff, dirInt);
    dir.position.set(3, 5, 4);
    dir.castShadow = true;
    dir.shadow.mapSize.set(1024, 1024);
    const sc = dir.shadow.camera;
    sc.near = 0.1; sc.far = 50;
    sc.left = -4; sc.right = 4; sc.top = 4; sc.bottom = -4;
    dir.shadow.bias = -0.002;
    scene.add(dir);

    // 地面陰影平面
    const ground = new T.Mesh(
      new T.PlaneGeometry(groundSize, groundSize),
      new T.ShadowMaterial({ opacity: shadowOpacity })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = groundY;
    ground.receiveShadow = true;
    scene.add(ground);

    // Resize Observer
    const ro = new ResizeObserver(() => {
      const w2 = el.clientWidth, h2 = el.clientHeight;
      if (!w2 || !h2) return;
      renderer.setSize(w2, h2);
      camera.left = -frust * (w2 / h2);
      camera.right = frust * (w2 / h2);
      camera.updateProjectionMatrix();
    });
    ro.observe(el);

    stateRef.current = { renderer, scene, camera, ground, dir, frust, ro };

    return () => {
      ro.disconnect();
      renderer.dispose();
      if (renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      stateRef.current = null;
    };
  }, []);  // 僅執行一次

  return stateRef;
};
