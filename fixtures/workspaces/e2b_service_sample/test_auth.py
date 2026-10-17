"""Unit tests for auth service to be executed in E2B micro-VM."""
import pytest
from auth import validate_token, check_permission, get_role_permissions

def test_token_validation_live():
    assert validate_token("tok_live_9988776655") is True

def test_token_validation_invalid():
    assert validate_token("invalid_token") is False
    assert validate_token("") is False

def test_permissions_admin():
    assert check_permission("admin", "delete") is True
    assert check_permission("admin", "admin") is True

def test_permissions_viewer():
    assert check_permission("viewer", "read") is True
    assert check_permission("viewer", "delete") is False

def test_verify_api_key():
    import auth
    if hasattr(auth, "verify_api_key"):
        assert auth.verify_api_key("ak_live_secure_999") is True
        assert auth.verify_api_key("invalid_key") is False
        assert auth.verify_api_key("") is False

