"""
memory_router.py
----------------
FastAPI router exposing the IMDCRA memory management API.

Endpoints
---------
GET  /memory/              List active memories for current user
GET  /memory/archived      List superseded/archived memories
GET  /memory/stats         Memory store statistics (counts, avg decay)
POST /memory/run-decay     Manually trigger the decay engine
DELETE /memory/{memory_id} Hard-delete a specific memory
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from auth import get_current_user
from models import User
from memory_store import get_all_memories, get_archived_memories, delete_memory
from decay_engine import run_decay_for_user, get_memory_stats

router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class MemoryResponse(BaseModel):
    memory_id: str
    fact_text: str
    importance_weight: float
    decay_score: float
    retrieval_count: int
    created_at: str
    last_retrieved_at: str
    validity_flag: bool
    superseded_by: Optional[str] = None

    class Config:
        from_attributes = True


class MemoryStatsResponse(BaseModel):
    active_count: int
    archived_count: int
    average_decay_score: float
    average_importance: float
    threshold: float


class DecayReportResponse(BaseModel):
    user_id: str
    processed: int
    archived: int
    active: int
    threshold: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[MemoryResponse], summary="List active memories")
async def list_active_memories(
    current_user: User = Depends(get_current_user),
):
    """Return all currently active (non-superseded, non-archived) memories."""
    memories = get_all_memories(str(current_user.id), active_only=True)
    return [
        MemoryResponse(
            memory_id=m.memory_id,
            fact_text=m.fact_text,
            importance_weight=m.importance_weight,
            decay_score=m.decay_score,
            retrieval_count=m.retrieval_count,
            created_at=m.created_at,
            last_retrieved_at=m.last_retrieved_at,
            validity_flag=m.validity_flag,
            superseded_by=m.superseded_by,
        )
        for m in memories
    ]


@router.get(
    "/archived", response_model=List[MemoryResponse], summary="List archived memories"
)
async def list_archived_memories(
    current_user: User = Depends(get_current_user),
):
    """Return superseded and decay-archived memories (historical audit trail)."""
    memories = get_archived_memories(str(current_user.id))
    return [
        MemoryResponse(
            memory_id=m.memory_id,
            fact_text=m.fact_text,
            importance_weight=m.importance_weight,
            decay_score=m.decay_score,
            retrieval_count=m.retrieval_count,
            created_at=m.created_at,
            last_retrieved_at=m.last_retrieved_at,
            validity_flag=m.validity_flag,
            superseded_by=m.superseded_by,
        )
        for m in memories
    ]


@router.get("/stats", response_model=MemoryStatsResponse, summary="Memory statistics")
async def memory_statistics(
    current_user: User = Depends(get_current_user),
):
    """Return aggregate statistics about the user's memory store."""
    stats = get_memory_stats(str(current_user.id))
    return MemoryStatsResponse(**stats)


@router.post(
    "/run-decay", response_model=DecayReportResponse, summary="Run decay engine"
)
async def trigger_decay(
    current_user: User = Depends(get_current_user),
):
    """Manually trigger one decay cycle for the current user."""
    report = run_decay_for_user(str(current_user.id))
    return DecayReportResponse(
        user_id=report["user_id"],
        processed=report["processed"],
        archived=report["archived"],
        active=report["active"],
        threshold=report["threshold"],
    )


@router.delete("/{memory_id}", summary="Delete a specific memory")
async def delete_user_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
):
    """Hard-delete a specific memory record (user-controlled deletion)."""
    success = delete_memory(str(current_user.id), memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or could not be deleted")
    return {"message": "Memory deleted", "memory_id": memory_id}
