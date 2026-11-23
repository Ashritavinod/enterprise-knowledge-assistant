"""Tests for campaigns and the AI marketing modules.

The model is replaced by ``FakeAI``, which returns canned structured outputs
per schema, so these tests are fast, free and deterministic. API tests use
the PostgreSQL database named by TEST_DATABASE_URL (dropped and recreated) and
are skipped when it is unreachable.
"""

import json
import os
import re
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

from dotenv import load_dotenv

load_dotenv()  # TEST_DATABASE_URL may be set in .env
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant_test",
)
os.environ["LLM_PROVIDER"] = "none"  # the chat assistant must not call Azure here

import logging  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.agents import sentiment, strategy, survey  # noqa: E402
from backend.agents.base import AgentError, AgentUnavailable, EvidenceSet, clean_points  # noqa: E402
from backend.db import models  # noqa: E402
from backend.db.database import check_db, get_engine  # noqa: E402
from backend.services import reports, web_search  # noqa: E402

logging.disable(logging.CRITICAL)

POSITIVE = ("love", "great", "best", "friendly", "fresh")
NEGATIVE = ("slow", "stale", "expensive", "crash", "rude", "tiny")


def _label(text: str) -> str:
    lower = text.lower()
    if any(w in lower for w in NEGATIVE):
        return "negative"
    if any(w in lower for w in POSITIVE):
        return "positive"
    return "neutral"


