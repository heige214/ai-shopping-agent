from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# bcrypt 只处理前 72 字节，超出部分会被静默截断，因此显式拒绝
BCRYPT_MAX_BYTES = 72


class InvalidTokenError(Exception):
    """访问令牌无效或已过期。"""


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希，自动加盐。"""
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError("密码不能超过 72 字节")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """校验明文密码；超长输入、损坏的哈希视为不匹配。"""
    try:
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int) -> tuple[str, int]:
    """签发 access token，返回令牌字符串与有效秒数。"""
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return token, expires_in


def decode_access_token(token: str) -> int:
    """校验 access token，返回用户 id；无效时抛出 InvalidTokenError。"""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("invalid token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise InvalidTokenError("invalid token type")

    try:
        return int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise InvalidTokenError("invalid subject") from exc
