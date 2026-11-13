import asyncio
import os

import asyncpg


def fetch_schema():
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")

    async def _fetch():
        connection = await asyncpg.connect(dsn)
        try:
            extensions = await connection.fetch(
                "SELECT extname FROM pg_extension WHERE extname = 'vector'"
            )
            columns = await connection.fetch(
                """
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name IN ('categories', 'products', 'product_skus', 'favorites')
                ORDER BY table_name, ordinal_position
                """
            )
            constraints = await connection.fetch(
                """
                SELECT conname, contype
                FROM pg_constraint
                WHERE conrelid::regclass::text IN
                      ('categories', 'products', 'product_skus', 'favorites')
                """
            )
            indexes = await connection.fetch(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('categories', 'products', 'product_skus', 'favorites')
                """
            )
            return extensions, columns, constraints, indexes
        finally:
            await connection.close()

    return asyncio.run(_fetch())


def test_catalog_tables_have_required_columns(migrated_database):
    extensions, columns, constraints, indexes = fetch_schema()
    assert [row["extname"] for row in extensions] == ["vector"]

    by_table: dict[str, dict[str, tuple[str, str]]] = {}
    for row in columns:
        by_table.setdefault(row["table_name"], {})[row["column_name"]] = (
            row["data_type"],
            row["is_nullable"],
        )

    assert set(by_table) == {"categories", "products", "product_skus", "favorites"}
    assert by_table["products"]["product_code"] == ("character varying", "NO")
    assert by_table["products"]["embedding"] == ("USER-DEFINED", "YES")
    assert by_table["products"]["attributes"] == ("jsonb", "NO")
    assert by_table["product_skus"]["sku_code"] == ("character varying", "NO")
    assert by_table["favorites"]["user_id"] == ("bigint", "NO")

    constraint_names = {row["conname"] for row in constraints}
    assert "uq_products_product_code" in constraint_names
    assert "uq_product_skus_product_color_size" in constraint_names
    assert "uq_product_skus_sku_code" in constraint_names
    assert "uq_favorites_user_product" in constraint_names

    index_defs = {row["indexname"]: row["indexdef"] for row in indexes}
    assert "ix_products_category_id" in index_defs
    assert "ix_products_attributes_gin" in index_defs
    assert "ix_products_embedding_hnsw" in index_defs
    assert "ix_product_skus_product_id" in index_defs
    assert "ix_favorites_user_id" in index_defs
