"""Vector-based document retrieval helpers."""

import logging
import re
from pathlib import Path

from backend.models.schemas import Source

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


CHAT_PASSAGES = 6
TOPIC_PASSAGES = 2
# Chat passages scoring more than this below the best match are dropped: they are
# usually loosely related sections that add noise (and source cards) to the answer.
RELATIVE_MARGIN = 0.1

# Words people use that the documents spell differently. Each entry: the pattern,
# the documents' own term (swapped into the query) and a short topic search run
# alongside, so the matching section is found even when the rest of the question
# ("write a social media campaign...") dominates the similarity search.
QUERY_SYNONYMS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(r"\b(?:christmas|x-?mas|festive|yule(?:tide)?|thanksgiving|new year'?s?)\b", re.I),
        "holiday season",
        "holiday season campaign, holiday cookie tins and gifting",
    ),
    (
        re.compile(r"\b(?:autumn|halloween)\b", re.I),
        "fall",
        "fall seasonal campaign",
    ),
]


def expand_query(question: str) -> tuple[str, list[str]]:
    """Return the question in the documents' terms, plus topic searches to run too."""
    topics: list[str] = []
    for pattern, term, topic in QUERY_SYNONYMS:
        if pattern.search(question):
            question = pattern.sub(term, question)
            topics.append(topic)
    return question, topics


def _chunk_key(result: dict[str, str | int | float]) -> tuple[str, str]:
    return str(result["source"]), str(result["content"])


def retrieve_for_chat(question: str, k: int = CHAT_PASSAGES) -> list[dict[str, str | int | float]]:
    """Passages for a chat message: the question (with synonyms swapped in) plus
    the top matches of any topic searches, best first, at most `k`, and none more
    than RELATIVE_MARGIN below the best match."""
    query, topics = expand_query(question)
    extra: list[dict[str, str | int | float]] = []
    seen: set[tuple[str, str]] = set()
    for topic in topics:
        for result in retrieve_documents(topic, k=TOPIC_PASSAGES):
            if _chunk_key(result) not in seen:
                seen.add(_chunk_key(result))
                extra.append(result)
    extra = extra[:k]
    main = [r for r in retrieve_documents(query, k=k) if _chunk_key(r) not in seen]
    merged = sorted(main[: k - len(extra)] + extra, key=lambda r: float(r["score"]), reverse=True)
    if not merged:
        return []
    floor = float(merged[0]["score"]) - RELATIVE_MARGIN
    return [r for r in merged if float(r["score"]) >= floor]


def search_question(question: str) -> list[dict[str, str | int | float]]:
    """Compatibility wrapper for callers using the previous helper name."""
    return retrieve_documents(question)


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


def to_sources(results: list[dict[str, str | int | float]]) -> list[Source]:
    """Retrieved chunks as API sources: 1-based page, cleaned excerpt."""
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


def document_chunks(name: str) -> list[dict[str, str | int | float]]:
    """Every chunk of one indexed document (e.g. "BrandGuidelines.pdf"), in reading order.

    Same shape as `retrieve_documents` results, with score 1.0. Used where a
    whole short document matters, such as checking copy against every brand rule.
    """
    vector_store = get_vector_store()
    results: list[dict[str, str | int | float]] = []
    for _, document_id in sorted(vector_store.index_to_docstore_id.items()):
        document = vector_store.docstore.search(document_id)
        source = Path(str(document.metadata.get("source", ""))).name
        if source == name:
            results.append({
                "content": document.page_content,
                "source": source,
                "page": document.metadata.get("page", 0),
                "section": str(document.metadata.get("section", "")),
                "score": 1.0,
            })
    return results
