"""Saving, loading and describing analyses and campaigns for the API and agents."""

import logging
import os
import uuid
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.agents.base import AgentError, AgentUnavailable, deployment
from backend.db.models import Analysis, Campaign, Survey, SurveyResponse
from backend.services.insights import KIND_LABELS, digest, summary_line

logger = logging.getLogger(__name__)
T = TypeVar("T")


def company_name() -> str:
    return os.getenv("COMPANY_NAME", "Honeycrumb Bakehouse").strip() or "Honeycrumb Bakehouse"


async def run_agent(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a blocking agent call off the event loop, mapping its errors to HTTP."""
    try:
        return await run_in_threadpool(fn, *args, **kwargs)
    except AgentUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except AgentError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error


def get_campaign(db: Session, campaign_id: uuid.UUID | None) -> Campaign | None:
    if campaign_id is None:
        return None
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Campaign not found")
    return campaign


def campaign_dict(campaign: Campaign) -> dict[str, Any]:
    return {
        "id": str(campaign.id),
        "name": campaign.name,
        "product": campaign.product,
        "objective": campaign.objective,
        "target_audience": campaign.target_audience,
        "positioning": campaign.positioning,
        "key_message": campaign.key_message,
        "budget": campaign.budget,
        "start_date": campaign.start_date.isoformat() if campaign.start_date else None,
        "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
        "channels": campaign.channels or [],
        "kpis": campaign.kpis or [],
        "status": campaign.status,
        "notes": campaign.notes,
    }


def campaign_context(campaign: Campaign | None) -> str:
    """One-line campaign description that agents use to focus recommendations."""
    if campaign is None:
        return ""
    parts = [campaign.name]
    if campaign.product:
        parts.append(f"product: {campaign.product}")
    if campaign.objective:
        parts.append(f"objective: {campaign.objective}")
    if campaign.target_audience:
        parts.append(f"audience: {campaign.target_audience}")
    if campaign.budget:
        parts.append(f"budget: ${campaign.budget:,.0f}")
    if campaign.start_date or campaign.end_date:
        parts.append(f"dates: {campaign.start_date or '?'} to {campaign.end_date or '?'}")
    return "; ".join(parts)[:1200]


def save_analysis(
    db: Session,
    *,
    kind: str,
    title: str,
    payload: dict[str, Any],
    request_input: dict[str, Any],
    campaign: Campaign | None = None,
    survey_id: uuid.UUID | None = None,
) -> Analysis:
    """Persist an agent result ({result, evidence, live_research})."""
    analysis = Analysis(
        kind=kind,
        title=title[:255],
        campaign_id=campaign.id if campaign else None,
        survey_id=survey_id,
        input=request_input,
        result=payload["result"],
        evidence=payload.get("evidence", []),
        live_research=bool(payload.get("live_research")),
        model=deployment(),
    )
    db.add(analysis)
    db.flush()
    db.refresh(analysis)
    logger.info("Saved %s analysis %s (%s)", kind, analysis.id, title)
    return analysis


def _campaign_names(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict(db.execute(select(Campaign.id, Campaign.name).where(Campaign.id.in_(ids))).all())


def summarize(db: Session, analyses: list[Analysis]) -> list[dict[str, Any]]:
    names = _campaign_names(db, {a.campaign_id for a in analyses if a.campaign_id})
    return [
        {
            "id": a.id,
            "kind": a.kind,
            "title": a.title,
            "campaign_id": a.campaign_id,
            "campaign_name": names.get(a.campaign_id) if a.campaign_id else None,
            "survey_id": a.survey_id,
            "live_research": a.live_research,
            "summary": summary_line(a.kind, a.result),
            "created_at": a.created_at,
        }
        for a in analyses
    ]


def full(db: Session, analysis: Analysis) -> dict[str, Any]:
    return {
        **summarize(db, [analysis])[0],
        "input": analysis.input,
        "result": analysis.result,
        "evidence": analysis.evidence,
        "model": analysis.model,
    }


def latest_insights(db: Session, campaign_id: uuid.UUID, kinds: tuple[str, ...]) -> list[Analysis]:
    """Most recent analysis of each kind linked to a campaign."""
    found = []
    for kind in kinds:
        analysis = db.scalar(
            select(Analysis)
            .where(Analysis.campaign_id == campaign_id, Analysis.kind == kind)
            .order_by(Analysis.created_at.desc())
            .limit(1)
        )
        if analysis:
            found.append(analysis)
    return found


def insight_digest(analysis: Analysis) -> dict[str, str]:
    return {
        "id": str(analysis.id),
        "kind": analysis.kind,
        "title": f"{KIND_LABELS[analysis.kind]}: {analysis.title} ({analysis.created_at:%Y-%m-%d})",
        "text": digest(analysis.kind, analysis.result, analysis.live_research),
    }


def response_counts(db: Session, survey_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not survey_ids:
        return {}
    rows = db.execute(
        select(SurveyResponse.survey_id, func.count())
        .where(SurveyResponse.survey_id.in_(survey_ids))
        .group_by(SurveyResponse.survey_id)
    ).all()
    return dict(rows)


def survey_summary(survey: Survey, count: int) -> dict[str, Any]:
    return {
        "id": survey.id,
        "title": survey.title,
        "status": survey.status,
        "campaign_id": survey.campaign_id,
        "response_count": count,
        "created_at": survey.created_at,
        "published_at": survey.published_at,
    }
