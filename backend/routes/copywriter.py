"""Campaign Copywriter: on-brand copy for a product, built on real customer reviews."""

from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from backend.services import copywriter, review_agent

router = APIRouter(prefix="/copy", tags=["campaign copywriter"])


class CopyRequest(BaseModel):
    product_id: int
    channel: copywriter.Channel
    notes: str = Field("", max_length=copywriter.MAX_NOTES)


@router.post("/generate")
async def generate(body: CopyRequest) -> dict[str, Any]:
    """Three copy variants, each quoting verified customer reviews and checked against the brand rules."""
    try:
        return await run_in_threadpool(copywriter.generate_copy, body.product_id, body.channel, body.notes)
    except copywriter.CopyError as error:
        code = status.HTTP_404_NOT_FOUND if "not found" in str(error) else status.HTTP_422_UNPROCESSABLE_CONTENT
        raise HTTPException(code, str(error)) from error
    except review_agent.AgentUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    except review_agent.AgentError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error
