"""
Tests for security and RBAC utilities.
"""

from datetime import timedelta
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    has_role,
    ROLE_HIERARCHY,
)


def test_password_hashing():
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_jwt_access_token_lifecycle():
    data = {"sub": "user-uuid-123", "role": "research_admin"}
    token = create_access_token(data, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-uuid-123"
    assert payload["role"] == "research_admin"
    assert payload["type"] == "access"


def test_jwt_refresh_token_lifecycle():
    data = {"sub": "user-uuid-456", "role": "faculty"}
    token = create_refresh_token(data)
    assert isinstance(token, str)

    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-uuid-456"
    assert payload["type"] == "refresh"


def test_decode_invalid_token():
    assert decode_token("invalid.token.structure") is None


def test_role_hierarchy():
    assert has_role("super_admin", "faculty") is True
    assert has_role("super_admin", "research_admin") is True
    assert has_role("research_admin", "faculty") is True
    assert has_role("dept_admin", "faculty") is True
    assert has_role("faculty", "faculty") is True
    assert has_role("faculty", "research_admin") is False
    assert has_role("faculty", "super_admin") is False
    assert has_role("dept_admin", "super_admin") is False
