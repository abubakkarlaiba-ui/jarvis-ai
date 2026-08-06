"""
Base types and configuration for browser automation.
=====================================================
Defines shared data structures, enums, and the browser configuration.

Usage:
    config = BrowserConfig(headless=False, user_data_dir="./browser_data")
    result = BrowserResult(success=True, url="https://example.com")
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class BrowserAction(Enum):
    """Browser action types for logging."""
    OPEN = auto()
    CLOSE = auto()
    NAVIGATE = auto()
    CLICK = auto()
    FILL = auto()
    SUBMIT = auto()
    SCROLL = auto()
    SCREENSHOT = auto()
    READ = auto()
    DOWNLOAD = auto()
    UPLOAD = auto()
    LOGIN = auto()
    SEARCH = auto()
    TAB_OPEN = auto()
    TAB_CLOSE = auto()
    TAB_SWITCH = auto()
    COOKIE_SET = auto()
    COOKIE_DELETE = auto()
    WATCH_START = auto()
    WATCH_STOP = auto()


@dataclass
class BrowserConfig:
    """Configuration for the browser engine."""
    headless: bool = False
    slow_mo: int = 0
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    user_data_dir: str = "./data/browser_profile"
    downloads_dir: str = "./data/downloads"
    screenshots_dir: str = "./data/screenshots/browser"
    persistent_context: bool = True
    chromium_channel: str = "chrome"
    proxy: str | None = None
    user_agent: str | None = None
    locale: str = "en-US"
    timezone_id: str = "America/New_York"
    ignore_https_errors: bool = True
    java_script_enabled: bool = True
    extra_http_headers: dict[str, str] = field(default_factory=dict)
    blocked_domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "headless": self.headless,
            "slow_mo": self.slow_mo,
            "timeout_ms": self.timeout_ms,
            "viewport": f"{self.viewport_width}x{self.viewport_height}",
            "persistent": self.persistent_context,
            "channel": self.chromium_channel,
        }


@dataclass
class BrowserResult:
    """Result of a browser operation."""
    success: bool
    message: str = ""
    url: str = ""
    title: str = ""
    data: Any = None
    duration_ms: float = 0.0
    screenshot_path: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "url": self.url,
            "title": self.title,
            "duration_ms": round(self.duration_ms, 1),
            "screenshot_path": self.screenshot_path,
            "error": self.error,
        }


@dataclass
class PageContent:
    """Extracted content from a web page."""
    url: str
    title: str
    text: str
    html: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)
    headings: list[dict[str, str]] = field(default_factory=list)
    word_count: int = 0
    language: str = ""
    extracted_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "text": self.text[:5000],
            "meta": self.meta,
            "links_count": len(self.links),
            "images_count": len(self.images),
            "forms_count": len(self.forms),
            "word_count": self.word_count,
            "language": self.language,
        }

    def to_summary(self, max_chars: int = 2000) -> str:
        """Create a concise summary of the page."""
        parts = [f"Page: {self.title}", f"URL: {self.url}"]
        if self.meta.get("description"):
            parts.append(f"Description: {self.meta['description']}")
        text_preview = self.text[:max_chars]
        if len(self.text) > max_chars:
            text_preview += "..."
        parts.append(f"\nContent:\n{text_preview}")
        return "\n".join(parts)


@dataclass
class TabInfo:
    """Information about a browser tab."""
    index: int
    url: str
    title: str
    is_active: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "url": self.url,
            "title": self.title,
            "is_active": self.is_active,
        }


@dataclass
class CookieInfo:
    """Browser cookie information."""
    name: str
    value: str
    domain: str
    path: str = "/"
    expires: float = -1
    http_only: bool = False
    secure: bool = False
    same_site: str = "Lax"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value[:50] + "..." if len(self.value) > 50 else self.value,
            "domain": self.domain,
            "path": self.path,
            "expires": self.expires,
            "http_only": self.http_only,
            "secure": self.secure,
            "same_site": self.same_site,
        }
