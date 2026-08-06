"""
Security routes — authentication, authorization, and security management.
========================================================================
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


# ── Request / Response models ─────────────────────────────────────


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    role: str = Field(default="user", description="Role: admin, user, viewer, operator")


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    success: bool
    session_id: str = ""
    token: str = ""
    refresh_token: str = ""
    expires_at: str = ""
    error: str = ""


class UserResponse(BaseModel):
    success: bool
    user_id: str = ""
    username: str = ""
    error: str = ""


class PermissionRequest(BaseModel):
    user_id: str
    permission: str


class RoleRequest(BaseModel):
    user_id: str
    role: str


class APIKeyRequest(BaseModel):
    name: str
    key_value: str
    permissions: list[str] = Field(default_factory=list)
    expires_days: int | None = None


class ConfirmRequest(BaseModel):
    action: str
    resource: str
    risk_level: str = "medium"
    details: dict = Field(default_factory=dict)


class ConfirmResponseRequest(BaseModel):
    confirmation_id: str
    approved: bool
    reason: str = ""


class CommandRequest(BaseModel):
    command: str
    timeout: float = 30


class AuditQueryRequest(BaseModel):
    user_id: str | None = None
    action: str | None = None
    limit: int = 100


class BackupRequest(BaseModel):
    label: str = ""
    include: list[str] | None = None


class RestoreRequest(BaseModel):
    backup_id: str


class RateLimitSetRequest(BaseModel):
    key: str
    limit: int
    window: int = 60


# ── Dependency ────────────────────────────────────────────────────


def _get_security():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    if not hasattr(core, "security"):
        raise HTTPException(status_code=503, detail="Security manager not initialized")
    return core.security


async def _get_current_user(authorization: str = Header(None)):
    security = _get_security()
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.replace("Bearer ", "")
    payload = security.validate_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = security.get_current_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Auth endpoints ────────────────────────────────────────────────


@router.post("/auth/register", response_model=UserResponse)
async def register(request: RegisterRequest) -> UserResponse:
    """Register a new user."""
    security = _get_security()
    role_map = {"admin": "ADMIN", "user": "USER", "viewer": "VIEWER", "operator": "OPERATOR"}
    from jarvis.core.security.base import Role
    role = Role[role_map.get(request.role, "USER").upper()]
    result = await security.register(request.username, request.email, request.password, role)
    return UserResponse(**result)


@router.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate and get token."""
    security = _get_security()
    result = await security.login(request.username, request.password)
    return TokenResponse(**result)


@router.post("/auth/logout")
async def logout(authorization: str = Header(None)):
    """Log out and revoke session."""
    security = _get_security()
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    token = authorization.replace("Bearer ", "")
    payload = security.validate_token(token)
    if payload:
        session_id = payload.get("session_id", "")
        user_id = payload.get("user_id", "")
        username = payload.get("username", "")
        await security.logout(session_id, user_id, username)
    return {"success": True}


@router.get("/auth/me")
async def get_me(user: dict = Depends(_get_current_user)):
    """Get current user info."""
    return {
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": user.roles,
        "is_active": user.is_active,
    }


# ── Permission endpoints ─────────────────────────────────────────


@router.get("/permissions/{user_id}")
async def get_user_permissions(user_id: str):
    """Get user's effective permissions."""
    security = _get_security()
    from jarvis.core.security.base import Permission
    user = security.auth._users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    perms = security.permissions.get_user_permissions(user)
    return {"user_id": user_id, "permissions": [p.value for p in perms]}


