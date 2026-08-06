from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jarvis.core.security.base import Permission, Role, ROLE_PERMISSIONS, User


class PermissionManager:
    """Role-based access control (RBAC) permission system."""

    def __init__(self, data_dir: str = "./data/security") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._permissions_file = self._data_dir / "custom_permissions.json"
        self._custom_roles: dict[str, list[str]] = {}
        self._load_permissions()

    def has_permission(self, user: User, permission: Permission) -> bool:
        return permission in self.get_effective_permissions(user)

    def has_any_permission(self, user: User, permissions: list[Permission]) -> bool:
        effective = self.get_effective_permissions(user)
        return any(p in effective for p in permissions)

    def has_all_permissions(self, user: User, permissions: list[Permission]) -> bool:
        effective = self.get_effective_permissions(user)
        return all(p in effective for p in permissions)

    def grant_permission(self, user: User, permission: Permission) -> bool:
        if permission.value not in user.permissions:
            user.permissions.append(permission.value)
            return True
        return False

    def revoke_permission(self, user: User, permission: Permission) -> bool:
        if permission.value in user.permissions:
            user.permissions.remove(permission.value)
            return True
        return False

    def assign_role(self, user: User, role: Role) -> bool:
        if role.value not in user.roles:
            user.roles.append(role.value)
            return True
        return False

    def remove_role(self, user: User, role: Role) -> bool:
        if role.value in user.roles:
            user.roles.remove(role.value)
            return True
        return False

    def get_user_permissions(self, user: User) -> list[Permission]:
        return sorted(self.get_effective_permissions(user), key=lambda p: p.value)

    def get_user_roles(self, user: User) -> list[Role]:
        roles: list[Role] = []
        for role_str in user.roles:
            try:
                roles.append(Role(role_str))
            except ValueError:
                pass
        return roles

    def create_custom_role(self, name: str, permissions: list[Permission]) -> Role:
        self._custom_roles[name] = [p.value for p in permissions]
        self._save_permissions()
        return Role(name)

    def list_roles(self) -> dict[str, list[str]]:
        all_roles: dict[str, list[str]] = {}
        for role, perms in ROLE_PERMISSIONS.items():
            all_roles[role.value] = [p.value for p in perms]
        for role_name, perms in self._custom_roles.items():
            all_roles[role_name] = perms
        return all_roles

    def check_access(self, user: User, resource: str, action: str) -> bool:
        action_key = f"{resource}.{action}".upper()
        try:
            perm = Permission(action_key)
            return self.has_permission(user, perm)
        except ValueError:
            return user.has_permission(Permission.SYSTEM_ADMIN)

    def _save_permissions(self) -> None:
        self._permissions_file.write_text(
            json.dumps(self._custom_roles, indent=2), encoding="utf-8"
        )

    def _load_permissions(self) -> None:
        if self._permissions_file.exists():
            try:
                data = json.loads(self._permissions_file.read_text(encoding="utf-8"))
                self._custom_roles = {k: list(v) for k, v in data.items()}
            except (json.JSONDecodeError, TypeError):
                self._custom_roles = {}

    def get_effective_permissions(self, user: User) -> set[Permission]:
        effective: set[Permission] = set()

        for role_str in user.roles:
            try:
                role = Role(role_str)
                effective.update(ROLE_PERMISSIONS.get(role, []))
            except ValueError:
                perms = self._custom_roles.get(role_str, [])
                for p_str in perms:
                    try:
                        effective.add(Permission(p_str))
                    except ValueError:
                        pass

        for p_str in user.permissions:
            try:
                effective.add(Permission(p_str))
            except ValueError:
                pass

        return effective
