"""
Screenshot manager for JARVIS desktop automation.
==================================================
Capture screenshots of the full screen, active window, or region.

Supports:
    - Full screen capture
    - Active window capture
    - Region capture (x, y, width, height)
    - Multi-monitor capture
    - Save to file with timestamps

Usage:
    screen = ScreenshotManager(safety_gate)
    result = await screen.capture_full()
    result = await screen.capture_active_window()
    result = await screen.capture_region(0, 0, 800, 600)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """Capture screenshots with safety checks.

    Example:
        gate = SafetyGate()
        screen = ScreenshotManager(gate, save_dir="./screenshots")
        result = await screen.capture_full()
        print(result.data["path"])
    """

    def __init__(
        self,
        safety_gate: SafetyGate | None = None,
        save_dir: str = "./data/screenshots",
    ):
        self._gate = safety_gate or SafetyGate()
        self._save_dir = Path(save_dir)
        self._save_dir.mkdir(parents=True, exist_ok=True)

    def _timestamp(self) -> str:
        return time.strftime("%Y%m%d_%H%M%S")

    async def capture_full(self, save_path: str | None = None) -> ActionResult:
        """Capture the full screen.

        Args:
            save_path: Optional custom save path.

        Returns:
            ActionResult with screenshot file path.
        """
        start = time.perf_counter()
        if not await self._gate.check(ActionSeverity.SAFE, "Take screenshot", "screenshot"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            path = save_path or str(self._save_dir / f"screenshot_{self._timestamp()}.png")

            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $screen = [System.Windows.Forms.Screen]::PrimaryScreen
            $bitmap = New-Object System.Drawing.Bitmap($screen.Bounds.Width, $screen.Bounds.Height)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
            $bitmap.Save('{path}')
            $graphics.Dispose()
            $bitmap.Dispose()
            """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            elapsed = (time.perf_counter() - start) * 1000
            if os.path.exists(path):
                return ActionResult(
                    success=True,
                    message=f"Screenshot saved: {path}",
                    data={"path": path, "type": "full"},
                    severity=ActionSeverity.SAFE,
                    duration_ms=elapsed,
                )
            else:
                return ActionResult(success=False, message="Screenshot file not created", duration_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Screenshot failed: {exc}", duration_ms=elapsed)

    async def capture_active_window(self, save_path: str | None = None) -> ActionResult:
        """Capture the active window.

        Args:
            save_path: Optional custom save path.

        Returns:
            ActionResult with screenshot file path.
        """
        start = time.perf_counter()
        if not await self._gate.check(ActionSeverity.SAFE, "Capture active window", "screenshot_active"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            path = save_path or str(self._save_dir / f"window_{self._timestamp()}.png")

            ps_script = f"""
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Win32 {{
                [DllImport("user32.dll")]
                public static extern IntPtr GetForegroundWindow();
                [DllImport("user32.dll")]
                public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
            }}
            public struct RECT {{
                public int Left, Top, Right, Bottom;
            }}
"@
            $hwnd = [Win32]::GetForegroundWindow()
            $rect = New-Object RECT
            [Win32]::GetWindowRect($hwnd, [ref]$rect)
            $w = $rect.Right - $rect.Left
            $h = $rect.Bottom - $rect.Top
            Add-Type -AssemblyName System.Drawing
            $bitmap = New-Object System.Drawing.Bitmap($w, $h)
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen($rect.Left, $rect.Top, 0, 0, [System.Drawing.Size]::new($w, $h))
            $bitmap.Save('{path}')
            $graphics.Dispose()
            $bitmap.Dispose()
            """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            elapsed = (time.perf_counter() - start) * 1000
            if os.path.exists(path):
                return ActionResult(
                    success=True,
                    message=f"Active window captured: {path}",
                    data={"path": path, "type": "window"},
                    severity=ActionSeverity.SAFE,
                    duration_ms=elapsed,
                )
            return ActionResult(success=False, message="Capture failed", duration_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Capture failed: {exc}", duration_ms=elapsed)

    async def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        save_path: str | None = None,
    ) -> ActionResult:
        """Capture a specific screen region.

        Args:
            x: Left coordinate.
            y: Top coordinate.
            width: Region width.
            height: Region height.
            save_path: Optional custom save path.

        Returns:
            ActionResult with screenshot file path.
        """
        start = time.perf_counter()
        description = f"Capture region ({x},{y} {width}x{height})"
        if not await self._gate.check(ActionSeverity.SAFE, description, "screenshot_region"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            path = save_path or str(self._save_dir / f"region_{self._timestamp()}.png")

            ps_script = f"""
            Add-Type -AssemblyName System.Drawing
            $bitmap = New-Object System.Drawing.Bitmap({width}, {height})
            $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
            $graphics.CopyFromScreen({x}, {y}, 0, 0, [System.Drawing.Size]::new({width}, {height}))
            $bitmap.Save('{path}')
            $graphics.Dispose()
            $bitmap.Dispose()
            """

            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            elapsed = (time.perf_counter() - start) * 1000
            if os.path.exists(path):
                return ActionResult(
                    success=True,
                    message=f"Region captured: {path}",
                    data={"path": path, "type": "region", "x": x, "y": y, "width": width, "height": height},
                    severity=ActionSeverity.SAFE,
                    duration_ms=elapsed,
                )
            return ActionResult(success=False, message="Region capture failed", duration_ms=elapsed)

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Region capture failed: {exc}", duration_ms=elapsed)

    async def list_screenshots(self, limit: int = 20) -> ActionResult:
        """List recent screenshots."""
        try:
            files = sorted(self._save_dir.glob("*.png"), key=lambda f: f.stat().st_mtime, reverse=True)
            items = []
            for f in files[:limit]:
                stat = f.stat()
                items.append({
                    "name": f.name,
                    "path": str(f),
                    "size_kb": round(stat.st_size / 1024, 1),
                    "created_at": stat.st_mtime,
                })
            return ActionResult(
                success=True,
                message=f"Found {len(items)} screenshots",
                data=items,
                severity=ActionSeverity.SAFE,
            )
        except Exception as exc:
            return ActionResult(success=False, message=f"List failed: {exc}")
