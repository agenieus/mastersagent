"""
retrieval.py
------------
Semantic retrieval module for IMDCRA.

Uses sentence-transformers (all-MiniLM-L6-v2) to encode queries and
facts into dense vectors, then calls the ChromaDB store to retrieve the
top-k most relevant active memories for a given user.

After retrieval, updates the retrieval_count and last_retrieved_at
metadata on every returned record (tracking usage for the decay engine).
"""

import logging
from typing import List, Tuple

from memory_model import EpisodicMemoryRecord
from memory_store import query_similar, record_retrieval, get_all_memories
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-load the embedding model (downloads ~80 MB on first use)
# ---------------------------------------------------------------------------

_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            model_name = getattr(settings, "embedding_model", "all-MiniLM-L6-v2")
            logger.info(f"[Retrieval] Loading embedding model: {model_name}")
            _embedder = SentenceTransformer(model_name)
            logger.info("[Retrieval] Embedding model loaded.")
        except Exception as e:
            logger.error(f"[Retrieval] Could not load embedding model: {e}")
            _embedder = None
    return _embedder


def embed_text(text: str) -> List[float]:
    """Encode a string into a dense embedding vector."""
    embedder = get_embedder()
    if embedder is None:
        # Fallback: return empty list — store will skip retrieval gracefully
        return []
    return embedder.encode(text, normalize_embeddings=True).tolist()


# ---------------------------------------------------------------------------
# Public retrieval API
# ---------------------------------------------------------------------------

def retrieve_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
    decay_threshold: float = 0.20,
) -> List[EpisodicMemoryRecord]:
    """
    Retrieve the most semantically relevant active memories for a query.

    1. Encode the query.
    2. Run cosine-similarity search in ChromaDB (filtered by validity + decay).
    3. Update retrieval metadata on each returned record.
    4. Return ordered list of EpisodicMemoryRecord objects.
    """
    if not query.strip():
        return []

    query_embedding = embed_text(query)
    if not query_embedding:
        logger.warning("[Retrieval] No embedding available — skipping retrieval.")
        return []

    raw_results: List[Tuple[EpisodicMemoryRecord, float]] = query_similar(
        user_id=user_id,
        query_embedding=query_embedding,
        top_k=top_k,
        active_only=True,
        decay_threshold=decay_threshold,
    )

    memories: List[EpisodicMemoryRecord] = []
    for record, _distance in raw_results:
        # Bump retrieval stats so decay engine tracks usage
        record_retrieval(user_id, record.memory_id, record.retrieval_count)
        memories.append(record)

    logger.info(
        f"[Retrieval] Retrieved {len(memories)} memories for user {user_id}"
    )
    return memories


def format_memory_context(memories: List[EpisodicMemoryRecord]) -> str:
    """
    Format retrieved memories into a concise block for injection into the
    LLM system prompt.
    """
    if not memories:
        return ""
    lines = ["[Remembered facts about this user]"]
    for m in memories:
        lines.append(f"• {m.fact_text}")
    return "\n".join(lines)


def embed_fact(fact_text: str) -> List[float]:
    """Public wrapper used by the memory store and contradiction resolver."""
    return embed_text(fact_text)
