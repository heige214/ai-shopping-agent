from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.catalog.models import Product, ProductSku
from app.modules.commerce import address_service
from app.modules.commerce.models import CartItem, Order, OrderItem
from app.modules.commerce.schemas import (
    AddressSnapshot,
    AgentOrderFilter,
    AgentOrderOut,
    OrderCreate,
    OrderItemOut,
    OrderOut,
    OrderStatus,
)

ORDER_EXPIRE_MINUTES = 15


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_order_no(now: datetime) -> str:
    return f"{now:%Y%m%d%H%M%S}{secrets.randbelow(100000):05d}"


def _generate_payment_no(now: datetime) -> str:
    return f"PAY{now:%Y%m%d%H%M%S}{secrets.randbelow(10000):04d}"


def _unit_price(sku: ProductSku, product: Product) -> Decimal:
    return sku.price_override if sku.price_override is not None else product.price


def _to_order_out(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        order_no=order.order_no,
        status=order.status,
        total_amount=float(order.total_amount),
        payment_method=order.payment_method,
        payment_no=order.payment_no,
        address_snapshot=AddressSnapshot.model_validate(order.address_snapshot),
        items=[
            OrderItemOut(
                id=item.id,
                sku_id=item.sku_id,
                product_id=item.product_id,
                title=item.title_snapshot,
                image=item.image_snapshot,
                price=float(item.price_snapshot),
                color=item.color_snapshot,
                size=item.size_snapshot,
                quantity=item.quantity,
            )
            for item in order.items
        ],
        created_at=order.created_at,
        expires_at=order.expires_at,
        paid_at=order.paid_at,
        shipped_at=order.shipped_at,
        completed_at=order.completed_at,
        cancelled_at=order.cancelled_at,
    )


async def _reload_order(db: AsyncSession, order_id: int) -> OrderOut:
    order = await db.scalar(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
        )
    return _to_order_out(order)


async def _get_order_for_user(
    db: AsyncSession, user: User, order_id: int, *, for_update: bool = False
) -> Order:
    stmt = select(Order).where(Order.id == order_id)
    if for_update:
        stmt = stmt.with_for_update()
    else:
        stmt = stmt.options(selectinload(Order.items))

    order = await db.scalar(stmt)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
        )
    if order.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该订单"
        )
    return order


async def _restore_stock(db: AsyncSession, order_id: int) -> None:
    """订单行锁保护下调用，保证库存只恢复一次。"""
    rows = (
        await db.execute(
            select(OrderItem.sku_id, OrderItem.quantity).where(
                OrderItem.order_id == order_id
            )
        )
    ).all()
    for sku_id, quantity in rows:
        await db.execute(
            update(ProductSku)
            .where(ProductSku.id == sku_id)
            .values(stock=ProductSku.stock + quantity)
        )


async def expire_orders(
    db: AsyncSession, user_id: int | None = None
) -> int:
    """取消已到期的待支付订单并恢复库存，返回处理数量。"""
    now = _now()
    stmt = select(Order).where(
        Order.status == "pending_payment", Order.expires_at <= now
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    stmt = (
        stmt.order_by(Order.id.asc())
        .limit(100)
        .with_for_update(skip_locked=True)
    )
    orders = (await db.scalars(stmt)).all()
    if not orders:
        return 0

    for order in orders:
        order.status = "cancelled"
        order.cancelled_at = now
        await _restore_stock(db, order.id)
    await db.commit()
    return len(orders)


async def create_order(
    db: AsyncSession, user: User, data: OrderCreate
) -> OrderOut:
    """事务内锁 SKU、校验并扣库存、创建订单快照、删除已结算购物车项。"""
    address = await address_service._get_address(db, user, data.address_id)

    cart_rows = (
        await db.scalars(select(CartItem).where(CartItem.user_id == user.id))
    ).all()
    by_id = {row.id: row for row in cart_rows}

    if data.cart_item_ids:
        cart_items: list[CartItem] = []
        for item_id in data.cart_item_ids:
            item = by_id.get(item_id)
            if item is None:
                other = await db.get(CartItem, item_id)
                if other is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="无权访问该购物车项",
                    )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="购物车项不存在",
                )
            cart_items.append(item)
    else:
        cart_items = [row for row in cart_rows if row.selected]

    if not cart_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请选择要结算的商品",
        )

    sku_ids = {item.sku_id for item in cart_items}
    locked_rows = (
        await db.execute(
            select(ProductSku, Product)
            .join(Product, ProductSku.product_id == Product.id)
            .where(ProductSku.id.in_(sku_ids))
            .order_by(ProductSku.id.asc())
            .with_for_update(of=ProductSku)
        )
    ).all()
    locked = {sku.id: (sku, product) for sku, product in locked_rows}

    total = Decimal("0.00")
    for cart_item in cart_items:
        pair = locked.get(cart_item.sku_id)
        if pair is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="商品规格不存在",
            )
        sku, product = pair
        if product.status != "on_sale" or sku.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"「{product.title}」已下架",
            )
        if cart_item.quantity > sku.stock:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"「{product.title}」库存不足，"
                    f"当前仅剩 {sku.stock} 件"
                ),
            )
        total += _unit_price(sku, product) * cart_item.quantity

    now = _now()
    order = Order(
        order_no=_generate_order_no(now),
        user_id=user.id,
        address_snapshot=AddressSnapshot.model_validate(address).model_dump(),
        total_amount=total,
        status="pending_payment",
        payment_method="simulated",
        expires_at=now + timedelta(minutes=ORDER_EXPIRE_MINUTES),
    )
    db.add(order)

    try:
        await db.flush()
        for cart_item in cart_items:
            sku, product = locked[cart_item.sku_id]
            sku.stock -= cart_item.quantity
            db.add(
                OrderItem(
                    order_id=order.id,
                    sku_id=sku.id,
                    product_id=product.id,
                    title_snapshot=product.title,
                    image_snapshot=product.main_image,
                    price_snapshot=_unit_price(sku, product),
                    color_snapshot=sku.color,
                    size_snapshot=sku.size,
                    quantity=cart_item.quantity,
                )
            )
        await db.execute(
            delete(CartItem).where(
                CartItem.id.in_([item.id for item in cart_items]),
                CartItem.user_id == user.id,
            )
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="订单创建冲突，请重试",
        ) from exc

    return await _reload_order(db, order.id)


