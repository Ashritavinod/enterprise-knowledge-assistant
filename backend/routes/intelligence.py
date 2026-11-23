"""AI marketing modules: competitor intelligence, market research, sentiment and strategy.

Each POST runs its specialist agent (see backend/services/operations.py) and
saves the result as an Analysis linked to the chosen campaign; saved analyses
can be listed, viewed and downloaded as Markdown or PDF reports.
"""

import io
import re
import uuid
from typing import Any, Literal

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents.base import AgentUnavailable, deployment
from backend.db.database import get_db
from backend.db.models import Analysis
from backend.models.intelligence import (
    AnalysisOut,
    AnalysisSummary,
    CompetitorRequest,
    ResearchRequest,
    SentimentRequest,
    StrategyRequest,
)
from backend.services import operations, reports, web_search
from backend.services.analyses import company_name, full, run_agent, summarize

router = APIRouter(tags=["marketing intelligence"])


@router.get("/ai/status")
def ai_status() -> dict[str, Any]:
    """Whether Azure OpenAI and live web search are configured (shown in the UI)."""
    try:
        model = deployment()
    except AgentUnavailable:
        model = None
    return {
        "ai_configured": model is not None,
        "model": model,
        "web_search": web_search.provider_status(),
        "company": company_name(),
    }


@router.post("/competitors/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def analyze_competitors(body: CompetitorRequest) -> dict[str, Any]:
    return await run_agent(
        operations.competitor_analysis,
        [c.model_dump() for c in body.competitors],
        body.industry,
        body.company,
        body.use_web,
        body.campaign_id,
        body.title,
    )


@router.post("/research/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def analyze_market(body: ResearchRequest) -> dict[str, Any]:
    return await run_agent(
        operations.market_research,
        body.industry,
        body.audience,
        body.products,
        body.market_notes,
        body.use_web,
        body.campaign_id,
        body.title,
    )


def _csv_texts(csv_text: str, column: str) -> tuple[list[str], str]:
    try:
        frame = pd.read_csv(io.StringIO(csv_text), dtype=str, on_bad_lines="skip")
    except Exception as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Could not read the CSV: {error}") from error
    if frame.empty:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The CSV has no rows.")
    if column:
        if column not in frame.columns:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Column {column!r} not found. Columns: {', '.join(map(str, frame.columns))}",
            )
    else:
        # Pick the column with the longest text on average (the feedback, not ids or dates).
        def average_length(name: Any) -> float:
            values = frame[name].dropna().astype(str)
            return float(values.str.len().mean()) if len(values) else 0.0

        column = str(max(frame.columns, key=average_length))
    return frame[column].dropna().astype(str).tolist(), column


@router.post("/sentiment/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def analyze_sentiment(body: SentimentRequest) -> dict[str, Any]:
    texts, column = list(body.texts), None
    if body.csv_text.strip():
        texts, column = _csv_texts(body.csv_text, body.csv_column.strip())
    return await run_agent(
        operations.sentiment_analysis, texts, body.source, body.campaign_id, body.title, column
    )


@router.post("/strategy/generate", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def generate_strategy(body: StrategyRequest) -> dict[str, Any]:
    return await run_agent(
        operations.marketing_strategy, body.campaign_id, body.analysis_ids, body.notes, body.title
    )


@router.get("/analyses", response_model=list[AnalysisSummary])
def list_analyses(
    kind: Literal["competitor", "research", "sentiment", "survey", "strategy"] | None = None,
    campaign_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    query = select(Analysis).order_by(Analysis.created_at.desc()).limit(limit)
    if kind:
        query = query.where(Analysis.kind == kind)
    if campaign_id:
        query = query.where(Analysis.campaign_id == campaign_id)
    return summarize(db, list(db.scalars(query)))


def _get(db: Session, analysis_id: uuid.UUID) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")
    return analysis


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return full(db, _get(db, analysis_id))


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(analysis_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get(db, analysis_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _filename(title: str, extension: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-").lower()[:80] or "report"
    return f"{slug}.{extension}"


@router.get("/analyses/{analysis_id}/report.md")
def report_markdown(analysis_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    data = full(db, _get(db, analysis_id))
    return Response(
        reports.to_markdown(data),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data["title"], "md")}"'},
    )


@router.get("/analyses/{analysis_id}/report.pdf")
def report_pdf(analysis_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    data = full(db, _get(db, analysis_id))
    return Response(
        reports.to_pdf(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{_filename(data["title"], "pdf")}"'},
    )
