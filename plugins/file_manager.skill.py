"""
Skill: File Manager
===================
List, read, write, copy, move, delete, and search files securely.

Restricted to the user's home directory by default. Configure allowed
directories via the 'allowed_dirs' parameter.
"""

from __future__ import annotations

import fnmatch
import glob
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

DEFAULT_ALLOWED_ROOTS = [Path.home()]


def _is_under_allowed(path: Path, allowed_roots: list[Path]) -> bool:
    try:
        resolved = path.resolve()
    except (OSError, ValueError):
        return False
    return any(
        resolved == root or root in resolved.parents
        for root in allowed_roots
    )


def _file_info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": str(path),
        "name": path.name,
        "is_dir": path.is_dir(),
        "size_bytes": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "extension": path.suffix.lower(),
    }


def _human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class FileManagerSkill(BaseSkill):
    """Secure file operations restricted to allowed directories."""

    metadata = SkillMetadata(
        name="file_manager",
        version="1.0.0",
        description="List, read, write, copy, move, delete, and search files",
        author="JARVIS Team",
        tags=["files", "filesystem", "operations"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "").lower()
        if not action and context.user_input.strip():
            action = context.user_input.strip().split()[0].lower()

        handlers: dict[str, Any] = {
            "list": self._list_dir,
            "read": self._read_file,
            "write": self._write_file,
            "copy": self._copy_file,
            "move": self._move_file,
            "delete": self._delete_file,
            "search": self._search_files,
            "info": self._file_info_action,
            "mkdir": self._make_dir,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(context)

    def _resolve_allowed(self, context: SkillContext) -> list[Path]:
        allowed = context.parameters.get("allowed_dirs", [])
        if isinstance(allowed, str):
            allowed = [d.strip() for d in allowed.split(",") if d.strip()]
        if not allowed:
            return DEFAULT_ALLOWED_ROOTS
        return [Path(d) for d in allowed]

    def _validate_path(self, target: Path, allowed_roots: list[Path]) -> str | None:
        if not _is_under_allowed(target, allowed_roots):
            return f"Access denied: '{target}' is outside allowed directories."
        return None

    async def _list_dir(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", ".")
        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)

        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        if not target.is_dir():
            return SkillResult(success=False, error=f"Not a directory: {target}")

        try:
            entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied: {target}")
        except OSError as exc:
            return SkillResult(success=False, error=f"Error listing directory: {exc}")

        lines = []
        for entry in entries[:200]:
            prefix = "  [DIR] " if entry.is_dir() else "       "
            lines.append(f"{prefix}{entry.name}")

        summary = f"Contents of {target}:\n" + "\n".join(lines) if lines else f"{target} is empty."
        return SkillResult(
            success=True,
            output=summary,
            metadata={"path": str(target), "count": len(entries)},
        )

    async def _read_file(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", "")
        if not path_str:
            return SkillResult(success=False, error="A 'path' parameter is required.")

        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        if not target.is_file():
            return SkillResult(success=False, error=f"Not a file: {target}")

        max_size = context.parameters.get("max_size", 1_000_000)
        try:
            size = target.stat().st_size
            if size > max_size:
                return SkillResult(
                    success=False,
                    error=f"File too large ({_human_size(size)}). Max: {_human_size(max_size)}.",
                )
            content = target.read_text(encoding="utf-8")
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied: {target}")
        except UnicodeDecodeError:
            return SkillResult(success=False, error="File is not valid UTF-8 text.")
        except OSError as exc:
            return SkillResult(success=False, error=f"Error reading file: {exc}")

        return SkillResult(
            success=True,
            output=content,
            metadata={"path": str(target), "size": size},
        )

    async def _write_file(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", "")
        content = context.parameters.get("content", "")
        if not path_str:
            return SkillResult(success=False, error="A 'path' parameter is required.")

        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        mode = context.parameters.get("mode", "overwrite")
        append = mode == "append"

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if append:
                with open(target, "a", encoding="utf-8") as f:
                    f.write(content)
            else:
                target.write_text(content, encoding="utf-8")
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied: {target}")
        except OSError as exc:
            return SkillResult(success=False, error=f"Error writing file: {exc}")

        verb = "Appended to" if append else "Wrote"
        return SkillResult(
            success=True,
            output=f"{verb} {target} ({len(content)} chars).",
            metadata={"path": str(target), "chars": len(content)},
        )

    async def _copy_file(self, context: SkillContext) -> SkillResult:
        src_str = context.parameters.get("source", "")
        dst_str = context.parameters.get("destination", "")
        if not src_str or not dst_str:
            return SkillResult(success=False, error="Both 'source' and 'destination' are required.")

        src = Path(src_str).resolve()
        dst = Path(dst_str).resolve()
        allowed = self._resolve_allowed(context)

        for label, p in [("source", src), ("destination", dst)]:
            denial = self._validate_path(p, allowed)
            if denial:
                return SkillResult(success=False, error=f"{label}: {denial}")

        if not src.exists():
            return SkillResult(success=False, error=f"Source not found: {src}")

        try:
            if src.is_dir():
                shutil.copytree(str(src), str(dst))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied during copy.")
        except OSError as exc:
            return SkillResult(success=False, error=f"Copy failed: {exc}")

        return SkillResult(
            success=True,
            output=f"Copied '{src}' to '{dst}'.",
            metadata={"source": str(src), "destination": str(dst)},
        )

    async def _move_file(self, context: SkillContext) -> SkillResult:
        src_str = context.parameters.get("source", "")
        dst_str = context.parameters.get("destination", "")
        if not src_str or not dst_str:
            return SkillResult(success=False, error="Both 'source' and 'destination' are required.")

        src = Path(src_str).resolve()
        dst = Path(dst_str).resolve()
        allowed = self._resolve_allowed(context)

        for label, p in [("source", src), ("destination", dst)]:
            denial = self._validate_path(p, allowed)
            if denial:
                return SkillResult(success=False, error=f"{label}: {denial}")

        if not src.exists():
            return SkillResult(success=False, error=f"Source not found: {src}")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied during move.")
        except OSError as exc:
            return SkillResult(success=False, error=f"Move failed: {exc}")

        return SkillResult(
            success=True,
            output=f"Moved '{src}' to '{dst}'.",
            metadata={"source": str(src), "destination": str(dst)},
        )

    async def _delete_file(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", "")
        if not path_str:
            return SkillResult(success=False, error="A 'path' parameter is required.")

        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        if not target.exists():
            return SkillResult(success=False, error=f"Not found: {target}")

        confirm = context.parameters.get("confirm", False)
        if not confirm:
            return SkillResult(
                success=False,
                error=f"Set confirm=true to delete '{target}'.",
            )

        try:
            if target.is_dir():
                shutil.rmtree(str(target))
            else:
                target.unlink()
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied: {target}")
        except OSError as exc:
            return SkillResult(success=False, error=f"Delete failed: {exc}")

        return SkillResult(
            success=True,
            output=f"Deleted '{target}'.",
            metadata={"path": str(target)},
        )

    async def _search_files(self, context: SkillContext) -> SkillResult:
        pattern = context.parameters.get("pattern", "")
        search_dir = context.parameters.get("path", str(Path.home()))

        if not pattern:
            return SkillResult(success=False, error="A 'pattern' parameter is required.")

        target_dir = Path(search_dir).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target_dir, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        if not target_dir.is_dir():
            return SkillResult(success=False, error=f"Not a directory: {target_dir}")

        max_results = context.parameters.get("max_results", 50)
        matches: list[dict[str, Any]] = []

        try:
            for match in target_dir.rglob(pattern):
                if len(matches) >= max_results:
                    break
                if match.is_file():
                    matches.append(_file_info(match))
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied during search.")
        except OSError as exc:
            return SkillResult(success=False, error=f"Search error: {exc}")

        if not matches:
            return SkillResult(success=True, output=f"No files matching '{pattern}' in {target_dir}.")

        lines = [f"{m['path']} ({m['size_human']})" for m in matches]
        return SkillResult(
            success=True,
            output=f"Found {len(matches)} matches for '{pattern}':\n" + "\n".join(lines),
            metadata={"matches": matches, "count": len(matches)},
        )

    async def _file_info_action(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", "")
        if not path_str:
            return SkillResult(success=False, error="A 'path' parameter is required.")

        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        if not target.exists():
            return SkillResult(success=False, error=f"Not found: {target}")

        try:
            info = _file_info(target)
        except (OSError, PermissionError) as exc:
            return SkillResult(success=False, error=f"Could not stat file: {exc}")

        lines = [
            f"Path: {info['path']}",
            f"Name: {info['name']}",
            f"Type: {'Directory' if info['is_dir'] else 'File'}",
            f"Size: {info['size_human']}",
            f"Modified: {info['modified']}",
            f"Extension: {info['extension'] or 'N/A'}",
        ]

        return SkillResult(
            success=True,
            output="\n".join(lines),
            metadata=info,
        )

    async def _make_dir(self, context: SkillContext) -> SkillResult:
        path_str = context.parameters.get("path", "")
        if not path_str:
            return SkillResult(success=False, error="A 'path' parameter is required.")

        target = Path(path_str).resolve()
        allowed = self._resolve_allowed(context)
        denial = self._validate_path(target, allowed)
        if denial:
            return SkillResult(success=False, error=denial)

        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return SkillResult(success=False, error=f"Permission denied: {target}")
        except OSError as exc:
            return SkillResult(success=False, error=f"Failed to create directory: {exc}")

        return SkillResult(
            success=True,
            output=f"Created directory: {target}",
            metadata={"path": str(target)},
        )
