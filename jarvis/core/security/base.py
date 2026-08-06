"""
Security module — base types and configuration.
================================================
Shared dataclasses, enums, and settings for all security submodules.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any


class Permission(Enum):
    """Granular permissions for the RBAC system."""
    # System
    SYSTEM_ADMIN = "system.admin"
    SYSTEM_CONFIG = "system.config"
    SYSTEM_SHUTDOWN = "system.shutdown"

    # Skills
    SKILL_READ = "skill.read"
    SKILL_EXECUTE = "skill.execute"
    SKILL_INSTALL = "skill.install"
    SKILL_REMOVE = "skill.remove"

    # Workflow
    WORKFLOW_READ = "workflow.read"
    WORKFLOW_CREATE = "workflow.create"
    WORKFLOW_EXECUTE = "workflow.execute"
    WORKFLOW_DELETE = "workflow.delete"

    # Memory
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    MEMORY_DELETE = "memory.delete"

    # Coding
    CODE_READ = "code.read"
    CODE_WRITE = "code.write"
    CODE_EXECUTE = "code.execute"
    CODE_DEPLOY = "code.deploy"

    # Files
    FILE_READ = "file.read"
    FILE_WRITE = "file.write"
    FILE_DELETE = "file.delete"
    FILE_ADMIN = "file.admin"

    # Voice
    VOICE_USE = "voice.use"
    VOICE_ADMIN = "voice.admin"

    # Chat
    CHAT_USE = "chat.use"
    CHAT_HISTORY = "chat.history"

    # Security
    SECURITY_READ = "security.read"
    SECURITY_ADMIN = "security.admin"
    AUDIT_READ = "audit.read"

    # API
    API_READ = "api.read"
    API_WRITE = "api.write"
    API_ADMIN = "api.admin"


class Role(Enum):
    """Built-in roles with preset permissions."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"
    OPERATOR = "operator"


ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.ADMIN: list(Permission),  # All permissions
    Role.OPERATOR: [
        Permission.SKILL_READ, Permission.SKILL_EXECUTE,
        Permission.WORKFLOW_READ, Permission.WORKFLOW_CREATE, Permission.WORKFLOW_EXECUTE,
        Permission.MEMORY_READ, Permission.MEMORY_WRITE,
        Permission.CODE_READ, Permission.CODE_WRITE, Permission.CODE_EXECUTE,
        Permission.FILE_READ, Permission.FILE_WRITE,
        Permission.VOICE_USE,
        Permission.CHAT_USE, Permission.CHAT_HISTORY,
        Permission.API_READ,
    ],
    Role.USER: [
        Permission.SKILL_READ, Permission.SKILL_EXECUTE,
        Permission.WORKFLOW_READ, Permission.WORKFLOW_CREATE,
        Permission.MEMORY_READ, Permission.MEMORY_WRITE,
        Permission.CODE_READ, Permission.CODE_WRITE,
        Permission.FILE_READ,
        Permission.VOICE_USE,
        Permission.CHAT_USE, Permission.CHAT_HISTORY,
    ],
    Role.VIEWER: [
        Permission.SKILL_READ,
        Permission.WORKFLOW_READ,
        Permission.MEMORY_READ,
        Permission.CODE_READ,
        Permission.FILE_READ,
        Permission.CHAT_HISTORY,
    ],
}


class SessionStatus(Enum):
    ACTIVE = auto()
    EXPIRED = auto()
    REVOKED = auto()


class AuditAction(Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    PERMISSION_GRANT = "permission_grant"
    PERMISSION_REVOKE = "permission_revoke"
    ROLE_ASSIGN = "role_assign"
    SKILL_EXECUTE = "skill_execute"
    SKILL_INSTALL = "skill_install"
    WORKFLOW_EXECUTE = "workflow_execute"
    CODE_EXECUTE = "code_execute"
    FILE_ACCESS = "file_access"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    SETTINGS_CHANGE = "settings_change"
    BACKUP_CREATE = "backup_create"
    BACKUP_RESTORE = "backup_restore"
    SYSTEM_ERROR = "system_error"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_HIT = "rate_limit_hit"
    CONFIRMATION_REQUEST = "confirmation_request"
    CONFIRMATION_APPROVED = "confirmation_approved"
    CONFIRMATION_DENIED = "confirmation_denied"
    VOICE_AUTH = "voice_auth"
    COMMAND_EXECUTE = "command_execute"


@dataclass
class User:
    """A registered user of the system."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    username: str = ""
    email: str = ""
    password_hash: str = ""
    salt: str = ""
    roles: list[str] = field(default_factory=lambda: ["user"])
    permissions: list[str] = field(default_factory=list)
    voice_print: str = ""
    is_active: bool = True
    is_verified: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_login: datetime | None = None
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """An active user session."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_id: str = ""
    token: str = ""
    refresh_token: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=lambda: datetime.now() + timedelta(hours=24))
    ip_address: str = ""
    user_agent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """A single audit log entry."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: str = ""
    username: str = ""
    action: AuditAction = AuditAction.LOGIN
    resource: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    success: bool = True
    error: str = ""


@dataclass
class APIKey:
    """A stored API key."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    key_hash: str = ""
    key_prefix: str = ""  # First 8 chars for identification
    user_id: str = ""
    permissions: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    last_used: datetime | None = None
    is_active: bool = True
    rate_limit: int = 100  # requests per minute


@dataclass
class BackupManifest:
    """Metadata for a backup."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=datetime.now)
    files: list[str] = field(default_factory=list)
    size_bytes: int = 0
    checksum: str = ""
    encrypted: bool = True
    label: str = ""
