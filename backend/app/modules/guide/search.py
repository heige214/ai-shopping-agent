from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, GuideQuery, LLMError
from app.ai.guide_slots import query_condition_text
from app.modules.catalog.models import Category, Product

STRUCTURED_TOP_K = 30
VECTOR_TOP_K = 30
FUSION_TOP_K = 30
ATTRIBUTE_FILTER_KEYS = ("color", "material", "thickness")


@dataclass
class GuideSearchResult:
    candidates: list[Product]
    relaxed: list[str] = field(default_factory=list)
    structured_count: int = 0
    vector_count: int = 0


async def resolve_category_ids(
    db: AsyncSession, category_path: list[str]
) -> list[int]:
    """把 LLM/本地解析的品类名或 slug 解析为商品 category_id；一级含子类。"""
    terms = [str(term).strip() for term in category_path if str(term).strip()]
    if not terms:
        return []
    categories = list((await db.scalars(select(Category))).all())
    children: dict[int, list[int]] = {}
    for category in categories:
        if category.parent_id is not None:
            children.setdefault(category.parent_id, []).append(category.id)

    matched = [
        category
        for term in terms
        for category in categories
        if category.name == term or category.slug == term
    ]
    if not matched:
        return []

    deepest = [category for category in matched if category.level == 2]
    if deepest:
        return list(dict.fromkeys(category.id for category in deepest))

    ids: list[int] = []
    for category in matched:
        ids.append(category.id)
        ids.extend(children.get(category.id, []))
    return list(dict.fromkeys(ids))


def _attribute_condition(key: str, values: list[str]):
    if key == "material":
        return or_(
            *[
                Product.attributes[key].astext.ilike(f"%{value}%")
                for value in values
            ]
        )
    return or_(
        *[Product.attributes[key].astext == value for value in values]
    )


def build_conditions(
    query: GuideQuery,
    category_ids: list[int],
    include: set[str],
    price_active: bool,
) -> list:
    conditions = [Product.status == "on_sale"]
    if category_ids:
        conditions.append(Product.category_id.in_(category_ids))
    if price_active:
        if query.price.min is not None:
            conditions.append(Product.price >= query.price.min)
        if query.price.max is not None:
            conditions.append(Product.price <= query.price.max)
    for key in ATTRIBUTE_FILTER_KEYS:
        values = query.filters.get(key) or []
        if key in include and values:
            conditions.append(_attribute_condition(key, values))
    return conditions


async def structured_candidates(
    db: AsyncSession,
    conditions: list,
    limit: int = STRUCTURED_TOP_K,
) -> list[Product]:
    stmt = (
        select(Product)
        .where(*conditions)
        .order_by(Product.sales_count.desc(), Product.id.asc())
        .limit(limit)
    )
    return list((await db.scalars(stmt)).all())


async def vector_candidates(
    db: AsyncSession,
    category_ids: list[int],
    query_text: str,
    embedding_client: EmbeddingClient,
    *,
    query: GuideQuery | None = None,
    include: set[str] | None = None,
    price_active: bool = True,
    limit: int = VECTOR_TOP_K,
) -> list[tuple[Product, float]]:
    """商品级向量召回；无 embedding 时返回空列表并退化为结构化召回。"""
    try:
        vector = await embedding_client.embed_query(query_text)
    except LLMError:
        return []
    if not vector:
        return []

    if query is not None:
        conditions = build_conditions(
            query,
            category_ids,
            include
            if include is not None
            else set(ATTRIBUTE_FILTER_KEYS),
            price_active,
        )
    else:
        conditions = [Product.status == "on_sale"]
        if category_ids:
            conditions.append(Product.category_id.in_(category_ids))

    distance = Product.embedding.cosine_distance(vector)
    stmt = (
        select(Product, (1 - distance).label("similarity"))
        .where(*conditions, Product.embedding.is_not(None))
        .order_by(distance, Product.id.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        (product, float(similarity or 0.0)) for product, similarity in rows
    ]


def rrf_merge_products(
    structured: list[Product],
    vector: list[tuple[Product, float]],
    k: int = 60,
    limit: int = FUSION_TOP_K,
) -> list[Product]:
    """Reciprocal Rank Fusion：按商品 id 累加 1/(k+rank)。"""
    products: dict[int, Product] = {}
    scores: dict[int, float] = {}
    for rank, product in enumerate(structured, start=1):
        products.setdefault(product.id, product)
        scores[product.id] = scores.get(product.id, 0.0) + 1.0 / (k + rank)
    for rank, (product, _similarity) in enumerate(vector, start=1):
        products.setdefault(product.id, product)
        scores[product.id] = scores.get(product.id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(
        products.values(), key=lambda product: (-scores[product.id], product.id)
    )
    return ordered[:limit]


async def search_products(
    db: AsyncSession,
    query: GuideQuery,
    embedding_client: EmbeddingClient,
) -> GuideSearchResult:
    """结构化 + 商品向量 → RRF；无结果时按厚薄→材质→价格逐级放宽。"""
    if (
        query.price.min is not None
        and query.price.max is not None
        and query.price.min > query.price.max
    ):
        return GuideSearchResult([])

    category_ids = await resolve_category_ids(db, query.category_path)
    query_text = query.semantic or query_condition_text(query) or "商品"
    relaxed: list[str] = []
    removed: set[str] = set()
    stages = [
        ("thickness", "厚薄"),
        ("material", "材质"),
        ("price", "价格"),
    ]

    for stage in [None, *stages]:
        if stage is not None:
            key, label = stage
            if key == "thickness" and not query.filters.get("thickness"):
                continue
            if key == "material" and not query.filters.get("material"):
                continue
            if (
                key == "price"
                and query.price.min is None
                and query.price.max is None
            ):
                continue
            removed.add(key)
            relaxed = [item for item in relaxed if item != label] + [label]

        include = {
            key
            for key in ATTRIBUTE_FILTER_KEYS
            if query.filters.get(key) and key not in removed
        }
        price_active = "price" not in removed
        conditions = build_conditions(
            query, category_ids, include, price_active
        )
        structured = await structured_candidates(db, conditions)
        vector = await vector_candidates(
            db,
            category_ids,
            query_text,
            embedding_client,
            query=query,
            include=include,
            price_active=price_active,
        )
        merged = rrf_merge_products(structured, vector)
        if merged:
            return GuideSearchResult(
                candidates=merged,
                relaxed=list(relaxed),
                structured_count=len(structured),
                vector_count=len(vector),
            )

    return GuideSearchResult(
        candidates=[],
        relaxed=list(relaxed),
        structured_count=0,
        vector_count=0,
    )