@router.post("/permissions/grant")
async def grant_permission(request: PermissionRequest, user: dict = Depends(_get_current_user)):
    """Grant a permission to a user."""
    security = _get_security()
    from jarvis.core.security.base import Permission, User as UserType
    target_user = security.auth._users.get(request.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        perm = Permission(request.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {request.permission}")
    result = security.grant_permission(target_user, perm)
    return {"success": result}


@router.post("/permissions/revoke")
async def revoke_permission(request: PermissionRequest, user: dict = Depends(_get_current_user)):
    """Revoke a permission from a user."""
    security = _get_security()
    from jarvis.core.security.base import Permission
    target_user = security.auth._users.get(request.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        perm = Permission(request.permission)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {request.permission}")
    result = security.permissions.revoke_permission(target_user, perm)
    return {"success": result}


@router.post("/roles/assign")
async def assign_role(request: RoleRequest, user: dict = Depends(_get_current_user)):
    """Assign a role to a user."""
    security = _get_security()
    from jarvis.core.security.base import Role
    target_user = security.auth._users.get(request.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    result = security.assign_role(target_user, role)
    return {"success": result}


@router.get("/roles")
async def list_roles():
    """List all roles and their permissions."""
    from jarvis.core.security.base import ROLE_PERMISSIONS, Role
    return {
        role.value: [p.value for p in perms]
        for role, perms in ROLE_PERMISSIONS.items()
    }


# ── API Key endpoints ────────────────────────────────────────────


@router.post("/api-keys")
async def create_api_key(request: APIKeyRequest, user: dict = Depends(_get_current_user)):
    """Store an API key."""
    security = _get_security()
    result = security.store_api_key(
        request.name, request.key_value, user.id,
        permissions=request.permissions,
        expires_days=request.expires_days,
    )
    return result


@router.get("/api-keys")
async def list_api_keys(user: dict = Depends(_get_current_user)):
    """List API keys."""
    security = _get_security()
    return security.vault.list_keys(user.id)


@router.post("/api-keys/{name}/revoke")
async def revoke_api_key(name: str, user: dict = Depends(_get_current_user)):
    """Revoke an API key."""
    security = _get_security()
    result = security.revoke_api_key(name, user.id)
    return {"success": result}


# ── Rate limiting ────────────────────────────────────────────────


@router.get("/rate-limit/{key}")
async def check_rate_limit(key: str):
    """Check rate limit for a key."""
    security = _get_security()
    allowed, info = security.check_rate_limit(key)
    return {"allowed": allowed, **info}


@router.post("/rate-limit")
async def set_rate_limit(request: RateLimitSetRequest):
    """Set custom rate limit."""
    security = _get_security()
    security.rate_limiter.set_limit(request.key, request.limit, request.window)
    return {"success": True}


# ── Command execution ────────────────────────────────────────────


@router.post("/execute")
async def execute_command(request: CommandRequest, user: dict = Depends(_get_current_user)):
    """Execute a command with safety checks."""
    security = _get_security()
    result = await security.execute_command(request.command, user.id, request.timeout)
    return result


# ── Confirmations ────────────────────────────────────────────────


@router.post("/confirmations/request")
async def request_confirmation(request: ConfirmRequest, user: dict = Depends(_get_current_user)):
    """Request confirmation for a sensitive action."""
    security = _get_security()
    result = security.request_confirmation(
        request.action, request.resource, user.id,
        risk_level=request.risk_level,
        details=request.details,
    )
    return result


@router.post("/confirmations/respond")
async def respond_confirmation(request: ConfirmResponseRequest, user: dict = Depends(_get_current_user)):
    """Respond to a confirmation prompt."""
    security = _get_security()
    result = security.confirm_action(
        request.confirmation_id, request.approved, user.id, request.reason
    )
    return {"success": result}


@router.get("/confirmations/pending")
async def get_pending_confirmations(user: dict = Depends(_get_current_user)):
    """Get pending confirmations."""
    security = _get_security()
    return security.confirmations.get_pending(user.id)


# ── Backup ───────────────────────────────────────────────────────


@router.post("/backups")
async def create_backup(request: BackupRequest, user: dict = Depends(_get_current_user)):
    """Create a backup."""
    security = _get_security()
    result = await security.create_backup(request.label, user.id)
    return result


@router.post("/backups/{backup_id}/restore")
async def restore_backup(backup_id: str, user: dict = Depends(_get_current_user)):
    """Restore from backup."""
    security = _get_security()
    result = await security.restore_backup(backup_id, user.id)
    return {"success": result}


@router.get("/backups")
async def list_backups():
    """List all backups."""
    security = _get_security()
    return security.backup.list_backups()


@router.delete("/backups/{backup_id}")
async def delete_backup(backup_id: str, user: dict = Depends(_get_current_user)):
    """Delete a backup."""
    security = _get_security()
    result = security.backup.delete_backup(backup_id)
    return {"success": result}


# ── Voice auth ───────────────────────────────────────────────────


@router.post("/voice/enroll")
async def enroll_voice(user: dict = Depends(_get_current_user)):
    """Enroll voice print (requires audio in request body)."""
    # In production, this would accept audio data
    return {"message": "Voice enrollment requires audio data via multipart upload"}


@router.post("/voice/verify")
async def verify_voice(user: dict = Depends(_get_current_user)):
    """Verify voice print."""
    return {"message": "Voice verification requires audio data via multipart upload"}


# ── Audit logs ───────────────────────────────────────────────────


@router.get("/audit/logs")
async def get_audit_logs(user_id: str = None, action: str = None, limit: int = 100):
    """Query audit logs."""
    security = _get_security()
    from jarvis.core.security.base import AuditAction
    action_enum = AuditAction(action) if action else None
    logs = security.get_audit_logs(user_id=user_id, action=action_enum, limit=limit)
    return [
        {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "user_id": entry.user_id,
            "username": entry.username,
            "action": entry.action.value,
            "resource": entry.resource,
            "success": entry.success,
            "error": entry.error,
        }
        for entry in logs
    ]


@router.get("/audit/summary")
async def get_audit_summary():
    """Get audit log summary."""
    security = _get_security()
    return security.get_audit_summary()


# ── System ───────────────────────────────────────────────────────


@router.get("/stats")
async def get_security_stats():
    """Get security statistics."""
    security = _get_security()
    return security.get_stats()


@router.post("/encrypt")
async def encrypt_data(data: str, user: dict = Depends(_get_current_user)):
    """Encrypt data."""
    security = _get_security()
    return {"encrypted": security.encrypt(data)}


@router.post("/decrypt")
async def decrypt_data(ciphertext: str, user: dict = Depends(_get_current_user)):
    """Decrypt data."""
    security = _get_security()
    return {"decrypted": security.decrypt(ciphertext)}
