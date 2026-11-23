"""Tests for the API used by the React chat frontend.

These run against a real PostgreSQL database named by TEST_DATABASE_URL
(default: knowledge_assistant_test on localhost). Its tables are dropped and
recreated, so never point it at a database whose data you need. The API tests
are skipped when that database is unreachable.
"""

import json
import logging
import os
import unittest
from unittest import mock

from dotenv import load_dotenv

load_dotenv()  # TEST_DATABASE_URL may be set in .env
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant_test",
)
# Answers must be the top passage here; Azure generation is tested with a fake client.
os.environ["LLM_PROVIDER"] = "none"

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


class AzureAnswerApiTests(ApiTestCase):
    def test_generated_answer_is_returned_and_stored(self) -> None:
        conversation_id = self.client.post("/conversations", json={"title": "Azure"}).json()["id"]
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch(
                "backend.routes.qa.generate_answer", return_value="Raspberry Swirl is #E8456B [1]."
            ) as generate,
        ):
            body = self.client.post(
                "/qa/ask",
                json={
                    "question": "What is the hex code for Raspberry Swirl?",
                    "conversation_id": conversation_id,
                },
            ).json()
        self.assertEqual(body["answer"], "Raspberry Swirl is #E8456B [1].")
        self.assertEqual(body["model"], "gpt-test")
        self.assertTrue(body["sources"])
        question, sources, history = generate.call_args.args
        self.assertEqual(question, "What is the hex code for Raspberry Swirl?")
        self.assertEqual([s.document for s in sources], [s["document"] for s in body["sources"]])
        self.assertEqual(history, [])
        detail = self.client.get(f"/conversations/{conversation_id}").json()
        self.assertEqual(detail["messages"][1]["text"], body["answer"])

    def test_follow_up_sends_conversation_history(self) -> None:
        conversation_id = self.client.post("/conversations", json={"title": "History"}).json()["id"]
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.generate_answer", side_effect=["First.", "Second."]) as generate,
            mock.patch(
                "backend.routes.qa.rewrite_question",
                return_value="What is the hex code for Raspberry Swirl?",
            ) as rewrite,
        ):
            for question in ("What is the hex code for Honey Gold?", "And Raspberry Swirl?"):
                self.client.post(
                    "/qa/ask", json={"question": question, "conversation_id": conversation_id}
                )
        history = generate.call_args_list[1].args[2]
        self.assertEqual(
            history,
            [("user", "What is the hex code for Honey Gold?"), ("assistant", "First.")],
        )
        # Only the follow-up is rewritten, and retrieval uses the rewritten query.
        rewrite.assert_called_once_with("And Raspberry Swirl?", history)
        sources = generate.call_args_list[1].args[1]
        self.assertIn("#E8456B", " ".join(s.excerpt for s in sources))
        self.assertEqual(generate.call_args_list[1].args[0], "And Raspberry Swirl?")

    def test_rewrite_error_searches_original_question(self) -> None:
        conversation_id = self.client.post("/conversations", json={"title": "Rewrite"}).json()["id"]
        question = "What is the hex code for Raspberry Swirl?"
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.generate_answer", return_value="Answer."),
            mock.patch("backend.routes.qa.rewrite_question", side_effect=RuntimeError("timeout")),
        ):
            for _ in range(2):
                body = self.client.post(
                    "/qa/ask", json={"question": question, "conversation_id": conversation_id}
                ).json()
        self.assertTrue(body["found"])
        self.assertEqual(body["answer"], "Answer.")

    def test_azure_error_falls_back_to_top_passage(self) -> None:
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.generate_answer", side_effect=RuntimeError("429")),
        ):
            body = self.client.post(
                "/qa/ask", json={"question": "What is the hex code for Raspberry Swirl?"}
            ).json()
        self.assertTrue(body["found"])
        self.assertEqual(body["answer"], body["sources"][0]["excerpt"])
        self.assertIsNone(body["model"])

    def test_unknown_conversation_skips_azure(self) -> None:
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.generate_answer") as generate,
        ):
            response = self.client.post(
                "/qa/ask",
                json={
                    "question": "What is the hex code for Raspberry Swirl?",
                    "conversation_id": "00000000-0000-0000-0000-000000000000",
                },
            )
        self.assertEqual(response.status_code, 404)
        generate.assert_not_called()

    def test_no_passages_still_gets_a_chat_reply(self) -> None:
        reply = "Hello! I can help with Honeycrumb's brand, campaigns and more."
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.generate_answer", return_value=reply) as generate,
        ):
            body = self.client.post("/qa/ask", json={"question": "Hello!"}).json()
        self.assertEqual(generate.call_args.args[1], [])
        self.assertEqual(body["answer"], reply)
        self.assertEqual(body["sources"], [])
        self.assertTrue(body["found"])  # answered, so the UI shows a normal reply
        with session_scope() as db:
            log = db.scalar(
                select(models.QueryLog)
                .where(models.QueryLog.question == "Hello!")
                .order_by(models.QueryLog.id.desc())
            )
            assert log is not None
            self.assertFalse(log.found)  # the query log still records the retrieval miss


