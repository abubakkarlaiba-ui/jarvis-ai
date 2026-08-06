"""
Web navigation for JARVIS browser automation.
==============================================
Open URLs, navigate history, reload, and search Google.

Usage:
    nav = Navigation(manager, config)
    await nav.goto("https://google.com")
    await nav.search_google("JARVIS AI")
    await nav.back()
    await nav.reload()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


class Navigation:
    """Navigate web pages with the browser manager.

    Example:
        nav = Navigation(manager, config)
        await nav.goto("https://example.com")
        await nav.search_google("weather today")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config

    @property
    def _page(self) -> Any | None:
        return self._manager.page

    async def goto(self, url: str, wait_until: str = "domcontentloaded") -> BrowserResult:
        """Navigate to a URL.

        Args:
            url: Target URL.
            wait_until: Playwright wait condition (load, domcontentloaded, networkidle).

        Returns:
            BrowserResult with page info.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            if not url.startswith(("http://", "https://", "about:", "javascript:")):
                url = "https://" + url

            response = await self._page.goto(url, wait_until=wait_until, timeout=self._config.timeout_ms)

            title = await self._page.title()
            elapsed = (time.perf_counter() - start) * 1000

            status = response.status if response else 0
            return BrowserResult(
                success=True,
                message=f"Navigated to {url} (HTTP {status})",
                url=self._page.url,
                title=title,
                data={"status": status},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Navigation failed: %s", exc)
            return BrowserResult(
                success=False,
                message=f"Navigation failed: {exc}",
                error=str(exc),
                duration_ms=elapsed,
            )

    async def search_google(self, query: str) -> BrowserResult:
        """Search Google with a query.

        Args:
            query: Search query string.

        Returns:
            BrowserResult with search results page.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            response = await self._page.goto(url, wait_until="domcontentloaded", timeout=self._config.timeout_ms)

            title = await self._page.title()
            elapsed = (time.perf_counter() - start) * 1000

            return BrowserResult(
                success=True,
                message=f"Google search: {query}",
                url=self._page.url,
                title=title,
                data={"query": query, "status": response.status if response else 0},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Search failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def back(self) -> BrowserResult:
        """Go back in browser history."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.go_back(timeout=self._config.timeout_ms)
            title = await self._page.title()
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message="Navigated back",
                url=self._page.url,
                title=title,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Back failed: {exc}", duration_ms=elapsed)

    async def forward(self) -> BrowserResult:
        """Go forward in browser history."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.go_forward(timeout=self._config.timeout_ms)
            title = await self._page.title()
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message="Navigated forward",
                url=self._page.url,
                title=title,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Forward failed: {exc}", duration_ms=elapsed)

    async def reload(self, wait_until: str = "domcontentloaded") -> BrowserResult:
        """Reload the current page."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.reload(wait_until=wait_until, timeout=self._config.timeout_ms)
            title = await self._page.title()
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message="Page reloaded",
                url=self._page.url,
                title=title,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Reload failed: {exc}", duration_ms=elapsed)

    async def wait_for_load(self, state: str = "domcontentloaded", timeout_ms: int = 0) -> BrowserResult:
        """Wait for page load state.

        Args:
            state: Load state to wait for (load, domcontentloaded, networkidle).
            timeout_ms: Timeout override.
        """
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.wait_for_load_state(
                state=state,
                timeout=timeout_ms or self._config.timeout_ms,
            )
            title = await self._page.title()
            return BrowserResult(
                success=True,
                message=f"Page loaded ({state})",
                url=self._page.url,
                title=title,
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Wait failed: {exc}")

    async def wait_for_url(self, url_pattern: str, timeout_ms: int = 0) -> BrowserResult:
        """Wait for URL to match a pattern."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.wait_for_url(url_pattern, timeout=timeout_ms or self._config.timeout_ms)
            title = await self._page.title()
            return BrowserResult(
                success=True,
                message=f"URL matched: {self._page.url}",
                url=self._page.url,
                title=title,
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"URL wait failed: {exc}")

    async def get_current_url(self) -> str:
        """Get the current page URL."""
        if self._page:
            return self._page.url
        return ""

    async def get_title(self) -> str:
        """Get the current page title."""
        if self._page:
            return await self._page.title()
        return ""
