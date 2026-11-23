"""Plain-text digests of saved analyses, for agents to build on.

The strategy agent and the supervisor read earlier results through these
digests rather than the full JSON, keeping prompts short and focused.
"""

from typing import Any

KIND_LABELS = {
    "competitor": "Competitor analysis",
    "research": "Market research",
    "sentiment": "Sentiment analysis",
    "survey": "Survey analysis",
    "strategy": "Marketing strategy",
}


def _points(label: str, points: list[dict[str, Any]], limit: int = 6) -> list[str]:
    if not points:
        return []
    lines = [f"{label}:"]
    for point in points[:limit]:
        text = point.get("text") or point.get("action") or point.get("title") or point.get("segment") or ""
        tag = "" if point.get("verified", True) else " (AI inference)"
        lines.append(f"- {text}{tag}")
    return lines


def digest(kind: str, result: dict[str, Any], live_research: bool = False) -> str:
    lines: list[str] = []
    if kind == "competitor":
        lines.append(result.get("summary", ""))
        swot = result.get("swot", {})
        for key in ("strengths", "weaknesses", "opportunities", "threats"):
            lines += _points(f"SWOT {key}", swot.get(key, []), 4)
        lines += _points("Market gaps", result.get("market_gaps", []))
        lines += _points("Differentiation", result.get("differentiation", []))
        lines += _points("Recommendations", result.get("recommendations", []), 5)
        lines.append(f"Live web research: {'yes' if live_research else 'no'}")
    elif kind == "research":
        lines.append(result.get("summary", ""))
        lines += _points("Verified findings", result.get("verified_findings", []))
        lines += _points("Trends", result.get("trends", []), 4)
        lines += _points("Customer needs", result.get("customer_needs", []), 4)
        lines += [f"Underserved segment: {s['segment']} — {s['description']}" for s in result.get("underserved_segments", [])[:4]]
        lines += [f"Opportunity ({o['confidence']}): {o['title']} — {o['description']}" for o in result.get("opportunities", [])[:4]]
        lines += [f"Hypothesis (unverified): {h['text']}" for h in result.get("hypotheses", [])[:4]]
        lines.append(f"Live web research: {'yes' if live_research else 'no'}")
    elif kind == "sentiment":
        stats, summary = result.get("stats", {}), result.get("summary", {})
        lines.append(
            f"{stats.get('total', 0)} feedback items: {stats.get('percentages', {})} "
            f"(net score {stats.get('net_score')}); satisfaction {summary.get('satisfaction_level')}."
        )
        lines.append(summary.get("overall_summary", ""))
        topics = ", ".join(f"{t['topic']} ({t['mentions']}, {t['negative']} negative)" for t in stats.get("topics", [])[:8])
        lines.append(f"Top topics: {topics}")
        lines += [f"Complaint: {c['issue']}" for c in summary.get("complaints", [])[:5]]
        lines += [f"Expectation: {e}" for e in summary.get("expectations", [])[:4]]
        lines += _points("Recommendations", summary.get("recommendations", []), 5)
    elif kind == "survey":
        stats, insights = result.get("stats", {}), result.get("insights", {})
        lines.append(f"{stats.get('total_responses', 0)} real responses. {insights.get('summary', '')}")
        lines += [f"Finding: {f['finding']}" for f in insights.get("key_findings", [])[:6]]
        lines += [f"Preference: {p}" for p in insights.get("preferences", [])[:4]]
        lines += [f"Expectation: {e}" for e in insights.get("expectations", [])[:4]]
        if result.get("small_sample"):
            lines.append("Caveat: small sample.")
    elif kind == "strategy":
        lines.append(result.get("executive_summary", ""))
        lines.append(f"Positioning: {result.get('positioning', {}).get('text', '')}")
        lines.append(f"USP: {result.get('usp', {}).get('text', '')}")
        lines += [f"Channel: {c['channel']} — {c['role']}" for c in result.get("channels", [])[:6]]
    return "\n".join(line for line in lines if line)


def summary_line(kind: str, result: dict[str, Any]) -> str:
    """One sentence shown in lists and dashboards."""
    if kind == "sentiment":
        stats = result.get("stats", {})
        pct = stats.get("percentages", {})
        return (
            f"{stats.get('total', 0)} items · {pct.get('positive', 0)}% positive · "
            f"{pct.get('negative', 0)}% negative"
        )
    if kind == "survey":
        return f"{result.get('stats', {}).get('total_responses', 0)} real responses · " + (
            result.get("insights", {}).get("summary", "")[:140]
        )
    text = result.get("summary") or result.get("executive_summary") or ""
    return text[:200]
