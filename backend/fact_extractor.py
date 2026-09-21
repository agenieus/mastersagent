"""
fact_extractor.py
-----------------
Extracts explicit, storable user facts from a conversation turn using the
local Ollama LLM. Falls back to a regex-based heuristic extractor if Ollama
is not available or returns malformed output.

The extraction is deliberately CONSERVATIVE:
- Only facts explicitly stated by the user are extracted.
- Inferences, opinions about the world, and assistant statements are ignored.
- Each extracted fact is tagged with an importance category.

Output format (list of dicts):
    [{"fact": "User is a software developer.", "importance": "high"}, ...]
"""

import json
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Importance mapping
# ---------------------------------------------------------------------------

IMPORTANCE_MAP = {
    "high":   1.0,   # identity, profession, location, key relationships
    "medium": 0.6,   # preferences, goals, skills, health
    "low":    0.3,   # temporary observations, minor details
}

HIGH_KEYWORDS = [
    "name", "live", "lives", "living", "located", "work", "works", "job",
    "profession", "career", "married", "born", "nationality", "age", "years old",
    "family", "children", "moved", "relocated", "husband", "wife", "partner",
]
MEDIUM_KEYWORDS = [
    "prefer", "like", "enjoy", "hobby", "interested", "goal", "studying",
    "learning", "language", "diet", "health", "skill", "experience",
]


def _infer_importance(fact: str) -> str:
    lower = fact.lower()
    for kw in HIGH_KEYWORDS:
        if kw in lower:
            return "high"
    for kw in MEDIUM_KEYWORDS:
        if kw in lower:
            return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Regex fallback extractor
# ---------------------------------------------------------------------------

USER_FACT_PATTERNS = [
    r"(?:my name is|i(?:'m| am) called)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
    r"i(?:'m| am) (?:a |an )?([a-z][\w\s]{2,30}(?:developer|engineer|doctor|teacher|student|designer|manager|analyst|nurse|lawyer|writer|scientist))",
    r"i(?:'m| am) ([0-9]{1,2}) years old",
    r"i live(?:d)? (?:in|at) ([\w\s,]+)",
    r"i(?:'ve)? moved? (?:to|from) ([\w\s,]+)",
    r"i work(?:ed)? (?:at|for|as) ([\w\s,]+)",
    r"i(?:'m| am) from ([\w\s,]+)",
    r"my (?:email|phone|number) is ([\w@.\-\+]+)",
    r"i(?:'m| am) (?:currently )?(?:studying|learning) ([\w\s]+)",
]


def _regex_extract(user_message: str) -> List[Dict[str, str]]:
    """Simple pattern-based fact extraction as a fallback."""
    facts = []
    for pattern in USER_FACT_PATTERNS:
        match = re.search(pattern, user_message, re.IGNORECASE)
        if match:
            # Reconstruct a clean fact string
            raw = match.group(0)
            # Capitalise and trim
            fact = raw.strip().capitalize()
            if not fact.endswith("."):
                fact += "."
            importance = _infer_importance(fact)
            facts.append({"fact": fact, "importance": importance})
    return facts


# ---------------------------------------------------------------------------
# LLM-based extractor (primary)
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """\
You are an information-extraction assistant. Your task is to identify explicit personal facts that the USER has stated about themselves in the conversation below.

Rules:
1. Only extract facts EXPLICITLY stated by the user (not inferred).
2. Do NOT extract opinions about the world, questions, or what the assistant said.
3. Rephrase each fact as a third-person statement beginning with "User".
4. Classify each fact as "high", "medium", or "low" importance:
   - high: identity, name, location, profession, key relationships, age
   - medium: preferences, hobbies, goals, skills, current activities
   - low: temporary or minor observations

Return a JSON array only, no other text. Example:
[
  {{"fact": "User lives in Abuja, Nigeria.", "importance": "high"}},
  {{"fact": "User prefers Python for development.", "importance": "medium"}}
]

If there are no extractable personal facts, return an empty array: []

Conversation:
{conversation}

User's latest message: {user_message}

JSON:"""


async def extract_facts_llm(
    user_message: str,
    recent_context: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """Use Ollama to extract facts from the user's message."""
    try:
        from config import settings
        import ollama

        # Build a compact conversation string
        context_str = ""
        for msg in recent_context[-6:]:  # last 3 turns
            role = msg["role"].capitalize()
            context_str += f"{role}: {msg['content']}\n"

        prompt = EXTRACTION_PROMPT.format(
            conversation=context_str.strip(),
            user_message=user_message,
        )

        client = ollama.AsyncClient(host=settings.ollama_host)
        response = await client.generate(
            model=settings.ollama_model,
            prompt=prompt,
            stream=False,
        )
        raw_text = response.response.strip()

        # Extract JSON array from response (model sometimes adds extra text)
        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if json_match:
            facts = json.loads(json_match.group(0))
            # Validate structure
            validated = []
            for item in facts:
                if isinstance(item, dict) and "fact" in item:
                    importance = item.get("importance", "low")
                    if importance not in IMPORTANCE_MAP:
                        importance = _infer_importance(item["fact"])
                    validated.append({
                        "fact": str(item["fact"]).strip(),
                        "importance": importance,
                    })
            return validated

    except Exception as e:
        logger.warning(f"[FactExtractor] LLM extraction failed: {e}. Using regex fallback.")

    # Fallback to regex
    return _regex_extract(user_message)


async def extract_facts(
    user_message: str,
    recent_context: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Public interface: extract storable user facts from a conversation turn.
    Returns list of {"fact": str, "importance": str ("high"/"medium"/"low")}
    """
    facts = await extract_facts_llm(user_message, recent_context)
    logger.info(
        f"[FactExtractor] Extracted {len(facts)} fact(s): "
        + ", ".join(f['fact'][:40] for f in facts)
    )
    return facts
