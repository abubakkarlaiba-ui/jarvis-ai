"""
Keyboard and mouse automation for JARVIS.
==========================================
Send keystrokes, key combinations, and mouse actions.

Capabilities:
    - Type text
    - Send key combinations (Ctrl+C, Alt+Tab, etc.)
    - Press/release individual keys
    - Mouse move, click, double-click, right-click
    - Mouse drag operations
    - Scroll wheel

Usage:
    kb = KeyboardMouseController(safety_gate)
    await kb.type_text("Hello, world!")
    await kb.hotkey("ctrl", "s")
    await kb.mouse_click(500, 300)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate

logger = logging.getLogger(__name__)

# Windows key name mapping for SendKeys
KEY_MAP: dict[str, str] = {
    "enter": "{ENTER}",
    "return": "{ENTER}",
    "tab": "{TAB}",
    "escape": "{ESC}",
    "esc": "{ESC}",
    "space": " ",
    "backspace": "{BACKSPACE}",
    "delete": "{DEL}",
    "del": "{DEL}",
    "insert": "{INS}",
    "home": "{HOME}",
    "end": "{END}",
    "pageup": "{PGUP}",
    "pagedown": "{PGDN}",
    "up": "{UP}",
    "down": "{DOWN}",
    "left": "{LEFT}",
    "right": "{RIGHT}",
    "f1": "{F1}",
    "f2": "{F2}",
    "f3": "{F3}",
    "f4": "{F4}",
    "f5": "{F5}",
    "f6": "{F6}",
    "f7": "{F7}",
    "f8": "{F8}",
    "f9": "{F9}",
    "f10": "{F10}",
    "f11": "{F11}",
    "f12": "{F12}",
    "capslock": "{CAPSLOCK}",
    "numlock": "{NUMLOCK}",
    "scrolllock": "{SCROLLLOCK}",
    "printscreen": "{PRTSC}",
}

MODIFIER_MAP: dict[str, str] = {
    "ctrl": "^",
    "control": "^",
    "alt": "%",
    "shift": "+",
    "win": "^{ESC}",
    "meta": "^{ESC}",
}


class KeyboardMouseController:
    """Send keyboard and mouse inputs.

    Example:
        gate = SafetyGate()
        kb = KeyboardMouseController(gate)
        await kb.type_text("Hello")
        await kb.hotkey("ctrl", "shift", "esc")
        await kb.mouse_click(500, 300)
    """

    def __init__(self, safety_gate: SafetyGate | None = None):
        self._gate = safety_gate or SafetyGate()

    async def type_text(self, text: str, interval_ms: int = 0) -> ActionResult:
        """Type text character by character.

        Args:
            text: Text to type.
            interval_ms: Delay between keystrokes (0 = default).

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        description = f"Type: {text[:50]}..." if len(text) > 50 else f"Type: {text}"

        if not await self._gate.check(ActionSeverity.DANGEROUS, description, "type"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            escaped = text.replace("~", "{~}").replace("+", "{+}").replace("^", "{^}").replace("%", "{%}")
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.SendKeys]::SendWait('{escaped}')
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
                message=f"Typed {len(text)} characters",
                data={"length": len(text)},
                severity=ActionSeverity.DANGEROUS,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Type failed: {exc}", duration_ms=elapsed)

    async def hotkey(self, *keys: str) -> ActionResult:
        """Send a key combination.

        Args:
            *keys: Keys to press together (e.g., "ctrl", "shift", "esc").

        Returns:
            ActionResult with success status.
        """
        start = time.perf_counter()
        combo = "+".join(keys)
        description = f"Hotkey: {combo}"

        if not await self._gate.check(ActionSeverity.DANGEROUS, description, f"hotkey:{combo}"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            send_keys = []
            for key in keys:
                lower = key.lower()
                if lower in MODIFIER_MAP:
                    send_keys.append(MODIFIER_MAP[lower])
                elif lower in KEY_MAP:
                    send_keys.append(KEY_MAP[lower])
                else:
                    send_keys.append(key.upper() if len(key) == 1 else key)

            combo_str = "".join(send_keys)
            if len(combo_str) > 1 and combo_str[0] in ("^", "%", "+"):
                combo_str = f"({combo_str})"

            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            [System.Windows.Forms.SendKeys]::SendWait('{combo_str}')
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
                message=f"Sent hotkey: {combo}",
                severity=ActionSeverity.DANGEROUS,
                duration_ms=elapsed,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Hotkey failed: {exc}", duration_ms=elapsed)

    async def press_key(self, key: str) -> ActionResult:
        """Press and release a single key.

        Args:
            key: Key name (e.g., "enter", "f5", "a").

        Returns:
            ActionResult with success status.
        """
        lower = key.lower()
        if lower in KEY_MAP:
            send_key = KEY_MAP[lower]
        elif len(key) == 1:
            send_key = key.upper()
        else:
            send_key = f"{{{key.upper()}}}"

        ps_script = f"""
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.SendKeys]::SendWait('{send_key}')
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return ActionResult(success=True, message=f"Pressed: {key}", severity=ActionSeverity.DANGEROUS)
        except Exception as exc:
            return ActionResult(success=False, message=f"Press failed: {exc}")

    async def mouse_move(self, x: int, y: int) -> ActionResult:
        """Move the mouse cursor to absolute coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
        """
        start = time.perf_counter()
        description = f"Move mouse to ({x}, {y})"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "mouse_move"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            ps_script = f"""
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Mouse {{
                [DllImport("user32.dll")]
                public static extern bool SetCursorPos(int X, int Y);
            }}
"@
            [Mouse]::SetCursorPos({x}, {y})
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
                message=f"Mouse moved to ({x}, {y})",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Mouse move failed: {exc}", duration_ms=elapsed)

    async def mouse_click(self, x: int, y: int, button: str = "left") -> ActionResult:
        """Click at coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: "left", "right", or "middle".
        """
        start = time.perf_counter()
        description = f"{button} click at ({x}, {y})"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "mouse_click"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            move_result = await self.mouse_move(x, y)
            if not move_result.success:
                return move_result

            button_map = {"left": "0", "right": "1", "middle": "4"}
            btn = button_map.get(button.lower(), "0")

            ps_script = f"""
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Mouse {{
                [DllImport("user32.dll")]
                public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);
            }}
"@
            [Mouse]::mouse_event({btn}, 0, 0, 0, [IntPtr]::Zero)
            Start-Sleep -Milliseconds 50
            [Mouse]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
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
                message=f"{button.capitalize()} clicked at ({x}, {y})",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Click failed: {exc}", duration_ms=elapsed)

    async def mouse_double_click(self, x: int, y: int) -> ActionResult:
        """Double-click at coordinates."""
        result = await self.mouse_click(x, y)
        if result.success:
            await asyncio.sleep(0.05)
            await self.mouse_click(x, y)
        return result

    async def mouse_right_click(self, x: int, y: int) -> ActionResult:
        """Right-click at coordinates."""
        return await self.mouse_click(x, y, button="right")

    async def mouse_scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> ActionResult:
        """Scroll the mouse wheel.

        Args:
            clicks: Positive = up, negative = down.
            x: Optional X coordinate to scroll at.
            y: Optional Y coordinate to scroll at.
        """
        start = time.perf_counter()
        description = f"Scroll {'up' if clicks > 0 else 'down'} {abs(clicks)} clicks"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "mouse_scroll"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            if x is not None and y is not None:
                await self.mouse_move(x, y)

            scroll_data = clicks * 120
            ps_script = f"""
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Mouse {{
                [DllImport("user32.dll")]
                public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);
            }}
