"""
Page change monitor for JARVIS browser automation.
====================================================
Watch for changes in web page content, DOM structure,
or specific elements.

Usage:
    monitor = PageMonitor(manager, config)
    await monitor.watch_element("h1", interval=5, callback=my_callback)
    changes = await monitor.detect_changes("https://example.com", hash_content=True)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


@dataclass
class ChangeRecord:
    """Record of a detected change."""
    timestamp: float
    change_type: str  # content, dom, element, url
    old_value: str
    new_value: str
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "change_type": self.change_type,
            "old_value": self.old_value[:500],
            "new_value": self.new_value[:500],
            "url": self.url,
        }


class PageMonitor:
    """Monitor web pages for changes.

    Example:
        monitor = PageMonitor(manager, config)
        result = await monitor.take_snapshot("https://example.com")
        await asyncio.sleep(60)
        changes = await monitor.check_for_changes("https://example.com")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config
        self._snapshots: dict[str, dict] = {}
        self._watch_tasks: dict[str, asyncio.Task] = {}
        self._changes_log: list[ChangeRecord] = []
        self._snapshot_dir = Path(config.user_data_dir) / "page_snapshots"
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)

    async def take_snapshot(
        self,
        url: str,
        include_text: bool = True,
        include_html: bool = True,
        element_selector: str | None = None,
    ) -> BrowserResult:
        """Take a snapshot of a page for change detection.

        Args:
            url: URL to snapshot.
            include_text: Include text content.
            include_html: Include HTML content.
            element_selector: Optional specific element to snapshot.

        Returns:
            BrowserResult with snapshot data.
        """
        start = time.perf_counter()

        try:
            if self._manager.page:
                current_url = self._manager.page.url
                await self._manager.navigation.goto(url)
                await asyncio.sleep(1)
            else:
                return BrowserResult(success=False, message="No active page")

            if element_selector:
                content = await self._manager.page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('{element_selector}');
                        return el ? {{ text: el.innerText, html: el.innerHTML }} : null;
                    }}
                """)
                text = content.get("text", "") if content else ""
                html = content.get("html", "") if content else ""
            else:
                text_result = await self._manager.page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('script, style, noscript');
                        const clone = document.body.cloneNode(true);
                        elements.forEach(el => clone.removeChild(el));
                        return clone.innerText || '';
                    }
                """)
                text = text_result
                html = await self._manager.page.content()

            text_hash = hashlib.sha256(text.encode()).hexdigest()
            html_hash = hashlib.sha256(html.encode()).hexdigest()

            snapshot = {
                "url": url,
                "timestamp": time.time(),
                "text": text,
                "html": html if include_html else "",
                "text_hash": text_hash,
                "html_hash": html_hash,
                "element_selector": element_selector,
            }

            self._snapshots[url] = snapshot

            snapshot_file = self._snapshot_dir / f"{hashlib.md5(url.encode()).hexdigest()}.json"
            save_data = {
                "url": url,
                "timestamp": snapshot["timestamp"],
                "text_hash": text_hash,
                "html_hash": html_hash,
                "text_preview": text[:1000],
            }
            snapshot_file.write_text(json.dumps(save_data, indent=2), encoding="utf-8")

            if current_url and current_url != url:
                await self._manager.navigation.goto(current_url)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Snapshot taken for {url}",
                data={
                    "url": url,
                    "text_hash": text_hash,
                    "html_hash": html_hash,
                    "text_length": len(text),
                },
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Snapshot failed: {exc}", duration_ms=elapsed)

    async def check_for_changes(self, url: str) -> BrowserResult:
        """Check if a page has changed since the last snapshot.

        Args:
            url: URL to check.

        Returns:
            BrowserResult with change details.
        """
        start = time.perf_counter()

        if url not in self._snapshots:
            return BrowserResult(success=False, message=f"No snapshot for {url}. Use take_snapshot() first.")

        old_snapshot = self._snapshots[url]

        try:
            snapshot_result = await self.take_snapshot(url, include_html=False)
            if not snapshot_result.success:
                return snapshot_result

            new_snapshot = self._snapshots.get(url, {})
            changes = []

            if old_snapshot.get("text_hash") != new_snapshot.get("text_hash"):
                old_text = old_snapshot.get("text", "")
                new_text = new_snapshot.get("text", "")

                change = ChangeRecord(
                    timestamp=time.time(),
                    change_type="content",
                    old_value=old_text[:500],
                    new_value=new_text[:500],
                    url=url,
                )
                changes.append(change)
                self._changes_log.append(change)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Changes detected: {len(changes)}" if changes else "No changes detected",
                data={
                    "changed": bool(changes),
                    "changes": [c.to_dict() for c in changes],
                    "old_hash": old_snapshot.get("text_hash"),
                    "new_hash": new_snapshot.get("text_hash"),
                },
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Change check failed: {exc}", duration_ms=elapsed)

    async def watch_url(
        self,
        url: str,
        interval_seconds: int = 30,
        callback: Callable[[ChangeRecord], Awaitable[None]] | None = None,
        max_checks: int = 0,
    ) -> BrowserResult:
        """Start watching a URL for changes.

        Args:
            url: URL to monitor.
            interval_seconds: Check interval.
            callback: Async callback for changes.
            max_checks: Stop after N checks (0 = unlimited).

        Returns:
            BrowserResult with watch status.
        """
        if url in self._watch_tasks:
            return BrowserResult(success=False, message=f"Already watching {url}")

        snapshot_result = await self.take_snapshot(url)
        if not snapshot_result.success:
            return snapshot_result

        async def _watch_loop():
            checks = 0
            while True:
                try:
                    await asyncio.sleep(interval_seconds)
                    checks += 1

                    change_result = await self.check_for_changes(url)
                    if change_result.success and change_result.data.get("changed"):
                        for change_data in change_result.data.get("changes", []):
                            record = ChangeRecord(**{
                                k: v for k, v in change_data.items()
                                if k in ChangeRecord.__dataclass_fields__
                            })
                            if callback:
                                await callback(record)

                    if max_checks > 0 and checks >= max_checks:
                        break

                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    logger.debug("Watch error for %s: %s", url, exc)

        task = asyncio.create_task(_watch_loop())
        self._watch_tasks[url] = task

        return BrowserResult(
            success=True,
            message=f"Watching {url} every {interval_seconds}s",
            data={"url": url, "interval": interval_seconds},
        )

    async def stop_watching(self, url: str) -> BrowserResult:
        """Stop watching a URL."""
        task = self._watch_tasks.pop(url, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            return BrowserResult(success=True, message=f"Stopped watching {url}")
        return BrowserResult(success=False, message=f"Not watching {url}")

    async def stop_all_watches(self) -> BrowserResult:
        """Stop all active watches."""
        count = len(self._watch_tasks)
        for url in list(self._watch_tasks.keys()):
            await self.stop_watching(url)
        return BrowserResult(success=True, message=f"Stopped {count} watches")

    def get_changes_log(self, limit: int = 50) -> list[dict]:
        """Get recent change records."""
        return [c.to_dict() for c in self._changes_log[-limit:]]

    def clear_snapshots(self) -> BrowserResult:
        """Clear all stored snapshots."""
        self._snapshots.clear()
        self._changes_log.clear()
        return BrowserResult(success=True, message="Snapshots cleared")
