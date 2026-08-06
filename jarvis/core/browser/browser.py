"""
Unified browser engine for JARVIS.
====================================
Wires together all browser automation subsystems into a single
cohesive API surface.

Subsystems:
    - BrowserManager — session, tabs, cookies, persistence
    - Navigation — open, search, back/forward, reload
    - Interaction — fill forms, click, scroll, select
    - FileOperations — download, upload files
    - LoginAutomation — credential store, login/logout
    - ContentExtractor — read, summarize, compare pages
    - PageMonitor — watch for changes
    - ScreenshotCapture — full page, element, viewport screenshots

Usage:
    browser = BrowserEngine(settings)
    await browser.initialize()
    await browser.open("https://google.com")
    await browser.search_google("JARVIS AI assistant")
    await browser.screenshot()
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from jarvis.config.settings import BrowserSettings
from jarvis.core.browser.base import BrowserConfig, BrowserResult, PageContent
from jarvis.core.browser.browser_manager import BrowserManager
from jarvis.core.browser.navigation import Navigation
from jarvis.core.browser.interaction import Interaction
from jarvis.core.browser.file_ops import FileOperations as BrowserFileOps
from jarvis.core.browser.auth import LoginAutomation
from jarvis.core.browser.content import ContentExtractor
from jarvis.core.browser.monitor import PageMonitor
from jarvis.core.browser.screenshots import ScreenshotCapture

logger = logging.getLogger(__name__)


class BrowserEngine:
    """Unified browser automation engine for JARVIS.

    Provides a single interface to all browser capabilities while
    maintaining session persistence and safety controls.

    Example:
        browser = BrowserEngine(settings)
        await browser.initialize()

        # Navigation
        await browser.open("https://example.com")
        await browser.search_google("weather today")

        # Interaction
        await browser.fill("input#q", "search term")
        await browser.click("button[type='submit']")

        # Content
        content = await browser.read_page()
        summary = await browser.summarize_page()

        # Downloads
        await browser.download("a.download-link", "file.zip")

        # Screenshots
        await browser.screenshot("page.png")
    """

    def __init__(self, settings: BrowserSettings):
        self._settings = settings
        self._config = BrowserConfig(
            headless=settings.headless,
            slow_mo=settings.slow_mo,
            timeout_ms=settings.timeout_ms,
            viewport_width=settings.viewport_width,
            viewport_height=settings.viewport_height,
            user_data_dir=settings.user_data_dir,
            downloads_dir=settings.downloads_dir,
            screenshots_dir=settings.screenshots_dir,
            persistent_context=settings.persistent_context,
            chromium_channel=settings.chromium_channel,
            proxy=settings.proxy,
            user_agent=settings.user_agent,
            locale=settings.locale,
            timezone_id=settings.timezone_id,
            ignore_https_errors=settings.ignore_https_errors,
            blocked_domains=settings.blocked_domains,
        )
        self._manager: BrowserManager | None = None
        self.navigation: Navigation | None = None
        self.interaction: Interaction | None = None
        self.files: BrowserFileOps | None = None
        self.auth: LoginAutomation | None = None
        self.content: ContentExtractor | None = None
        self.monitor: PageMonitor | None = None
        self.screenshots: ScreenshotCapture | None = None
        self._initialized = False

    async def initialize(self) -> BrowserResult:
        """Initialize the browser and all subsystems."""
        if self._initialized:
            return BrowserResult(success=True, message="Already initialized")

        self._manager = BrowserManager(self._config)
        result = await self._manager.launch()

        if not result.success:
            return result

        self.navigation = Navigation(self._manager, self._config)
        self.interaction = Interaction(self._manager, self._config)
        self.files = BrowserFileOps(self._manager, self._config)
        self.auth = LoginAutomation(self._manager, self._config)
        self.content = ContentExtractor(self._manager, self._config)
        self.monitor = PageMonitor(self._manager, self._config)
        self.screenshots = ScreenshotCapture(self._manager, self._config)

        self._initialized = True
        logger.info("Browser engine initialized")
        return BrowserResult(success=True, message="Browser engine initialized")

    async def shutdown(self) -> None:
        """Shut down the browser engine."""
        if self._manager:
            await self.monitor.stop_all_watches()
            await self._manager.shutdown()
        self._initialized = False

    # ──────────────────────────────────────────────
    # Navigation shortcuts
    # ──────────────────────────────────────────────

    async def open(self, url: str) -> BrowserResult:
        return await self.navigation.goto(url)

    async def search_google(self, query: str) -> BrowserResult:
        return await self.navigation.search_google(query)

    async def back(self) -> BrowserResult:
        return await self.navigation.back()

    async def forward(self) -> BrowserResult:
        return await self.navigation.forward()

    async def reload(self) -> BrowserResult:
        return await self.navigation.reload()

    async def get_url(self) -> str:
        return await self.navigation.get_current_url()

    async def get_title(self) -> str:
        return await self.navigation.get_title()

    # ──────────────────────────────────────────────
    # Tab management shortcuts
    # ──────────────────────────────────────────────

    async def new_tab(self, url: str = "") -> BrowserResult:
        return await self._manager.new_tab(url)

    async def close_tab(self, index: int | None = None) -> BrowserResult:
        return await self._manager.close_tab(index)

    async def switch_tab(self, index: int) -> BrowserResult:
        return await self._manager.switch_tab(index)

    async def list_tabs(self) -> BrowserResult:
        return await self._manager.list_tabs()

    # ──────────────────────────────────────────────
    # Interaction shortcuts
    # ──────────────────────────────────────────────

    async def click(self, selector: str) -> BrowserResult:
        return await self.interaction.click(selector)

    async def fill(self, selector: str, value: str) -> BrowserResult:
        return await self.interaction.fill(selector, value)

    async def type(self, selector: str, text: str) -> BrowserResult:
        return await self.interaction.type_text(selector, text)

    async def select(self, selector: str, value: str) -> BrowserResult:
        return await self.interaction.select(selector, value)

    async def scroll_down(self, pixels: int = 500) -> BrowserResult:
        return await self.interaction.scroll_down(pixels)

    async def scroll_up(self, pixels: int = 500) -> BrowserResult:
        return await self.interaction.scroll_up(pixels)

    async def get_text(self, selector: str) -> BrowserResult:
        return await self.interaction.get_text(selector)

    async def press_key(self, key: str) -> BrowserResult:
        return await self.interaction.press_key(key)

    async def evaluate(self, js: str) -> BrowserResult:
        return await self.interaction.evaluate(js)

    # ──────────────────────────────────────────────
    # Content shortcuts
    # ──────────────────────────────────────────────

    async def read_page(self) -> BrowserResult:
        return await self.content.read_page()

    async def summarize_page(self, max_chars: int = 2000) -> BrowserResult:
        return await self.content.summarize_page(max_chars)

    async def search_page(self, query: str) -> BrowserResult:
        return await self.content.search_page(query)

    async def compare_pages(self, url1: str, url2: str) -> BrowserResult:
        return await self.content.compare_pages(url1, url2)

    async def extract_links(self, domain: str = "") -> BrowserResult:
        return await self.content.get_links(domain)

    async def extract_table(self, selector: str = "table") -> BrowserResult:
        return await self.content.extract_table(selector)

    # ──────────────────────────────────────────────
    # File operation shortcuts
    # ──────────────────────────────────────────────

    async def download(self, selector: str, filename: str | None = None) -> BrowserResult:
        return await self.files.download_link(selector, filename)

    async def download_url(self, url: str, filename: str | None = None) -> BrowserResult:
        return await self.files.download_url(url, filename)

    async def upload(self, selector: str, file_path: str) -> BrowserResult:
        return await self.files.upload_file(selector, file_path)

    # ──────────────────────────────────────────────
    # Auth shortcuts
    # ──────────────────────────────────────────────

    async def login(self, domain: str, username: str = "", password: str = "", **kwargs) -> BrowserResult:
        return await self.auth.login(domain, username=username, password=password, **kwargs)

    async def save_credentials(self, domain: str, username: str, password: str) -> BrowserResult:
        return await self.auth.save_credentials(domain, username, password)

    async def check_login(self, domain: str) -> BrowserResult:
        return await self.auth.check_login_status(domain)

    async def logout(self, domain: str) -> BrowserResult:
        return await self.auth.logout(domain)

    # ──────────────────────────────────────────────
    # Screenshot shortcuts
    # ──────────────────────────────────────────────

    async def screenshot(self, save_path: str | None = None) -> BrowserResult:
        return await self.screenshots.full_page(save_path)

    async def screenshot_viewport(self, save_path: str | None = None) -> BrowserResult:
        return await self.screenshots.viewport(save_path)

    async def screenshot_element(self, selector: str, save_path: str | None = None) -> BrowserResult:
        return await self.screenshots.element(selector, save_path)

    async def save_as_pdf(self, save_path: str | None = None) -> BrowserResult:
        return await self.screenshots.pdf(save_path)

    # ──────────────────────────────────────────────
    # Monitor shortcuts
    # ──────────────────────────────────────────────

    async def watch_page(self, url: str, interval: int = 30, callback: Any = None) -> BrowserResult:
        return await self.monitor.watch_url(url, interval_seconds=interval, callback=callback)

    async def stop_watching(self, url: str) -> BrowserResult:
        return await self.monitor.stop_watching(url)

    async def check_changes(self, url: str) -> BrowserResult:
        return await self.monitor.check_for_changes(url)

    # ──────────────────────────────────────────────
    # Session shortcuts
    # ──────────────────────────────────────────────

    async def save_session(self) -> BrowserResult:
        return await self._manager.save_session()

    async def restore_session(self) -> BrowserResult:
        return await self._manager.restore_session()

    async def set_cookies(self, cookies: list[dict]) -> BrowserResult:
        return await self._manager.set_cookies(cookies)

    async def get_cookies(self, domain: str = "") -> BrowserResult:
        return await self._manager.get_cookies(domain)

    async def clear_cookies(self, domain: str = "") -> BrowserResult:
        return await self._manager.clear_cookies(domain)
