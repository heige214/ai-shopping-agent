"""把 seeds/knowledge/knowledge.json 导入数据库；重复执行幂等。

- 按文档标题 + seed_key 定位，已存在则更新内容，不重复插入
- 新 chunk 有 embedding 时先与已有 chunk 做余弦去重（>0.92 跳过）
- 没有 DASHSCOPE_API_KEY 时 embedding 为 NULL，关键词检索仍可用
- --embeddings-only 只补齐缺失 embedding
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import jieba
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import LLMError
from app.ai.deps import get_embedding_client
from app.db.session import AsyncSessionLocal, engine
from app.modules.catalog.models import Category, Product
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument

BACKEND_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = BACKEND_DIR / "seeds" / "knowledge" / "knowledge.json"
DUPLICATE_THRESHOLD = 0.92
EMBED_BATCH_SIZE = 10

logger = logging.getLogger(__name__)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"知识种子不存在：{path}，请先运行 build_knowledge_seed.py")
    return json.loads(path.read_text(encoding="utf-8"))


def build_search_text(content: str, question: str | None = None) -> str:
    text = f"{question} {content}" if question else content
    tokens = [token.strip() for token in jieba.cut_for_search(text) if token.strip()]
    return " ".join(tokens)


async def _embed_texts(client, texts: list[str]) -> list[list[float] | None]:
    vectors: list[list[float] | None] = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[start : start + EMBED_BATCH_SIZE]
        try:
            vectors.extend(await client.embed_texts(batch))
        except LLMError as exc:
            logger.warning("embedding 失败，保留 NULL：%s", exc)
            vectors.extend([None] * len(batch))
    return vectors


async def _find_document(
    session: AsyncSession,
    document: dict[str, Any],
    product_id: int | None,
    category_id: int | None,
) -> KnowledgeDocument | None:
    conditions = [
        KnowledgeDocument.scope == document["scope"],
        KnowledgeDocument.doc_type == document["doc_type"],
        KnowledgeDocument.title == document["title"],
    ]
    conditions.append(
        KnowledgeDocument.product_id == product_id
        if product_id is not None
        else KnowledgeDocument.product_id.is_(None)
    )
    conditions.append(
        KnowledgeDocument.category_id == category_id
        if category_id is not None
        else KnowledgeDocument.category_id.is_(None)
    )
    return await session.scalar(select(KnowledgeDocument).where(*conditions))


async def _find_chunk(
    session: AsyncSession, document_id: int, seed_key: str
) -> KnowledgeChunk | None:
    return await session.scalar(
        select(KnowledgeChunk).where(
            KnowledgeChunk.document_id == document_id,
            KnowledgeChunk.meta["seed_key"].astext == seed_key,
        )
    )


async def _is_duplicate(
    session: AsyncSession,
    vector: list[float],
    scope: str,
    product_id: int | None,
    category_id: int | None,
) -> bool:
    """只在同类检索范围内去重，避免把不同商品的尺码/详情误删。"""
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    conditions = [KnowledgeChunk.embedding.is_not(None)]
    if scope == "product":
        conditions.append(KnowledgeChunk.product_id == product_id)
    elif scope == "category":
        conditions.append(KnowledgeChunk.category_id == category_id)
    similarity = await session.scalar(
        select(1 - distance)
        .where(*conditions)
        .order_by(distance)
        .limit(1)
    )
    return similarity is not None and float(similarity) > DUPLICATE_THRESHOLD


async def seed(
    session: AsyncSession,
    knowledge_file: Path = KNOWLEDGE_FILE,
    force_embed: bool = False,
) -> dict[str, int]:
    data = load_json(knowledge_file)
    documents = data.get("documents", [])
    client = get_embedding_client()
    stats = {
        "documents": 0,
        "chunks_inserted": 0,
        "chunks_updated": 0,
        "chunks_duplicate": 0,
        "documents_skipped": 0,
    }

    for document in documents:
        product: Product | None = None
        category: Category | None = None
        if document["scope"] == "product":
            product = await session.scalar(
                select(Product).where(
                    Product.product_code == document["product_code"]
                )
            )
            if product is None:
                stats["documents_skipped"] += 1
                continue
            product_id = product.id
            category_id = product.category_id
        elif document["scope"] == "category":
            category = await session.scalar(
                select(Category).where(Category.slug == document["category_slug"])
            )
            if category is None:
                stats["documents_skipped"] += 1
                continue
            product_id = None
            category_id = category.id
        else:
            product_id = None
            category_id = None

        existing_document = await _find_document(
            session, document, product_id, category_id
        )
        if existing_document is None:
            existing_document = KnowledgeDocument(
                scope=document["scope"],
                product_id=product_id,
                category_id=category_id,
                doc_type=document["doc_type"],
                title=document["title"],
                source=document["source"],
                status="active",
            )
            session.add(existing_document)
            await session.flush()
        else:
            existing_document.source = document["source"]
            existing_document.status = "active"
        stats["documents"] += 1

        chunks = document["chunks"]
        chunk_records: list[tuple[dict[str, Any], KnowledgeChunk | None]] = []
        for chunk in chunks:
            existing_chunk = await _find_chunk(
                session, existing_document.id, chunk["seed_key"]
            )
            chunk_records.append((chunk, existing_chunk))

        texts_to_embed = [
            chunk["content"]
            for chunk, existing_chunk in chunk_records
            if existing_chunk is None or existing_chunk.embedding is None
        ]
        vectors = await _embed_texts(client, texts_to_embed) if texts_to_embed else []
        vector_iter = iter(vectors)

        for chunk, existing_chunk in chunk_records:
            search_text = chunk.get("search_text") or build_search_text(
                chunk["content"], chunk.get("question")
            )
            vector: list[float] | None = None
            if existing_chunk is None or existing_chunk.embedding is None:
                if texts_to_embed:
                    vector = next(vector_iter, None)
                if vector is None and force_embed:
                    logger.warning("chunk %s 未生成 embedding", chunk["seed_key"])

            if existing_chunk is not None:
                existing_chunk.content = chunk["content"]
                existing_chunk.search_text = search_text
                existing_chunk.meta = chunk["meta"]
                if existing_chunk.embedding is None and vector is not None:
                    existing_chunk.embedding = vector
                stats["chunks_updated"] += 1
                continue

            if vector is not None and await _is_duplicate(
                session,
                vector,
                document["scope"],
                product_id,
                category_id,
            ):
                stats["chunks_duplicate"] += 1
                continue

            session.add(
                KnowledgeChunk(
                    document_id=existing_document.id,
                    product_id=product_id,
                    category_id=category_id,
                    content=chunk["content"],
                    search_text=search_text,
                    embedding=vector,
                    meta=chunk["meta"],
                )
            )
            stats["chunks_inserted"] += 1

    await session.commit()
    return stats


async def backfill_embeddings(session: AsyncSession) -> dict[str, int]:
    client = get_embedding_client()
    chunks = (
        await session.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.embedding.is_(None))
            .order_by(KnowledgeChunk.id)
        )
    ).all()
    if not chunks:
        return {"chunks_found": 0, "embeddings_filled": 0}
    vectors = await _embed_texts(client, [chunk.content for chunk in chunks])
    filled = 0
    for chunk, vector in zip(chunks, vectors):
        if vector is not None:
            chunk.embedding = vector
            filled += 1
        if chunk.search_text is None:
            question = (chunk.meta or {}).get("question")
            chunk.search_text = build_search_text(chunk.content, question)
    await session.commit()
    return {"chunks_found": len(chunks), "embeddings_filled": filled}


async def count_rows(session: AsyncSession) -> dict[str, int]:
    from sqlalchemy import func

    documents = await session.scalar(select(func.count(KnowledgeDocument.id)))
    chunks = await session.scalar(select(func.count(KnowledgeChunk.id)))
    embedded = await session.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.embedding.is_not(None)
        )
    )
    return {
        "documents": int(documents or 0),
        "chunks": int(chunks or 0),
        "embedded": int(embedded or 0),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--embeddings-only",
        action="store_true",
        help="只补齐缺失 embedding，不导入/更新文档",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=KNOWLEDGE_FILE,
        help="知识种子 JSON 路径（测试可指定小样本）",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    async with AsyncSessionLocal() as session:
        if args.embeddings_only:
            stats = await backfill_embeddings(session)
            print(
                f"embedding 补齐：找到 {stats['chunks_found']} 个 NULL，"
                f"写入 {stats['embeddings_filled']} 个"
            )
        else:
            stats = await seed(session, knowledge_file=args.file)
            print(
                "知识导入：文档 {documents}，新增 chunk {chunks_inserted}，"
                "更新 {chunks_updated}，去重跳过 {chunks_duplicate}，"
                "缺商品/品类跳过 {documents_skipped}".format(**stats)
            )
        counts = await count_rows(session)
        print(
            f"数据库现有：文档 {counts['documents']} / chunk {counts['chunks']} / "
            f"有向量 {counts['embedded']}"
        )
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
