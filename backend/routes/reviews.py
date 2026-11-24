"""Customer reviews dataset and the Review Insights Agent.

Browse the dataset (products with statistics, filterable reviews, CSV export)
and run the AI agent that classifies sentiment and writes marketing insights.
"""

import csv
import io
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from backend.db.database import get_db
from backend.db.models import Product, Review, ReviewInsight
from backend.services import review_agent

router = APIRouter(prefix="/reviews", tags=["customer reviews"])

Sentiment = Literal["positive", "neutral", "negative", "unanalysed"]


@router.get("/overview")
def overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Dataset size and period, how much is analysed, and whether AI is available."""
    total = db.scalar(select(func.count()).select_from(Review)) or 0
    analysed = db.scalar(select(func.count()).select_from(Review).where(Review.sentiment.is_not(None))) or 0
    first, last = db.execute(select(func.min(Review.review_date), func.max(Review.review_date))).one()
    latest = db.scalar(select(ReviewInsight.created_at).order_by(ReviewInsight.created_at.desc()).limit(1))
    try:
        model = review_agent.deployment()
    except review_agent.AgentUnavailable:
        model = None
    return {
        "products": db.scalar(select(func.count()).select_from(Product)) or 0,
        "reviews": total,
        "analysed": analysed,
        "first_review": first,
        "last_review": last,
        "latest_insight_at": latest,
        "ai_configured": model is not None,
        "model": model,
    }


@router.get("/products")
def products(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Every product with review, sentiment, demand and seasonality statistics."""
    stats = review_agent.compute_stats(db)
    return {"months": stats["months"], "products": stats["products"], "rankings": stats["rankings"]}


def _filtered(
    product_id: int | None,
    sentiment: Sentiment | None,
    rating: int | None,
    q: str,
    date_from: date | None,
    date_to: date | None,
) -> Select:
    query = select(Review, Product.name).join(Product)
    if product_id:
        query = query.where(Review.product_id == product_id)
    if sentiment == "unanalysed":
        query = query.where(Review.sentiment.is_(None))
    elif sentiment:
        query = query.where(Review.sentiment == sentiment)
    if rating:
        query = query.where(Review.rating == rating)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(or_(Review.text.ilike(pattern), Review.customer.ilike(pattern), Review.city.ilike(pattern)))
    if date_from:
        query = query.where(Review.review_date >= date_from)
    if date_to:
        query = query.where(Review.review_date <= date_to)
    return query


def _row(review: Review, product_name: str) -> dict[str, Any]:
    return {
        "id": review.id,
        "product_id": review.product_id,
        "product": product_name,
        "customer": review.customer,
        "rating": review.rating,
        "text": review.text,
        "channel": review.channel,
        "city": review.city,
        "review_date": review.review_date,
        "sentiment": review.sentiment,
        "confidence": review.confidence,
        "topics": review.topics or [],
    }


@router.get("")
def list_reviews(
    product_id: int | None = None,
    sentiment: Sentiment | None = None,
    rating: int | None = Query(None, ge=1, le=5),
    q: str = Query("", max_length=200),
    date_from: date | None = None,
    date_to: date | None = None,
    sort: Literal["newest", "oldest", "rating_high", "rating_low"] = "newest",
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = _filtered(product_id, sentiment, rating, q, date_from, date_to)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = {
        "newest": (Review.review_date.desc(), Review.id.desc()),
        "oldest": (Review.review_date.asc(), Review.id.asc()),
        "rating_high": (Review.rating.desc(), Review.review_date.desc()),
        "rating_low": (Review.rating.asc(), Review.review_date.desc()),
    }[sort]
    rows = db.execute(query.order_by(*order).limit(limit).offset(offset)).all()
    return {"total": total, "items": [_row(review, name) for review, name in rows]}


@router.get("/export.csv")
def export_csv(
    product_id: int | None = None,
    sentiment: Sentiment | None = None,
    rating: int | None = Query(None, ge=1, le=5),
    q: str = Query("", max_length=200),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
) -> Response:
    """The (filtered) reviews as a CSV file."""
    rows = db.execute(
        _filtered(product_id, sentiment, rating, q, date_from, date_to).order_by(Review.review_date, Review.id)
    ).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "date", "product", "rating", "review", "customer", "city", "channel",
                     "sentiment", "confidence", "topics"])
    for review, name in rows:
        writer.writerow([review.id, review.review_date, name, review.rating, review.text, review.customer,
                         review.city, review.channel, review.sentiment or "", review.confidence or "",
                         "; ".join(review.topics or [])])
    return Response(
        "﻿" + buffer.getvalue(),  # BOM so Excel reads UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="honeycrumb-reviews.csv"'},
    )


class InsightRequest(BaseModel):
    reclassify: bool = False


@router.post("/insights", status_code=status.HTTP_201_CREATED)
async def run_insights(body: InsightRequest | None = None) -> dict[str, Any]:
    """Run the agent: classify new reviews, compute statistics, write the marketing report."""
    try:
        return await run_in_threadpool(review_agent.generate_insights, bool(body and body.reclassify))
    except review_agent.AgentUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except review_agent.AgentError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error


@router.get("/insights/latest")
def latest_insight(db: Session = Depends(get_db)) -> dict[str, Any]:
    insight = db.scalar(select(ReviewInsight).order_by(ReviewInsight.created_at.desc()).limit(1))
    if insight is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No AI analysis has been run yet")
    return review_agent.insight_out(insight)
