"""Chat history stored in PostgreSQL."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db.database import get_db
from backend.db.models import Conversation
from backend.models.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationSummary,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_or_404(db: Session, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation


@router.get("", response_model=list[ConversationSummary])
def list_conversations(limit: int = 30, db: Session = Depends(get_db)) -> list[Conversation]:
    limit = max(1, min(limit, 100))
    return list(
        db.scalars(
            select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)
        )
    )


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)) -> Conversation:
    conversation = Conversation(title=body.title.strip())
    db.add(conversation)
    db.flush()
    db.refresh(conversation)
    conversation.messages = []
    # Commit before responding: get_db's own commit runs after the response is
    # sent, so a client asking right away could otherwise get a 404.
    db.commit()
    return conversation


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> Conversation:
    return _get_or_404(db, conversation_id)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get_or_404(db, conversation_id))
    db.commit()  # before responding, as in create_conversation
    return Response(status_code=status.HTTP_204_NO_CONTENT)
