from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.catalog.models import Product, ProductSku
from app.modules.commerce.models import CartItem
from app.modules.commerce.schemas import (
    CartItemCreate,
    CartItemOut,
    CartItemUpdate,
    CartOut,
)


def _unit_price(product: Product, sku: ProductSku) -> Decimal:
    return sku.price_override if sku.price_override is not None else product.price


def _to_item_out(
    cart_item: CartItem, sku: ProductSku, product: Product
) -> CartItemOut:
    available = (
        product.status == "on_sale"
        and sku.status == "active"
        and sku.stock >= cart_item.quantity
    )
    return CartItemOut(
        id=cart_item.id,
        sku_id=sku.id,
        product_id=product.id,
        title=product.title,
        main_image=product.main_image,
        color=sku.color,
        size=sku.size,
        price=float(_unit_price(product, sku)),
        quantity=cart_item.quantity,
        stock=sku.stock,
        selected=cart_item.selected,
        available=available,
    )


async def _cart_rows(db: AsyncSession, user: User):
    stmt = (
        select(CartItem, ProductSku, Product)
        .join(ProductSku, CartItem.sku_id == ProductSku.id)
        .join(Product, ProductSku.product_id == Product.id)
        .where(CartItem.user_id == user.id)
        .order_by(CartItem.created_at.desc(), CartItem.id.desc())
    )
    return (await db.execute(stmt)).all()


async def get_cart(db: AsyncSession, user: User) -> CartOut:
    rows = await _cart_rows(db, user)
    items = [_to_item_out(cart_item, sku, product) for cart_item, sku, product in rows]
    total_quantity = sum(item.quantity for item in items)
    selected = [item for item in items if item.selected]
    selected_amount = sum(
        (Decimal(str(item.price)) * item.quantity for item in selected),
        Decimal("0.00"),
    )
    return CartOut(
        items=items,
        total_quantity=total_quantity,
        selected_count=len(selected),
        selected_amount=float(selected_amount),
        all_selected=bool(items) and len(selected) == len(items),
    )


async def _load_sku_product(
    db: AsyncSession, sku_id: int
) -> tuple[ProductSku, Product]:
    sku = await db.get(ProductSku, sku_id)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品规格不存在"
        )
    product = await db.get(Product, sku.product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在"
        )
    return sku, product


async def _get_cart_item(
    db: AsyncSession, user: User, item_id: int
) -> CartItem:
    cart_item = await db.get(CartItem, item_id)
    if cart_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="购物车项不存在"
        )
    if cart_item.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该购物车项"
        )
    return cart_item


def _ensure_on_sale(sku: ProductSku, product: Product) -> None:
    if product.status != "on_sale" or sku.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="商品已下架"
        )


async def add_cart_item(
    db: AsyncSession, user: User, data: CartItemCreate
) -> CartItemOut:
    """同 SKU 累加数量；加购只校验库存，不锁库存。"""
    sku, product = await _load_sku_product(db, data.sku_id)
    _ensure_on_sale(sku, product)

    cart_item = await db.scalar(
        select(CartItem)
        .where(CartItem.user_id == user.id, CartItem.sku_id == data.sku_id)
        .with_for_update()
    )
    new_quantity = data.quantity + (cart_item.quantity if cart_item else 0)
    if new_quantity > sku.stock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"库存不足，当前仅剩 {sku.stock} 件",
        )

    if cart_item is None:
        cart_item = CartItem(
            user_id=user.id,
            sku_id=data.sku_id,
            quantity=data.quantity,
            selected=True,
        )
        db.add(cart_item)
    else:
        cart_item.quantity = new_quantity

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="购物车更新冲突，请重试",
        ) from exc

    await db.refresh(cart_item)
    return _to_item_out(cart_item, sku, product)


async def update_cart_item(
    db: AsyncSession, user: User, item_id: int, data: CartItemUpdate
) -> CartItemOut:
    cart_item = await _get_cart_item(db, user, item_id)
    sku, product = await _load_sku_product(db, cart_item.sku_id)

    if data.quantity is not None:
        if data.quantity > sku.stock:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"库存不足，当前仅剩 {sku.stock} 件",
            )
        cart_item.quantity = data.quantity
    if data.selected is not None:
        cart_item.selected = data.selected

    await db.commit()
    await db.refresh(cart_item)
    return _to_item_out(cart_item, sku, product)


async def delete_cart_item(db: AsyncSession, user: User, item_id: int) -> None:
    cart_item = await _get_cart_item(db, user, item_id)
    await db.delete(cart_item)
    await db.commit()
