"""
memory_store.py
---------------
ChromaDB-backed episodic memory store for the IMDCRA system.

Each user gets an isolated namespace via their user_id.
All reads respect validity_flag and decay_score threshold filters.
All writes/updates maintain the full EpisodicMemoryRecord metadata.
"""

import os
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings

from memory_model import EpisodicMemoryRecord, _now_iso
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB client (singleton) — persisted to disk
# ---------------------------------------------------------------------------

_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        persist_dir = getattr(settings, "chroma_persist_dir", "./chroma_db")
        os.makedirs(persist_dir, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def _collection_name(user_id: str) -> str:
    """Each user gets their own ChromaDB collection."""
    # ChromaDB collection names must be alphanumeric + underscore/hyphen
    safe = str(user_id).replace("@", "_at_").replace(".", "_")
    return f"imdcra_user_{safe}"


def get_collection(user_id: str):
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=_collection_name(user_id),
        metadata={"hnsw:space": "cosine"},
    )


# ---------------------------------------------------------------------------
# Core CRUD operations
# ---------------------------------------------------------------------------

def add_memory(record: EpisodicMemoryRecord, embedding: List[float]) -> str:
    """Persist a new memory record with its embedding. Returns memory_id."""
    col = get_collection(record.user_id)
    col.add(
        ids=[record.memory_id],
        embeddings=[embedding],
        documents=[record.fact_text],
        metadatas=[record.to_metadata()],
    )
    logger.info(f"[MemoryStore] Added memory {record.memory_id} for user {record.user_id}")
    return record.memory_id


def get_memory(user_id: str, memory_id: str) -> Optional[EpisodicMemoryRecord]:
    """Retrieve a single memory record by its ID."""
    col = get_collection(user_id)
    try:
        result = col.get(ids=[memory_id], include=["documents", "metadatas"])
        if result["ids"]:
            return EpisodicMemoryRecord.from_metadata(
                fact_text=result["documents"][0],
                metadata=result["metadatas"][0],
            )
    except Exception as e:
        logger.error(f"[MemoryStore] get_memory error: {e}")
    return None


def update_metadata(user_id: str, memory_id: str, updates: dict) -> None:
    """Patch specific metadata fields on an existing record."""
    col = get_collection(user_id)
    try:
        col.update(ids=[memory_id], metadatas=[updates])
    except Exception as e:
        logger.error(f"[MemoryStore] update_metadata error: {e}")


def mark_superseded(user_id: str, old_memory_id: str, new_memory_id: str) -> None:
    """Mark an existing memory as superseded by a newer fact."""
    update_metadata(user_id, old_memory_id, {
        "validity_flag": 0,
        "superseded_by": new_memory_id,
    })
    logger.info(
        f"[MemoryStore] Memory {old_memory_id} superseded by {new_memory_id}"
    )


def record_retrieval(user_id: str, memory_id: str, current_count: int) -> None:
    """Update retrieval timestamp and increment retrieval count."""
    update_metadata(user_id, memory_id, {
        "last_retrieved_at": _now_iso(),
        "retrieval_count": current_count + 1,
    })


def update_decay_score(user_id: str, memory_id: str, new_score: float) -> None:
    """Persist a freshly calculated decay score."""
    update_metadata(user_id, memory_id, {"decay_score": new_score})


def archive_memory(user_id: str, memory_id: str) -> None:
    """Mark a memory as invalid (archived) but keep it for audit trail."""
    update_metadata(user_id, memory_id, {"validity_flag": 0})
    logger.info(f"[MemoryStore] Archived memory {memory_id}")


# ---------------------------------------------------------------------------
# Query / listing helpers
# ---------------------------------------------------------------------------

def query_similar(
    user_id: str,
    query_embedding: List[float],
    top_k: int = 10,
    active_only: bool = True,
    decay_threshold: float = 0.20,
) -> List[Tuple[EpisodicMemoryRecord, float]]:
    """
    Semantic similarity search.
    Returns list of (EpisodicMemoryRecord, distance) sorted by relevance.
    Only returns memories that pass validity and decay filters.
    """
    col = get_collection(user_id)
    try:
        # Fetch more candidates than needed so we can filter
        raw = col.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 3, 50),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        logger.error(f"[MemoryStore] query_similar error: {e}")
        return []

    results: List[Tuple[EpisodicMemoryRecord, float]] = []
    if not raw["ids"] or not raw["ids"][0]:
        return results

    for doc, meta, dist in zip(
        raw["documents"][0], raw["metadatas"][0], raw["distances"][0]
    ):
        record = EpisodicMemoryRecord.from_metadata(fact_text=doc, metadata=meta)
        if active_only and not record.validity_flag:
            continue
        if record.decay_score < decay_threshold:
            continue
        results.append((record, float(dist)))

    return results[:top_k]


def get_all_memories(
    user_id: str,
    active_only: bool = True,
) -> List[EpisodicMemoryRecord]:
    """Return all stored memories for a user (for decay engine and API)."""
    col = get_collection(user_id)
    try:
        raw = col.get(include=["documents", "metadatas"])
    except Exception as e:
        logger.error(f"[MemoryStore] get_all_memories error: {e}")
        return []

    records = []
    for doc, meta in zip(raw["documents"], raw["metadatas"]):
        record = EpisodicMemoryRecord.from_metadata(fact_text=doc, metadata=meta)
        if active_only and not record.validity_flag:
            continue
        records.append(record)
    return records


def get_archived_memories(user_id: str) -> List[EpisodicMemoryRecord]:
    """Return superseded/archived memories for audit trail display."""
    col = get_collection(user_id)
    try:
        raw = col.get(include=["documents", "metadatas"])
    except Exception as e:
        logger.error(f"[MemoryStore] get_archived_memories error: {e}")
        return []

    return [
        EpisodicMemoryRecord.from_metadata(fact_text=doc, metadata=meta)
        for doc, meta in zip(raw["documents"], raw["metadatas"])
        if not bool(int(meta.get("validity_flag", 1)))
    ]


def delete_memory(user_id: str, memory_id: str) -> bool:
    """Hard-delete a memory (user-controlled deletion)."""
    col = get_collection(user_id)
    try:
        col.delete(ids=[memory_id])
        logger.info(f"[MemoryStore] Deleted memory {memory_id}")
        return True
    except Exception as e:
        logger.error(f"[MemoryStore] delete_memory error: {e}")
        return False
