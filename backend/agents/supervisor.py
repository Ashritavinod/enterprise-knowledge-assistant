"""Supervisor Agent: understands a request and coordinates the specialist agents.

It works through Azure OpenAI tool calling. Simple questions are answered
directly (searching the documents if needed); requests that need analysis
call the specialist agents, which save their results as analyses linked to a
campaign. Independent specialist calls in the same turn run in parallel.

``run`` yields progress events for the UI:

    {"type": "step", "id", "agent", "action", "status": "running"|"done"|"error",
     "detail", "analysis_id"?, "survey_id"?}
    {"type": "answer", "text": "..."}
"""

import json
import logging
import uuid
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from backend.agents.base import AGENT_TIMEOUT_SECONDS, AgentError, AgentUnavailable, deployment
from backend.db.database import session_scope
from backend.db.models import Analysis, Campaign, Survey
from backend.services import operations
from backend.services.analyses import (
    campaign_dict,
    company_name,
    insight_digest,
    latest_insights,
    response_counts,
)
from backend.services.azure_openai import get_client

logger = logging.getLogger(__name__)

MAX_ROUNDS = 6

SYSTEM_PROMPT = """You are the Supervisor of {company}'s AI marketing team. You understand the \
user's request and decide which specialists to involve:

- Competitor Intelligence Agent (run_competitor_analysis): competitor comparison, SWOT, gaps.
- Market Research Agent (run_market_research): trends, customer needs, segments, opportunities.
- Sentiment Analysis Agent (analyze_feedback): classify and summarise customer feedback text.
- Survey Agent (draft_survey): draft a survey for a product, objective and audience.
- Marketing Strategy Agent (generate_strategy): a full strategy for a campaign from saved insights.

Rules:
- Do not use specialists for simple questions. Answer greetings and questions about \
the company directly, using search_documents when you need facts from the marketing documents.
- Check existing work first: list_campaigns and get_campaign_insights show campaigns and \
their saved analyses, so you can reuse them instead of re-running agents.
- Run several specialists in the same turn when their work is independent. Run \
generate_strategy after the insights it needs exist.
- Specialists save their results; mention what was created so the user can open it.
- Never invent facts, numbers, competitor details or customer data. Say clearly when \
something was not found, when no live web research was available, and which points \
are AI inference rather than sourced facts.
- Finish with a concise, well-structured answer in Markdown (short sections or bullets), \
combining the specialists' findings into clear recommendations and next steps.{campaign}"""


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


CAMPAIGN_ID = {"type": "string", "description": "Campaign UUID to link the result to (optional)."}

