"""
Unified automation orchestrator for JARVIS.
============================================
Wires together all automation subsystems into a single, cohesive API.

Subsystems:
    - ApplicationManager — open, close, launch apps
    - FileOperations — search, move, rename, delete, create folders
    - SystemControl — brightness, volume, lock, shutdown, restart, sleep
    - ScreenshotManager — screen capture
    - ClipboardManager — clipboard operations
    - KeyboardMouseController — keyboard and mouse input
    - MultiMonitorManager — multi-display support
    - ProcessManager — process monitoring and control

All operations go through SafetyGate for confirmation on destructive actions.

Usage:
    auto = AutomationSystem(settings)
    await auto.initialize()
    await auto.open_application("notepad")
    await auto.take_screenshot()
    await auto.set_volume(50)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from jarvis.config.settings import AutomationSettings
from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate
from jarvis.core.automation.app_manager import ApplicationManager
from jarvis.core.automation.file_operations import FileOperations
from jarvis.core.automation.system_control import SystemControl
from jarvis.core.automation.screenshot import ScreenshotManager
from jarvis.core.automation.clipboard import ClipboardManager
from jarvis.core.automation.keyboard_mouse import KeyboardMouseController
from jarvis.core.automation.multi_monitor import MultiMonitorManager
from jarvis.core.automation.process_manager import ProcessManager

logger = logging.getLogger(__name__)


class AutomationSystem:
    """Unified desktop automation system for JARVIS.

    Provides a single interface to all automation capabilities while
    maintaining safety gates for destructive operations.

    Example:
        auto = AutomationSystem(settings)
        await auto.initialize()

        # Application management
        await auto.open_application("notepad")
        await auto.close_application("notepad")

        # System control
        await auto.set_volume(75)
        await auto.set_brightness(50)
        await auto.lock_computer()

        # Screenshots
        result = await auto.take_screenshot()

        # File operations
        result = await auto.search_files("*.py", root=".")

        # Keyboard/mouse
        await auto.type_text("Hello, world!")
        await auto.mouse_click(500, 300)

        # Clipboard
        text = await auto.get_clipboard()
        await auto.set_clipboard("copied text")
    """

    def __init__(self, settings: AutomationSettings):
        self._settings = settings
        self._safety_gate: SafetyGate | None = None
        self._apps: ApplicationManager | None = None
        self._files: FileOperations | None = None
        self._system: SystemControl | None = None
        self._screen: ScreenshotManager | None = None
        self._clipboard: ClipboardManager | None = None
        self._kb: KeyboardMouseController | None = None
        self._monitors: MultiMonitorManager | None = None
        self._processes: ProcessManager | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all automation subsystems."""
        if self._initialized:
            return

        logger.info("Initializing automation system...")

        self._safety_gate = SafetyGate(
            auto_approve_safe=True,
            auto_approve_moderate=True,
            require_confirm_dangerous=True,
            require_confirm_destructive=True,
        )

        self._apps = ApplicationManager(self._safety_gate)
        self._files = FileOperations(
            safety_gate=self._safety_gate,
            allowed_directories=self._settings.allowed_directories,
        )
        self._system = SystemControl(self._safety_gate)
        self._screen = ScreenshotManager(self._safety_gate)
        self._clipboard = ClipboardManager(self._safety_gate)
        self._kb = KeyboardMouseController(self._safety_gate)
        self._monitors = MultiMonitorManager(self._safety_gate)
        self._processes = ProcessManager(self._safety_gate)

        self._initialized = True
        logger.info("Automation system initialized")

    async def shutdown(self) -> None:
        """Clean shutdown."""
        self._initialized = False

    def set_confirmation_callback(
        self,
        callback: Callable[[str, ActionSeverity], Awaitable[bool]],
    ) -> None:
        """Set a custom confirmation callback for safety gate.

        Args:
            callback: Async function that receives (description, severity)
                      and returns True to approve, False to cancel.
        """
        if self._safety_gate:
            self._safety_gate._confirmation_callback = callback

    def pre_approve(self, action_pattern: str) -> None:
        """Pre-approve an action pattern."""
        if self._safety_gate:
            self._safety_gate.pre_approve(action_pattern)

    def block_action(self, action_pattern: str) -> None:
        """Block an action pattern."""
        if self._safety_gate:
            self._safety_gate.block(action_pattern)

    # ──────────────────────────────────────────────
    # Application shortcuts
    # ──────────────────────────────────────────────

    async def open_application(self, name: str, **kwargs) -> ActionResult:
        return await self._apps.open(name, **kwargs)

    async def close_application(self, name: str = "", pid: int | None = None, force: bool = False) -> ActionResult:
        return await self._apps.close(app_name=name, pid=pid, force=force)

    async def launch_game(self, name: str) -> ActionResult:
        return await self._apps.launch_game(name)

    async def list_running_apps(self, filter_name: str = "") -> list:
        return await self._apps.list_running(filter_name)

    # ──────────────────────────────────────────────
    # File operation shortcuts
    # ──────────────────────────────────────────────

    async def search_files(self, pattern: str, root: str = ".", **kwargs) -> ActionResult:
        return await self._files.search(pattern, root=root, **kwargs)

    async def move_file(self, source: str, dest: str) -> ActionResult:
        return await self._files.move(source, dest)

    async def rename_file(self, path: str, new_name: str) -> ActionResult:
        return await self._files.rename(path, new_name)

    async def delete_file(self, path: str, permanent: bool = False) -> ActionResult:
        return await self._files.delete(path, permanent=permanent)

    async def create_folder(self, path: str) -> ActionResult:
        return await self._files.create_folder(path)

    async def get_file_info(self, path: str) -> ActionResult:
        return await self._files.get_info(path)

    # ──────────────────────────────────────────────
    # System control shortcuts
    # ──────────────────────────────────────────────

    async def set_volume(self, level: int) -> ActionResult:
        return await self._system.set_volume(level)

    async def get_volume(self) -> ActionResult:
        return await self._system.get_volume()

    async def set_brightness(self, level: int) -> ActionResult:
        return await self._system.set_brightness(level)

    async def get_brightness(self) -> ActionResult:
        return await self._system.get_brightness()

    async def mute_audio(self) -> ActionResult:
        return await self._system.mute()

    async def lock_computer(self) -> ActionResult:
        return await self._system.lock()

    async def shutdown_computer(self, delay: int = 0, force: bool = False) -> ActionResult:
        return await self._system.shutdown(delay_seconds=delay, force=force)

    async def restart_computer(self, delay: int = 0, force: bool = False) -> ActionResult:
        return await self._system.restart(delay_seconds=delay, force=force)

    async def sleep_computer(self) -> ActionResult:
        return await self._system.sleep()

    async def cancel_shutdown(self) -> ActionResult:
        return await self._system.cancel_shutdown()

    async def get_system_info(self) -> ActionResult:
        return await self._system.get_system_info()

    # ──────────────────────────────────────────────
    # Screenshot shortcuts
    # ──────────────────────────────────────────────

    async def take_screenshot(self, save_path: str | None = None) -> ActionResult:
        return await self._screen.capture_full(save_path)

    async def capture_active_window(self, save_path: str | None = None) -> ActionResult:
        return await self._screen.capture_active_window(save_path)

    async def capture_region(self, x: int, y: int, w: int, h: int) -> ActionResult:
        return await self._screen.capture_region(x, y, w, h)

    # ──────────────────────────────────────────────
    # Clipboard shortcuts
    # ──────────────────────────────────────────────

    async def get_clipboard(self) -> ActionResult:
        return await self._clipboard.get()

    async def set_clipboard(self, text: str) -> ActionResult:
        return await self._clipboard.set(text)

    async def clear_clipboard(self) -> ActionResult:
        return await self._clipboard.clear()

    # ──────────────────────────────────────────────
    # Keyboard/Mouse shortcuts
    # ──────────────────────────────────────────────

    async def type_text(self, text: str) -> ActionResult:
        return await self._kb.type_text(text)

    async def hotkey(self, *keys: str) -> ActionResult:
        return await self._kb.hotkey(*keys)

    async def press_key(self, key: str) -> ActionResult:
        return await self._kb.press_key(key)

    async def mouse_click(self, x: int, y: int, button: str = "left") -> ActionResult:
        return await self._kb.mouse_click(x, y, button)

    async def mouse_move(self, x: int, y: int) -> ActionResult:
        return await self._kb.mouse_move(x, y)

    async def mouse_scroll(self, clicks: int) -> ActionResult:
        return await self._kb.mouse_scroll(clicks)

    # ──────────────────────────────────────────────
    # Multi-monitor shortcuts
    # ──────────────────────────────────────────────

    async def list_monitors(self) -> ActionResult:
        return await self._monitors.list_monitors()

    async def get_primary_monitor(self) -> ActionResult:
        return await self._monitors.get_primary()

    # ──────────────────────────────────────────────
    # Process management shortcuts
    # ──────────────────────────────────────────────

    async def list_processes(self, sort_by: str = "memory", limit: int = 50) -> ActionResult:
        return await self._processes.list_processes(sort_by=sort_by, limit=limit)

    async def find_process(self, name: str = "", pid: int | None = None) -> ActionResult:
        return await self._processes.find(name=name, pid=pid)

    async def kill_process(self, name: str = "", pid: int | None = None, force: bool = False) -> ActionResult:
        return await self._processes.kill(name=name, pid=pid, force=force)

    # ──────────────────────────────────────────────
    # Safety & stats
    # ──────────────────────────────────────────────

    def get_action_log(self, limit: int = 20) -> list[dict]:
        """Get recent action log from safety gate."""
        if self._safety_gate:
            return self._safety_gate.get_log(limit)
        return []

    def get_subsystems(self) -> dict:
        """Get all subsystem instances."""
        return {
            "apps": self._apps,
            "files": self._files,
            "system": self._system,
            "screenshot": self._screen,
            "clipboard": self._clipboard,
            "keyboard_mouse": self._kb,
            "monitors": self._monitors,
            "processes": self._processes,
        }
