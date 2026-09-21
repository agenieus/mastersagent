"""
contradiction_resolver.py
--------------------------
NLI-based contradiction detection for the IMDCRA system.

Algorithm (Section 3.5.5 of the project):
  1. Receive a new candidate fact.
  2. Retrieve semantically related active memories (top-k).
  3. For each candidate, run NLI: new_fact (hypothesis) vs. existing (premise).
  4. If contradiction probability >= threshold → mark old memory superseded.
  5. Return a resolution report listing all supersession decisions.

NLI model: cross-encoder/nli-MiniLM-L2-v2 (~90 MB download on first use).
Labels order from this model: ['contradiction', 'entailment', 'neutral']
"""

import logging
from typing import List, Dict, Optional

from memory_model import EpisodicMemoryRecord, IMPORTANCE_MAP
from memory_store import query_similar, mark_superseded, add_memory
from retrieval import embed_fact
from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-load NLI cross-encoder model
# ---------------------------------------------------------------------------

_nli_pipe = None


def get_nli_pipeline():
    global _nli_pipe
    if _nli_pipe is None:
        try:
            from transformers import pipeline
            model_name = getattr(
                settings, "nli_model", "cross-encoder/nli-MiniLM-L2-v2"
            )
            logger.info(f"[ContradictionResolver] Loading NLI model: {model_name}")
            _nli_pipe = pipeline(
                "text-classification",
                model=model_name,
                top_k=None,   # return all labels
                device=-1,    # CPU
            )
            logger.info("[ContradictionResolver] NLI model loaded.")
        except Exception as e:
            logger.error(f"[ContradictionResolver] NLI model load failed: {e}")
            _nli_pipe = None
    return _nli_pipe


# ---------------------------------------------------------------------------
# NLI scoring
# ---------------------------------------------------------------------------

def _score_pair(premise: str, hypothesis: str) -> Dict[str, float]:
    """
    Score a (premise, hypothesis) pair with the NLI model.
    Returns {"contradiction": float, "entailment": float, "neutral": float}
    """
    pipe = get_nli_pipeline()
    if pipe is None:
        return {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0}

    try:
        # cross-encoder models expect "premise [SEP] hypothesis"
        results = pipe(f"{premise} [SEP] {hypothesis}")
        scores = {}
        if isinstance(results[0], list):
            results = results[0]
        for item in results:
            label = item["label"].lower()
            scores[label] = round(item["score"], 4)
        return scores
    except Exception as e:
        logger.error(f"[ContradictionResolver] NLI scoring error: {e}")
        return {"contradiction": 0.0, "entailment": 0.0, "neutral": 1.0}


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------

def resolve_contradiction(
    user_id: str,
    new_fact_text: str,
    new_fact_embedding: List[float],
    top_k: int = None,
    contradiction_threshold: float = None,
) -> Dict:
    """
    Run the full contradiction-resolution pipeline for a new fact.

    Returns a report dict:
    {
        "new_fact": str,
        "candidates_checked": int,
        "superseded": [{"memory_id": str, "old_fact": str, "score": float}],
        "no_conflict": [str],   # fact texts that passed NLI as neutral/entailment
    }
    """
    top_k = top_k or int(getattr(settings, "nli_top_k", 10))
    threshold = contradiction_threshold or float(
        getattr(settings, "nli_contradiction_threshold", 0.75)
    )

    report = {
        "new_fact": new_fact_text,
        "candidates_checked": 0,
        "superseded": [],
        "no_conflict": [],
    }

    if not new_fact_embedding:
        return report

    # Step 1: retrieve semantically related memories
    candidates = query_similar(
        user_id=user_id,
        query_embedding=new_fact_embedding,
        top_k=top_k,
        active_only=True,
        decay_threshold=0.0,  # check all active regardless of score
    )
    report["candidates_checked"] = len(candidates)

    # Step 2: NLI comparison
    for record, _dist in candidates:
        if record.fact_text.strip() == new_fact_text.strip():
            # Same fact — skip (no contradiction)
            report["no_conflict"].append(record.fact_text)
            continue

        scores = _score_pair(
            premise=record.fact_text,
            hypothesis=new_fact_text,
        )
        contradiction_prob = scores.get("contradiction", 0.0)

        logger.info(
            f"[ContradictionResolver] '{record.fact_text[:50]}' vs "
            f"'{new_fact_text[:50]}' → contradiction={contradiction_prob:.3f}"
        )

        if contradiction_prob >= threshold:
            # Supersede the older memory
            mark_superseded(user_id, record.memory_id, new_memory_id="pending")
            report["superseded"].append({
                "memory_id": record.memory_id,
                "old_fact": record.fact_text,
                "contradiction_score": contradiction_prob,
            })
        else:
            report["no_conflict"].append(record.fact_text)

    return report
