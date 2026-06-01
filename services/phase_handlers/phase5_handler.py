"""phase_handlers/phase5_handler.py — Phase V 3D Viewer + Multiview PNG Handler。

由 bridge.cad_output 找到 STL 檔，用 trimesh 渲染多視圖 PNG，
並將 Three.js HTML 注入 ui/index.html。

Rendering and Three.js generation are in helper modules:
  _phase5_renderer.py  — multiview PNG rendering
  _phase5_threejs.py   — Three.js HTML generation + injection
"""
from __future__ import annotations
import base64
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import logging

from .base import PhaseHandler
from ..shared.models import Job, PhaseID
from ..shared.bridge_store import save_bridge, DRIVE_ROOT
from ._phase5_renderer import render_multiview
from ._phase5_threejs import build_threejs_html, inject_html

_log = logging.getLogger("cadhllm.phase5")


class Phase5Handler(PhaseHandler):
    """Phase V: 3D Viewer — multiview PNG + Three.js HTML injection。"""

    phase_id = PhaseID.P5

    def execute(
        self,
        job: Job,
        bridge: dict,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> Tuple[dict, Dict[str, Any]]:
        cad_out = bridge.get("cad_output", {})
        bottom_stl = cad_out.get("bottom_stl")
        lid_stl    = cad_out.get("lid_stl")

        if not bottom_stl and not lid_stl:
            self._log(progress_cb, "⚠️  cad_output 無 STL 路徑，跳過 3D viewer")
            return bridge, {"views": [], "html_injected": False}

        out_dir = Path(cad_out.get("subdir", "/tmp/cadhllm_cad"))

        views = render_multiview(
            bottom_stl, lid_stl, out_dir, progress_cb, bridge, self._log,
        )

        threejs_html = build_threejs_html(bottom_stl, lid_stl, job, bridge)
        injected = inject_html(threejs_html, progress_cb, self._log)

        firmware_data = self._generate_firmware(bridge, progress_cb)

        views_b64 = {}
        for label, path in views.items():
            try:
                views_b64[label] = base64.b64encode(
                    Path(path).read_bytes()).decode()
            except OSError as _e:
                _log.debug("b64 encode failed for %s: %s", label, _e)

        bridge["viewer"] = {
            "views": views,
            "views_b64": views_b64,
            "html_injected": injected,
        }
        if firmware_data:
            bridge["firmware"] = firmware_data
        self._save_bridge_safe(job, bridge, progress_cb)

        summary = f"3D viewer：{len(views)} 視圖 / HTML {'已注入' if injected else '未注入'}"
        self._log(progress_cb, summary)
        return bridge, {"views": views, "html_injected": injected, "summary": summary}

    # ── ED1：韌體生成 ──────────────────────────────────────

    def _generate_firmware(
        self,
        bridge: dict,
        progress_cb,
    ) -> Optional[dict]:
        """ED1：從 bridge.components 提取 Brain/Power/Output/Sensor，呼叫 lib/firmware.to_json()。"""
        try:
            from lib.firmware import to_json as firmware_to_json
            from lib.wiring import normalize_brain, normalize_comp
        except ImportError as e:
            self._log(progress_cb, f"  ⚠️ firmware import 失敗：{e}")
            return None

        components = bridge.get("components", [])
        if not components:
            return None

        brain_type = ""
        power_key = "USB-5V"
        outputs: List[str] = []
        sensors: List[str] = []

        _OUTPUT_ROLES = {"Output", "Actuator", "Lighting", "Display",
                         "Motor", "Audio", "Control", "Sound", "Mist"}
        _SENSOR_ROLES = {"Sensor", "Input"}

        for c in components:
            role = c.get("role", "")
            ctype = c.get("type", "")
            if role == "Brain":
                brain_type = ctype
            elif role == "Power":
                power_key = normalize_comp(ctype)
            elif role in _OUTPUT_ROLES:
                outputs.append(normalize_comp(ctype))
            elif role in _SENSOR_ROLES:
                sensors.append(normalize_comp(ctype))

        if not brain_type:
            self._log(progress_cb, "  ⚠️ 無 Brain 元件，跳過韌體生成")
            return None

        brain_key = normalize_brain(brain_type)
        try:
            fw_data = firmware_to_json(brain_key, power_key, outputs, sensors)
            fw = fw_data.get("firmware", {})
            code = fw.get("code", "") if isinstance(fw, dict) else str(fw)
            loc = len(code.split("\n")) if code else 0
            n_tests = len(fw_data.get("test_codes", {}))

            wiring_pin_map = self._build_wiring_pin_map(bridge)
            if wiring_pin_map:
                fw_data["wiring_pin_map"] = wiring_pin_map

            self._log(progress_cb,
                      f"  ✅ 韌體生成完成（{brain_key}，{loc} LOC，{n_tests} 個測試碼）")
            return fw_data
        except Exception as e:
            self._log(progress_cb, f"  ⚠️ 韌體生成失敗：{e}")
            _log.exception("firmware generation failed")
            return None

    # ── CAG: Wiring Pin Map ─────────────────────────────────

    def _build_wiring_pin_map(self, bridge: dict) -> dict:
        """從 CAG WiringTemplate 提取每個元件的 pin 語義標註。"""
        try:
            from lib.wiring.template_gen import get_template
            from lib.wiring import normalize_comp
        except ImportError:
            return {}

        result = {}
        for comp in bridge.get("components", []):
            ctype = comp.get("type", "")
            role = comp.get("role", "")
            if role in ("Brain", "Power"):
                continue
            try:
                short = normalize_comp(ctype)
                tmpl = get_template(short)
            except Exception:
                continue
            if not tmpl:
                continue
            result[short] = {
                "label": tmpl.label,
                "vcc": tmpl.vcc,
                "decoupling": tmpl.decoupling,
                "pins": [
                    {"name": e.comp, "tag": e.tag, "note": e.note,
                     "passive": e.passive}
                    for e in (tmpl.extra or [])
                ],
            }
        return result

    @staticmethod
    def _log(cb: Optional[Callable], msg: str):
        prefix = "[Phase V] "
        if cb:
            cb(prefix + msg)
        else:
            print(prefix + msg)
