"""Tests for the Brand Compliance Checker and the Campaign Copywriter.

The model is replaced by fakes, so these tests are fast, free and deterministic.
API tests use the PostgreSQL database named by TEST_DATABASE_URL and are
skipped when it is unreachable.
"""

import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

from dotenv import load_dotenv

load_dotenv()
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant_test",
)
os.environ["LLM_PROVIDER"] = "none"  # nothing here may call Azure
os.environ["REVIEW_FEED_SECONDS"] = "0"

import logging  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.db import models  # noqa: E402
from backend.db.database import check_db, get_engine  # noqa: E402
from backend.models.schemas import Source  # noqa: E402
from backend.services import brand_checker, copywriter  # noqa: E402

logging.disable(logging.CRITICAL)


def passage(text: str) -> Source:
    return Source(document="BrandGuidelines.pdf", page=2, section="", excerpt=text, score=1.0)


PASSAGES = [
    passage('Our tagline is "Life\'s sweeter by the crumb." Do not rewrite or translate the tagline.'),
    passage("Never call a product \"healthy\". Limit emojis to two per social caption and none in subject lines."),
    passage("Use no more than three hashtags per post."),
    passage("Subject lines must be 45 characters or fewer."),
    passage("Hero banners use one headline of eight words or fewer."),
    passage("Honey Gold | #F5A623 | Primary"),
    passage("No banned words: healthy, guilt-free, skinny, sinful."),
]


def categories(issues: list[dict]) -> list[str]:
    return sorted(i["category"] for i in issues)


class RuleTests(unittest.TestCase):
    def test_clean_copy_passes(self) -> None:
        text = "Flaky, golden and still warm: our honey butter croissant. Life's sweeter by the crumb. #HoneycrumbMoments"
        self.assertEqual(brand_checker.rule_issues(text, "social", PASSAGES), [])

    def test_banned_words_cite_the_checklist(self) -> None:
        issues = brand_checker.rule_issues("A skinny, Guilt free and HEALTHY cake. Sinful!", "menu", PASSAGES)
        self.assertEqual({i["quote"].lower() for i in issues}, {"skinny", "guilt free", "healthy", "sinful"})
        self.assertTrue(all(i["severity"] == "must_fix" and i["citations"] == [7] for i in issues))
        self.assertEqual(brand_checker.rule_issues("Skinnydip? Unhealthy? Fine.", "menu", PASSAGES), [])

    def test_social_limits(self) -> None:
        issues = brand_checker.rule_issues("Treat time 😍🎉🔥 #a #b #c #d", "social", PASSAGES)
        self.assertEqual(categories(issues), ["Emoji limit", "Hashtag limit"])
        hashtags = next(i for i in issues if i["category"] == "Hashtag limit")
        self.assertEqual(hashtags["citations"], [3])
        # The same copy is fine on a channel without those limits.
        self.assertEqual(brand_checker.rule_issues("Treat time 😍🎉🔥 #a #b #c #d", "other", PASSAGES), [])

    def test_email_subject(self) -> None:
        long = "Subject: Our holiday cookie tins are back and better than ever before\n\nHello!"
        self.assertEqual(categories(brand_checker.rule_issues(long, "email", PASSAGES)), ["Subject line length"])
        self.assertEqual(brand_checker.split_subject(long)[0], "Our holiday cookie tins are back and better than ever before")
        issues = brand_checker.rule_issues("Hello!", "email", PASSAGES, subject="Cookies 🍪")
        self.assertEqual(categories(issues), ["Emoji in subject line"])

    def test_banner_headline(self) -> None:
        issues = brand_checker.rule_issues("Our brand new seasonal croissant is finally here for you\nOrder now", "website", PASSAGES)
        self.assertEqual(categories(issues), ["Headline length"])

    def test_colours(self) -> None:
        issues = brand_checker.rule_issues("Use #FF0000 and #f5a623 and #FFF.", "other", PASSAGES)
        self.assertEqual({i["quote"] for i in issues}, {"#FF0000", "#FFF"})
        # Hashtags and numbers that look like hex codes are not colours.
        self.assertEqual(brand_checker.rule_issues("A #decade of baking. Review #410.", "other", PASSAGES), [])

    def test_tagline(self) -> None:
        issues = brand_checker.rule_issues("Life is sweeter by every crumb.", "other", PASSAGES)
        self.assertEqual(categories(issues), ["Tagline changed"])
        self.assertEqual(issues[0]["citations"], [1])
        self.assertEqual(brand_checker.rule_issues("Life’s sweeter by the crumb.", "other", PASSAGES), [])

    def test_score_and_verdict(self) -> None:
        must = {"severity": "must_fix", "category": "Banned word"}
        should = {"severity": "should_fix", "category": "Tone"}
        self.assertEqual((brand_checker.score([]), brand_checker.verdict([])), (100, "on_brand"))
        self.assertEqual((brand_checker.score([should]), brand_checker.verdict([should])), (90, "minor_changes"))
        self.assertEqual((brand_checker.score([must, should]), brand_checker.verdict([must, should])), (65, "needs_changes"))
        # Each category costs once, at its worst severity: repeats don't pile up.
        self.assertEqual(brand_checker.score([must] * 5 + [should] * 3), 65)
        self.assertEqual(brand_checker.score([{**should, "category": "tone"}, {**must, "category": "Tone"}]), 75)
        many = [{"severity": "must_fix", "category": f"c{n}"} for n in range(5)]
        self.assertEqual(brand_checker.score(many), 0)

    def test_looks_like_copy(self) -> None:
        for text in ("W7I3OsycUkHW02E", "😍🎉", "  1234 #FF0000 ", ""):
            self.assertFalse(brand_checker.looks_like_copy(text), text)
        for text in ("Hi", "Fresh croissants!", "Life’s sweeter", "Don't miss it"):
            self.assertTrue(brand_checker.looks_like_copy(text), text)


