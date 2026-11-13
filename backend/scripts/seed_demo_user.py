"""创建或修复演示账号 demo / demo123；重复执行不会重复创建。"""

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


async def seed_demo_user() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.username == DEMO_USERNAME)
        )
        if existing is not None:
            if verify_password(DEMO_PASSWORD, existing.password_hash):
                print("演示账号已存在，跳过")
                return
            # 已有同名账号但密码不是 demo123，重置为演示账号，避免验收登录失败
            existing.password_hash = hash_password(DEMO_PASSWORD)
            for field, value in DEMO_PROFILE.items():
                setattr(existing, field, value)
            await session.commit()
            print("演示账号已存在，已重置密码与资料")
            return

        session.add(
            User(
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                **DEMO_PROFILE,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            # 并发执行时由唯一索引兜底，另一个进程已经创建成功
            await session.rollback()
            print("演示账号已存在，跳过")
            return
        print("已创建演示账号 demo / demo123")


async def main() -> None:
    try:
        await seed_demo_user()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
