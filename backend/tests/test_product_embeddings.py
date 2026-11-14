import asyncio
import os

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.embeddings import FakeEmbeddingClient, NoopEmbeddingClient
from app.modules.catalog.models import Product
from scripts.seed_product_embeddings import seed_product_embeddings


def _run(handler):
    async def _run_handler():
        engine = create_async_engine(
            os.environ["DATABASE_URL"], poolclass=NullPool
        )
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await handler(session)
        finally:
            await engine.dispose()

    return asyncio.run(_run_handler())


async def _null_count(session) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.embedding.is_(None))
        )
        or 0
    )


def test_fills_null_embeddings_and_is_idempotent(guide_catalog):
    async def handler(session):
        await session.execute(update(Product).values(embedding=None))
        await session.commit()
        first = await seed_product_embeddings(
            session, client=FakeEmbeddingClient()
        )
        remaining_after_first = await _null_count(session)
        second = await seed_product_embeddings(
            session, client=FakeEmbeddingClient()
        )
        return first, second, remaining_after_first

    first, second, remaining = _run(handler)

    assert first["products_found"] == 40
    assert first["embeddings_filled"] == 40
    assert first["remaining_null"] == 0
    assert remaining == 0
    assert second["products_found"] == 0
    assert second["embeddings_filled"] == 0


def test_reembed_refreshes_all_products(guide_catalog):
    async def handler(session):
        await seed_product_embeddings(session, client=FakeEmbeddingClient())
        refreshed = await seed_product_embeddings(
            session, refresh=True, client=FakeEmbeddingClient()
        )
        return refreshed

    refreshed = _run(handler)

    assert refreshed["products_found"] == 40
    assert refreshed["embeddings_filled"] == 40
    assert refreshed["remaining_null"] == 0


def test_noop_client_keeps_embeddings_null(guide_catalog):
    async def handler(session):
        await session.execute(update(Product).values(embedding=None))
        await session.commit()
        stats = await seed_product_embeddings(
            session, client=NoopEmbeddingClient()
        )
        return stats, await _null_count(session)

    stats, remaining = _run(handler)

    assert stats["products_found"] == 40
    assert stats["embeddings_filled"] == 0
    assert stats["remaining_null"] == 40
    assert remaining == 40
