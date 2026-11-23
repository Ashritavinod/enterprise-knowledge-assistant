"""Survey Agent: drafts survey questions and interprets real responses.

Question drafting and the written insights come from the model. Response
counts, percentages and averages are computed here from stored responses.
The app never fabricates responses: analysis requires real submissions.
"""

from collections import Counter
from typing import Any

from backend.agents import sentiment
from backend.agents.base import (
    BOOL,
    INT,
    PRIORITY,
    STR,
    arr,
    call_structured,
    obj,
)

QUESTION_TYPES = ("multiple_choice", "rating", "open_ended")
SMALL_SAMPLE = 10

QUESTION_SCHEMA = obj(
    type={"type": "string", "enum": list(QUESTION_TYPES)},
    text=STR,
    options=arr(STR),
    allow_multiple=BOOL,
    scale_min=INT,
    scale_max=INT,
    scale_min_label=STR,
    scale_max_label=STR,
    required=BOOL,
)
DRAFT_SCHEMA = obj(title=STR, description=STR, questions=arr(QUESTION_SCHEMA))

DRAFT_PROMPT = (
    "You are a market researcher designing a short customer survey. Write clear, "
    "neutral, non-leading questions in plain language for the target audience. Mix "
    "question types: multiple_choice (3-6 mutually exclusive options; set "
    "allow_multiple true only for 'select all that apply'), rating (scale 1-5 with "
    "labels for the ends, e.g. 'Very unlikely' and 'Very likely'), and open_ended "
    "(no options). For non-rating questions set scale_min 0, scale_max 0 and empty "
    "scale labels. Ask one thing per question. Start with easy questions and end "
    "with an open-ended question. The description is shown to respondents: say what "
    "the survey is about and roughly how long it takes."
)

INSIGHT_SCHEMA = obj(
    summary=STR,
    key_findings=arr(obj(finding=STR, question_ids=arr(STR))),
    preferences=arr(STR),
    expectations=arr(STR),
    recommendations=arr(obj(action=STR, rationale=STR, priority=PRIORITY)),
    caveats=arr(STR),
)

INSIGHT_PROMPT = (
    "You are a customer insights analyst. Interpret the survey results below. "
    "Every finding must be supported by the numbers or quotes given and list the "
    "question ids it comes from. Identify customer preferences and expectations "
    "and give practical recommendations{campaign}. Mention in caveats if the "
    "sample is small ({small} or fewer responses) or a question has few answers. "
    "Do not invent numbers or quotes."
)


def normalise_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and tidy questions; assigns ids q1, q2 … when missing."""
    cleaned = []
    used: set[str] = set()
    for number, raw in enumerate(questions, start=1):
        qtype = raw.get("type")
        if qtype not in QUESTION_TYPES:
            raise ValueError(f"Question {number}: unknown type {qtype!r}")
        text = " ".join(str(raw.get("text", "")).split())
        if not text:
            raise ValueError(f"Question {number} has no text")
        qid = str(raw.get("id") or f"q{number}")
        while qid in used:
            qid = f"{qid}_{number}"
        used.add(qid)
        question: dict[str, Any] = {
            "id": qid,
            "type": qtype,
            "text": text[:500],
            "required": bool(raw.get("required", True)),
            "options": [],
            "allow_multiple": False,
            "scale_min": None,
            "scale_max": None,
            "scale_min_label": "",
            "scale_max_label": "",
        }
        if qtype == "multiple_choice":
            options = []
            for option in raw.get("options") or []:
                option = " ".join(str(option).split())[:200]
                if option and option not in options:
                    options.append(option)
            if len(options) < 2:
                raise ValueError(f"Question {number} needs at least two options")
            question["options"] = options[:12]
            question["allow_multiple"] = bool(raw.get("allow_multiple"))
        elif qtype == "rating":
            low, high = int(raw.get("scale_min") or 1), int(raw.get("scale_max") or 5)
            if not (0 <= low < high <= 10):
                low, high = 1, 5
            question.update(
                scale_min=low,
                scale_max=high,
                scale_min_label=str(raw.get("scale_min_label") or "")[:60],
                scale_max_label=str(raw.get("scale_max_label") or "")[:60],
            )
        cleaned.append(question)
    if not cleaned:
        raise ValueError("A survey needs at least one question")
    return cleaned


def draft(product: str, objective: str, audience: str, question_count: int, context: str = "") -> dict[str, Any]:
    user = (
        f"Product or service: {product}\nBusiness objective: {objective}\n"
        f"Target audience: {audience}\nNumber of questions: {question_count}"
    )
    if context:
        user += f"\nBackground (from the campaign and company documents):\n{context}"
    data = call_structured(DRAFT_PROMPT, user, "survey_draft", DRAFT_SCHEMA, temperature=0.5)
    return {
        "title": data["title"][:255],
        "description": data["description"],
        "questions": normalise_questions(data["questions"])[: max(1, question_count)],
    }


def validate_answers(questions: list[dict[str, Any]], answers: dict[str, Any]) -> dict[str, Any]:
    """Check a respondent's answers against the questions; returns the cleaned answers."""
    cleaned: dict[str, Any] = {}
    for q in questions:
        value = answers.get(q["id"])
        empty = value is None or value == "" or value == []
        if empty:
            if q["required"]:
                raise ValueError(f"Please answer: {q['text']}")
            continue
        if q["type"] == "multiple_choice":
            values = value if isinstance(value, list) else [value]
            if not q["allow_multiple"] and len(values) != 1:
                raise ValueError(f"Choose one option for: {q['text']}")
            if any(v not in q["options"] for v in values):
                raise ValueError(f"Invalid option for: {q['text']}")
            cleaned[q["id"]] = values if q["allow_multiple"] else values[0]
        elif q["type"] == "rating":
            if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
                raise ValueError(f"Give a whole-number rating for: {q['text']}")
            if not q["scale_min"] <= value <= q["scale_max"]:
                raise ValueError(f"Rating out of range for: {q['text']}")
            cleaned[q["id"]] = int(value)
        else:
            text = " ".join(str(value).split())[:2000]
            if text:
                cleaned[q["id"]] = text
            elif q["required"]:
                raise ValueError(f"Please answer: {q['text']}")
    return cleaned


