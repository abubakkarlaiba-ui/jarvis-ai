"""
Automation module — desktop, web, and file system automation.
=============================================================
Provides hands-free control of the user's computer and applications.

Capabilities:
    - Desktop automation (mouse, keyboard, window management)
    - Web browser control (navigation, form filling, scraping)
    - File system operations (CRUD, search, organization)

Usage:
    automation = AutomationModule(settings)
    await automation.initialize()
    await automation.open_application("notepad")
    await automation.search_web("JARVIS AI assistant")
"""

from __future__ import annotations

import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jarvis.config.settings import AutomationSettings
from jarvis.utils.helpers import ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class FileOperation:
    """Result of a file system operation."""
    success: bool
    source_path: str
    destination_path: str | None = None
    message: str = ""


@dataclass
class WebResult:
    """Result of a web automation action."""
    success: bool
    url: str
    title: str = ""
    content: str = ""
    metadata: dict[str, Any] | None = None


class DesktopController(ABC):
    """Abstract base class for desktop automation (mouse, keyboard, windows)."""

    @abstractmethod
    async def open_application(self, name: str) -> bool:
        """Launch an application by name.

        Args:
            name: Application name or path.

        Returns:
            True if the application was launched successfully.
        """
        ...

    @abstractmethod
    async def type_text(self, text: str) -> None:
        """Type text as if from a keyboard.

        Args:
            text: Text to type.
        """
        ...

    @abstractmethod
    async def press_key(self, *keys: str) -> None:
        """Press a key combination.

        Args:
            *keys: Keys to press simultaneously (e.g., 'ctrl', 'c').
        """
        ...

    @abstractmethod
    async def get_active_window(self) -> dict[str, Any]:
        """Return information about the currently active window."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the desktop controller."""
        ...


