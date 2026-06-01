"""lib/rag/rag_wiring.py — Wiring-specific RAG index for unknown component matching.

Layer 2: 未知元件 → 語義搜尋已知元件的 pin pattern → 推斷接線。
索引來源：data/component_datasheet_verified.json 的 pin_layout + wiring_hints。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .rag_embedding import (
    _get_db,
    embed_text,
    embed_texts,
)

_log = logging.getLogger("cadhllm.rag.wiring")

COLL_WIRING = "comp_wiring"

# Similarity threshold: scores above this indicate a reliable match
_INFER_THRESHOLD = 0.7

# ── Datasheet path ──────────────────────────────────────────────
_DS_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data" / "component_datasheet_verified.json"
)

# MCU / power-supply / chassis — 不是可接線的感測/致動元件
_SKIP_KEYS = frozenset({
    "Arduino-Uno-class", "ESP32-class", "RaspberryPi-class", "Microbit-class",
    "Battery-AA-class", "Battery-LiPo-class", "USB-5V-class",
    "AC-Adapter-class", "USB-Adapter-class",
    "Chassis-Car-class",
})


# ── Text conversion ─────────────────────────────────────────────

def _pin_layout_to_text(comp_key: str, comp_data: dict) -> str:
    """將元件的 pin layout 轉為 embedding 文字。

    格式範例：
    "DHT22 temperature humidity sensor | pins: VCC(PWR,5V) DATA(GPIO,digital_out) GND |
     protocol: single-wire | passive: DATA pullup 4.7kΩ | decoupling: 100nF"

    包含：元件名 + pin 名/類型/方向 + protocol + passive + decoupling。
    元件名出現兩次以提高 embedding 權重。
    """
    identity = comp_data.get("identity", {})
    full_name = identity.get("full_name", comp_key)

    # ── 收集 pin 描述 ──
    pin_parts: list[str] = []
    pin_types_seen: set[str] = set()
    layout = comp_data.get("pin_layout", {})
    for group in layout.get("header_groups", []):
        for pin in group.get("pins", []):
            pname = pin.get("name", "?")
            ptype = pin.get("type", "")
            direction = pin.get("direction", "")
            vdomain = pin.get("voltage_domain", "")

            # 建構 pin 描述文字
            desc_parts = [ptype] if ptype else []
            if direction and direction != "other":
                desc_parts.append(direction)
            if vdomain and vdomain not in ("n/a", ""):
                desc_parts.append(vdomain)

            if desc_parts:
                pin_parts.append(f"{pname}({','.join(desc_parts)})")
            else:
                pin_parts.append(pname)

            if ptype:
                pin_types_seen.add(ptype)

    pins_str = " ".join(pin_parts) if pin_parts else "no-pins"

    # ── Protocol ──
    electrical = comp_data.get("electrical", {})
    protocol = electrical.get("protocol", "")
    # 從 pin types 推斷 protocol（若 datasheet 未顯式標記）
    if not protocol:
        if "I2C" in pin_types_seen:
            protocol = "I2C"
        elif "SPI" in pin_types_seen:
            protocol = "SPI"
        elif "UART" in pin_types_seen:
            protocol = "UART"

    # ── I2C address ──
    i2c_addr = electrical.get("i2c_address", "")

    # ── Wiring hints: passives + decoupling ──
    hints = comp_data.get("wiring_hints", {})
    passives = hints.get("passives", [])
    passive_parts: list[str] = []
    for p in passives:
        passive_parts.append(
            f"{p.get('pin', '?')} {p.get('topo', '')} {p.get('value', '')}"
        )
    passives_str = "; ".join(passive_parts) if passive_parts else ""

    decoupling = hints.get("decoupling", "")

    # ── Cross-component hints ──
    cross = hints.get("cross_component", [])
    cross_parts: list[str] = []
    for c in cross:
        target = c.get("target_comp", "")
        note = c.get("note", "")
        cross_parts.append(f"{target}:{note}" if note else target)
    cross_str = "; ".join(cross_parts) if cross_parts else ""

    # ── VCC voltage ──
    vcc = hints.get("vcc", "")
    if not vcc:
        # 從 PWR pin 推斷
        for group in layout.get("header_groups", []):
            for pin in group.get("pins", []):
                if pin.get("type") == "PWR":
                    vd = pin.get("voltage_domain", "")
                    if vd in ("5V", "3V3", "3.3V"):
                        vcc = vd.replace("3V3", "3.3V")
                        break
            if vcc:
                break

    # ── Voltage / current summary ──
    voltage_str = ""
    v_typ = electrical.get("voltage_typ_v") or electrical.get("voltage_operating_v")
    if v_typ:
        voltage_str = f"{v_typ}V"
    current_str = ""
    c_typ = electrical.get("current_typ_ma") or electrical.get("current_max_ma")
    if c_typ:
        current_str = f"{c_typ}mA"

    # ── Pin count ──
    total_pins = sum(
        g.get("pin_count", 0)
        for g in layout.get("header_groups", [])
    )

    # ── Assemble text ──
    parts = [
        f"{full_name} {comp_key}",
        f"pins({total_pins}): {pins_str}",
    ]
    if vcc:
        parts.append(f"vcc: {vcc}")
    if voltage_str or current_str:
        parts.append(f"power: {voltage_str} {current_str}".strip())
    if protocol:
        parts.append(f"protocol: {protocol}")
    if i2c_addr:
        parts.append(f"i2c_addr: {i2c_addr}")
    if passives_str:
        parts.append(f"passive: {passives_str}")
    if decoupling:
        parts.append(f"decoupling: {decoupling}")
    if cross_str:
        parts.append(f"cross: {cross_str}")
    # Repeat name for embedding weight
    parts.append(full_name)

    return " | ".join(parts)


def _pin_summary(comp_data: dict) -> str:
    """產生簡短的 pin 摘要（用於搜尋結果顯示）。"""
    parts: list[str] = []
    layout = comp_data.get("pin_layout", {})
    hints = comp_data.get("wiring_hints", {})
    vcc = hints.get("vcc", "")

    for group in layout.get("header_groups", []):
        for pin in group.get("pins", []):
            pname = pin.get("name", "?")
            ptype = pin.get("type", "")
            vd = pin.get("voltage_domain", "")

            if ptype == "NC":
                continue
            if ptype == "GND":
                parts.append("GND")
                continue
            if ptype == "PWR":
                v = vcc or vd
                parts.append(f"{pname}({v})" if v else pname)
                continue
            parts.append(f"{pname}({ptype})")

    return " ".join(parts)


# ── Index build ──────────────────────────────────────────────────

def _load_datasheet() -> dict:
    """載入 component_datasheet_verified.json。"""
    if not _DS_PATH.exists():
        _log.warning("Datasheet 不存在: %s", _DS_PATH)
        return {}
    with open(_DS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_wiring_index(force: bool = False) -> int:
    """建立 wiring pin pattern 向量索引。

    從 component_datasheet_verified.json 讀取所有可接線元件，
    為每個元件建立 pin pattern embedding。

    Args:
        force: True = 強制重建；False = 若數量相同則跳過

    Returns:
        索引的元件數量
    """
    ds = _load_datasheet()
    if not ds:
        return 0

    # 篩選可索引元件：有 pin_layout 且不在排除名單
    indexable: list[tuple[str, dict]] = []
    for comp_key, comp_data in ds.items():
        if comp_key == "_meta":
            continue
        if comp_key in _SKIP_KEYS:
            continue
        layout = comp_data.get("pin_layout", {})
        if not layout.get("header_groups"):
            continue
        indexable.append((comp_key, comp_data))

    if not indexable:
        _log.warning("No indexable components found")
        return 0

    db = _get_db()

    # 若索引已存在且數量相同，跳過
    if not force:
        try:
            tbl = db.open_table(COLL_WIRING)
            if len(tbl) == len(indexable):
                _log.info(
                    "Wiring index exists (%d rows), skipping", len(tbl)
                )
                return len(tbl)
        except Exception:
            pass

    # 建構 records + embeddings
    texts: list[str] = []
    records: list[dict[str, Any]] = []

    for comp_key, comp_data in indexable:
        text = _pin_layout_to_text(comp_key, comp_data)
        identity = comp_data.get("identity", {})
        full_name = identity.get("full_name", comp_key)
        hints = comp_data.get("wiring_hints", {})
        summary = _pin_summary(comp_data)

        # 偵測 protocol
        electrical = comp_data.get("electrical", {})
        protocol = electrical.get("protocol", "")
        if not protocol:
            pin_types = set()
            for g in comp_data.get("pin_layout", {}).get("header_groups", []):
                for p in g.get("pins", []):
                    pt = p.get("type", "")
                    if pt:
                        pin_types.add(pt)
            if "I2C" in pin_types:
                protocol = "I2C"
            elif "SPI" in pin_types:
                protocol = "SPI"
            elif "UART" in pin_types:
                protocol = "UART"

        total_pins = sum(
            g.get("pin_count", 0)
            for g in comp_data.get("pin_layout", {}).get("header_groups", [])
        )

        records.append({
            "comp_key": comp_key,
            "short_name": full_name,
            "text": text,
            "pin_summary": summary,
            "protocol": protocol,
            "pin_count": total_pins,
            "has_passives": bool(hints.get("passives")),
            "has_decoupling": bool(hints.get("decoupling")),
            "wiring_hints_json": json.dumps(hints, ensure_ascii=False)
            if hints else "{}",
        })
        texts.append(text)

    # Batch embed
    try:
        vectors = embed_texts(texts)
    except Exception as exc:
        _log.error("rag_wiring: embed_texts failed, index not built: %s", exc)
        return 0
    for rec, vec in zip(records, vectors):
        rec["vector"] = vec

    # Drop existing + create
    try:
        db.drop_table(COLL_WIRING)
    except Exception:
        pass

    db.create_table(COLL_WIRING, data=records)
    _log.info("Wiring index built: %d rows", len(records))
    return len(records)


def _ensure_index() -> bool:
    """確保索引已建立（lazy init）。回傳 True 表示索引可用。"""
    db = _get_db()
    try:
        tbl = db.open_table(COLL_WIRING)
        if len(tbl) > 0:
            return True
    except Exception:
        pass

    count = build_wiring_index(force=False)
    return count > 0


# ── Search ───────────────────────────────────────────────────────

def search_similar_wiring(
    query: str,
    top_k: int = 3,
    protocol_filter: str | None = None,
) -> list[dict]:
    """語義搜尋最相似的元件 pin pattern。

    Args:
        query: 自然語言描述或元件名稱
               例："BME280 溫濕度氣壓感測器 I2C 介面"
               例："GPS module UART TX RX"
        top_k: 回傳前 N 個最相似結果
        protocol_filter: 可選 protocol 篩選 ("I2C", "SPI", "UART" 等)

    Returns:
        [
            {
                "comp_key": "Sensor-TempHumid-class",
                "short_name": "DHT22 (AM2302) ...",
                "score": 0.85,
                "pin_summary": "VCC(5V) DATA(GPIO) GND",
                "protocol": "single-wire",
                "wiring_hints": {...},
                "template": WiringTemplate(...)  # 可直接使用的 template
            },
            ...
        ]
    """
    if not _ensure_index():
        _log.warning("Wiring index not available")
        return []

    db = _get_db()
    try:
        tbl = db.open_table(COLL_WIRING)
    except Exception:
        _log.warning("Cannot open wiring index table")
        return []

    q_vec = embed_text(query)
    search = tbl.search(q_vec).limit(top_k)

    if protocol_filter:
        from .rag_embedding import _sanitize_filter
        search = search.where(
            f"protocol = '{_sanitize_filter(protocol_filter)}'"
        )

    results = search.to_list()

    # Lazy import to avoid circular dependency at module level
    from ..wiring.template_gen import (
        template_from_datasheet,
        _apply_override,
        _DS_TO_SHORT,
    )

    out: list[dict] = []
    for r in results:
        comp_key = r["comp_key"]
        short_name = _DS_TO_SHORT.get(comp_key, comp_key)

        # 取得 WiringTemplate
        tmpl = template_from_datasheet(comp_key)
        tmpl = _apply_override(short_name, tmpl)

        # 解析 wiring_hints
        hints_raw = r.get("wiring_hints_json", "{}")
        try:
            hints = json.loads(hints_raw)
        except (json.JSONDecodeError, TypeError):
            hints = {}

        # LanceDB 距離分數：越小越相似，轉為 0-1 相似度
        distance = r.get("_distance", 0.0)
        score = max(0.0, 1.0 - distance)

        out.append({
            "comp_key": comp_key,
            "short_name": short_name,
            "score": round(score, 4),
            "pin_summary": r.get("pin_summary", ""),
            "protocol": r.get("protocol", ""),
            "wiring_hints": hints,
            "template": tmpl,
        })

    return out


# ── Inference entry point ────────────────────────────────────────

def infer_template(query: str) -> "WiringTemplate | None":
    """Layer 2 入口：為未知元件推斷 WiringTemplate。

    1. search_similar_wiring 找最近鄰
    2. 若 score > threshold，回傳最近鄰的 template（標記 source）
    3. 否則回傳 None（交給 Layer 3 或 fallback）

    Args:
        query: 元件名稱或描述

    Returns:
        WiringTemplate（帶 _rag_source 標記）或 None
    """
    from ..wiring.engine import WiringTemplate

    results = search_similar_wiring(query, top_k=1)
    if not results:
        return None

    best = results[0]
    if best["score"] < _INFER_THRESHOLD:
        _log.debug(
            "RAG wiring: best match %s score=%.3f < threshold %.2f, skip",
            best["comp_key"], best["score"], _INFER_THRESHOLD,
        )
        return None

    tmpl = best["template"]
    if tmpl is None:
        return None

    _log.info(
        "RAG wiring inferred: query=%r → %s (score=%.3f)",
        query, best["comp_key"], best["score"],
    )

    # 標記為 RAG 推斷結果，讓下游知道來源
    # （不修改 WiringTemplate dataclass，改用 annotation dict）
    tmpl._rag_source = {  # type: ignore[attr-defined]
        "matched_key": best["comp_key"],
        "score": best["score"],
        "inferred": True,
    }

    return tmpl
