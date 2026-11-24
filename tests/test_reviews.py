"""Tests for the customer reviews dataset and the Review Insights Agent.

The model is replaced by a fake that labels reviews from their star rating
and returns a canned report, so these tests are fast, free and deterministic.
API tests use the PostgreSQL database named by TEST_DATABASE_URL (dropped and
recreated) and are skipped when it is unreachable.
"""

import csv
import io
import os
import random
import re
import unittest
from datetime import date
from unittest import mock

from dotenv import load_dotenv

load_dotenv()  # TEST_DATABASE_URL may be set in .env
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_assistant_test",
)
os.environ["LLM_PROVIDER"] = "none"  # nothing here may call Azure
os.environ["REVIEW_FEED_SECONDS"] = "0"  # tests add reviews explicitly instead

import logging  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from backend.db import models  # noqa: E402
from backend.db.database import check_db, get_engine  # noqa: E402
from backend.services import review_agent, review_dataset, review_feed  # noqa: E402

logging.disable(logging.CRITICAL)


def fake_structured(system: str, user: str, name: str, schema: dict) -> dict:
    if name == "review_sentiment":
        items = re.findall(r"^\[(\d+)\] \((\d) stars\)", user, flags=re.M)
        labels = {5: "positive", 4: "positive", 3: "neutral"}
        return {"items": [
            {"id": int(i), "sentiment": labels.get(int(stars), "negative"), "confidence": 0.9,
             "topics": ["Taste", " ", "price"]}
            for i, stars in items
        ]}
    if name == "review_insights":
        first_id = int(re.search(r'"id": (\d+)', user).group(1))
        return {
            "summary": "Customers love the croissant.",
            "best_reviewed": [{"product": "Honey Butter Croissant", "why": "Loved", "review_ids": [first_id, 99999999]}],
            "in_demand": [{"product": "Honey Butter Croissant", "why": "Most units"},
                          {"product": "Mystery Pie", "why": "Invented"}],
            "seasonal": [{"product": "Holiday Cookie Tin", "season": "Nov–Dec", "why": "Holiday"}],
            "needs_attention": [{"product": "Almond Orange Cake (GF)", "issue": "Dry", "fix": "New recipe",
                                 "review_ids": []}],
            "christmas": {
                "headline": "A Honeycrumb Christmas",
                "hero_products": [{"product": "Holiday Cookie Tin", "why": "Gift", "message": "Share the joy",
                                   "ideas": ["Instagram"], "review_ids": []}],
                "bundles": ["Holiday Cookie Tin + Corporate Gift Box", "Holiday Cookie Tin + Summer Scoops Gelato"],
                "timing": "Start November 1",
                "avoid": [{"product": "Summer Scoops Gelato", "why": "Not on sale"}],
            },
            "recommendations": [{"action": "Push cookie tins", "rationale": "Top holiday seller", "priority": "high"}],
        }
    raise AssertionError(name)


# --- Unit tests -------------------------------------------------------------------


class DatasetTests(unittest.TestCase):
    def test_generation_is_deterministic_and_matches_the_catalog(self) -> None:
        products, sales, reviews = review_dataset.generate()
        self.assertEqual(review_dataset.generate()[2], reviews)
        self.assertEqual(len(products), len(review_dataset.PRODUCTS))
        self.assertGreater(len(reviews), 500)
        self.assertTrue(all(1 <= r["rating"] <= 5 for r in reviews))
        months = review_dataset.months()
        self.assertEqual((months[0], months[-1]), (date(2024, 11, 1), date(2026, 10, 1)))

    def test_seasonal_items_only_sell_in_season(self) -> None:
        _, sales, reviews = review_dataset.generate()
        tin = {s["month"].month for s in sales if s["sku"] == "SEA-002"}
        self.assertEqual(tin, {11, 12})
        gelato = sorted(s["month"] for s in sales if s["sku"] == "SEA-004")
        self.assertEqual(gelato[0], date(2026, 6, 1))  # launched June 2026
        self.assertTrue(all(r["review_date"] >= date(2026, 6, 15) for r in reviews if r["sku"] == "SEA-004"))

    def test_review_text_keeps_proper_nouns(self) -> None:
        texts = " ".join(r["text"] for r in review_dataset.generate()[2])
        self.assertNotIn("christmas", texts)
        self.assertIn("Christmas", texts)