def _events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


class StreamApiTests(ApiTestCase):
    def test_streams_sources_deltas_and_done(self) -> None:
        conversation_id = self.client.post("/conversations", json={"title": "Stream"}).json()["id"]
        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch(
                "backend.routes.qa.stream_answer", return_value=iter(["Raspberry Swirl ", "is #E8456B [1]."])
            ),
        ):
            response = self.client.post(
                "/qa/ask/stream",
                json={
                    "question": "What is the hex code for Raspberry Swirl?",
                    "conversation_id": conversation_id,
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        events = _events(response)
        self.assertEqual([e["type"] for e in events], ["sources", "delta", "delta", "done"])
        self.assertIn("#E8456B", " ".join(s["excerpt"] for s in events[0]["sources"]))
        done = events[-1]
        self.assertEqual(done["answer"], "Raspberry Swirl is #E8456B [1].")
        self.assertEqual(done["model"], "gpt-test")
        self.assertTrue(done["found"])
        messages = self.client.get(f"/conversations/{conversation_id}").json()["messages"]
        self.assertEqual([m["text"] for m in messages], [
            "What is the hex code for Raspberry Swirl?",
            "Raspberry Swirl is #E8456B [1].",
        ])
        self.assertEqual(messages[1]["sources"], events[0]["sources"])

    def test_without_azure_streams_the_top_passage(self) -> None:
        events = _events(
            self.client.post(
                "/qa/ask/stream", json={"question": "What is the hex code for Raspberry Swirl?"}
            )
        )
        self.assertEqual([e["type"] for e in events], ["sources", "delta", "done"])
        self.assertEqual(events[1]["text"], events[0]["sources"][0]["excerpt"])
        self.assertIsNone(events[-1]["model"])

    def test_azure_failure_before_any_text_falls_back(self) -> None:
        def failing(*_args):
            raise RuntimeError("429")
            yield  # pragma: no cover - makes this a generator

        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.stream_answer", side_effect=failing),
        ):
            events = _events(
                self.client.post("/qa/ask/stream", json={"question": "What is the capital of France?"})
            )
        self.assertEqual(events[-1]["answer"], NO_ANSWER)
        self.assertIsNone(events[-1]["model"])
        self.assertFalse(events[-1]["found"])

    def test_azure_failure_mid_answer_keeps_text_and_notes_it(self) -> None:
        def partial(*_args):
            yield "Raspberry Swirl is"
            raise RuntimeError("connection reset")

        with (
            mock.patch("backend.routes.qa.chat_deployment", return_value="gpt-test"),
            mock.patch("backend.routes.qa.stream_answer", side_effect=partial),
        ):
            events = _events(
                self.client.post(
                    "/qa/ask/stream", json={"question": "What is the hex code for Raspberry Swirl?"}
                )
            )
        self.assertTrue(events[-1]["answer"].startswith("Raspberry Swirl is"))
        self.assertIn("cut off", events[-1]["answer"])
        self.assertEqual(events[-1]["model"], "gpt-test")

    def test_unknown_conversation_is_404_before_streaming(self) -> None:
        response = self.client.post(
            "/qa/ask/stream",
            json={"question": "Hi", "conversation_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertEqual(response.status_code, 404)


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
