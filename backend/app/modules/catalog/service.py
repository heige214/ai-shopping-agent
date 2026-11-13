from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.catalog.models import Category, Favorite, Product, ProductSku
from app.modules.catalog.schemas import (
    AttributeSchema,
    CategoryNode,
    FavoriteState,
    ProductDetail,
    ProductPage,
    ProductSummary,
    SkuOut,
    SortOption,
)


def merge_attribute_schema(*schemas: dict[str, Any] | None) -> dict[str, Any]:
    """从父级到叶子合并 attributes，同 key 以叶子为准，保持插入顺序。"""
    merged: dict[str, dict[str, Any]] = {}
    for schema in schemas:
        if not schema:
            continue
        attributes = schema.get("attributes")
        if not isinstance(attributes, list):
            continue
        for attribute in attributes:
            if isinstance(attribute, dict) and attribute.get("key"):
                merged[str(attribute["key"])] = attribute
    return {"attributes": list(merged.values())}


async def get_category_tree(db: AsyncSession) -> list[CategoryNode]:
    categories = (
        await db.scalars(
            select(Category).order_by(
                Category.level.asc(), Category.sort_order.asc(), Category.id.asc()
            )
        )
    ).all()
    by_id = {category.id: category for category in categories}
    nodes: dict[int, CategoryNode] = {}

    for category in categories:
        parent = by_id.get(category.parent_id) if category.parent_id else None
        merged = merge_attribute_schema(
            parent.attribute_schema if parent else None,
            category.attribute_schema,
        )
        size_chart = (
            category.size_chart_template
            or (parent.size_chart_template if parent else None)
        )
        nodes[category.id] = CategoryNode(
            id=category.id,
            parent_id=category.parent_id,
            name=category.name,
            slug=category.slug,
            level=category.level,
            sort_order=category.sort_order,
            attribute_schema=merged,
            size_chart_template=size_chart,
            children=[],
        )

    roots: list[CategoryNode] = []
    for category in categories:
        node = nodes[category.id]
        if category.parent_id and category.parent_id in nodes:
            nodes[category.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


async def list_products(
    db: AsyncSession,
    *,
    category_id: int | None,
    q: str | None,
    page: int,
    page_size: int,
    sort: SortOption,
) -> ProductPage:
    filters = [Product.status == "on_sale"]

    if category_id is not None:
        category = await db.get(Category, category_id)
        if category is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="品类不存在"
            )
        if category.level == 1:
            child_ids = (
                await db.scalars(
                    select(Category.id).where(Category.parent_id == category.id)
                )
            ).all()
            filters.append(Product.category_id.in_(child_ids))
        else:
            filters.append(Product.category_id == category.id)

    keyword = (q or "").strip()
    if keyword:
        filters.append(
            or_(
                Product.title.contains(keyword, autoescape=True),
                Product.brand.contains(keyword, autoescape=True),
                Product.description.contains(keyword, autoescape=True),
            )
        )

    count_stmt = select(func.count()).select_from(Product).where(*filters)
    total = int(await db.scalar(count_stmt) or 0)

    order_by = {
        "recommended": (Product.sales_count.desc(), Product.id.asc()),
        "price_asc": (Product.price.asc(), Product.id.asc()),
        "price_desc": (Product.price.desc(), Product.id.asc()),
    }[sort]

    stmt = (
        select(Product)
        .where(*filters)
        .order_by(*order_by)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    products = (await db.scalars(stmt)).all()
    return ProductPage(
        items=[ProductSummary.model_validate(product) for product in products],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_product_detail(
    db: AsyncSession, product_id: int, current_user: User | None
) -> ProductDetail:
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )

    category = await db.get(Category, product.category_id)
    parent = (
        await db.get(Category, category.parent_id)
        if category is not None and category.parent_id is not None
        else None
    )
    merged = merge_attribute_schema(
        parent.attribute_schema if parent else None,
        category.attribute_schema if category else None,
    )
    size_chart = (
        product.size_chart
        or (category.size_chart_template if category else None)
        or (parent.size_chart_template if parent else None)
    )

    skus = (
        await db.scalars(
            select(ProductSku)
            .where(
                ProductSku.product_id == product.id,
                ProductSku.status == "active",
            )
            .order_by(ProductSku.id.asc())
        )
    ).all()

    is_favorited = False
    if current_user is not None:
        is_favorited = (
            await db.scalar(
                select(Favorite.id).where(
                    Favorite.user_id == current_user.id,
                    Favorite.product_id == product.id,
                )
            )
        ) is not None

    images = list(product.images or [])
    if not images and product.main_image:
        images = [product.main_image]

    return ProductDetail(
        id=product.id,
        product_code=product.product_code,
        category_id=product.category_id,
        title=product.title,
        price=float(product.price),
        original_price=(
            float(product.original_price)
            if product.original_price is not None
            else None
        ),
        main_image=product.main_image,
        brand=product.brand,
        sales_count=product.sales_count,
        description=product.description,
        images=images,
        attributes=dict(product.attributes or {}),
        attribute_schema=AttributeSchema.model_validate(merged),
        size_chart=size_chart,
        category_name=category.name if category else "",
        parent_category_name=parent.name if parent else None,
        skus=[
            SkuOut(
                id=sku.id,
                color=sku.color,
                size=sku.size,
                stock=sku.stock,
                price=float(
                    sku.price_override
                    if sku.price_override is not None
                    else product.price
                ),
                status=sku.status,
            )
            for sku in skus
        ],
        is_favorited=is_favorited,
    )


async def list_favorites(db: AsyncSession, user: User) -> list[ProductSummary]:
    stmt = (
        select(Product)
        .join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id, Product.status == "on_sale")
        .order_by(Favorite.created_at.desc(), Favorite.id.desc())
    )
    products = (await db.scalars(stmt)).all()
    return [ProductSummary.model_validate(product) for product in products]


async def add_favorite(db: AsyncSession, user: User, product_id: int) -> FavoriteState:
    product = await db.scalar(
        select(Product.id).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )
    existing = await db.scalar(
        select(Favorite.id).where(
            Favorite.user_id == user.id, Favorite.product_id == product_id
        )
    )
    if existing is None:
        db.add(Favorite(user_id=user.id, product_id=product_id))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
    return FavoriteState(favorited=True)


async def remove_favorite(
    db: AsyncSession, user: User, product_id: int
) -> FavoriteState:
    product = await db.scalar(
        select(Product.id).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在或已下架"
        )
    await db.execute(
        delete(Favorite).where(
            Favorite.user_id == user.id, Favorite.product_id == product_id
        )
    )
    await db.commit()
    return FavoriteState(favorited=False)