class ReviewFeedTests(unittest.TestCase):
    def test_new_reviews_only_cover_products_on_sale(self) -> None:
        rng = random.Random(7)
        november = {review_feed.new_review(rng, date(2026, 11, 24))["sku"] for _ in range(300)}
        self.assertIn("SEA-002", november)  # holiday cookie tin is on sale
        self.assertNotIn("SEA-004", november)  # summer gelato is not
        self.assertNotIn("SEA-005", november)  # nor Valentine's cookies
        row = review_feed.new_review(rng, date(2026, 11, 24))
        self.assertEqual(row["review_date"], date(2026, 11, 24))
        self.assertTrue(1 <= row["rating"] <= 5 and row["text"])

    def test_feed_interval_setting(self) -> None:
        for raw, expected in (("", 0.0), ("0", 0.0), ("90", 90.0), ("soon", 0.0), ("-5", 0.0)):
            with mock.patch.dict(os.environ, {"REVIEW_FEED_SECONDS": raw}):
                self.assertEqual(review_feed.feed_interval(), expected)


class SeasonalityTests(unittest.TestCase):
    def test_month_range_labels(self) -> None:
        self.assertEqual(review_agent._month_range_label([11, 12]), "Nov–Dec")
        self.assertEqual(review_agent._month_range_label([12, 1, 2]), "Dec–Feb")
        self.assertEqual(review_agent._month_range_label([2, 5]), "Feb, May")
        self.assertEqual(review_agent._month_range_label(list(range(1, 13))), "Year-round")

    def test_seasonality_profiles(self) -> None:
        flat = {date(2025, m, 1): 100 for m in range(1, 13)}
        self.assertEqual(review_agent.seasonality(flat)["season"], "Year-round")
        holiday = {date(2025, m, 1): (500 if m == 12 else 250 if m == 11 else 60) for m in range(1, 13)}
        profile = review_agent.seasonality(holiday)
        self.assertTrue(profile["seasonal"])
        self.assertEqual(profile["season"], "Nov–Dec")
        limited = {date(2025, 9, 1): 10, date(2025, 10, 1): 12, date(2025, 11, 1): 9, date(2025, 12, 1): 0}
        self.assertEqual(review_agent.seasonality(limited)["season"], "Sep–Nov")


# --- API tests --------------------------------------------------------------------


