"""
Desktop automation module for JARVIS.
======================================
Safe, confirmation-gated system control with comprehensive capabilities:
    - Application management (open, close, launch)
    - File operations (search, move, rename, delete, create folders)
    - System control (brightness, volume, lock, shutdown, restart, sleep)
    - Screenshots and clipboard
    - Keyboard/mouse automation
    - Multi-monitor support
    - Process management

All destructive operations require confirmation before execution.

Quick Start:
    from jarvis.core.automation import AutomationSystem
    auto = AutomationSystem(settings)
    await auto.initialize()
    await auto.open_application("notepad")
    await auto.take_screenshot()
"""

from jarvis.core.automation.automation import AutomationSystem
from jarvis.core.automation.base import ActionSeverity, ActionResult, SafetyGate
from jarvis.core.automation.app_manager import ApplicationManager
from jarvis.core.automation.file_operations import FileOperations
from jarvis.core.automation.system_control import SystemControl
from jarvis.core.automation.screenshot import ScreenshotManager
from jarvis.core.automation.clipboard import ClipboardManager
from jarvis.core.automation.keyboard_mouse import KeyboardMouseController
from jarvis.core.automation.multi_monitor import MultiMonitorManager
from jarvis.core.automation.process_manager import ProcessManager

__all__ = [
    "AutomationSystem",
    "ActionSeverity",
    "ActionResult",
    "SafetyGate",
    "ApplicationManager",
    "FileOperations",
    "SystemControl",
    "ScreenshotManager",
    "ClipboardManager",
    "KeyboardMouseController",
    "MultiMonitorManager",
    "ProcessManager",
]
