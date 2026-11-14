from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.catalog.models import Product, ProductSku
from app.modules.commerce import cart_service
from app.modules.commerce.schemas import CartItemCreate
from app.modules.guide.cart import available_sizes
from app.modules.guide.schemas import ChatActionOut
from app.modules.support.models import ChatAction, ChatMessage, ChatSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_owned_action(
    db: AsyncSession, user: User, action_id: int, *, lock: bool = False
) -> ChatAction | None:
    stmt = (
        select(ChatAction)
        .join(ChatSession, ChatSession.id == ChatAction.session_id)
        .where(
            ChatAction.id == action_id,
            ChatSession.user_id == user.id,
        )
    )
    if lock:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


def _action_out(action: ChatAction) -> ChatActionOut:
    payload = action.payload or {}
    result = dict(action.result or {})
    return ChatActionOut(
        action_id=action.id,
        status=action.status,
        result=result,
        quantity=payload.get("quantity"),
        cart_item_id=result.get("cart_item_id"),
        available_sizes=list(result.get("available_sizes") or []),
    )


async def _sync_card(db: AsyncSession, action: ChatAction) -> None:
    """把动作状态同步回 action_card 消息，历史抽屉刷新后仍显示正确状态。"""
    message = await db.get(ChatMessage, action.message_id)
    if message is None:
        return
    content = dict(message.content or {})
    content.update({"status": action.status, "result": action.result})
    message.content = content
    meta = dict(message.meta or {})
    meta.update({"status": action.status, "result": action.result})
    message.meta = meta


async def _fail(
    db: AsyncSession,
    action: ChatAction,
    reason: str,
    sizes: list[str] | None = None,
) -> ChatActionOut:
    action.status = "failed"
    action.result = {
        "reason": reason,
        "available_sizes": list(sizes or []),
    }
    await _sync_card(db, action)
    await db.commit()
    return _action_out(action)


async def confirm_action(
    db: AsyncSession, user: User, action_id: int
) -> ChatActionOut:
    """确认加购：锁 action/SKU，复校验库存并复用 cart_service 写入。"""
    action = await _get_owned_action(db, user, action_id, lock=True)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="动作不存在"
        )
    if action.status != "pending":
        return _action_out(action)

    payload = dict(action.payload or {})
    product_id = int(payload.get("product_id") or 0)
    sku_id = int(payload.get("sku_id") or 0)
    quantity = int(payload.get("quantity") or 1)

    sku = await db.scalar(
        select(ProductSku)
        .where(ProductSku.id == sku_id)
        .with_for_update()
    )
    if sku is None:
        return await _fail(db, action, "商品规格不存在")
    product = await db.get(Product, product_id)
    if product is None:
        return await _fail(db, action, "商品不存在")
    if product.status != "on_sale":
        return await _fail(db, action, "商品已下架，暂时无法加入购物车")
    if sku.status != "active":
        sizes = await available_sizes(db, product_id)
        return await _fail(db, action, "该尺码已下架", sizes)

    try:
        item = await cart_service.add_cart_item(
            db,
            user,
            CartItemCreate(sku_id=sku_id, quantity=quantity),
            commit=False,
        )
    except HTTPException as exc:
        sizes = await available_sizes(db, product_id)
        return await _fail(db, action, str(exc.detail), sizes)

    action.status = "executed"
    action.result = {
        "cart_item_id": item.id,
        "quantity": quantity,
        "sku_id": sku_id,
        "price": item.price,
        "color": item.color,
        "size": item.size,
    }
    action.executed_at = _now()
    await _sync_card(db, action)
    await db.commit()
    return _action_out(action)


async def cancel_action(
    db: AsyncSession, user: User, action_id: int
) -> ChatActionOut:
    """取消动作：pending → cancelled；其余状态幂等返回。"""
    action = await _get_owned_action(db, user, action_id, lock=True)
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="动作不存在"
        )
    if action.status != "pending":
        return _action_out(action)

    action.status = "cancelled"
    action.result = {}
    await _sync_card(db, action)
    await db.commit()
    return _action_out(action)
