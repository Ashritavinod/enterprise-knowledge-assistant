"""Question-answering endpoints used by the chat frontend."""

import logging
import re
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.database import get_db, session_scope
from backend.db.models import Conversation, Document, Message, QueryLog
from backend.models.schemas import (
    AskRequest,
    AskResponse,
    DocumentInfo,
    DocumentsResponse,
    Source,
)
from backend.services.azure_openai import chat_deployment, generate_answer, rewrite_question
from backend.services.rag_service import retrieve_documents
from backend.services.vector_store import get_embedding_model_id

logger = logging.getLogger(__name__)
HISTORY_MESSAGES = 6

router = APIRouter(prefix="/qa", tags=["question answering"])

NO_ANSWER = (
    "I couldn't find that in Honeycrumb's marketing documents. Try rephrasing, "
    "or ask about the brand, campaigns, the 2026 strategy, menu and cakes, "
    "social media, email or the Crumb Club."
)


def clean_excerpt(text: str, section: str = "") -> str:
    """Return a chunk's body: one paragraph, bullet or table row per line.

    Chunks start with their section path; drop it because the API returns
    the section separately.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if section and lines and lines[0] == section:
        lines = lines[1:]
    return _drop_leading_fragment("\n".join(lines))


def _drop_leading_fragment(text: str) -> str:
    """Chunks can start mid-sentence; drop a short lowercase lead-in fragment."""
    if not text or not text[0].islower():
        return text
    match = re.search(r"[.!?:]\s+(?=[A-Z0-9•\"“])", text[:160])
    return text[match.end():] if match else text


def _history(conversation_id: uuid.UUID | None) -> list[tuple[str, str]]:
    """The conversation's last few (role, text) turns, oldest first.

    Raises 404 for an unknown conversation, before any Azure OpenAI call is made.
    """
    if conversation_id is None:
        return []
    with session_scope() as db:
        if db.get(Conversation, conversation_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
        rows = db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(HISTORY_MESSAGES)
        ).all()
        return [(row.role, row.text) for row in reversed(rows)]


def _search_query(question: str, history: list[tuple[str, str]]) -> str:
    """The question to retrieve with: follow-ups are rewritten to stand alone."""
    if not history or chat_deployment() is None:
        return question
    try:
        return rewrite_question(question, history)
    except Exception:
        logger.exception("Azure OpenAI question rewrite failed; searching the original")
        return question


def _generate(
    question: str,
    sources: list[Source],
    history: list[tuple[str, str]],
) -> tuple[str, str | None]:
    """Return (answer, model): an Azure OpenAI answer, or the top passage as fallback."""
    fallback = sources[0].excerpt if sources else NO_ANSWER
    if not sources or chat_deployment() is None:
        return fallback, None
    try:
        answer = generate_answer(question, sources, history)
    except Exception:
        logger.exception("Azure OpenAI generation failed; returning the top passage")
        return fallback, None
    return (answer, chat_deployment()) if answer else (fallback, None)


def _record(
    request: AskRequest,
    response: AskResponse,
    latency_ms: float,
) -> None:
    """Log the query and, if a conversation was given, store both messages."""
    with session_scope() as db:
        conversation = None
        if request.conversation_id is not None:
            conversation = db.get(Conversation, request.conversation_id)
            if conversation is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
            db.add_all(
                [
                    Message(conversation_id=conversation.id, role="user", text=response.question),
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        text=response.answer,
                        found=response.found,
                        sources=[s.model_dump() for s in response.sources],
                    ),
                ]
            )
            conversation.updated_at = func.now()

        top = response.sources[0] if response.sources else None
        db.add(
            QueryLog(
                question=response.question,
                found=response.found,
                result_count=len(response.sources),
                top_score=top.score if top else None,
                top_document=top.document if top else None,
                latency_ms=round(latency_ms, 2),
                embedding_model=get_embedding_model_id(),
                conversation_id=conversation.id if conversation else None,
            )
        )


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    started = time.perf_counter()
    question = request.question.strip()
    history: list[tuple[str, str]] = []
    results: list[dict[str, str | int | float]] = []
    if question:
        history = await run_in_threadpool(_history, request.conversation_id)
        search_query = await run_in_threadpool(_search_query, question, history)
        results = await run_in_threadpool(retrieve_documents, search_query)
    sources = [
        Source(
            document=str(result["source"]),
            page=int(result["page"]) + 1,
            section=str(result.get("section", "")),
            excerpt=clean_excerpt(str(result["content"]), str(result.get("section", ""))),
            score=round(float(result["score"]), 4),
        )
        for result in results
    ]
    answer, model = await run_in_threadpool(_generate, question, sources, history)
    response = AskResponse(
        question=question,
        answer=answer,
        found=bool(sources),
        sources=sources,
        conversation_id=request.conversation_id,
        model=model,
    )
    if question:
        latency_ms = (time.perf_counter() - started) * 1000
        await run_in_threadpool(_record, request, response, latency_ms)
    return response


@router.get("/documents", response_model=DocumentsResponse)
def documents(db: Session = Depends(get_db)) -> DocumentsResponse:
    rows = db.scalars(select(Document).order_by(Document.name))
    return DocumentsResponse(
        documents=[
            DocumentInfo(
                name=row.name,
                title=row.title,
                page_count=row.page_count,
                chunk_count=row.chunk_count,
                indexed_at=row.indexed_at,
            )
            for row in rows
        ]
    )