async def list_orders(
    db: AsyncSession, user: User, status_filter: OrderStatus | None
) -> list[OrderOut]:
    await expire_orders(db, user_id=user.id)
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
    )
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc())
    orders = (await db.scalars(stmt)).all()
    return [_to_order_out(order) for order in orders]


async def get_order(db: AsyncSession, user: User, order_id: int) -> OrderOut:
    await expire_orders(db, user_id=user.id)
    order = await _get_order_for_user(db, user, order_id)
    return _to_order_out(order)


async def pay_order(db: AsyncSession, user: User, order_id: int) -> OrderOut:
    """支付幂等：首次支付才写流水并累加销量。"""
    order = await _get_order_for_user(db, user, order_id, for_update=True)

    if order.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="订单已取消，无法支付"
        )
    if order.status in ("paid", "shipped", "completed"):
        return await _reload_order(db, order.id)

    now = _now()
    if order.expires_at <= now:
        order.status = "cancelled"
        order.cancelled_at = now
        await _restore_stock(db, order.id)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="订单已超时取消"
        )

    order.status = "paid"
    order.paid_at = now
    order.payment_no = _generate_payment_no(now)

    totals: dict[int, int] = defaultdict(int)
    rows = (
        await db.execute(
            select(OrderItem.product_id, OrderItem.quantity).where(
                OrderItem.order_id == order.id
            )
        )
    ).all()
    for product_id, quantity in rows:
        totals[product_id] += quantity
    for product_id, quantity in totals.items():
        await db.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(sales_count=Product.sales_count + quantity)
        )

    await db.commit()
    return await _reload_order(db, order.id)


async def cancel_order(db: AsyncSession, user: User, order_id: int) -> OrderOut:
    order = await _get_order_for_user(db, user, order_id, for_update=True)

    if order.status == "cancelled":
        return await _reload_order(db, order.id)
    if order.status != "pending_payment":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="当前订单状态无法取消",
        )

    order.status = "cancelled"
    order.cancelled_at = _now()
    await _restore_stock(db, order.id)
    await db.commit()
    return await _reload_order(db, order.id)


async def confirm_order(
    db: AsyncSession, user: User, order_id: int
) -> OrderOut:
    order = await _get_order_for_user(db, user, order_id, for_update=True)
    if order.status != "shipped":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仅已发货订单可确认收货",
        )
    order.status = "completed"
    order.completed_at = _now()
    await db.commit()
    return await _reload_order(db, order.id)


async def ship_order(db: AsyncSession, order_id: int) -> OrderOut:
    order = await db.scalar(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在"
        )
    if order.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="仅已支付订单可发货",
        )
    order.status = "shipped"
    order.shipped_at = _now()
    await db.commit()
    return await _reload_order(db, order.id)


async def list_agent_orders(
    db: AsyncSession, status_filter: AgentOrderFilter
) -> list[AgentOrderOut]:
    await expire_orders(db)

    stmt = (
        select(Order, User)
        .join(User, User.id == Order.user_id)
        .options(selectinload(Order.items))
    )
    if status_filter != "all":
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.order_by(Order.created_at.desc(), Order.id.desc())

    rows = (await db.execute(stmt)).all()
    result: list[AgentOrderOut] = []
    for order, buyer in rows:
        base = _to_order_out(order).model_dump()
        result.append(
            AgentOrderOut(
                **base,
                buyer_id=buyer.id,
                buyer_username=buyer.username,
                buyer_nickname=buyer.nickname,
            )
        )
    return result
