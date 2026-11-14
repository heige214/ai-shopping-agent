from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.catalog.models import Product
from app.modules.support.models import ChatMessage, ChatSession, SupportTicket
from app.modules.support.schemas import (
    MessageCreate,
    MessageOut,
    MessagePage,
    SessionCreate,
    SessionOut,
    SupportProduct,
)

GREETING_TEMPLATE = "你好，我是{title}的 AI 客服。商品参数、尺码、洗护或平台政策都可以问我。"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_out(session: ChatSession) -> SessionOut:
    product = session.product
    return SessionOut(
        id=session.id,
        type=session.type,
        product_id=session.product_id,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        product=SupportProduct(
            id=product.id,
            title=product.title,
            main_image=product.main_image,
            price=float(product.price),
        )
        if product
        else None,
    )


def _message_out(message: ChatMessage) -> MessageOut:
    return MessageOut(
        id=message.id,
        session_id=message.session_id,
        sender_type=message.sender_type,
        content_type=message.content_type,
        content=message.content,
        meta=message.meta or {},
        created_at=message.created_at,
    )


async def _get_owned_session(
    db: AsyncSession,
    user: User,
    session_id: int,
    *,
    lock: bool = False,
) -> ChatSession:
    stmt = select(ChatSession).where(
        ChatSession.id == session_id, ChatSession.user_id == user.id
    )
    if lock:
        stmt = stmt.with_for_update()
    session = await db.scalar(stmt)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在"
        )
    return session


async def create_session(
    db: AsyncSession, user: User, data: SessionCreate
) -> tuple[SessionOut, bool]:
    if data.type != "support":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="M3 暂只支持商品客服会话",
        )
    if data.product_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="商品客服会话必须指定商品",
        )
    product = await db.get(Product, data.product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在"
        )

    existing = await db.scalar(
        select(ChatSession)
        .where(
            ChatSession.user_id == user.id,
            ChatSession.type == "support",
            ChatSession.product_id == product.id,
            ChatSession.status == "active",
        )
        .order_by(ChatSession.id.desc())
        .limit(1)
    )
    if existing is not None:
        return _session_out(existing), False

    session = ChatSession(
        user_id=user.id,
        type="support",
        product_id=product.id,
        product=product,
        title=None,
        status="active",
        slot_state={},
    )
    db.add(session)
    await db.flush()
    db.add(
        ChatMessage(
            session_id=session.id,
            sender_type="ai",
            content_type="text",
            content={"text": GREETING_TEMPLATE.format(title=product.title)},
            meta={"greeting": True},
        )
    )
    await db.commit()
    created = await db.scalar(
        select(ChatSession).where(ChatSession.id == session.id)
    )
    assert created is not None
    return _session_out(created), True


async def list_sessions(
    db: AsyncSession, user: User, session_type: str | None
) -> list[SessionOut]:
    if session_type is not None and session_type != "support":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="M3 暂只支持商品客服会话",
        )
    stmt = select(ChatSession).where(ChatSession.user_id == user.id)
    if session_type:
        stmt = stmt.where(ChatSession.type == session_type)
    stmt = stmt.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
    sessions = (await db.scalars(stmt)).all()
    return [_session_out(item) for item in sessions]


async def list_messages(
    db: AsyncSession,
    user: User,
    session_id: int,
    before_id: int | None,
    limit: int,
) -> MessagePage:
    session = await _get_owned_session(db, user, session_id)
    limit = max(1, min(limit, 100))
    stmt = select(ChatMessage).where(ChatMessage.session_id == session.id)
    if before_id is not None:
        stmt = stmt.where(ChatMessage.id < before_id)
    stmt = stmt.order_by(ChatMessage.id.desc()).limit(limit + 1)
    rows = list((await db.scalars(stmt)).all())
    has_more = len(rows) > limit
    rows = list(reversed(rows[:limit]))
    return MessagePage(
        items=[_message_out(item) for item in rows], has_more=has_more
    )


async def append_user_message(
    db: AsyncSession,
    user: User,
    session_id: int,
    data: MessageCreate,
) -> tuple[ChatSession, ChatMessage]:
    session = await _get_owned_session(db, user, session_id, lock=True)
    if session.status != "active":
        detail = (
            "已转人工，请等待客服接入"
            if session.status == "waiting_human"
            else "会话已结束，请重新发起咨询"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if data.content_type != "text":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="M3 暂只支持文字消息",
        )
    text = str((data.content or {}).get("text") or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空"
        )
    if len(text) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="消息不能超过 2000 字",
        )

    message = ChatMessage(
        session_id=session.id,
        sender_type="user",
        content_type="text",
        content={"text": text},
        meta={},
    )
    if not session.title:
        session.title = text[:50]
    session.updated_at = _now()
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return session, message


async def escalate_session(
    db: AsyncSession, user: User, session_id: int
) -> tuple[SupportTicket, ChatSession]:
    session = await _get_owned_session(db, user, session_id, lock=True)
    if session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="会话已结束"
        )
    if session.status == "human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="客服已接入"
        )

    existing = await db.scalar(
        select(SupportTicket)
        .where(
            SupportTicket.session_id == session.id,
            SupportTicket.status == "waiting",
        )
        .order_by(SupportTicket.id.desc())
        .limit(1)
    )
    if existing is not None:
        session.status = "waiting_human"
        session.updated_at = _now()
        await db.commit()
        return existing, session

    last_user_message = await db.scalar(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session.id,
            ChatMessage.sender_type == "user",
        )
        .order_by(ChatMessage.id.desc())
        .limit(1)
    )
    summary = "商品客服转人工"
    if last_user_message is not None:
        text = str(last_user_message.content.get("text") or "").strip()
        if text:
            summary = f"商品客服转人工：{text[:200]}"

    ticket = SupportTicket(
        session_id=session.id,
        user_id=user.id,
        product_id=session.product_id,
        status="waiting",
        context_summary=summary,
        extraction_status="pending",
    )
    session.status = "waiting_human"
    session.updated_at = _now()
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket, session


async def add_feedback(
    db: AsyncSession,
    user: User,
    message_id: int,
    helpful: bool,
    comment: str | None,
) -> ChatMessage:
    message = await db.scalar(
        select(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .where(
            ChatMessage.id == message_id,
            ChatSession.user_id == user.id,
            ChatMessage.sender_type == "ai",
        )
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在"
        )
    message.meta = {
        **(message.meta or {}),
        "feedback": {
            "helpful": helpful,
            "comment": comment,
            "created_at": _now().isoformat(),
        },
    }
    await db.commit()
    return message
