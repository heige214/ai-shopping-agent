from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.guide.actions import cancel_action, confirm_action
from app.modules.guide.schemas import ChatActionOut, SizeRecommendationOut
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


@router.post(
    "/chat/actions/{action_id}/confirm", response_model=ChatActionOut
)
async def confirm_chat_action(
    action_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatActionOut:
    """确认加购；非 pending 直接返回当前状态，不重复加购。"""
    return await confirm_action(db, current_user, action_id)


@router.post(
    "/chat/actions/{action_id}/cancel", response_model=ChatActionOut
)
async def cancel_chat_action(
    action_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatActionOut:
    """取消加购；非 pending 幂等返回当前状态。"""
    return await cancel_action(db, current_user, action_id)
