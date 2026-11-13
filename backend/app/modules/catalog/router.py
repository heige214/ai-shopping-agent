from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user, get_current_user_optional
from app.modules.auth.models import User
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    CategoryNode,
    FavoriteState,
    ProductDetail,
    ProductPage,
    ProductSummary,
    SortOption,
)

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryNode])
async def list_categories(
    db: AsyncSession = Depends(get_db),
) -> list[CategoryNode]:
    """返回 4 个一级品类及其全部叶子，叶子 schema 已合并父级属性。"""
    return await service.get_category_tree(db)


@router.get("/products", response_model=ProductPage)
async def list_products(
    category_id: int | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    sort: SortOption = "recommended",
    db: AsyncSession = Depends(get_db),
) -> ProductPage:
    """商品列表：公开；一级品类默认包含其全部叶子。"""
    return await service.list_products(
        db,
        category_id=category_id,
        q=q,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product_detail(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
) -> ProductDetail:
    """商品详情：公开；带有效 Bearer 时返回 is_favorited。"""
    return await service.get_product_detail(db, product_id, current_user)


@router.get("/favorites", response_model=list[ProductSummary])
async def list_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductSummary]:
    """当前用户收藏列表，按收藏时间倒序。"""
    return await service.list_favorites(db, current_user)


@router.post("/products/{product_id}/favorite", response_model=FavoriteState)
async def add_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteState:
    """收藏商品；重复收藏幂等。"""
    return await service.add_favorite(db, current_user, product_id)


@router.delete("/products/{product_id}/favorite", response_model=FavoriteState)
async def remove_favorite(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FavoriteState:
    """取消收藏；未收藏时幂等返回 false。"""
    return await service.remove_favorite(db, current_user, product_id)
