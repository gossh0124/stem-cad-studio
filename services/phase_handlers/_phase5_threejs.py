"""Three.js HTML generation helpers for Phase 5.

Extracted from phase5_handler.py to keep files under 500 lines.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Callable, List, Optional

from ..shared.models import Job

_THREEJS_CDN = "https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"
_ORBIT_CDN   = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"
_STL_CDN     = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"

_INJECT_MARKER = "<!-- THREE_JS_INJECT -->"


def build_threejs_html(
    bottom_stl: Optional[str],
    lid_stl: Optional[str],
    job: Job,
    bridge: dict,
) -> str:
    spec = bridge.get("cad_output", {}).get("spec", {})
    _missing = [k for k in ("inner_length", "inner_width", "inner_height") if k not in spec]
    if _missing:
        raise ValueError(
            f"cad_output.spec 缺少必要殼體尺寸 {_missing}，拒絕以預設值頂替產生 3D 殼體"
            "（fail-before-render：尺寸算不出寧可明示失敗，不畫假殼）"
        )
    L    = spec["inner_length"]
    W    = spec["inner_width"]
    H    = spec["inner_height"]
    wall = spec.get("wall", 2.0)

    _MAX_STL_BYTES = 3 * 1024 * 1024

    def _stl_b64(path: Optional[str]) -> str:
        if not path or not Path(path).exists():
            return ""
        raw = Path(path).read_bytes()
        if len(raw) > _MAX_STL_BYTES:
            return ""
        return base64.b64encode(raw).decode()

    b64_bottom = _stl_b64(bottom_stl)
    b64_lid    = _stl_b64(lid_stl)

    io_js = _build_io_markers_js(bridge)
    comp_js = _build_component_boxes_js(bridge, wall)

    html = f"""<script src="{_THREEJS_CDN}"></script>
