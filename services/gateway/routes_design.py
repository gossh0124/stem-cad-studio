"""gateway/routes_design.py — 設計輔助 API + 元件殼 + Artifact + User Components。"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..shared.bridge_store import load_bridge, DRIVE_ROOT
from ..shared.auth import get_token_job_id, require_job_owner
from lib.ui_constants import get_ui_constants

router = APIRouter()

_SHELLS_DIR = Path(__file__).resolve().parent.parent.parent / "shells"
_DATASHEET_JSON = Path(__file__).resolve().parent.parent.parent / "data" / "component_datasheet_verified.json"
_datasheet_cache: Optional[Dict[str, Any]] = None
_datasheet_mtime: float = 0.0


def _load_datasheet() -> Dict[str, Any]:
    """Lazy load + cache verified.json（SSOT）。

    P5.2: 包 try/except 把損壞/缺檔轉成 HTTP 500（避免 raw stacktrace 給 client）。
    P5.5: 用 mtime check 達成 dev 模式 hot-reload（修 verified.json 不用重啟 server）。
    """
    global _datasheet_cache, _datasheet_mtime
    try:
        mt = _DATASHEET_JSON.stat().st_mtime
    except OSError as e:
        raise HTTPException(500, f"SSOT datasheet 不存在或無法讀取：{e}")
    if _datasheet_cache is None or mt > _datasheet_mtime:
        try:
            _datasheet_cache = json.loads(_DATASHEET_JSON.read_text(encoding="utf-8"))
            _datasheet_mtime = mt
        except json.JSONDecodeError as e:
            raise HTTPException(500, f"SSOT datasheet JSON 損壞：{e}")
    return _datasheet_cache


# ── 元件常數 ────────────────────────────────────────────
@router.get("/api/v1/components")
async def api_components():
    return get_ui_constants()


# ── Datasheet SSOT API（Phase 3C） ───────────────────────
# data/component_datasheet_verified.json 是專案 SSOT；前端透過此 endpoint
# runtime 取得 physical / electrical / on_board_components / _3d_hints / _ui_hints

@router.get("/api/v1/datasheet")
async def list_datasheet_classes():
    return {"classes": sorted(_load_datasheet().keys())}


@router.get("/api/v1/datasheet/{class_name}")
async def get_datasheet(class_name: str):
    data = _load_datasheet()
    # alias 解析（共用 shell resolver 邏輯）
    if class_name in data:
        return {"class_name": class_name, **data[class_name]}
    resolved = _resolve_shell_type(class_name)
    if resolved and resolved in data:
        return {"class_name": resolved, "alias_of": class_name, **data[resolved]}
    raise HTTPException(404, f"datasheet 無 {class_name} 條目")


# ── Design API（wiring / schematic / firmware）──────────
class DesignRequest(BaseModel):
    brain: str = "Arduino"
    power: str = "USB-5V"
    outputs: List[str] = Field(default_factory=list)
    sensors: List[str] = Field(default_factory=list)
    project_name: str = ""
    plan: str = ""


@router.post("/api/v1/wiring")
async def api_wiring(req: DesignRequest):
    from lib.wiring import to_json, PinAllocationError
    try:
        return to_json(req.brain, req.outputs + req.sensors)
    except PinAllocationError as e:
        raise HTTPException(422, f"接線無法分配（設計問題：pin 不足或不符）：{e}")


@router.post("/api/v1/schematic")
async def api_schematic(req: DesignRequest):
    from lib.schematic import to_json
    from lib.wiring import PinAllocationError
    try:
        return to_json(req.brain, req.power, req.outputs, req.sensors)
    except PinAllocationError as e:
        raise HTTPException(422, f"原理圖接線無法分配（設計問題）：{e}")


@router.post("/api/v1/firmware")
async def api_firmware(req: DesignRequest):
    from lib.firmware import to_json
    from lib.wiring import PinAllocationError
    try:
        return to_json(req.brain, req.power, req.outputs, req.sensors,
                       req.project_name, req.plan)
    except PinAllocationError as e:
        raise HTTPException(422, f"韌體接線無法分配（設計問題）：{e}")


# ── 元件殼 API ──────────────────────────────────────────

def _resolve_shell_type(comp_type: str) -> Optional[str]:
    if (_SHELLS_DIR / comp_type).exists():
        return comp_type
    _ALIAS = {
        "DHT22-class": "Sensor-TempHumid-class", "DHT11-class": "Sensor-TempHumid-class",
        "SG90-Servo-class": "Motor-Servo-class", "Servo-class": "Motor-Servo-class",
        "HC-SR04-class": "Sensor-Ultrasonic-class", "Ultrasonic-class": "Sensor-Ultrasonic-class",
        "OLED-128x64-class": "Display-OLED-class", "OLED-class": "Display-OLED-class",
        "LCD1602-class": "Display-LCD-class",
        "Soil-Moisture-class": "Sensor-SoilMoisture-class",
        "Water-Pump-class": "Pump-Water-class",
        "PIR-class": "Sensor-PIR-class",
        "BME280-class": "Sensor-TempHumid-class", "SHT41-class": "Sensor-TempHumid-class",
        "WS2812B-class": "Lighting-NeoPixel-class",
        "LED-5mm-class": "Lighting-LED-RGB-class", "LED-class": "Lighting-LED-RGB-class",
        "NRF24-class": "Remote-class",
        "L298N-class": "Motor-DC-class",
        "DC-Motor-class": "Motor-DC-class",
        "Stepper-class": "Motor-Stepper-class",
        "Buzzer-class": "Buzzer-Active-class",
        "E-Ink-class": "Display-EInk-class",
        "MPPT-class": "USB-5V-class",
        "MSGEQ7-class": "Sensor-IR-class",
        "Fingerprint-class": "Sensor-IR-class",
        "Solenoid-class": "Relay-Module-class",
        "USB-5V": "USB-5V-class",
        "Arduino-Nano-class": "Arduino-Uno-class",
        "Sensor-MSGEQ7-class": "Sensor-IR-class",
        "Switch-Generic-class": "Switch-class",
        "USB-Adapter-class": "USB-5V-class",
        "BatteryHolder-AA-class": "Battery-AA-class",
        "L298N-Driver-class": "Motor-DC-class",
    }
    resolved = _ALIAS.get(comp_type)
    if resolved and (_SHELLS_DIR / resolved).exists():
        return resolved
    return None


@router.get("/api/shells")
async def list_shells():
    if not _SHELLS_DIR.exists():
        return {"shells": []}
    result = []
    for d in sorted(_SHELLS_DIR.iterdir()):
        if d.is_dir() and any((d / f).exists() for f in ("shell.stl", "base_stl.stl", "mount_stl.stl")):
            meta = {}
            meta_path = d / "meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            result.append({"type": d.name, "tri_count": meta.get("tri_count", 0)})
    return {"shells": result}


# 各 variant 候選檔（一律 GLB 優先 → 載入更快更小，fallback STL）
_VARIANT_CANDIDATES = {
    "lid":      ("lid.glb", "lid_stl.stl", "lid.stl"),
    "mount":    ("mount.glb", "mount_stl.stl", "mount.stl"),
    "pcb_body": ("pcb_body.glb", "pcb_body.stl"),
    "base":     ("base.glb", "base_stl.stl", "base.stl", "shell.stl"),
}


@router.get("/api/shells/{comp_type}/stl")
async def serve_shell_stl(comp_type: str, variant: str = "base"):
    resolved = _resolve_shell_type(comp_type)
    if not resolved:
        raise HTTPException(404, f"找不到元件殼：{comp_type}")
    base_dir = _SHELLS_DIR / resolved

    candidates = _VARIANT_CANDIDATES.get(
        variant, ("shell.stl", "base_stl.stl", "mount_stl.stl"))

    for fname in candidates:
        p = base_dir / fname
        if p.exists():
            is_glb = fname.endswith(".glb")
            ext = "glb" if is_glb else "stl"
            return FileResponse(
                str(p),
                media_type="model/gltf-binary" if is_glb else "application/octet-stream",
                headers={"Content-Disposition": f"inline; filename={resolved}_{variant}.{ext}",
                         "Cache-Control": "no-cache, no-store, must-revalidate"})
    raise HTTPException(404, f"mesh 不存在：{resolved}/{variant}")


@router.get("/api/shells/{comp_type}/meta")
async def serve_shell_meta(comp_type: str):
    resolved = _resolve_shell_type(comp_type)
    if not resolved:
        raise HTTPException(404, f"找不到元件殼：{comp_type}")
    base_dir = _SHELLS_DIR / resolved
    # S5(b): 列出實際存在的 variant，前端據此跳過缺漏 variant 的 fetch，避免 404 噪音
    available_variants = [v for v, cands in _VARIANT_CANDIDATES.items()
                          if any((base_dir / fn).exists() for fn in cands)]
    result = {"resolved_type": resolved, "available_variants": available_variants}
    for fname in ["meta.json", "shell.meta.json"]:
        p = base_dir / fname
        if p.exists():
            try:
                result[fname.replace(".json", "")] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return result


# ── STL / Artifact 服務 ─────────────────────────────────

def _safe_resolve(base: Path, user_path: str) -> Optional[Path]:
    try:
        resolved = (base / user_path).resolve()
        if resolved.is_relative_to(base.resolve()):
            return resolved
    except (ValueError, OSError):
        pass
    return None


@router.get("/api/stl/{job_id}/{filename:path}")
async def serve_stl(job_id: str, filename: str, token_job_id: str = Depends(get_token_job_id)):
    require_job_owner(token_job_id, job_id)
    bridge = load_bridge(job_id)
    if not bridge:
        raise HTTPException(404, "Job bridge 不存在")
    cad_out = bridge.get("cad_output", {})
    subdir  = cad_out.get("subdir", "")

    drive = Path(DRIVE_ROOT).resolve()
    stl_path: Optional[Path] = None

    base = Path(subdir) if Path(subdir).is_absolute() else drive / subdir
    candidate = _safe_resolve(base, filename)
    if candidate and candidate.exists():
        stl_path = candidate

    if not stl_path:
        job_cad_dir = drive / "cad_output" / job_id
        candidate = _safe_resolve(job_cad_dir, filename)
        if candidate and candidate.exists():
            stl_path = candidate

    if not stl_path:
        proj_dir = bridge.get("_project_output_dir", "")
        if proj_dir:
            candidate = _safe_resolve(Path(proj_dir) / "cad", filename)
            if candidate and candidate.exists():
                stl_path = candidate

    if not stl_path:
        raise HTTPException(404, f"STL 檔案不存在：{filename}")
    return FileResponse(str(stl_path), media_type="application/octet-stream",
               headers={"Content-Disposition": f"attachment; filename={stl_path.name}"})


_ARTIFACT_MIME = {
    "stl":  "model/stl",
    "step": "application/step",
    "ino":  "text/x-arduino",
    "csv":  "text/csv",
}


def _resolve_artifact_path(kind: str, job_id: Optional[str]) -> Optional[Path]:
    drive = Path(DRIVE_ROOT).resolve()
    cad_root = drive / "cad_output"

    def _is_safe(p: Path) -> bool:
        try:
            return p.resolve().is_relative_to(drive)
        except (ValueError, OSError):
            return False

    if job_id:
        bridge = load_bridge(job_id)
        if bridge:
            cad_out = bridge.get("cad_output", {})
            subdir  = cad_out.get("subdir") or str(cad_root / job_id)
            base    = Path(subdir)
            if not base.is_absolute():
                base = drive / base
            if _is_safe(base) and base.exists():
                for f in base.rglob(f"*.{kind}"):
                    if _is_safe(f):
                        return f
                if kind == "ino":
                    for f in base.rglob("firmware.*"):
                        if f.suffix.lower() in (".ino", ".txt") and _is_safe(f):
                            return f
                if kind == "csv":
                    for f in base.rglob("BOM*.csv"):
                        if _is_safe(f):
                            return f
        return None

    if cad_root.exists():
        candidates = [p for p in cad_root.rglob(f"*.{kind}") if _is_safe(p)]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)

    outputs_root = drive.parent / "outputs" if drive.name == "CADHLLM" else drive / "outputs"
    if outputs_root.exists():
        candidates = [p for p in outputs_root.rglob(f"*.{kind}") if _is_safe(p)]
        if candidates:
            return max(candidates, key=lambda p: p.stat().st_mtime)

    return None


@router.get("/api/artifact/{kind}")
async def serve_artifact(kind: str, project_id: Optional[str] = None, token_job_id: str = Depends(get_token_job_id)):
    kind = kind.lower()
    if kind not in _ARTIFACT_MIME:
        raise HTTPException(400, f"不支援的 artifact 類型：{kind}")
    if project_id:
        require_job_owner(token_job_id, project_id)
    path = _resolve_artifact_path(kind, project_id)
    if not path or not path.exists():
        raise HTTPException(404, f"{kind.upper()} 檔案尚未產生")

    filename = path.name if path.suffix.lstrip(".").lower() == kind else f"{path.stem}.{kind}"
    return FileResponse(
        str(path),
        media_type=_ARTIFACT_MIME[kind],
        filename=filename,
        headers={"Cache-Control": "no-store"},
    )


# ── User Components CRUD ─────────────────────────────────

class UserComponentRequest(BaseModel):
    name: str = Field(..., min_length=1)
    class_name: str = Field(..., min_length=1)
    length_mm: float = Field(..., gt=0)
    width_mm: float = Field(..., gt=0)
    height_mm: float = Field(..., gt=0)
    voltage_v: float = 5.0
    current_ma: float = 50.0
    tags: List[str] = Field(..., min_length=1)
    connector_ports: List[Dict[str, Any]] = []


@router.get("/api/v1/user-components")
async def list_user_components() -> dict:
    from ..shared.user_components_store import list_components
    return {"components": list_components()}


@router.post("/api/v1/user-components", status_code=201)
async def add_user_component(req: UserComponentRequest) -> dict:
    from ..shared.user_components_store import add_component, UserComponentSpec
    spec = UserComponentSpec(
        name=req.name, class_name=req.class_name,
        length_mm=req.length_mm, width_mm=req.width_mm, height_mm=req.height_mm,
        voltage_v=req.voltage_v, current_ma=req.current_ma,
        tags=req.tags, connector_ports=req.connector_ports,
        # 無 port → external（無走線終點）；有 port → internal（user 後續可在 UI 升級為 panel/breadboard）
        enclosure_relation='external' if len(req.connector_ports) == 0 else 'internal',
    )
    add_component(spec)
    return {"class_name": req.class_name, "created": True}


@router.get("/api/v1/user-components/{class_name}")
async def get_user_component(class_name: str) -> dict:
    from ..shared.user_components_store import get_spec
    from dataclasses import asdict
    spec = get_spec(class_name)
    if spec is None:
        raise HTTPException(404, f"User component '{class_name}' not found")
    return asdict(spec)


@router.delete("/api/v1/user-components/{class_name}")
async def delete_user_component(class_name: str) -> dict:
    from ..shared.user_components_store import remove_component
    if not remove_component(class_name):
        raise HTTPException(404, f"User component '{class_name}' not found")
    return {"class_name": class_name, "deleted": True}
