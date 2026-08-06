"""
Security Manager — orchestrator for all security submodules.
==========================================================
Coordinates auth, encryption, permissions, audit, and safety.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.security.audit import AuditLogger
from jarvis.core.security.auth import AuthManager
from jarvis.core.security.backup import BackupManager
from jarvis.core.security.base import (
    AuditAction,
    Permission,
    Role,
    User,
)
from jarvis.core.security.confirmations import ConfirmationManager
from jarvis.core.security.encryption import EncryptionManager
from jarvis.core.security.permissions import PermissionManager
from jarvis.core.security.rate_limiter import RateLimiter
from jarvis.core.security.safe_executor import SafeExecutor
from jarvis.core.security.vault import Vault
from jarvis.core.security.voice_auth import VoiceAuth

logger = logging.getLogger(__name__)


class SecurityManager:
    """Unified security orchestrator.

    Provides a single entry point for all security operations:
    authentication, authorization, encryption, auditing, and safety.
    """

    def __init__(self, data_dir: str = "./data/security"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize sub-modules
        self.encryption = EncryptionManager(
            key_file=str(self.data_dir / "master.key")
        )
        self.auth = AuthManager(
            secret_key=str(self.data_dir / "jwt_secret"),
            token_expiry_hours=24,
        )
        self.voice_auth = VoiceAuth(
            data_dir=str(self.data_dir / "voice")
        )
        self.vault = Vault(
            vault_file=str(self.data_dir / "vault.json"),
            encryption=self.encryption,
        )
        self.permissions = PermissionManager(
            data_dir=str(self.data_dir)
        )
        self.audit = AuditLogger(
            log_dir=str(self.data_dir / "audits")
        )
        self.rate_limiter = RateLimiter(
            default_limit=60,
            default_window=60,
        )
        self.safe_executor = SafeExecutor()
        self.confirmations = ConfirmationManager(
            timeout=300,
            data_dir=str(self.data_dir),
        )
        self.backup = BackupManager(
            backup_dir=str(self.data_dir.parent / "backups"),
            encryption=self.encryption,
        )

        logger.info("SecurityManager initialized at %s", self.data_dir)

    # ── Authentication facade ─────────────────────────────────────

    async def register(
        self, username: str, email: str, password: str, role: Role = Role.USER
    ) -> dict[str, Any]:
        """Register a new user."""
        try:
            user = await self.auth.register(username, email, password)
            self.permissions.assign_role(user, role)
            self.audit.log_register(user.id, username)
            return {"success": True, "user_id": user.id, "username": username}
        except ValueError as e:
            self.audit.log_security_violation("", {"error": str(e), "action": "register"})
            return {"success": False, "error": str(e)}

    async def login(
        self, username: str, password: str, ip: str = ""
    ) -> dict[str, Any]:
        """Authenticate a user."""
        session = await self.auth.login(username, password, ip)
        if session:
            user = self.auth.get_user(session.token)
            self.audit.log_login(user.id, username, True, ip)
            return {
                "success": True,
                "session_id": session.id,
                "token": session.token,
                "refresh_token": session.refresh_token,
                "expires_at": session.expires_at.isoformat(),
            }
        else:
            self.audit.log_login("", username, False, ip, "Invalid credentials")
            return {"success": False, "error": "Invalid credentials"}

    async def logout(self, session_id: str, user_id: str = "", username: str = "") -> bool:
        """Log out a user."""
        result = await self.auth.logout(session_id)
        if result:
            self.audit.log_logout(user_id, username)
        return result

    def validate_token(self, token: str) -> dict | None:
        """Validate a JWT token."""
        return self.auth.validate_token(token)

    def get_current_user(self, token: str) -> User | None:
        """Get user from token."""
        return self.auth.get_user(token)

    # ── Authorization facade ──────────────────────────────────────

    def check_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has a permission."""
        allowed = self.permissions.has_permission(user, permission)
        if not allowed:
            self.audit.log_security_violation(
                user.id,
                {"permission": permission.value, "action": "access_denied"},
            )
        return allowed

    def grant_permission(self, user: User, permission: Permission) -> bool:
        """Grant a permission."""
        result = self.permissions.grant_permission(user, permission)
        if result:
            self.audit.log_permission_change(
                user.id, user.username, user.id, "grant", permission.value
            )
        return result

    def assign_role(self, user: User, role: Role) -> bool:
        """Assign a role."""
        result = self.permissions.assign_role(user, role)
        if result:
            self.audit.log_permission_change(
                user.id, user.username, user.id, "role_assign", role.value
            )
        return result

    # ── Encryption facade ─────────────────────────────────────────

    def encrypt(self, data: str | bytes) -> str:
        return self.encryption.encrypt(data)

    def decrypt(self, ciphertext: str) -> str:
        return self.encryption.decrypt(ciphertext)

    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        return self.encryption.encrypt_file(file_path, output_path)

    def decrypt_file(self, file_path: str, output_path: str = None) -> str:
        return self.encryption.decrypt_file(file_path, output_path)

    # ── Vault facade ──────────────────────────────────────────────

    def store_api_key(
        self, name: str, key_value: str, user_id: str = "", **kwargs
    ) -> dict:
        """Store an API key."""
        api_key = self.vault.store_key(name, key_value, user_id, **kwargs)
        self.audit.log_api_key(user_id, "create", name)
        return {"success": True, "key_id": api_key.id, "prefix": api_key.key_prefix}

    def get_api_key(self, name: str) -> str | None:
        return self.vault.get_key(name)

    def revoke_api_key(self, name: str, user_id: str = "") -> bool:
        result = self.vault.revoke_key(name)
        if result:
            self.audit.log_api_key(user_id, "revoke", name)
        return result

    # ── Rate limiting facade ──────────────────────────────────────

    def check_rate_limit(self, key: str) -> tuple[bool, dict]:
        allowed, info = self.rate_limiter.check(key)
        if not allowed:
            self.audit.log_rate_limit("", "", key)
        return allowed, info

    # ── Safe execution facade ─────────────────────────────────────

    async def execute_command(
        self, command: str, user_id: str = "", timeout: float = 30
    ) -> dict:
        """Execute a command with safety checks."""
        safe, reason = self.safe_executor._validate_command(command)
        if not safe:
            self.audit.log(
                AuditAction.COMMAND_EXECUTE,
                user_id=user_id,
                resource=command,
                success=False,
                error=reason,
            )
            return {"success": False, "error": f"Blocked: {reason}"}

        result = await self.safe_executor.execute(command, timeout=timeout)
        self.audit.log(
            AuditAction.COMMAND_EXECUTE,
            user_id=user_id,
            resource=command,
            success=result.get("success", False),
        )
        return result

    # ── Confirmation facade ───────────────────────────────────────

    def request_confirmation(
        self, action: str, resource: str, user_id: str, **kwargs
    ) -> dict:
        """Request confirmation for a sensitive action."""
        result = self.confirmations.request_confirmation(action, resource, user_id, **kwargs)
        self.audit.log(
            AuditAction.CONFIRMATION_REQUEST,
            user_id=user_id,
            resource=resource,
            details={"action": action, "risk_level": kwargs.get("risk_level", "medium")},
        )
        return result

    def confirm_action(
        self, confirmation_id: str, approved: bool, user_id: str, reason: str = ""
    ) -> bool:
        """Respond to a confirmation."""
        result = self.confirmations.confirm(confirmation_id, approved, user_id, reason)
        action = AuditAction.CONFIRMATION_APPROVED if approved else AuditAction.CONFIRMATION_DENIED
        self.audit.log(action, user_id=user_id, resource=confirmation_id)
        return result

    # ── Backup facade ─────────────────────────────────────────────

    async def create_backup(self, label: str = "", user_id: str = "") -> dict:
        """Create a backup."""
        manifest = await self.backup.create_backup(label)
        self.audit.log_backup_create(user_id, manifest.id)
        return {
            "success": True,
            "backup_id": manifest.id,
            "size": manifest.size_bytes,
            "files": len(manifest.files),
        }

    async def restore_backup(self, backup_id: str, user_id: str = "") -> bool:
        """Restore from backup."""
        result = await self.backup.restore_backup(backup_id)
        if result:
            self.audit.log(AuditAction.BACKUP_RESTORE, user_id=user_id, resource=backup_id)
        return result

    # ── Voice auth facade ─────────────────────────────────────────

    async def enroll_voice(self, user_id: str, audio_samples: list[bytes]) -> bool:
        result = await self.voice_auth.enroll(user_id, audio_samples)
        if result:
            self.audit.log(AuditAction.VOICE_AUTH, user_id=user_id, details={"action": "enroll"})
        return result

    async def verify_voice(self, user_id: str, audio_sample: bytes) -> tuple[bool, float]:
        match, confidence = await self.voice_auth.verify(user_id, audio_sample)
        self.audit.log(
            AuditAction.VOICE_AUTH,
            user_id=user_id,
            details={"match": match, "confidence": confidence},
        )
        return match, confidence

    # ── Audit facade ──────────────────────────────────────────────

    def get_audit_logs(self, **kwargs) -> list:
        return self.audit.query(**kwargs)

    def get_audit_summary(self, **kwargs) -> dict:
        return self.audit.get_summary(**kwargs)

    # ── System operations ─────────────────────────────────────────

    async def initialize(self) -> None:
        """Initialize all security sub-systems."""
        logger.info("Initializing security sub-systems...")
        self.auth._load_users()
        self.permissions._load_permissions()
        self.rate_limiter.cleanup()
        self.confirmations.cleanup_expired()
        self.vault.cleanup_expired()
        logger.info("Security sub-systems initialized")

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        logger.info("Shutting down security manager...")
        self.auth._save_users()
        self.permissions._save_permissions()

    def get_stats(self) -> dict:
        """Get security statistics."""
        return {
            "users": len(self.auth._users),
            "active_sessions": len([
                s for s in self.auth._sessions.values()
                if s.status.name == "ACTIVE"
            ]),
            "api_keys": len(self.vault.list_keys()),
            "audit_entries": len(self.audit.get_recent(1000)),
            "rate_limit_stats": self.rate_limiter.get_stats(),
            "pending_confirmations": len(self.confirmations.get_pending()),
            "backup_count": len(self.backup.list_backups()),
        }
