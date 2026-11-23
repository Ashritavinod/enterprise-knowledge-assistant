"""Embedding, chunking and FAISS index helpers."""

import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_DIRECTORY = PROJECT_ROOT / "data" / "index"
INDEX_FILE = INDEX_DIRECTORY / "index.faiss"
DOCUMENTS_FILE = INDEX_DIRECTORY / "documents.json"
INDEX_FORMAT_VERSION = 3
CHUNK_SIZE = 700
CHUNK_OVERLAP = 50
DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"


def _normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


class LocalHashEmbeddings(Embeddings):
    """Create deterministic local token-hash vectors without external models.

    This is a lexical fallback: it only matches shared words and word pairs, so
    it cannot handle synonyms or paraphrases. Prefer FastEmbedEmbeddings.
    """

    model_id = "local-hash-v2"
    # Measured on the marketing corpus: correct answers score >= 0.11, while
    # unrelated queries score 0.06-0.12. Lexical scores overlap, so this only
    # trims clear noise; semantic embeddings are needed for a sharp cut-off.
    default_min_score = 0.10
    dimension = 2048
    _stop_words = frozenset(
        """
        a about all also am an and any are as at be been being but by can could
        did do does doing for from get gets give had has have how i if in into is
        it its me more most my no not of on or our ours should so than that the
        their them then there these they this those to us was we were what when
        where which who whom why will with would you your
        """.split()
    )
    _normalizations = {
        "airfare": "airfare",
        "employees": "employee",
        "hours": "hour",
        "leaves": "leave",
        "policies": "policy",
        "reimbursements": "reimbursement",
        "working": "work",
    }

    def _tokens(self, text: str) -> list[str]:
        return [
            self._normalizations.get(token, token)
            for token in re.findall(r"\b\w+\b", text.lower())
            if token not in self._stop_words
        ]

    def _embed(self, text: str) -> list[float]:
        tokens = self._tokens(text)
        vector = [0.0] * self.dimension
        features = [f"word:{token}" for token in tokens]
        features.extend(
            f"pair:{first}_{second}" for first, second in zip(tokens, tokens[1:])
        )
        for feature in set(features):
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            vector[int.from_bytes(digest, byteorder="big") % self.dimension] = 1.0
        return _normalize(vector)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


class FastEmbedEmbeddings(Embeddings):
    """Semantic embeddings from a local ONNX model via the `fastembed` package.

    The model is downloaded once on first use and then runs offline on CPU.
    """

    # bge-small-en-v1.5 cosine scores sit roughly in [0.5, 1.0]; unrelated text
    # usually stays below ~0.6. Override with RETRIEVAL_MIN_SCORE if needed.
    default_min_score = 0.6

    def __init__(self, model_name: str = DEFAULT_FASTEMBED_MODEL) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.model_id = f"fastembed:{model_name}"
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_normalize(vector.tolist()) for vector in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vector = next(iter(self._model.query_embed(text)))
        return _normalize(vector.tolist())


_embedding_model: Embeddings | None = None
_vector_store: FAISS | None = None


def _create_embedding_model() -> Embeddings:
    """Pick the embedding backend from EMBEDDING_PROVIDER (auto|fastembed|hash)."""
    provider = os.getenv("EMBEDDING_PROVIDER", "auto").strip().lower()
    if provider == "hash":
        return LocalHashEmbeddings()
    if provider not in {"auto", "fastembed"}:
        raise ValueError(
            f"Unknown EMBEDDING_PROVIDER {provider!r}; use auto, fastembed or hash"
        )

    model_name = os.getenv("FASTEMBED_MODEL", DEFAULT_FASTEMBED_MODEL)
    try:
        model = FastEmbedEmbeddings(model_name)
    except Exception:
        if provider == "fastembed":
            raise
        logger.warning(
            "fastembed is unavailable (install it with `pip install fastembed`); "
            "falling back to lexical hash embeddings, which miss paraphrases",
            exc_info=logger.isEnabledFor(logging.DEBUG),
        )
        return LocalHashEmbeddings()
    logger.info("Using fastembed embeddings: %s", model_name)
    return model


