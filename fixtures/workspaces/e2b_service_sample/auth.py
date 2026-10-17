"""Authentication and token validation service."""

def validate_token(token: str) -> bool:
    if not token or len(token) < 8:
        return False
    return token.startswith("tok_live_")

def get_role_permissions(role: str) -> list[str]:
    roles = {
        "admin": ["read", "write", "delete", "admin"],
        "developer": ["read", "write"],
        "viewer": ["read"]
    }
    return roles.get(role, [])

def check_permission(role: str, permission: str) -> bool:
    return permission in get_role_permissions(role)

