"""
File operations for JARVIS browser automation.
===============================================
Download and upload files through the browser.

Usage:
    file_ops = FileOperations(manager, config)
    await file_ops.download("a.download-link", "./downloads/file.zip")
    await file_ops.upload("input[type='file']", "./upload/document.pdf")
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from jarvis.core.browser.base import BrowserConfig, BrowserResult

logger = logging.getLogger(__name__)


class FileOperations:
    """Handle file downloads and uploads in the browser.

    Example:
        file_ops = FileOperations(manager, config)
        result = await file_ops.download_link("a#download-btn")
        result = await file_ops.upload_file("input[type='file']", "report.pdf")
    """

    def __init__(self, manager: Any, config: BrowserConfig):
        self._manager = manager
        self._config = config
        self._download_dir = Path(config.downloads_dir)
        self._download_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _page(self) -> Any | None:
        return self._manager.page

    async def download_link(self, selector: str, save_as: str | None = None) -> BrowserResult:
        """Download a file by clicking a download link.

        Args:
            selector: CSS selector for the download link/button.
            save_as: Optional filename to save as.

        Returns:
            BrowserResult with download path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            async with self._page.expect_download(timeout=self._config.timeout_ms) as download_info:
                await self._page.click(selector)

            download = await download_info.value

            if save_as:
                save_path = self._download_dir / save_as
            else:
                save_path = self._download_dir / download.suggested_filename

            await download.save_as(str(save_path))

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Downloaded: {save_path.name}",
                data={
                    "path": str(save_path),
                    "filename": download.suggested_filename,
                    "size_bytes": save_path.stat().st_size if save_path.exists() else 0,
                },
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Download failed: %s", exc)
            return BrowserResult(success=False, message=f"Download failed: {exc}", error=str(exc), duration_ms=elapsed)

    async def download_url(self, url: str, filename: str | None = None) -> BrowserResult:
        """Download a file directly from a URL.

        Args:
            url: Direct download URL.
            filename: Optional filename.

        Returns:
            BrowserResult with download path.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        try:
            response = await self._page.request.get(url)

            if not response.ok:
                return BrowserResult(
                    success=False,
                    message=f"Download failed: HTTP {response.status}",
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

            body = await response.body()

            if not filename:
                content_disp = response.headers.get("content-disposition", "")
                if "filename=" in content_disp:
                    filename = content_disp.split("filename=")[-1].strip('" ')
                else:
                    filename = url.split("/")[-1].split("?")[0] or "download"

            save_path = self._download_dir / filename
            save_path.write_bytes(body)

            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Downloaded: {filename} ({len(body)} bytes)",
                data={"path": str(save_path), "size_bytes": len(body)},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Download failed: {exc}", duration_ms=elapsed)

    async def upload_file(self, selector: str, file_path: str) -> BrowserResult:
        """Upload a file to a file input.

        Args:
            selector: CSS selector for the file input.
            file_path: Path to the file to upload.

        Returns:
            BrowserResult with upload status.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        path = Path(file_path)
        if not path.exists():
            return BrowserResult(success=False, message=f"File not found: {file_path}")

        try:
            await self._page.set_input_files(selector, str(path), timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Uploaded: {path.name}",
                data={"filename": path.name, "size_bytes": path.stat().st_size},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Upload failed: {exc}", duration_ms=elapsed)

    async def upload_files(self, selector: str, file_paths: list[str]) -> BrowserResult:
        """Upload multiple files to a file input.

        Args:
            selector: CSS selector for the file input.
            file_paths: List of file paths to upload.

        Returns:
            BrowserResult with upload status.
        """
        start = time.perf_counter()
        if not self._page:
            return BrowserResult(success=False, message="No active page")

        paths = [Path(p) for p in file_paths]
        missing = [str(p) for p in paths if not p.exists()]
        if missing:
            return BrowserResult(success=False, message=f"Files not found: {missing}")

        try:
            await self._page.set_input_files(selector, [str(p) for p in paths], timeout=self._config.timeout_ms)
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(
                success=True,
                message=f"Uploaded {len(paths)} files",
                data={"files": [p.name for p in paths]},
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return BrowserResult(success=False, message=f"Upload failed: {exc}", duration_ms=elapsed)

    async def upload_via_input(self, file_path: str) -> BrowserResult:
        """Find any file input on the page and upload to it.

        Args:
            file_path: Path to the file to upload.
        """
        selectors = [
            "input[type='file']",
            "input[accept*='image']",
            "input[accept*='pdf']",
            "input[accept]",
        ]

        for selector in selectors:
            try:
                if self._page:
                    count = await self._page.locator(selector).count()
                    if count > 0:
                        return await self.upload_file(selector, file_path)
            except Exception:
                continue

        return BrowserResult(success=False, message="No file input found on page")

    async def get_downloads(self) -> BrowserResult:
        """List files in the downloads directory."""
        try:
            files = sorted(self._download_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
            items = []
            for f in files[:50]:
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
                message=f"{len(items)} downloads",
                data=items,
            )
        except Exception as exc:
            return BrowserResult(success=False, message=f"List downloads failed: {exc}")

    async def clear_downloads(self) -> BrowserResult:
        """Clear all files in the downloads directory."""
        try:
            count = 0
            for f in self._download_dir.iterdir():
                if f.is_file():
                    f.unlink()
                    count += 1
            return BrowserResult(success=True, message=f"Cleared {count} downloads")
        except Exception as exc:
            return BrowserResult(success=False, message=f"Clear downloads failed: {exc}")
