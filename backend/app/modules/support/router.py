from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, GuideLLM, SupportLLM, VisionClient
from app.ai.deps import (
    get_embedding_client,
    get_guide_llm,
    get_support_llm,
    get_vision_client,
)
from app.db.session import get_db
from app.modules.auth.deps import get_current_user
from app.modules.auth.models import User
from app.modules.guide.pipeline import stream_guide_turn
from app.modules.support import service
from app.modules.support.pipeline import stream_support_turn
from app.modules.support.schemas import (
    EscalateOut,
    FeedbackIn,
    FeedbackOut,
    MessageCreate,
    MessagePage,
    SessionCreate,
    SessionOut,
)

router = APIRouter(tags=["support"])


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/sessions", response_model=SessionOut)
async def create_session(
    data: SessionCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionOut:
    """创建/复用商品客服会话；同用户同商品复用最近 active 会话。"""
    session, created = await service.create_session(db, current_user, data)
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return session


@router.get("/chat/sessions", response_model=list[SessionOut])
async def list_sessions(
    type: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SessionOut]:
    return await service.list_sessions(db, current_user, type)


@router.get("/chat/sessions/{session_id}/messages", response_model=MessagePage)
async def list_messages(
    session_id: int,
    before_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessagePage:
    return await service.list_messages(
        db, current_user, session_id, before_id, limit
    )


@router.post("/chat/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    llm: SupportLLM = Depends(get_support_llm),
    guide_llm: GuideLLM = Depends(get_guide_llm),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    vision_client: VisionClient = Depends(get_vision_client),
) -> StreamingResponse:
    """发送消息并以 SSE 返回 AI 回答；guide 支持图片/语音，support 仅文字。"""
    session, user_message = await service.append_user_message(
        db, current_user, session_id, data
    )

    async def event_stream() -> AsyncIterator[str]:
        if session.type == "guide":
            events = stream_guide_turn(
                db,
                session,
                user_message,
                current_user,
                guide_llm,
                embedding_client,
                vision_client,
            )
        else:
            events = stream_support_turn(
                db, session, user_message, llm, embedding_client
            )
        async for event, payload in events:
            yield _sse(event, payload)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat/sessions/{session_id}/escalate", response_model=EscalateOut)
async def escalate_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EscalateOut:
    """最小转人工闭环：创建 waiting 工单并把会话置为 waiting_human。"""
    ticket, session = await service.escalate_session(
        db, current_user, session_id
    )
    return EscalateOut(
        ticket_id=ticket.id,
        ticket_status=ticket.status,
        session_status=session.status,
    )


@router.post("/chat/messages/{message_id}/feedback", response_model=FeedbackOut)
async def message_feedback(
    message_id: int,
    data: FeedbackIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeedbackOut:
    message = await service.add_feedback(
        db, current_user, message_id, data.helpful, data.comment
    )
    return FeedbackOut(message_id=message.id, helpful=data.helpful)
