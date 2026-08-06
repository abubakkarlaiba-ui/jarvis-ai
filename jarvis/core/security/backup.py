"""
Security module — automatic encrypted backups of critical data.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.security.base import BackupManifest
from jarvis.core.security.encryption import EncryptionManager


class BackupManager:
    def __init__(
        self,
        backup_dir: str = "./data/backups",
        encryption: EncryptionManager | None = None,
        max_backups: int = 10,
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.encryption = encryption or EncryptionManager()
        self.max_backups = max_backups
        self._auto_backup_timer: threading.Timer | None = None

    # ── backup creation ──────────────────────────────────────────
    async def create_backup(
        self, label: str = "", include: list[str] | None = None
    ) -> BackupManifest:
        if include is None:
            include = self._get_default_include()

        backup_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + os.urandom(4).hex()
        archive_name = f"{backup_id}.tar.gz"
        archive_path = self.backup_dir / archive_name
        encrypted_path = self.backup_dir / f"{archive_name}.enc"
        manifest_path = self.backup_dir / f"{backup_id}.json"

        files = []
        for pattern in include:
            p = Path(pattern)
            if p.is_dir():
                files.extend(str(f) for f in p.rglob("*") if f.is_file())
            elif p.is_file():
                files.append(str(p))

        files = [f for f in files if Path(f).exists()]

        archive_str = self._create_archive(files, str(archive_path))

        data = Path(archive_str).read_bytes()
        checksum = self.calculate_checksum(data)

        encrypted_content = self.encryption.encrypt(data)
        encrypted_path.write_text(encrypted_content, encoding="utf-8")

        if archive_path.exists():
            archive_path.unlink()

        manifest = BackupManifest(
            id=backup_id,
            timestamp=datetime.now(),
            files=files,
            size_bytes=len(data),
            checksum=checksum,
            encrypted=True,
            label=label or f"backup_{backup_id}",
        )

        manifest_dict = {
            "id": manifest.id,
            "timestamp": manifest.timestamp.isoformat(),
            "files": manifest.files,
            "size_bytes": manifest.size_bytes,
            "checksum": manifest.checksum,
            "encrypted": manifest.encrypted,
            "label": manifest.label,
        }
        manifest_path.write_text(json.dumps(manifest_dict, indent=2), encoding="utf-8")

        self.cleanup_old_backups()
        return manifest

    # ── backup restoration ───────────────────────────────────────
    async def restore_backup(
        self, backup_id: str, output_dir: str | None = None
    ) -> bool:
        manifest = self.get_backup(backup_id)
        if not manifest:
            return False

        archive_path = self.backup_dir / f"{manifest.id}.tar.gz.enc"
        if not archive_path.exists():
            return False

        encrypted_content = archive_path.read_text(encoding="utf-8")
        data = self.encryption.decrypt(encrypted_content)

        current_checksum = self.calculate_checksum(data)
        if current_checksum != manifest.checksum:
            return False

        if output_dir is None:
            output_dir = str(self.backup_dir / "restores" / manifest.id)

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        temp_archive = self.backup_dir / f"{manifest.id}_restore.tar.gz"
        temp_archive.write_bytes(data)

        try:
            self._extract_archive(str(temp_archive), output_dir)
        except Exception:
            return False
        finally:
            if temp_archive.exists():
                temp_archive.unlink()

        return True

    # ── listing & metadata ───────────────────────────────────────
    def list_backups(self) -> list[dict[str, Any]]:
        backups = []
        for manifest_path in sorted(self.backup_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                backups.append(data)
            except (json.JSONDecodeError, OSError):
                continue
        return backups

    def get_backup(self, backup_id: str) -> BackupManifest | None:
        manifest_path = self.backup_dir / f"{backup_id}.json"
        if not manifest_path.exists():
            return None
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return BackupManifest(
                id=data["id"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                files=data.get("files", []),
                size_bytes=data.get("size_bytes", 0),
                checksum=data.get("checksum", ""),
                encrypted=data.get("encrypted", True),
                label=data.get("label", ""),
            )
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def delete_backup(self, backup_id: str) -> bool:
        deleted = False
        for suffix in [".json", ".tar.gz.enc"]:
            path = self.backup_dir / f"{backup_id}{suffix}"
            if path.exists():
                path.unlink()
                deleted = True
        return deleted

    def get_latest_backup(self) -> BackupManifest | None:
        backups = self.list_backups()
        if not backups:
            return None
        latest = backups[0]
        return self.get_backup(latest["id"])

    # ── integrity ────────────────────────────────────────────────
    def calculate_checksum(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def verify_backup(self, backup_id: str) -> bool:
        manifest = self.get_backup(backup_id)
        if not manifest:
            return False

        archive_path = self.backup_dir / f"{backup_id}.tar.gz.enc"
        if not archive_path.exists():
            return False

        encrypted_content = archive_path.read_text(encoding="utf-8")
        data = self.encryption.decrypt(encrypted_content)
        current_checksum = self.calculate_checksum(data)
        return current_checksum == manifest.checksum

    # ── cleanup ──────────────────────────────────────────────────
    def cleanup_old_backups(self) -> int:
        backups = self.list_backups()
        if len(backups) <= self.max_backups:
            return 0

        to_remove = backups[self.max_backups:]
        removed = 0
        for backup_data in to_remove:
            if self.delete_backup(backup_data["id"]):
                removed += 1
        return removed

    # ── defaults & archive helpers ───────────────────────────────
    def _get_default_include(self) -> list[str]:
        return ["data/", "config/", "plugins/"]

    def _create_archive(self, files: list[str], output_path: str) -> str:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_path, "w:gz") as tar:
            for file_path in files:
                p = Path(file_path)
                if p.exists():
                    tar.add(str(p), arcname=str(p))
        return output_path

    def _extract_archive(self, archive_path: str, output_dir: str) -> list[str]:
        extracted: list[str] = []
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=output_dir, filter="data")
            extracted = [member.name for member in tar.getmembers()]
        return extracted

    # ── stats ────────────────────────────────────────────────────
    def get_backup_stats(self) -> dict[str, Any]:
        backups = self.list_backups()
        if not backups:
            return {
                "total_backups": 0,
                "total_size_bytes": 0,
                "oldest": None,
                "newest": None,
            }

        total_size = sum(b.get("size_bytes", 0) for b in backups)
        timestamps = [b.get("timestamp", "") for b in backups]

        return {
            "total_backups": len(backups),
            "total_size_bytes": total_size,
            "oldest": min(timestamps) if timestamps else None,
            "newest": max(timestamps) if timestamps else None,
        }

    # ── auto backup scheduling ───────────────────────────────────
    def schedule_auto_backup(self, interval_hours: int = 24) -> None:
        if self._auto_backup_timer:
            self._auto_backup_timer.cancel()

        import asyncio

        def _run() -> None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self.create_backup(label="auto"))
                else:
                    loop.run_until_complete(self.create_backup(label="auto"))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.create_backup(label="auto"))
            finally:
                self.schedule_auto_backup(interval_hours)

        self._auto_backup_timer = threading.Timer(interval_hours * 3600, _run)
        self._auto_backup_timer.daemon = True
        self._auto_backup_timer.start()