def fake_structured(system: str, user: str, schema_name: str, schema: dict, **_: object) -> dict:
    """Canned model output for each structured-output schema."""
    if schema_name == "feedback_labels":
        items = re.findall(r"^(\d+)\. (.*)$", user, flags=re.M)
        return {"items": [
            {"index": int(i), "sentiment": _label(t), "confidence": 0.9,
             "topics": ["price"] if "expensive" in t.lower() else ["service"]}
            for i, t in items
        ]}
    if schema_name == "sentiment_report":
        return {"overall_summary": "Mixed feedback.", "satisfaction_level": "mixed",
                "complaints": [{"issue": "Slow service", "topics": ["service"], "example": "Service was slow"}],
                "expectations": ["Faster service"], "strengths": [{"text": "Friendly staff", "topics": ["service"]}],
                "weaknesses": [{"text": "Prices", "topics": ["price"]}],
                "recommendations": [{"action": "Add staff at lunch", "rationale": "Slow service", "priority": "high", "topics": ["service"]}]}
    if schema_name == "survey_draft":
        return {"title": "Gelato survey", "description": "Two minutes.", "questions": [
            {"type": "multiple_choice", "text": "Favourite flavour?", "options": ["Mango", "Pistachio", "Mango"],
             "allow_multiple": False, "scale_min": 0, "scale_max": 0, "scale_min_label": "", "scale_max_label": "", "required": True},
            {"type": "rating", "text": "How likely to buy at $5.50?", "options": [], "allow_multiple": False,
             "scale_min": 1, "scale_max": 5, "scale_min_label": "Unlikely", "scale_max_label": "Likely", "required": True},
            {"type": "open_ended", "text": "Anything else?", "options": [], "allow_multiple": False,
             "scale_min": 0, "scale_max": 0, "scale_min_label": "", "scale_max_label": "", "required": False},
        ]}
    if schema_name == "survey_insights":
        return {"summary": "Mango leads.", "key_findings": [{"finding": "Mango is preferred", "question_ids": ["q1"]}],
                "preferences": ["Mango"], "expectations": ["Fair price"],
                "recommendations": [{"action": "Feature mango", "rationale": "Most chosen", "priority": "medium"}],
                "caveats": ["Small sample"]}
    if schema_name == "competitor_analysis":
        cell = lambda text, sources: {"text": text, "sources": sources}  # noqa: E731
        row = lambda name: {"competitor": name, "products_services": cell("Pastries", ["D1"]),  # noqa: E731
                            "pricing": cell("Not found in the available sources", []),
                            "features": cell("Delivery", ["U1", "X9"]), "marketing_strategy": cell("TikTok", ["D1"]),
                            "positioning": cell("Premium", ["D1"])}
        return {"summary": "Comparison.", "comparison": [row("Rival Co")],
                "competitor_profiles": [{"competitor": "Rival Co", "strengths": [cell("Fast", ["D1"])], "weaknesses": []}],
                "swot": {"strengths": [cell("Scratch baking", ["D1"])], "weaknesses": [cell("Prices", [])],
                         "opportunities": [], "threats": []},
                "market_gaps": [cell("Gluten-free", [])], "differentiation": [],
                "recommendations": [{"action": "Lead with freshness", "rationale": "x", "priority": "high", "sources": ["D1"]}],
                "data_limitations": ["Pricing unknown"]}
    if schema_name == "market_research":
        return {"summary": "Growing market.",
                "verified_findings": [{"text": "Documented fact", "sources": ["D1"]}, {"text": "Unsupported claim", "sources": []}],
                "trends": [], "customer_needs": [], "underserved_segments": [], "opportunities": [],
                "product_gaps": [], "hypotheses": [{"text": "Maybe", "rationale": "guess", "how_to_validate": "survey"}],
                "recommendations": [], "data_limitations": []}
    if schema_name == "marketing_strategy":
        point = {"text": "Fresh gelato", "sources": ["A1"]}
        return {"executive_summary": "Plan.", "target_audience": [{"segment": "Families", "description": "Parents", "rationale": "r", "sources": []}],
                "segmentation": [], "positioning": point, "usp": {"text": "Scratch-made", "sources": []},
                "objectives": [{"objective": "Grow sales", "metric": "Revenue", "target": "+10%", "sources": []}],
                "channels": [{"channel": "Instagram", "role": "Awareness", "budget_share_percent": 30, "rationale": "r", "sources": []},
                             {"channel": "Email", "role": "Retention", "budget_share_percent": 25, "rationale": "r", "sources": []}],
                "content_ideas": [], "promotions": [], "differentiation": [], "timeline": [], "action_plan": [],
                "kpis": [{"kpi": "Sales", "target": "+10%", "measurement": "POS"}], "risks": []}
    if schema_name == "campaign_import":
        base = {"product": "Gelato", "objective": "", "target_audience": "", "key_message": "", "budget": 420000.0,
                "start_date": "2026-06-15", "end_date": None, "channels": [], "kpis": [], "notes": "Tier 3"}
        return {"campaigns": [{**base, "name": "Summer Scoops", "sources": ["D1"]},
                              {**base, "name": "Invented campaign", "sources": []}]}
    raise AssertionError(f"Unexpected schema {schema_name}")


AGENT_MODULES = ("sentiment", "survey", "competitor", "research", "strategy", "campaigns")


def fake_ai(stack: ExitStack, structured=fake_structured) -> None:
    for name in AGENT_MODULES:
        stack.enter_context(mock.patch(f"backend.agents.{name}.call_structured", side_effect=structured))
    stack.enter_context(mock.patch("backend.services.analyses.deployment", return_value="gpt-test"))


# --- Unit tests -----------------------------------------------------------------


class EvidenceTests(unittest.TestCase):
    def test_clean_points_drops_unknown_ids_and_flags_inference(self) -> None:
        data = {"a": {"text": "x", "sources": ["D1", "X9", "D1"]}, "b": [{"text": "y", "sources": []}], "c": "plain"}
        cleaned = clean_points(data, {"D1"})
        self.assertEqual(cleaned["a"], {"text": "x", "sources": ["D1"], "verified": True})
        self.assertEqual(cleaned["b"][0]["verified"], False)
        self.assertEqual(cleaned["c"], "plain")

    def test_evidence_ids_and_deduplication(self) -> None:
        evidence = EvidenceSet()
        evidence.add_user("note", "Hello")
        evidence.add("web", "Page", "Text", url="https://a.example")
        evidence.add("web", "Same page", "Other text", url="https://a.example")
        evidence.add("document", "Doc", "Passage", document="A.pdf", page=1)
        self.assertEqual([e.id for e in evidence.items], ["U1", "W1", "D1"])
        self.assertIn("[W1] Page — https://a.example", evidence.for_prompt())


