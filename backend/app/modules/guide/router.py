from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.guide.schemas import SizeRecommendationOut
from app.modules.guide.size import recommend_product_size

router = APIRouter(tags=["guide"])


@router.get(
    "/products/{product_id}/size-recommendation",
    response_model=SizeRecommendationOut,
)
async def size_recommendation(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SizeRecommendationOut:
    """按当前用户档案与商品尺码表返回推荐尺码；不改 M1 商品详情 DTO。"""
    product = await db.scalar(
        select(Product).where(
            Product.id == product_id, Product.status == "on_sale"
        )
    )
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="商品不存在或已下架",
        )
    recommendation = await recommend_product_size(db, product, current_user)
    return SizeRecommendationOut(
        product_id=product.id,
        recommended_size=recommendation.recommended_size,
        size_reason=recommendation.size_reason,
        source=recommendation.source,
        height_cm=current_user.height_cm,
        weight_kg=current_user.weight_kg,
        usual_size=current_user.usual_size,
    )
