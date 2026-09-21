"""
memory_model.py
---------------
Defines the EpisodicMemoryRecord dataclass — the canonical unit of
storage in the IMDCRA system (corresponds to Table 3.1 in the project).

Fields
------
memory_id         : Unique UUID string identifier
user_id           : User namespace (maps to the authenticated user's id)
fact_text         : The stored user fact in plain text
created_at        : ISO-format timestamp of initial storage
last_retrieved_at : ISO-format timestamp of most recent retrieval
retrieval_count   : Total number of times this memory has been retrieved
importance_weight : Float 0.0–1.0 indicating memory importance category
decay_score       : Current composite retention score D(m) ∈ [0, 1]
validity_flag     : True = active/current; False = archived or superseded
superseded_by     : memory_id of the newer fact that replaced this one
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid


# Importance categories (maps to a numeric weight)
IMPORTANCE_HIGH = 1.0    # identity, profession, location, key relationships
IMPORTANCE_MEDIUM = 0.6  # stable preferences, goals, skills
IMPORTANCE_LOW = 0.3     # temporary observations, minor preferences


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class EpisodicMemoryRecord:
    """A single persisted user fact with full lifecycle metadata."""

    user_id: str
    fact_text: str
    importance_weight: float = IMPORTANCE_MEDIUM

    # Auto-generated fields
    memory_id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now_iso)
    last_retrieved_at: str = field(default_factory=_now_iso)
    retrieval_count: int = 0
    decay_score: float = 1.0          # starts at maximum retention
    validity_flag: bool = True        # True = active and retrievable
    superseded_by: Optional[str] = None  # memory_id of successor fact

    def to_metadata(self) -> dict:
        """Serialise lifecycle fields for ChromaDB metadata storage."""
        return {
            "memory_id": self.memory_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_retrieved_at": self.last_retrieved_at,
            "retrieval_count": self.retrieval_count,
            "importance_weight": self.importance_weight,
            "decay_score": self.decay_score,
            "validity_flag": int(self.validity_flag),  # ChromaDB stores int
            "superseded_by": self.superseded_by or "",
        }

    @classmethod
    def from_metadata(cls, fact_text: str, metadata: dict) -> "EpisodicMemoryRecord":
        """Reconstruct a record from ChromaDB metadata."""
        return cls(
            memory_id=metadata.get("memory_id", _new_id()),
            user_id=metadata.get("user_id", ""),
            fact_text=fact_text,
            created_at=metadata.get("created_at", _now_iso()),
            last_retrieved_at=metadata.get("last_retrieved_at", _now_iso()),
            retrieval_count=int(metadata.get("retrieval_count", 0)),
            importance_weight=float(metadata.get("importance_weight", IMPORTANCE_MEDIUM)),
            decay_score=float(metadata.get("decay_score", 1.0)),
            validity_flag=bool(int(metadata.get("validity_flag", 1))),
            superseded_by=metadata.get("superseded_by") or None,
        )

    def mark_superseded(self, new_memory_id: str) -> None:
        """Mark this memory as superseded by a newer fact."""
        self.validity_flag = False
        self.superseded_by = new_memory_id
