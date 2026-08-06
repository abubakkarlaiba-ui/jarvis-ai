"""
Browser automation module for JARVIS.
======================================
Playwright-based browser control with session persistence,
form filling, content extraction, and change monitoring.

Quick Start:
    from jarvis.core.browser import BrowserEngine
    browser = BrowserEngine(settings)
    await browser.initialize()
    await browser.open("https://google.com")
    await browser.search_google("JARVIS AI")
    content = await browser.read_page()
"""

from jarvis.core.browser.browser import BrowserEngine
from jarvis.core.browser.base import BrowserConfig, BrowserResult, PageContent
from jarvis.core.browser.browser_manager import BrowserManager
from jarvis.core.browser.navigation import Navigation
from jarvis.core.browser.interaction import Interaction
from jarvis.core.browser.file_ops import FileOperations
from jarvis.core.browser.auth import LoginAutomation
from jarvis.core.browser.content import ContentExtractor
from jarvis.core.browser.monitor import PageMonitor
from jarvis.core.browser.screenshots import ScreenshotCapture

__all__ = [
    "BrowserEngine",
    "BrowserConfig",
    "BrowserResult",
    "PageContent",
    "BrowserManager",
    "Navigation",
    "Interaction",
    "FileOperations",
    "LoginAutomation",
    "ContentExtractor",
    "PageMonitor",
    "ScreenshotCapture",
]
