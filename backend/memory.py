from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Message
from config import settings
from typing import List, Dict


async def get_conversation_context(
    conversation_id: int, db: AsyncSession
) -> List[Dict[str, str]]:
    """Load the last N messages from a conversation to use as LLM context."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(settings.memory_window)
    )
    messages = result.scalars().all()
    # Reverse so oldest messages come first (chronological order for the LLM)
    messages = list(reversed(messages))

    return [{"role": msg.role, "content": msg.content} for msg in messages]
