from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth.deps import get_current_user, require_agent
from app.modules.auth.models import User
from app.modules.commerce import (
    address_service,
    cart_service,
    order_service,
)
from app.modules.commerce.schemas import (
    AddressIn,
    AddressOut,
    AddressUpdate,
    AgentOrderFilter,
    AgentOrderOut,
    CartItemCreate,
    CartItemOut,
    CartItemUpdate,
    CartOut,
    OrderCreate,
    OrderOut,
    OrderStatus,
)

router = APIRouter(tags=["commerce"])


# ---------------------------------------------------------------- 购物车
@router.get("/cart", response_model=CartOut)
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartOut:
    return await cart_service.get_cart(db, current_user)


@router.post("/cart/items", response_model=CartItemOut)
async def add_cart_item(
    data: CartItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartItemOut:
    """加购；同一 SKU 累加数量，累加后超过库存返回 409。"""
    return await cart_service.add_cart_item(db, current_user, data)


@router.patch("/cart/items/{item_id}", response_model=CartItemOut)
async def update_cart_item(
    item_id: int,
    data: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CartItemOut:
    return await cart_service.update_cart_item(db, current_user, item_id, data)


@router.delete("/cart/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cart_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await cart_service.delete_cart_item(db, current_user, item_id)


# ---------------------------------------------------------------- 地址
@router.get("/addresses", response_model=list[AddressOut])
async def list_addresses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AddressOut]:
    return await address_service.list_addresses(db, current_user)


@router.post(
    "/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED
)
async def create_address(
    data: AddressIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddressOut:
    """新增地址；首个地址自动设为默认。"""
    return await address_service.create_address(db, current_user, data)


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    address_id: int,
    data: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddressOut:
    return await address_service.update_address(
        db, current_user, address_id, data
    )


@router.delete(
    "/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_address(
    address_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    await address_service.delete_address(db, current_user, address_id)


# ---------------------------------------------------------------- 订单
@router.post(
    "/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED
)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """创建订单；cart_item_ids 为空时结算当前勾选项。"""
    return await order_service.create_order(db, current_user, data)


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrderOut]:
    return await order_service.list_orders(db, current_user, status_filter)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    return await order_service.get_order(db, current_user, order_id)


@router.post("/orders/{order_id}/pay", response_model=OrderOut)
async def pay_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """模拟支付；已支付订单重复调用直接返回成功。"""
    return await order_service.pay_order(db, current_user, order_id)


@router.post("/orders/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    return await order_service.cancel_order(db, current_user, order_id)


@router.post("/orders/{order_id}/confirm", response_model=OrderOut)
async def confirm_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderOut:
    """确认收货；仅已发货订单可确认。"""
    return await order_service.confirm_order(db, current_user, order_id)


# ---------------------------------------------------------------- 客服端
@router.get("/agent/orders", response_model=list[AgentOrderOut])
async def list_agent_orders(
    status_filter: AgentOrderFilter = Query(default="paid", alias="status"),
    db: AsyncSession = Depends(get_db),
    _agent: User = Depends(require_agent),
) -> list[AgentOrderOut]:
    """客服端订单列表；默认返回待发货的已支付订单。"""
    return await order_service.list_agent_orders(db, status_filter)


@router.post("/agent/orders/{order_id}/ship", response_model=OrderOut)
async def ship_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _agent: User = Depends(require_agent),
) -> OrderOut:
    """模拟发货；仅 paid 可发货。"""
    return await order_service.ship_order(db, order_id)
