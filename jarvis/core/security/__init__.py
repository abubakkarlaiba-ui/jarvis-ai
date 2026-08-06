"""
JARVIS Security module.
======================
Enterprise-grade security for the JARVIS AI assistant.

Quick Start:
    from jarvis.core.security import SecurityManager, Permission, Role

    security = SecurityManager()
    await security.initialize()
    result = await security.login("admin", "password")
"""

from jarvis.core.security.audit import AuditLogger
from jarvis.core.security.auth import AuthManager
from jarvis.core.security.backup import BackupManager
from jarvis.core.security.base import (
    APIKey,
    AuditAction,
    AuditEntry,
    Permission,
    Role,
    ROLE_PERMISSIONS,
    Session,
    SessionStatus,
    User,
)
from jarvis.core.security.confirmations import ConfirmationManager
from jarvis.core.security.encryption import EncryptionManager
from jarvis.core.security.permissions import PermissionManager
from jarvis.core.security.rate_limiter import RateLimiter
from jarvis.core.security.safe_executor import SafeExecutor
from jarvis.core.security.security_manager import SecurityManager
from jarvis.core.security.vault import Vault
from jarvis.core.security.voice_auth import VoiceAuth

__all__ = [
    "AuditLogger",
    "AuthManager",
    "BackupManager",
    "APIKey",
    "AuditAction",
    "AuditEntry",
    "ConfirmationManager",
    "EncryptionManager",
    "Permission",
    "PermissionManager",
    "RateLimiter",
    "Role",
    "ROLE_PERMISSIONS",
    "SafeExecutor",
    "SecurityManager",
    "Session",
    "SessionStatus",
    "User",
    "Vault",
    "VoiceAuth",
]
