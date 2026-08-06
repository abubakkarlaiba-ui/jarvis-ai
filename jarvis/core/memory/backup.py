"""
Memory backup and export system for JARVIS.
=============================================
Provides backup, restore, and export capabilities for the memory system.

Backups are timestamped snapshots of all memory data that can be
restored in case of data loss or corruption.

Usage:
    backup = MemoryBackup(settings)
    await backup.create_backup()
    await backup.restore_backup("backup_20240115_120000")
    await backup.export_all("export.json")
"""

from __future__ import annotations

import json
import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


class MemoryBackup:
    """Manages memory backups and exports.

    Example:
        backup = MemoryBackup(settings)
        # Create a backup
        backup_id = await backup.create_backup()
        # List backups
        backups = await backup.list_backups()
        # Restore
        await backup.restore_backup(backups[0]["id"])
    """

    def __init__(self, settings: MemorySettings):
        self._backup_dir = Path(settings.backup_dir)
        self._data_dir = Path(settings.data_dir)
        self._max_backups = settings.max_backups
        self._enabled = settings.backup_enabled

    async def create_backup(self, label: str = "") -> str:
        """Create a backup of all memory data.

        Args:
            label: Optional label for the backup.

        Returns:
            Backup ID string.
        """
        if not self._enabled:
            logger.warning("Backups are disabled")
            return ""

        ensure_directory(self._backup_dir)

        timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}" + (f"_{label}" if label else "")
        backup_path = self._backup_dir / f"{backup_id}.zip"

        try:
            with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Backup all memory files
                for file_path in self._data_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(self._data_dir)
                        zf.write(file_path, arcname)

            size_kb = backup_path.stat().st_size / 1024
            logger.info("Backup created: %s (%.1f KB)", backup_id, size_kb)

            # Enforce max backups
            await self._cleanup_old_backups()

            return backup_id

        except Exception as exc:
            logger.error("Backup failed: %s", exc)
            return ""

    async def restore_backup(self, backup_id: str) -> bool:
        """Restore memory from a backup.

        Args:
            backup_id: The backup to restore (without .zip extension).

        Returns:
            True on success.
        """
        backup_path = self._backup_dir / f"{backup_id}.zip"
        if not backup_path.exists():
            logger.error("Backup not found: %s", backup_id)
            return False

        try:
            # Create a backup of current state first
            await self.create_backup(label="pre_restore")

            # Extract backup
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall(self._data_dir)

            logger.info("Restored from backup: %s", backup_id)
            return True

        except Exception as exc:
            logger.error("Restore failed: %s", exc)
            return False

    async def export_all(self, output_path: str) -> bool:
        """Export all memory data to a single JSON file.

        Args:
            output_path: Path for the export file.

        Returns:
            True on success.
        """
        try:
            export_data = {
                "exported_at": utc_now().isoformat(),
                "version": "1.0",
                "data": {},
            }

            for file_path in self._data_dir.rglob("*.json"):
                rel_path = str(file_path.relative_to(self._data_dir))
                try:
                    content = json.loads(file_path.read_text(encoding="utf-8"))
                    export_data["data"][rel_path] = content
                except Exception:
                    continue

            Path(output_path).write_text(
                json.dumps(export_data, indent=2, default=str),
                encoding="utf-8",
            )

            logger.info("Exported all memory to: %s", output_path)
            return True

        except Exception as exc:
            logger.error("Export failed: %s", exc)
            return False

    async def import_data(self, import_path: str) -> bool:
        """Import memory data from an export file.

        Args:
            import_path: Path to the export file.

        Returns:
            True on success.
        """
        try:
            data = json.loads(Path(import_path).read_text(encoding="utf-8"))
            for rel_path, content in data.get("data", {}).items():
                target = self._data_dir / rel_path
                ensure_directory(target.parent)
                target.write_text(
                    json.dumps(content, indent=2, default=str),
                    encoding="utf-8",
                )
            logger.info("Imported memory from: %s", import_path)
            return True
        except Exception as exc:
            logger.error("Import failed: %s", exc)
            return False

    async def list_backups(self) -> list[dict]:
        """List all available backups."""
        backups = []
        for backup_file in sorted(self._backup_dir.glob("backup_*.zip"), reverse=True):
            stat = backup_file.stat()
            backups.append({
                "id": backup_file.stem,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": str(stat.st_mtime),
                "path": str(backup_file),
            })
        return backups

    async def _cleanup_old_backups(self) -> None:
        """Remove old backups beyond the retention limit."""
        backups = sorted(self._backup_dir.glob("backup_*.zip"), key=lambda f: f.stat().st_mtime)
        while len(backups) > self._max_backups:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.debug("Removed old backup: %s", oldest.name)
