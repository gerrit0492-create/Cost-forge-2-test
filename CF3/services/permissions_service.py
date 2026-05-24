from __future__ import annotations


class PermissionsService:

    ROLE_PERMISSIONS = {
        'admin': ['read', 'write', 'approve'],
        'engineer': ['read', 'write'],
        'viewer': ['read'],
    }

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:

        permissions = cls.ROLE_PERMISSIONS.get(role, [])

        return permission in permissions
