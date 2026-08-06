"""
Content extraction for JARVIS browser automation.
==================================================
Read webpages, extract structured content, compare pages,
and generate summaries.

Usage:
    content = ContentExtractor(manager, config)
    page_data = await content.read_page()
    summary = await content.summarize_page()
    comparison = await content.compare_pages(url1, url2)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult, PageContent

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract and analyze web page content.

    Example:
        extractor = ContentExtractor(manager, config)
        result = await extractor.read_page()
        text = result.data["text"]
        summary = await extractor.summarize_page(max_chars=1000)
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config

    @property
    def _page(self) -> Any | None:
        return self._manager.page

    async def read_page(self, extract_links: bool = True, extract_images: bool = True) -> BrowserResult:
        """Read and extract structured content from the current page.

        Args:
            extract_links: Include link extraction.
            extract_images: Include image extraction.

        Returns:
            BrowserResult with PageContent data.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            title = await self._page.title()
            url = self._page.url

            text = await self._page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('script, style, noscript, iframe');
                    const clone = document.body.cloneNode(true);
                    elements.forEach(el => clone.removeChild(el));
                    return clone.innerText || '';
                }
            """)

            html = await self._page.content()

            meta = await self._page.evaluate("""
                () => {
                    const metas = {};
                    document.querySelectorAll('meta[name], meta[property]').forEach(m => {
                        const key = m.getAttribute('name') || m.getAttribute('property');
                        metas[key] = m.getAttribute('content') || '';
                    });
                    return metas;
                }
            """)

            headings = await self._page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                        level: parseInt(h.tagName[1]),
                        text: h.innerText.trim()
                    }));
                }
            """)

            links = []
            if extract_links:
                links = await self._page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a[href]')).slice(0, 100).map(a => ({
                            text: a.innerText.trim().substring(0, 100),
                            href: a.href,
                            title: a.title || ''
                        }));
                    }
                """)

            images = []
            if extract_images:
                images = await self._page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('img[src]')).slice(0, 50).map(img => ({
                            src: img.src,
                            alt: img.alt || '',
                            width: img.naturalWidth,
                            height: img.naturalHeight
                        }));
                    }
                """)

            forms = await self._page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('form')).map(f => ({
                        action: f.action,
                        method: f.method,
                        id: f.id || '',
                        inputs: Array.from(f.querySelectorAll('input, select, textarea')).map(i => ({
                            type: i.type || 'text',
                            name: i.name || '',
                            id: i.id || '',
                            placeholder: i.placeholder || ''
                        }))
                    }));
                }
            """)

            word_count = len(text.split())

            content = PageContent(
                url=url,
                title=title,
                text=text.strip(),
                html=html,
                meta=meta,
                links=links,
                images=images,
                forms=forms,
                headings=headings,
                word_count=word_count,
            )

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Page read: {title} ({word_count} words)",
                url=url,
                title=title,
                data=content.to_dict(),
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Read page failed: %s", exc)
            return BrowserResult(success=False, message=f"Read failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def get_text(self) -> BrowserResult:
        """Get plain text content of the page."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            text = await self._page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('script, style, noscript');
                    const clone = document.body.cloneNode(true);
                    elements.forEach(el => clone.removeChild(el));
                    return clone.innerText || '';
                }
            """)
            return BrowserResult(
                success=True,
                message=f"Extracted {len(text)} chars",
                data={"text": text.strip()},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get text failed: {exc}")

    async def get_html(self) -> BrowserResult:
        """Get full HTML content."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            html = await self._page.content()
            return BrowserResult(
                success=True,
                message=f"Extracted {len(html)} chars HTML",
                data={"html": html},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get HTML failed: {exc}")

    async def get_links(self, filter_domain: str = "") -> BrowserResult:
        """Extract all links from the page."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            js = """
                () => {
                    return Array.from(document.querySelectorAll('a[href]')).map(a => ({
                        text: a.innerText.trim().substring(0, 200),
                        href: a.href,
                        title: a.title || '',
                        is_external: !a.href.startsWith(window.location.origin)
                    }));
                }
            """
            links = await self._page.evaluate(js)

            if filter_domain:
                links = [l for l in links if filter_domain in l.get("href", "")]

            return BrowserResult(
                success=True,
                message=f"Found {len(links)} links",
                data=links[:200],
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get links failed: {exc}")

    async def search_page(self, query: str) -> BrowserResult:
        """Search for text within the current page.

        Args:
            query: Text to search for.

        Returns:
            BrowserResult with matching text snippets.
        """
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            matches = await self._page.evaluate(f"""
                () => {{
                    const results = [];
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    let node;
                    while (node = walker.nextNode()) {{
                        const text = node.textContent;
                        const idx = text.toLowerCase().indexOf('{query.lower()}');
                        if (idx >= 0) {{
                            const start = Math.max(0, idx - 50);
                            const end = Math.min(text.length, idx + query.length + 50);
                            results.push(text.substring(start, end).trim());
                        }}
                    }}
                    return results.slice(0, 20);
                }}
            """)

            return BrowserResult(
                success=True,
                message=f"Found {len(matches)} matches for '{query}'",
                data={"query": query, "matches": matches},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Search failed: {exc}")

    async def summarize_page(self, max_chars: int = 2000) -> BrowserResult:
        """Create a summary of the current page.

        Args:
            max_chars: Maximum characters in summary.

        Returns:
            BrowserResult with summary text.
        """
        read_result = await self.read_page(extract_links=False, extract_images=False)
        if not read_result.success:
            return read_result

        try:
            content = read_result.data
            title = content.get("title", "")
            url = content.get("url", "")
            text = content.get("text", "")
            headings = content.get("headings", [])
            meta = content.get("meta", {})

            parts = [f"Title: {title}", f"URL: {url}"]

            desc = meta.get("description", "") or meta.get("og:description", "")
            if desc:
                parts.append(f"Description: {desc}")

            if headings:
                heading_text = " | ".join(h["text"] for h in headings[:10])
                parts.append(f"Headings: {heading_text}")

            if text:
                sentences = re.split(r'[.!?]+', text)
                sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
                summary_text = ". ".join(sentences[:15])
                if len(summary_text) > max_chars:
                    summary_text = summary_text[:max_chars] + "..."
                parts.append(f"\nSummary:\n{summary_text}")

            return BrowserResult(
                success=True,
                message=f"Page summarized ({len(text)} chars -> {len(summary_text) if 'summary_text' in dir() else 0} chars)",
                data={"summary": "\n".join(parts)},
            )

        except Exception as exc:
            return BrowserResult(success=False, message=f"Summarize failed: {exc}")

    async def compare_pages(self, url1: str, url2: str) -> BrowserResult:
        """Compare content of two pages.

        Args:
            url1: First page URL.
            url2: Second page URL.

        Returns:
            BrowserResult with comparison data.
        """
        start = time.perf_counter()

        try:
            current_url = self._page.url if self._page else ""

            page1_result = await self._manager.navigation.goto(url1)
            if not page1_result.success:
                return BrowserResult(success=False, message=f"Failed to load page 1: {url1}")

            content1_result = await self.read_page(extract_links=False, extract_images=False)
            content1 = content1_result.data if content1_result.success else {}

            page2_result = await self._manager.navigation.goto(url2)
            if not page2_result.success:
                return BrowserResult(success=False, message=f"Failed to load page 2: {url2}")

            content2_result = await self.read_page(extract_links=False, extract_images=False)
            content2 = content2_result.data if content2_result.success else {}

            if current_url:
                await self._manager.navigation.goto(current_url)

            text1 = content1.get("text", "")
            text2 = content2.get("text", "")
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
            common = words1 & words2
            unique1 = words1 - words2
            unique2 = words2 - words1

            total = max(len(words1 | words2), 1)
            similarity = len(common) / total

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Pages compared (similarity: {similarity:.1%})",
                data={
                    "page1": {"url": url1, "title": content1.get("title", ""), "word_count": content1.get("word_count", 0)},
                    "page2": {"url": url2, "title": content2.get("title", ""), "word_count": content2.get("word_count", 0)},
                    "similarity": round(similarity, 4),
                    "common_words": len(common),
                    "unique_to_page1": len(unique1),
                    "unique_to_page2": len(unique2),
                },
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Compare failed: {exc}", duration_ms=elapsed)

    async def extract_table(self, table_selector: str = "table") -> BrowserResult:
        """Extract data from an HTML table."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            data = await self._page.evaluate(f"""
                () => {{
                    const table = document.querySelector('{table_selector}');
                    if (!table) return null;
                    const rows = Array.from(table.querySelectorAll('tr'));
                    return rows.map(row => {{
                        const cells = Array.from(row.querySelectorAll('th, td'));
                        return cells.map(cell => cell.innerText.trim());
                    }});
                }}
            """)

            if not data:
                return BrowserResult(success=False, message="No table found")

            return BrowserResult(
                success=True,
                message=f"Extracted table ({len(data)} rows)",
                data={"rows": data},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Table extraction failed: {exc}")
