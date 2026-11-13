import asyncio
import os

import asyncpg


def test_users_table_exists(migrated_database):
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def table_name() -> str | None:
        connection = await asyncpg.connect(dsn)
        try:
            return await connection.fetchval("SELECT to_regclass('public.users')::text")
        finally:
            await connection.close()

    assert asyncio.run(table_name()) == "users"
