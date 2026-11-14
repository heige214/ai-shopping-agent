"""为 products.embedding 生成商品级向量；无 key 时保持 NULL。

- 默认只补齐 embedding 为 NULL 的在售商品，重复执行幂等
- --reembed 重建全部在售商品向量（切换 embedding 模型后使用）
- 未配置 DASHSCOPE_API_KEY 时客户端返回 None，脚本只报告数量，不中断
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, LLMError
from app.ai.deps import get_embedding_client
from app.db.session import AsyncSessionLocal, engine
from app.modules.catalog.models import Category, Product

EMBED_BATCH_SIZE = 10
ATTRIBUTE_LABELS = {
    "color": "颜色",
    "material": "材质",
    "fit": "版型",
    "thickness": "厚薄",
    "style": "风格",
    "gender": "适用人群",
    "season": "适用季节",
}

logger = logging.getLogger(__name__)


def build_product_text(
    product: Product,
    category: Category | None = None,
    parent: Category | None = None,
) -> str:
    """商品级检索文本：标题、品牌、品类、描述与关键属性。"""
    parts: list[str] = [product.title]
    if product.brand:
        parts.append(product.brand)
    category_path = " > ".join(
        name for name in (parent.name if parent else None, category.name if category else None) if name
    )
    if category_path:
        parts.append(category_path)
    if product.description:
        parts.append(product.description)
    for key, label in ATTRIBUTE_LABELS.items():
        value = (product.attributes or {}).get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        parts.append(f"{label}{value}")
    return "；".join(parts)[:1200]


async def _embed_texts(
    client: EmbeddingClient, texts: list[str]
) -> list[list[float] | None]:
    vectors: list[list[float] | None] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        try:
            vectors.extend(await client.embed_texts(batch))
        except LLMError as exc:
            logger.warning("embedding 失败，保留 NULL：%s", exc)
            vectors.extend([None] * len(batch))
    return vectors


async def _count_null(session: AsyncSession) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.embedding.is_(None))
        )
        or 0
    )


async def seed_product_embeddings(
    session: AsyncSession,
    *,
    refresh: bool = False,
    client: EmbeddingClient | None = None,
) -> dict[str, int]:
    """按需生成商品向量；返回扫描数、写入数与剩余 NULL 数。"""
    embedder = client or get_embedding_client()
    categories = list((await session.scalars(select(Category))).all())
    by_id = {category.id: category for category in categories}

    stmt = (
        select(Product)
        .where(Product.status == "on_sale")
        .order_by(Product.id)
    )
    if not refresh:
        stmt = stmt.where(Product.embedding.is_(None))
    products = list((await session.scalars(stmt)).all())
    if not products:
        return {
            "products_found": 0,
            "embeddings_filled": 0,
            "remaining_null": await _count_null(session),
        }

    texts = [
        build_product_text(
            product,
            by_id.get(product.category_id),
            (
                by_id.get(by_id[product.category_id].parent_id)
                if product.category_id in by_id
                and by_id[product.category_id].parent_id is not None
                else None
            ),
        )
        for product in products
    ]
    vectors = await _embed_texts(embedder, texts)
    filled = 0
    for product, vector in zip(products, vectors):
        if vector is not None:
            product.embedding = vector
            filled += 1
    await session.commit()
    return {
        "products_found": len(products),
        "embeddings_filled": filled,
        "remaining_null": await _count_null(session),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reembed",
        action="store_true",
        help="重建全部在售商品向量（切换 embedding 模型后使用）",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async with AsyncSessionLocal() as session:
        stats = await seed_product_embeddings(
            session, refresh=args.reembed
        )
        action = "重建" if args.reembed else "补齐"
        print(
            f"商品向量{action}：扫描 {stats['products_found']}，"
            f"写入 {stats['embeddings_filled']}，"
            f"剩余 NULL {stats['remaining_null']}"
        )
        if stats["products_found"] and not stats["embeddings_filled"]:
            print("未配置 DASHSCOPE_API_KEY，products.embedding 保持 NULL。")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
