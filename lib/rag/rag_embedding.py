"""rag_embedding.py — Embedding model management + LanceDB connection.

Singleton management for:
  - LanceDB connection (thread-safe)
  - SentenceTransformer model loading (thread-safe)
  - embed_text / embed_texts helpers with LRU cache
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import List

_log = logging.getLogger("cadhllm.rag")
_lock = threading.RLock()  # RLock: 允許同 thread 重入（ensure_initialized → _get_db/_get_embed_model）

# ── Lazy singletons ──────────────────────────────────────────
_db = None
_embed_model = None
# Embedding model: bge-base-zh-v1.5 (768-dim, ~200MB)
# Upgraded from bge-small-zh-v1.5 (512-dim, 48MB) for better Chinese semantic precision.
# Override via env CADHLLM_EMBED_MODEL if needed.
_EMBED_MODEL_NAME = os.environ.get("CADHLLM_EMBED_MODEL", "BAAI/bge-base-zh-v1.5")
_EMBED_DIM = 768  # bge-base-zh-v1.5 output dimension

# Collection name constants
COLL_COMPONENTS = "components"
COLL_CASES = "cases"
COLL_ASSEMBLY = "assembly"

# Per-collection distance thresholds (L2 distance, lower = more similar).
# Results with _distance above this value are filtered out as low-quality.
# Calibrated for bge-base-zh-v1.5 normalized embeddings (L2 range ~0–2).
DISTANCE_THRESHOLDS: dict[str, float] = {
    COLL_COMPONENTS: 1.2,   # 元件搜尋：較嚴格，避免推薦無關元件
    COLL_CASES:      1.4,   # 案例搜尋：稍寬鬆，歷史案例多樣性有價值
    COLL_ASSEMBLY:   1.4,   # 組裝決策：同案例
    "comp_wiring":   0.6,   # 接線模板：最嚴格（已有 score=0.7 閾值對應 dist≈0.3）
}


def _sanitize_filter(value: str) -> str:
    """Escape single quotes for safe SQL string literal ('' is standard SQL escape)."""
    return value.replace("'", "''")


def _rag_db_path() -> str:
    return os.environ.get(
        "CADHLLM_RAG_DB",
        str(Path(__file__).parent.parent.parent / "data" / "rag_db"),
    )


def _get_db():
    """Get LanceDB connection (singleton, thread-safe)."""
    global _db
    with _lock:
        if _db is not None:
            return _db
        import lancedb
        db_path = _rag_db_path()
        Path(db_path).mkdir(parents=True, exist_ok=True)
        _db = lancedb.connect(db_path)
        _log.info("LanceDB connected: %s", db_path)
        return _db


def _get_embed_model():
    """Get embedding model (singleton, thread-safe)."""
    global _embed_model
    with _lock:
        if _embed_model is not None:
            return _embed_model
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(_EMBED_MODEL_NAME)
        _log.info("Embedding model loaded: %s (dim=%d)",
                  _EMBED_MODEL_NAME,
                  _embed_model.get_sentence_embedding_dimension())
        return _embed_model


def check_db_dimension_compat():
    """Check if existing DB collections match current embedding dimension.

    If dimension mismatch is detected, drop the stale collection so it
    will be rebuilt on next index build. Called at startup.
    """
    try:
        db = _get_db()
    except Exception:
        return
    model = _get_embed_model()
    expected_dim = model.get_sentence_embedding_dimension()
    all_colls = [COLL_COMPONENTS, COLL_CASES, COLL_ASSEMBLY, "comp_wiring"]
    for coll_name in all_colls:
        try:
            tbl = db.open_table(coll_name)
            sample = tbl.head(1)
            if len(sample) == 0:
                continue
            vec = sample["vector"][0]
            actual_dim = len(vec) if hasattr(vec, "__len__") else 0
        except Exception:
            continue  # table doesn't exist yet
        # NOTE: drop_table failures must NOT be swallowed — a known dimension
        # mismatch that we fail to drop would let a stale-dim collection survive
        # and silently corrupt downstream search. Let it propagate.
        if actual_dim and actual_dim != expected_dim:
            _log.warning(
                "Collection '%s' dim=%d != model dim=%d — dropping for rebuild",
                coll_name, actual_dim, expected_dim,
            )
            db.drop_table(coll_name)


@lru_cache(maxsize=512)
def _cached_embed_single(text_hash: str, text: str) -> tuple:
    """Cache single embedding to avoid recomputation on repeated queries."""
    model = _get_embed_model()
    vec = model.encode(text, normalize_embeddings=True)
    return tuple(vec.tolist())


def embed_text(text: str) -> list:
    """Compute embedding vector for text (with LRU cache)."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()
    return list(_cached_embed_single(h, text))


def embed_texts(texts: List[str]) -> List[list]:
    """Batch compute embeddings (no cache, direct batch encode)."""
    model = _get_embed_model()
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]