CLEAN = {"reviewable": True, "summary": "Lovely.", "strengths": ["Warm."], "issues": []}


class CheckCopyTests(unittest.TestCase):
    def run_check(self, review: dict, rewrites: list[dict] | None = None, rewrite_review: dict | None = None,
                  **kwargs) -> dict:
        """`review` answers the draft check, `rewrite_review` (default: clean) the checks of each rewrite."""
        rewrites = list(rewrites or [{"subject": "", "revised": "Golden and flaky."}])

        def fake(system: str, user: str, name: str, schema: dict, temperature: float = 0.2) -> dict:
            self.assertEqual(temperature, 0)
            if name == "brand_rewrite":
                return rewrites.pop(0) if len(rewrites) > 1 else rewrites[0]
            body = kwargs["text"].split("\n\n")[-1].strip()  # the draft without any subject line
            is_draft = f"{body}\n>>>" in user
            return {"reviewable": True, **review} if is_draft else rewrite_review or CLEAN

        with mock.patch.object(brand_checker, "guideline_passages", return_value=PASSAGES), \
                mock.patch.object(brand_checker, "deployment", return_value="fake-model"), \
                mock.patch.object(brand_checker, "call_structured", side_effect=fake) as calls:
            result = brand_checker.check_copy(**kwargs)
        result["calls"] = [c.args[2] for c in calls.call_args_list]
        return result

    def test_ai_issues_are_cleaned_and_merged(self) -> None:
        def ai(quote: str, problem: str, citations: list[int], category: str = "tone") -> dict:
            return {"severity": "should_fix", "category": category, "quote": quote, "problem": problem,
                    "fix": "Reword it.", "citations": citations}

        review = {
            "summary": "Mostly off-brand.",
            "strengths": ["Names the product."],
            "issues": [
                ai("HURRY", "Pressure tactics.", [2, 99]),  # keeps citation 2 only
                ai("not in the draft", "Invented quote.", [3]),  # quote blanked
                ai("Free", "Uncited.", []),  # dropped
                ai("", "Says healthy, a banned word.", [7]),  # duplicate of a rule
                ai("", "Missing sensory words.", [2], category="writing_style"),
            ],
        }
        result = self.run_check(review, text="HURRY! Our healthy croissant.", channel="social")
        self.assertEqual(result["calls"], ["brand_check", "brand_rewrite", "brand_check"])
        ai_issues = [i for i in result["issues"] if i["source"] == "ai"]
        self.assertEqual([(i["quote"], i["citations"]) for i in ai_issues],
                         [("HURRY", [2]), ("", [3]), ("", [2])])
        self.assertEqual(ai_issues[2]["category"], "Writing style")
        self.assertEqual(result["issues"][0]["category"], "Banned word")  # must_fix sorts first
        # Banned word 25 + Tone 10 (two issues, charged once) + Writing style 10.
        self.assertEqual((result["verdict"], result["score"], result["model"]), ("needs_changes", 55, "fake-model"))
        self.assertEqual((result["revised"], result["revised_flags"], result["revised_score"]), ("Golden and flaky.", [], 100))

    def test_rewrite_gets_the_full_check_and_a_second_try(self) -> None:
        tone = {"severity": "should_fix", "category": "Tone", "quote": "", "problem": "Pushy.", "fix": "Soften.",
                "citations": [2]}
        rewrites = [{"subject": "Short", "revised": "So skinny!"}, {"subject": "Short", "revised": "Golden cookies."}]
        result = self.run_check({**CLEAN, "issues": [tone]}, rewrites,
                                text="Subject: Cookies are here\n\nA healthy cookie.", channel="email")
        self.assertEqual(result["calls"], ["brand_check", "brand_rewrite", "brand_check", "brand_rewrite", "brand_check"])
        self.assertEqual(result["revised"], "Subject: Short\n\nGolden cookies.")
        self.assertEqual((result["revised_flags"], result["revised_score"]), ([], 100))

    def test_rewrite_no_better_than_the_draft_is_not_offered(self) -> None:
        tone = {"severity": "should_fix", "category": "Tone", "quote": "", "problem": "Pushy.", "fix": "Soften.",
                "citations": [2]}
        result = self.run_check({**CLEAN, "issues": [tone]}, rewrite_review={**CLEAN, "issues": [tone]},
                                text="Buy our cookies now.", channel="social")
        self.assertEqual(result["calls"], ["brand_check", "brand_rewrite", "brand_check", "brand_rewrite", "brand_check"])
        self.assertEqual((result["score"], result["revised"], result["revised_score"]), (90, "", None))

    def test_no_rewrite_when_on_brand(self) -> None:
        result = self.run_check(CLEAN, text="Flaky and golden.", channel="menu")
        self.assertEqual((result["verdict"], result["revised"], result["calls"]), ("on_brand", "", ["brand_check"]))

    def test_gibberish_is_not_reviewed(self) -> None:
        result = self.run_check(CLEAN, text="W7I3OsycUkHW02E", channel="social")
        self.assertEqual((result["verdict"], result["score"], result["revised"], result["calls"]),
                         ("not_reviewable", None, "", []))
        # Words the heuristic lets through can still be judged not reviewable by the model.
        result = self.run_check({**CLEAN, "reviewable": False, "summary": "Nothing to review."}, text="asdf qwer", channel="social")
        self.assertEqual((result["verdict"], result["score"], result["summary"], result["calls"]),
                         ("not_reviewable", None, "Nothing to review.", ["brand_check"]))

    def test_rules_still_run_without_ai(self) -> None:
        with mock.patch.object(brand_checker, "guideline_passages", return_value=PASSAGES):
            result = brand_checker.check_copy("A sinful brownie.", "menu")
        self.assertIsNone(result["model"])
        self.assertEqual(categories(result["issues"]), ["Banned word"])
        self.assertIn("needs Azure OpenAI", result["summary"])


