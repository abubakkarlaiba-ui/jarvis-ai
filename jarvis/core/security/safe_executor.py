"""
Security module — Sandboxed command execution with safety checks.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any, Optional


class SafeExecutor:
    """
    Sandboxed command and file execution with path validation.

    Commands are executed via :func:`asyncio.create_subprocess_shell` with
    stdout/stderr capture and configurable timeouts.  Destructive commands
    are blocked by default and paths are validated against an allow-list.
    """

    def __init__(
        self,
        allowed_dirs: list[str] | None = None,
        blocked_commands: list[str] | None = None,
    ) -> None:
        self._allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [os.getcwd()])]
        self._blocked_commands = blocked_commands or self._default_blocked_commands()
        self._execution_history: list[dict[str, Any]] = []

    @staticmethod
    def _default_blocked_commands() -> list[str]:
        """Return the default list of dangerous command patterns."""
        return [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "format",
            "format c:",
            "del /s",
            "del /f /s /q",
            "rmdir /s /q",
            "mkfs",
            "dd if=",
            ":(){ :|:& };:",
            "chmod -R 777 /",
            "chown -R",
            "> /dev/sda",
            "shutdown",
            "reboot",
            "halt",
            "init 0",
            "init 6",
            "poweroff",
            "systemctl stop",
            "killall",
            "pkill",
        ]

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Check whether *command* is safe to execute."""
        normalized = command.lower().strip()
        for blocked in self._blocked_commands:
            if blocked.lower() in normalized:
                return False, f"Blocked command pattern: {blocked}"
        if any(seg in normalized for seg in ["&&", "||", ";", "|", "$(", "`"]):
            if not normalized.startswith("echo "):
                return False, "Shell chaining or substitution detected"
        return True, ""

    def _validate_path(self, path: str) -> tuple[bool, str]:
        """Check whether *path* resides inside an allowed directory."""
        try:
            resolved = Path(path).resolve()
        except (OSError, ValueError) as exc:
            return False, f"Invalid path: {exc}"
        for allowed in self._allowed_dirs:
            try:
                resolved.relative_to(allowed)
                return True, ""
            except ValueError:
                continue
        return False, f"Path {resolved} is outside allowed directories"

    def _check_path_traversal(self, path: str) -> bool:
        """Return ``True`` if *path* contains traversal indicators."""
        normalized = path.replace("\\", "/")
        if ".." in normalized:
            return True
        try:
            resolved = Path(path).resolve()
            if resolved != Path(path):
                return True
        except (OSError, ValueError):
            return True
        return False

    async def execute(
        self,
        command: str,
        timeout: float = 30,
        working_dir: str | None = None,
    ) -> dict[str, Any]:
        """Execute *command* safely with timeout and output capture."""
        safe, reason = self._validate_command(command)
        if not safe:
            result = {"success": False, "error": reason, "stdout": "", "stderr": "", "returncode": -1}
            self._log_execution(command, result)
            return result

        if working_dir:
            path_ok, path_reason = self._validate_path(working_dir)
            if not path_ok:
                result = {"success": False, "error": path_reason, "stdout": "", "stderr": "", "returncode": -1}
                self._log_execution(command, result)
                return result

        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            elapsed = time.monotonic() - start
            result = {
                "success": proc.returncode == 0,
                "stdout": stdout_bytes.decode(errors="replace"),
                "stderr": stderr_bytes.decode(errors="replace"),
                "returncode": proc.returncode,
                "elapsed": round(elapsed, 3),
            }
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            result = {"success": False, "error": f"Command timed out after {timeout}s", "stdout": "", "stderr": "", "returncode": -1, "elapsed": round(elapsed, 3)}
        except Exception as exc:
            elapsed = time.monotonic() - start
            result = {"success": False, "error": str(exc), "stdout": "", "stderr": "", "returncode": -1, "elapsed": round(elapsed, 3)}

        self._log_execution(command, result)
        return result

    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30,
    ) -> dict[str, Any]:
        """Execute *code* in a sandboxed subprocess of the given *language*."""
        interpreters = {
            "python": "python -c",
            "python3": "python3 -c",
            "node": "node -e",
            "bash": "bash -c",
        }
        prefix = interpreters.get(language)
        if not prefix:
            return {"success": False, "error": f"Unsupported language: {language}", "stdout": "", "stderr": "", "returncode": -1}

        escaped = code.replace('"', '\\"')
        command = f'{prefix} "{escaped}"'
        return await self.execute(command, timeout=timeout)

    async def execute_file(
        self,
        file_path: str,
        args: list[str] | None = None,
        timeout: float = 60,
    ) -> dict[str, Any]:
        """Execute *file_path* with optional *args*."""
        path_ok, reason = self._validate_path(file_path)
        if not path_ok:
            result = {"success": False, "error": reason, "stdout": "", "stderr": "", "returncode": -1}
            self._log_execution(file_path, result)
            return result

        resolved = str(Path(file_path).resolve())
        arg_str = " ".join(f'"{a}"' for a in (args or []))
        command = f'"{resolved}" {arg_str}'.strip()
        return await self.execute(command, timeout=timeout)

    async def read_file(
        self,
        file_path: str,
        max_size: int = 10_000_000,
    ) -> dict[str, Any]:
        """Read *file_path* with a size limit."""
        path_ok, reason = self._validate_path(file_path)
        if not path_ok:
            return {"success": False, "error": reason, "content": ""}

        resolved = Path(file_path).resolve()
        try:
            size = resolved.stat().st_size
            if size > max_size:
                return {"success": False, "error": f"File exceeds max size ({size} > {max_size})", "content": ""}
            content = resolved.read_text(errors="replace")
            return {"success": True, "content": content, "size": size}
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc), "content": ""}

    async def write_file(
        self,
        file_path: str,
        content: str,
    ) -> dict[str, Any]:
        """Write *content* to *file_path* safely."""
        path_ok, reason = self._validate_path(file_path)
        if not path_ok:
            return {"success": False, "error": reason}

        resolved = Path(file_path).resolve()
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, errors="replace")
            return {"success": True, "size": len(content)}
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc)}

    async def list_directory(
        self,
        dir_path: str,
        pattern: str = "*",
    ) -> dict[str, Any]:
        """List entries in *dir_path* matching *pattern*."""
        path_ok, reason = self._validate_path(dir_path)
        if not path_ok:
            return {"success": False, "error": reason, "entries": []}

        resolved = Path(dir_path).resolve()
        try:
            entries = [str(e.name) for e in resolved.glob(pattern)]
            return {"success": True, "entries": sorted(entries)}
        except (OSError, ValueError) as exc:
            return {"success": False, "error": str(exc), "entries": []}

    def add_allowed_directory(self, path: str) -> None:
        """Add *path* to the allowed directories list."""
        resolved = Path(path).resolve()
        if resolved not in self._allowed_dirs:
            self._allowed_dirs.append(resolved)

    def remove_allowed_directory(self, path: str) -> None:
        """Remove *path* from the allowed directories list."""
        resolved = Path(path).resolve()
        self._allowed_dirs = [d for d in self._allowed_dirs if d != resolved]

    def get_execution_history(self, count: int = 50) -> list[dict[str, Any]]:
        """Return the most recent *count* execution records."""
        return list(self._execution_history[-count:])

    def _log_execution(self, command: str, result: dict[str, Any]) -> None:
        """Append an entry to the execution history."""
        entry = {
            "command": command,
            "timestamp": time.time(),
            "success": result.get("success", False),
            "returncode": result.get("returncode"),
            "error": result.get("error", ""),
        }
        self._execution_history.append(entry)
        if len(self._execution_history) > 500:
            self._execution_history = self._execution_history[-500:]
