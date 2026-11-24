"""Mirror the indexed PDFs and their chunks into PostgreSQL."""

import hashlib
import logging
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Chunk, Document

logger = logging.getLogger(__name__)


def title_from_filename(name: str) -> str:
    """'MarketingStrategy2026.pdf' -> 'Marketing Strategy 2026'."""
    stem = name.rsplit(".", 1)[0]
    words = re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Z])", " ", stem)
    return words.strip()


_LAST_UPDATED = re.compile(r"Last updated\W+([A-Z][a-z]+ \d{1,2}, \d{4})")


def last_updated(text: str) -> date | None:
    """Read 'Last updated | November 10, 2026' from a document's details table."""
    match = _LAST_UPDATED.search(text)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%B %d, %Y").date()
    except ValueError:
        return None


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sync_documents(session: Session, vector_store: FAISS) -> None:
    """Make the documents/chunks tables match the FAISS index.

    A document's chunks are rewritten only when its FAISS ids changed (the
    index was rebuilt), so restarts with an unchanged corpus do no writes.
    """
    by_source: dict[str, list[tuple[str, LCDocument]]] = defaultdict(list)
    for _, faiss_id in sorted(vector_store.index_to_docstore_id.items()):
        chunk = vector_store.docstore.search(faiss_id)
        if isinstance(chunk, LCDocument):
            by_source[str(chunk.metadata.get("source", ""))].append((faiss_id, chunk))

    existing = {doc.name: doc for doc in session.scalars(select(Document))}
    seen: set[str] = set()

    for source, chunks in by_source.items():
        path = Path(source)
        name = path.name
        seen.add(name)
        document = existing.get(name)
        faiss_ids = [faiss_id for faiss_id, _ in chunks]
        if document is not None and [c.faiss_id for c in document.chunks] == faiss_ids:
            continue

        if document is None:
            document = Document(name=name)
            session.add(document)
        else:
            # Delete old rows before inserting new ones so the
            # (document_id, chunk_index) unique constraint never collides.
            document.chunks.clear()
            session.flush()
        document.title = title_from_filename(name)
        document.content_hash = _file_hash(path) if path.is_file() else ""
        document.page_count = int(chunks[0][1].metadata.get("total_pages", 0))
        document.chunk_count = len(chunks)
        document.chunks = [
            Chunk(
                chunk_index=position,
                faiss_id=faiss_id,
                page=int(chunk.metadata.get("page", 0)) + 1,
                section=str(chunk.metadata.get("section", "")),
                content=chunk.page_content,
            )
            for position, (faiss_id, chunk) in enumerate(chunks)
        ]
        session.flush()
        logger.info("Stored %d chunk(s) for %s in PostgreSQL", len(chunks), name)

    for name, document in existing.items():
        if name not in seen:
            logger.info("Removing %s from PostgreSQL: no longer indexed", name)
            session.delete(document)