"@
            [Mouse]::mouse_event(2048, 0, 0, {scroll_data}, [IntPtr]::Zero)
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
                message=f"Scrolled {abs(clicks)} clicks {'up' if clicks > 0 else 'down'}",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Scroll failed: {exc}", duration_ms=elapsed)

    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 500,
    ) -> ActionResult:
        """Drag from one point to another.

        Args:
            start_x: Starting X coordinate.
            start_y: Starting Y coordinate.
            end_x: Ending X coordinate.
            end_y: Ending Y coordinate.
            duration_ms: Duration of the drag in milliseconds.
        """
        start = time.perf_counter()
        description = f"Drag from ({start_x},{start_y}) to ({end_x},{end_y})"

        if not await self._gate.check(ActionSeverity.MODERATE, description, "mouse_drag"):
            return ActionResult(success=False, message="Cancelled", cancelled=True)

        try:
            await self.mouse_move(start_x, start_y)
            await asyncio.sleep(0.1)

            ps_script = f"""
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Mouse {{
                [DllImport("user32.dll")]
                public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);
            }}
"@
            [Mouse]::mouse_event(2, 0, 0, 0, [IntPtr]::Zero)
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            steps = max(10, duration_ms // 16)
            dx = (end_x - start_x) / steps
            dy = (end_y - start_y) / steps

            for i in range(1, steps + 1):
                cx = int(start_x + dx * i)
                cy = int(start_y + dy * i)
                await self.mouse_move(cx, cy)
                await asyncio.sleep(duration_ms / 1000 / steps)

            ps_script_up = """
            Add-Type @"
            using System;
            using System.Runtime.InteropServices;
            public class Mouse {{
                [DllImport("user32.dll")]
                public static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, IntPtr dwExtraInfo);
            }}
"@
            [Mouse]::mouse_event(4, 0, 0, 0, [IntPtr]::Zero)
            """
            proc = await asyncio.create_subprocess_exec(
                "powershell", "-Command", ps_script_up,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(
                success=True,
                message=f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})",
                severity=ActionSeverity.MODERATE,
                duration_ms=elapsed,
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=False, message=f"Drag failed: {exc}", duration_ms=elapsed)
