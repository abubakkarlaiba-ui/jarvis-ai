"""
File operations for JARVIS desktop automation.
================================================
Safe file system operations with confirmation for destructive actions.

Capabilities:
    - Search files by name, extension, date, size
    - Move files between directories
    - Rename files and folders
    - Delete files (with recycle bin support)
    - Create folders recursively
    - Get file metadata and stats

All operations validate paths against allowed directories.

Usage:
    ops = FileOperations(safety_gate, settings)
    results = await ops.search("*.py", root="C:/Projects")
    await ops.move("old.txt", "archive/old.txt")
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Metadata about a file."""
    path: str
    name: str
    size_bytes: int
    is_dir: bool
    created_at: float
    modified_at: float
    extension: str = ""

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "size_human": self._human_size(),
            "is_dir": self.is_dir,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "extension": self.extension,
        }

    def _human_size(self) -> str:
        size = self.size_bytes
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class FileOperations:
    """Safe file system operations with path validation.

    Example:
        gate = SafetyGate()
        settings = AutomationSettings()
        ops = FileOperations(gate, settings)
        results = await ops.search("*.txt", root="Documents")
        await ops.create_folder("Projects/new_app")
    """

    def __init__(
        self,
        safety_gate: SafetyGate | None = None,
        allowed_directories: list[str] | None = None,
    ):
        self._gate = safety_gate or SafetyGate()
        self._allowed_dirs = [Path(d) for d in (allowed_directories or [os.path.expanduser("~")])]
        self._trash_dir = Path.home() / ".jarvis_trash"

    def _is_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed directories."""
        try:
            resolved = path.resolve()
            for allowed in self._allowed_dirs:
                try:
                    resolved.relative_to(allowed.resolve())
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    async def search(
        self,
        pattern: str,
        root: str = ".",
        max_results: int = 50,
        min_size: int = 0,
        max_size: int = 0,
        modified_after: float = 0,
        modified_before: float = 0,
        recursive: bool = True,
    ) -> ActionResult:
        """Search for files matching a pattern.

        Args:
            pattern: Glob pattern (e.g., "*.py", "**/*.txt").
            root: Root directory to search from.
            max_results: Maximum results to return.
            min_size: Minimum file size in bytes.
            max_size: Maximum file size in bytes (0 = no limit).
            modified_after: Only files modified after this timestamp.
            modified_before: Only files modified before this timestamp.
            recursive: Search recursively.

        Returns:
            ActionResult with list of FileInfo objects.
        """
        start = time.perf_counter()
        root_path = Path(root).resolve()

        if not self._is_allowed(root_path):
            return ActionResult(
                success=False,
                message=f"Directory not allowed: {root}",
                severity=ActionSeverity.SAFE,
            )

        try:
            if not root_path.exists():
                return ActionResult(
                    success=False,
                    message=f"Directory not found: {root}",
                    severity=ActionSeverity.SAFE,
                )

            glob_pattern = str(root_path / ("**/" + pattern if recursive else pattern))
            matches = []

            for match_path in glob.glob(glob_pattern, recursive=recursive):
                p = Path(match_path)
                try:
                    stat = p.stat()
                except (OSError, PermissionError):
                    continue

                if min_size and stat.st_size < min_size:
                    continue
                if max_size and stat.st_size > max_size:
                    continue
                if modified_after and stat.st_mtime < modified_after:
                    continue
                if modified_before and stat.st_mtime > modified_before:
                    continue

                matches.append(FileInfo(
                    path=str(p),
                    name=p.name,
                    size_bytes=stat.st_size,
                    is_dir=p.is_dir(),
                    created_at=stat.st_ctime,
                    modified_at=stat.st_mtime,
                    extension=p.suffix.lower(),
                ))

                if len(matches) >= max_results:
                    break

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Found {len(matches)} files matching '{pattern}'",
                data=[f.to_dict() for f in matches],
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Search failed: %s", exc)
            return ActionResult(
                success=False,
                message=f"Search failed: {exc}",
                duration_ms=elapsed,
            )

    async def move(self, source: str, destination: str) -> ActionResult:
        """Move a file or folder.

        Args:
            source: Source path.
            destination: Destination path.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        src = Path(source).resolve()
        dst = Path(destination).resolve()

        if not self._is_allowed(src) or not self._is_allowed(dst):
            return ActionResult(
                success=False,
                message="Path not in allowed directories",
                severity=ActionSeverity.MODERATE,
            )

        description = f"Move {src.name} to {dst.parent}"
        if not await self._gate.check(ActionSeverity.MODERATE, description, f"move:{src}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if not src.exists():
                return ActionResult(success=False, message=f"Source not found: {source}")

            if dst.is_dir():
                dst = dst / src.name

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Moved {src.name} to {dst}",
                data={"source": str(src), "destination": str(dst)},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Move failed: %s", exc)
            return ActionResult(success=False, message=f"Move failed: {exc}", duration_ms=elapsed)

    async def rename(self, path: str, new_name: str) -> ActionResult:
        """Rename a file or folder.

        Args:
            path: Current path.
            new_name: New name (not full path).

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        src = Path(path).resolve()

        if not self._is_allowed(src):
            return ActionResult(
                success=False,
                message="Path not in allowed directories",
                severity=ActionSeverity.DANGEROUS,
            )

        description = f"Rename {src.name} to {new_name}"
        if not await self._gate.check(ActionSeverity.DANGEROUS, description, f"rename:{src}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if not src.exists():
                return ActionResult(success=False, message=f"Path not found: {path}")

            dst = src.parent / new_name
            if dst.exists():
                return ActionResult(success=False, message=f"Target already exists: {new_name}")

            src.rename(dst)

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Renamed to {new_name}",
                data={"old_path": str(src), "new_path": str(dst)},
                severity=ActionSeverity.DANGEROUS,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Rename failed: {exc}", duration_ms=elapsed)

    async def delete(self, path: str, permanent: bool = False) -> ActionResult:
        """Delete a file or folder.

        Args:
            path: Path to delete.
            permanent: Skip recycle bin and delete permanently.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        src = Path(path).resolve()

        if not self._is_allowed(src):
            return ActionResult(
                success=False,
                message="Path not in allowed directories",
                severity=ActionSeverity.DESTRUCTIVE,
            )

        description = f"{'Permanently delete' if permanent else 'Delete'}: {src.name}"
        if not await self._gate.check(ActionSeverity.DESTRUCTIVE, description, f"delete:{src}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if not src.exists():
                return ActionResult(success=False, message=f"Path not found: {path}")

            if permanent:
                if src.is_dir():
                    shutil.rmtree(str(src))
                else:
                    src.unlink()
                msg = f"Permanently deleted {src.name}"
            else:
                self._trash_dir.mkdir(parents=True, exist_ok=True)
                trash_path = self._trash_dir / f"{int(time.time())}_{src.name}"
                shutil.move(str(src), str(trash_path))
                msg = f"Moved {src.name} to trash"

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=msg,
                severity=ActionSeverity.DESTRUCTIVE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Delete failed: {exc}", duration_ms=elapsed)

    async def create_folder(self, path: str) -> ActionResult:
        """Create a folder recursively.

        Args:
            path: Folder path to create.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        target = Path(path).resolve()

        if not self._is_allowed(target):
            return ActionResult(
                success=False,
                message="Path not in allowed directories",
                severity=ActionSeverity.MODERATE,
            )

        try:
            existed = target.exists()
            target.mkdir(parents=True, exist_ok=True)

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Created folder: {target.name}" if not existed else f"Folder exists: {target.name}",
                data={"path": str(target), "existed": existed},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Create folder failed: {exc}", duration_ms=elapsed)

    async def get_info(self, path: str) -> ActionResult:
        """Get file/folder metadata.

        Args:
            path: Path to inspect.

        Returns:
            ActionResult with FileInfo data.
        """
        start = time.perf_counter()
        target = Path(path).resolve()

        try:
            if not target.exists():
                return ActionResult(success=False, message=f"Path not found: {path}")

            stat = target.stat()
            info = FileInfo(
                path=str(target),
                name=target.name,
                size_bytes=stat.st_size,
                is_dir=target.is_dir(),
                created_at=stat.st_ctime,
                modified_at=stat.st_mtime,
                extension=target.suffix.lower(),
            )

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Info for {target.name}",
                data=info.to_dict(),
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Failed to get info: {exc}", duration_ms=elapsed)

    async def empty_trash(self) -> ActionResult:
        """Empty the JARVIS trash folder.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        description = "Empty trash (permanently delete all trashed files)"

        if not await self._gate.check(ActionSeverity.DESTRUCTIVE, description, "empty_trash"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if not self._trash_dir.exists():
                return ActionResult(success=True, message="Trash is already empty")

            count = sum(1 for _ in self._trash_dir.iterdir())
            shutil.rmtree(str(self._trash_dir))

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Emptied trash ({count} items)",
                severity=ActionSeverity.DESTRUCTIVE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Empty trash failed: {exc}", duration_ms=elapsed)
