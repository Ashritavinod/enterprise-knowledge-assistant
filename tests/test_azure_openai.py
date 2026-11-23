"""Unit tests for the Azure OpenAI (Microsoft Foundry) integration.

No network calls: the OpenAI client is replaced with a fake.
"""

import os
import unittest
from types import SimpleNamespace
from unittest import mock

from backend.models.schemas import Source
from backend.services import azure_openai
from backend.services.vector_store import AzureOpenAIEmbeddings

CONFIGURED = {
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
    "AZURE_OPENAI_API_KEY": "test-key",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-test",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "embed-test",
    "LLM_PROVIDER": "auto",
}
UNSET = {name: "" for name in CONFIGURED}


def _source(number: int) -> Source:
    return Source(
        document=f"Doc{number}.pdf",
        page=number,
        section=f"Section {number}",
        excerpt=f"Excerpt {number}.",
        score=0.9,
    )


class FakeClient:
    def __init__(self, answer: str = "Generated [1].") -> None:
        self.chat_calls: list[dict] = []
        self.embedding_calls: list[dict] = []
        self.answer = answer
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))
        self.embeddings = SimpleNamespace(create=self._embed)

    def _chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        message = SimpleNamespace(content=self.answer)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def _embed(self, **kwargs):
        self.embedding_calls.append(kwargs)
        # Return items out of order to check they are re-sorted by index.
        data = [
            SimpleNamespace(index=i, embedding=[float(i), 1.0])
            for i in range(len(kwargs["input"]))
        ]
        return SimpleNamespace(data=list(reversed(data)))


class BaseUrlTests(unittest.TestCase):
    def test_appends_v1_path(self) -> None:
        for endpoint, expected in [
            ("https://r.openai.azure.com", "https://r.openai.azure.com/openai/v1/"),
            ("https://r.openai.azure.com/", "https://r.openai.azure.com/openai/v1/"),
            ("https://r.services.ai.azure.com/openai", "https://r.services.ai.azure.com/openai/v1/"),
            ("https://r.openai.azure.com/openai/v1/", "https://r.openai.azure.com/openai/v1/"),
        ]:
            self.assertEqual(azure_openai._base_url(endpoint), expected, endpoint)


class ChatDeploymentTests(unittest.TestCase):
    def test_auto_uses_azure_only_when_configured(self) -> None:
        with mock.patch.dict(os.environ, CONFIGURED):
            self.assertEqual(azure_openai.chat_deployment(), "gpt-test")
        with mock.patch.dict(os.environ, {**CONFIGURED, "AZURE_OPENAI_API_KEY": ""}):
            self.assertIsNone(azure_openai.chat_deployment())

    def test_none_turns_generation_off(self) -> None:
        with mock.patch.dict(os.environ, {**CONFIGURED, "LLM_PROVIDER": "none"}):
            self.assertIsNone(azure_openai.chat_deployment())

    def test_azure_requires_settings(self) -> None:
        with mock.patch.dict(os.environ, {**UNSET, "LLM_PROVIDER": "azure"}):
            with self.assertRaises(azure_openai.AzureOpenAINotConfigured):
                azure_openai.chat_deployment()

    def test_unknown_provider_is_rejected(self) -> None:
        with mock.patch.dict(os.environ, {**CONFIGURED, "LLM_PROVIDER": "gemini"}):
            with self.assertRaises(ValueError):
                azure_openai.chat_deployment()


class GenerateAnswerTests(unittest.TestCase):
    def test_sends_numbered_passages_and_history(self) -> None:
        client = FakeClient()
        with (
            mock.patch.dict(os.environ, CONFIGURED),
            mock.patch.object(azure_openai, "get_client", return_value=client),
        ):
            answer = azure_openai.generate_answer(
                "What colour?",
                [_source(1), _source(2)],
                [("user", "Earlier question"), ("assistant", "Earlier answer")],
            )
        self.assertEqual(answer, "Generated [1].")
        call = client.chat_calls[0]
        self.assertEqual(call["model"], "gpt-test")
        roles = [m["role"] for m in call["messages"]]
        self.assertEqual(roles, ["system", "user", "assistant", "user"])
        prompt = call["messages"][-1]["content"]
        self.assertIn("[1] Doc1.pdf, page 1, section: Section 1\nExcerpt 1.", prompt)
        self.assertIn("[2] Doc2.pdf, page 2", prompt)
        self.assertTrue(prompt.endswith("Question: What colour?"))

    def test_returns_none_without_sources_or_config(self) -> None:
        client = FakeClient()
        with mock.patch.object(azure_openai, "get_client", return_value=client):
            with mock.patch.dict(os.environ, CONFIGURED):
                self.assertIsNone(azure_openai.generate_answer("Q?", []))
            with mock.patch.dict(os.environ, UNSET):
                self.assertIsNone(azure_openai.generate_answer("Q?", [_source(1)]))
        self.assertEqual(client.chat_calls, [])

    def test_blank_completion_returns_none(self) -> None:
        with (
            mock.patch.dict(os.environ, CONFIGURED),
            mock.patch.object(azure_openai, "get_client", return_value=FakeClient("  ")),
        ):
            self.assertIsNone(azure_openai.generate_answer("Q?", [_source(1)]))


class RewriteQuestionTests(unittest.TestCase):
    def test_rewrites_with_transcript(self) -> None:
        client = FakeClient('"What colour is used for call-to-action buttons?"')
        history = [("user", "What are the brand colors?"), ("assistant", "Honey Gold, ...")]
        with (
            mock.patch.dict(os.environ, CONFIGURED),
            mock.patch.object(azure_openai, "get_client", return_value=client),
        ):
            rewritten = azure_openai.rewrite_question("Which for CTA buttons?", history)
        self.assertEqual(rewritten, "What colour is used for call-to-action buttons?")
        prompt = client.chat_calls[0]["messages"][-1]["content"]
        self.assertIn("user: What are the brand colors?\nassistant: Honey Gold, ...", prompt)
        self.assertTrue(prompt.endswith("Latest question: Which for CTA buttons?"))

    def test_no_history_or_config_returns_question(self) -> None:
        client = FakeClient("ignored")
        with mock.patch.object(azure_openai, "get_client", return_value=client):
            with mock.patch.dict(os.environ, CONFIGURED):
                self.assertEqual(azure_openai.rewrite_question("Q?", []), "Q?")
            with mock.patch.dict(os.environ, UNSET):
                self.assertEqual(azure_openai.rewrite_question("Q?", [("user", "x")]), "Q?")
        self.assertEqual(client.chat_calls, [])


class AzureEmbeddingsTests(unittest.TestCase):
    def test_batches_orders_and_normalizes(self) -> None:
        client = FakeClient()
        with (
            mock.patch.dict(os.environ, CONFIGURED),
            mock.patch.object(azure_openai, "get_client", return_value=client),
        ):
            embeddings = AzureOpenAIEmbeddings()
            embeddings.batch_size = 2
            vectors = embeddings.embed_documents(["a", "b", "c"])
        self.assertEqual(embeddings.model_id, "azure-openai:embed-test")
        self.assertEqual([len(call["input"]) for call in client.embedding_calls], [2, 1])
        half = 2 ** -0.5
        expected = [[0.0, 1.0], [half, half], [0.0, 1.0]]  # batches [a, b], [c]
        for vector, want in zip(vectors, expected, strict=True):
            for value, target in zip(vector, want, strict=True):
                self.assertAlmostEqual(value, target)
        self.assertEqual(client.embedding_calls[0]["model"], "embed-test")


if __name__ == "__main__":
    unittest.main()
