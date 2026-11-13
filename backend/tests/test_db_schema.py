import asyncio
import os

import asyncpg


def test_users_table_schema(migrated_database):
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def fetch_schema():
        connection = await asyncpg.connect(dsn)
        try:
            columns = await connection.fetch(
                """
                SELECT column_name, data_type, character_maximum_length,
                       is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                ORDER BY ordinal_position
                """
            )
            indexes = await connection.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'users'
                """
            )
            return columns, indexes
        finally:
            await connection.close()

    columns, indexes = asyncio.run(fetch_schema())

    actual = {
        row["column_name"]: (
            row["data_type"],
            row["character_maximum_length"],
            row["is_nullable"],
        )
        for row in columns
    }
    assert list(actual) == [
        "id",
        "username",
        "password_hash",
        "nickname",
        "avatar_url",
        "role",
        "height_cm",
        "weight_kg",
        "usual_size",
        "created_at",
        "updated_at",
    ]
    assert actual["id"] == ("bigint", None, "NO")
    assert actual["username"] == ("character varying", 50, "NO")
    assert actual["password_hash"] == ("character varying", 255, "NO")
    assert actual["nickname"] == ("character varying", 50, "YES")
    assert actual["avatar_url"] == ("character varying", 500, "YES")
    assert actual["role"] == ("character varying", 20, "NO")
    assert actual["height_cm"] == ("smallint", None, "YES")
    assert actual["weight_kg"] == ("smallint", None, "YES")
    assert actual["usual_size"] == ("character varying", 10, "YES")
    assert actual["created_at"] == ("timestamp with time zone", None, "NO")
    assert actual["updated_at"] == ("timestamp with time zone", None, "NO")

    defaults = {row["column_name"]: row["column_default"] for row in columns}
    assert "'user'" in defaults["role"]
    assert "now()" in defaults["created_at"]
    assert "now()" in defaults["updated_at"]

    index_defs = {row["indexname"]: row["indexdef"] for row in indexes}
    assert set(index_defs) == {"pk_users", "ix_users_username"}
    assert "UNIQUE" in index_defs["pk_users"]
    assert "UNIQUE" in index_defs["ix_users_username"]
    assert "(username)" in index_defs["ix_users_username"]