TOOLS = [
    _fn("search_documents", "Search the company's marketing documents.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("list_campaigns", "List campaigns with ids, products, status and dates.", {}, []),
    _fn("get_campaign_insights", "A campaign's details plus digests of its latest saved analyses and its surveys.",
        {"campaign_id": {"type": "string"}}, ["campaign_id"]),
    _fn("run_competitor_analysis", "Competitor Intelligence Agent: comparison table, SWOT, gaps, recommendations.",
        {
            "competitors": {"type": "array", "items": {"type": "object", "properties": {
                "name": {"type": "string"}, "website": {"type": "string"}, "notes": {"type": "string"}},
                "required": ["name"]}},
            "industry": {"type": "string"},
            "use_web": {"type": "boolean", "description": "Use live web search if configured."},
            "campaign_id": CAMPAIGN_ID,
        }, ["competitors"]),
    _fn("run_market_research", "Market Research Agent: trends, needs, underserved segments, opportunities.",
        {"industry": {"type": "string"}, "audience": {"type": "string"}, "products": {"type": "string"},
         "notes": {"type": "string"}, "use_web": {"type": "boolean"}, "campaign_id": CAMPAIGN_ID}, []),
    _fn("analyze_feedback", "Sentiment Analysis Agent: classify and summarise customer feedback.",
        {"texts": {"type": "array", "items": {"type": "string"}}, "campaign_id": CAMPAIGN_ID}, ["texts"]),
    _fn("draft_survey", "Survey Agent: draft a survey (saved as a draft for the user to edit and publish).",
        {"product": {"type": "string"}, "objective": {"type": "string"}, "audience": {"type": "string"},
         "question_count": {"type": "integer"}, "campaign_id": CAMPAIGN_ID},
        ["product", "objective", "audience"]),
    _fn("generate_strategy", "Marketing Strategy Agent: full strategy for a campaign from its latest saved insights.",
        {"campaign_id": {"type": "string"}, "notes": {"type": "string"}}, ["campaign_id"]),
]

AGENT_NAMES = {
    "search_documents": "Supervisor",
    "list_campaigns": "Supervisor",
    "get_campaign_insights": "Supervisor",
    "run_competitor_analysis": "Competitor Intelligence Agent",
    "run_market_research": "Market Research Agent",
    "analyze_feedback": "Sentiment Analysis Agent",
    "draft_survey": "Survey Agent",
    "generate_strategy": "Marketing Strategy Agent",
}


def _uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError as error:
        raise ValueError(f"Invalid campaign id {value!r}; use list_campaigns to find ids.") from error


def _analysis_result(analysis: dict[str, Any]) -> dict[str, Any]:
    with session_scope() as db:
        row = db.get(Analysis, analysis["id"])
        text = insight_digest(row)["text"] if row else ""
    return {"analysis_id": str(analysis["id"]), "kind": analysis["kind"], "title": analysis["title"],
            "live_research": analysis["live_research"], "digest": text}


# --- Tools ---------------------------------------------------------------------


def _search_documents(query: str) -> dict[str, Any]:
    from backend.agents.base import EvidenceSet

    evidence = EvidenceSet()
    evidence.add_documents([query], per_query=4)
    return {"passages": [{"source": f"{e.document} p.{e.page}", "section": e.section, "text": e.text}
                         for e in evidence.items]}


def _list_campaigns() -> dict[str, Any]:
    with session_scope() as db:
        rows = db.scalars(select(Campaign).order_by(Campaign.updated_at.desc()).limit(30))
        return {"campaigns": [
            {"id": str(c.id), "name": c.name, "product": c.product, "status": c.status,
             "start_date": str(c.start_date or ""), "end_date": str(c.end_date or "")}
            for c in rows
        ]}


def _campaign_insights(campaign_id: str) -> dict[str, Any]:
    with session_scope() as db:
        campaign = db.get(Campaign, _uuid(campaign_id))
        if campaign is None:
            return {"error": "Campaign not found"}
        insights = latest_insights(db, campaign.id, ("competitor", "research", "survey", "sentiment", "strategy"))
        surveys = list(db.scalars(select(Survey).where(Survey.campaign_id == campaign.id)))
        counts = response_counts(db, [s.id for s in surveys])
        return {
            "campaign": campaign_dict(campaign),
            "latest_analyses": [insight_digest(a) for a in insights],
            "surveys": [{"id": str(s.id), "title": s.title, "status": s.status,
                         "real_responses": counts.get(s.id, 0)} for s in surveys],
        }


def _competitors(args: dict[str, Any]) -> dict[str, Any]:
    return _analysis_result(operations.competitor_analysis(
        args.get("competitors") or [], args.get("industry", ""), "", bool(args.get("use_web", True)),
        _uuid(args.get("campaign_id")),
    ))


def _research(args: dict[str, Any]) -> dict[str, Any]:
    return _analysis_result(operations.market_research(
        args.get("industry", ""), args.get("audience", ""), args.get("products", ""), args.get("notes", ""),
        bool(args.get("use_web", True)), _uuid(args.get("campaign_id")),
    ))


def _feedback(args: dict[str, Any]) -> dict[str, Any]:
    return _analysis_result(operations.sentiment_analysis(
        args.get("texts") or [], "paste", _uuid(args.get("campaign_id")),
    ))


def _survey(args: dict[str, Any]) -> dict[str, Any]:
    count = max(3, min(int(args.get("question_count") or 8), 15))
    survey = operations.draft_survey(
        args["product"], args["objective"], args["audience"], count, _uuid(args.get("campaign_id")),
    )
    return {"survey_id": str(survey["id"]), "title": survey["title"], "status": "draft",
            "questions": [q["text"] for q in survey["questions"]]}


def _strategy(args: dict[str, Any]) -> dict[str, Any]:
    campaign_id = _uuid(args.get("campaign_id"))
    if campaign_id is None:
        raise ValueError("generate_strategy needs a campaign_id")
    return _analysis_result(operations.marketing_strategy(campaign_id, None, args.get("notes", "")))


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "search_documents": lambda a: _search_documents(a.get("query", "")),
    "list_campaigns": lambda a: _list_campaigns(),
    "get_campaign_insights": lambda a: _campaign_insights(a.get("campaign_id", "")),
    "run_competitor_analysis": _competitors,
    "run_market_research": _research,
    "analyze_feedback": _feedback,
    "draft_survey": _survey,
    "generate_strategy": _strategy,
}


