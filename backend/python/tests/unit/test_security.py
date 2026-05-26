import pytest

from core.security import hash_password, verify_password

pytestmark = pytest.mark.unit


def test_password_hashing():
    """Verify that password hashing works and is not plaintext."""
    password = "secret_password_123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_hashing_is_probabilistic():
    """Verify that hashing the same password twice results in different hashes (salt)."""
    password = "secret_password_123"
    hashed1 = hash_password(password)
    hashed2 = hash_password(password)

    assert hashed1 != hashed2
    assert verify_password(password, hashed1) is True
    assert verify_password(password, hashed2) is True
