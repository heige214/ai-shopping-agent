from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import jieba
from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, LLMError
from app.ai.size_rules import LETTER_SIZE_ORDER
from app.modules.catalog.models import Category, Product, ProductSku
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument

RRF_K = 60
VECTOR_TOP_K = 20
KEYWORD_TOP_K = 20
FINAL_TOP_K = 8
# 低于该相似度的向量命中视为噪声；全部被过滤且无关键词命中时走不可答短路
VECTOR_MIN_SIMILARITY = 0.35

STOPWORDS = {
    "的",
    "了",
    "吗",
    "呢",
    "啊",
    "呀",
    "吧",
    "是",
    "我",
    "你",
    "他",
    "她",
    "它",
    "这",
    "那",
    "这个",
    "这件",
    "那个",
    "商品",
    "东西",
    "请问",
    "什么",
    "怎么",
    "怎样",
    "如何",
    "可以",
    "能否",
    "一下",
    "一个",
    "有",
    "会",
    "能",
    "想",
    "要",
    "买",
    "在",
    "和",
    "跟",
    "与",
    "就",
    "都",
    "也",
    "还",
    "很",
    "比较",
    "适合",
    "吗？",
    "呢？",
}

DOC_LABELS = {
    "detail": "商品详情",
    "faq": "商品问答",
    "size": "尺码指南",
    "care": "洗护指南",
    "policy": "平台规则",
}

ATTRIBUTE_LABELS = {
    "color": "颜色",
    "material": "材质",
    "fit": "版型",
    "thickness": "厚薄",
    "style": "风格",
    "gender": "适用人群",
    "season": "适用季节",
    "size": "可选尺码",
    "key_features": "设计细节",
}


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    content: str
    doc_type: str
    title: str | None
    scope: str
    product_id: int | None
    category_id: int | None
    similarity: float = 0.0
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float = 0.0


@dataclass
class ProductFacts:
    product_id: int
    title: str
    brand: str | None
    price: float
    attributes: dict[str, Any]
    size_chart: dict[str, Any] | None
    stock_by_size: dict[str, int] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    max_similarity: float
    vector_hits: int
    keyword_hits: int
    ancestor_category_ids: list[int]
    facts_text: str
    facts: ProductFacts


QUERY_SYNONYMS = {
    # 用户常把“尺码”简说成“码/号”，检索时统一回尺码文档
    "码": "尺码",
    "号": "尺码",
    # 知识片段用“现货/库存”描述库存，统一成“现货”便于召回
    "有货": "现货",
}


def tokenize_query(query: str) -> list[str]:
    """jieba 分词后只保留中文/字母/数字，过滤停用词，最多 12 个。"""
    tokens: list[str] = []
    for raw in jieba.cut_for_search(query):
        token = raw.strip().lower()
        if not token or token in STOPWORDS:
            continue
        if not re.fullmatch(r"[0-9a-z一-鿿]+", token):
            continue
        token = QUERY_SYNONYMS.get(token, token)
        if token.upper() in LETTER_SIZE_ORDER:
            token = "尺码"
        if token not in tokens:
            tokens.append(token)
        if len(tokens) >= 12:
            break
    return tokens


def _hit_key(hit: RetrievedChunk) -> int:
    return hit.chunk_id


