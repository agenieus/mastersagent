import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database import get_db, AsyncSessionLocal
from models import Conversation, Message, User
from schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    ChatRequest,
)
from auth import get_current_user
from memory import get_conversation_context
from ollama_client import stream_response

router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(user_id=current_user.id, title=data.title or "New Chat")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(conv)
    await db.commit()
    return {"message": "Deleted"}


@router.patch("/conversations/{conv_id}/title", response_model=ConversationResponse)
async def rename_conversation(
    conv_id: int,
    data: ConversationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv.title = data.title or conv.title
    await db.commit()
    await db.refresh(conv)
    return conv


@router.post("/conversations/{conv_id}/messages")
async def send_message(
    conv_id: int,
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify conversation ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conv_id, Conversation.user_id == current_user.id
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_msg = Message(conversation_id=conv_id, role="user", content=data.content)
    db.add(user_msg)
    await db.commit()

    # Load full context (including the user message we just saved)
    context = await get_conversation_context(conv_id, db)

    # Auto-title the conversation from the first user message
    if len(context) == 1:
        title = data.content[:60] + ("..." if len(data.content) > 60 else "")
        await db.execute(
            update(Conversation).where(Conversation.id == conv_id).values(title=title)
        )
        await db.commit()

    async def generate():
        full_response = ""
        try:
            async for token in stream_response(context):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # Persist the assistant message and update conversation timestamp
        async with AsyncSessionLocal() as new_db:
            async with new_db.begin():
                assistant_msg = Message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=full_response,
                )
                new_db.add(assistant_msg)
                await new_db.execute(
                    update(Conversation)
                    .where(Conversation.id == conv_id)
                    .values(updated_at=datetime.now(timezone.utc))
                )

        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
