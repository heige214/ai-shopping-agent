import asyncio
import os

import asyncpg


def fetch_schema():
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch():
        connection = await asyncpg.connect(dsn)
        try:
            columns = await connection.fetch(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN
                      ('addresses', 'cart_items', 'orders', 'order_items')
                ORDER BY table_name, ordinal_position
                """
            )
            constraints = await connection.fetch(
                """
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid::regclass::text IN
                      ('addresses', 'cart_items', 'orders', 'order_items')
                """
            )
            indexes = await connection.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN
                      ('addresses', 'cart_items', 'orders', 'order_items')
                """
            )
            return columns, constraints, indexes
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_commerce_tables_have_required_columns_and_constraints(migrated_database):
    columns, constraints, indexes = fetch_schema()

    by_table: dict[str, dict[str, tuple[str, str]]] = {}
    for row in columns:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = (
            row["data_type"],
            row["is_nullable"],
        )

    assert set(by_table) == {
        "addresses",
        "cart_items",
        "orders",
        "order_items",
    }
    assert by_table["addresses"]["user_id"] == ("bigint", "NO")
    assert by_table["addresses"]["is_default"] == ("boolean", "NO")
    assert by_table["cart_items"]["quantity"] == ("integer", "NO")
    assert by_table["cart_items"]["selected"] == ("boolean", "NO")
    assert by_table["orders"]["order_no"] == ("character varying", "NO")
    assert by_table["orders"]["address_snapshot"] == ("jsonb", "NO")
    assert by_table["orders"]["total_amount"] == ("numeric", "NO")
    assert by_table["orders"]["expires_at"] == (
        "timestamp with time zone",
        "NO",
    )
    assert by_table["order_items"]["price_snapshot"] == ("numeric", "NO")
    assert by_table["order_items"]["quantity"] == ("integer", "NO")

    constraint_names = {row["conname"] for row in constraints}
    assert "uq_addresses_user_default" not in constraint_names
    assert "uq_cart_items_user_sku" in constraint_names
    assert "ck_cart_items_quantity_positive" in constraint_names
    assert "uq_orders_order_no" in constraint_names
    assert "ck_orders_status_valid" in constraint_names
    assert "ck_order_items_quantity_positive" in constraint_names

    index_defs = {row["indexname"]: row["indexdef"] for row in indexes}
    assert "ix_addresses_user_id" in index_defs
    assert "uq_addresses_user_default" in index_defs
    assert "WHERE is_default" in index_defs["uq_addresses_user_default"]
    assert "ix_cart_items_user_id" in index_defs
    assert "ix_orders_user_status" in index_defs
    assert "ix_order_items_order_id" in index_defs
