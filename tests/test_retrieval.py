"""End-to-end tests for PDF loading, chunking and FAISS retrieval.

Run from the repository root with either:
    python -m unittest discover tests -v
    python -m pytest tests
"""

import json
import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from langchain_core.documents import Document

from backend.services import rag_service, vector_store
from backend.services.pdf_loader import find_pdf_files, load_documents

logging.disable(logging.CRITICAL)

# (question, substring of the answer that must appear in a top-3 chunk)
LEXICAL_CASES = [
    ("What is the hex code for Raspberry Swirl?", "#E8456B"),
    ("Which color is primary in our palette?", "Honey Gold"),
    ("How many hashtags can I use in a social post?", "three hashtags"),
    ("What's the max subject line length for emails?", "45 characters"),
    ("How is the 2026 marketing budget allocated?", "26%"),
    ("What is the Crumb Club membership target for 2026?", "600,000"),
    ("Who reviews allergen claims?", "Arun Mehta"),
    ("How often do we post on Instagram and TikTok?", "four TikToks"),
    ("What is the approval SLA for Tier 1 content?", "1 business day"),
    ("Minimum sample size for an A/B test?", "2,000"),
    ("What date does Summer Scoops launch?", "June 15, 2026"),
    ("Can we offer 30% off in a campaign?", "25%"),
    ("How much does an 8-inch celebration cake cost?", "$54"),
    ("When is the post-campaign report due?", "7 business days"),
    ("Who are the Tier 2 approvers?", "Theo Marchetti"),
    ("which fonts are approved?", "Fraunces"),
    ("revenue growth goal this year", "$182M"),
    ("What is our tagline?", "sweeter by the crumb"),
    ("How many honey butter croissants did we sell last year?", "2.1 million"),
    ("What can we label as gluten-free?", "20 ppm"),
]

# Paraphrased questions with little word overlap; need semantic embeddings.
SEMANTIC_CASES = [
    ("How fast must we reply to people commenting on instagram?", "two hours"),
    ("What perks do loyalty members get?", "birthday"),
    ("How big a cake do I need for 20 people?", "10-inch"),
    ("Can influencers get free stuff?", "$150"),
    ("What words are we not allowed to use?", "guilt-free"),
    # These used to miss when chunks were cut every 500 characters.
    ("Who are our main competitors?", "Sweetwell"),
    ("Give me the 30-second elevator pitch", "30-second pitch"),
    ("What time of day should marketing emails go out?", "10:00"),
    ("Where are we opening new stores this year?", "Denver"),
]
SEMANTIC_OFF_TOPIC = [
    "How many vacation days do employees get?",
    "What is the travel reimbursement policy for airfare?",
    "How do I reset my laptop password?",
]

_original_paths: dict[str, Path] = {}
_temp_dir: Path


def setUpModule() -> None:
    """Build the index in a temporary directory so data/index is untouched."""
    global _temp_dir
    _temp_dir = Path(tempfile.mkdtemp(prefix="faiss-test-"))
    for name in ("INDEX_DIRECTORY", "INDEX_FILE", "DOCUMENTS_FILE"):
        _original_paths[name] = getattr(vector_store, name)
    vector_store.INDEX_DIRECTORY = _temp_dir
    vector_store.INDEX_FILE = _temp_dir / "index.faiss"
    vector_store.DOCUMENTS_FILE = _temp_dir / "documents.json"
    vector_store._vector_store = None
    vector_store.get_vector_store()


def tearDownModule() -> None:
    for name, value in _original_paths.items():
        setattr(vector_store, name, value)
    vector_store._vector_store = None
    shutil.rmtree(_temp_dir, ignore_errors=True)


def _uses_semantic_embeddings() -> bool:
    return isinstance(vector_store.get_embedding_model(), vector_store.FastEmbedEmbeddings)


def _answer_rank(question: str, answer: str) -> int | None:
    results = rag_service.retrieve_documents(question)
    return next(
        (
            rank
            for rank, result in enumerate(results, start=1)
            if answer.lower() in str(result["content"]).lower()
        ),
        None,
    )


class PdfExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents = load_documents()

    def test_all_policy_pdfs_load(self) -> None:
        pdf_files = find_pdf_files()
        self.assertGreaterEqual(len(pdf_files), 1)
        loaded = {Path(d.metadata["source"]).name for d in self.documents}
        self.assertEqual(loaded, {path.name for path in pdf_files})

    def test_pages_have_text_and_page_numbers(self) -> None:
        for document in self.documents:
            self.assertGreater(len(document.page_content.strip()), 50)
            self.assertEqual(
                document.metadata["page_number"], document.metadata["page"] + 1
            )

    def test_chunks_keep_metadata_and_size(self) -> None:
        chunks = vector_store.split_documents(self.documents)
        self.assertGreater(len(chunks), len(self.documents))
        for chunk in chunks:
            self.assertIn("source", chunk.metadata)
            self.assertIn("page", chunk.metadata)
            self.assertLessEqual(len(chunk.page_content), vector_store.CHUNK_SIZE)
            self.assertIn("section", chunk.metadata)

    def test_loader_marks_headings_and_table_rows(self) -> None:
        text = "\n\n".join(d.page_content for d in self.documents)
        self.assertIn("## 7. Color Palette", text)
        self.assertIn("### Social media", text)
        self.assertIn("Paid social | 26% | $3.07M", text)
        self.assertNotIn("Page 1 of", text)  # running footers are dropped


