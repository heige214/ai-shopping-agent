import asyncio
import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.ai.embeddings import FakeEmbeddingClient, NoopEmbeddingClient
from app.modules.knowledge.retrieval import (
    RetrievedChunk,
    retrieve_context,
    rrf_merge,
    tokenize_query,
)


def _hit(chunk_id: int, similarity: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=chunk_id,
        content=f"chunk-{chunk_id}",
        doc_type="faq",
        title=f"title-{chunk_id}",
        scope="product",
        product_id=1,
        category_id=1,
        similarity=similarity,
    )


@asynccontextmanager
async def session_scope():
    engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
    finally:
        await engine.dispose()


def test_rrf_merge_dedupes_and_prefers_both_lists():
    vector_hits = [_hit(1, 0.9), _hit(2, 0.8), _hit(3, 0.7)]
    keyword_hits = [_hit(3), _hit(1), _hit(4)]
    merged = rrf_merge(vector_hits, keyword_hits)
    ids = [hit.chunk_id for hit in merged]
    assert ids[0] == 1
    assert len(ids) == len(set(ids)) == 4
    assert ids.index(3) < ids.index(2)
    assert merged[0].rrf_score > merged[1].rrf_score
    assert merged[0].vector_rank == 1
    assert merged[0].keyword_rank == 2


def test_tokenize_filters_stopwords_and_keeps_topics():
    tokens = tokenize_query("这件商品的材质是什么，会起球吗？")
    assert "材质" in tokens
    assert "起球" in tokens
    assert "这件" not in tokens
    assert "什么" not in tokens


def test_retrieval_scope_only_product_ancestor_category_and_platform(
    sample_knowledge,
):
    async def _run():
        async with session_scope() as session:
            result = await retrieve_context(
                session,
                sample_knowledge["product_a_id"],
                "材质",
                FakeEmbeddingClient(),
            )
            contents = [chunk.content for chunk in result.chunks]
            assert any("纯棉" in content for content in contents)
            assert not any("涤纶" in content for content in contents)
            assert not any("鞋靴" in content for content in contents)
            assert result.facts.title == "测试衬衫"
            assert "价格" in result.facts_text

    asyncio.run(_run())


def test_keyword_fallback_when_embeddings_unavailable(sample_knowledge):
    async def _run():
        async with session_scope() as session:
            result = await retrieve_context(
                session,
                sample_knowledge["product_a_id"],
                "尺码",
                NoopEmbeddingClient(),
            )
            assert result.vector_hits == 0
            assert result.max_similarity == 0.0
            assert any("尺码表" in chunk.content for chunk in result.chunks)

    asyncio.run(_run())


def test_vector_recall_with_fake_embeddings(sample_knowledge):
    async def _run():
        async with session_scope() as session:
            result = await retrieve_context(
                session,
                sample_knowledge["product_a_id"],
                sample_knowledge["detail_content"],
                FakeEmbeddingClient(),
            )
            assert result.vector_hits >= 1
            assert result.max_similarity > 0.99
            assert result.chunks[0].content == sample_knowledge["detail_content"]

    asyncio.run(_run())


def test_unrelated_query_returns_no_chunks(sample_knowledge):
    async def _run():
        async with session_scope() as session:
            result = await retrieve_context(
                session,
                sample_knowledge["product_a_id"],
                "这件衣服能防弹吗",
                FakeEmbeddingClient(),
            )
            assert result.chunks == []
            assert result.max_similarity < 0.35

    asyncio.run(_run())
