"""rag_components.py — Component-level RAG queries.

Handles:
  - Building component vector index from COMPONENT_REGISTRY
  - Semantic search over components with metadata filters
  - S3: Abstract function -> component mapping
"""
from __future__ import annotations

import json
import logging
import re as _re
from typing import Any, Dict, List, Optional

from .rag_embedding import (
    COLL_COMPONENTS,
    DISTANCE_THRESHOLDS,
    _get_db,
    _sanitize_filter,
    embed_text,
    embed_texts,
)

_log = logging.getLogger("cadhllm.rag")


def _component_to_text(spec) -> str:
    """Convert ComponentSpec to weighted embedding text.

    Name appears twice = higher weight in embedding space.
    """
    tags_str = " ".join(spec.tags) if spec.tags else ""
    return (
        f"{spec.name} {spec.class_name} | "
        f"tags: {tags_str} | "
        f"voltage {spec.voltage_v}V current {spec.current_ma}mA "
        f"thermal {spec.thermal_mw}mW weight {spec.weight_g}g | "
        f"size {spec.length_mm}x{spec.width_mm}x{spec.height_mm}mm | "
        f"{spec.name}"
    )


def _component_role(class_name: str) -> str:
    """Reverse-lookup component role from TAXONOMY_CONFIG."""
    try:
        from ..config import TAXONOMY_CONFIG
    except ImportError:
        from config import TAXONOMY_CONFIG
    for role, types in TAXONOMY_CONFIG.get("component_taxonomy", {}).items():
        if class_name in types:
            return role
    return "Unknown"


def build_component_index(force: bool = False):
    """Build component vector index from COMPONENT_REGISTRY.

    Parameters
    ----------
    force : bool
        True = drop and rebuild; False = skip if exists with same count
    """
    import pyarrow as pa

    try:
        from ..registry import COMPONENT_REGISTRY
    except ImportError:
        from registry import COMPONENT_REGISTRY

    db = _get_db()

    if not force:
        try:
            tbl = db.open_table(COLL_COMPONENTS)
            if len(tbl) == len(COMPONENT_REGISTRY):
                _log.info("Component index exists (%d rows), skipping", len(tbl))
                return len(tbl)
        except Exception as exc:
            _log.debug("Component table check failed (will rebuild): %s", exc)

    texts = []
    records = []
    for class_name, spec in COMPONENT_REGISTRY.items():
        text = _component_to_text(spec)
        role = _component_role(class_name)
        tags_str = ",".join(spec.tags) if spec.tags else ""
        records.append({
            "class_name": class_name,
            "name": spec.name,
            "role": role,
            "text": text,
            "voltage_v": spec.voltage_v,
            "current_ma": spec.current_ma,
            "weight_g": spec.weight_g,
            "thermal_mw": spec.thermal_mw,
            "length_mm": spec.length_mm,
            "width_mm": spec.width_mm,
            "height_mm": spec.height_mm,
            "tags": tags_str,
            "enclosure_relation": spec.enclosure_relation,
            "skip_enclosure": spec.skip_enclosure,
        })
        texts.append(text)

    vectors = embed_texts(texts)
    for rec, vec in zip(records, vectors):
        rec["vector"] = vec

    try:
        db.drop_table(COLL_COMPONENTS)
    except Exception as exc:
        _log.debug("Component table drop skipped: %s", exc)

    db.create_table(COLL_COMPONENTS, data=records)
    _log.info("Component index built: %d rows", len(records))


def search_components(
    query: str,
    top_k: int = 5,
    role_filter: Optional[str] = None,
    max_voltage: Optional[float] = None,
    tags_contain: Optional[str] = None,
    include_physical: bool = False,
) -> List[Dict[str, Any]]:
    """Semantic search over components.

    Parameters
    ----------
    query : str
        Natural language query (Chinese/English)
    top_k : int
        Number of results to return
    role_filter : str, optional
        Filter by role (Brain/Sensor/Actuator/...)
    max_voltage : float, optional
        Max voltage filter
    tags_contain : str, optional
        Tag substring filter (e.g. "bus:i2c")
    include_physical : bool
        True = attach connector_ports + mounting_holes from COMPONENT_REGISTRY

    Returns
    -------
    list[dict]
        Contains class_name, name, role, score, and full metadata
    """
    db = _get_db()
    try:
        tbl = db.open_table(COLL_COMPONENTS)
    except Exception:
        _log.warning("Component index not found, call build_component_index() first")
        return []

    q_vec = embed_text(query)

    where_clauses = []
    if role_filter:
        where_clauses.append(f"role = '{_sanitize_filter(role_filter)}'")
    if max_voltage is not None:
        where_clauses.append(f"voltage_v <= {float(max_voltage)}")
    if tags_contain:
        where_clauses.append(f"tags LIKE '%{_sanitize_filter(tags_contain)}%'")

    search = tbl.search(q_vec).limit(top_k)
    if where_clauses:
        search = search.where(" AND ".join(where_clauses))

    results = search.to_list()

    # Distance threshold filtering — discard low-quality matches
    max_dist = DISTANCE_THRESHOLDS.get(COLL_COMPONENTS, 1.2)
    results = [r for r in results if r.get("_distance", 0.0) <= max_dist]

    registry = None
    if include_physical:
        try:
            from ..registry import COMPONENT_REGISTRY
        except ImportError:
            from registry import COMPONENT_REGISTRY
        registry = COMPONENT_REGISTRY

    out = []
    for r in results:
        entry = {
            "class_name": r["class_name"],
            "name": r["name"],
            "role": r["role"],
            "voltage_v": r["voltage_v"],
            "current_ma": r["current_ma"],
            "tags": r["tags"],
            "score": r.get("_distance", 0.0),
        }
        if registry and r["class_name"] in registry:
            spec = registry[r["class_name"]]
            entry["connector_ports"] = [
                {"name": p.name, "side": p.side, "z_height": p.z}
                for p in spec.ports
            ]
            entry["mounting_holes"] = [
                {"x": h.x, "y": h.y, "diameter": h.diameter}
                for h in spec.mounting_holes
            ]
            entry["dimensions_mm"] = f"{spec.length_mm}x{spec.width_mm}x{spec.height_mm}"
        out.append(entry)
    return out