def _page(text: str, page: int, source: str = "Guide.pdf") -> Document:
    return Document(page_content=text, metadata={"source": source, "page": page})


class StructuredChunkingTests(unittest.TestCase):
    def test_chunks_start_with_their_section_and_never_cross_headings(self) -> None:
        chunks = vector_store.split_documents([
            _page("# Guide\n\n## 1. Logo\n\nUse the logo.\n\n## 2. Colors\n\n### Primary\n\nGold.", 0),
        ])
        self.assertEqual(
            [(c.metadata["section"], c.page_content) for c in chunks],
            [
                ("1. Logo", "1. Logo\nUse the logo."),
                ("2. Colors › Primary", "2. Colors › Primary\nGold."),
            ],
        )

    def test_faq_entries_are_their_own_chunks(self) -> None:
        chunks = vector_store.split_documents([
            _page("## FAQ\n\nQ: One? A: First.\n\nQ: Two? A: Second.", 0),
        ])
        self.assertEqual([c.page_content for c in chunks],
                         ["FAQ\nQ: One? A: First.", "FAQ\nQ: Two? A: Second."])

    def test_paragraph_split_by_page_break_is_rejoined(self) -> None:
        chunks = vector_store.split_documents([
            _page("## Goals\n\nQ: Target? A: Grow from 410,000 members to", 0),
            _page("600,000 members.\n\n## Next\n\nMore.", 1),
        ])
        self.assertEqual(chunks[0].page_content, "Goals\nQ: Target? A: Grow from 410,000 members to 600,000 members.")
        self.assertEqual(chunks[0].metadata["page"], 0)
        self.assertEqual(chunks[1].metadata["page"], 1)

    def test_pages_from_different_files_are_not_joined(self) -> None:
        chunks = vector_store.split_documents([
            _page("Ends without a period", 0, "A.pdf"),
            _page("starts a new file.", 0, "B.pdf"),
        ])
        self.assertEqual(len(chunks), 2)

    def test_long_paragraphs_are_split_within_the_size_limit(self) -> None:
        sentence = "Every campaign needs a brief with a goal and a budget. "
        chunks = vector_store.split_documents([_page("## Rules\n\n" + sentence * 40, 0)])
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertTrue(chunk.page_content.startswith("Rules\n"))
            self.assertLessEqual(len(chunk.page_content), vector_store.CHUNK_SIZE)


class RetrievalTests(unittest.TestCase):
    def test_sample_questions_retrieve_answer(self) -> None:
        for question, answer in LEXICAL_CASES:
            with self.subTest(question=question):
                self.assertIsNotNone(_answer_rank(question, answer))

    def test_paraphrased_questions_retrieve_answer(self) -> None:
        if not _uses_semantic_embeddings():
            self.skipTest("requires fastembed semantic embeddings")
        for question, answer in SEMANTIC_CASES:
            with self.subTest(question=question):
                self.assertIsNotNone(_answer_rank(question, answer))

    def test_results_have_expected_shape_and_threshold(self) -> None:
        results = rag_service.retrieve_documents("What is the MQL target for 2026?")
        self.assertTrue(1 <= len(results) <= 3)
        min_score = vector_store.get_retrieval_min_score()
        for result in results:
            self.assertEqual(set(result), {"content", "source", "page", "section", "score"})
            self.assertTrue(str(result["source"]).endswith(".pdf"))
            self.assertGreaterEqual(result["score"], min_score)

    def test_unrelated_question_returns_nothing(self) -> None:
        self.assertEqual(rag_service.retrieve_documents("What is the capital of France?"), [])

    def test_off_topic_policy_questions_return_nothing(self) -> None:
        if not _uses_semantic_embeddings():
            self.skipTest("lexical embeddings cannot separate these reliably")
        for question in SEMANTIC_OFF_TOPIC:
            with self.subTest(question=question):
                self.assertEqual(rag_service.retrieve_documents(question), [])

    def test_empty_question_returns_nothing(self) -> None:
        self.assertEqual(rag_service.retrieve_documents(""), [])


class IndexPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = vector_store.split_documents(load_documents())
        self.fingerprint = vector_store.compute_corpus_fingerprint(self.chunks)

    def tearDown(self) -> None:
        # Restore the index for the real corpus for any later tests.
        vector_store._vector_store = None
        vector_store.initialize_vector_store(self.chunks)

    def test_unchanged_corpus_reuses_index(self) -> None:
        self.assertIsNotNone(vector_store.load_index(self.fingerprint))

    def test_changed_corpus_triggers_rebuild(self) -> None:
        changed = self.chunks + [
            Document(page_content="New policy text", metadata={"source": "New.pdf", "page": 0})
        ]
        new_fingerprint = vector_store.compute_corpus_fingerprint(changed)
        self.assertNotEqual(new_fingerprint, self.fingerprint)
        self.assertIsNone(vector_store.load_index(new_fingerprint))

        rebuilt = vector_store.initialize_vector_store(changed)
        self.assertEqual(rebuilt.index.ntotal, len(changed))

    def test_index_from_other_embedding_model_is_ignored(self) -> None:
        saved = json.loads(vector_store.DOCUMENTS_FILE.read_text(encoding="utf-8"))
        saved["embedding_model"] = "some-other-model"
        vector_store.DOCUMENTS_FILE.write_text(json.dumps(saved), encoding="utf-8")
        self.assertIsNone(vector_store.load_index(self.fingerprint))


if __name__ == "__main__":
    unittest.main()
