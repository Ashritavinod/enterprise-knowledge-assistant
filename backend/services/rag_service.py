"""Vector-based document retrieval helpers."""

import logging
from pathlib import Path

from .vector_store import get_retrieval_min_score, get_vector_store

logger = logging.getLogger(__name__)


def retrieve_documents(question: str, k: int = 3) -> list[dict[str, str | int | float]]:
    """Return the `k` most similar chunks for a question (above the relevance threshold)."""
    logger.info("Executing FAISS query: %s", question)
    vector_store = get_vector_store()
    if vector_store.index.ntotal == 0:
        logger.info("FAISS index is empty; returning no results")
        return []
    matches = vector_store.similarity_search_with_score(
        question,
        k=min(k, vector_store.index.ntotal),
    )

    min_score = get_retrieval_min_score()
    results: list[dict[str, str | int | float]] = []
    for document, similarity in matches:
        if similarity < min_score or similarity <= 0:
            logger.info(
                "Dropping chunk below relevance threshold: similarity=%.4f < %.4f",
                similarity,
                min_score,
            )
            continue
        source = document.metadata.get("source", "")
        result = {
            "content": document.page_content,
            "source": Path(str(source)).name if source else "Unknown",
            "page": document.metadata.get("page", 0),
            "section": str(document.metadata.get("section", "")),
            "score": float(similarity),
        }
        results.append(result)
        logger.info(
            "Retrieved chunk: source=%s page=%s similarity=%.4f",
            result["source"],
            result["page"],
            result["score"],
        )

    logger.info(
        "FAISS retrieved %d chunk(s) from sources %s",
        len(results),
        sorted({str(result["source"]) for result in results}),
    )
    return results


def search_question(question: str) -> list[dict[str, str | int | float]]:
    """Compatibility wrapper for callers using the previous helper name."""
    return retrieve_documents(question)