class SentimentStatsTests(unittest.TestCase):
    def test_counts_and_topics_are_computed_not_generated(self) -> None:
        items = [
            {"sentiment": "positive", "topics": ["service"]},
            {"sentiment": "negative", "topics": ["service", "price"]},
            {"sentiment": "negative", "topics": ["price"]},
            {"sentiment": "neutral", "topics": []},
        ]
        stats = sentiment.statistics(items)
        self.assertEqual(stats["counts"], {"positive": 1, "neutral": 1, "negative": 2})
        self.assertEqual(stats["percentages"]["negative"], 50.0)
        self.assertEqual(stats["net_score"], -25.0)
        self.assertEqual(stats["topics"][0], {"topic": "price", "mentions": 2, "positive": 0, "neutral": 0, "negative": 2})

    def test_unlabelled_items_default_to_neutral_zero_confidence(self) -> None:
        with mock.patch("backend.agents.sentiment.call_structured", return_value={"items": []}):
            items = sentiment.classify(["one", "two"])
        self.assertEqual([i["sentiment"] for i in items], ["neutral", "neutral"])
        self.assertEqual(items[0]["confidence"], 0.0)

    def test_texts_are_cleaned_and_capped(self) -> None:
        texts = sentiment.clean_texts(["  a  b ", "", "x" * 5000] + ["y"] * 600)
        self.assertEqual(texts[0], "a b")
        self.assertEqual(len(texts[1]), sentiment.MAX_ITEM_CHARS)
        self.assertEqual(len(texts), sentiment.MAX_ITEMS)


class SurveyLogicTests(unittest.TestCase):
    QUESTIONS = survey.normalise_questions([
        {"type": "multiple_choice", "text": "Flavour?", "options": ["A", "B"], "required": True},
        {"type": "multiple_choice", "text": "Toppings?", "options": ["X", "Y", "Z"], "allow_multiple": True, "required": False},
        {"type": "rating", "text": "Rate", "scale_min": 1, "scale_max": 5, "required": True},
        {"type": "open_ended", "text": "Why?", "required": False},
    ])

    def test_normalise_assigns_ids_and_validates(self) -> None:
        self.assertEqual([q["id"] for q in self.QUESTIONS], ["q1", "q2", "q3", "q4"])
        with self.assertRaises(ValueError):
            survey.normalise_questions([{"type": "multiple_choice", "text": "One option", "options": ["A"]}])
        with self.assertRaises(ValueError):
            survey.normalise_questions([{"type": "slider", "text": "x"}])
        rating = survey.normalise_questions([{"type": "rating", "text": "r", "scale_min": 5, "scale_max": 3}])[0]
        self.assertEqual((rating["scale_min"], rating["scale_max"]), (1, 5))

    def test_answer_validation(self) -> None:
        ok = survey.validate_answers(self.QUESTIONS, {"q1": "A", "q2": ["X", "Z"], "q3": 4, "q4": "  Good  "})
        self.assertEqual(ok, {"q1": "A", "q2": ["X", "Z"], "q3": 4, "q4": "Good"})
        for bad in ({"q3": 4}, {"q1": "C", "q3": 4}, {"q1": "A", "q3": 9}, {"q1": "A", "q3": 2.5},
                    {"q1": ["A", "B"], "q3": 3}, {"q1": "A", "q3": True}):
            with self.assertRaises(ValueError, msg=bad):
                survey.validate_answers(self.QUESTIONS, bad)

    def test_results_from_real_responses(self) -> None:
        stats = survey.results(self.QUESTIONS, [{"q1": "A", "q3": 5}, {"q1": "A", "q2": ["X"], "q3": 3, "q4": "Nice"}])
        q1, q2, q3, q4 = stats["questions"]
        self.assertEqual(stats["total_responses"], 2)
        self.assertEqual(q1["options"][0], {"option": "A", "count": 2, "percent": 100.0})
        self.assertEqual(q2["answered"], 1)
        self.assertEqual(q3["average"], 4.0)
        self.assertEqual(q3["distribution"][4], {"value": 5, "count": 1})
        self.assertEqual(q4["answers"], ["Nice"])

    def test_analysis_needs_real_responses(self) -> None:
        with self.assertRaises(ValueError):
            survey.analyse(self.QUESTIONS, [])


