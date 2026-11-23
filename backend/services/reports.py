"""Downloadable reports (Markdown and PDF) for saved analyses.

Each report lists its evidence with retrieval dates and states whether live
web research was performed. Uncited points are marked as AI inference.
"""

import html
import io
import re
from datetime import datetime
from typing import Any

import pymupdf

from backend.services.insights import KIND_LABELS

# Same look as the company PDFs (scripts/generate_marketing_docs.py).
CSS = """
body { font-family: sans-serif; font-size: 10pt; line-height: 1.45; color: #4A2C2A; }
h1 { font-family: serif; font-size: 20pt; color: #4A2C2A; margin-bottom: 2pt; }
h2 { font-family: serif; font-size: 13.5pt; color: #C77A06; margin-top: 14pt; margin-bottom: 4pt; }
h3 { font-size: 11pt; color: #E8456B; margin-top: 8pt; margin-bottom: 2pt; }
p { margin-top: 0; margin-bottom: 6pt; }
ul { margin-top: 0; margin-bottom: 6pt; }
li { margin-bottom: 3pt; }
table { border-collapse: collapse; width: 100%; margin-bottom: 8pt; }
th { border-bottom: 2px solid #F5A623; color: #C77A06; text-align: left; padding: 3pt; font-size: 8.5pt; }
td { border-bottom: 1px solid #EED9C4; padding: 3pt; font-size: 8.5pt; vertical-align: top; }
em { color: #8A6B5A; }
"""
PAGE = pymupdf.paper_rect("letter")
CONTENT = PAGE + (54, 54, -54, -54)


def _cite(point: dict[str, Any]) -> str:
    sources = point.get("sources") or []
    if sources:
        return f" [{', '.join(sources)}]"
    return " *(AI inference)*" if "verified" in point else ""


def _point_lines(points: list[dict[str, Any]], key: str = "text") -> list[str]:
    return [f"- {p.get(key, '')}{_cite(p)}" for p in points] or ["- None identified."]


def _cell(text: Any) -> str:
    return str(text if text is not None else "").replace("|", "/").replace("\n", " ")


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_No data._"]
    return [
        "| " + " | ".join(headers) + " |",
        "|" + "---|" * len(headers),
        *("| " + " | ".join(_cell(c) for c in row) + " |" for row in rows),
    ]


def _recommendations(recs: list[dict[str, Any]]) -> list[str]:
    return [
        f"- **{r['action']}** ({r.get('priority', '')} priority) — {r.get('rationale', '')}{_cite(r)}" for r in recs
    ] or ["- None."]


def _competitor(r: dict[str, Any]) -> list[str]:
    lines = ["## Summary", r.get("summary", ""), "", "## Comparison"]
    lines += _table(
        ["Company", "Products & services", "Pricing", "Features", "Marketing", "Positioning"],
        [
            [row["competitor"]] + [f"{row[a]['text']}{_cite(row[a])}" for a in
                                   ("products_services", "pricing", "features", "marketing_strategy", "positioning")]
            for row in r.get("comparison", [])
        ],
    )
    for profile in r.get("competitor_profiles", []):
        lines += ["", f"### {profile['competitor']}", "**Strengths**", *_point_lines(profile["strengths"]),
                  "**Weaknesses**", *_point_lines(profile["weaknesses"])]
    swot = r.get("swot", {})
    lines += ["", "## SWOT"]
    for key in ("strengths", "weaknesses", "opportunities", "threats"):
        lines += [f"### {key.title()}", *_point_lines(swot.get(key, []))]
    lines += ["", "## Market gaps", *_point_lines(r.get("market_gaps", [])),
              "", "## Differentiation opportunities", *_point_lines(r.get("differentiation", [])),
              "", "## Recommendations", *_recommendations(r.get("recommendations", [])),
              "", "## Data limitations", *[f"- {d}" for d in r.get("data_limitations", [])]]
    return lines


def _research(r: dict[str, Any]) -> list[str]:
    return [
        "## Summary", r.get("summary", ""),
        "", "## Verified findings", *_point_lines(r.get("verified_findings", [])),
        "", "## Trends", *_point_lines(r.get("trends", [])),
        "", "## Customer needs", *_point_lines(r.get("customer_needs", [])),
        "", "## Underserved segments",
        *[f"- **{s['segment']}** — {s['description']}{_cite(s)}" for s in r.get("underserved_segments", [])],
        "", "## Opportunities",
        *[f"- **{o['title']}** ({o['confidence']} confidence) — {o['description']}{_cite(o)}" for o in r.get("opportunities", [])],
        "", "## Product and service gaps", *_point_lines(r.get("product_gaps", [])),
        "", "## Hypotheses (AI-generated, not verified)",
        *[f"- {h['text']} — *{h['rationale']}*" + (f" Validate: {h['how_to_validate']}" if h.get("how_to_validate") else "")
          for h in r.get("hypotheses", [])],
        "", "## Recommendations", *_recommendations(r.get("recommendations", [])),
        "", "## Data limitations", *[f"- {d}" for d in r.get("data_limitations", [])],
    ]


