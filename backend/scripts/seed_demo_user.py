"""创建演示账号 demo / demo123；重复执行不会重复创建。"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.modules.auth.models import User

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


async def seed_demo_user() -> None:
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(User.id).where(User.username == DEMO_USERNAME)
        )
        if existing is not None:
            print("演示账号已存在，跳过")
            return

        session.add(
            User(
                username=DEMO_USERNAME,
                password_hash=hash_password(DEMO_PASSWORD),
                nickname="小鹿",
                role="user",
                height_cm=172,
                weight_kg=75,
                usual_size="M",
            )
        )
        await session.commit()
        print("已创建演示账号 demo / demo123")


async def main() -> None:
    try:
        await seed_demo_user()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
