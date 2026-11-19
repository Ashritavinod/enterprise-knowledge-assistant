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
    ("What is the hex code for Pulse Coral?", "#FF6B5A"),
    ("What is our primary brand color?", "Aurelis Indigo"),
    ("How many hashtags can I use in a social post?", "three hashtags"),
    ("What's the max subject line length for emails?", "50 characters"),
    ("How is the 2026 marketing budget allocated?", "28%"),
    ("What is the MQL target for 2026?", "18,000"),
    ("Who handles legal review of competitive claims?", "Samuel Grant"),
    ("How far before launch is a Tier 3 campaign brief due?", "8 weeks"),
    ("What is the approval SLA for Tier 1 content?", "1 business day"),
    ("Minimum sample size for an A/B test?", "1,000"),
    ("When does Pulse Copilot become generally available?", "April 14, 2026"),
    ("Can we offer a 20% discount in a campaign email?", "15%"),
    ("How much did Brightwater Financial reduce churn?", "23%"),
    ("Give me the 30-second elevator pitch", "30-second"),
    ("When is the post-campaign report due?", "10 business days"),
    ("Who owns web and SEO standards?", "Aisha Bello"),
    ("which fonts are approved?", "Inter"),
    ("revenue growth goal this year", "$240M"),
]

# Paraphrased questions with little word overlap; need semantic embeddings.
SEMANTIC_CASES = [
    ("What are the Starter and Growth list prices?", "$1,200"),
    ("Who are our main competitors?", "InsightHive"),
    ("What time of day should marketing emails be sent?", "9:00"),
    ("How fast must we reply to people mentioning us on twitter?", "four business hours"),
]
SEMANTIC_OFF_TOPIC = [
    "How many vacation days do employees get?",
    "What is the travel reimbursement policy for airfare?",
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
            self.assertEqual(set(result), {"content", "source", "page", "score"})
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
