from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    """M3 只接受 type=support；guide 由 service 返回 400。"""

    type: str = "support"
    product_id: int | None = None


class SupportProduct(BaseModel):
    id: int
    title: str
    main_image: str | None
    price: float


class SessionOut(BaseModel):
    id: int
    type: str
    product_id: int | None
    title: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    product: SupportProduct | None = None


class MessageCreate(BaseModel):
    content_type: str = "text"
    content: dict[str, Any] = Field(default_factory=dict)


class MessageOut(BaseModel):
    id: int
    session_id: int
    sender_type: str
    content_type: str
    content: dict[str, Any]
    meta: dict[str, Any]
    created_at: datetime


class MessagePage(BaseModel):
    items: list[MessageOut]
    has_more: bool


class EscalateOut(BaseModel):
    ticket_id: int
    ticket_status: str
    session_status: str


class FeedbackIn(BaseModel):
    helpful: bool
    comment: str | None = Field(default=None, max_length=500)


class FeedbackOut(BaseModel):
    message_id: int
    helpful: bool


class SessionList(BaseModel):
    items: list[SessionOut]

    model_config = ConfigDict(from_attributes=True)
