"""Campaigns: the hub that competitor, research, survey, sentiment and strategy work attaches to."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents import campaigns as campaign_agent
from backend.agents.strategy import campaign_updates
from backend.db.database import get_db
from backend.db.models import Analysis, Campaign, Survey
from backend.models.intelligence import (
    CampaignCreate,
    CampaignDetail,
    CampaignOut,
    CampaignUpdate,
)
from backend.services.analyses import (
    get_campaign,
    response_counts,
    run_agent,
    summarize,
    survey_summary,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)) -> list[Campaign]:
    return list(db.scalars(select(Campaign).order_by(Campaign.updated_at.desc())))


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)) -> Campaign:
    if body.start_date and body.end_date and body.end_date < body.start_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "End date is before start date")
    campaign = Campaign(**body.model_dump())
    db.add(campaign)
    db.flush()
    db.refresh(campaign)
    db.commit()  # before responding, so an immediate follow-up request sees it
    return campaign


@router.post("/import-proposals")
async def import_proposals() -> dict[str, Any]:
    """Campaigns found in the company documents, for the user to review and save."""
    return await run_agent(campaign_agent.propose)


@router.get("/{campaign_id}", response_model=CampaignDetail)
def campaign_detail(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    campaign = get_campaign(db, campaign_id)
    assert campaign is not None
    analyses = list(
        db.scalars(
            select(Analysis).where(Analysis.campaign_id == campaign_id).order_by(Analysis.created_at.desc())
        )
    )
    surveys = list(db.scalars(select(Survey).where(Survey.campaign_id == campaign_id).order_by(Survey.created_at.desc())))
    counts = response_counts(db, [s.id for s in surveys])
    return {
        **CampaignOut.model_validate(campaign).model_dump(),
        "analyses": summarize(db, analyses),
        "surveys": [survey_summary(s, counts.get(s.id, 0)) for s in surveys],
    }


@router.patch("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: uuid.UUID, body: CampaignUpdate, db: Session = Depends(get_db)) -> Campaign:
    campaign = get_campaign(db, campaign_id)
    assert campaign is not None
    nullable = {"budget", "start_date", "end_date"}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field not in nullable:
            if field in ("name", "status"):
                continue  # required fields can't be cleared
            value = [] if field in ("channels", "kpis") else ""
        setattr(campaign, field, value)
    if campaign.start_date and campaign.end_date and campaign.end_date < campaign.start_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "End date is before start date")
    db.flush()
    db.refresh(campaign)
    db.commit()
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign(campaign_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Deletes the campaign; its analyses and surveys are kept, unlinked."""
    db.delete(get_campaign(db, campaign_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{campaign_id}/apply-strategy/{analysis_id}")
def apply_strategy(campaign_id: uuid.UUID, analysis_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Fill the campaign's positioning, message, audience, objectives, channels and KPIs from a strategy."""
    campaign = get_campaign(db, campaign_id)
    assert campaign is not None
    analysis = db.get(Analysis, analysis_id)
    if analysis is None or analysis.kind != "strategy":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found")
    updates = campaign_updates(analysis.result)
    for field, value in updates.items():
        setattr(campaign, field, value)
    if campaign.status == "draft":
        campaign.status = "planned"
    db.flush()
    db.refresh(campaign)
    db.commit()
    return {"campaign": CampaignOut.model_validate(campaign).model_dump(mode="json"), "applied_fields": sorted(updates)}
