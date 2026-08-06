"""
Skill: Web Search
=================
Searches the web using DuckDuckGo instant answer API with Google scraping fallback.

Extracts title, snippet, and URL from results. Supports configurable result count.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

import httpx

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

DUCKDUCKGO_API = "https://api.duckduckgo.com/"
GOOGLE_SEARCH_URL = "https://www.google.com/search"


def _extract_google_results(html: str, count: int) -> list[dict]:
    results = []
    pattern = re.compile(
        r'<a[^>]+href="/url\?q=([^&"]+)[^"]*"[^>]*>(.*?)</a>',
        re.DOTALL,
    )
    for match in pattern.finditer(html):
        if len(results) >= count:
            break
        url = match.group(1)
        raw_title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if url.startswith("/search") or not raw_title:
            continue
        snippet_match = re.search(
            r'<span[^>]*class="[^"]*(?:st|aCOpRe)[^"]*"[^>]*>(.*?)</span>',
            html[match.end():match.end() + 500],
            re.DOTALL,
        )
        snippet = ""
        if snippet_match:
            snippet = re.sub(r"<[^>]+>", "", snippet_match.group(1)).strip()
        results.append({"title": raw_title, "snippet": snippet, "url": url})
    return results


async def _search_duckduckgo(
    client: httpx.AsyncClient, query: str, count: int
) -> list[dict]:
    resp = await client.get(
        DUCKDUCKGO_API,
        params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
    )
    resp.raise_for_status()
    data = resp.json()
    results = []
    abstract_text = data.get("AbstractText", "")
    abstract_url = data.get("AbstractURL", "")
    if abstract_text and abstract_url:
        results.append({
            "title": data.get("Heading", query),
            "snippet": abstract_text,
            "url": abstract_url,
        })
    for topic in data.get("RelatedTopics", [])[:count - len(results)]:
        if isinstance(topic, dict) and "Text" in topic:
            results.append({
                "title": topic.get("Text", "")[:80],
                "snippet": topic.get("Text", ""),
                "url": topic.get("FirstURL", ""),
            })
    return results[:count]


async def _search_google(
    client: httpx.AsyncClient, query: str, count: int
) -> list[dict]:
    resp = await client.get(
        GOOGLE_SEARCH_URL,
        params={"q": query, "num": count},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    resp.raise_for_status()
    return _extract_google_results(resp.text, count)


class WebSearchSkill(BaseSkill):
    """Searches the web and returns titles, snippets, and URLs.

    Example:
        User: "Search for Python async tutorials"
        JARVIS: "1. Async IO in Python ...\\n   https://..."
    """

    metadata = SkillMetadata(
        name="web_search",
        version="1.0.0",
        description="Web search via DuckDuckGo with Google fallback",
        author="JARVIS Team",
        tags=["search", "web", "internet", "information"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        query = context.parameters.get("query", context.user_input).strip()
        if not query:
            return SkillResult(success=False, error="No search query provided.")
        count = min(int(context.parameters.get("count", 5)), 20)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                results = await _search_duckduckgo(client, query, count)
            except Exception:
                results = []

            if not results:
                try:
                    results = await _search_google(client, query, count)
                except Exception as exc:
                    return SkillResult(
                        success=False,
                        error=f"Search failed: {exc}",
                    )

        if not results:
            return SkillResult(
                success=True,
                output=f"No results found for: {query}",
                metadata={"query": query, "count": 0},
            )

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r['title']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet'][:200]}")
            lines.append(f"   {r['url']}")
            lines.append("")

        return SkillResult(
            success=True,
            output="\n".join(lines).strip(),
            metadata={
                "query": query,
                "count": len(results),
                "results": results,
            },
        )
