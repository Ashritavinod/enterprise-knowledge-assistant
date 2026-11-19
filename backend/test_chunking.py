"""Standalone smoke test for policy-document chunking."""

import logging

from services.pdf_loader import find_pdf_files, load_documents
from services.vector_store import get_chunk_stats, split_documents


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    documents = load_documents()
    chunks = split_documents(documents)

    print(f"Documents Loaded: {len(find_pdf_files())}")
    print(f"Pages Loaded: {len(documents)}")
    print(f"Chunks Created: {len(chunks)}")

    if any(
        "source" not in chunk.metadata or "page" not in chunk.metadata
        for chunk in chunks
    ):
        raise AssertionError("A chunk is missing source or page metadata")

    if chunks:
        print("First chunk metadata:")
        print(chunks[0].metadata)
        print("First 300 characters of first chunk:")
        print(chunks[0].page_content[:300])
    else:
        print("No chunks were created.")

    print("Chunk statistics:")
    for name, value in get_chunk_stats(chunks).items():
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
