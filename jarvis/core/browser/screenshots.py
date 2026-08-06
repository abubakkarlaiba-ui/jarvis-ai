"""
Screenshot capture for JARVIS browser automation.
===================================================
Capture full-page screenshots, element screenshots,
and viewport screenshots.

Usage:
    screenshots = ScreenshotCapture(manager, config)
    result = await screenshots.full_page("./screenshots/page.png")
    result = await screenshots.element("h1", "./screenshots/header.png")
    result = await screenshots.viewport()
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


class ScreenshotCapture:
    """Capture browser screenshots.

    Example:
        capture = ScreenshotCapture(manager, config)
        result = await capture.full_page("./screenshots/page.png")
        result = await capture.element(".hero", "./screenshots/hero.png")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config
        self._screenshot_dir = Path(config.screenshots_dir)
        self._screenshot_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _page(self) -> Any | None:
        return self._manager.page

    def _timestamp(self) -> str:
        return time.strftime("%Y%m%d_%H%M%S")

    async def full_page(self, save_path: str | None = None) -> BrowserResult:
        """Capture a full-page screenshot.

        Args:
            save_path: Optional save path.

        Returns:
            BrowserResult with screenshot path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            path = save_path or str(self._screenshot_dir / f"full_{self._timestamp()}.png")

            await self._page.screenshot(path=path, full_page=True)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Full-page screenshot: {path}",
                url=self._page.url,
                screenshot_path=path,
                data={"path": path, "type": "full_page"},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Screenshot failed: {exc}", duration_ms=elapsed)

    async def viewport(self, save_path: str | None = None) -> BrowserResult:
        """Capture viewport (visible area) screenshot.

        Args:
            save_path: Optional save path.

        Returns:
            BrowserResult with screenshot path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            path = save_path or str(self._screenshot_dir / f"viewport_{self._timestamp()}.png")

            await self._page.screenshot(path=path, full_page=False)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Viewport screenshot: {path}",
                url=self._page.url,
                screenshot_path=path,
                data={"path": path, "type": "viewport"},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Screenshot failed: {exc}", duration_ms=elapsed)

    async def element(self, selector: str, save_path: str | None = None) -> BrowserResult:
        """Capture a screenshot of a specific element.

        Args:
            selector: CSS selector for the element.
            save_path: Optional save path.

        Returns:
            BrowserResult with screenshot path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            path = save_path or str(self._screenshot_dir / f"element_{self._timestamp()}.png")

            element = self._page.locator(selector)
            await element.screenshot(path=path)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Element screenshot: {path}",
                url=self._page.url,
                screenshot_path=path,
                data={"path": path, "type": "element", "selector": selector},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Element screenshot failed: {exc}", duration_ms=elapsed)

    async def region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        save_path: str | None = None,
    ) -> BrowserResult:
        """Capture a specific region of the page.

        Args:
            x: Left coordinate.
            y: Top coordinate.
            width: Region width.
            height: Region height.

        Returns:
            BrowserResult with screenshot path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            path = save_path or str(self._screenshot_dir / f"region_{self._timestamp()}.png")

            await self._page.screenshot(
                path=path,
                clip={"x": x, "y": y, "width": width, "height": height},
            )

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Region screenshot: {path}",
                url=self._page.url,
                screenshot_path=path,
                data={"path": path, "type": "region", "x": x, "y": y, "width": width, "height": height},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Region screenshot failed: {exc}", duration_ms=elapsed)

    async def pdf(self, save_path: str | None = None) -> BrowserResult:
        """Save the page as a PDF.

        Args:
            save_path: Optional save path.

        Returns:
            BrowserResult with PDF path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            path = save_path or str(self._screenshot_dir / f"page_{self._timestamp()}.pdf")

            await self._page.pdf(path=path, format="A4", print_background=True)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"PDF saved: {path}",
                url=self._page.url,
                data={"path": path, "type": "pdf"},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"PDF failed: {exc}", duration_ms=elapsed)

    async def list_screenshots(self, limit: int = 30) -> BrowserResult:
        """List recent screenshots."""
        try:
            files = sorted(self._screenshot_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            items = []
            for f in files[:limit]:
                if f.is_file():
                    stat = f.stat()
                    items.append({
                        "name": f.name,
                        "path": str(f),
                        "size_kb": round(stat.st_size / 1024, 1),
                        "modified_at": stat.st_mtime,
                    })
            return BrowserResult(
                success=True,
                message=f"{len(items)} screenshots",
                data=items,
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"List failed: {exc}")