<script src="{_ORBIT_CDN}"></script>
<script src="{_STL_CDN}"></script>
<script>
(function(){{
  var canvas = document.getElementById('three-canvas');
  if (!canvas) return;

  // ── WebGL Context Lifecycle ─────────────────────────────
  if (window.__cadhllm_renderer) {{
    try {{
      window.__cadhllm_renderer.dispose();
      window.__cadhllm_renderer.forceContextLoss();
    }} catch(e) {{}}
    window.__cadhllm_renderer = null;
  }}

  var W3 = canvas.clientWidth || 600, H3 = canvas.clientHeight || 400;
  var renderer = new THREE.WebGLRenderer({{canvas:canvas, antialias:true}});
  renderer.setSize(W3, H3);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.shadowMap.enabled = true;
  window.__cadhllm_renderer = renderer;

  var scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1a2e);
  scene.add(new THREE.HemisphereLight(0xddeeff, 0x445566, 0.6));
  var keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
  keyLight.position.set(200,300,200); keyLight.castShadow=true; scene.add(keyLight);
  var fillLight = new THREE.DirectionalLight(0x8899bb, 0.4);
  fillLight.position.set(-150,200,-100); scene.add(fillLight);
  var rimLight = new THREE.DirectionalLight(0x4466aa, 0.3);
  rimLight.position.set(0,-100,250); scene.add(rimLight);

  var camera = new THREE.PerspectiveCamera(45, W3/H3, 1, 5000);
  camera.position.set({L}*1.8, {H}*3, {W}*2.5);
  camera.lookAt(0,0,0);
  var controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;

  // ── STL helper（Base64 → ArrayBuffer → STLLoader.parse）──
  function b64ToArrayBuffer(b64) {{
    var bin = atob(b64), buf = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return buf.buffer;
  }}
  function addSTL(b64, fbL, fbW, fbH, color, opacity, posX, posY, posZ) {{
    var geo = null;
    if (b64) {{
      try {{ geo = new THREE.STLLoader().parse(b64ToArrayBuffer(b64)); }} catch(e) {{}}
    }}
    if (!geo) {{ geo = new THREE.BoxGeometry(fbL, fbH, fbW); }}
    geo.computeBoundingBox();
    var bb = geo.boundingBox;
    geo.translate(-(bb.max.x+bb.min.x)/2, -(bb.max.y+bb.min.y)/2, -(bb.max.z+bb.min.z)/2);
    var mat = new THREE.MeshPhongMaterial({{color:color, transparent:true, opacity:opacity, shininess:60, specular:0x222244}});
    var mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(posX, posY, posZ);
    scene.add(mesh);
    return mesh;
  }}

  addSTL('{b64_bottom}', {L+2*wall}, {W+2*wall}, {H},   0x2d6a9f, 0.85, 0, 0, 0);
  addSTL('{b64_lid}',    {L+2*wall}, {W+2*wall}, {wall*2}, 0x4da6ff, 0.55, 0, {H/2+wall}, 0);

  // ── Component Placement Boxes (actual proportions from REGISTRY) ──
  __COMP_BOXES__

  // ── IO Port Markers ──────────────────────────────────────
  __IO_MARKERS__

  // ── Grid & Animate ───────────────────────────────────────
  scene.add(new THREE.GridHelper(400, 20, 0x444466, 0x333355));
  (function animate() {{
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }})();

  // ── Resize：requestAnimationFrame 延遲對齊 tab 切換 ──────
  function onResize() {{
    requestAnimationFrame(function() {{
      var w = canvas.clientWidth || 600, h = canvas.clientHeight || 400;
      if (w < 10 || h < 10) return;
      camera.aspect = w / h; camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }});
  }}
  window.addEventListener('resize', onResize);
  if (typeof ResizeObserver !== 'undefined') {{
    new ResizeObserver(onResize).observe(canvas);
  }}
}})();
</script>"""
    return html.replace("__COMP_BOXES__", comp_js).replace("__IO_MARKERS__", io_js)


def _build_io_markers_js(bridge: dict) -> str:
    cad_out = bridge.get("cad_output", {})
    placements = cad_out.get("component_placements", [])
    wire_routes = cad_out.get("wire_routes", [])
    if not placements or not wire_routes:
        return ""

    spec = cad_out.get("spec", {})
    _missing_io = [k for k in ("inner_length", "inner_width", "inner_height") if k not in spec]
    if _missing_io:
        raise ValueError(
            f"_build_io_markers_js: cad_output.spec 缺少幾何尺寸 {_missing_io}，"
            "無法計算 waypoint 世界座標，拒絕以假值頂替"
        )
    inner_l = spec["inner_length"]
    inner_w = spec["inner_width"]
    wall = spec.get("wall", 2.0)
    outer_h = spec["inner_height"] + 2 * wall

    placement_map = {p["type"]: p for p in placements}

    lines: List[str] = []
    for wr in wire_routes:
        for end_key in ("from", "to"):
            comp_type = wr.get(end_key)
            p = placement_map.get(comp_type)
            if not p:
                continue
            wps = wr.get("waypoints", [])
            if not wps:
                continue
            wp = wps[0] if end_key == "from" else wps[-1]
            px = wp[0] - inner_l / 2
            pz_cq = -outer_h / 2 + wall + wp[2]
            py = -(wp[1] - inner_w / 2)
            sig = wr.get("signal_type", "digital")
            color_map = {
                "power": "0xff4444", "gnd": "0x333333",
                "i2c": "0x44ddff", "spi": "0xdd44ff",
                "analog": "0xffaa00", "digital": "0x44cc44",
            }
            marker_color = color_map.get(sig, "0xff6644")
            lines.append(
                f"(function(){{var g=new THREE.SphereGeometry(1.5,8,8);"
                f"var m=new THREE.Mesh(g,new THREE.MeshBasicMaterial("
                f"{{color:{marker_color}}}));"
                f"m.position.set({px:.1f},{pz_cq:.1f},{py:.1f});"
                f"scene.add(m);}})();"
                f" // {comp_type} {end_key} ({sig})"
            )
    return "\n  ".join(lines)


def _build_component_boxes_js(bridge: dict, wall: float) -> str:
    cad_out = bridge.get("cad_output", {})
    placements = cad_out.get("component_placements", [])
    if not placements:
        return ""

    spec = cad_out.get("spec", {})
    _missing_cb = [k for k in ("inner_length", "inner_width", "inner_height") if k not in spec]
    if _missing_cb:
        raise ValueError(
            f"_build_component_boxes_js: cad_output.spec 缺少幾何尺寸 {_missing_cb}，"
            "無法計算元件 box 定位座標，拒絕以假值頂替"
        )
    inner_l = spec["inner_length"]
    inner_w = spec["inner_width"]
    outer_h = spec["inner_height"] + 2 * wall

    # Wave B: 衍生自 lib/config.ROLE_PALETTE 單一 SSOT（#RRGGBB → Three.js 0xRRGGBB）;
    # 補向後相容別名（Output/Motor→Actuator、Audio→Sound）。
    from lib.config import ROLE_PALETTE
    _ROLE_COLORS = {r: "0x" + c.lstrip("#") for r, c in ROLE_PALETTE.items()}
    _ROLE_COLORS.update({
        "Output": _ROLE_COLORS["Actuator"], "Motor": _ROLE_COLORS["Actuator"],
        "Audio": _ROLE_COLORS["Sound"],
    })
    lines: List[str] = []
    for p in placements:
        for _req in ("L", "W", "H", "x", "y"):
            if _req not in p:
                raise ValueError(
                    f"_build_component_boxes_js: placement 缺少必要鍵 {_req!r}，"
                    f"拒絕以假值頂替（30/20/10/0）: {p!r}"
                )
        cL = p["L"]
        cW = p["W"]
        cH = p["H"]
        cx_cq = p["x"] + cL / 2 - inner_l / 2
        cy_cq = p["y"] + cW / 2 - inner_w / 2
        cz_cq = -outer_h / 2 + wall + cH / 2
        tx, ty, tz = cx_cq, cz_cq, -cy_cq
        color = _ROLE_COLORS.get(p.get("role", ""), "0x888888")
        ctype = p.get("type", "unknown")
        lines.append(
            f"(function(){{var g=new THREE.BoxGeometry({cL:.1f},{cH:.1f},{cW:.1f});"
            f"var m=new THREE.Mesh(g,new THREE.MeshPhongMaterial("
            f"{{color:{color},transparent:true,opacity:0.45}}));"
            f"m.position.set({tx:.1f},{ty:.1f},{tz:.1f});scene.add(m);}})();"
            f" // {ctype} ({cL:.0f}x{cW:.0f}x{cH:.0f}mm)"
        )
    return "\n  ".join(lines)


def inject_html(
    threejs_html: str,
    progress_cb: Optional[Callable[[str], None]],
    log_fn: Callable,
) -> bool:
    _CLEAR_END = "    </div>\n\n  </main>"
    candidates = [
        str(Path(__file__).parents[2] / "ui" / "index.html"),
        "ui/index.html",
    ]
    for candidate in candidates:
        p = Path(candidate)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8").replace('\r\n', '\n')
        if _INJECT_MARKER not in content:
            log_fn(progress_cb, f"  ⚠️  找不到 {_INJECT_MARKER} in {candidate}")
            continue

        marker_idx = content.find(_INJECT_MARKER)
        end_idx    = content.find(_CLEAR_END, marker_idx)
        if end_idx == -1:
            new_content = content.replace(
                _INJECT_MARKER, _INJECT_MARKER + "\n" + threejs_html)
        else:
            new_content = (
                content[:marker_idx + len(_INJECT_MARKER)]
                + "\n" + threejs_html + "\n"
                + content[end_idx:]
            )

        p.write_text(new_content, encoding="utf-8")
        log_fn(progress_cb, f"  ✅ Three.js 已注入（取代前次）→ {candidate}")
        return True
    return False
