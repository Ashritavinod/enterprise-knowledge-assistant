"""Brand Compliance Checker: check draft copy against the brand guidelines."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from backend.services import brand_checker

router = APIRouter(prefix="/brand", tags=["brand compliance"])


class CheckRequest(BaseModel):
    text: str = Field(..., max_length=brand_checker.MAX_TEXT)
    channel: brand_checker.Channel = "other"
    subject: str = Field("", max_length=300, description="Email subject line (email channel only)")


@router.post("/check")
async def check(body: CheckRequest) -> dict[str, Any]:
    """Issues (each citing a guideline passage), a verdict and score, and a compliant rewrite.

    The hard rules always run; the tone and style review and the rewrite need Azure OpenAI.
    """
    if not body.text.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Paste some copy to check")
    return await run_in_threadpool(brand_checker.check_copy, body.text, body.channel, body.subject)
