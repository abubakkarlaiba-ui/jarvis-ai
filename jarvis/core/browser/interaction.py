"""
Page interaction for JARVIS browser automation.
================================================
Fill forms, click elements, select options, scroll, and interact
with page elements using selectors.

Usage:
    interact = Interaction(manager, config)
    await interact.fill("input#email", "user@example.com")
    await interact.click("button[type='submit']")
    await interact.select("select#country", "us")
    await interact.scroll_down(500)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


class Interaction:
    """Interact with page elements via selectors.

    Example:
        interact = Interaction(manager, config)
        await interact.fill("#username", "admin")
        await interact.click("submit-button")
        result = await interact.get_text("h1")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config

    @property
    def _page(self) -> Any | None:
        return self._manager.page

    async def click(self, selector: str, timeout_ms: int = 0) -> BrowserResult:
        """Click an element by selector.

        Args:
            selector: CSS or text selector.
            timeout_ms: Timeout override.

        Returns:
            BrowserResult with click status.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.click(selector, timeout=timeout_ms or self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Clicked: {selector}",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Click failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def double_click(self, selector: str) -> BrowserResult:
        """Double-click an element."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.dblclick(selector, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=True, message=f"Double-clicked: {selector}", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Double-click failed: {exc}", duration_ms=elapsed)

    async def right_click(self, selector: str) -> BrowserResult:
        """Right-click an element."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.click(selector, button="right", timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=True, message=f"Right-clicked: {selector}", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Right-click failed: {exc}", duration_ms=elapsed)

    async def fill(self, selector: str, value: str, clear: bool = True) -> BrowserResult:
        """Fill a form input with a value.

        Args:
            selector: CSS selector for the input.
            value: Value to fill.
            clear: Clear existing value first.

        Returns:
            BrowserResult with fill status.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            if clear:
                await self._page.fill(selector, "", timeout=self._config.timeout_ms)
            await self._page.fill(selector, value, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Filled {selector} ({len(value)} chars)",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Fill failed: {exc}", duration_ms=elapsed)

    async def type_text(self, selector: str, text: str, delay_ms: int = 50) -> BrowserResult:
        """Type text character by character into an input.

        Args:
            selector: CSS selector for the input.
            text: Text to type.
            delay_ms: Delay between keystrokes.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.type(selector, text, delay=delay_ms, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Typed {len(text)} chars into {selector}",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Type failed: {exc}", duration_ms=elapsed)

    async def select(self, selector: str, value: str) -> BrowserResult:
        """Select an option from a dropdown.

        Args:
            selector: CSS selector for the select element.
            value: Option value to select.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.select_option(selector, value, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Selected '{value}' in {selector}",
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Select failed: {exc}", duration_ms=elapsed)

    async def check(self, selector: str) -> BrowserResult:
        """Check a checkbox."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.check(selector, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=True, message=f"Checked: {selector}", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Check failed: {exc}", duration_ms=elapsed)

    async def uncheck(self, selector: str) -> BrowserResult:
        """Uncheck a checkbox."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.uncheck(selector, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=True, message=f"Unchecked: {selector}", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Uncheck failed: {exc}", duration_ms=elapsed)

    async def hover(self, selector: str) -> BrowserResult:
        """Hover over an element."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.hover(selector, timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=True, message=f"Hovered: {selector}", duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Hover failed: {exc}", duration_ms=elapsed)

    async def focus(self, selector: str) -> BrowserResult:
        """Focus an element."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.focus(selector, timeout=self._config.timeout_ms)
            return BrowserResult(success=True, message=f"Focused: {selector}")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Focus failed: {exc}")

    async def scroll_down(self, pixels: int = 500) -> BrowserResult:
        """Scroll down by pixels."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.mouse.wheel(0, pixels)
            return BrowserResult(success=True, message=f"Scrolled down {pixels}px")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Scroll failed: {exc}")

    async def scroll_up(self, pixels: int = 500) -> BrowserResult:
        """Scroll up by pixels."""
        return await self.scroll_down(-pixels)

    async def scroll_to_bottom(self) -> BrowserResult:
        """Scroll to the bottom of the page."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            return BrowserResult(success=True, message="Scrolled to bottom")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Scroll failed: {exc}")

    async def scroll_to_top(self) -> BrowserResult:
        """Scroll to the top of the page."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.evaluate("window.scrollTo(0, 0)")
            return BrowserResult(success=True, message="Scrolled to top")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Scroll failed: {exc}")

    async def get_text(self, selector: str) -> BrowserResult:
        """Get text content of an element."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            text = await self._page.text_content(selector, timeout=self._config.timeout_ms)
            return BrowserResult(
                success=True,
                message=f"Text from {selector}",
                data={"text": text or ""},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get text failed: {exc}")

    async def get_attribute(self, selector: str, attribute: str) -> BrowserResult:
        """Get an attribute value from an element."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            value = await self._page.get_attribute(selector, attribute, timeout=self._config.timeout_ms)
            return BrowserResult(
                success=True,
                message=f"Attribute {attribute} from {selector}",
                data={"value": value},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get attribute failed: {exc}")

    async def get_input_value(self, selector: str) -> BrowserResult:
        """Get current value of an input element."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            value = await self._page.input_value(selector, timeout=self._config.timeout_ms)
            return BrowserResult(
                success=True,
                message=f"Input value from {selector}",
                data={"value": value},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"Get input value failed: {exc}")

    async def wait_for_selector(self, selector: str, timeout_ms: int = 0) -> BrowserResult:
        """Wait for an element to appear in the DOM."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.wait_for_selector(selector, timeout=timeout_ms or self._config.timeout_ms)
            return BrowserResult(success=True, message=f"Element appeared: {selector}")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Wait failed: {exc}")

    async def wait_for_hidden(self, selector: str, timeout_ms: int = 0) -> BrowserResult:
        """Wait for an element to be hidden/removed."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.wait_for_selector(selector, state="hidden", timeout=timeout_ms or self._config.timeout_ms)
            return BrowserResult(success=True, message=f"Element hidden: {selector}")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Wait hidden failed: {exc}")

    async def press_key(self, key: str) -> BrowserResult:
        """Press a keyboard key on the page."""
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.keyboard.press(key)
            return BrowserResult(success=True, message=f"Pressed key: {key}")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Key press failed: {exc}")

    async def submit_form(self, selector: str = "form") -> BrowserResult:
        """Submit a form."""
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            await self._page.evaluate(f"document.querySelector('{selector}').submit()")
            await self._page.wait_for_load_state("domcontentloaded", timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Form submitted: {selector}",
                url=self._page.url,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Submit failed: {exc}", duration_ms=elapsed)

    async def evaluate(self, expression: str) -> BrowserResult:
        """Execute JavaScript in the page context.

        Args:
            expression: JavaScript expression to evaluate.

        Returns:
            BrowserResult with evaluation result.
        """
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            result = await self._page.evaluate(expression)
            return BrowserResult(
                success=True,
                message="JS evaluated",
                data={"result": result},
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"JS evaluation failed: {exc}")

    async def count_elements(self, selector: str) -> int:
        """Count elements matching a selector."""
        if not self._page:
            return 0

        try:
            return await self._page.locator(selector).count()
        except Exception:
            return 0

    async def is_visible(self, selector: str) -> bool:
        """Check if an element is visible."""
        if not self._page:
            return False

        try:
            return await self._page.locator(selector).is_visible()
        except Exception:
            return False
