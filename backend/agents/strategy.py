"""Marketing Strategy Agent: turns a campaign and saved insights into a strategy.

Inputs are the campaign record, the latest (or chosen) competitor, market
research, survey and sentiment analyses for it (as A# evidence), and brand,
channel and KPI rules from the company documents (D#). The result can be
downloaded as a report and applied back onto the campaign.
"""

from typing import Any

from backend.agents.base import (
    CITATION_RULES,
    NUM_OR_NULL,
    POINT,
    PRIORITY,
    STR,
    EvidenceSet,
    arr,
    call_structured,
    clean_points,
    obj,
)

SOURCED = {"sources": arr(STR)}

SCHEMA = obj(
    executive_summary=STR,
    target_audience=arr(obj(segment=STR, description=STR, rationale=STR, **SOURCED)),
    segmentation=arr(obj(segment=STR, needs=STR, message=STR, priority=PRIORITY, **SOURCED)),
    positioning=POINT,
    usp=POINT,
    objectives=arr(obj(objective=STR, metric=STR, target=STR, **SOURCED)),
    channels=arr(obj(channel=STR, role=STR, budget_share_percent=NUM_OR_NULL, rationale=STR, **SOURCED)),
    content_ideas=arr(obj(idea=STR, channel=STR, format=STR)),
    promotions=arr(POINT),
    differentiation=arr(POINT),
    timeline=arr(obj(phase=STR, start=STR, end=STR, activities=arr(STR))),
    action_plan=arr(obj(step=STR, owner=STR, due=STR)),
    kpis=arr(obj(kpi=STR, target=STR, measurement=STR)),
    risks=arr(POINT),
)

PROMPT = (
    "You are a senior marketing strategist at {company}. Build a complete, "
    "practical marketing strategy for the campaign below, combining the saved "
    "insights (competitor analysis, market research, survey results, customer "
    "sentiment) with the company's brand, channel and approval rules from the "
    "documents. Cover target audience, segmentation, positioning, a single clear "
    "USP, SMART objectives, channels (budget_share_percent is the share of THIS "
    "campaign's budget and the shares must add up to 100; do not copy the company-wide "
    "budget split from the documents; use null for all channels if no budget is known), "
    "content and promotion ideas, competitor "
    "differentiation, a dated timeline within the campaign dates when given, an "
    "action plan, KPIs with targets and how to measure them, and risks. Follow the "
    "brand rules in the documents (e.g. tone, colours, competitor-naming rules). "
    "Where an insight is missing, say what to research instead of inventing data.\n\n"
    + CITATION_RULES
)


def campaign_brief(campaign: dict[str, Any]) -> str:
    fields = [
        ("Name", campaign.get("name")),
        ("Product", campaign.get("product")),
        ("Objective", campaign.get("objective")),
        ("Target audience", campaign.get("target_audience")),
        ("Positioning", campaign.get("positioning")),
        ("Key message", campaign.get("key_message")),
        ("Budget (USD)", campaign.get("budget")),
        ("Start date", campaign.get("start_date")),
        ("End date", campaign.get("end_date")),
        ("Channels", ", ".join(campaign.get("channels") or [])),
        ("KPIs", "; ".join(campaign.get("kpis") or [])),
        ("Status", campaign.get("status")),
        ("Notes", campaign.get("notes")),
    ]
    return "\n".join(f"{label}: {value}" for label, value in fields if value not in (None, "", []))


def generate(
    company: str,
    campaign: dict[str, Any],
    insights: list[dict[str, str]],
    notes: str = "",
) -> dict[str, Any]:
    """`insights` are [{"id", "title", "text"}] digests of saved analyses."""
    evidence = EvidenceSet()
    for insight in insights:
        evidence.add_analysis(insight["title"], insight["text"], insight["id"])
    if notes.strip():
        evidence.add_user("Strategy notes from the user", notes)
    product = campaign.get("product") or campaign.get("name") or ""
    evidence.add_documents(
        [
            f"{product} campaign launch",
            "brand voice tone visual rules",
            "marketing channels budget allocation",
            "campaign tiers approvals timeline brief",
            "KPIs reporting measurement",
            f"target audience personas {campaign.get('target_audience', '')}",
        ],
        per_query=3,
    )
    missing = sorted({"competitor", "research", "survey", "sentiment"} - {i["kind"] for i in insights})
    gaps = (
        f"No saved {', '.join(missing)} analysis is available for this campaign; note what to research."
        if missing
        else "All four insight types are available."
    )
    user = f"Campaign:\n{campaign_brief(campaign)}\n\n{gaps}\n\nEvidence:\n{evidence.for_prompt()}"
    result = call_structured(PROMPT.format(company=company), user, "marketing_strategy", SCHEMA, temperature=0.4)
    result = clean_points(result, evidence.ids())
    result["insight_gaps"] = missing
    result["budget_note"] = _check_budget_shares(result["channels"], campaign.get("budget"))
    return {"result": result, "evidence": evidence.as_list(), "live_research": False}


def _check_budget_shares(channels: list[dict[str, Any]], budget: float | None) -> str:
    """Keep channel budget shares consistent: all null without a budget, ~100% with one."""
    if not budget:
        for channel in channels:
            channel["budget_share_percent"] = None
        return "No campaign budget is set, so no budget split is given."
    shares = [c["budget_share_percent"] for c in channels]
    if not channels or any(s is None or s < 0 for s in shares):
        for channel in channels:
            channel["budget_share_percent"] = None
        return "The AI did not give a complete budget split; allocate the budget manually."
    total = sum(shares)
    if total <= 0:
        return "The AI did not give a usable budget split; allocate the budget manually."
    note = ""
    if abs(total - 100) > 2:
        for channel in channels:
            channel["budget_share_percent"] = round(channel["budget_share_percent"] * 100 / total, 1)
        note = f"The AI's channel shares added up to {total:g}%; they were rescaled proportionally to 100%."
    for channel in channels:
        channel["budget_amount"] = round(budget * channel["budget_share_percent"] / 100)
    return note


def campaign_updates(strategy: dict[str, Any]) -> dict[str, Any]:
    """Campaign fields filled from a strategy (used by 'Apply to campaign')."""
    updates: dict[str, Any] = {}
    if strategy.get("positioning", {}).get("text"):
        updates["positioning"] = strategy["positioning"]["text"]
    if strategy.get("usp", {}).get("text"):
        updates["key_message"] = strategy["usp"]["text"]
    if strategy.get("target_audience"):
        updates["target_audience"] = "; ".join(
            f"{a['segment']}: {a['description']}" for a in strategy["target_audience"]
        )
    if strategy.get("objectives"):
        updates["objective"] = "; ".join(
            f"{o['objective']} ({o['metric']}: {o['target']})" for o in strategy["objectives"]
        )
    if strategy.get("channels"):
        updates["channels"] = [c["channel"] for c in strategy["channels"]]
    if strategy.get("kpis"):
        updates["kpis"] = [f"{k['kpi']}: {k['target']}" for k in strategy["kpis"]]
    return updates