class StrategyLogicTests(unittest.TestCase):
    def test_budget_shares_rescaled_with_amounts(self) -> None:
        channels = [{"budget_share_percent": 30}, {"budget_share_percent": 25}]
        note = strategy._check_budget_shares(channels, 110000)
        self.assertIn("rescaled", note)
        self.assertEqual([c["budget_share_percent"] for c in channels], [54.5, 45.5])
        self.assertEqual([c["budget_amount"] for c in channels], [59950, 50050])

    def test_no_budget_means_no_split(self) -> None:
        channels = [{"budget_share_percent": 60}]
        strategy._check_budget_shares(channels, None)
        self.assertIsNone(channels[0]["budget_share_percent"])

    def test_campaign_updates(self) -> None:
        updates = strategy.campaign_updates({
            "positioning": {"text": "P"}, "usp": {"text": "U"},
            "target_audience": [{"segment": "Families", "description": "Parents"}],
            "objectives": [{"objective": "Grow", "metric": "Revenue", "target": "+10%"}],
            "channels": [{"channel": "Instagram"}], "kpis": [{"kpi": "Sales", "target": "+10%"}],
        })
        self.assertEqual(updates["key_message"], "U")
        self.assertEqual(updates["channels"], ["Instagram"])
        self.assertEqual(updates["kpis"], ["Sales: +10%"])
        self.assertEqual(updates["objective"], "Grow (Revenue: +10%)")


class WebSearchTests(unittest.TestCase):
    def test_not_configured_without_key(self) -> None:
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}):
            self.assertFalse(web_search.is_configured())
            with self.assertRaises(web_search.WebSearchError):
                web_search.search("x")

    def test_parses_results_and_strips_markup(self) -> None:
        payload = {"web": {"results": [
            {"title": "<strong>Rival</strong> &amp; Co", "url": "https://rival.example", "description": "Cakes <b>from</b> $4", "age": "2 days ago"},
            {"title": "No url"},
        ]}}
        response = SimpleNamespace(status_code=200, json=lambda: payload)
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k"}), \
                mock.patch("backend.services.web_search.httpx.get", return_value=response) as get:
            results = web_search.search("rival cakes", count=3)
        self.assertEqual(get.call_args.kwargs["headers"]["X-Subscription-Token"], "k")
        self.assertEqual(len(results), 1)
        self.assertEqual((results[0].title, results[0].description, results[0].age), ("Rival & Co", "Cakes from $4", "2 days ago"))

    def test_http_error_raises(self) -> None:
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k"}), \
                mock.patch("backend.services.web_search.httpx.get", return_value=SimpleNamespace(status_code=401)):
            with self.assertRaises(web_search.WebSearchError):
                web_search.search("x")


