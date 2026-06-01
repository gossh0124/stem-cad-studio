"""thermal_index.py — 各 component 熱源資料的查詢索引（長期記憶讀取層）。

Z1 階段把 thermal_typical_mw 等欄位寫入 lib/pcb/*.py 與 lib/cad/mounts.py，
本模組負責把所有 component 的熱源資料聚合輸出成單一 JSON，
供前端 3D View / BOM / 熱場 solver 不必 import Python 模組就能取用。

輸出位置：shells/thermal_index.json（與 shell_cache 同 root）

每個 entry：
  {
    "class_name": "Arduino-Uno-class",
    "name": "Arduino Uno R3",
    "tier": "MCU" | "Module" | "Mount",
    "total_typical_mw": 400.0,
    "total_idle_mw": 40.0,
    "total_peak_mw": 755.0,
    "centroid": {"x": 36.7, "y": 20.5},   # 加權熱源重心（mw weighted）
    "dominant": {"name": "ATmega328P", "mw": 200.0, "source": "..."},
    "sources": [{x, y, z, mw, sub_name, source}, ...],   # 完整熱源清單
  }
"""
from __future__ import annotations
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
THERMAL_INDEX_PATH = _PROJECT_ROOT / "shells" / "thermal_index.json"


def _pcb_entry(class_name: str, spec, tier: str) -> dict:
    """從 PCBSpec 生 thermal index entry。"""
    sources = spec.thermal_profile('typical')
    total_typ = spec.total_thermal_mw('typical')
    total_idle = spec.total_thermal_mw('idle')
    total_peak = spec.total_thermal_mw('peak')

    # 加權重心（mw 為權重）
    centroid = {'x': 0.0, 'y': 0.0}
    if total_typ > 0:
        cx = sum(s['x'] * s['mw'] for s in sources) / total_typ
        cy = sum(s['y'] * s['mw'] for s in sources) / total_typ
        centroid = {'x': round(cx, 2), 'y': round(cy, 2)}

    # 主導熱源（mw 最大）
    dominant: dict = {}
    if sources:
        top = max(sources, key=lambda s: s['mw'])
        dominant = {'name': top['sub_name'], 'mw': top['mw'],
                    'source': top['source']}

    return {
        'class_name':       class_name,
        'name':             spec.name,
        'tier':             tier,
        'total_typical_mw': total_typ,
        'total_idle_mw':    total_idle,
        'total_peak_mw':    total_peak,
        'centroid':         centroid,
        'dominant':         dominant,
        'sources':          sources,
    }


def _mount_entry(class_name: str, kind: str, label: str, spec_obj) -> dict:
    """從 mount spec dataclass 生 thermal index entry。"""
    if not is_dataclass(spec_obj):
        return {}
    typ = getattr(spec_obj, 'thermal_typical_mw', 0.0)
    idle = getattr(spec_obj, 'thermal_idle_mw', 0.0)
    peak = getattr(spec_obj, 'thermal_peak_mw', 0.0)
    formula = getattr(spec_obj, 'thermal_formula', '')
    source = getattr(spec_obj, 'thermal_source', '')

    # mount 是單一熱源（內嵌設備），位置 = 殼體中心 (0,0)
    sources: List[dict] = []
    if typ > 0:
        sources.append({
            'sub_name': label,
            'package':  kind,
            'x': 0.0, 'y': 0.0, 'z': 0.0,
            'body_l': 0.0, 'body_w': 0.0,
            'mw': typ,
            'formula': formula,
            'source':  source,
        })
    return {
        'class_name':       class_name,
        'name':             label,
        'tier':             'Mount',
        'total_typical_mw': typ,
        'total_idle_mw':    idle,
        'total_peak_mw':    peak,
        'centroid':         {'x': 0.0, 'y': 0.0},
        'dominant':         {'name': label, 'mw': typ, 'source': source},
        'sources':          sources,
    }


def build_thermal_index() -> Dict[str, dict]:
    """走 PCB_REGISTRY + ALL_MOUNTS 聚合成 {class_name: entry}。"""
    from lib.pcb import PCB_REGISTRY
    from lib.cad.mounts import ALL_MOUNTS, DEFAULT_MOUNT_SPECS

    # tier 判斷：四個 MCU 為 MCU，其他 PCB 為 Module
    mcu_classes = {'Arduino-Uno-class', 'ESP32-class',
                   'Microbit-class', 'RaspberryPi-class'}
    out: Dict[str, dict] = {}
    for cn, spec in PCB_REGISTRY.items():
        tier = 'MCU' if cn in mcu_classes else 'Module'
        out[cn] = _pcb_entry(cn, spec, tier)
    for cn, (kind, label, _builder) in ALL_MOUNTS.items():
        mount_spec = DEFAULT_MOUNT_SPECS.get(kind)
        if mount_spec is not None:
            out[cn] = _mount_entry(cn, kind, label, mount_spec)
    return out


def write_thermal_index(path: Path | None = None) -> Path:
    """生成 thermal_index.json（持久化）。"""
    target = path or THERMAL_INDEX_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    index = build_thermal_index()
    target.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding='utf-8')
    return target


def load_thermal_index(path: Path | None = None) -> Dict[str, dict]:
    """讀已存的 thermal_index.json；不存在則 build + write 後再讀。"""
    target = path or THERMAL_INDEX_PATH
    if not target.exists():
        write_thermal_index(target)
    return json.loads(target.read_text(encoding='utf-8'))


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(_PROJECT_ROOT))
    p = write_thermal_index()
    idx = load_thermal_index()
    print(f'寫入 {p}')
    print(f'共 {len(idx)} 個 component')
    for cn, e in idx.items():
        print(f'  {cn:25s} {e["tier"]:6s} '
              f'typ={e["total_typical_mw"]:7.0f}mW '
              f'centroid=({e["centroid"]["x"]:5.1f},{e["centroid"]["y"]:5.1f}) '
              f'dom={e["dominant"].get("name", "-")}')
