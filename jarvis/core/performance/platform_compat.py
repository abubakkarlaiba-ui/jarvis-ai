"""
Performance module — cross-platform compatibility.
===================================================
Detects the host OS and exposes platform-appropriate helpers for paths,
directories, process info, networking, and OS-level operations.
"""

from __future__ import annotations

import getpass
import multiprocessing
import os
import platform
import shutil
import subprocess
import sys
from typing import Any

from jarvis.core.performance.base import PlatformInfo


class PlatformCompat:
    """Cross-platform compatibility utilities."""

    _PLATFORM_MAP: dict[str, str] = {
        "Windows": "windows",
        "Linux": "linux",
        "Darwin": "darwin",
    }

    _priority_map: dict[str, int] = {
        "low": 1,  # below normal
        "normal": 0,
        "high": -1,
        "critical": -2,  # real-time on Windows (requires admin)
    }

    def __init__(self) -> None:
        self._info: PlatformInfo = self.detect()

    # ------------------------------------------------------------------ #
    #  Detection                                                          #
    # ------------------------------------------------------------------ #

    def detect(self) -> PlatformInfo:
        """Detect and return platform info."""
        system_name = platform.system()
        normalized = self._PLATFORM_MAP.get(system_name, system_name.lower())

        info = PlatformInfo(
            system=normalized,
            release=platform.release(),
            version=platform.version(),
            machine=platform.machine(),
            python_version=platform.python_version(),
            is_windows=normalized == "windows",
            is_linux=normalized == "linux",
            is_macos=normalized == "darwin",
            shell=self.get_shell(),
            path_separator=self.get_path_separator(),
            temp_dir=self.get_temp_dir(),
            home_dir=self.get_home_dir(),
        )
        self._info = info
        return info

    def get_platform(self) -> str:
        """Return 'windows', 'linux', or 'darwin'."""
        return self._info.system

    # ------------------------------------------------------------------ #
    #  Boolean helpers                                                    #
    # ------------------------------------------------------------------ #

    def is_windows(self) -> bool:
        return self._info.is_windows

    def is_linux(self) -> bool:
        return self._info.is_linux

    def is_macos(self) -> bool:
        return self._info.is_macos

    # ------------------------------------------------------------------ #
    #  Paths                                                              #
    # ------------------------------------------------------------------ #

    def get_path_separator(self) -> str:
        """Return path separator ('\\\\' or '/')."""
        return os.sep

    def get_temp_dir(self) -> str:
        """Get platform temp directory."""
        if self.is_windows():
            return os.environ.get("TEMP", os.environ.get("TMP", os.path.join(os.environ.get("SystemDrive", "C:"), "Temp")))
        return "/tmp"

    def get_home_dir(self) -> str:
        """Get user home directory."""
        return os.path.expanduser("~")

    def get_data_dir(self) -> str:
        """Get platform-appropriate data directory."""
        if self.is_windows():
            return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "JARVIS")
        if self.is_macos():
            return os.path.join(self.get_home_dir(), "Library", "Application Support", "JARVIS")
        return os.path.join(self.get_home_dir(), ".local", "share", "jarvis")

    def get_config_dir(self) -> str:
        """Get platform-appropriate config directory."""
        if self.is_windows():
            return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "JARVIS")
        if self.is_macos():
            return os.path.join(self.get_home_dir(), "Library", "Preferences", "JARVIS")
        return os.path.join(self.get_home_dir(), ".config", "jarvis")

    def get_cache_dir(self) -> str:
        """Get platform-appropriate cache directory."""
        if self.is_windows():
            return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JARVIS", "Cache")
        if self.is_macos():
            return os.path.join(self.get_home_dir(), "Library", "Caches", "JARVIS")
        return os.path.join(self.get_home_dir(), ".cache", "jarvis")

    def get_log_dir(self) -> str:
        """Get platform-appropriate log directory."""
        if self.is_windows():
            return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "JARVIS", "Logs")
        if self.is_macos():
            return os.path.join(self.get_home_dir(), "Library", "Logs", "JARVIS")
        return os.path.join(self.get_home_dir(), ".local", "state", "jarvis", "logs")

    def normalize_path(self, path: str) -> str:
        """Normalize path separators for the current platform."""
        if self.is_windows():
            return path.replace("/", os.sep)
        return path.replace("\\", os.sep)

    # ------------------------------------------------------------------ #
    #  Process info                                                       #
    # ------------------------------------------------------------------ #

    def get_process_name(self) -> str:
        """Get current process name."""
        try:
            import psutil
            return psutil.Process().name()
        except Exception:
            return os.path.basename(sys.argv[0]) if sys.argv else "unknown"

    def get_pid(self) -> int:
        """Get current process ID."""
        return os.getpid()

    # ------------------------------------------------------------------ #
    #  System resources                                                   #
    # ------------------------------------------------------------------ #

    def get_cpu_count(self) -> int:
        """Get number of CPU cores."""
        try:
            import psutil
            return psutil.cpu_count(logical=True) or multiprocessing.cpu_count()
        except Exception:
            return multiprocessing.cpu_count()

    def get_total_memory(self) -> int:
        """Get total system memory in bytes."""
        try:
            import psutil
            return psutil.virtual_memory().total
        except Exception:
            if self.is_windows():
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    c_ulonglong = ctypes.c_ulonglong
                    mem = c_ulonglong()
                    kernel32.GetPhysicallyInstalledMemory(ctypes.byref(mem))
                    return mem.value
                except Exception:
                    return 0
            return 0

    def is_admin(self) -> bool:
        """Check if running as admin/root."""
        try:
            if self.is_windows():
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            return os.geteuid() == 0
        except Exception:
            return False

    def get_shell(self) -> str:
        """Get default shell (powershell, bash, zsh)."""
        if self.is_windows():
            return "powershell"
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            return "zsh"
        return "bash"

    # ------------------------------------------------------------------ #
    #  File / network                                                     #
    # ------------------------------------------------------------------ #

    def open_file(self, file_path: str) -> bool:
        """Open file with the platform default application."""
        try:
            if self.is_windows():
                os.startfile(file_path)
            elif self.is_macos():
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
            return True
        except Exception:
            return False

    def get_network_interfaces(self) -> list[dict]:
        """List network interfaces with addresses."""
        try:
            import psutil
            interfaces: list[dict] = []
            for name, addrs in psutil.net_if_addrs().items():
                entry: dict[str, Any] = {"name": name, "addresses": []}
                for addr in addrs:
                    entry["addresses"].append({
                        "family": str(addr.family),
                        "address": addr.address,
                        "netmask": addr.netmask,
                        "broadcast": addr.broadcast,
                    })
                interfaces.append(entry)
            return interfaces
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    #  Environment                                                        #
    # ------------------------------------------------------------------ #

    def get_environment(self, key: str, default: str | None = None) -> str | None:
        """Get an environment variable."""
        return os.environ.get(key, default)

    def set_environment(self, key: str, value: str) -> None:
        """Set an environment variable."""
        os.environ[key] = value

    # ------------------------------------------------------------------ #
    #  Process management                                                 #
    # ------------------------------------------------------------------ #

    def run_background(self, command: str) -> Any:
        """Run a command in the background (platform-appropriate)."""
        if self.is_windows():
            return subprocess.Popen(
                command,
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return subprocess.Popen(
            command,
            shell=True,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def set_process_priority(self, priority: str = "normal") -> bool:
        """Set the current process priority."""
        try:
            import psutil
            proc = psutil.Process()
            level = priority.lower()
            if self.is_windows():
                windows_map = {
                    "low": psutil.BELOW_NORMAL_PRIORITY_CLASS,
                    "normal": psutil.NORMAL_PRIORITY_CLASS,
                    "high": psutil.HIGH_PRIORITY_CLASS,
                    "critical": psutil.REALTIME_PRIORITY_CLASS,
                }
                proc.nice(windows_map.get(level, psutil.NORMAL_PRIORITY_CLASS))
            else:
                unix_map = {
                    "low": 10,
                    "normal": 0,
                    "high": -10,
                    "critical": -20,
                }
                proc.nice(unix_map.get(level, 0))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Aggregated info                                                    #
    # ------------------------------------------------------------------ #

    def get_platform_info(self) -> dict[str, Any]:
        """Get full platform information dict."""
        return {
            "system": self._info.system,
            "release": self._info.release,
            "version": self._info.version,
            "machine": self._info.machine,
            "python_version": self._info.python_version,
            "is_windows": self._info.is_windows,
            "is_linux": self._info.is_linux,
            "is_macos": self._info.is_macos,
            "shell": self._info.shell,
            "path_separator": self._info.path_separator,
            "temp_dir": self._info.temp_dir,
            "home_dir": self._info.home_dir,
            "data_dir": self.get_data_dir(),
            "config_dir": self.get_config_dir(),
            "cache_dir": self.get_cache_dir(),
            "log_dir": self.get_log_dir(),
            "is_admin": self.is_admin(),
            "cpu_count": self.get_cpu_count(),
            "total_memory": self.get_total_memory(),
            "username": getpass.getuser(),
            "pid": self.get_pid(),
        }
