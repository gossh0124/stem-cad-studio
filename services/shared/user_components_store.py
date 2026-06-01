"""shared/user_components_store.py — 用戶自填元件暫存池 CRUD。

目錄結構：
  user_components/
    _index.json              — 全域索引（class_name → 摘要）
    {class_name}/spec.json   — 物理規格（對齊 ComponentSpec 欄位）
    {class_name}/used_in.json — 使用紀錄 [{job_id, project_name, ts}]
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOCK = threading.Lock()

_USER_COMP_ROOT = Path(__file__).parents[2] / "user_components"
_INDEX_PATH = _USER_COMP_ROOT / "_index.json"


_USER_ENCLOSURE_RELATIONS = frozenset({"internal", "breadboard", "panel", "external", "embedded"})
_SAFE_CLASS_NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


@dataclass
class UserComponentSpec:
    name: str
    class_name: str
    length_mm: float
    width_mm: float
    height_mm: float
    voltage_v: float = 5.0
    current_ma: float = 50.0
    weight_g: float = 10.0
    thermal_mw: float = 0.0
    enclosure_relation: str = "external"  # user 元件預設殼外（最保守，跳過 solver 幾何處理）
    skip_enclosure: bool = True  # legacy mirror; auto-synced via __post_init__
    tags: List[str] = field(default_factory=list)
    connector_ports: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "user"

    def __post_init__(self):
        if self.enclosure_relation not in _USER_ENCLOSURE_RELATIONS:
            raise ValueError(
                f"enclosure_relation 必須是 {sorted(_USER_ENCLOSURE_RELATIONS)} 之一，"
                f"收到 {self.enclosure_relation!r}（class_name={self.class_name}）"
            )
        # 雙向同步 — 與 lib/registry.ComponentSpec 一致
        if self.enclosure_relation != "internal":
            self.skip_enclosure = True
        elif self.skip_enclosure:
            self.enclosure_relation = "external"


# ── 內部 helpers ─────────────────────────────────────────────────

def _validate_class_name(class_name: str) -> None:
    """Reject class_name values that could cause path traversal."""
    if not _SAFE_CLASS_NAME.match(class_name):
        raise ValueError(f"Invalid class_name: {class_name!r}")
    resolved = (_USER_COMP_ROOT / class_name).resolve()
    if not str(resolved).startswith(str(_USER_COMP_ROOT.resolve())):
        raise ValueError(f"Path traversal detected: {class_name!r}")


def _comp_dir(class_name: str) -> Path:
    _validate_class_name(class_name)
    return _USER_COMP_ROOT / class_name


def _read_json(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_index() -> Dict[str, Any]:
    idx = _read_json(_INDEX_PATH)
    if idx is None:
        return {"version": "1.0", "components": {}}
    return idx


def _save_index(idx: Dict[str, Any]) -> None:
    _write_json(_INDEX_PATH, idx)


# ── CRUD ─────────────────────────────────────────────────────────

def add_component(spec: UserComponentSpec) -> Path:
    """新增或覆寫用戶元件規格。回傳 spec.json 路徑。"""
    if not spec.name or not spec.class_name or not spec.tags:
        raise ValueError("UserComponentSpec 必須有 name, class_name, tags")

    cdir = _comp_dir(spec.class_name)
    spec_path = cdir / "spec.json"

    with _LOCK:
        _write_json(spec_path, asdict(spec))

        if not (cdir / "used_in.json").exists():
            _write_json(cdir / "used_in.json", [])

        idx = _load_index()
        idx["components"][spec.class_name] = {
            "name": spec.name,
            "n_projects": 0,
            "tags": spec.tags,
            "source": spec.source,
        }
        _save_index(idx)

    return spec_path


def record_usage(class_name: str, job_id: str, project_name: str) -> None:
    """記錄元件在某專案中被使用。"""
    cdir = _comp_dir(class_name)
    used_path = cdir / "used_in.json"

    rec = {"job_id": job_id, "project_name": project_name,
           "ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}

    with _LOCK:
        records: list = _read_json(used_path) or []
        if any(r["job_id"] == job_id for r in records):
            return
        records.append(rec)
        _write_json(used_path, records)

        idx = _load_index()
        entry = idx["components"].get(class_name)
        if entry:
            entry["n_projects"] = len({r["project_name"] for r in records})
            _save_index(idx)


def get_spec(class_name: str) -> Optional[UserComponentSpec]:
    """讀取用戶元件規格。"""
    data = _read_json(_comp_dir(class_name) / "spec.json")
    if data is None:
        return None
    return UserComponentSpec(**{k: v for k, v in data.items()
                               if k in UserComponentSpec.__dataclass_fields__})


def list_components() -> Dict[str, Dict[str, Any]]:
    """回傳所有用戶元件索引（class_name → 摘要）。"""
    return _load_index().get("components", {})


def remove_component(class_name: str) -> bool:
    """移除用戶元件。回傳是否實際刪除。"""
    import shutil
    cdir = _comp_dir(class_name)
    if not cdir.exists():
        return False

    with _LOCK:
        shutil.rmtree(cdir)
        idx = _load_index()
        idx["components"].pop(class_name, None)
        _save_index(idx)

    return True


# ── promote 候選 ─────────────────────────────────────────────────

def _count_projects(class_name: str) -> int:
    """計算元件被多少不同專案使用。"""
    records = _read_json(_comp_dir(class_name) / "used_in.json") or []
    return len({r["project_name"] for r in records})


def promote_candidates(min_projects: int = 3) -> List[Tuple[str, int]]:
    """回傳 n_projects >= min_projects 的 promote 候選，按使用次數降序。"""
    idx = _load_index()
    candidates = []
    for cn, info in idx.get("components", {}).items():
        n = info.get("n_projects", 0)
        if n >= min_projects:
            candidates.append((cn, n))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates
