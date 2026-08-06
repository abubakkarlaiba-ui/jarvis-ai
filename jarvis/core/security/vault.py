"""
Security module — Secure API key storage with encryption.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from jarvis.core.security.base import APIKey
from jarvis.core.security.encryption import EncryptionManager


class Vault:
    """
    Secure API key storage with encryption.
    Stores vault encrypted on disk. Each key is an APIKey from base.py.
    """

    def __init__(
        self,
        vault_file: str = "./data/security/vault.json",
        encryption: EncryptionManager = None,
    ):
        self.vault_file = Path(vault_file)
        self.encryption = encryption or EncryptionManager()
        self._keys: dict[str, APIKey] = {}
        self._encrypted_values: dict[str, str] = {}
        self._load_vault()

    def _load_vault(self) -> dict:
        """Load encrypted vault file."""
        if not self.vault_file.exists():
            self._keys = {}
            self._encrypted_values = {}
            return {}

        try:
            content = self.vault_file.read_text()
            if not content.strip():
                self._keys = {}
                self._encrypted_values = {}
                return {}

            decrypted = self.encryption.decrypt(content)
            data = json.loads(decrypted)

            self._keys = {}
            self._encrypted_values = {}
            for name, key_data in data.get("keys", {}).items():
                api_key = APIKey(
                    id=key_data.get("id", ""),
                    name=key_data.get("name", name),
                    key_hash=key_data.get("key_hash", ""),
                    key_prefix=key_data.get("key_prefix", ""),
                    user_id=key_data.get("user_id", ""),
                    permissions=key_data.get("permissions", []),
                    created_at=datetime.fromisoformat(key_data["created_at"]) if key_data.get("created_at") else datetime.now(),
                    expires_at=datetime.fromisoformat(key_data["expires_at"]) if key_data.get("expires_at") else None,
                    last_used=datetime.fromisoformat(key_data["last_used"]) if key_data.get("last_used") else None,
                    is_active=key_data.get("is_active", True),
                    rate_limit=key_data.get("rate_limit", 100),
                )
                self._keys[name] = api_key
                self._encrypted_values[name] = key_data.get("encrypted_value", "")

            return data
        except Exception:
            self._keys = {}
            self._encrypted_values = {}
            return {}

    def _save_vault(self) -> None:
        """Save vault with encryption."""
        data = {"keys": {}}
        for name, api_key in self._keys.items():
            key_data = {
                "id": api_key.id,
                "name": api_key.name,
                "key_hash": api_key.key_hash,
                "key_prefix": api_key.key_prefix,
                "user_id": api_key.user_id,
                "permissions": api_key.permissions,
                "created_at": api_key.created_at.isoformat(),
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
                "is_active": api_key.is_active,
                "rate_limit": api_key.rate_limit,
                "encrypted_value": self._encrypted_values.get(name, ""),
            }
            data["keys"][name] = key_data

        encrypted = self.encryption.encrypt_dict(data)
        self.vault_file.parent.mkdir(parents=True, exist_ok=True)
        self.vault_file.write_text(encrypted)

    def store_key(
        self,
        name: str,
        key_value: str,
        user_id: str = "",
        permissions: list[str] = None,
        expires_days: int = None,
    ) -> APIKey:
        """Store API key encrypted."""
        if name in self._keys:
            raise ValueError(f"Key '{name}' already exists. Use rotate_key to update.")

        encrypted_value = self.encryption.encrypt(key_value)
        key_hash = self.encryption.hash_data(key_value)
        key_prefix = key_value[:8] if len(key_value) >= 8 else key_value

        expires_at = None
        if expires_days:
            expires_at = datetime.now() + timedelta(days=expires_days)

        api_key = APIKey(
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            user_id=user_id,
            permissions=permissions or [],
            expires_at=expires_at,
        )

        self._keys[name] = api_key
        self._encrypted_values[name] = encrypted_value
        self._save_vault()
        return api_key

    def get_key(self, name: str) -> Optional[str]:
        """Retrieve decrypted API key value."""
        api_key = self._keys.get(name)
        if not api_key:
            return None

        if not api_key.is_active:
            return None

        if api_key.expires_at and datetime.now() > api_key.expires_at:
            api_key.is_active = False
            self._save_vault()
            return None

        encrypted_value = self._encrypted_values.get(name)
        if not encrypted_value:
            return None

        api_key.last_used = datetime.now()
        self._save_vault()

        return self.encryption.decrypt(encrypted_value)

    def get_key_info(self, name: str) -> Optional[APIKey]:
        """Get key metadata without revealing value."""
        return self._keys.get(name)

    def revoke_key(self, name: str) -> bool:
        """Mark key as inactive."""
        api_key = self._keys.get(name)
        if not api_key:
            return False

        api_key.is_active = False
        self._save_vault()
        return True

    def delete_key(self, name: str) -> bool:
        """Remove key permanently."""
        if name not in self._keys:
            return False

        del self._keys[name]
        self._encrypted_values.pop(name, None)
        self._save_vault()
        return True

    def list_keys(self, user_id: str = None) -> list[dict]:
        """List key metadata (no values)."""
        result = []
        for name, api_key in self._keys.items():
            if user_id and api_key.user_id != user_id:
                continue
            result.append({
                "name": api_key.name,
                "id": api_key.id,
                "user_id": api_key.user_id,
                "key_prefix": api_key.key_prefix,
                "permissions": api_key.permissions,
                "created_at": api_key.created_at.isoformat(),
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "last_used": api_key.last_used.isoformat() if api_key.last_used else None,
                "is_active": api_key.is_active,
                "rate_limit": api_key.rate_limit,
            })
        return result

    def rotate_key(self, name: str, new_value: str) -> APIKey:
        """Replace key value."""
        api_key = self._keys.get(name)
        if not api_key:
            raise KeyError(f"Key '{name}' not found.")

        encrypted_value = self.encryption.encrypt(new_value)
        key_hash = self.encryption.hash_data(new_value)
        key_prefix = new_value[:8] if len(new_value) >= 8 else new_value

        api_key.key_hash = key_hash
        api_key.key_prefix = key_prefix
        api_key.is_active = True
        api_key.last_used = None

        self._encrypted_values[name] = encrypted_value
        self._save_vault()
        return api_key

    def validate_key(self, name: str, key_value: str) -> bool:
        """Validate a key matches stored value."""
        api_key = self._keys.get(name)
        if not api_key:
            return False

        stored_hash = api_key.key_hash
        provided_hash = self.encryption.hash_data(key_value)
        return stored_hash == provided_hash

    def cleanup_expired(self) -> int:
        """Remove expired keys, return count."""
        expired_names = []
        for name, api_key in self._keys.items():
            if api_key.expires_at and datetime.now() > api_key.expires_at:
                expired_names.append(name)

        for name in expired_names:
            del self._keys[name]
            self._encrypted_values.pop(name, None)

        if expired_names:
            self._save_vault()

        return len(expired_names)

    def export_keys(self, user_id: str, include_values: bool = False) -> dict:
        """Export keys (encrypted unless include_values)."""
        export_data = {"keys": {}}
        for name, api_key in self._keys.items():
            if user_id and api_key.user_id != user_id:
                continue

            key_data = {
                "name": api_key.name,
                "id": api_key.id,
                "user_id": api_key.user_id,
                "key_prefix": api_key.key_prefix,
                "permissions": api_key.permissions,
                "created_at": api_key.created_at.isoformat(),
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
                "is_active": api_key.is_active,
                "rate_limit": api_key.rate_limit,
            }

            if include_values:
                encrypted_value = self._encrypted_values.get(name)
                if encrypted_value:
                    key_data["key_value"] = self.encryption.decrypt(encrypted_value)
            else:
                key_data["encrypted_value"] = self._encrypted_values.get(name, "")

            export_data["keys"][name] = key_data

        return export_data

    def import_keys(self, data: dict) -> int:
        """Import keys from export."""
        count = 0
        for name, key_data in data.get("keys", {}).items():
            if name in self._keys:
                continue

            key_value = key_data.get("key_value")
            if not key_value:
                continue

            self.store_key(
                name=name,
                key_value=key_value,
                user_id=key_data.get("user_id", ""),
                permissions=key_data.get("permissions", []),
            )
            count += 1

        return count