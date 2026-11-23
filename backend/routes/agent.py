"""AI marketing team: the supervisor agent, streamed as newline-delimited JSON."""

import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from backend.agents import supervisor
from backend.agents.base import AgentError, AgentUnavailable, deployment
from backend.db.database import session_scope
from backend.models.intelligence import AgentRequest
from backend.services.analyses import get_campaign

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["AI team"])


@router.post("/chat")
def agent_chat(body: AgentRequest) -> StreamingResponse:
    """Events: {"type": "step", ...} while specialists work, then {"type": "answer", "text"}.

    On failure mid-way, an {"type": "error", "message"} event ends the stream.
    """
    try:
        deployment()
    except AgentUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error)) from error
    with session_scope() as db:
        get_campaign(db, body.campaign_id)  # 404 before streaming starts

    def events() -> Iterator[bytes]:
        try:
            for event in supervisor.run(body.message, body.history, body.campaign_id):
                yield (json.dumps(event, default=str) + "\n").encode("utf-8")
        except (AgentError, AgentUnavailable) as error:
            yield (json.dumps({"type": "error", "message": str(error)}) + "\n").encode("utf-8")
        except Exception:
            logger.exception("Supervisor failed")
            yield (json.dumps({"type": "error", "message": "The AI team hit an unexpected error."}) + "\n").encode()

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
