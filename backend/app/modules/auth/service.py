import anyio
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest

# 账号不存在时也执行一次哈希校验，避免用响应时间探测账号是否存在
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


async def register_user(db: AsyncSession, data: RegisterRequest) -> User:
    """注册新用户：检查用户名重复后写入数据库。"""
    existing = await db.scalar(select(User.id).where(User.username == data.username))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
        )

    # bcrypt 是 CPU 密集操作，放到线程池避免阻塞事件循环
    password_hash = await anyio.to_thread.run_sync(hash_password, data.password)
    user = User(
        username=data.username,
        password_hash=password_hash,
        nickname=data.nickname or data.username,
        role="user",
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        # 并发注册同名用户时由数据库唯一约束兜底
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="用户名已被注册"
        ) from exc
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, data: LoginRequest) -> User:
    """按用户名查找用户并校验密码；凭据错误统一返回 401。"""
    user = await db.scalar(select(User).where(User.username == data.username))

    if user is None:
        await anyio.to_thread.run_sync(
            verify_password, data.password, DUMMY_PASSWORD_HASH
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )

    password_ok = await anyio.to_thread.run_sync(
        verify_password, data.password, user.password_hash
    )
    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    return user


def issue_access_token(user: User) -> tuple[str, int]:
    """为用户签发 access token。"""
    return create_access_token(user.id)