def _describe(name: str, args: dict[str, Any]) -> str:
    if name == "search_documents":
        return f"Searching documents for “{args.get('query', '')}”"
    if name == "run_competitor_analysis":
        return "Analysing " + ", ".join(c.get("name", "") for c in args.get("competitors", []))
    if name == "run_market_research":
        return f"Researching {args.get('industry') or args.get('products') or 'the market'}"
    if name == "analyze_feedback":
        return f"Analysing {len(args.get('texts') or [])} feedback items"
    if name == "draft_survey":
        return f"Drafting a survey on {args.get('product', '')}"
    if name == "generate_strategy":
        return "Building the marketing strategy"
    if name == "get_campaign_insights":
        return "Reviewing the campaign's saved insights"
    return "Listing campaigns"


def _execute(name: str, raw_args: str) -> dict[str, Any]:
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {"error": "Invalid tool arguments"}
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return handler(args)
    except HTTPException as error:
        return {"error": str(error.detail)}
    except (ValueError, AgentError) as error:
        return {"error": str(error)}
    except AgentUnavailable:
        raise
    except Exception:
        logger.exception("Tool %s failed", name)
        return {"error": f"{name} failed unexpectedly"}


def run(message: str, history: list[dict[str, str]], campaign_id: uuid.UUID | None = None) -> Iterator[dict[str, Any]]:
    model = deployment()
    campaign_note = ""
    if campaign_id:
        with session_scope() as db:
            campaign = db.get(Campaign, campaign_id)
            if campaign:
                campaign_note = (f"\n\nThe user is working on campaign “{campaign.name}” "
                                 f"(id {campaign.id}); link results to it unless told otherwise.")
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT.format(company=company_name(), campaign=campaign_note)}
    ]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-10:]
                 if m.get("role") in ("user", "assistant") and m.get("content")]
    messages.append({"role": "user", "content": message})

    client = get_client().with_options(timeout=AGENT_TIMEOUT_SECONDS)
    step = 0
    for _ in range(MAX_ROUNDS):
        try:
            response = client.chat.completions.create(model=model, messages=messages, tools=TOOLS, temperature=0.3)
        except Exception as error:
            logger.exception("Supervisor call failed")
            raise AgentError(f"The AI service failed: {error.__class__.__name__}") from error
        reply = response.choices[0].message
        calls = reply.tool_calls or []
        if not calls:
            yield {"type": "answer", "text": (reply.content or "").strip()}
            return

        messages.append({
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls],
        })
        started: dict[str, dict[str, Any]] = {}
        for call in calls:
            step += 1
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            started[call.id] = {"type": "step", "id": step, "agent": AGENT_NAMES.get(call.function.name, "Supervisor"),
                                "action": call.function.name, "detail": _describe(call.function.name, args)}
            yield {**started[call.id], "status": "running"}

        results: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_execute, c.function.name, c.function.arguments): c for c in calls}
            for future in as_completed(futures):
                call = futures[future]
                result = future.result()
                results[call.id] = result
                event = {**started[call.id], "status": "error" if "error" in result else "done"}
                if "error" in result:
                    event["detail"] = f"{event['detail']}: {result['error']}"
                if "analysis_id" in result:
                    event["analysis_id"] = result["analysis_id"]
                    event["kind"] = result["kind"]
                if "survey_id" in result:
                    event["survey_id"] = result["survey_id"]
                yield event
        for call in calls:
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(results[call.id], default=str)[:12000]})

    yield {"type": "answer", "text": "I stopped after several steps without finishing. Please narrow the request."}
