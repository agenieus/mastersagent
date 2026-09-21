"""
imdcra_orchestrator.py
----------------------
Coordinates the full IMDCRA post-turn memory pipeline:

  Step 1: Extract user facts from the conversation turn.
  Step 2: For each fact, embed it.
  Step 3: Run contradiction resolution (identify and supersede stale facts).
  Step 4: Write the new fact as an active memory record.
  Step 5: Update superseded-by references on older records.
  Step 6: Optionally run the decay engine (triggered after each session turn).

This module is called as a FastAPI BackgroundTask from chat.py so it does NOT
block the streaming response that has already been sent to the user.
"""

import logging
from typing import List, Dict

from memory_model import (
    EpisodicMemoryRecord,
    IMPORTANCE_MAP,
    IMPORTANCE_MEDIUM,
)
from memory_store import add_memory, update_metadata
from retrieval import embed_fact
from fact_extractor import extract_facts, IMPORTANCE_MAP as FACT_IMPORTANCE_MAP
from contradiction_resolver import resolve_contradiction
from decay_engine import run_decay_for_user

logger = logging.getLogger(__name__)


async def process_turn(
    user_id: str,
    user_message: str,
    recent_context: List[Dict[str, str]],
    run_decay: bool = True,
) -> Dict:
    """
    Full IMDCRA pipeline for one conversation turn.

    Parameters
    ----------
    user_id        : The authenticated user's ID (string)
    user_message   : The raw text of the user's latest message
    recent_context : Last N messages as list of {"role": str, "content": str}
    run_decay      : Whether to run the decay engine after writing memories

    Returns
    -------
    A summary dict describing what was extracted, resolved, and stored.
    """
    summary = {
        "user_id": user_id,
        "extracted_facts": [],
        "stored_memories": [],
        "superseded_memories": [],
        "decay_report": None,
    }

    # ------------------------------------------------------------------
    # Step 1: Extract user facts
    # ------------------------------------------------------------------
    try:
        facts: List[Dict] = await extract_facts(user_message, recent_context)
    except Exception as e:
        logger.error(f"[Orchestrator] Fact extraction failed: {e}")
        facts = []

    if not facts:
        logger.info("[Orchestrator] No extractable facts in this turn.")
        if run_decay:
            _run_decay_safe(user_id, summary)
        return summary

    summary["extracted_facts"] = [f["fact"] for f in facts]

    # ------------------------------------------------------------------
    # Steps 2–5: Per-fact embedding, contradiction check, and storage
    # ------------------------------------------------------------------
    for fact_item in facts:
        fact_text: str = fact_item["fact"]
        importance_label: str = fact_item.get("importance", "medium")
        importance_weight: float = FACT_IMPORTANCE_MAP.get(
            importance_label, IMPORTANCE_MEDIUM
        )

        # Embed the new fact
        embedding = embed_fact(fact_text)
        if not embedding:
            logger.warning(f"[Orchestrator] Could not embed fact: {fact_text[:50]}")
            continue

        # Run contradiction resolution
        resolution = resolve_contradiction(
            user_id=user_id,
            new_fact_text=fact_text,
            new_fact_embedding=embedding,
        )

        for sup in resolution.get("superseded", []):
            summary["superseded_memories"].append(sup)

        # Create the new memory record
        record = EpisodicMemoryRecord(
            user_id=user_id,
            fact_text=fact_text,
            importance_weight=importance_weight,
        )

        # Write to ChromaDB
        try:
            add_memory(record, embedding)
            summary["stored_memories"].append(record.memory_id)

            # Update superseded_by on older records now that we have the new ID
            for sup in resolution.get("superseded", []):
                update_metadata(user_id, sup["memory_id"], {
                    "superseded_by": record.memory_id
                })

            logger.info(
                f"[Orchestrator] Stored memory {record.memory_id}: '{fact_text[:60]}'"
            )
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to store memory: {e}")

    # ------------------------------------------------------------------
    # Step 6: Run decay engine
    # ------------------------------------------------------------------
    if run_decay:
        _run_decay_safe(user_id, summary)

    return summary


def _run_decay_safe(user_id: str, summary: dict) -> None:
    """Run decay engine and attach report to summary (swallows exceptions)."""
    try:
        decay_report = run_decay_for_user(user_id)
        summary["decay_report"] = decay_report
    except Exception as e:
        logger.error(f"[Orchestrator] Decay engine failed: {e}")
