"""AI Survey Studio: draft with AI, edit, publish, collect real responses, analyse.

Public routes (/public/surveys/...) are what respondents use through the
shareable link; they expose only the questions and accept answers while the
survey is published. Responses are always real submissions: nothing here
generates sample data.
"""

import csv
import io
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agents import survey as survey_agent
from backend.db.database import get_db, session_scope
from backend.db.models import Survey, SurveyResponse
from backend.models.intelligence import (
    AnalysisOut,
    PublicSurvey,
    SurveyAnswer,
    SurveyGenerateRequest,
    SurveyOut,
    SurveySummary,
    SurveyUpdate,
)
from backend.services import operations
from backend.services.analyses import (
    campaign_context,
    full,
    get_campaign,
    response_counts,
    run_agent,
    save_analysis,
    survey_summary,
)
from backend.services.operations import survey_out

router = APIRouter(tags=["surveys"])


def _get(db: Session, survey_id: uuid.UUID) -> Survey:
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    return survey


def _out(db: Session, survey: Survey) -> dict[str, Any]:
    return survey_out(survey, response_counts(db, [survey.id]).get(survey.id, 0))


@router.post("/surveys/generate", response_model=SurveyOut, status_code=status.HTTP_201_CREATED)
async def generate_survey(body: SurveyGenerateRequest) -> dict[str, Any]:
    return await run_agent(
        operations.draft_survey, body.product, body.objective, body.audience, body.question_count, body.campaign_id
    )


@router.get("/surveys", response_model=list[SurveySummary])
def list_surveys(campaign_id: uuid.UUID | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    query = select(Survey).order_by(Survey.created_at.desc())
    if campaign_id:
        query = query.where(Survey.campaign_id == campaign_id)
    surveys = list(db.scalars(query))
    counts = response_counts(db, [s.id for s in surveys])
    return [survey_summary(s, counts.get(s.id, 0)) for s in surveys]


@router.get("/surveys/{survey_id}", response_model=SurveyOut)
def get_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _out(db, _get(db, survey_id))


@router.put("/surveys/{survey_id}", response_model=SurveyOut)
def update_survey(survey_id: uuid.UUID, body: SurveyUpdate, db: Session = Depends(get_db)) -> dict[str, Any]:
    survey = _get(db, survey_id)
    changes = body.model_dump(exclude_unset=True)
    if "questions" in changes:
        if survey.status != "draft":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Questions can only be edited while the survey is a draft, so collected answers stay consistent.",
            )
        try:
            survey.questions = survey_agent.normalise_questions(changes.pop("questions"))
        except ValueError as error:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    if "campaign_id" in changes:
        get_campaign(db, changes["campaign_id"])
    for field, value in changes.items():
        if value is not None or field == "campaign_id":
            setattr(survey, field, value)
    db.flush()
    out = _out(db, survey)
    db.commit()
    return out


def _set_status(db: Session, survey_id: uuid.UUID, new_status: str) -> dict[str, Any]:
    survey = _get(db, survey_id)
    if new_status == "published":
        if not survey.questions:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Add questions before publishing")
        survey.published_at = survey.published_at or datetime.now(timezone.utc)
    survey.status = new_status
    db.flush()
    out = _out(db, survey)
    db.commit()
    return out


@router.post("/surveys/{survey_id}/publish", response_model=SurveyOut)
def publish_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_status(db, survey_id, "published")


@router.post("/surveys/{survey_id}/close", response_model=SurveyOut)
def close_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _set_status(db, survey_id, "closed")


@router.delete("/surveys/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    db.delete(_get(db, survey_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _answers(db: Session, survey_id: uuid.UUID) -> list[dict[str, Any]]:
    return [
        r.answers
        for r in db.scalars(
            select(SurveyResponse).where(SurveyResponse.survey_id == survey_id).order_by(SurveyResponse.id)
        )
    ]


@router.get("/surveys/{survey_id}/results")
def survey_results(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Counts, percentages and averages from real responses (no AI)."""
    survey = _get(db, survey_id)
    return survey_agent.results(survey.questions, _answers(db, survey_id))


@router.get("/surveys/{survey_id}/responses.csv")
def export_responses(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    survey = _get(db, survey_id)
    rows = db.scalars(select(SurveyResponse).where(SurveyResponse.survey_id == survey_id).order_by(SurveyResponse.id))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["response_id", "submitted_at", *[q["text"] for q in survey.questions]])
    for row in rows:
        values = []
        for q in survey.questions:
            value = row.answers.get(q["id"], "")
            values.append("; ".join(value) if isinstance(value, list) else value)
        writer.writerow([row.id, row.submitted_at.isoformat(), *values])
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="survey-{survey_id}-responses.csv"'},
    )


@router.post("/surveys/{survey_id}/analyze", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def analyze_survey(survey_id: uuid.UUID) -> dict[str, Any]:
    with session_scope() as db:
        survey = _get(db, survey_id)
        questions, answers = survey.questions, _answers(db, survey_id)
        campaign_id, title = survey.campaign_id, survey.title
        context = campaign_context(get_campaign(db, campaign_id))
    analysed = await run_agent(survey_agent.analyse, questions, answers, context)
    with session_scope() as db:
        analysis = save_analysis(
            db,
            kind="survey",
            title=f"Survey analysis: {title}",
            payload={"result": analysed, "evidence": [], "live_research": False},
            request_input={"survey_id": str(survey_id), "survey_title": title, "responses_analysed": len(answers)},
            campaign=get_campaign(db, campaign_id),
            survey_id=survey_id,
        )
        return full(db, analysis)


# --- Public (respondent) routes ----------------------------------------------


def _public_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = ("id", "type", "text", "options", "allow_multiple", "scale_min", "scale_max",
            "scale_min_label", "scale_max_label", "required")
    return [{k: q.get(k) for k in keys} for q in questions]


@router.get("/public/surveys/{survey_id}", response_model=PublicSurvey)
def public_survey(survey_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    survey = db.get(Survey, survey_id)
    if survey is None or survey.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This survey is not available")
    return {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "questions": _public_questions(survey.questions),
        "accepting_responses": survey.status == "published",
    }


@router.post("/public/surveys/{survey_id}/responses", status_code=status.HTTP_201_CREATED)
def submit_response(survey_id: uuid.UUID, body: SurveyAnswer, db: Session = Depends(get_db)) -> dict[str, Any]:
    survey = db.get(Survey, survey_id)
    if survey is None or survey.status == "draft":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This survey is not available")
    if survey.status != "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "This survey is closed and no longer accepts responses")
    try:
        answers = survey_agent.validate_answers(survey.questions, body.answers)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from error
    response = SurveyResponse(survey_id=survey_id, answers=answers)
    db.add(response)
    db.flush()
    db.commit()
    return {"id": response.id, "message": "Thank you! Your response has been recorded."}
