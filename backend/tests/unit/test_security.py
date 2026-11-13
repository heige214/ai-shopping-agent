import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_round_trip():
    password_hash = hash_password("secret123")
    assert password_hash != "secret123"
    assert verify_password("secret123", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_password_hash_rejects_over_72_bytes():
    with pytest.raises(ValueError):
        hash_password("密" * 30)


def test_access_token_round_trip():
    token, expires_in = create_access_token(42)
    assert expires_in > 0
    assert decode_access_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-token")
