"""
Skill: News
============
Fetches top headlines from NewsAPI.org with optional category filtering.

Requires environment variable NEWSAPI_KEY with a free-tier key
from https://newsapi.org/register.  If no key is set the skill falls
back to a simple web search via JARVIS's built-in search capability.
"""

from __future__ import annotations

import os

import httpx

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

NEWSAPI_BASE = "https://newsapi.org/v2"

# Mapping of user-friendly category names to NewsAPI slugs
_CATEGORIES = {
    "tech": "technology",
    "technology": "technology",
    "science": "science",
    "business": "business",
    "general": "general",
    "entertainment": "entertainment",
    "health": "health",
    "sports": "sports",
}


def _api_key(context: SkillContext) -> str | None:
    return os.getenv("NEWSAPI_KEY") or context.parameters.get("api_key")


def _resolve_category(raw: str) -> str | None:
    return _CATEGORIES.get(raw.lower().strip())


def _format_headline(article: dict, idx: int) -> str:
    source = article.get("source", {}).get("name", "Unknown")
    title = article.get("title", "No title")
    url = article.get("url", "")
    return f"{idx}. {title}\n   Source: {source}\n   {url}"


async def _fetch_newsapi(
    client: httpx.AsyncClient,
    key: str,
    category: str | None,
    country: str = "us",
) -> list[dict]:
    params: dict = {
        "apiKey": key,
        "country": country,
        "pageSize": 5,
    }
    if category:
        params["category"] = category

    resp = await client.get(f"{NEWSAPI_BASE}/top-headlines", params=params)
    resp.raise_for_status()
    return resp.json().get("articles", [])


async def _fallback_search(
    context: SkillContext,
    category: str | None,
) -> SkillResult:
    """Use JARVIS built-in web search when no API key is available."""
    query = "top news headlines"
    if category:
        query = f"{category} news headlines"

    # Delegate to the core search if available
    if hasattr(context, "search"):
        results = await context.search(query, num_results=5)
        lines = [f"{i+1}. {r.get('title', r.get('snippet', 'Result'))}" for i, r in enumerate(results)]
        return SkillResult(
            success=True,
            output=f"Top headlines (via web search):\n\n" + "\n\n".join(lines),
            metadata={"source": "web_search", "query": query},
        )

    return SkillResult(
        success=False,
        error=(
            "NEWSAPI_KEY not set and no built-in search available. "
            "Set NEWSAPI_KEY or pass api_key in parameters."
        ),
    )


class NewsSkill(BaseSkill):
    """Fetches top news headlines with optional category filtering.

    Example:
        User: "What's in the news today?"
        JARVIS: "1. Breaking: ...\n   Source: Reuters ..."

        User: "Show me tech news"
        JARVIS: "1. AI advances ...\n   Source: TechCrunch ..."
    """

    metadata = SkillMetadata(
        name="news",
        version="1.0.0",
        description="Top headlines via NewsAPI.org with category filtering",
        author="JARVIS Team",
        tags=["news", "headlines"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        raw_category = context.parameters.get("category", "")
        category = _resolve_category(raw_category) if raw_category else None

        key = _api_key(context)

        # If no API key, try fallback search
        if not key:
            return await _fallback_search(context, category)

        country = context.parameters.get("country", "us")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                articles = await _fetch_newsapi(client, key, category, country)
            except httpx.HTTPStatusError as exc:
                return SkillResult(
                    success=False,
                    error=f"NewsAPI error: {exc.response.status_code}",
                )

        if not articles:
            return SkillResult(
                success=True,
                output="No headlines found for that category/country.",
                metadata={"category": category, "country": country},
            )

        lines = [_format_headline(a, i + 1) for i, a in enumerate(articles[:5])]
        summary = f"Top headlines" + (f" ({category})" if category else "") + ":\n\n"
        summary += "\n\n".join(lines)

        return SkillResult(
            success=True,
            output=summary,
            metadata={
                "category": category,
                "country": country,
                "count": len(articles[:5]),
            },
        )
