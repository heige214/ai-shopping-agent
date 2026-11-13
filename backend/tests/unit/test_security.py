import pytest

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


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
    assert expires_in == settings.jwt_expire_minutes * 60
    assert decode_access_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-token")


def make_token(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "42",
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    payload.update(overrides)
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def test_expired_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(
            make_token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))
        )


def test_wrong_secret_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "42",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        "x" * 32,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_non_access_token_type_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(make_token(type="refresh"))


def test_alg_none_rejected():
    now = datetime.now(timezone.utc)
    unsigned = jwt.encode(
        {
            "sub": "42",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        None,
        algorithm="none",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned)


def test_missing_required_claim_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "42", "type": "access", "iat": now},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_non_numeric_subject_rejected():
    with pytest.raises(InvalidTokenError):
        decode_access_token(make_token(sub="abc"))


def test_verify_password_malformed_hash_returns_false():
    assert verify_password("secret123", "not-a-bcrypt-hash") is False


def test_verify_password_over_72_bytes_returns_false():
    password_hash = hash_password("a" * 72)
    assert verify_password("a" * 72 + "b", password_hash) is False


def test_hash_password_accepts_exactly_72_bytes():
    assert verify_password("a" * 72, hash_password("a" * 72))


def test_password_hash_is_salted():
    assert hash_password("secret123") != hash_password("secret123")
