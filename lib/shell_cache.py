"""shell_cache.py — Phase IV Layer 1 元件殼快取（跨專案複用）。

快取 key = class_name（例：'Arduino-Uno-class' / 'Motor-Servo-class'）。
每個 entry 存一組檔案（base/lid 或 mount，含 STL+STEP）+ meta.json fingerprint。
fingerprint 從 spec 幾何欄位 hash，spec 變動則自動失效。

支援兩類 entry：
  - 'two_piece' (Brain)：base.stl + lid.stl + base.step + lid.step
  - 'mount' (Tier 4)：mount.stl + mount.step
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHELLS_DIR = _PROJECT_ROOT / "shells"


def _fingerprint_pcb(spec) -> str:
    """PCBSpec 幾何 hash — 取尺寸 + pins + mounting_holes + sub_components 摘要。

    sub_components 只取 (name, anchor_x, anchor_y, body_l, body_w, body_h, protrudes)，
    thermal 欄位不影響殼體幾何，不納入 fingerprint。
    """
    geo = {
        'name': spec.name,
        'L': spec.length,
        'W': spec.width,
        'T': spec.pcb_thickness,
        'pins': [(p.pad_index, p.x, p.y) for p in spec.pins],
        'holes': [(h.x, h.y, h.diameter) for h in spec.mounting_holes],
        'subs': [(sc.name, sc.anchor_x, sc.anchor_y,
                  sc.body_l, sc.body_w, sc.body_h, sc.protrudes)
                 for sc in spec.sub_components],
        'hgrps': [(g.name, g.profile, g.rows, g.pin_indices)
                  for g in spec.header_groups],
    }
    raw = json.dumps(geo, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _fingerprint_mount(spec_obj) -> str:
    """Mount spec dataclass 幾何 hash — 排除 thermal_* 欄位。"""
    if not is_dataclass(spec_obj):
        return hashlib.sha256(repr(spec_obj).encode()).hexdigest()[:16]
    d = {k: v for k, v in asdict(spec_obj).items()
         if not k.startswith('thermal_')}
    raw = json.dumps(d, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _entry_dir(class_name: str) -> Path:
    return SHELLS_DIR / class_name


def get_cached_shell(class_name: str, fingerprint: str) -> Optional[Dict[str, str]]:
    """命中則回傳 {logical_name: cached_path, 'kind': ..., 'fingerprint': ...}；否則 None。"""
    d = _entry_dir(class_name)
    meta_path = d / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if meta.get('fingerprint') != fingerprint:
        return None
    files = meta.get('files', {})
    # 把 meta 內所有額外欄位（spec_dict / tris / label …）一併返回
    out = {k: v for k, v in meta.items() if k not in ('files', 'class_name')}
    for logical, fname in files.items():
        fpath = d / fname
        if not fpath.exists():
            return None
        out[logical] = str(fpath)
    return out


def save_shell_to_cache(
    class_name: str,
    fingerprint: str,
    kind: str,
    files: Dict[str, str],
    extra_meta: Optional[dict] = None,
) -> str:
    """寫快取。`files` = {logical_name: src_path}，例 {'base_stl': '/tmp/x.stl', 'lid_stl': ...}。"""
    d = _entry_dir(class_name)
    d.mkdir(parents=True, exist_ok=True)

    file_map: Dict[str, str] = {}
    for logical, src in files.items():
        ext = Path(src).suffix.lower()
        cached_name = f'{logical}{ext}'
        shutil.copy2(src, d / cached_name)
        file_map[logical] = cached_name

    meta = {
        'class_name': class_name,
        'kind':        kind,
        'fingerprint': fingerprint,
        'files':       file_map,
    }
    if extra_meta:
        meta.update(extra_meta)
    (d / 'meta.json').write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    return str(d)


def fingerprint_for_spec(spec) -> str:
    """統一入口 — PCBSpec 走 _fingerprint_pcb，其他 dataclass 走 _fingerprint_mount。"""
    from lib.pcb._types import PCBSpec
    if isinstance(spec, PCBSpec):
        return _fingerprint_pcb(spec)
    return _fingerprint_mount(spec)