def get_embedding_model() -> Embeddings:
    """Return the process-wide embedding implementation."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = _create_embedding_model()
    return _embedding_model


def get_embedding_model_id() -> str:
    return getattr(get_embedding_model(), "model_id", type(get_embedding_model()).__name__)


def get_retrieval_min_score() -> float:
    """Minimum similarity a chunk needs to be returned (RETRIEVAL_MIN_SCORE overrides)."""
    override = os.getenv("RETRIEVAL_MIN_SCORE")
    if override:
        return float(override)
    return float(getattr(get_embedding_model(), "default_min_score", 0.0))


def compute_corpus_fingerprint(chunks: list[Document]) -> str:
    """Hash chunk text, source file names and chunking settings.

    A persisted index is reused only when this matches, so adding, removing or
    editing a PDF (or changing chunk settings) triggers a rebuild.
    """
    digest = hashlib.sha256(f"{CHUNK_SIZE}:{CHUNK_OVERLAP}".encode())
    for chunk in chunks:
        source = Path(str(chunk.metadata.get("source", ""))).name
        page = chunk.metadata.get("page", "")
        digest.update(f"\0{source}\0{page}\0".encode("utf-8"))
        digest.update(chunk.page_content.encode("utf-8"))
    return digest.hexdigest()


def build_faiss_index(chunks: list[Document]) -> FAISS:
    """Build a cosine-similarity FAISS index from chunked documents."""
    embedding_model = get_embedding_model()
    dimension = len(embedding_model.embed_query("dimension probe"))
    vector_store = FAISS(
        embedding_function=embedding_model,
        index=faiss.IndexFlatIP(dimension),
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )
    if chunks:
        vector_store.add_documents(chunks)
    logger.info("Created FAISS index for %d chunk(s)", len(chunks))
    return vector_store


def save_index(vector_store: FAISS, corpus_fingerprint: str) -> None:
    """Persist the FAISS index and its documents without pickle deserialization."""
    INDEX_DIRECTORY.mkdir(parents=True, exist_ok=True)
    documents: list[dict[str, Any]] = []
    for index, document_id in sorted(vector_store.index_to_docstore_id.items()):
        document = vector_store.docstore.search(document_id)
        if not isinstance(document, Document):
            raise TypeError(f"FAISS document ID {document_id!r} is missing")
        documents.append(
            {
                "index": index,
                "id": document_id,
                "content": document.page_content,
                "metadata": document.metadata,
            }
        )

    faiss.write_index(vector_store.index, str(INDEX_FILE))
    DOCUMENTS_FILE.write_text(
        json.dumps(
            {
                "format_version": INDEX_FORMAT_VERSION,
                "embedding_model": get_embedding_model_id(),
                "corpus_fingerprint": corpus_fingerprint,
                "documents": documents,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(
        "Saved FAISS index with %d chunk(s) to %s",
        len(documents),
        INDEX_DIRECTORY,
    )


def load_index(expected_fingerprint: str | None = None) -> FAISS | None:
    """Load a persisted FAISS index, or return None when it is missing or stale."""
    if not INDEX_FILE.is_file() or not DOCUMENTS_FILE.is_file():
        logger.info("No complete FAISS index found in %s", INDEX_DIRECTORY)
        return None

    saved_data = json.loads(DOCUMENTS_FILE.read_text(encoding="utf-8"))
    if (
        not isinstance(saved_data, dict)
        or saved_data.get("format_version") != INDEX_FORMAT_VERSION
        or saved_data.get("embedding_model") != get_embedding_model_id()
    ):
        logger.info("Persisted FAISS index uses a different embedding model or format")
        return None
    if (
        expected_fingerprint is not None
        and saved_data.get("corpus_fingerprint") != expected_fingerprint
    ):
        logger.info("Policy documents changed since the FAISS index was built")
        return None

    records = saved_data["documents"]
    index = faiss.read_index(str(INDEX_FILE))
    embedding_model = get_embedding_model()
    embedding_dimension = len(embedding_model.embed_query("dimension probe"))
    if index.d != embedding_dimension:
        raise ValueError(
            f"FAISS index dimension {index.d} does not match embedding dimension "
            f"{embedding_dimension}"
        )
    documents = {
        record["id"]: Document(
            page_content=record["content"],
            metadata=record["metadata"],
        )
        for record in records
    }
    index_to_docstore_id = {int(record["index"]): record["id"] for record in records}
    if index.ntotal != len(index_to_docstore_id):
        raise ValueError(
            "FAISS index and document metadata contain different chunk counts"
        )

    vector_store = FAISS(
        embedding_function=embedding_model,
        index=index,
        docstore=InMemoryDocstore(documents),
        index_to_docstore_id=index_to_docstore_id,
        distance_strategy=DistanceStrategy.MAX_INNER_PRODUCT,
    )
    logger.info(
        "Loaded FAISS index with %d chunk(s) from %s",
        index.ntotal,
        INDEX_DIRECTORY,
    )
    return vector_store


def initialize_vector_store(chunks: list[Document]) -> FAISS:
    """Reuse the persisted index if it matches these chunks; otherwise rebuild it."""
    global _vector_store
    fingerprint = compute_corpus_fingerprint(chunks)
    existing_index = load_index(expected_fingerprint=fingerprint)
    if existing_index is not None:
        _vector_store = existing_index
        return existing_index

    _vector_store = build_faiss_index(chunks)
    save_index(_vector_store, fingerprint)
    return _vector_store


def get_vector_store() -> FAISS:
    """Return the initialized index, creating it from policy PDFs if necessary."""
    if _vector_store is not None:
        return _vector_store

    from .pdf_loader import load_documents

    documents = load_documents()
    chunks = split_documents(documents)
    return initialize_vector_store(chunks)


_QA_PARAGRAPH = re.compile(r"^Q\s*[:.]")
_STRUCTURAL = re.compile(r"^(#{1,3} |• |Q\s*[:.])")


def _continues(previous: str, paragraph: str) -> bool:
    """True when `paragraph` is the rest of `previous`, split by a page break."""
    if previous.startswith("#") or " | " in previous or " | " in paragraph:
        return False
    if previous.rstrip().endswith((".", "!", "?", ":", '"', "”")):
        return False
    return not _STRUCTURAL.match(paragraph)


class _SectionChunker:
    """Pack whole paragraphs into chunks that never cross a section heading.

    Every chunk starts with a one-line section path ("2. Goals › Paid media")
    so the heading's words are embedded with the text under it. FAQ-style
    "Q: ... A: ..." paragraphs always become their own chunk, so a question is
    never separated from its answer.
    """

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks: list[Document] = []
        self._source = ""
        self._title = ""
        self._h2 = ""
        self._h3 = ""
        self._paragraphs: list[str] = []
        self._page: Any = None
        self._metadata: dict[str, Any] = {}

    def section(self) -> str:
        if self._h2:
            return " › ".join(part for part in (self._h2, self._h3) if part)
        return self._title

    def start_source(self, source: str, fallback_title: str) -> None:
        self.flush()
        self._source = source
        self._title = fallback_title
        self._h2 = self._h3 = ""

    def add_paragraph(self, paragraph: str, page: Any, metadata: dict[str, Any]) -> None:
        self._metadata = metadata
        if paragraph.startswith("# "):
            self.flush()
            self._title = paragraph[2:].strip()
        elif paragraph.startswith("## "):
            self.flush()
            self._h2, self._h3 = paragraph[3:].strip(), ""
        elif paragraph.startswith("### "):
            self.flush()
            self._h3 = paragraph[4:].strip()
        elif _QA_PARAGRAPH.match(paragraph):
            self.flush()
            self._add(paragraph, page)
            self.flush()
        else:
            self._add(paragraph, page)

    def _header(self) -> str:
        section = self.section()
        return f"{section}\n" if section else ""

    def _add(self, paragraph: str, page: Any) -> None:
        budget = self.chunk_size - len(self._header())
        if len(paragraph) > budget:
            self.flush()
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=max(budget, 100),
                chunk_overlap=self.chunk_overlap,
                separators=["\n", ". ", "; ", ", ", " ", ""],
                keep_separator="end",
            )
            for piece in splitter.split_text(paragraph):
                self._paragraphs, self._page = [piece.strip()], page
                self.flush()
            return
        current = sum(len(p) + 1 for p in self._paragraphs)
        if self._paragraphs and current + len(paragraph) > budget:
            self.flush()
        if not self._paragraphs:
            self._page = page
        self._paragraphs.append(paragraph)

    def flush(self) -> None:
        if not self._paragraphs:
            return
        metadata = {
            key: value
            for key, value in self._metadata.items()
            if key in {"source", "page_number", "total_pages"}
        }
        metadata.update(
            source=self._source or metadata.get("source", ""),
            page=self._page if self._page is not None else 0,
            page_number=(self._page if isinstance(self._page, int) else 0) + 1,
            section=self.section(),
        )
        self.chunks.append(
            Document(
                page_content=self._header() + "\n".join(self._paragraphs),
                metadata=metadata,
            )
        )
        self._paragraphs = []
        self._page = None


def split_documents(documents: list[Document]) -> list[Document]:
    """Split page documents into section-aware chunks that keep their metadata.

    Pages should carry the structure markers produced by
    pdf_loader.extract_structured_pages ("#"/"##"/"###" headings, blank lines
    between paragraphs). Plain text without markers is still split on blank
    lines and, when needed, sentence boundaries.
    """
    logger.info("Documents received: %d", len(documents))
    chunker = _SectionChunker(CHUNK_SIZE, CHUNK_OVERLAP)
    current_source: object = None
    # The last paragraph of each page is held back in case the next page of the
    # same PDF continues it (a paragraph cut by a page break).
    carry: tuple[str, Any] | None = None
    metadata: dict[str, Any] = {}
    for document in documents:
        source = document.metadata.get("source", "")
        if source != current_source:
            if carry:
                chunker.add_paragraph(*carry, metadata)
                carry = None
            current_source = source
            stem = Path(str(source)).stem if source else ""
            chunker.start_source(str(source), re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", stem))
        metadata = dict(document.metadata)
        page = metadata.get("page")
        items = [
            (paragraph.strip(), page)
            for paragraph in document.page_content.split("\n\n")
            if paragraph.strip()
        ]
        if carry:
            if items and _continues(carry[0], items[0][0]):
                items[0] = (f"{carry[0]} {items[0][0]}", carry[1])
            else:
                items.insert(0, carry)
        carry = items.pop() if items else None
        for paragraph, paragraph_page in items:
            chunker.add_paragraph(paragraph, paragraph_page, metadata)
    if carry:
        chunker.add_paragraph(*carry, metadata)
    chunker.flush()
    chunks = chunker.chunks

    average_chunk_length = (
        sum(len(chunk.page_content) for chunk in chunks) / len(chunks) if chunks else 0
    )
    logger.info(
        "Chunks created: %d; average chunk length: %.2f",
        len(chunks),
        average_chunk_length,
    )
    return chunks


def get_chunk_stats(chunks: list[Document]) -> dict[str, int | float]:
    """Return chunk count and content-length statistics."""
    chunk_lengths = [len(chunk.page_content) for chunk in chunks]
    return {
        "chunk_count": len(chunk_lengths),
        "avg_chunk_size": (
            sum(chunk_lengths) / len(chunk_lengths) if chunk_lengths else 0
        ),
        "largest_chunk": max(chunk_lengths, default=0),
        "smallest_chunk": min(chunk_lengths, default=0),
    }