def _sentiment_block(result: dict[str, Any]) -> list[str]:
    stats, summary = result["stats"], result["summary"]
    lines = [
        f"**{stats['total']} items analysed.** Satisfaction: {summary['satisfaction_level']}. "
        f"Net sentiment score: {stats['net_score']} (from -100 to +100).",
        "",
        *_table(["Sentiment", "Count", "Share"],
                [[s.title(), stats["counts"][s], f"{stats['percentages'][s]}%"] for s in ("positive", "neutral", "negative")]),
        "", summary["overall_summary"],
        "", "### Topics",
        *_table(["Topic", "Mentions", "Positive", "Neutral", "Negative"],
                [[t["topic"], t["mentions"], t["positive"], t["neutral"], t["negative"]] for t in stats["topics"][:15]]),
        "", "### Complaints", *([f'- **{c["issue"]}** — "{c["example"]}"' for c in summary["complaints"]] or ["- None."]),
        "", "### Expectations", *([f"- {e}" for e in summary["expectations"]] or ["- None."]),
        "", "### Strengths", *([f"- {s['text']}" for s in summary["strengths"]] or ["- None."]),
        "", "### Weaknesses", *([f"- {w['text']}" for w in summary["weaknesses"]] or ["- None."]),
        "", "### Recommendations",
        *([f"- **{r['action']}** ({r['priority']} priority) — {r['rationale']}" for r in summary["recommendations"]] or ["- None."]),
    ]
    return lines


def _survey(r: dict[str, Any]) -> list[str]:
    stats, insights = r["stats"], r["insights"]
    lines = [
        "## Summary",
        f"**{stats['total_responses']} real responses collected.** No synthetic or sample data is included.",
        "", insights["summary"],
    ]
    if r.get("small_sample"):
        lines += ["", "*Small sample: treat percentages as indicative only.*"]
    lines += ["", "## Results by question"]
    for q in stats["questions"]:
        lines += ["", f"### {q['text']}", f"_{q['answered']} answered_"]
        if q["type"] == "multiple_choice":
            lines += _table(["Option", "Responses", "Share"], [[o["option"], o["count"], f"{o['percent']}%"] for o in q["options"]])
        elif q["type"] == "rating":
            lines.append(f"Average: **{q['average']}** on a {q['scale_min']}-{q['scale_max']} scale")
            lines += _table(["Rating", "Responses"], [[d["value"], d["count"]] for d in q["distribution"]])
        else:
            lines += [f'- "{a}"' for a in q["answers"][:20]] or ["- No answers."]
    lines += ["", "## Key findings", *[f"- {f['finding']} ({', '.join(f['question_ids'])})" for f in insights["key_findings"]],
              "", "## Preferences", *[f"- {p}" for p in insights["preferences"]],
              "", "## Expectations", *[f"- {e}" for e in insights["expectations"]],
              "", "## Recommendations",
              *[f"- **{x['action']}** ({x['priority']} priority) — {x['rationale']}" for x in insights["recommendations"]],
              "", "## Caveats", *([f"- {c}" for c in insights["caveats"]] or ["- None."])]
    if r.get("open_ended_sentiment"):
        lines += ["", "## Sentiment of open-ended answers", *_sentiment_block(r["open_ended_sentiment"])]
    return lines


