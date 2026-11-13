"""创建或修复演示账号 demo / demo123 与客服账号 agent / agent123。"""

import asyncio

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.db.session import AsyncSessionLocal, engine
from app.modules.auth.models import User

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"
DEMO_PROFILE = {
    "nickname": "小鹿",
    "role": "user",
    "height_cm": 172,
    "weight_kg": 75,
    "usual_size": "M",
}

AGENT_USERNAME = "agent"
AGENT_PASSWORD = "agent123"
AGENT_PROFILE = {
    "nickname": "客服小助手",
    "role": "agent",
}


async def _seed_account(
    username: str, password: str, profile: dict, label: str
) -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.username == username)
        )
        if existing is not None:
            profile_matches = all(
                getattr(existing, field) == value
                for field, value in profile.items()
            )
            if verify_password(password, existing.password_hash) and profile_matches:
                print(f"{label}已存在，跳过")
                return
            # 已有同名账号但密码或资料不符，重置为演示账号，避免验收登录失败
            existing.password_hash = hash_password(password)
            for field, value in profile.items():
                setattr(existing, field, value)
            await session.commit()
            print(f"{label}已存在，已重置密码与资料")
            return

        session.add(
            User(
                username=username,
                password_hash=hash_password(password),
                **profile,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # 并发执行时由唯一索引兜底，另一个进程已经创建成功
            await session.rollback()
            print(f"{label}已存在，跳过")
            return
        print(f"已创建{label} {username} / {password}")


async def seed_demo_user() -> None:
    await _seed_account(DEMO_USERNAME, DEMO_PASSWORD, DEMO_PROFILE, "演示账号")


async def seed_agent_user() -> None:
    await _seed_account(AGENT_USERNAME, AGENT_PASSWORD, AGENT_PROFILE, "客服账号")


async def main() -> None:
    try:
        await seed_demo_user()
        await seed_agent_user()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
