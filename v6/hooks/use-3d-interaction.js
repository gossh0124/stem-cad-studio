// ─── use-3d-interaction.js ─────────────────────────────────────────────────
// STR1: 3D 互動 hook（CSS transform / SVG 正交投影通用）
// 抽自 views-engineer.jsx use3DInteraction（第 7-56 行）
// window.use3DInteraction 掛載，供 Babel standalone 環境的所有 JSX 使用
// ──────────────────────────────────────────────────────────────────────────

window.use3DInteraction = function use3DInteraction(initialY = 35, initialX = 15) {
  const [rotY, setRotY] = React.useState(initialY);
  const [rotX, setRotX] = React.useState(initialX);
  const [dragging, setDragging] = React.useState(false);
  const [autoRotate, setAutoRotate] = React.useState(true);
  const dragRef = React.useRef({ sx: 0, sy: 0, startY: 0, startX: 0 });

  React.useEffect(() => {
    if (!autoRotate || dragging) return;
    const id = setInterval(() => setRotY(r => (r + 0.2) % 360), 50);
    return () => clearInterval(id);
  }, [autoRotate, dragging]);

  const onPointerDown = (e) => {
    setDragging(true);
    setAutoRotate(false);
    dragRef.current = { sx: e.clientX, sy: e.clientY, startY: rotY, startX: rotX };
    const onMove = (ev) => {
      const dx = ev.clientX - dragRef.current.sx;
      const dy = ev.clientY - dragRef.current.sy;
      // 拖曳跟手:拖右→物件右轉(相機左繞)。原 +dx 會使物件反向轉(左右相反 bug)。
      setRotY(dragRef.current.startY - dx * 0.5);
      setRotX(Math.max(-80, Math.min(80, dragRef.current.startX + dy * 0.3)));
    };
    const onUp = () => {
      setDragging(false);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const project = React.useCallback((x, y, z, cx0 = 250, cy0 = 200, scale = 1.2) => {
    const ry = (rotY * Math.PI) / 180;
    const rx = (rotX * Math.PI) / 180;
    const cy = Math.cos(ry), sy2 = Math.sin(ry);
    const cx = Math.cos(rx), sx = Math.sin(rx);
    const px = x * cy - z * sy2;
    const py = -(x * sy2 + z * cy) * sx + y * cx;
    return [cx0 + px * scale, cy0 + py * scale];
  }, [rotY, rotX]);

  const setView = React.useCallback((ry, rx) => {
    setAutoRotate(false);
    setRotY(ry);
    setRotX(rx);
  }, []);

  return { rotY, rotX, dragging, autoRotate, setAutoRotate, onPointerDown, project, setView };
};
