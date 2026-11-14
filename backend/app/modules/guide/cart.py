from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import GuideCartQuery, GuideQuery
from app.ai.size_rules import LETTER_SIZE_ORDER, normalize_size
from app.modules.auth.models import User
from app.modules.catalog.models import Product, ProductSku
from app.modules.support.models import ChatAction, ChatMessage, ChatSession


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _size_key(size: str) -> tuple[int, str]:
    normalized = normalize_size(size)
    if normalized.isdigit():
        return (100 + int(normalized), normalized)
    return (LETTER_SIZE_ORDER.get(normalized.upper(), -1), normalized)


def _last_products(slot_state: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = (slot_state or {}).get("last_products") or []
    return [
        row
        for row in rows[:8]
        if isinstance(row, dict) and row.get("product_id")
    ]


def _recommended_size(
    slot_state: dict[str, Any] | None, product_id: int
) -> str | None:
    for row in _last_products(slot_state):
        if int(row.get("product_id") or 0) == product_id:
            value = row.get("recommended_size")
            return str(value) if value else None
    return None


def _available_sizes(skus: list[ProductSku]) -> list[str]:
    seen: dict[str, str] = {}
    for sku in skus:
        if sku.stock > 0:
            seen.setdefault(normalize_size(sku.size), sku.size)
    return sorted(seen.values(), key=_size_key)


@dataclass
class CartPlan:
    product: Product | None = None
    sku: ProductSku | None = None
    quantity: int = 1
    message: str | None = None
    quick_replies: list[str] = field(default_factory=list)
    available_sizes: list[str] = field(default_factory=list)


async def _find_named_product(
    db: AsyncSession,
    name: str,
    slot_state: dict[str, Any] | None,
) -> Product | None:
    cleaned = name.strip()
    if not cleaned:
        return None
    for row in _last_products(slot_state):
        title = str(row.get("title") or "")
        if title == cleaned or cleaned in title or title in cleaned:
            return await db.get(Product, int(row["product_id"]))

    stmt = select(Product).where(Product.title.ilike(f"%{cleaned}%"))
    on_sale = await db.scalar(
        stmt.where(Product.status == "on_sale")
        .order_by(Product.sales_count.desc(), Product.id.asc())
        .limit(1)
    )
    if on_sale is not None:
        return on_sale
    return await db.scalar(
        stmt.order_by(Product.sales_count.desc(), Product.id.asc()).limit(1)
    )


async def _resolve_target(
    db: AsyncSession,
    cart: GuideCartQuery,
    slot_state: dict[str, Any] | None,
) -> tuple[Product | None, str | None, list[str]]:
    rows = _last_products(slot_state)
    if cart.reference == "name":
        if not cart.product_name:
            return None, "要加购哪件商品？可以说商品名或第几件。", []
        product = await _find_named_product(db, cart.product_name, slot_state)
        if product is None:
            return (
                None,
                f"没有找到「{cart.product_name}」，可以说商品名或第几件。",
                [],
            )
        return product, None, []

    if cart.reference == "ordinal":
        ordinal = cart.ordinal or 1
        if not rows:
            return None, "还没有推荐商品，先告诉我想找什么，再帮你加入购物车。", []
        if ordinal > len(rows):
            return (
                None,
                f"当前只有 {len(rows)} 件推荐商品，没有第 {ordinal} 件。",
                [
                    f"把第{index}件加入购物车"
                    for index in range(1, min(len(rows), 4) + 1)
                ],
            )
        product = await db.get(Product, int(rows[ordinal - 1]["product_id"]))
        if product is None:
            return None, "这件商品已经不存在，可以重新找一件。", []
        return product, None, []

    if cart.reference == "deictic":
        if not rows:
            return None, "还没有推荐商品，先告诉我想找什么，再帮你加入购物车。", []
        if len(rows) == 1:
            product = await db.get(Product, int(rows[0]["product_id"]))
            if product is None:
                return None, "这件商品已经不存在，可以重新找一件。", []
            return product, None, []
        return (
            None,
            "你想加哪一件？可以说「第几件」，或者直接说商品名。",
            [
                f"把第{index}件加入购物车"
                for index in range(1, min(len(rows), 4) + 1)
            ],
        )

    if not rows:
        return None, "还没有推荐商品，先告诉我想找什么，再帮你加入购物车。", []
    return None, "你想把哪一件加入购物车？可以说「第几件」，或者直接说商品名。", [
        f"把第{index}件加入购物车" for index in range(1, min(len(rows), 4) + 1)
    ]


async def available_sizes(
    db: AsyncSession, product_id: int
) -> list[str]:
    """同款可售尺码（active 且库存 > 0），供失败卡换码。"""
    skus = list(
        (
            await db.scalars(
                select(ProductSku).where(
                    ProductSku.product_id == product_id,
                    ProductSku.status == "active",
                )
            )
        ).all()
    )
    return _available_sizes(skus)


async def _resolve_sku(
    db: AsyncSession,
    product: Product,
    cart: GuideCartQuery,
    slot_state: dict[str, Any] | None,
    quantity: int,
) -> tuple[ProductSku | None, str | None, list[str]]:
    if product.status != "on_sale":
        return None, "商品已下架，暂时无法加入购物车。", []

    skus = list(
        (
            await db.scalars(
                select(ProductSku)
                .where(
                    ProductSku.product_id == product.id,
                    ProductSku.status == "active",
                )
                .order_by(ProductSku.id.asc())
            )
        ).all()
    )
    if not skus:
        return None, "商品暂无可售规格。", []

    available = _available_sizes(skus)
    requested = cart.size or _recommended_size(slot_state, product.id)
    if requested:
        normalized = normalize_size(requested)
        candidates = [
            sku for sku in skus if normalize_size(sku.size) == normalized
        ]
        if not candidates:
            return (
                None,
                f"没有 {requested} 码，可选尺码：{'、'.join(available) or '无'}。",
                available,
            )
    else:
        distinct = {normalize_size(sku.size) for sku in skus}
        if len(distinct) > 1:
            sizes = available or sorted(
                {sku.size for sku in skus}, key=_size_key
            )
            return (
                None,
                "请告诉我想加的尺码"
                f"（{'、'.join(sizes)}），例如「把第二件 L 码加入购物车」。",
                available,
            )
        candidates = skus

    chosen = max(
        candidates,
        key=lambda sku: (sku.stock >= quantity, sku.stock, -sku.id),
    )
    if chosen.stock < quantity:
        if chosen.stock <= 0:
            reason = "该尺码已售罄"
        else:
            reason = f"库存不足，当前仅剩 {chosen.stock} 件"
        return (
            None,
            f"{reason}。可选尺码：{'、'.join(available) or '无'}。",
            available,
        )
    return chosen, None, available


async def resolve_cart_plan(
    db: AsyncSession,
    cart: GuideCartQuery,
    slot_state: dict[str, Any] | None,
) -> CartPlan:
    product, message, quick_replies = await _resolve_target(
        db, cart, slot_state
    )
    if message is not None or product is None:
        return CartPlan(
            message=message, quick_replies=quick_replies
        )
    sku, message, available = await _resolve_sku(
        db, product, cart, slot_state, cart.quantity
    )
    if message is not None or sku is None:
        return CartPlan(
            message=message,
            available_sizes=available,
        )
    return CartPlan(
        product=product,
        sku=sku,
        quantity=cart.quantity,
        available_sizes=available,
    )


def _payload(product: Product, sku: ProductSku, quantity: int) -> dict[str, Any]:
    price = (
        sku.price_override
        if sku.price_override is not None
        else product.price
    )
    return {
        "product_id": product.id,
        "sku_id": sku.id,
        "title": product.title,
        "color": sku.color,
        "size": sku.size,
        "quantity": quantity,
        "price": float(price),
        "image": product.main_image,
    }


async def _save_text(
    db: AsyncSession,
    session: ChatSession,
    query: GuideQuery,
    text: str,
    *,
    need_clarify: bool,
    quick_replies: list[str],
    degraded: bool,
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        sender_type="ai",
        content_type="text",
        content={"text": text},
        meta={
            "intent": "add_to_cart",
            "query": query.model_dump(),
            "need_clarify": need_clarify,
            "quick_replies": quick_replies,
            "degraded": degraded,
        },
    )
    session.updated_at = _now()
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def _create_action(
    db: AsyncSession,
    session: ChatSession,
    query: GuideQuery,
    payload: dict[str, Any],
) -> tuple[ChatAction, dict[str, Any]]:
    message = ChatMessage(
        session_id=session.id,
        sender_type="ai",
        content_type="action_card",
        content={},
        meta={"intent": "add_to_cart", "query": query.model_dump()},
    )
    session.updated_at = _now()
    db.add(message)
    await db.flush()

    action = ChatAction(
        session_id=session.id,
        message_id=message.id,
        action_type="add_to_cart",
        payload=payload,
        status="pending",
        result={},
    )
    db.add(action)
    await db.flush()

    card = {
        "action_id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "payload": payload,
    }
    message.content = card
    message.meta = {
        "intent": "add_to_cart",
        "query": query.model_dump(),
        "action_id": action.id,
        "action_type": action.action_type,
        "status": action.status,
        "payload": payload,
    }
    await db.commit()
    return action, card


async def stream_cart_turn(
    db: AsyncSession,
    session: ChatSession,
    user_message: ChatMessage,
    user: User,
    query: GuideQuery,
    slot_state: dict[str, Any],
    *,
    degraded: bool = False,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """加购轮次：meta → action → done；需要澄清时 meta → token* → done。"""
    started = time.monotonic()
    del user_message, user  # 用户消息已由 append_user_message 持久化
    cart = query.cart or GuideCartQuery()
    plan = await resolve_cart_plan(db, cart, slot_state)

    async def emit_done(message: ChatMessage) -> tuple[str, dict[str, Any]]:
        return "done", {
            "message_id": message.id,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    if plan.message is not None or plan.product is None or plan.sku is None:
        text = plan.message or "暂时无法加入购物车，请换个说法试试。"
        yield "meta", {
            "intent": "add_to_cart",
            "query": query.model_dump(),
            "need_clarify": True,
            "quick_replies": list(plan.quick_replies),
            "degraded": degraded,
            "available_sizes": list(plan.available_sizes),
        }
        yield "token", {"text": text}
        message = await _save_text(
            db,
            session,
            query,
            text,
            need_clarify=True,
            quick_replies=list(plan.quick_replies),
            degraded=degraded,
        )
        yield await emit_done(message)
        return

    payload = _payload(plan.product, plan.sku, plan.quantity)
    action, card = await _create_action(db, session, query, payload)
    yield "meta", {
        "intent": "add_to_cart",
        "query": query.model_dump(),
        "need_clarify": False,
        "quick_replies": [],
        "degraded": degraded,
        "action_id": action.id,
        "payload": payload,
    }
    yield "action", card
    yield "done", {
        "message_id": action.message_id,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