class ReportTests(unittest.TestCase):
    ANALYSIS = {
        "kind": "competitor", "title": "Us vs Rival", "created_at": "2026-11-23T10:00:00", "campaign_name": "Launch",
        "model": "gpt-test", "live_research": False,
        "result": clean_points(fake_structured("", "", "competitor_analysis", {}), {"D1", "U1"}),
        "evidence": [{"id": "D1", "kind": "document", "title": "Strategy p.2", "text": "t", "url": None, "document": "S.pdf",
                      "page": 2, "section": "Competitors", "retrieved_at": "2026-11-23T10:00:00", "published": None}],
    }

    def test_markdown_marks_sources_and_inference(self) -> None:
        markdown = reports.to_markdown(self.ANALYSIS)
        self.assertIn("# Us vs Rival", markdown)
        self.assertIn("Delivery [U1]", markdown)  # X9 dropped
        self.assertIn("Prices *(AI inference)*", markdown)
        self.assertIn("Live web research: **not performed**", markdown)
        self.assertIn("**D1** Strategy p.2 — S.pdf, page 2 (Competitors); retrieved 2026-11-23", markdown)

    def test_pdf_and_html_conversion(self) -> None:
        self.assertTrue(reports.to_pdf(self.ANALYSIS).startswith(b"%PDF"))
        html = reports.markdown_to_html("## Title\n- **Bold** item\n| A | B |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<h2>Title</h2>", html)
        self.assertIn("<li><b>Bold</b> item</li>", html)
        self.assertIn("<th>A</th>", html)
        self.assertIn("<td>2</td>", html)


# --- API tests --------------------------------------------------------------------