# ════════════════════════════════════════════════════════════════
# S3: Function -> Component mapping (abstract function -> recommendation)
# ════════════════════════════════════════════════════════════════

_FUNCTION_COMPONENT_MAP: list[tuple[str, list[str], str]] = [
    # (regex_pattern, [component_classes], educational_note)
    (r"提醒|鬧鐘|alarm|remind|notify|通知|警報",
     ["Buzzer-Active-class", "Display-OLED-class"],
     "提醒功能需要聲音或視覺輸出"),
    (r"計時|timer|倒數|countdown|stopwatch",
     ["Display-OLED-class", "Buzzer-Active-class", "Button-class"],
     "計時器需要顯示倒數 + 按鈕控制 + 結束提示音"),
    (r"偵測|detect|感應|感測|sense|monitor|監測|監控",
     ["Sensor-PIR-class", "Sensor-Ultrasonic-class"],
     "偵測功能常用紅外線或超音波感測器"),
    (r"澆水|灌溉|irrigat|watering|盆栽.*澆|自動.*澆|garden.*water",
     ["Pump-Water-class", "Sensor-SoilMoisture-class", "Relay-Module-class"],
     "自動澆水需要水泵 + 土壤濕度感測 + 繼電器控制"),
    (r"溫度|溫濕|climate|氣候|weather|temperature|humid",
     ["Sensor-TempHumid-class", "Display-OLED-class"],
     "環境監測需要溫濕度感測器 + 顯示"),
    (r"燈|light|照明|夜燈|lamp|glow|luminous|發光",
     ["Lighting-NeoPixel-class", "Lighting-LED-PWM-class"],
     "照明功能使用 LED 或 NeoPixel 燈條"),
    (r"音樂|播放|music|play|song|melody|聲音|sound|audio",
     ["MP3-Module-class", "Speaker-class"],
     "音訊播放需要 MP3 模組 + 喇叭"),
    (r"移動|走路|drive|遙控車|避障車|避障|follow.*line|追蹤|行走",
     ["Motor-DC-class", "Sensor-Ultrasonic-class"],
     "移動功能需要馬達驅動 + 距離感測避障"),
    (r"旋轉|轉動|角度|rotate|angle|sweep|擺動",
     ["Motor-Servo-class"],
     "角度控制使用伺服馬達"),
    (r"顯示|show|display|screen|螢幕|資訊",
     ["Display-OLED-class"],
     "資訊顯示使用 OLED 或 LCD 螢幕"),
    (r"按|button|press|觸發|trigger|switch|開關",
     ["Button-class", "Switch-Generic-class"],
     "使用者互動需要按鈕或開關"),
    (r"喝水|飲水|drink|hydrat",
     ["Buzzer-Active-class", "Display-OLED-class", "Button-class"],
     "喝水提醒需要提示音 + 顯示 + 重置按鈕"),
    (r"門禁|門鎖|door.*lock|鎖|lock|access.*control|進出管制",
     ["Motor-Servo-class", "Sensor-PIR-class", "Buzzer-Active-class"],
     "門控需要伺服馬達開閉 + PIR 偵測 + 提示音"),
    (r"霧|mist|加濕|humidif|噴霧",
     ["Mist-Atomizer-class", "Sensor-TempHumid-class"],
     "加濕功能使用霧化器 + 濕度回饋"),
]

_COMPONENT_KEYWORDS = _re.compile(
    r"-class|arduino|esp32|raspberry|servo|motor|oled|lcd|led|buzzer|"
    r"pump|relay|sensor|pir|dht|neopixel|ultrasonic|stepper",
    _re.IGNORECASE,
)


def resolve_abstract_functions(instruction: str) -> list[dict]:
    """S3: Derive possible components from abstract function description.

    Only triggers when prompt has no explicit component names (avoid interference).
    Returns [{"classes": [...], "reason": "..."}].
    """
    if _COMPONENT_KEYWORDS.search(instruction):
        return []

    matches = []
    seen_classes: set[str] = set()
    for pattern, classes, reason in _FUNCTION_COMPONENT_MAP:
        if _re.search(pattern, instruction, _re.IGNORECASE):
            new_classes = [c for c in classes if c not in seen_classes]
            if new_classes:
                matches.append({"classes": new_classes, "reason": reason})
                seen_classes.update(new_classes)
    return matches
