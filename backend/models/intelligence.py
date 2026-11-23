"""Request and response models for campaigns and the AI marketing modules."""

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CampaignStatus = Literal["draft", "planned", "active", "completed"]
AnalysisKind = Literal["competitor", "research", "sentiment", "survey", "strategy"]


def _strip_list(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        value = " ".join(str(value).split())
        if value and value not in seen:
            seen.append(value[:200])
    return seen


class CampaignFields(BaseModel):
    product: str = Field("", max_length=2000)
    objective: str = Field("", max_length=4000)
    target_audience: str = Field("", max_length=4000)
    positioning: str = Field("", max_length=4000)
    key_message: str = Field("", max_length=2000)
    budget: float | None = Field(None, ge=0, le=1e10)
    start_date: date | None = None
    end_date: date | None = None
    channels: list[str] = Field(default_factory=list, max_length=30)
    kpis: list[str] = Field(default_factory=list, max_length=30)
    status: CampaignStatus = "draft"
    notes: str = Field("", max_length=8000)

    _clean_lists = field_validator("channels", "kpis")(_strip_list)


class CampaignCreate(CampaignFields):
    name: str = Field(..., min_length=1, max_length=255)
    origin: Literal["user", "documents"] = "user"
    origin_sources: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class CampaignUpdate(BaseModel):
    """Partial update: only the fields sent are changed."""

    name: str | None = Field(None, min_length=1, max_length=255)
    product: str | None = Field(None, max_length=2000)
    objective: str | None = Field(None, max_length=4000)
    target_audience: str | None = Field(None, max_length=4000)
    positioning: str | None = Field(None, max_length=4000)
    key_message: str | None = Field(None, max_length=2000)
    budget: float | None = Field(None, ge=0, le=1e10)
    start_date: date | None = None
    end_date: date | None = None
    channels: list[str] | None = Field(None, max_length=30)
    kpis: list[str] | None = Field(None, max_length=30)
    status: CampaignStatus | None = None
    notes: str | None = Field(None, max_length=8000)

    @field_validator("channels", "kpis")
    @classmethod
    def _clean(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else _strip_list(values)


class CampaignOut(CampaignFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    origin: str
    origin_sources: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class AnalysisSummary(BaseModel):
    id: uuid.UUID
    kind: AnalysisKind
    title: str
    campaign_id: uuid.UUID | None
    campaign_name: str | None = None
    survey_id: uuid.UUID | None = None
    live_research: bool
    summary: str
    created_at: datetime


class AnalysisOut(AnalysisSummary):
    input: dict[str, Any]
    result: dict[str, Any]
    evidence: list[dict[str, Any]]
    model: str


class CampaignDetail(CampaignOut):
    analyses: list[AnalysisSummary]
    surveys: list["SurveySummary"]


# --- AI module requests ------------------------------------------------------


class CompetitorInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    website: str = Field("", max_length=500)
    notes: str = Field("", max_length=4000)


class CompetitorRequest(BaseModel):
    competitors: list[CompetitorInput] = Field(..., min_length=1, max_length=6)
    industry: str = Field("", max_length=300)
    company: str = Field("", max_length=200, description="Defaults to COMPANY_NAME.")
    use_web: bool = True
    campaign_id: uuid.UUID | None = None
    title: str = Field("", max_length=255)


class ResearchRequest(BaseModel):
    industry: str = Field("", max_length=300)
    audience: str = Field("", max_length=1000)
    products: str = Field("", max_length=1000)
    market_notes: str = Field("", max_length=8000)
    use_web: bool = True
    campaign_id: uuid.UUID | None = None
    title: str = Field("", max_length=255)


class SentimentRequest(BaseModel):
    texts: list[str] = Field(default_factory=list, max_length=500)
    csv_text: str = Field("", max_length=3_000_000, description="Raw CSV content instead of `texts`.")
    csv_column: str = Field("", max_length=200)
    source: Literal["paste", "csv", "reviews", "survey"] = "paste"
    campaign_id: uuid.UUID | None = None
    title: str = Field("", max_length=255)


class StrategyRequest(BaseModel):
    campaign_id: uuid.UUID
    analysis_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=12,
        description="Insights to use; defaults to the latest of each kind for the campaign.",
    )
    notes: str = Field("", max_length=4000)
    title: str = Field("", max_length=255)


# --- Surveys -----------------------------------------------------------------


class SurveyQuestion(BaseModel):
    id: str = Field("", max_length=40)
    type: Literal["multiple_choice", "rating", "open_ended"]
    text: str = Field(..., min_length=1, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=12)
    allow_multiple: bool = False
    scale_min: int | None = None
    scale_max: int | None = None
    scale_min_label: str = Field("", max_length=60)
    scale_max_label: str = Field("", max_length=60)
    required: bool = True


class SurveyGenerateRequest(BaseModel):
    product: str = Field(..., min_length=1, max_length=1000)
    objective: str = Field(..., min_length=1, max_length=1000)
    audience: str = Field(..., min_length=1, max_length=1000)
    question_count: int = Field(8, ge=3, le=15)
    campaign_id: uuid.UUID | None = None


class SurveyUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    questions: list[SurveyQuestion] | None = Field(None, min_length=1, max_length=30)
    campaign_id: uuid.UUID | None = None


class SurveySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    campaign_id: uuid.UUID | None
    response_count: int = 0
    created_at: datetime
    published_at: datetime | None


class SurveyOut(SurveySummary):
    description: str
    product: str
    objective: str
    audience: str
    questions: list[dict[str, Any]]


class PublicSurvey(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    questions: list[dict[str, Any]]
    accepting_responses: bool


class SurveyAnswer(BaseModel):
    answers: dict[str, Any] = Field(..., max_length=60)


class AgentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    campaign_id: uuid.UUID | None = None
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


CampaignDetail.model_rebuild()
