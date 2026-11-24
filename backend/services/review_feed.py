"""Simulated live review feed: adds a realistic new customer review every so often.

Lets the demo show "Run again" picking up fresh reviews. New reviews reuse the
dataset's product specs and wording, are dated today, and only cover products
that are on the menu this month (no gelato reviews in November).

Turned on by REVIEW_FEED_SECONDS (seconds between reviews; unset or 0 = off).
"""

import asyncio
import logging
import os
import random
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.database import session_scope
from backend.db.models import Product, Review
from backend.services import review_dataset as ds

logger = logging.getLogger(__name__)


def feed_interval() -> float:
    """Seconds between simulated reviews; 0 means the feed is off."""
    raw = os.getenv("REVIEW_FEED_SECONDS", "").strip()
    try:
        seconds = float(raw) if raw else 0.0
    except ValueError:
        logger.warning("Ignoring REVIEW_FEED_SECONDS=%r: not a number", raw)
        return 0.0
    return max(seconds, 0.0)


def _months_since_start(day: date) -> int:
    return (day.year - ds.FIRST_MONTH.year) * 12 + day.month - ds.FIRST_MONTH.month


def new_review(rng: random.Random, today: date) -> dict:
    """One review row (with `sku`) for a product on sale today, picked in proportion to demand."""
    month = today.replace(day=1)
    index = _months_since_start(month)
    weights = [ds._demand(spec, month, index) for spec in ds.PRODUCTS]
    spec = rng.choices(ds.PRODUCTS, weights=weights)[0]
    rating = ds._rating(rng, spec.rating)
    return {
        "sku": spec.sku,
        "customer": f"{rng.choice(ds.FIRST_NAMES)} {rng.choice('ABCDEFGHJKLMNPRSTW')}.",
        "rating": rating,
        "text": ds._review_text(rng, spec, rating, month),
        "channel": rng.choice(ds.CHANNELS),
        "city": rng.choice(ds.CITIES),
        "review_date": today,
    }


def add_reviews(db: Session, count: int = 1, rng: random.Random | None = None) -> list[Review]:
    """Insert `count` new unanalysed reviews dated today and return them."""
    rng = rng or random.Random()
    ids = {sku: product_id for sku, product_id in db.execute(select(Product.sku, Product.id))}
    added = []
    for _ in range(count):
        row = new_review(rng, date.today())
        product_id = ids.get(row.pop("sku"))
        if product_id is None:  # catalog not seeded
            continue
        review = Review(product_id=product_id, topics=[], **row)
        db.add(review)
        added.append(review)
    db.flush()
    return added


def _add_one() -> None:
    with session_scope() as db:
        for review in add_reviews(db):
            logger.info("Review feed: added review #%d (%d stars)", review.id, review.rating)


async def run_feed(interval: float) -> None:
    """Add one review every `interval` seconds until cancelled."""
    logger.info("Review feed on: a new customer review every %g seconds", interval)
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(_add_one)
        except Exception:  # noqa: BLE001 - keep the feed alive through a DB hiccup
            logger.exception("Review feed could not add a review")
