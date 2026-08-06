"""
Application manager for JARVIS desktop automation.
===================================================
Open, close, and launch applications with safety checks.

Supports:
    - Opening apps by name or path
    - Closing apps by name or PID
    - Launching games via Steam/shortcuts
    - Listing running processes
    - UAC elevation requests

Usage:
    manager = ApplicationManager(safety_gate)
    await manager.open("notepad")
    await manager.close("calc")
    await manager.launch_game("Cyberpunk 2077")
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)

# Common Windows apps with executable names
COMMON_APPS: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "wordpad": "write.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "settings": "ms-settings:",
    "control panel": "control",
    "Snipping Tool": "SnippingTool.exe",
    "snipping tool": "SnippingTool.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "teams": "ms-teams.exe",
    "slack": "slack.exe",
    "discord": "Discord.exe",
    "spotify": "Spotify.exe",
    "visual studio code": "code.exe",
    "vscode": "code.exe",
    "vs code": "code.exe",
    "intellij": "idea64.exe",
    "pycharm": "pycharm64.exe",
    "sublime": "sublime_text.exe",
    "notepad++": "notepad++.exe",
    "7zip": "7zFM.exe",
    "winrar": "WinRAR.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "word": "WINWORD.EXE",
    "excel": "EXCEL.EXE",
    "powerpoint": "POWERPNT.EXE",
    "outlook": "OUTLOOK.EXE",
    "onenote": "ONENOTE.EXE",
}


@dataclass
class RunningApp:
    """Info about a running application."""
    name: str
    pid: int
    executable: str
    title: str = ""
    memory_mb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "pid": self.pid,
            "executable": self.executable,
            "title": self.title,
            "memory_mb": round(self.memory_mb, 1),
        }


class ApplicationManager:
    """Manage desktop applications with safety gates.

    Example:
        gate = SafetyGate()
        manager = ApplicationManager(gate)
        result = await manager.open("notepad")
        apps = await manager.list_running()
    """

    def __init__(self, safety_gate: SafetyGate | None = None):
        self._gate = safety_gate or SafetyGate()
        self._game_launchers: dict[str, str] = {}

    async def open(
        self,
        app_name: str,
        args: list[str] | None = None,
        working_dir: str | None = None,
        elevated: bool = False,
    ) -> ActionResult:
        """Open an application by name or path.

        Args:
            app_name: Application name, executable, or full path.
            args: Optional command-line arguments.
            working_dir: Optional working directory.
            elevated: Request UAC elevation.

        Returns:
            ActionResult with success status and process info.
        """
        start = time.perf_counter()
        description = f"Open application: {app_name}"

        if not await self._gate.check(ActionSeverity.MODERATE, description, f"open:{app_name}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            exe = self._resolve_executable(app_name)
            cmd = [exe] + (args or [])

            if elevated:
                cmd = ["powershell", "-Command", f"Start-Process '{exe}' -Verb RunAs"]
                if args:
                    cmd = ["powershell", "-Command", f"Start-Process '{exe}' -ArgumentList '{' '.join(args)}' -Verb RunAs"]

            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if not elevated else 0
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                creationflags=creation_flags,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            elapsed = (time.perf_counter() - start) * 1000
            logger.info("Opened %s (pid=%d)", app_name, process.pid)

            return ActionResult(
                success=True,
                message=f"Opened {app_name} (PID: {process.pid})",
                data={"pid": process.pid, "executable": exe, "args": args or []},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

        except FileNotFoundError:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=False,
                message=f"Application not found: {app_name}",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Failed to open %s: %s", app_name, exc)
            return ActionResult(
                success=False,
                message=f"Failed to open {app_name}: {exc}",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

    async def close(
        self,
        app_name: str | None = None,
        pid: int | None = None,
        force: bool = False,
    ) -> ActionResult:
        """Close an application by name or PID.

        Args:
            app_name: Application name to close.
            pid: Process ID to close.
            force: Force close (kill).

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        description = f"Close application: {app_name or pid}"
        severity = ActionSeverity.DANGEROUS if force else ActionSeverity.MODERATE

        if not await self._gate.check(severity, description, f"close:{app_name or pid}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if pid:
                result = await self._kill_pid(pid, force)
            elif app_name:
                result = await self._kill_by_name(app_name, force)
            else:
                return ActionResult(success=False, message="Specify app_name or pid")

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=result,
                message=f"Closed {app_name or pid}" if result else f"Failed to close {app_name or pid}",
                severity=severity,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Failed to close %s: %s", app_name, exc)
            return ActionResult(
                success=False,
                message=f"Failed to close {app_name}: {exc}",
                duration_ms=elapsed,
            )

    async def launch_game(self, game_name: str) -> ActionResult:
        """Launch a game via Steam or registered handler.

        Args:
            game_name: Game name or Steam app ID.

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        description = f"Launch game: {game_name}"

        if not await self._gate.check(ActionSeverity.MODERATE, description, f"game:{game_name}"):
            return ActionResult(success=False, message="Cancelled by user", cancelled=True)

        try:
            if game_name.isdigit():
                cmd = ["cmd", "/c", "start", "steam://rungameid/" + game_name]
            else:
                steam_path = self._find_steam()
                if steam_path:
                    cmd = ["cmd", "/c", "start", f"steam://search/text/{game_name}"]
                else:
                    return ActionResult(
                        success=False,
                        message="Steam not found. Install Steam or provide a Steam app ID.",
                        duration_ms=(time.perf_counter() - start) * 1000,
                    )

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Launching {game_name}",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=False,
                message=f"Failed to launch game: {exc}",
                duration_ms=elapsed,
            )

    async def list_running(self, filter_name: str = "") -> list[RunningApp]:
        """List running applications.

        Args:
            filter_name: Optional filter by process name.

        Returns:
            List of RunningApp objects.
        """
        try:
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
            if filter_name:
                cmd.extend(["/FI", f"IMAGENAME eq {filter_name}*"])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            apps = []
            for line in stdout.decode(errors="ignore").strip().split("\n"):
                if not line or line.startswith('"Name"'):
                    continue
                parts = line.strip('"').split('","')
                if len(parts) >= 5:
                    name = parts[0]
                    pid_str = parts[1]
                    try:
                        pid = int(pid_str)
                    except ValueError:
                        continue
                    mem_str = parts[4].replace(" K", "").replace(",", "")
                    try:
                        mem_mb = float(mem_str) / 1024
                    except ValueError:
                        mem_mb = 0.0
                    apps.append(RunningApp(
                        name=name,
                        pid=pid,
                        executable=name,
                        memory_mb=mem_mb,
                    ))
            return apps

        except Exception as exc:
            logger.error("Failed to list processes: %s", exc)
            return []

    def _resolve_executable(self, app_name: str) -> str:
        """Resolve app name to executable path."""
        lower = app_name.lower().strip()

        if lower in COMMON_APPS:
            return COMMON_APPS[lower]

        if os.path.isfile(app_name):
            return app_name

        if lower.endswith(".exe"):
            return lower

        return app_name

    async def _kill_pid(self, pid: int, force: bool) -> bool:
        """Kill a process by PID."""
        try:
            flag = "/F" if force else ""
            proc = await asyncio.create_subprocess_exec(
                "taskkill", flag, "/PID", str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    async def _kill_by_name(self, name: str, force: bool) -> bool:
        """Kill processes by name."""
        try:
            flag = "/F" if force else ""
            proc = await asyncio.create_subprocess_exec(
                "taskkill", flag, "/IM", name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception:
            return False

    def _find_steam(self) -> str | None:
        """Find Steam installation path."""
        candidates = [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
            os.path.expanduser(r"~\AppData\Local\Steam\steam.exe"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None
