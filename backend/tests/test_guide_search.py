import asyncio
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.base import GuidePrice, GuideQuery
from app.ai.embeddings import FakeEmbeddingClient
from app.modules.guide.search import (
    resolve_category_ids,
    rrf_merge_products,
    search_products,
    vector_candidates,
)


def _run(coro):
    return asyncio.run(coro)


def _with_session(handler):
    async def _run_handler():
        engine = create_async_engine(
            os.environ["DATABASE_URL"], poolclass=NullPool
        )
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await handler(session)
        finally:
            await engine.dispose()

    return _run(_run_handler())


def _query(**overrides) -> GuideQuery:
    data = {
        "intent": "search",
        "semantic": "找商品",
        "category_path": ["服装", "衬衫"],
        "filters": {},
        "price": GuidePrice(),
    }
    data.update(overrides)
    return GuideQuery(**data)


def _codes(result) -> set[str]:
    return {product.product_code for product in result.candidates}


def test_resolve_category_path_uses_deepest_child(guide_catalog):
    async def handler(session):
        ids = await resolve_category_ids(session, ["服装", "衬衫"])
        parent_ids = await resolve_category_ids(session, ["服装"])
        return ids, parent_ids

    ids, parent_ids = _with_session(handler)

    assert ids == [guide_catalog["category_ids"]["shirts"]]
    assert set(parent_ids) == {
        guide_catalog["category_ids"]["clothing"],
        guide_catalog["category_ids"]["shirts"],
    }


def test_structured_filters_color_thickness_and_price(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(
                filters={"color": ["蓝色"], "thickness": ["薄款"]},
                price=GuidePrice(max=200),
            ),
            FakeEmbeddingClient(),
        )
    )

    assert _codes(result) == {"G01", "G02"}
    assert all(product.price <= 200 for product in result.candidates)


def test_material_filter_uses_contains_match(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(filters={"material": ["棉"]}),
            FakeEmbeddingClient(),
        )
    )

    codes = _codes(result)
    assert {"G01", "G03", "G06", "G07"} <= codes
    assert "G02" not in codes
    assert "G09" not in codes


def test_vector_candidates_recall_related_product(guide_catalog):
    async def handler(session):
        products = await resolve_category_ids(session, ["服装", "衬衫"])
        return await vector_candidates(
            session,
            products,
            "蓝色亚麻衬衫",
            FakeEmbeddingClient(),
        )

    hits = _with_session(handler)
    hit_codes = {product.product_code for product, _ in hits}

    assert "G02" in hit_codes


def test_rrf_merge_puts_shared_hits_first():
    class Item:
        def __init__(self, item_id: int) -> None:
            self.id = item_id

    structured = [Item(1), Item(2)]
    vector = [(Item(2), 0.9), (Item(3), 0.8)]
    merged = rrf_merge_products(structured, vector)

    assert [item.id for item in merged][0] == 2
    assert {item.id for item in merged} == {1, 2, 3}


def test_relaxation_order_thickness_then_material(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(
                filters={
                    "color": ["蓝色"],
                    "material": ["真丝"],
                    "thickness": ["薄款"],
                }
            ),
            FakeEmbeddingClient(),
        )
    )

    assert result.relaxed == ["厚薄", "材质"]
    codes = _codes(result)
    assert {"G01", "G02", "G05"} <= codes


def test_price_is_relaxed_last(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(filters={"color": ["蓝色"]}, price=GuidePrice(max=50)),
            FakeEmbeddingClient(),
        )
    )

    assert result.relaxed == ["价格"]
    assert _codes(result) == {"G01", "G02", "G05"}


def test_color_is_never_relaxed(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(filters={"color": ["紫色"]}, price=GuidePrice(max=1000)),
            FakeEmbeddingClient(),
        )
    )

    assert result.relaxed == ["价格"]
    assert result.candidates == []


def test_contradictory_price_returns_empty(guide_catalog):
    result = _with_session(
        lambda session: search_products(
            session,
            _query(price=GuidePrice(min=500, max=100)),
            FakeEmbeddingClient(),
        )
    )

    assert result.candidates == []
    assert result.relaxed == []
