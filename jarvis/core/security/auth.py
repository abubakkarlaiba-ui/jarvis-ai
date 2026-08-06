"""
Security module — JWT authentication and session management.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.core.security.base import Session, SessionStatus, User

_USERS_PATH = Path("./data/security/users.json")
_SESSIONS_PATH = Path("./data/security/sessions.json")

_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 30


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class AuthManager:
    def __init__(self, secret_key: str = "", token_expiry_hours: int = 24) -> None:
        self.secret_key = secret_key or secrets.token_hex(32)
        self.token_expiry_hours = token_expiry_hours
        self._users: dict[str, User] = {}
        self._sessions: dict[str, Session] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────
    def _load(self) -> None:
        for path, store, ctor in [
            (_USERS_PATH, self._users, User),
            (_SESSIONS_PATH, self._sessions, Session),
        ]:
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    for raw in data:
                        obj = ctor()
                        for k, v in raw.items():
                            if k in ("created_at", "expires_at", "last_login", "locked_until"):
                                v = datetime.fromisoformat(v) if v else None
                            if hasattr(obj, k):
                                setattr(obj, k, v)
                        key = obj.id
                        store[key] = obj
                except Exception:
                    pass

    def _save(self) -> None:
        _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)

        def _ser(obj: Any) -> dict[str, Any]:
            d = {}
            for k, v in obj.__dict__.items():
                if isinstance(v, datetime):
                    v = v.isoformat()
                d[k] = v
            return d

        _USERS_PATH.write_text(
            json.dumps([_ser(u) for u in self._users.values()], indent=2, default=str),
            encoding="utf-8",
        )
        _SESSIONS_PATH.write_text(
            json.dumps([_ser(s) for s in self._sessions.values()], indent=2, default=str),
            encoding="utf-8",
        )

    # ── password hashing ─────────────────────────────────────────
    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
        if salt is None:
            salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
        return dk.hex(), salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
        return hmac.compare_digest(dk.hex(), password_hash)

    # ── JWT helpers ──────────────────────────────────────────────
    def _sign(self, payload: dict[str, Any]) -> str:
        header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        body = _b64url(json.dumps(payload).encode())
        sig = hmac.new(self.secret_key.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
        return f"{header}.{body}.{_b64url(sig)}"

    def generate_token(self, user: User) -> str:
        now = time.time()
        payload = {
            "user_id": user.id,
            "roles": user.roles,
            "iat": int(now),
            "exp": int(now + self.token_expiry_hours * 3600),
        }
        return self._sign(payload)

    def validate_token(self, token: str) -> dict[str, Any] | None:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            header_b64, body_b64, sig_b64 = parts
            expected_sig = hmac.new(
                self.secret_key.encode(), f"{header_b64}.{body_b64}".encode(), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(_b64url_decode(sig_b64), expected_sig):
                return None
            payload = json.loads(_b64url_decode(body_b64))
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception:
            return None

    # ── sessions ─────────────────────────────────────────────────
    def create_session(self, user: User, ip: str = "", user_agent: str = "") -> Session:
        now = datetime.now()
        token = self.generate_token(user)
        refresh = secrets.token_hex(32)
        session = Session(
            user_id=user.id,
            token=token,
            refresh_token=refresh,
            status=SessionStatus.ACTIVE,
            created_at=now,
            expires_at=now + timedelta(hours=self.token_expiry_hours),
            ip_address=ip,
            user_agent=user_agent,
        )
        self._sessions[session.id] = session
        self._save()
        return session

    def get_session(self, session_id: str) -> Session | None:
        s = self._sessions.get(session_id)
        if s and s.status == SessionStatus.ACTIVE and s.expires_at > datetime.now():
            return s
        return None

    def revoke_session(self, session_id: str) -> bool:
        s = self._sessions.get(session_id)
        if s:
            s.status = SessionStatus.REVOKED
            self._save()
            return True
        return False

    def cleanup_sessions(self) -> int:
        now = datetime.now()
        removed = 0
        for sid in list(self._sessions):
            s = self._sessions[sid]
            if s.status != SessionStatus.ACTIVE or s.expires_at <= now:
                del self._sessions[sid]
                removed += 1
        if removed:
            self._save()
        return removed

    # ── user management ──────────────────────────────────────────
    def _user_by_username(self, username: str) -> User | None:
        for u in self._users.values():
            if u.username == username:
                return u
        return None

    def _user_by_email(self, email: str) -> User | None:
        for u in self._users.values():
            if u.email == email:
                return u
        return None

    async def register(self, username: str, email: str, password: str) -> User:
        if self._user_by_username(username):
            raise ValueError("Username already taken")
        if self._user_by_email(email):
            raise ValueError("Email already registered")
        pw_hash, salt = self.hash_password(password)
        user = User(
            username=username,
            email=email,
            password_hash=pw_hash,
            salt=salt,
        )
        self._users[user.id] = user
        self._save()
        return user

    async def login(self, username: str, password: str, ip: str = "") -> Session | None:
        user = self._user_by_username(username)
        if not user or not user.is_active:
            return None
        if self.is_locked(user):
            return None
        if not self.verify_password(password, user.password_hash, user.salt):
            self.record_failed_login(user)
            return None
        self.reset_failed_attempts(user)
        user.last_login = datetime.now()
        self._save()
        return self.create_session(user, ip=ip)

    async def logout(self, session_id: str) -> bool:
        return self.revoke_session(session_id)

    def get_user(self, token: str) -> User | None:
        payload = self.validate_token(token)
        if not payload:
            return None
        return self._users.get(payload.get("user_id", ""))

    # ── lockout helpers ──────────────────────────────────────────
    def is_locked(self, user: User) -> bool:
        if user.locked_until and user.locked_until > datetime.now():
            return True
        return False

    def record_failed_login(self, user: User) -> None:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= _MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.now() + timedelta(minutes=_LOCKOUT_MINUTES)
        self._save()

    def reset_failed_attempts(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        self._save()