class WebBrowser(ABC):
    """Abstract base class for web browser automation."""

    @abstractmethod
    async def navigate(self, url: str) -> WebResult:
        """Navigate to a URL.

        Args:
            url: Target URL.

        Returns:
            WebResult with page information.
        """
        ...

    @abstractmethod
    async def search(self, query: str) -> WebResult:
        """Perform a web search.

        Args:
            query: Search query.

        Returns:
            WebResult with search results.
        """
        ...

    @abstractmethod
    async def get_page_content(self) -> str:
        """Return the current page's text content."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the browser."""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Close the browser and release resources."""
        ...


class FileManager:
    """File system operations with safety checks.

    All operations validate paths against allowed directories before execution.
    """

    def __init__(self, allowed_directories: list[str] | None = None):
        self.allowed_directories = [Path(d).resolve() for d in (allowed_directories or [])]

    def _is_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed directories."""
        if not self.allowed_directories:
            return True
        resolved = path.resolve()
        return any(
            str(resolved).startswith(str(allowed))
            for allowed in self.allowed_directories
        )

    async def read_file(self, file_path: str) -> str:
        """Read and return the contents of a text file.

        Args:
            file_path: Path to the file to read.

        Returns:
            File contents as a string.

        Raises:
            PermissionError: If the path is not allowed.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path).resolve()
        if not self._is_allowed(path):
            raise PermissionError(f"Access denied: {file_path} is outside allowed directories")
        return path.read_text(encoding="utf-8")

    async def write_file(self, file_path: str, content: str) -> FileOperation:
        """Write content to a file.

        Args:
            file_path: Path to the file to write.
            content: Content to write.

        Returns:
            FileOperation with success status.
        """
        path = Path(file_path).resolve()
        if not self._is_allowed(path):
            return FileOperation(
                success=False,
                source_path=file_path,
                message="Permission denied: path outside allowed directories",
            )
        ensure_directory(path.parent)
        path.write_text(content, encoding="utf-8")
        return FileOperation(success=True, source_path=file_path, message="File written successfully")

    async def list_directory(self, dir_path: str = ".") -> list[str]:
        """List files and directories at the given path.

        Args:
            dir_path: Directory path to list.

        Returns:
            List of file/directory names.
        """
        path = Path(dir_path).resolve()
        if not self._is_allowed(path):
            return []
        return [str(entry.name) for entry in path.iterdir()]

    async def search_files(self, directory: str, pattern: str) -> list[str]:
        """Search for files matching a glob pattern.

        Args:
            directory: Root directory to search.
            pattern: Glob pattern (e.g., '*.py', '**/*.txt').

        Returns:
            List of matching file paths.
        """
        path = Path(directory).resolve()
        if not self._is_allowed(path):
            return []
        return [str(f) for f in path.glob(pattern)]

    async def delete_file(self, file_path: str) -> FileOperation:
        """Delete a file.

        Args:
            file_path: Path to the file to delete.

        Returns:
            FileOperation with success status.
        """
        path = Path(file_path).resolve()
        if not self._is_allowed(path):
            return FileOperation(
                success=False,
                source_path=file_path,
                message="Permission denied: path outside allowed directories",
            )
        if path.exists():
            path.unlink()
            return FileOperation(success=True, source_path=file_path, message="File deleted")
        return FileOperation(success=False, source_path=file_path, message="File not found")

    async def move_file(self, source: str, destination: str) -> FileOperation:
        """Move a file to a new location.

        Args:
            source: Current file path.
            destination: Target file path.

        Returns:
            FileOperation with success status.
        """
        src = Path(source).resolve()
        dst = Path(destination).resolve()
        if not self._is_allowed(src) or not self._is_allowed(dst):
            return FileOperation(
                success=False,
                source_path=source,
                destination_path=destination,
                message="Permission denied: path outside allowed directories",
            )
        shutil.move(str(src), str(dst))
        return FileOperation(
            success=True,
            source_path=source,
            destination_path=destination,
            message="File moved successfully",
        )


class DummyDesktopController(DesktopController):
    """Placeholder desktop controller for development."""

    async def initialize(self) -> None:
        logger.info("DummyDesktopController initialized")

    async def open_application(self, name: str) -> bool:
        logger.info("DummyDesktopController: would open '%s'", name)
        return True

    async def type_text(self, text: str) -> None:
        logger.debug("DummyDesktopController: would type '%s'", text[:50])

    async def press_key(self, *keys: str) -> None:
        logger.debug("DummyDesktopController: would press %s", keys)

    async def get_active_window(self) -> dict[str, Any]:
        return {"title": "Dummy Window", "pid": 0}


class DummyWebBrowser(WebBrowser):
    """Placeholder web browser for development."""

    async def initialize(self) -> None:
        logger.info("DummyWebBrowser initialized")

    async def navigate(self, url: str) -> WebResult:
        logger.info("DummyWebBrowser: would navigate to '%s'", url)
        return WebResult(success=True, url=url, title="Dummy Page")

    async def search(self, query: str) -> WebResult:
        logger.info("DummyWebBrowser: would search for '%s'", query)
        return WebResult(success=True, url="", title="Search Results")

    async def get_page_content(self) -> str:
        return "Dummy page content"

    async def cleanup(self) -> None:
        pass


class AutomationModule:
    """Unified automation orchestrator.

    Coordinates desktop control, web browsing, and file operations.

    Example:
        automation = AutomationModule(settings)
        await automation.initialize()
        await automation.open_application("vscode")
        await automation.search_web("python async")
    """

    def __init__(self, settings: AutomationSettings):
        self._settings = settings
        self.desktop: DesktopController = DummyDesktopController()
        self.browser: WebBrowser = DummyWebBrowser()
        self.files: FileManager = FileManager(settings.allowed_directories)
        logger.info("AutomationModule created")

    async def initialize(self) -> None:
        """Initialize all automation subsystems."""
        await self.desktop.initialize()
        if self._settings.web_browser_enabled:
            await self.browser.initialize()
        logger.info("AutomationModule initialized")

    async def open_application(self, name: str) -> bool:
        """Launch an application by name."""
        return await self.desktop.open_application(name)

    async def search_web(self, query: str) -> WebResult:
        """Search the web for a query."""
        return await self.browser.search(query)

    async def read_file(self, file_path: str) -> str:
        """Read a file's contents."""
        return await self.files.read_file(file_path)

    async def write_file(self, file_path: str, content: str) -> FileOperation:
        """Write content to a file."""
        return await self.files.write_file(file_path, content)

    async def cleanup(self) -> None:
        """Release all automation resources."""
        await self.browser.cleanup()
        logger.info("AutomationModule cleaned up")
