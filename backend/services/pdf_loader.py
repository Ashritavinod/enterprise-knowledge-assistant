"""Helpers for loading policy PDFs."""

import logging
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document

logger = logging.getLogger(__name__)
POLICIES_DIRECTORY = Path(__file__).resolve().parents[2] / "data" / "policies"


def find_pdf_files() -> list[Path]:
    """Return all PDF files under the policies directory in stable order."""
    return sorted(
        (
            path
            for path in POLICIES_DIRECTORY.rglob("*")
            if path.is_file() and path.suffix.lower() == ".pdf"
        ),
        key=lambda path: str(path).casefold(),
    )


def load_documents() -> list[Document]:
    """Load every PDF under the policies directory, skipping unreadable files."""
    pdf_files = find_pdf_files()
    logger.info(
        "Discovered %d PDF file(s) in %s",
        len(pdf_files),
        POLICIES_DIRECTORY,
    )

    documents: list[Document] = []
    loaded_files = 0
    failures = 0

    for pdf_path in pdf_files:
        logger.info("Found PDF: %s", pdf_path.name)
        try:
            file_documents = PyMuPDFLoader(str(pdf_path)).load()
        except Exception:
            failures += 1
            logger.exception("Failed to load PDF: %s", pdf_path)
            continue

        for page_offset, document in enumerate(file_documents):
            document.metadata.setdefault("source", str(pdf_path))
            page_index = document.metadata.get("page")
            page_number = (
                page_index + 1 if isinstance(page_index, int) else page_offset + 1
            )
            document.metadata.setdefault("page_number", page_number)

        documents.extend(file_documents)
        loaded_files += 1

    logger.info(
        "Loaded %d page(s) from %d PDF file(s); %d file(s) failed",
        len(documents),
        loaded_files,
        failures,
    )
    return documents
