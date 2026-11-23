"""Question-answering endpoints used by the chat frontend."""

import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
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
from backend.services.azure_openai import (
    chat_deployment,
    generate_answer,
    rewrite_question,
    stream_answer,
)
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


def _fallback(sources: list[Source]) -> str:
    """Answer used without Azure OpenAI: the top passage, or the not-found message."""
    return sources[0].excerpt if sources else NO_ANSWER


def _generate(
    question: str,
    sources: list[Source],
    history: list[tuple[str, str]],
) -> tuple[str, str | None]:
    """Return (answer, model): an Azure OpenAI chat reply, or the fallback answer.

    The model is asked even when no passages matched, so greetings, thanks,
    off-topic questions and requests about earlier answers get a real reply.
    """
    if chat_deployment() is None:
        return _fallback(sources), None
    try:
        answer = generate_answer(question, sources, history)
    except Exception:
        logger.exception("Azure OpenAI generation failed; returning the fallback answer")
        return _fallback(sources), None
    return (answer, chat_deployment()) if answer else (_fallback(sources), None)


def _to_sources(results: list[dict[str, str | int | float]]) -> list[Source]:
    return [
        Source(
            document=str(result["source"]),
            page=int(result["page"]) + 1,
            section=str(result.get("section", "")),
            excerpt=clean_excerpt(str(result["content"]), str(result.get("section", ""))),
            score=round(float(result["score"]), 4),
        )
        for result in results
    ]


async def _prepare(question: str, conversation_id: uuid.UUID | None) -> tuple[
    list[tuple[str, str]], list[Source]
]:
    """Load history (404 for an unknown conversation), rewrite follow-ups, retrieve."""
    if not question:
        return [], []
    history = await run_in_threadpool(_history, conversation_id)
    search_query = await run_in_threadpool(_search_query, question, history)
    results = await run_in_threadpool(retrieve_documents, search_query)
    return history, _to_sources(results)


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
                # Whether retrieval matched; `response.found` is also true for
                # model replies to greetings and other messages without passages.
                found=bool(response.sources),
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
    history, sources = await _prepare(question, request.conversation_id)
    if question:
        answer, model = await run_in_threadpool(_generate, question, sources, history)
    else:
        answer, model = NO_ANSWER, None
    response = AskResponse(
        question=question,
        answer=answer,
        found=bool(sources) or model is not None,
        sources=sources,
        conversation_id=request.conversation_id,
        model=model,
    )
    if question:
        latency_ms = (time.perf_counter() - started) * 1000
        await run_in_threadpool(_record, request, response, latency_ms)
    return response


def _event(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, default=str) + "\n").encode("utf-8")


@router.post("/ask/stream")
async def ask_stream(request: AskRequest) -> StreamingResponse:
    """Like /qa/ask, but streams the reply as newline-delimited JSON events.

    Events, in order:
      {"type": "sources", "sources": [...]}
      {"type": "delta", "text": "..."}  (zero or more; concatenate them)
      {"type": "done", "answer": "...", "found": bool, "model": str | null,
       "conversation_id": str | null}
    Errors before streaming starts (e.g. unknown conversation: 404) are normal
    HTTP errors. If Azure OpenAI fails before writing anything, the fallback
    answer is sent as a single delta.
    """
    started = time.perf_counter()
    question = request.question.strip()
    history, sources = await _prepare(question, request.conversation_id)

    def events() -> Iterator[bytes]:
        yield _event({"type": "sources", "sources": [s.model_dump() for s in sources]})
        parts: list[str] = []
        model = chat_deployment() if question else None
        if model is not None:
            try:
                for piece in stream_answer(question, sources, history):
                    parts.append(piece)
                    yield _event({"type": "delta", "text": piece})
            except Exception:
                logger.exception("Azure OpenAI streaming failed")
                if parts:
                    note = "\n\n(The answer was cut off. Please retry.)"
                    parts.append(note)
                    yield _event({"type": "delta", "text": note})
        if not "".join(parts).strip():
            model = None
            parts = [_fallback(sources) if question else NO_ANSWER]
            yield _event({"type": "delta", "text": parts[0]})

        response = AskResponse(
            question=question,
            answer="".join(parts).strip(),
            found=bool(sources) or model is not None,
            sources=sources,
            conversation_id=request.conversation_id,
            model=model,
        )
        if question:
            try:
                _record(request, response, (time.perf_counter() - started) * 1000)
            except Exception:  # e.g. the conversation was deleted mid-stream
                logger.exception("Could not save the streamed answer")
        yield _event(
            {
                "type": "done",
                "answer": response.answer,
                "found": response.found,
                "model": response.model,
                "conversation_id": response.conversation_id,
            }
        )

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        # Ask proxies (nginx, Vite) not to buffer, so text appears as it is written.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
