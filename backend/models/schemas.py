"""Request and response models for the API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AskRequest(BaseModel):
    question: str = Field(..., max_length=1000)
    conversation_id: uuid.UUID | None = Field(
        None,
        description="Store the question and answer in this conversation (see /conversations).",
    )


class Source(BaseModel):
    document: str
    page: int = Field(..., description="1-based page number in the PDF")
    section: str = Field("", description="Heading path of the passage, e.g. '7. Color Palette'")
    excerpt: str
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    found: bool
    sources: list[Source]
    conversation_id: uuid.UUID | None = None
    model: str | None = Field(
        None,
        description="Azure OpenAI deployment that wrote the answer; null when the answer is the top passage.",
    )


class DocumentInfo(BaseModel):
    name: str
    title: str
    page_count: int = 0
    chunk_count: int = 0
    indexed_at: datetime | None = None


class DocumentsResponse(BaseModel):
    documents: list[DocumentInfo]


class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["user", "assistant"]
    text: str
    found: bool | None = None
    sources: list[Source] | None = None
    created_at: datetime


class ConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageOut]
