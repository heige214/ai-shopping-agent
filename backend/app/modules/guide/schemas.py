from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GuideProductCard(BaseModel):
    """导购商品卡：在商品摘要上增加推荐理由与尺码。"""

    id: int
    title: str
    price: float
    original_price: float | None = None
    main_image: str | None = None
    brand: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    recommended_size: str | None = None
    size_reason: str | None = None
    sales_count: int = 0


class GuideProductsPayload(BaseModel):
    items: list[GuideProductCard] = Field(default_factory=list)
    relaxed: list[str] = Field(default_factory=list)
    query: dict[str, Any] = Field(default_factory=dict)


class ChatActionOut(BaseModel):
    """确认/取消动作的返回；非 pending 时也返回当前状态（幂等）。"""

    action_id: int
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    quantity: int | None = None
    cart_item_id: int | None = None
    available_sizes: list[str] = Field(default_factory=list)


class SizeRecommendationOut(BaseModel):
    product_id: int
    recommended_size: str | None = None
    size_reason: str | None = None
    source: str | None = None
    height_cm: int | None = None
    weight_kg: int | None = None
    usual_size: str | None = None
