"""Live web search through the Brave Search API (optional).

Set BRAVE_SEARCH_API_KEY in .env (https://api-dashboard.search.brave.com) to
enable it. Without a key, ``is_configured()`` is False and the research agents
use only the company documents and what the user supplies, and say so.
"""

import html
import logging
import os
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class WebSearchError(RuntimeError):
    """The search provider could not be reached or rejected the request."""


@dataclass
class WebResult:
    title: str
    url: str
    description: str
    age: str | None  # how old the page is, as reported by the provider


def _api_key() -> str:
    return os.getenv("BRAVE_SEARCH_API_KEY", "").strip()


def is_configured() -> bool:
    return bool(_api_key())


def provider_status() -> dict[str, object]:
    return {"provider": "brave" if is_configured() else None, "configured": is_configured()}


_TAG = re.compile(r"<[^>]+>")


def _plain(text: str) -> str:
    return html.unescape(_TAG.sub("", text or "")).strip()


def search(query: str, count: int = 5) -> list[WebResult]:
    """Return up to `count` web results for `query`. Raises WebSearchError."""
    key = _api_key()
    if not key:
        raise WebSearchError("BRAVE_SEARCH_API_KEY is not set")
    try:
        response = httpx.get(
            BRAVE_ENDPOINT,
            params={"q": query[:400], "count": max(1, min(count, 20))},
            headers={"Accept": "application/json", "X-Subscription-Token": key},
            timeout=float(os.getenv("WEB_SEARCH_TIMEOUT", "15")),
        )
    except httpx.HTTPError as error:
        raise WebSearchError(f"Brave Search unreachable: {error.__class__.__name__}") from error
    if response.status_code != 200:
        raise WebSearchError(f"Brave Search returned HTTP {response.status_code}")

    results = response.json().get("web", {}).get("results", [])
    logger.info("Brave Search %r: %d result(s)", query, len(results))
    return [
        WebResult(
            title=_plain(item.get("title", "")),
            url=item.get("url", ""),
            description=_plain(item.get("description", "")),
            age=item.get("age") or item.get("page_age"),
        )
        for item in results
        if item.get("url")
    ]