class IntelligenceApiTests(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        if not check_db():
            raise unittest.SkipTest(f"PostgreSQL test database unreachable ({os.environ['DATABASE_URL']})")
        from backend.main import app

        models.Base.metadata.drop_all(get_engine())
        cls.client = TestClient(app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def setUp(self) -> None:
        self.stack = ExitStack()
        fake_ai(self.stack)
        self.stack.enter_context(mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": ""}))
        self.addCleanup(self.stack.close)

    def campaign(self, **fields: object) -> dict:
        body = {"name": "Summer launch", "product": "Gelato", "budget": 110000, "start_date": "2026-06-15",
                "end_date": "2026-08-31", **fields}
        response = self.client.post("/campaigns", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    # Campaigns

    def test_campaign_crud_and_validation(self) -> None:
        c = self.campaign(channels=["Instagram", " Instagram ", ""])
        self.assertEqual(c["channels"], ["Instagram"])
        self.assertIn(c["id"], [x["id"] for x in self.client.get("/campaigns").json()])
        patched = self.client.patch(f"/campaigns/{c['id']}", json={"status": "active", "budget": None, "notes": None})
        self.assertEqual(patched.status_code, 200)
        self.assertEqual((patched.json()["status"], patched.json()["budget"], patched.json()["notes"]), ("active", None, ""))
        bad_dates = self.client.patch(f"/campaigns/{c['id']}", json={"end_date": "2026-01-01"})
        self.assertEqual(bad_dates.status_code, 422)
        self.assertEqual(self.client.post("/campaigns", json={"name": ""}).status_code, 422)
        detail = self.client.get(f"/campaigns/{c['id']}").json()
        self.assertEqual((detail["analyses"], detail["surveys"]), ([], []))
        self.assertEqual(self.client.delete(f"/campaigns/{c['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/campaigns/{c['id']}").status_code, 404)

    def test_import_proposals_keep_only_sourced_campaigns(self) -> None:
        proposals = self.client.post("/campaigns/import-proposals").json()["campaigns"]
        self.assertEqual([p["name"] for p in proposals], ["Summer Scoops"])
        self.assertEqual(proposals[0]["origin_sources"][0]["kind"], "document")

    # Sentiment

    def test_sentiment_from_texts_links_campaign_and_reports(self) -> None:
        c = self.campaign()
        response = self.client.post("/sentiment/analyze", json={
            "texts": ["Love the croissants", "Service was slow", "Too expensive", "It was fine", "  "],
            "campaign_id": c["id"]})
        self.assertEqual(response.status_code, 201, response.text)
        a = response.json()
        self.assertEqual(a["result"]["stats"]["counts"], {"positive": 1, "neutral": 1, "negative": 2})
        self.assertEqual(a["input"]["item_count"], 4)
        self.assertEqual((a["campaign_id"], a["model"]), (c["id"], "gpt-test"))
        self.assertEqual(self.client.get(f"/campaigns/{c['id']}").json()["analyses"][0]["id"], a["id"])
        self.assertTrue(self.client.get(f"/analyses/{a['id']}/report.pdf").content.startswith(b"%PDF"))
        markdown = self.client.get(f"/analyses/{a['id']}/report.md")
        self.assertIn("4 items analysed", markdown.text)
        self.assertIn("attachment;", markdown.headers["content-disposition"])

    def test_sentiment_from_csv_picks_text_column(self) -> None:
        csv_text = "id,date,review\n1,2026-05-01,Love the gelato\n2,2026-05-02,Service was slow at lunch\n"
        a = self.client.post("/sentiment/analyze", json={"csv_text": csv_text, "source": "csv"}).json()
        self.assertEqual((a["input"]["csv_column"], a["input"]["item_count"]), ("review", 2))
        missing = self.client.post("/sentiment/analyze", json={"csv_text": csv_text, "csv_column": "comment"})
        self.assertEqual(missing.status_code, 422)
        self.assertIn("Columns: id, date, review", missing.json()["detail"])
        self.assertEqual(self.client.post("/sentiment/analyze", json={"texts": []}).status_code, 422)

    # Competitor and research

    def test_competitor_analysis_cites_evidence_without_live_research(self) -> None:
        a = self.client.post("/competitors/analyze", json={
            "competitors": [{"name": "Rival Co", "notes": "Delivery-first, cupcakes from $3.95"}],
            "industry": "bakery", "use_web": True}).json()
        row = a["result"]["comparison"][0]
        self.assertEqual(row["features"]["sources"], ["U1"])  # X9 never existed
        self.assertFalse(a["result"]["swot"]["weaknesses"][0]["verified"])
        self.assertFalse(a["live_research"])
        self.assertTrue(a["result"]["data_limitations"][0].startswith("No live web research was performed"))
        self.assertEqual(a["evidence"][0]["kind"], "user")

    def test_competitor_uses_web_search_when_configured(self) -> None:
        result = web_search.WebResult("Rival menu", "https://rival.example/menu", "Cupcakes $3.95", "1 week ago")
        with mock.patch.dict(os.environ, {"BRAVE_SEARCH_API_KEY": "k"}), \
                mock.patch("backend.services.web_search.search", return_value=[result]) as search:
            a = self.client.post("/competitors/analyze", json={"competitors": [{"name": "Rival Co"}]}).json()
        self.assertTrue(search.called)
        self.assertTrue(a["live_research"])
        web = [e for e in a["evidence"] if e["kind"] == "web"]
        self.assertEqual((web[0]["id"], web[0]["url"], web[0]["published"]), ("W1", "https://rival.example/menu", "1 week ago"))
        self.assertTrue(web[0]["retrieved_at"])

    def test_research_moves_unsupported_findings_to_hypotheses(self) -> None:
        a = self.client.post("/research/analyze", json={"industry": "bakery", "use_web": False}).json()
        r = a["result"]
        self.assertEqual([p["text"] for p in r["verified_findings"]], ["Documented fact"])
        self.assertIn("Unsupported claim", [h["text"] for h in r["hypotheses"]])
        self.assertEqual(self.client.post("/research/analyze", json={}).status_code, 422)

    # Strategy

    def test_strategy_uses_campaign_insights_and_applies(self) -> None:
        c = self.campaign()
        insight = self.client.post("/sentiment/analyze", json={"texts": ["Service was slow"], "campaign_id": c["id"]}).json()
        s = self.client.post("/strategy/generate", json={"campaign_id": c["id"]})
        self.assertEqual(s.status_code, 201, s.text)
        s = s.json()
        self.assertEqual(s["input"]["insights_used"], [insight["id"]])
        self.assertEqual(s["result"]["insight_gaps"], ["competitor", "research", "survey"])
        self.assertEqual(sum(ch["budget_share_percent"] for ch in s["result"]["channels"]), 100)
        self.assertIn("rescaled", s["result"]["budget_note"])
        self.assertEqual(s["result"]["positioning"]["sources"], ["A1"])
        applied = self.client.post(f"/campaigns/{c['id']}/apply-strategy/{s['id']}").json()
        self.assertEqual(applied["campaign"]["positioning"], "Fresh gelato")
        self.assertEqual(applied["campaign"]["channels"], ["Instagram", "Email"])
        self.assertEqual(applied["campaign"]["status"], "planned")
        wrong = self.client.post(f"/campaigns/{c['id']}/apply-strategy/{insight['id']}")
        self.assertEqual(wrong.status_code, 404)

    # Surveys

    def test_survey_lifecycle_with_real_responses(self) -> None:
        c = self.campaign()
        s = self.client.post("/surveys/generate", json={
            "product": "Gelato", "objective": "Pick flavours", "audience": "Parents", "question_count": 3,
            "campaign_id": c["id"]}).json()
        self.assertEqual(s["status"], "draft")
        self.assertEqual(s["questions"][0]["options"], ["Mango", "Pistachio"])  # duplicate removed
        sid = s["id"]
        self.assertEqual(self.client.get(f"/public/surveys/{sid}").status_code, 404)  # draft is private
        self.assertEqual(self.client.post(f"/surveys/{sid}/analyze").status_code, 422)  # no responses

        edited = [{**q, "text": q["text"] + "!"} for q in s["questions"]]
        self.assertEqual(self.client.put(f"/surveys/{sid}", json={"questions": edited}).status_code, 200)
        self.assertEqual(self.client.post(f"/surveys/{sid}/publish").json()["status"], "published")
        self.assertEqual(self.client.put(f"/surveys/{sid}", json={"questions": edited}).status_code, 409)

        public = self.client.get(f"/public/surveys/{sid}").json()
        self.assertTrue(public["accepting_responses"])
        self.assertNotIn("objective", public)
        submit = lambda answers: self.client.post(f"/public/surveys/{sid}/responses", json={"answers": answers})  # noqa: E731
        self.assertEqual(submit({"q1": "Mango", "q2": 5, "q3": "Bigger cups"}).status_code, 201)
        self.assertEqual(submit({"q1": "Mango", "q2": 2}).status_code, 201)
        self.assertEqual(submit({"q1": "Lemon", "q2": 2}).status_code, 422)
        self.assertEqual(submit({"q2": 2}).status_code, 422)
        self.assertEqual(submit({"q1": "Mango", "q2": 6}).status_code, 422)

        results = self.client.get(f"/surveys/{sid}/results").json()
        self.assertEqual(results["total_responses"], 2)
        self.assertEqual(results["questions"][0]["options"][0]["count"], 2)
        self.assertEqual(results["questions"][1]["average"], 3.5)
        export = self.client.get(f"/surveys/{sid}/responses.csv").text.splitlines()
        self.assertEqual(len(export), 3)
        self.assertIn("Favourite flavour?!", export[0])

        analysis = self.client.post(f"/surveys/{sid}/analyze").json()
        self.assertEqual((analysis["kind"], analysis["survey_id"]), ("survey", sid))
        self.assertTrue(analysis["result"]["small_sample"])
        self.assertEqual(analysis["result"]["open_ended_sentiment"]["stats"]["total"], 1)
        self.assertEqual(self.client.get("/surveys", params={"campaign_id": c["id"]}).json()[0]["response_count"], 2)

        self.client.post(f"/surveys/{sid}/close")
        self.assertFalse(self.client.get(f"/public/surveys/{sid}").json()["accepting_responses"])
        self.assertEqual(submit({"q1": "Mango", "q2": 2}).status_code, 409)
        self.assertEqual(self.client.delete(f"/surveys/{sid}").status_code, 204)

    # Errors and status

    def test_ai_errors_map_to_http_status(self) -> None:
        with mock.patch("backend.agents.sentiment.call_structured", side_effect=AgentUnavailable("not configured")):
            self.assertEqual(self.client.post("/sentiment/analyze", json={"texts": ["x"]}).status_code, 503)
        with mock.patch("backend.agents.sentiment.call_structured", side_effect=AgentError("rate limited")):
            response = self.client.post("/sentiment/analyze", json={"texts": ["x"]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "rate limited")
        missing = self.client.post("/sentiment/analyze", json={"texts": ["x"], "campaign_id": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(missing.status_code, 404)

    def test_ai_status_reports_configuration(self) -> None:
        status = self.client.get("/ai/status").json()
        self.assertEqual(status["web_search"], {"provider": None, "configured": False})
        self.assertTrue(status["company"])

    def test_analyses_listing_and_delete(self) -> None:
        a = self.client.post("/sentiment/analyze", json={"texts": ["Love it"]}).json()
        listed = self.client.get("/analyses", params={"kind": "sentiment"}).json()
        self.assertIn(a["id"], [x["id"] for x in listed])
        self.assertTrue(all(x["kind"] == "sentiment" for x in listed))
        self.assertEqual(self.client.delete(f"/analyses/{a['id']}").status_code, 204)
        self.assertEqual(self.client.get(f"/analyses/{a['id']}").status_code, 404)

    # Supervisor

    def test_supervisor_runs_specialists_and_streams_steps(self) -> None:
        c = self.campaign()

        def tool_call(call_id: str, name: str, args: dict) -> SimpleNamespace:
            return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))

        replies = iter([
            SimpleNamespace(content="", tool_calls=[
                tool_call("t1", "search_documents", {"query": "brand colours"}),
                tool_call("t2", "analyze_feedback", {"texts": ["Service was slow"], "campaign_id": c["id"]}),
                tool_call("t3", "generate_strategy", {"campaign_id": "not-a-uuid"}),
            ]),
            SimpleNamespace(content="## Findings\nService is slow.", tool_calls=None),
        ])
        sent_messages: list = []

        def create(**kwargs: object) -> SimpleNamespace:
            sent_messages.append(kwargs["messages"])
            return SimpleNamespace(choices=[SimpleNamespace(message=next(replies))])

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        client.with_options = lambda **_: client
        with mock.patch("backend.agents.supervisor.get_client", return_value=client), \
                mock.patch("backend.agents.supervisor.deployment", return_value="gpt-test"), \
                mock.patch("backend.routes.agent.deployment", return_value="gpt-test"):
            response = self.client.post("/agent/chat", json={"message": "Analyse feedback", "campaign_id": c["id"]})
        events = [json.loads(line) for line in response.text.splitlines()]
        steps = [e for e in events if e["type"] == "step"]
        self.assertEqual(sum(1 for e in steps if e["status"] == "running"), 3)
        done = {e["action"]: e for e in steps if e["status"] != "running"}
        self.assertEqual(done["analyze_feedback"]["agent"], "Sentiment Analysis Agent")
        self.assertEqual(done["analyze_feedback"]["kind"], "sentiment")
        self.assertEqual(done["generate_strategy"]["status"], "error")
        self.assertEqual(events[-1], {"type": "answer", "text": "## Findings\nService is slow."})
        self.assertIn(c["id"], sent_messages[0][0]["content"])  # campaign context in the system prompt
        tool_results = [m for m in sent_messages[1] if m["role"] == "tool"]
        self.assertEqual(len(tool_results), 3)
        linked = self.client.get(f"/campaigns/{c['id']}").json()["analyses"]
        self.assertEqual(linked[0]["id"], done["analyze_feedback"]["analysis_id"])

    def test_supervisor_unavailable_without_azure(self) -> None:
        with mock.patch("backend.routes.agent.deployment", side_effect=AgentUnavailable("Azure OpenAI is not configured.")):
            response = self.client.post("/agent/chat", json={"message": "hi"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
