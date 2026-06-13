"""bake_holders.py — audit-driven, unified component-holder (外殼) baker.

Classification from the 2026-06-06 datasheet audit + user policy「評估真實需求後比對 mcu
的外殼進行設計」. Every holder-needing component gets an MCU-style 2-piece case (base+lid):
precise (build_pcb_two_piece) when a PCBSpec exists, else generic (build_generic_two_piece
from SSOT footprint). Actuators keep their bespoke mount. Self-enclosed / embedded parts get
no holder (their over-baked cradles are removed).

Run:  python -m lib.cad.bake_holders
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.cad import build_pcb_two_piece, export_step, export_stl_high_density
from lib.cad.glb_convert import ensure_shell_glbs
from lib.cad.mounts import ALL_MOUNTS, build_generic_two_piece
from lib.pcb import PCB_REGISTRY

_REPO = Path(__file__).resolve().parent.parent.parent
_SHELLS = _REPO / "shells"
_SSOT = _REPO / "data" / "component_datasheet_verified.json"

# Precise 2-piece case via build_pcb_two_piece (PCBSpec exists + builds watertight).
CASE_PCBSPEC = [
    "Arduino-Uno-class", "ESP32-class", "Microbit-class", "RaspberryPi-class",
    "Relay-Module-class", "Display-OLED-class", "Display-LCD-class",
    "Sensor-TempHumid-class", "Sensor-Ultrasonic-class", "Sensor-PIR-class",
]
# Generic 2-piece case from SSOT footprint (no PCBSpec, but a holder is warranted).
HOLDER_GENERIC = [
    # Arduino-Nano: MCU brain without a PCBSpec — geometry derives from verified.json
    # SSOT footprint (2026-06-13 decision: no redundant per-board pcb module for Nano).
    # First surfaced by biped_robot, the first demo to use Arduino-Nano-class.
    "Arduino-Nano-class",
    "L298N-Driver-class", "Display-EInk-class", "LED-Matrix-class", "MP3-Module-class",
    "Joystick-class", "Sensor-Light-class", "Sensor-IR-class",
    "Battery-LiPo-class", "Button-class",
    "Lighting-LED-PWM-class", "Lighting-LED-RGB-class", "Potentiometer-class",
    "USB-5V-class", "Mist-Atomizer-class", "Mist-Ultrasonic-class",
]
# Bespoke purpose-built mounts (keep).
BESPOKE = ["Motor-DC-class", "Motor-Servo-class", "Motor-Stepper-class", "Speaker-class"]
# Self-enclosed / embedded / strips / chassis → no holder (remove any over-baked cradle).
NONE = [
    "Chassis-Car-class", "Sensor-MSGEQ7-class", "Pump-Water-class", "Battery-AA-class",
    "Lighting-NeoPixel-class", "Lighting-LED-Strip-class", "Remote-class",
    "Switch-class", "Switch-Generic-class", "USB-Adapter-class", "AC-Adapter-class",
    # 2026-06-07 user visual review: soil probe self-exposes / panel-mount buzzers →
    # no wrapping 2-piece case (it occluded/double-wrapped them). See fidelity-diagnose wf.
    "Sensor-SoilMoisture-class", "Buzzer-Active-class", "Buzzer-Passive-class",
]

_MOUNT_FILES = ["mount_stl.stl", "mount.glb", "mount_step.step"]
_CASE_FILES = ["base_stl.stl", "lid_stl.stl", "base.glb", "lid.glb", "base_step.step", "lid_step.step"]


def _rm(d: Path, names):
    for n in names:
        p = d / n
        if p.exists():
            p.unlink()


def _write_case_meta(d: Path, cls: str, spec_dict: dict):
    meta_path = d / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"class_name": cls}
    files = meta.setdefault("files", {})
    files["base_stl"] = "base_stl.stl"
    files["lid_stl"] = "lid_stl.stl"
    files.pop("mount_stl", None)
    meta["kind"] = "two_piece"
    meta["spec_dict"] = spec_dict
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _scrub_none_meta(d: Path, cls: str) -> None:
    """NONE class self-encloses via its own pcb_body.glb. Drop stale case/mount file
    refs (+ mount_kind) left in meta.json so loaders never chase a deleted file."""
    meta_path = d / "meta.json"
    if not meta_path.exists():
        return
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    changed = False
    files = meta.get("files")
    if isinstance(files, dict):
        for k in ("base_stl", "lid_stl", "mount_stl", "base_step", "lid_step", "mount_step"):
            if files.pop(k, None) is not None:
                changed = True
    if meta.pop("mount_kind", None) is not None:
        changed = True
    if changed:
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def _spec_to_dict(spec) -> dict:
    import dataclasses
    try:
        sd = dataclasses.asdict(spec) if dataclasses.is_dataclass(spec) else dict(vars(spec))
    except Exception:  # noqa: BLE001
        sd = {}
    return {k: v for k, v in sd.items() if isinstance(v, (int, float, str, bool))}


def bake_holders() -> dict:
    ssot = json.loads(_SSOT.read_text(encoding="utf-8"))
    touched, summary = [], {"case": 0, "generic": 0, "bespoke": 0, "none": 0, "fail": 0}

    for cls in CASE_PCBSPEC:
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        try:
            base, lid, spec = build_pcb_two_piece(PCB_REGISTRY[cls], class_name=cls)
            export_stl_high_density(base, str(d / "base_stl.stl"))
            export_stl_high_density(lid, str(d / "lid_stl.stl"))
            _rm(d, _MOUNT_FILES)                       # drop over-baked cradle
            _write_case_meta(d, cls, _spec_to_dict(spec))
            touched.append(cls); summary["case"] += 1
            print(f"  [CASE]    {cls}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL]    {cls}: {exc}"); summary["fail"] += 1

    for cls in HOLDER_GENERIC:
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        ph = (ssot.get(cls) or {}).get("physical", {})
        L, W, H = ph.get("length_mm"), ph.get("width_mm"), ph.get("height_mm")
        if not (L and W and H):
            print(f"  [SKIP]    {cls}: no SSOT dims"); continue
        try:
            base, lid, sd = build_generic_two_piece(L, W, H)
            export_stl_high_density(base, str(d / "base_stl.stl"))
            export_stl_high_density(lid, str(d / "lid_stl.stl"))
            _rm(d, _MOUNT_FILES)
            _write_case_meta(d, cls, sd)
            touched.append(cls); summary["generic"] += 1
            print(f"  [GENERIC] {cls}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL]    {cls}: {exc}"); summary["fail"] += 1

    for cls in BESPOKE:
        d = _SHELLS / cls
        d.mkdir(parents=True, exist_ok=True)
        try:
            _, _label, builder = ALL_MOUNTS[cls]
            part, _info = builder()
            export_stl_high_density(part, str(d / "mount_stl.stl"))
            _rm(d, ["base_stl.stl", "lid_stl.stl", "base.glb", "lid.glb"])
            meta_path = d / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"class_name": cls}
            meta.setdefault("files", {})["mount_stl"] = "mount_stl.stl"
            meta["mount_kind"] = ALL_MOUNTS[cls][0]
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            touched.append(cls); summary["bespoke"] += 1
            print(f"  [BESPOKE] {cls}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [FAIL]    {cls}: {exc}"); summary["fail"] += 1

    for cls in NONE:
        d = _SHELLS / cls
        if d.exists():
            _rm(d, _MOUNT_FILES + _CASE_FILES)         # self-enclosed → no holder
            _scrub_none_meta(d, cls)                    # drop stale base/lid/mount refs
            summary["none"] += 1
            print(f"  [NONE]    {cls} (holders removed)")

    # overwrite=True:重烘的 base/lid STL 必須覆蓋舊 GLB(否則 cutout/窗等幾何改動
    # 留在 STL、舊 GLB 仍被服務)。pcb_body.glb 多色版受 protect,不受影響。
    res = ensure_shell_glbs(_SHELLS, types=touched, overwrite=True)
    print(f"\n{summary}  GLB converted {len(res['converted'])}")
    return summary


if __name__ == "__main__":
    bake_holders()
