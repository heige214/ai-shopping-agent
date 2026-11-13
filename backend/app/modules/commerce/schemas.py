from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OrderStatus = Literal[
    "pending_payment", "paid", "shipped", "completed", "cancelled"
]
AgentOrderFilter = Literal[
    "pending_payment", "paid", "shipped", "completed", "cancelled", "all"
]


class AddressIn(BaseModel):
    """新增地址请求；首个地址由服务端自动设为默认。"""

    receiver_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=6, max_length=20, pattern=r"^[0-9+\-\s]+$")
    province: str = Field(min_length=1, max_length=50)
    city: str = Field(min_length=1, max_length=50)
    district: str = Field(min_length=1, max_length=50)
    detail: str = Field(min_length=1, max_length=255)
    is_default: bool = False

    @field_validator(
        "receiver_name", "phone", "province", "city", "district", "detail",
        mode="before",
    )
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("不能为空")
        return value


class AddressUpdate(BaseModel):
    """部分更新地址；传入的字段才会被修改。"""

    receiver_name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(
        default=None, min_length=6, max_length=20, pattern=r"^[0-9+\-\s]+$"
    )
    province: str | None = Field(default=None, min_length=1, max_length=50)
    city: str | None = Field(default=None, min_length=1, max_length=50)
    district: str | None = Field(default=None, min_length=1, max_length=50)
    detail: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None

    @field_validator(
        "receiver_name", "phone", "province", "city", "district", "detail",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("不能为空")
        return value


class AddressOut(BaseModel):
    id: int
    receiver_name: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AddressSnapshot(BaseModel):
    receiver_name: str
    phone: str
    province: str
    city: str
    district: str
    detail: str

    model_config = ConfigDict(from_attributes=True)


class CartItemCreate(BaseModel):
    sku_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=999)


class CartItemUpdate(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=999)
    selected: bool | None = None


class CartItemOut(BaseModel):
    id: int
    sku_id: int
    product_id: int
    title: str
    main_image: str | None
    color: str
    size: str
    price: float
    quantity: int
    stock: int
    selected: bool
    available: bool


class CartOut(BaseModel):
    items: list[CartItemOut]
    total_quantity: int
    selected_count: int
    selected_amount: float
    all_selected: bool


class OrderCreate(BaseModel):
    address_id: int = Field(gt=0)
    cart_item_ids: list[int] = Field(default_factory=list, max_length=100)

    @field_validator("cart_item_ids")
    @classmethod
    def validate_item_ids(cls, value: list[int]) -> list[int]:
        if any(item_id <= 0 for item_id in value):
            raise ValueError("购物车项 ID 必须为正整数")
        return list(dict.fromkeys(value))


class OrderItemOut(BaseModel):
    id: int
    sku_id: int
    product_id: int
    title: str
    image: str | None
    price: float
    color: str
    size: str
    quantity: int


class OrderOut(BaseModel):
    id: int
    order_no: str
    status: OrderStatus
    total_amount: float
    payment_method: str
    payment_no: str | None
    address_snapshot: AddressSnapshot
    items: list[OrderItemOut]
    created_at: datetime
    expires_at: datetime
    paid_at: datetime | None
    shipped_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class AgentOrderOut(OrderOut):
    buyer_id: int
    buyer_username: str
    buyer_nickname: str | None
