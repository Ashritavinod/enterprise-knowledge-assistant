import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.services.pdf_loader import load_documents
from backend.services.vector_store import initialize_vector_store, split_documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load policies and initialize the persistent vector index at startup."""
    logger.info("Loading policy PDFs for FAISS startup")
    documents = load_documents()
    chunks = split_documents(documents)
    app.state.vector_store = initialize_vector_store(chunks)
    yield


app = FastAPI(title="Employee Knowledge Assistant API", lifespan=lifespan)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
