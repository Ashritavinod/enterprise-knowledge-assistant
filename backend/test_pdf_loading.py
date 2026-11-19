"""Standalone smoke test for loading policy PDFs."""

import logging

from services.pdf_loader import find_pdf_files, load_documents


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    pdf_files = find_pdf_files()
    documents = load_documents()

    print(f"PDFs found: {len(pdf_files)}")
    print(f"Pages loaded: {len(documents)}")

    if documents:
        print("First document metadata:")
        print(documents[0].metadata)
        print("First 300 characters:")
        print(documents[0].page_content[:300])
    else:
        print("No pages were loaded.")


if __name__ == "__main__":
    main()
