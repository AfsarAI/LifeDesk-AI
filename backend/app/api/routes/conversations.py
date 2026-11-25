"""REST endpoints for listing conversations and their persisted messages."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.database.repositories import ConversationRepository
from app.schemas.chat import (
    ConversationListResponse,
    ConversationOut,
    MessageListResponse,
    MessageOut,
    ToolExecutionRecord,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=ConversationListResponse)
def list_conversations(db: Session = Depends(get_db)) -> ConversationListResponse:
    """Return all saved conversations ordered by most recently updated."""
    repo = ConversationRepository(db)
    conversations = repo.list_all()
    return ConversationListResponse(
        conversations=[ConversationOut.model_validate(c) for c in conversations],
        count=len(conversations),
    )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> MessageListResponse:
    """Return all persisted messages for a given conversation."""
    repo = ConversationRepository(db)
    conversation = repo.get_by_id(conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} was not found.",
        )

    raw_messages = repo.list_messages(conversation_id)
    serialized: list[MessageOut] = []
    for msg in raw_messages:
        tool_calls: list[ToolExecutionRecord] = []
        if msg.tool_metadata:
            try:
                parsed = json.loads(msg.tool_metadata)
                if isinstance(parsed, list):
                    tool_calls = [ToolExecutionRecord.model_validate(item) for item in parsed]
                elif isinstance(parsed, dict):
                    tool_calls = [ToolExecutionRecord.model_validate(parsed)]
            except Exception:
                tool_calls = []

        serialized.append(
            MessageOut(
                id=msg.id,
                conversation_id=msg.conversation_id,
                role=msg.role,
                content=msg.content,
                tool_calls=tool_calls,
                created_at=msg.created_at,
            )
        )

    return MessageListResponse(
        conversation=ConversationOut.model_validate(conversation),
        messages=serialized,
    )