def review(id_: int, text: str, rating: int = 5) -> SimpleNamespace:
    return SimpleNamespace(id=id_, text=text, rating=rating, customer="Ana P.", city="Portland",
                           review_date=date(2026, 11, 20))


REVIEWS = {
    1: review(1, "Best holiday cookie tin I've had in a long time. The gingerbread ones were amazing!"),
    2: review(2, "Flaky, buttery and still warm. Worth the line."),
}


def variant(body: str, quotes: list[dict], headline: str = "Holiday cookie tin") -> dict:
    return {"angle": "favourite", "headline": headline, "preheader": "", "body": body, "cta": "Order today",
            "hashtags": [], "quotes": quotes, "citations": [1]}


class QuoteVerificationTests(unittest.TestCase):
    def test_verbatim_quotes_are_kept_with_original_wording(self) -> None:
        v = copywriter.verify_variant(
            variant('Guests say "the gingerbread ones were amazing" (review #1).',
                    [{"review_id": 1, "excerpt": "the gingerbread ones were amazing"}]),
            REVIEWS,
        )
        self.assertEqual(v["quotes"][0]["excerpt"], "The gingerbread ones were amazing!")
        self.assertEqual(v["quotes"][0]["customer"], "Ana P.")
        self.assertEqual(v["body"], "Guests say “The gingerbread ones were amazing!”.")

    def test_unverifiable_quotes_are_removed(self) -> None:
        v = copywriter.verify_variant(
            variant('"Flaky, buttery and still warm."',
                    [{"review_id": 2, "excerpt": "Flaky, buttery and still warm."},
                     {"review_id": 2, "excerpt": "the best croissant in Oregon"},  # not in review 2
                     {"review_id": 99, "excerpt": "Flaky, buttery"}]),  # unknown review
            REVIEWS,
        )
        self.assertEqual([q["review_id"] for q in v["quotes"]], [2])

    def test_variant_with_an_invented_quote_in_the_copy_is_dropped(self) -> None:
        bad = variant('Customers call it "the best cookie tin on the West Coast".',
                      [{"review_id": 1, "excerpt": "Best holiday cookie tin"}])
        self.assertIsNone(copywriter.verify_variant(bad, REVIEWS))

    def test_tagline_and_short_quoted_words_are_allowed(self) -> None:
        ok = variant('Our "famous" tin. "Life\'s sweeter by the crumb."',
                     [{"review_id": 1, "excerpt": "Best holiday cookie tin"}])
        self.assertIsNotNone(copywriter.verify_variant(ok, REVIEWS))

    def test_review_references_are_stripped(self) -> None:
        self.assertEqual(copywriter.REVIEW_REF.sub("", 'Loved it." [Review 400]. Yes (410) and (review #3)!'),
                         'Loved it.". Yes and!')


