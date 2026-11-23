"""Tests for the API used by the React chat frontend.

These run against a real PostgreSQL database named by TEST_DATABASE_URL
(default: knowledge_assistant_test on localhost). Its tables are dropped and
recreated, so never point it at a database whose data you need. The API tests
are skipped when that database is unreachable.
"""

import logging
import os
import unittest

os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant_test",
)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from backend.db import models  # noqa: E402
from backend.db.database import check_db, get_engine, session_scope  # noqa: E402
from backend.main import app  # noqa: E402
from backend.routes.qa import NO_ANSWER, clean_excerpt  # noqa: E402

logging.disable(logging.CRITICAL)


class CleanExcerptTests(unittest.TestCase):
    def test_strips_section_header_and_keeps_lines(self) -> None:
        raw = "7. Color Palette\nIntro paragraph.\n• First bullet\nHoney Gold | #F5A623\n"
        self.assertEqual(
            clean_excerpt(raw, "7. Color Palette"),
            "Intro paragraph.\n• First bullet\nHoney Gold | #F5A623",
        )
        # A first line that is not the section is kept.
        self.assertEqual(clean_excerpt("Other\nText.", "7. Color Palette"), "Other\nText.")

    def test_drops_mid_sentence_lead_in(self) -> None:
        self.assertEqual(
            clean_excerpt("outcomes. Neutrals keep layouts calm."),
            "Neutrals keep layouts calm.",
        )
        self.assertEqual(clean_excerpt("no sentence break here"), "no sentence break here")


class ApiTestCase(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        if not check_db():
            raise unittest.SkipTest(
                f"PostgreSQL test database unreachable ({os.environ['DATABASE_URL']}); "
                "set TEST_DATABASE_URL"
            )
        models.Base.metadata.drop_all(get_engine())
        cls.client = TestClient(app)
        cls.client.__enter__()  # runs the lifespan: create tables, index, sync

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)


class QaApiTests(ApiTestCase):
    def test_health_reports_database(self) -> None:
        self.assertEqual(
            self.client.get("/health").json(), {"status": "ok", "database": "ok"}
        )

    def test_ask_returns_answer_with_sources(self) -> None:
        response = self.client.post(
            "/qa/ask", json={"question": "What is the hex code for Raspberry Swirl?"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["found"])
        self.assertTrue(1 <= len(body["sources"]) <= 3)
        self.assertIn("#E8456B", " ".join(s["excerpt"] for s in body["sources"]))
        for source in body["sources"]:
            self.assertTrue(source["document"].endswith(".pdf"))
            self.assertGreaterEqual(source["page"], 1)
            self.assertFalse(source["excerpt"].startswith(source["section"] + "\n"))
        self.assertIn("Color Palette", body["sources"][0]["section"])
        self.assertEqual(body["answer"], body["sources"][0]["excerpt"])

    def test_ask_is_logged(self) -> None:
        question = "What is the hex code for Honey Gold?"
        self.client.post("/qa/ask", json={"question": question})
        with session_scope() as db:
            log = db.scalar(
                select(models.QueryLog).where(models.QueryLog.question == question)
            )
            self.assertIsNotNone(log)
            assert log is not None
            self.assertTrue(log.found)
            self.assertEqual(log.top_document, "BrandGuidelines.pdf")
            self.assertGreater(log.top_score or 0, 0)

    def test_unrelated_question_returns_fallback(self) -> None:
        body = self.client.post(
            "/qa/ask", json={"question": "What is the capital of France?"}
        ).json()
        self.assertFalse(body["found"])
        self.assertEqual(body["sources"], [])
        self.assertEqual(body["answer"], NO_ANSWER)

    def test_blank_question_returns_fallback(self) -> None:
        body = self.client.post("/qa/ask", json={"question": "   "}).json()
        self.assertFalse(body["found"])

    def test_documents_lists_indexed_pdfs_from_database(self) -> None:
        documents = self.client.get("/qa/documents").json()["documents"]
        by_name = {d["name"]: d for d in documents}
        self.assertIn("BrandGuidelines.pdf", by_name)
        self.assertGreater(by_name["BrandGuidelines.pdf"]["chunk_count"], 0)
        self.assertGreater(by_name["BrandGuidelines.pdf"]["page_count"], 0)
        self.assertIn("Marketing Strategy 2026", {d["title"] for d in documents})
        with session_scope() as db:
            stored_chunks = db.scalar(select(func.count()).select_from(models.Chunk))
        self.assertEqual(stored_chunks, sum(d["chunk_count"] for d in documents))


class ConversationApiTests(ApiTestCase):
    def test_conversation_round_trip(self) -> None:
        created = self.client.post("/conversations", json={"title": "Colors"})
        self.assertEqual(created.status_code, 201)
        conversation_id = created.json()["id"]

        answer = self.client.post(
            "/qa/ask",
            json={
                "question": "What is the hex code for Raspberry Swirl?",
                "conversation_id": conversation_id,
            },
        ).json()
        self.assertEqual(answer["conversation_id"], conversation_id)

        detail = self.client.get(f"/conversations/{conversation_id}").json()
        self.assertEqual([m["role"] for m in detail["messages"]], ["user", "assistant"])
        self.assertEqual(detail["messages"][1]["text"], answer["answer"])
        self.assertEqual(detail["messages"][1]["sources"], answer["sources"])

        listed = [c["id"] for c in self.client.get("/conversations").json()]
        self.assertIn(conversation_id, listed)

        self.assertEqual(self.client.delete(f"/conversations/{conversation_id}").status_code, 204)
        self.assertEqual(self.client.get(f"/conversations/{conversation_id}").status_code, 404)

    def test_unknown_conversation_is_404(self) -> None:
        missing = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            "/qa/ask", json={"question": "Brand colors?", "conversation_id": missing}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.delete(f"/conversations/{missing}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
