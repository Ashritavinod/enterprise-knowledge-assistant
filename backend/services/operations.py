"""Run a specialist agent end to end: read the campaign, call the agent, save the result.

Shared by the module API routes and the supervisor agent so both produce the
same saved analyses. These are blocking functions: call them from a thread
(the routes use ``run_agent``). Database sessions are short-lived and never
held open while the model is working.
"""

import uuid
from datetime import date
from typing import Any

from fastapi import HTTPException, status

from backend.agents import competitor, research, sentiment, strategy
from backend.agents import survey as survey_agent
from backend.agents.base import EvidenceSet
from backend.db.database import session_scope
from backend.db.models import Analysis, Survey
from backend.services.analyses import (
    campaign_context,
    campaign_dict,
    company_name,
    full,
    get_campaign,
    insight_digest,
    latest_insights,
    response_counts,
    save_analysis,
    survey_summary,
)

INSIGHT_KINDS = ("competitor", "research", "survey", "sentiment")


def _context(campaign_id: uuid.UUID | None) -> str:
    with session_scope() as db:
        return campaign_context(get_campaign(db, campaign_id))


def _save(kind: str, title: str, payload: dict[str, Any], request_input: dict[str, Any],
          campaign_id: uuid.UUID | None, survey_id: uuid.UUID | None = None) -> dict[str, Any]:
    with session_scope() as db:
        analysis = save_analysis(db, kind=kind, title=title, payload=payload, request_input=request_input,
                                 campaign=get_campaign(db, campaign_id), survey_id=survey_id)
        return full(db, analysis)


def competitor_analysis(
    competitors: list[dict[str, str]],
    industry: str = "",
    company: str = "",
    use_web: bool = True,
    campaign_id: uuid.UUID | None = None,
    title: str = "",
) -> dict[str, Any]:
    context = _context(campaign_id)
    company = company.strip() or company_name()
    competitors = [
        {"name": c["name"].strip(), "website": (c.get("website") or "").strip(), "notes": (c.get("notes") or "").strip()}
        for c in competitors
        if c.get("name", "").strip()
    ]
    payload = competitor.analyse(company, industry, competitors, use_web, context)
    title = title.strip() or f"{company} vs {', '.join(c['name'] for c in competitors)}"
    request_input = {"competitors": competitors, "industry": industry, "company": company, "use_web": use_web,
                     "campaign_id": str(campaign_id) if campaign_id else None}
    return _save("competitor", title[:255], payload, request_input, campaign_id)


def market_research(
    industry: str = "",
    audience: str = "",
    products: str = "",
    market_notes: str = "",
    use_web: bool = True,
    campaign_id: uuid.UUID | None = None,
    title: str = "",
) -> dict[str, Any]:
    context = _context(campaign_id)
    payload = research.analyse(company_name(), industry, audience, products, market_notes, use_web, context)
    title = title.strip() or f"Market research: {industry or products or audience}"
    request_input = {"industry": industry, "audience": audience, "products": products,
                     "market_notes": market_notes, "use_web": use_web,
                     "campaign_id": str(campaign_id) if campaign_id else None}
    return _save("research", title[:255], payload, request_input, campaign_id)


def sentiment_analysis(
    texts: list[str],
    source: str = "paste",
    campaign_id: uuid.UUID | None = None,
    title: str = "",
    csv_column: str | None = None,
) -> dict[str, Any]:
    texts = sentiment.clean_texts(texts)
    if not texts:
        raise ValueError("Add some feedback text to analyse.")
    context = _context(campaign_id)
    analysed = sentiment.analyse(texts, context)
    title = title.strip() or f"Customer feedback ({len(texts)} items, {date.today():%b %d})"
    request_input = {"source": source, "item_count": len(texts), "csv_column": csv_column,
                     "campaign_id": str(campaign_id) if campaign_id else None}
    return _save("sentiment", title[:255], {"result": analysed, "evidence": [], "live_research": False},
                 request_input, campaign_id)


def marketing_strategy(
    campaign_id: uuid.UUID,
    analysis_ids: list[uuid.UUID] | None = None,
    notes: str = "",
    title: str = "",
) -> dict[str, Any]:
    with session_scope() as db:
        campaign = get_campaign(db, campaign_id)
        assert campaign is not None
        if analysis_ids:
            chosen = [db.get(Analysis, analysis_id) for analysis_id in analysis_ids]
            if any(a is None for a in chosen):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "An insight was not found")
            insights = [a for a in chosen if a is not None and a.kind != "strategy"]
        else:
            insights = latest_insights(db, campaign.id, INSIGHT_KINDS)
        digests = [insight_digest(a) for a in insights]
        brief = campaign_dict(campaign)
    payload = strategy.generate(company_name(), brief, digests, notes)
    title = title.strip() or f"Marketing strategy: {brief['name']}"
    request_input = {"campaign_id": str(campaign_id), "notes": notes,
                     "analysis_ids": [str(a) for a in analysis_ids or []],
                     "insights_used": [d["id"] for d in digests]}
    return _save("strategy", title[:255], payload, request_input, campaign_id)


def _survey_background(product: str, campaign_text: str) -> str:
    """Brief background from the documents so questions use the right product names."""
    evidence = EvidenceSet()
    evidence.add_documents([f"{product} customers", f"{product} positioning"], per_query=2)
    passages = "\n".join(f"- {item.text[:400]}" for item in evidence.items[:4])
    return "\n".join(part for part in (campaign_text, passages) if part)


def survey_out(survey: Survey, count: int) -> dict[str, Any]:
    return {
        **survey_summary(survey, count),
        "description": survey.description,
        "product": survey.product,
        "objective": survey.objective,
        "audience": survey.audience,
        "questions": survey.questions,
    }


def draft_survey(
    product: str,
    objective: str,
    audience: str,
    question_count: int = 8,
    campaign_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    context = _survey_background(product, _context(campaign_id))
    drafted = survey_agent.draft(product, objective, audience, question_count, context)
    with session_scope() as db:
        get_campaign(db, campaign_id)
        survey = Survey(
            campaign_id=campaign_id,
            title=drafted["title"],
            description=drafted["description"],
            product=product,
            objective=objective,
            audience=audience,
            questions=drafted["questions"],
        )
        db.add(survey)
        db.flush()
        db.refresh(survey)
        return survey_out(survey, response_counts(db, [survey.id]).get(survey.id, 0))