class BrandCopyApiTests(unittest.TestCase):
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

    def product_id(self, name: str) -> int:
        return next(p["id"] for p in self.client.get("/reviews/products").json()["products"] if p["name"] == name)

    def test_brand_check_without_ai(self) -> None:
        response = self.client.post("/brand/check", json={"text": "Our skinny cookie 😍🎉🔥", "channel": "social"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(categories(data["issues"]), ["Banned word", "Emoji limit"])
        self.assertIsNone(data["model"])
        passages = data["passages"]
        self.assertTrue(passages and passages[0]["document"] == "BrandGuidelines.pdf")
        for issue in data["issues"]:
            cited = passages[issue["citations"][0] - 1]["excerpt"]
            self.assertTrue("banned" in cited.lower() or "emoji" in cited.lower(), cited)
        self.assertEqual(self.client.post("/brand/check", json={"text": "  "}).status_code, 422)
        self.assertEqual(self.client.post("/brand/check", json={"text": "Hi", "channel": "fax"}).status_code, 422)

    def test_copy_needs_ai(self) -> None:
        response = self.client.post("/copy/generate", json={"product_id": self.product_id("Yule Log"), "channel": "email"})
        self.assertEqual(response.status_code, 503)

    def test_copy_generation_keeps_only_verified_variants(self) -> None:
        product_id = self.product_id("Holiday Cookie Tin")
        seen = {}

        def fake(system: str, user: str, name: str, schema: dict, temperature: float = 0.2) -> dict:
            line = next(line for line in user.splitlines() if line.startswith("["))
            review_id = int(line[1:line.index("]")])
            text = line.split(") ", 1)[1]
            words = " ".join(text.split()[:5])
            seen["offered"] = user.count("\n[") + 1
            return {"variants": [
                {**variant(f'"{words}" Life\'s sweeter by the crumb. Healthy too!',
                           [{"review_id": review_id, "excerpt": words}]), "hashtags": ["Cookies", "#cookies", "x y"]},
                variant('"An invented rave about the tin"', [{"review_id": review_id, "excerpt": words}]),
                variant("No quotes at all.", []),
            ]}

        with mock.patch.object(copywriter, "deployment", return_value="fake-model"), \
                mock.patch.object(copywriter, "call_structured", side_effect=fake):
            response = self.client.post("/copy/generate",
                                        json={"product_id": product_id, "channel": "instagram", "notes": "gifting"})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["variants"]), 1)
        v = data["variants"][0]
        self.assertEqual(v["hashtags"], ["#Cookies", "#xy"])
        self.assertEqual(categories(v["brand_flags"]), ["Banned word"])
        self.assertEqual(data["availability_note"],
                         "Holiday Cookie Tin is only on sale Nov–Dec. Schedule this copy for that window.")
        self.assertGreater(seen["offered"], 1)
        self.assertEqual(data["passages"][0]["document"], "BrandGuidelines.pdf")

    def test_copy_errors(self) -> None:
        with mock.patch.object(copywriter, "deployment", return_value="fake-model"):
            self.assertEqual(self.client.post("/copy/generate", json={"product_id": 999999, "channel": "email"}).status_code, 404)
            self.assertEqual(self.client.post("/copy/generate", json={"product_id": 1, "channel": "fax"}).status_code, 422)
            with mock.patch.object(copywriter, "call_structured", return_value={"variants": [variant('"Made up words here"', [])]}):
                response = self.client.post("/copy/generate", json={"product_id": self.product_id("Yule Log"), "channel": "email"})
        self.assertEqual(response.status_code, 502)

    def test_emails_always_carry_the_tagline(self) -> None:
        def fake(system: str, user: str, name: str, schema: dict, temperature: float = 0.2) -> dict:
            line = next(line for line in user.splitlines() if line.startswith("["))
            review_id, text = int(line[1:line.index("]")]), line.split(") ", 1)[1]
            words = " ".join(text.split()[:4])
            return {"variants": [variant(f'"{words}"', [{"review_id": review_id, "excerpt": words}])]}

        with mock.patch.object(copywriter, "deployment", return_value="fake-model"), \
                mock.patch.object(copywriter, "call_structured", side_effect=fake):
            data = self.client.post("/copy/generate", json={"product_id": self.product_id("Yule Log"), "channel": "email"}).json()
        self.assertTrue(data["variants"][0]["body"].endswith("\n\nLife's sweeter by the crumb."))


if __name__ == "__main__":
    unittest.main()
