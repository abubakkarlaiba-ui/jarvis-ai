"""
Clipboard manager for JARVIS desktop automation.
==================================================
Read, write, and manage clipboard contents with history.

Capabilities:
    - Get current clipboard text
    - Set clipboard text
    - Get clipboard history
    - Clear clipboard
    - Copy/paste operations

Usage:
    clip = ClipboardManager(safety_gate)
    text = await clip.get()
    await clip.set("Hello, world!")
    await clip.clear()
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)


@dataclass
class ClipboardEntry:
    """A clipboard history entry."""
    content: str
    timestamp: float
    content_type: str = "text"
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "content": self.content[:500],
            "timestamp": self.timestamp,
            "content_type": self.content_type,
            "source": self.source,
        }


class ClipboardManager:
    """Manage clipboard with history tracking.

    Example:
        gate = SafetyGate()
        clip = ClipboardManager(gate, history_size=50)
        await clip.set("copied text")
        text = await clip.get()
        history = await clip.get_history()
    """

    def __init__(
        self,
        safety_gate: SafetyGate | None = None,
        history_size: int = 50,
    ):
        self._gate = safety_gate or SafetyGate()
        self._history: deque[ClipboardEntry] = deque(maxlen=history_size)
        self._last_content: str = ""

    async def get(self) -> ActionResult:
        """Get current clipboard content."""
        start = time.perf_counter()
        try:
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            $clip = [System.Windows.Forms.Clipboard]::GetText()
            $clip
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            content = stdout.decode(errors="ignore").strip()

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Clipboard: {content[:100]}..." if len(content) > 100 else f"Clipboard: {content}",
                data={"content": content, "length": len(content)},
                severity=ActionSeverity.SAFE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Get clipboard failed: {exc}", duration_ms=elapsed)

    async def set(self, text: str, source: str = "jarvis") -> ActionResult:
        """Set clipboard content.

        Args:
            text: Text to copy to clipboard.
            source: Source identifier for history tracking.
        """
        start = time.perf_counter()
        description = f"Set clipboard: {text[:50]}..." if len(text) > 50 else f"Set clipboard: {text}"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "clipboard_set"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.Clipboard]::SetText('{text.replace("'", "''")}')
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            entry = ClipboardEntry(
                content=text,
                timestamp=time.time(),
                source=source,
            )
            self._history.append(entry)
            self._last_content = text

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Clipboard set ({len(text)} chars)",
                data={"length": len(text)},
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Set clipboard failed: {exc}", duration_ms=elapsed)

    async def clear(self) -> ActionResult:
        """Clear the clipboard."""
        start = time.perf_counter()
        if not await self._gate.check(ActionSeverity.MODERATE, "Clear clipboard", "clipboard_clear"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.Clipboard]::Clear()
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Clipboard cleared",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Clear failed: {exc}", duration_ms=elapsed)

    async def get_history(self, limit: int = 20) -> ActionResult:
        """Get clipboard history."""
        items = list(self._history)[-limit:]
        return ActionResult(
            success=True,
            message=f"Clipboard history: {len(items)} items",
            data=[e.to_dict() for e in reversed(items)],
            severity=ActionSeverity.SAFE,
        )

    async def paste(self) -> ActionResult:
        """Simulate Ctrl+V paste operation."""
        start = time.perf_counter()
        try:
            ps_script = """
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.SendKeys]::SendWait("^v")
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message="Pasted from clipboard",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Paste failed: {exc}", duration_ms=elapsed)