def results(questions: list[dict[str, Any]], responses: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-question statistics computed from real responses."""
    total = len(responses)
    per_question = []
    for q in questions:
        answered = [r[q["id"]] for r in responses if q["id"] in r]
        entry: dict[str, Any] = {"id": q["id"], "type": q["type"], "text": q["text"], "answered": len(answered)}
        if q["type"] == "multiple_choice":
            counts: Counter = Counter()
            for value in answered:
                counts.update(value if isinstance(value, list) else [value])
            entry["options"] = [
                {
                    "option": option,
                    "count": counts.get(option, 0),
                    "percent": round(100 * counts.get(option, 0) / len(answered), 1) if answered else 0.0,
                }
                for option in q["options"]
            ]
        elif q["type"] == "rating":
            counts = Counter(answered)
            entry["distribution"] = [
                {"value": v, "count": counts.get(v, 0)} for v in range(q["scale_min"], q["scale_max"] + 1)
            ]
            entry["average"] = round(sum(answered) / len(answered), 2) if answered else None
            entry["scale_min"], entry["scale_max"] = q["scale_min"], q["scale_max"]
            entry["scale_min_label"], entry["scale_max_label"] = q["scale_min_label"], q["scale_max_label"]
        else:
            entry["answers"] = answered
        per_question.append(entry)
    return {"total_responses": total, "questions": per_question}


def _describe(stats: dict[str, Any]) -> str:
    lines = [f"Total real responses: {stats['total_responses']}"]
    for q in stats["questions"]:
        lines.append(f"\n[{q['id']}] ({q['type']}) {q['text']} — answered by {q['answered']}")
        if q["type"] == "multiple_choice":
            lines += [f"  - {o['option']}: {o['count']} ({o['percent']}%)" for o in q["options"]]
        elif q["type"] == "rating":
            dist = ", ".join(f"{d['value']}: {d['count']}" for d in q["distribution"])
            lines.append(f"  average {q['average']} on {q['scale_min']}-{q['scale_max']} ({dist})")
        else:
            lines += [f'  - "{a[:250]}"' for a in q["answers"][:15]]
    return "\n".join(lines)


def analyse(questions: list[dict[str, Any]], responses: list[dict[str, Any]], campaign_context: str = "") -> dict[str, Any]:
    if not responses:
        raise ValueError("This survey has no responses yet. Share the link and analyse once people have answered.")
    stats = results(questions, responses)
    campaign = f", relating them to this campaign where relevant: {campaign_context}" if campaign_context else ""
    insights = call_structured(
        INSIGHT_PROMPT.format(campaign=campaign, small=SMALL_SAMPLE), _describe(stats), "survey_insights", INSIGHT_SCHEMA
    )
    open_texts = [a for q in stats["questions"] if q["type"] == "open_ended" for a in q.get("answers", [])]
    open_sentiment = sentiment.analyse(open_texts, campaign_context) if open_texts else None
    return {
        "stats": stats,
        "insights": insights,
        "open_ended_sentiment": open_sentiment,
        "small_sample": stats["total_responses"] <= SMALL_SAMPLE,
    }
