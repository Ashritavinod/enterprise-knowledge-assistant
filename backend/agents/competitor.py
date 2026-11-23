"""Competitor Intelligence Agent: comparison table, SWOT, gaps and recommendations.

Evidence comes from the company documents, what the user enters about each
competitor, and (when BRAVE_SEARCH_API_KEY is set and the user asks for it)
live web search. Every comparison cell and SWOT point cites that evidence;
anything uncited is flagged as AI inference.
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

ASPECTS = ("products_services", "pricing", "features", "marketing_strategy", "positioning")

SCHEMA = obj(
    summary=STR,
    comparison=arr(
        obj(
            competitor=STR,
            products_services=POINT,
            pricing=POINT,
            features=POINT,
            marketing_strategy=POINT,
            positioning=POINT,
        )
    ),
    competitor_profiles=arr(obj(competitor=STR, strengths=arr(POINT), weaknesses=arr(POINT))),
    swot=obj(
        strengths=arr(POINT),
        weaknesses=arr(POINT),
        opportunities=arr(POINT),
        threats=arr(POINT),
    ),
    market_gaps=arr(POINT),
    differentiation=arr(POINT),
    recommendations=arr(RECOMMENDATION),
    data_limitations=arr(STR),
)

PROMPT = (
    "You are a competitive intelligence analyst for {company}. Compare {company} "
    "with the listed competitors in the {industry} market using ONLY the evidence "
    "provided. Produce:\n"
    "- comparison: one row per competitor and one row for {company}, covering "
    "products/services, pricing (only prices stated in evidence), features, "
    "marketing strategy and positioning;\n"
    "- competitor_profiles: strengths and weaknesses of each competitor;\n"
    "- swot: a SWOT analysis of {company} relative to these competitors;\n"
    "- market_gaps and differentiation opportunities for {company};\n"
    "- recommendations: concrete actions{campaign};\n"
    "- data_limitations: what could not be verified, e.g. missing pricing, and "
    "whether live web research was available.\n\n" + CITATION_RULES
)


def gather_evidence(
    company: str,
    industry: str,
    competitors: list[dict[str, str]],
    use_web: bool,
) -> tuple[EvidenceSet, bool]:
    evidence = EvidenceSet()
    for competitor in competitors:
        details = [f"Name: {competitor['name']}"]
        if competitor.get("website"):
            details.append(f"Website: {competitor['website']}")
        if competitor.get("notes"):
            details.append(f"Notes: {competitor['notes']}")
        if len(details) > 1:
            evidence.add_user(f"User-supplied details on {competitor['name']}", "\n".join(details))

    names = [c["name"] for c in competitors]
    evidence.add_documents(
        [f"competitors {' '.join(names)}"]
        + [f"{name} competitor" for name in names]
        + [f"{company} positioning differentiation", f"{company} pricing menu", f"{company} marketing channels"],
        per_query=3,
    )

    live = False
    if use_web:
        queries = []
        for competitor in competitors:
            base = competitor.get("website") or competitor["name"]
            queries += [f"{competitor['name']} {industry}", f"{base} pricing products"]
        live = evidence.add_web(queries, per_query=4)
    return evidence, live


def analyse(
    company: str,
    industry: str,
    competitors: list[dict[str, str]],
    use_web: bool,
    campaign_context: str = "",
) -> dict[str, Any]:
    """Run the analysis. Returns {result, evidence, live_research}."""
    if not competitors:
        raise ValueError("Add at least one competitor.")
    evidence, live = gather_evidence(company, industry, competitors, use_web)
    campaign = f", especially for this campaign: {campaign_context}" if campaign_context else ""
    research_note = (
        "Live web search results are included (W#)."
        if live
        else "No live web research was performed; use only documents (D#) and user input (U#)."
    )
    user = (
        f"Competitors: {', '.join(c['name'] for c in competitors)}\n{research_note}\n\n"
        f"Evidence:\n{evidence.for_prompt()}"
    )
    result = call_structured(
        PROMPT.format(company=company, industry=industry or "its", campaign=campaign),
        user,
        "competitor_analysis",
        SCHEMA,
    )
    result = clean_points(result, evidence.ids())
    if not live:
        note = (
            "No live web research was performed (web search not configured or not requested); "
            "findings rely on company documents and user-supplied details only."
        )
        result["data_limitations"] = [note] + [d for d in result["data_limitations"] if d != note]
    return {"result": result, "evidence": evidence.as_list(), "live_research": live}