class ReviewsApiTests(unittest.TestCase):
    client: TestClient

    @classmethod
    def setUpClass(cls) -> None:
        if not check_db():
            raise unittest.SkipTest(f"PostgreSQL test database unreachable ({os.environ['DATABASE_URL']})")
        from backend.main import app

        models.Base.metadata.drop_all(get_engine())
        cls.client = TestClient(app)
        cls.client.__enter__()  # lifespan creates the tables and seeds the dataset

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)

    def product_id(self, name: str) -> int:
        return next(p["id"] for p in self.client.get("/reviews/products").json()["products"] if p["name"] == name)

    def test_dataset_is_seeded_once(self) -> None:
        overview = self.client.get("/reviews/overview").json()
        expected = len(review_dataset.generate()[2])
        self.assertEqual((overview["products"], overview["reviews"]), (17, expected))
        self.assertFalse(overview["ai_configured"])
        from backend.db.database import session_scope

        with session_scope() as db:
            self.assertFalse(review_dataset.seed(db))  # already there

    def test_product_statistics(self) -> None:
        data = self.client.get("/reviews/products").json()
        self.assertEqual(len(data["months"]), 24)
        products = {p["name"]: p for p in data["products"]}
        tin, croissant, gelato = products["Holiday Cookie Tin"], products["Honey Butter Croissant"], products["Summer Scoops Gelato"]
        self.assertEqual((tin["seasonal"], tin["season"]), (True, "Nov–Dec"))
        self.assertEqual(tin["holiday_share_pct"], 100.0)
        home = products["Bake-at-Home Croissant 6-Pack"]
        self.assertEqual((home["seasonal"], home["season"]), (True, "Nov–Dec"))  # year-round, but peaks
        christmas = [p["name"] for p in data["products"] if p["id"] in data["rankings"]["christmas_sellers"]]
        self.assertIn("Holiday Cookie Tin", christmas)
        self.assertNotIn("Pumpkin Spice Croissant", christmas)  # sells in November, not December
        self.assertEqual(croissant["season"], "Year-round")
        self.assertIsNone(gelato["growth_pct"])  # new in 2026: no prior year
        self.assertLess(products["Almond Orange Cake (GF)"]["growth_pct"], -10)
        self.assertEqual(data["rankings"]["most_units"][0], croissant["id"])
        self.assertEqual(len(croissant["monthly_units"]), 24)

    def test_review_filters_and_paging(self) -> None:
        pid = self.product_id("Yule Log")
        page = self.client.get("/reviews", params={"product_id": pid, "limit": 5}).json()
        self.assertEqual(len(page["items"]), 5)
        self.assertTrue(all(r["product"] == "Yule Log" for r in page["items"]))
        dates = [r["review_date"] for r in page["items"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        rest = self.client.get("/reviews", params={"product_id": pid, "limit": 200, "offset": 5}).json()
        self.assertEqual(len(rest["items"]), page["total"] - 5)
        ones = self.client.get("/reviews", params={"rating": 1, "limit": 200}).json()
        self.assertTrue(all(r["rating"] == 1 for r in ones["items"]))
        found = self.client.get("/reviews", params={"q": "gingerbread"}).json()
        self.assertTrue(found["total"] > 0 and all("gingerbread" in r["text"].lower() for r in found["items"]))
        self.assertEqual(self.client.get("/reviews", params={"rating": 6}).status_code, 422)

    def test_csv_export(self) -> None:
        response = self.client.get("/reviews/export.csv", params={"product_id": self.product_id("Yule Log")})
        self.assertIn("attachment;", response.headers["content-disposition"])
        rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))
        self.assertEqual(rows[0][:4], ["id", "date", "product", "rating"])
        self.assertTrue(all(row[2] == "Yule Log" for row in rows[1:]))

    def test_insights_need_azure(self) -> None:
        self.assertEqual(self.client.post("/reviews/insights").status_code, 503)

    def test_agent_classifies_and_writes_a_checked_report(self) -> None:
        with mock.patch("backend.services.review_agent.call_structured", side_effect=fake_structured), \
                mock.patch("backend.services.review_agent.deployment", return_value="gpt-test"):
            response = self.client.post("/reviews/insights", json={})
            again = self.client.post("/reviews/insights", json={})
        self.assertEqual(response.status_code, 201, response.text)
        data = response.json()
        total = self.client.get("/reviews/overview").json()["reviews"]
        self.assertEqual(data["classified"], {"classified": total, "skipped": 0})
        self.assertEqual(again.json()["classified"]["classified"], 0)  # only new reviews are classified

        report = data["report"]
        self.assertEqual([x["product"] for x in report["in_demand"]], ["Honey Butter Croissant"])  # invented product dropped
        self.assertNotIn(99999999, report["best_reviewed"][0]["review_ids"])  # invented review id dropped
        # A bundle containing a product the report says not to feature is removed.
        self.assertEqual(report["christmas"]["bundles"], ["Holiday Cookie Tin + Corporate Gift Box"])
        cited = report["best_reviewed"][0]["review_ids"][0]
        self.assertIn(str(cited), report["quotes"])
        self.assertEqual(data["stats"]["totals"]["analysed"], total)

        reviews = self.client.get("/reviews", params={"rating": 5, "limit": 3}).json()["items"]
        self.assertEqual(reviews[0]["sentiment"], "positive")
        self.assertEqual(reviews[0]["topics"], ["taste", "price"])
        products = {p["name"]: p for p in self.client.get("/reviews/products").json()["products"]}
        self.assertIsNotNone(products["Yule Log"]["net_sentiment"])
        self.assertEqual(self.client.get("/reviews/insights/latest").json()["id"], again.json()["id"])

    def test_simulated_reviews_await_the_next_run(self) -> None:
        before = self.client.get("/reviews/overview").json()
        added = self.client.post("/reviews/simulate", params={"count": 3})
        self.assertEqual(added.status_code, 201, added.text)
        ids = [r["id"] for r in added.json()["added"]]
        self.assertEqual(len(ids), 3)
        after = self.client.get("/reviews/overview").json()
        self.assertEqual(after["reviews"], before["reviews"] + 3)
        self.assertEqual(after["reviews"] - after["analysed"], before["reviews"] - before["analysed"] + 3)
        self.assertIsNone(after["feed_seconds"])  # the live feed is off in tests
        newest = self.client.get("/reviews", params={"sentiment": "unanalysed", "limit": 200}).json()["items"]
        self.assertTrue(set(ids) <= {r["id"] for r in newest})
        self.assertEqual(self.client.post("/reviews/simulate", params={"count": 0}).status_code, 422)
        # Leave the dataset as the other tests expect it.
        from backend.db.database import session_scope

        with session_scope() as db:
            db.execute(models.Review.__table__.delete().where(models.Review.id.in_(ids)))


if __name__ == "__main__":
    unittest.main()
