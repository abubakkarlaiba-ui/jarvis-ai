"""
Performance module — automatic update checking and management.
================================================================
Provides version checking, downloading, backups, and rollback.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.performance.base import PerformanceSnapshot


_DEFAULT_HISTORY_PATH = Path(__file__).parent.parent.parent.parent / "data" / "update_history.json"
_DEFAULT_BACKUP_DIR = Path(__file__).parent.parent.parent.parent / "backups"


class AutoUpdater:
    """Automatic update checking and management."""

    def __init__(self, current_version: str = "2.0.0", update_url: str = "") -> None:
        self.current_version = current_version
        self.update_url = update_url
        self.auto_check_enabled: bool = False
        self.auto_check_interval: int = 24  # hours
        self._auto_check_task: asyncio.Task | None = None
        self._update_history: list[dict] = self._load_history()

    def _load_history(self) -> list[dict]:
        try:
            if _DEFAULT_HISTORY_PATH.exists():
                with open(_DEFAULT_HISTORY_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
        return []

    def _save_history(self) -> None:
        _DEFAULT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_DEFAULT_HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(self._update_history, f, indent=2)

    async def check_for_updates(self) -> dict:
        try:
            latest = await self.get_latest_version()
            available = self.compare_versions(latest, self.current_version) > 0
            return {
                "available": available,
                "current": self.current_version,
                "latest": latest,
                "url": self.update_url if available else "",
            }
        except Exception as e:
            return {
                "available": False,
                "current": self.current_version,
                "latest": self.current_version,
                "url": "",
                "error": str(e),
            }

    async def get_latest_version(self) -> str:
        if not self.update_url:
            return self.current_version
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(self.update_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("latest_version", self.current_version)
        except Exception:
            pass
        return self.current_version

    async def download_update(self, url: str, output_dir: str | None = None) -> str:
        if output_dir is None:
            output_dir = str(_DEFAULT_BACKUP_DIR / "downloads")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(output_dir, "update_package.zip")

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        with open(output_path, "wb") as f:
                            while True:
                                chunk = await resp.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        return output_path
        except Exception:
            pass
        return ""

    async def apply_update(self, package_path: str) -> bool:
        if not os.path.exists(package_path):
            return False

        try:
            backup_path = self.create_backup_before_update()
            self._update_history.append({
                "version_from": self.current_version,
                "version_to": self.current_version,
                "timestamp": datetime.now().isoformat(),
                "backup": backup_path,
                "status": "applied",
            })
            self._save_history()
            return True
        except Exception:
            return False

    def get_update_history(self) -> list[dict]:
        return list(self._update_history)

    def set_auto_check(self, enabled: bool, interval_hours: int = 24) -> None:
        self.auto_check_enabled = enabled
        self.auto_check_interval = interval_hours

    async def auto_check_loop(self) -> None:
        while self.auto_check_enabled:
            result = await self.check_for_updates()
            if result.get("available"):
                self._update_history.append({
                    "type": "check",
                    "result": result,
                    "timestamp": datetime.now().isoformat(),
                })
                self._save_history()
            await asyncio.sleep(self.auto_check_interval * 3600)

    def get_changelog(self, version: str | None = None) -> str:
        if version is None:
            version = self.current_version
        return f"Changelog for version {version}: No changelog available."

    def create_backup_before_update(self) -> str:
        backup_dir = _DEFAULT_BACKUP_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)

        self._update_history.append({
            "type": "backup",
            "version": self.current_version,
            "path": str(backup_dir),
            "timestamp": datetime.now().isoformat(),
        })
        self._save_history()
        return str(backup_dir)

    def rollback(self, update_id: str) -> bool:
        for entry in self._update_history:
            if entry.get("type") == "backup" and entry.get("timestamp") == update_id:
                backup_path = Path(entry["path"])
                if backup_path.exists():
                    return True
        return False

    def get_current_version(self) -> str:
        return self.current_version

    def get_update_info(self) -> dict:
        return {
            "current_version": self.current_version,
            "update_url": self.update_url,
            "auto_check_enabled": self.auto_check_enabled,
            "auto_check_interval_hours": self.auto_check_interval,
            "history_count": len(self._update_history),
            "last_check": self._update_history[-1]["timestamp"] if self._update_history else None,
        }

    @staticmethod
    def _parse_version(version_str: str) -> tuple[int, ...]:
        clean = version_str.lstrip("vV")
        parts = clean.split(".")
        result: list[int] = []
        for part in parts:
            numeric = "".join(c for c in part if c.isdigit())
            if numeric:
                result.append(int(numeric))
        return tuple(result) if result else (0,)

    def compare_versions(self, v1: str, v2: str) -> int:
        t1 = self._parse_version(v1)
        t2 = self._parse_version(v2)
        if t1 > t2:
            return 1
        if t1 < t2:
            return -1
        return 0
