"""Validate policy retrieval using the local FAISS vector index."""

import logging

from services.rag_service import retrieve_documents

QUESTIONS = (
    ("What is the hex code for Raspberry Swirl?", "BrandGuidelines.pdf"),
    ("How is the 2026 marketing budget allocated?", "MarketingStrategy2026.pdf"),
    ("Who approves Tier 2 campaigns?", "CampaignPlaybook.pdf"),
    ("How much does an 8-inch celebration cake cost?", "ProductMarketingGuide.pdf"),
    ("What do Crumb Club members get?", "MarketingFAQ.pdf"),
)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    for question, expected_source in QUESTIONS:
        results = retrieve_documents(question)
        print(f"\nQuestion: {question}")
        if not results:
            raise AssertionError(f"No results returned for {question!r}")

        for rank, result in enumerate(results, start=1):
            preview = str(result["content"]).replace("\n", " ")[:160]
            print(f"Result Rank: {rank}")
            print(f"Source: {result['source']}")
            print(f"Page: {result['page']}")
            print(f"Similarity Score: {result['score']:.4f}")
            print(f"Content Preview: {preview}")

        if expected_source not in {result["source"] for result in results}:
            raise AssertionError(
                f"Expected {expected_source} among the results for {question!r}"
            )


if __name__ == "__main__":
    main()
