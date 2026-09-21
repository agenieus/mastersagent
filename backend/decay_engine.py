"""
decay_engine.py
---------------
Implements the IMDCRA memory decay function:

    D(m) = wr·R(m) + wf·F(m) + wi·I(m)

Where:
    R(m) = e^(-λ·Δt)              recency score     (exponential decay)
    F(m) = log(1+n)/log(1+nmax)   frequency score   (logarithmic normalisation)
    I(m) = importance_weight       importance score  (fixed category weight)

Memories with D(m) < θ (default 0.20) are moved to archived status.

The engine can be triggered:
  - After each conversation session (via orchestrator)
  - Manually via the /memory/run-decay endpoint
  - Periodically (cron-style in a production deployment)
"""

import math
import logging
from datetime import datetime, timezone
from typing import List, Dict, Tuple

from memory_model import EpisodicMemoryRecord
from memory_store import get_all_memories, update_decay_score, archive_memory
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default configurable parameters (can be overridden in config.py / .env)
# ---------------------------------------------------------------------------

def _get(attr: str, default):
    return getattr(settings, attr, default)


# ---------------------------------------------------------------------------
# Component scoring functions
# ---------------------------------------------------------------------------

def recency_score(last_retrieved_at: str, decay_lambda: float = None) -> float:
    """
    R(m) = e^(-λ·Δt)
    Δt is measured in days since last retrieval.
    λ controls the rate of decay (default 0.02 → half-life ≈ 35 days).
    """
    lam = decay_lambda or _get("decay_lambda", 0.02)
    try:
        last = datetime.fromisoformat(last_retrieved_at)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        delta_days = (datetime.now(timezone.utc) - last).total_seconds() / 86_400.0
    except Exception:
        delta_days = 0.0
    return math.exp(-lam * delta_days)


def frequency_score(retrieval_count: int, max_count: int) -> float:
    """
    F(m) = log(1+n) / log(1+nmax)
    Normalised logarithmic retrieval frequency.
    Returns 0 if nmax is 0 (no retrievals yet in the user's memory set).
    """
    if max_count <= 0:
        return 0.0
    return math.log(1 + retrieval_count) / math.log(1 + max_count)


def composite_score(
    record: EpisodicMemoryRecord,
    max_retrieval_count: int,
    wr: float = None,
    wf: float = None,
    wi: float = None,
) -> float:
    """
    D(m) = wr·R(m) + wf·F(m) + wi·I(m)
    Default weights: wr=0.4, wf=0.3, wi=0.3
    """
    wr = wr or _get("decay_weight_recency",   0.4)
    wf = wf or _get("decay_weight_frequency", 0.3)
    wi = wi or _get("decay_weight_importance", 0.3)

    r = recency_score(record.last_retrieved_at)
    f = frequency_score(record.retrieval_count, max_retrieval_count)
    i = record.importance_weight  # already 0.0–1.0

    score = wr * r + wf * f + wi * i
    return round(min(max(score, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# Main decay engine
# ---------------------------------------------------------------------------

def run_decay_for_user(user_id: str) -> Dict:
    """
    Run one full decay cycle for a user.

    1. Load all active memories.
    2. Find the maximum retrieval count (for frequency normalisation).
    3. Recalculate D(m) for every active memory.
    4. Archive memories where D(m) < threshold.
    5. Return a summary report.
    """
    threshold = _get("decay_threshold", 0.20)
    memories: List[EpisodicMemoryRecord] = get_all_memories(user_id, active_only=True)

    if not memories:
        return {"user_id": user_id, "processed": 0, "archived": 0, "active": 0}

    max_count = max(m.retrieval_count for m in memories) if memories else 0

    archived_ids: List[str] = []
    updated: List[Tuple[str, float]] = []

    for mem in memories:
        score = composite_score(mem, max_count)
        updated.append((mem.memory_id, score))

        if score < threshold:
            archive_memory(user_id, mem.memory_id)
            archived_ids.append(mem.memory_id)
            logger.info(
                f"[DecayEngine] Archived {mem.memory_id} "
                f"(score={score:.4f} < threshold={threshold})"
            )
        else:
            update_decay_score(user_id, mem.memory_id, score)

    active_count = len(memories) - len(archived_ids)
    report = {
        "user_id": user_id,
        "processed": len(memories),
        "archived": len(archived_ids),
        "active": active_count,
        "threshold": threshold,
        "scores": {mid: sc for mid, sc in updated},
    }
    logger.info(
        f"[DecayEngine] Cycle complete for user {user_id}: "
        f"{active_count} active, {len(archived_ids)} archived."
    )
    return report


def get_memory_stats(user_id: str) -> Dict:
    """
    Return summary statistics for the memory panel API endpoint.
    Includes active count, archived count, average decay score.
    """
    from memory_store import get_archived_memories

    active = get_all_memories(user_id, active_only=True)
    archived = get_archived_memories(user_id)

    avg_score = (
        sum(m.decay_score for m in active) / len(active) if active else 0.0
    )
    avg_importance = (
        sum(m.importance_weight for m in active) / len(active) if active else 0.0
    )

    return {
        "active_count": len(active),
        "archived_count": len(archived),
        "average_decay_score": round(avg_score, 4),
        "average_importance": round(avg_importance, 4),
        "threshold": _get("decay_threshold", 0.20),
    }
