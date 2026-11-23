import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.db.database import check_db, dispose_engine, init_db, session_scope
from backend.routes.conversations import router as conversations_router
from backend.routes.qa import router as qa_router
from backend.services.document_registry import sync_documents
from backend.services.pdf_loader import load_documents
from backend.services.vector_store import initialize_vector_store, split_documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect to PostgreSQL, build or load the FAISS index, and mirror it to the DB."""
    init_db()
    logger.info("Loading policy PDFs for FAISS startup")
    documents = load_documents()
    chunks = split_documents(documents)
    app.state.vector_store = initialize_vector_store(chunks)
    with session_scope() as session:
        sync_documents(session, app.state.vector_store)
    yield
    dispose_engine()


app = FastAPI(title="Employee Knowledge Assistant API", lifespan=lifespan)
app.include_router(qa_router)
app.include_router(conversations_router)


@app.get("/health")
def health_check() -> JSONResponse:
    database = "ok" if check_db() else "unavailable"
    status = "ok" if database == "ok" else "degraded"
    return JSONResponse(
        {"status": status, "database": database},
        status_code=200 if status == "ok" else 503,
    )