def _strategy(r: dict[str, Any]) -> list[str]:
    lines = [
        "## Executive summary", r.get("executive_summary", ""),
        "", "## Target audience",
        *[f"- **{a['segment']}** — {a['description']} *{a['rationale']}*{_cite(a)}" for a in r.get("target_audience", [])],
        "", "## Customer segmentation",
        *_table(["Segment", "Needs", "Message", "Priority"],
                [[s["segment"], s["needs"], s["message"], s["priority"]] for s in r.get("segmentation", [])]),
        "", "## Positioning", f"{r['positioning']['text']}{_cite(r['positioning'])}",
        "", "## Unique selling proposition", f"{r['usp']['text']}{_cite(r['usp'])}",
        "", "## Objectives",
        *_table(["Objective", "Metric", "Target"], [[o["objective"], o["metric"], o["target"]] for o in r.get("objectives", [])]),
        "", "## Channels",
        *_table(["Channel", "Role", "Budget share", "Rationale"],
                [[c["channel"], c["role"],
                  (f"{c['budget_share_percent']:g}%"
                   + (f" (${c['budget_amount']:,})" if c.get("budget_amount") is not None else ""))
                  if c.get("budget_share_percent") is not None else "—",
                  c["rationale"]] for c in r.get("channels", [])]),
        *([f"*{r['budget_note']}*"] if r.get("budget_note") else []),
        "", "## Content ideas",
        *_table(["Idea", "Channel", "Format"], [[c["idea"], c["channel"], c["format"]] for c in r.get("content_ideas", [])]),
        "", "## Promotions", *_point_lines(r.get("promotions", [])),
        "", "## Competitor differentiation", *_point_lines(r.get("differentiation", [])),
        "", "## Timeline",
        *_table(["Phase", "Start", "End", "Activities"],
                [[t["phase"], t["start"], t["end"], "; ".join(t["activities"])] for t in r.get("timeline", [])]),
        "", "## Action plan",
        *_table(["Step", "Owner", "Due"], [[a["step"], a["owner"], a["due"]] for a in r.get("action_plan", [])]),
        "", "## KPIs and measurement",
        *_table(["KPI", "Target", "How to measure"], [[k["kpi"], k["target"], k["measurement"]] for k in r.get("kpis", [])]),
        "", "## Risks", *_point_lines(r.get("risks", [])),
    ]
    if r.get("insight_gaps"):
        lines += ["", "## Missing insights",
                  f"No saved {', '.join(r['insight_gaps'])} analysis was available when this strategy was generated."]
    return lines


def _evidence(evidence: list[dict[str, Any]], live_research: bool, kind: str) -> list[str]:
    lines = ["", "## Sources"]
    if kind in ("competitor", "research"):
        lines.append(
            "Live web research: **performed**." if live_research
            else "Live web research: **not performed**. Findings use company documents and user-supplied information only."
        )
    if not evidence:
        return lines + ["- No external sources were used."]
    for item in evidence:
        if item["kind"] == "document":
            where = f"{item['document']}, page {item['page']}" + (f" ({item['section']})" if item.get("section") else "")
        elif item["kind"] == "web":
            where = item["url"] + (f", published {item['published']}" if item.get("published") else "")
        elif item["kind"] == "analysis":
            where = "saved analysis in the app"
        else:
            where = "supplied by the user"
        lines.append(f"- **{item['id']}** {item['title']} — {where}; retrieved {item['retrieved_at'][:10]}")
    return lines


RENDERERS = {
    "competitor": _competitor,
    "research": _research,
    "sentiment": lambda r: ["## Results", *_sentiment_block(r)],
    "survey": _survey,
    "strategy": _strategy,
}


def to_markdown(analysis: dict[str, Any]) -> str:
    created = analysis["created_at"]
    created = created.strftime("%Y-%m-%d %H:%M UTC") if isinstance(created, datetime) else str(created)[:16]
    lines = [
        f"# {analysis['title']}",
        f"*{KIND_LABELS[analysis['kind']]} · generated {created}"
        + (f" · campaign: {analysis['campaign_name']}" if analysis.get("campaign_name") else "")
        + (f" · model: {analysis['model']}" if analysis.get("model") else "")
        + "*",
        "",
        *RENDERERS[analysis["kind"]](analysis["result"]),
        *_evidence(analysis.get("evidence", []), analysis.get("live_research", False), analysis["kind"]),
        "",
        "*Points marked AI inference are not backed by a cited source. Verify them before acting.*",
    ]
    return "\n".join(lines) + "\n"


# --- Markdown → HTML (the subset produced above) → PDF ------------------------


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_(.+?)_(?!\w)", r"<i>\1</i>", text)
    return text


def markdown_to_html(markdown: str) -> str:
    out: list[str] = []
    lines = markdown.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|(\s*-+\s*\|)+$", lines[i]):
                    rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            head, body = rows[0], rows[1:]
            out.append("<table><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr>")
            out += ["<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>" for row in body]
            out.append("</table>")
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        heading = re.match(r"^(#{1,3}) (.*)", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif line:
            out.append(f"<p>{_inline(line)}</p>")
        i += 1
    return "\n".join(out)


def to_pdf(analysis: dict[str, Any]) -> bytes:
    story = pymupdf.Story(html=markdown_to_html(to_markdown(analysis)), user_css=CSS)
    buffer = io.BytesIO()  # in memory: no temp file for Windows to keep locked
    writer = pymupdf.DocumentWriter(buffer)
    more = True
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(CONTENT)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()
