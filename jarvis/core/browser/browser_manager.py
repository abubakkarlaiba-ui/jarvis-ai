"""
Browser manager for session persistence and tab management.
===========================================================
Handles browser lifecycle, persistent contexts, tabs, cookies,
and session save/restore.

Usage:
    manager = BrowserManager(config)
    await manager.launch()
    await manager.new_tab("https://google.com")
    tabs = await manager.list_tabs()
    await manager.save_session()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult, TabInfo, CookieInfo

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manage browser lifecycle, tabs, cookies, and sessions.

    Example:
        config = BrowserConfig(headless=False)
        manager = BrowserManager(config)
        await manager.launch()
        page = await manager.new_tab("https://example.com")
    """

    def __init__(self, config: BrowserConfig):
        self._config = config
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._pages: list[Any] = []
        self._active_index: int = 0
        self._session_file = Path(config.user_data_dir) / "session.json"
        self._cookies_file = Path(config.user_data_dir) / "cookies.json"
        self._initialized = False

    @property
    def page(self) -> Any | None:
        """Get the active page."""
        if 0 <= self._active_index < len(self._pages):
            return self._pages[self._active_index]
        return None

    @property
    def pages(self) -> list[Any]:
        return self._pages

    async def launch(self) -> BrowserResult:
        """Launch the browser with persistent context."""
        start = time.perf_counter()
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

            user_data = Path(self._config.user_data_dir)
            user_data.mkdir(parents=True, exist_ok=True)

            downloads = Path(self._config.downloads_dir)
            downloads.mkdir(parents=True, exist_ok=True)

            launch_args = {
                "headless": self._config.headless,
                "slow_mo": self._config.slow_mo,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    f"--download-default-directory={downloads}",
                ],
            }

            if self._config.proxy:
                launch_args["proxy"] = {"server": self._config.proxy}

            if self._config.persistent_context:
                self._context = await self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data),
                    channel=self._config.chromium_channel,
                    viewport={"width": self._config.viewport_width, "height": self._config.viewport_height},
                    locale=self._config.locale,
                    timezone_id=self._config.timezone_id,
                    ignore_https_errors=self._config.ignore_https_errors,
                    java_script_enabled=self._config.java_script_enabled,
                    extra_http_headers=self._config.extra_http_headers or None,
                    user_agent=self._config.user_agent,
                    accept_downloads=True,
                    **launch_args,
                )
                self._pages = list(self._context.pages)
                if not self._pages:
                    self._pages.append(await self._context.new_page())
            else:
                browser = await self._playwright.chromium.launch(**launch_args)
                self._context = await browser.new_context(
                    viewport={"width": self._config.viewport_width, "height": self._config.viewport_height},
                    locale=self._config.locale,
                    timezone_id=self._config.timezone_id,
                    ignore_https_errors=self._config.ignore_https_errors,
                    user_agent=self._config.user_agent,
                    accept_downloads=True,
                )
                self._browser = browser
                page = await self._context.new_page()
                self._pages = [page]

            self._active_index = 0
            self._initialized = True

            if self._config.blocked_domains:
                await self._context.route("**/*", self._route_handler)

            elapsed = (time.perf_counter() - start) * 1000
            logger.info("Browser launched (headless=%s)", self._config.headless)
            return BrowserResult(
                success=True,
                message="Browser launched",
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Browser launch failed: %s", exc)
            return BrowserResult(
                success=False,
                message=f"Launch failed: {exc}",
                error=str(exc),
                duration_ms=elapsed,
            )

    async def shutdown(self) -> None:
        """Close browser and save session."""
        try:
            await self.save_session()
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
            self._initialized = False
            logger.info("Browser shut down")
        except Exception as exc:
            logger.debug("Shutdown error: %s", exc)

    async def new_tab(self, url: str = "about:blank") -> BrowserResult:
        """Open a new tab.

        Args:
            url: Initial URL for the new tab.

        Returns:
            BrowserResult with tab info.
        """
        start = time.perf_counter()
        try:
            page = await self._context.new_page()
            self._pages.append(page)
            self._active_index = len(self._pages) - 1

            if url and url != "about:blank":
                await page.goto(url, wait_until="domcontentloaded", timeout=self._config.timeout_ms)

            elapsed = (time.perf_counter() - start) * 1000
            title = await page.title()
            return BrowserResult(
                success=True,
                message=f"New tab opened: {url}",
                url=page.url,
                title=title,
                data={"tab_index": self._active_index},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"New tab failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def close_tab(self, index: int | None = None) -> BrowserResult:
        """Close a tab by index.

        Args:
            index: Tab index to close (None = active tab).
        """
        start = time.perf_counter()
        idx = index if index is not None else self._active_index

        if idx < 0 or idx >= len(self._pages):
            return BrowserResult(success=False, message=f"Tab {idx} not found")

        try:
            page = self._pages[idx]
            await page.close()
            self._pages.pop(idx)

            if self._active_index >= len(self._pages):
                self._active_index = max(0, len(self._pages) - 1)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Tab {idx} closed",
                data={"tab_index": idx},
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Close tab failed: {exc}", duration_ms=elapsed)

    async def switch_tab(self, index: int) -> BrowserResult:
        """Switch to a tab by index."""
        if index < 0 or index >= len(self._pages):
            return BrowserResult(success=False, message=f"Tab {index} not found")

        self._active_index = index
        page = self._pages[index]
        title = await page.title()
        return BrowserResult(
            success=True,
            message=f"Switched to tab {index}",
            url=page.url,
            title=title,
            data={"tab_index": index},
        )

    async def list_tabs(self) -> BrowserResult:
        """List all open tabs."""
        tabs = []
        for i, page in enumerate(self._pages):
            try:
                title = await page.title()
                tabs.append(TabInfo(
                    index=i,
                    url=page.url,
                    title=title,
                    is_active=(i == self._active_index),
                ))
            except Exception:
                tabs.append(TabInfo(index=i, url="about:blank", title="(loading)"))

        return BrowserResult(
            success=True,
            message=f"{len(tabs)} tabs open",
            data=[t.to_dict() for t in tabs],
        )

    async def set_cookies(self, cookies: list[dict]) -> BrowserResult:
        """Set cookies on the browser context.

        Args:
            cookies: List of cookie dicts with name, value, domain, etc.
        """
        try:
            await self._context.add_cookies(cookies)
            return BrowserResult(
                success=True,
                message=f"Set {len(cookies)} cookies",
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Set cookies failed: {exc}")

    async def get_cookies(self, domain: str = "") -> BrowserResult:
        """Get cookies, optionally filtered by domain."""
        try:
            cookies = await self._context.cookies()
            if domain:
                cookies = [c for c in cookies if domain in c.get("domain", "")]
            items = [CookieInfo(
                name=c["name"],
                value=c["value"],
                domain=c.get("domain", ""),
                path=c.get("path", "/"),
                expires=c.get("expires", -1),
                http_only=c.get("httpOnly", False),
                secure=c.get("secure", False),
                same_site=c.get("sameSite", "Lax"),
            ) for c in cookies]
            return BrowserResult(
                success=True,
                message=f"{len(items)} cookies",
                data=[c.to_dict() for c in items],
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get cookies failed: {exc}")

    async def clear_cookies(self, domain: str = "") -> BrowserResult:
        """Clear cookies, optionally by domain."""
        try:
            if domain:
                cookies = await self._context.cookies()
                for c in cookies:
                    if domain in c.get("domain", ""):
                        await self._context.clear_cookies()
                        break
            else:
                await self._context.clear_cookies()
            return BrowserResult(success=True, message="Cookies cleared")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Clear cookies failed: {exc}")

    async def save_session(self) -> BrowserResult:
        """Save session state (tabs, cookies) to disk."""
        try:
            session_data = {
                "saved_at": time.time(),
                "tabs": [],
                "active_index": self._active_index,
            }
            for i, page in enumerate(self._pages):
                try:
                    title = await page.title()
                    session_data["tabs"].append({
                        "url": page.url,
                        "title": title,
                    })
                except Exception:
                    session_data["tabs"].append({"url": "about:blank", "title": ""})

            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            self._session_file.write_text(
                json.dumps(session_data, indent=2, default=str),
                encoding="utf-8",
            )

            cookies_result = await self.get_cookies()
            if cookies_result.success:
                self._cookies_file.write_text(
                    json.dumps(cookies_result.data, indent=2, default=str),
                    encoding="utf-8",
                )

            return BrowserResult(
                success=True,
                message=f"Session saved ({len(self._pages)} tabs)",
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Save session failed: {exc}")

    async def restore_session(self) -> BrowserResult:
        """Restore session from disk."""
        try:
            if not self._session_file.exists():
                return BrowserResult(success=False, message="No saved session found")

            data = json.loads(self._session_file.read_text(encoding="utf-8"))
            tabs = data.get("tabs", [])

            if not tabs:
                return BrowserResult(success=False, message="No tabs in saved session")

            for tab_data in tabs:
                url = tab_data.get("url", "about:blank")
                await self.new_tab(url)

            if self._pages:
                await self.close_tab(0)

            self._active_index = min(data.get("active_index", 0), len(self._pages) - 1)

            if self._cookies_file.exists():
                try:
                    cookies = json.loads(self._cookies_file.read_text(encoding="utf-8"))
                    await self.set_cookies(cookies)
                except Exception:
                    pass

            return BrowserResult(
                success=True,
                message=f"Session restored ({len(self._pages)} tabs)",
                data={"tabs_count": len(self._pages)},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Restore session failed: {exc}")

    async def _route_handler(self, route) -> None:
        """Block requests to forbidden domains."""
        url = route.request.url
        for domain in self._config.blocked_domains:
            if domain in url:
                await route.abort()
                return
        await route.continue_()
