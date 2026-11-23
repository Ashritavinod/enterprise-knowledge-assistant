"""Question-answering endpoints used by the chat frontend."""

import re
import time

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
from backend.services.rag_service import retrieve_documents
from backend.services.vector_store import get_embedding_model_id

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
    results = await run_in_threadpool(retrieve_documents, question) if question else []
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
    answer = sources[0].excerpt if sources else NO_ANSWER
    response = AskResponse(
        question=question,
        answer=answer,
        found=bool(sources),
        sources=sources,
        conversation_id=request.conversation_id,
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