def rrf_merge(
    vector_hits: list[RetrievedChunk],
    keyword_hits: list[RetrievedChunk],
    k: int = RRF_K,
    limit: int = FINAL_TOP_K,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion：按 chunk id 累加 1/(k+rank)。"""
    merged: dict[int, RetrievedChunk] = {}
    scores: dict[int, float] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        key = _hit_key(hit)
        merged.setdefault(key, hit)
        merged[key].vector_rank = rank
        merged[key].similarity = max(merged[key].similarity, hit.similarity)
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)

    for rank, hit in enumerate(keyword_hits, start=1):
        key = _hit_key(hit)
        if key not in merged:
            merged[key] = hit
        merged[key].keyword_rank = rank
        scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)

    ordered = sorted(
        merged.values(), key=lambda item: (-scores[_hit_key(item)], item.chunk_id)
    )[:limit]
    for item in ordered:
        item.rrf_score = scores[_hit_key(item)]
    return ordered


async def _ancestor_category_ids(db: AsyncSession, category_id: int | None) -> list[int]:
    """只返回一级品类 id；叶子品类知识由一级品类继承。"""
    ids: list[int] = []
    current = category_id
    visited: set[int] = set()
    while current and current not in visited:
        visited.add(current)
        category = await db.get(Category, current)
        if category is None:
            break
        if category.level == 1:
            ids.append(category.id)
        current = category.parent_id
    return ids


def _scope_condition(product_id: int, ancestor_ids: list[int]):
    return or_(
        and_(
            KnowledgeDocument.scope == "product",
            KnowledgeDocument.product_id == product_id,
        ),
        and_(
            KnowledgeDocument.scope == "category",
            KnowledgeDocument.category_id.in_(ancestor_ids),
        ),
        KnowledgeDocument.scope == "platform",
    )


def _base_select(product_id: int, ancestor_ids: list[int]):
    return (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(
            KnowledgeDocument,
            KnowledgeChunk.document_id == KnowledgeDocument.id,
        )
        .where(
            KnowledgeDocument.status == "active",
            _scope_condition(product_id, ancestor_ids),
        )
    )


def _to_hit(
    chunk: KnowledgeChunk,
    document: KnowledgeDocument,
    similarity: float = 0.0,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=document.id,
        content=chunk.content,
        doc_type=document.doc_type,
        title=document.title,
        scope=document.scope,
        product_id=document.product_id,
        category_id=document.category_id,
        similarity=max(0.0, min(1.0, similarity)),
    )


async def _vector_hits(
    db: AsyncSession,
    product_id: int,
    ancestor_ids: list[int],
    vector: list[float],
) -> list[RetrievedChunk]:
    distance = KnowledgeChunk.embedding.cosine_distance(vector)
    stmt = (
        _base_select(product_id, ancestor_ids)
        .add_columns((1 - distance).label("similarity"))
        .where(KnowledgeChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(VECTOR_TOP_K)
    )
    rows = (await db.execute(stmt)).all()
    return [
        _to_hit(chunk, document, float(similarity or 0.0))
        for chunk, document, similarity in rows
    ]


async def _keyword_hits(
    db: AsyncSession,
    product_id: int,
    ancestor_ids: list[int],
    query: str,
) -> list[RetrievedChunk]:
    tokens = tokenize_query(query)
    if not tokens:
        return []
    # regconfig 用字面量，避免 asyncpg 把 'simple' 推断成 text
    config = literal_column("'simple'")
    tsquery = func.to_tsquery(config, " | ".join(tokens))
    tsvector = func.to_tsvector(config, KnowledgeChunk.search_text)
    rank = func.ts_rank(tsvector, tsquery)
    stmt = (
        _base_select(product_id, ancestor_ids)
        .add_columns(rank.label("rank"))
        .where(tsvector.op("@@")(tsquery))
        .order_by(rank.desc(), KnowledgeChunk.id.asc())
        .limit(KEYWORD_TOP_K)
    )
    rows = (await db.execute(stmt)).all()
    return [_to_hit(chunk, document) for chunk, document, _ in rows]


async def load_product_facts(db: AsyncSession, product: Product) -> ProductFacts:
    skus = (
        await db.scalars(
            select(ProductSku)
            .where(ProductSku.product_id == product.id)
            .order_by(ProductSku.id)
        )
    ).all()
    stock_by_size: dict[str, int] = {}
    for sku in skus:
        stock_by_size[sku.size] = stock_by_size.get(sku.size, 0) + sku.stock
    return ProductFacts(
        product_id=product.id,
        title=product.title,
        brand=product.brand,
        price=float(product.price),
        attributes=product.attributes or {},
        size_chart=product.size_chart,
        stock_by_size=stock_by_size,
    )


def format_product_facts(facts: ProductFacts) -> str:
    lines = [f"商品：{facts.title}"]
    if facts.brand:
        lines.append(f"品牌：{facts.brand}")
    lines.append(f"价格：¥{facts.price:.2f}")
    for key, label in ATTRIBUTE_LABELS.items():
        value = facts.attributes.get(key)
        if value in (None, "", []):
            continue
        if isinstance(value, list):
            value = "、".join(str(item) for item in value)
        lines.append(f"{label}：{value}")
    if facts.stock_by_size:
        stock_text = "；".join(
            f"{size} {stock} 件" for size, stock in facts.stock_by_size.items()
        )
        lines.append(f"库存：{stock_text}")
    if facts.size_chart and facts.size_chart.get("rows"):
        unit = facts.size_chart.get("unit", "cm")
        rows: list[str] = []
        for row in facts.size_chart["rows"]:
            size = row.get("size")
            parts: list[str] = []
            for key, label in (
                ("height", "身高"),
                ("weight", "体重"),
                ("chest", "胸围"),
                ("waist", "腰围"),
                ("foot_length", "脚长"),
            ):
                value = row.get(key)
                if isinstance(value, list) and len(value) == 2:
                    parts.append(f"{label}{value[0]}-{value[1]}{unit}")
            if parts:
                rows.append(f"{size}：" + "，".join(parts))
        if rows:
            lines.append("尺码表：" + "；".join(rows))
    return "\n".join(lines)


def citations_from_chunks(
    chunks: list[RetrievedChunk],
    limit: int = 4,
) -> list[dict[str, Any]]:
    """把检索切片转成前端引用，按文档类型+标题去重。"""
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for chunk in chunks:
        key = (chunk.doc_type, chunk.title)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "doc_type": chunk.doc_type,
                "title": chunk.title,
                "chunk_id": chunk.chunk_id,
                "content": chunk.content[:400],
            }
        )
        if len(items) >= limit:
            break
    return items


async def load_product_doc_chunk(
    db: AsyncSession,
    product_id: int,
    doc_type: str,
) -> RetrievedChunk | None:
    """读取当前商品某类知识的第一条切片，用于结构化事实回答附引用。"""
    stmt = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeChunk.product_id == product_id,
            KnowledgeDocument.doc_type == doc_type,
            KnowledgeDocument.status == "active",
        )
        .order_by(KnowledgeChunk.id)
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    return _to_hit(row[0], row[1]) if row else None


def format_chunks_for_llm(chunks: list[RetrievedChunk]) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        label = DOC_LABELS.get(chunk.doc_type, chunk.doc_type)
        title = f"｜{chunk.title}" if chunk.title else ""
        lines.append(f"[{index}] {label}{title}")
        lines.append(chunk.content)
    return "\n".join(lines)


async def retrieve_context(
    db: AsyncSession,
    product_id: int,
    query: str,
    embedding_client: EmbeddingClient,
    facts: ProductFacts | None = None,
) -> RetrievalResult:
    product = await db.get(Product, product_id)
    if product is None:
        raise LookupError("商品不存在")
    ancestor_ids = await _ancestor_category_ids(db, product.category_id)

    vector: list[float] | None = None
    try:
        vector = await embedding_client.embed_query(query)
    except LLMError:
        vector = None

    vector_candidates = (
        await _vector_hits(db, product_id, ancestor_ids, vector) if vector else []
    )
    max_similarity = max(
        (hit.similarity for hit in vector_candidates), default=0.0
    )
    vector_hits = [
        hit for hit in vector_candidates if hit.similarity >= VECTOR_MIN_SIMILARITY
    ]
    keyword_hits = await _keyword_hits(db, product_id, ancestor_ids, query)
    chunks = rrf_merge(vector_hits, keyword_hits)
    if facts is None:
        facts = await load_product_facts(db, product)
    return RetrievalResult(
        chunks=chunks,
        max_similarity=max_similarity,
        vector_hits=len(vector_hits),
        keyword_hits=len(keyword_hits),
        ancestor_category_ids=ancestor_ids,
        facts_text=format_product_facts(facts),
        facts=facts,
    )
