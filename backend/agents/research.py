"""Market Research Agent: trends, needs, underserved segments and opportunities.

Findings backed by evidence (documents, user input, live web results) are
kept separate from AI hypotheses, which the result lists on their own.
"""

from typing import Any

from backend.agents.base import (
    CITATION_RULES,
    POINT,
    RECOMMENDATION,
    STR,
    EvidenceSet,
    arr,
    call_structured,
    clean_points,
    obj,
)

CONFIDENCE = {"type": "string", "enum": ["high", "medium", "low"]}

SCHEMA = obj(
    summary=STR,
    verified_findings=arr(POINT),
    trends=arr(POINT),
    customer_needs=arr(POINT),
    underserved_segments=arr(obj(segment=STR, description=STR, sources=arr(STR))),
    opportunities=arr(obj(title=STR, description=STR, confidence=CONFIDENCE, sources=arr(STR))),
    product_gaps=arr(POINT),
    hypotheses=arr(obj(text=STR, rationale=STR, how_to_validate=STR)),
    recommendations=arr(RECOMMENDATION),
    data_limitations=arr(STR),
)

PROMPT = (
    "You are a market research analyst for {company}. Analyse the {industry} market "
    "for the given audience and products using ONLY the evidence provided. Produce:\n"
    "- verified_findings: facts stated in the evidence that matter for this market;\n"
    "- trends and customer_needs (cite evidence);\n"
    "- underserved_segments and opportunities (cite evidence where it supports them);\n"
    "- product_gaps in {company}'s current offer;\n"
    "- hypotheses: ideas NOT directly supported by evidence, each with its rationale "
    "and how to validate it (e.g. a survey question);\n"
    "- recommendations{campaign};\n"
    "- data_limitations, including whether live web research was available.\n\n"
    + CITATION_RULES
)


def analyse(
    company: str,
    industry: str,
    audience: str,
    products: str,
    market_notes: str,
    use_web: bool,
    campaign_context: str = "",
) -> dict[str, Any]:
    if not (industry or audience or products):
        raise ValueError("Describe the industry, audience or products to research.")
    evidence = EvidenceSet()
    if market_notes.strip():
        evidence.add_user("User-supplied market information", market_notes)
    evidence.add_documents(
        [
            f"target audience personas {audience}",
            f"market trends {industry}",
            f"{products} customers",
            "growth goals new markets expansion",
            "customer research insights",
        ],
        per_query=3,
    )
    live = False
    if use_web:
        live = evidence.add_web(
            [
                f"{industry} market trends 2026",
                f"{industry} consumer needs {audience}",
                f"{products} demand trends",
            ],
            per_query=5,
        )

    campaign = f" for this campaign: {campaign_context}" if campaign_context else ""
    research_note = (
        "Live web search results are included (W#)."
        if live
        else "No live web research was performed; use only documents (D#) and user input (U#)."
    )
    user = (
        f"Industry: {industry}\nTarget audience: {audience}\nProducts/services: {products}\n"
        f"{research_note}\n\nEvidence:\n{evidence.for_prompt()}"
    )
    result = call_structured(
        PROMPT.format(company=company, industry=industry or "target", campaign=campaign),
        user,
        "market_research",
        SCHEMA,
    )
    result = clean_points(result, evidence.ids())
    # Anything presented as a verified finding must actually cite evidence.
    unverified = [p for p in result["verified_findings"] if not p["verified"]]
    result["verified_findings"] = [p for p in result["verified_findings"] if p["verified"]]
    result["hypotheses"] += [
        {"text": p["text"], "rationale": "Stated as a finding but not supported by the evidence.", "how_to_validate": ""}
        for p in unverified
    ]
    if not live:
        result["data_limitations"].insert(
            0,
            "No live web research was performed (web search not configured or not requested); "
            "findings rely on company documents and user-supplied information only.",
        )
    return {"result": result, "evidence": evidence.as_list(), "live_research": live}
