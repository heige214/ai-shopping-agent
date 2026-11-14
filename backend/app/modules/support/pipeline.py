from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    AnswerabilityResult,
    EmbeddingClient,
    LLMError,
    SupportLLM,
)
from app.core.config import settings
from app.modules.knowledge.retrieval import (
    RetrievalResult,
    format_chunks_for_llm,
    retrieve_context,
)
from app.modules.support.models import ChatMessage, ChatSession

RAG_INTENTS = {"product_qa", "size_qa", "policy_qa"}
FIXED_HANDOFF_INTENTS = {"order_qa", "complaint"}

CLARIFY_TEXT = "我还不太确定你的问题。你是想问尺码、材质、洗护，还是平台政策？"
FALLBACK_TEXT = "知识库暂未检索到有效信息，建议转人工客服进一步确认。"
ORDER_QA_TEXT = (
    "订单和物流进度需要人工客服核实，我可以帮你转人工，"
    "对接后会结合你的订单信息继续处理。"
)
COMPLAINT_TEXT = (
    "非常抱歉给你带来不好的体验。这个问题需要人工客服跟进，"
    "你可以点击转人工，客服会尽快接入处理。"
)
CHITCHAT_TEXT = "我是这件商品的 AI 客服，可以问我商品材质、尺码、洗护或平台政策。"
DEGRADED_TEXT = "服务繁忙，暂时无法完成回答，请稍后再试或转人工客服。"
PARTIAL_SUFFIX = "其余部分建议转人工客服确认。"
MISSING_PRODUCT_TEXT = "商品资料暂时不可用，建议转人工客服进一步确认。"
MIN_ANSWER_SIMILARITY = 0.35
MIN_ANSWER_CONFIDENCE = 0.6


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "LLM_TIMEOUT"
    return getattr(exc, "code", "LLM_ERROR")


def _clarify_count(session: ChatSession) -> int:
    try:
        return int((session.slot_state or {}).get("clarify_count", 0))
    except (TypeError, ValueError):
        return 0


def _set_clarify_count(session: ChatSession, count: int) -> None:
    session.slot_state = {**(session.slot_state or {}), "clarify_count": count}


def _citations(retrieval: RetrievalResult) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for chunk in retrieval.chunks:
        key = (chunk.doc_type, chunk.title)
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "doc_type": chunk.doc_type,
                "title": chunk.title,
                "chunk_id": chunk.chunk_id,
            }
        )
        if len(items) >= 4:
            break
    return items


def _retrieval_stats(retrieval: RetrievalResult) -> dict[str, Any]:
    return {
        "chunks": len(retrieval.chunks),
        "vector_hits": retrieval.vector_hits,
        "keyword_hits": retrieval.keyword_hits,
        "max_similarity": round(retrieval.max_similarity, 4),
        "ancestor_category_ids": retrieval.ancestor_category_ids,
    }


async def stream_support_turn(
    db: AsyncSession,
    session: ChatSession,
    user_message: ChatMessage,
    llm: SupportLLM,
    embedding_client: EmbeddingClient,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """执行一轮客服回答，按 SSE 事件顺序产出 (event, data)。"""
    started = time.monotonic()
    question = str(user_message.content.get("text") or "").strip()
    product = session.product

    answer_text = ""
    citation_items: list[dict[str, Any]] = []
    intent_name = "unknown"
    can_answer = False
    confidence = 0.0
    partial = False
    handoff_required = False
    degraded = False
    retrieval_stats: dict[str, Any] = {}
    clarify_count = _clarify_count(session)
    question_topic: str | None = None

    async def finalize() -> AsyncIterator[tuple[str, dict[str, Any]]]:
        latency_ms = int((time.monotonic() - started) * 1000)
        yield "answer_meta", {
            "intent": intent_name,
            "can_answer": can_answer,
            "confidence": round(float(confidence), 3),
            "partial": partial,
            "handoff_required": handoff_required,
            "degraded": degraded,
        }
        message = ChatMessage(
            session_id=session.id,
            sender_type="ai",
            content_type="text",
            content={"text": answer_text or DEGRADED_TEXT},
            meta={
                "intent": intent_name,
                "question_topic": question_topic,
                "can_answer": can_answer,
                "confidence": round(float(confidence), 3),
                "partial": partial,
                "handoff_required": handoff_required,
                "degraded": degraded,
                "citations": citation_items,
                "clarify_count": clarify_count,
                "retrieval": retrieval_stats,
                "latency_ms": latency_ms,
            },
        )
        session.updated_at = _now()
        db.add(message)
        await db.commit()
        yield "done", {"message_id": message.id, "latency_ms": latency_ms}

    def stream_fixed(text: str) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        async def _iterate() -> AsyncIterator[tuple[str, dict[str, Any]]]:
            nonlocal answer_text
            for index in range(0, len(text), 8):
                token = text[index : index + 8]
                answer_text += token
                yield "token", {"text": token}

        return _iterate()

    async def stream_llm(
        retrieval: RetrievalResult,
        answerability: AnswerabilityResult,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        nonlocal answer_text, handoff_required, degraded, can_answer, confidence
        nonlocal partial
        chunks_text = format_chunks_for_llm(retrieval.chunks)
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                async for token in llm.stream_answer(
                    question,
                    retrieval.facts_text,
                    chunks_text,
                    answerability.partial,
                ):
                    answer_text += token
                    yield "token", {"text": token}
        except (TimeoutError, LLMError) as exc:
            degraded = True
            handoff_required = True
            can_answer = False
            confidence = 0.0
            partial = False
            citation_items.clear()
            yield "error", {
                "code": _error_code(exc),
                "message": "服务繁忙，请稍后再试",
            }
            suffix = DEGRADED_TEXT if not answer_text else f"\n{DEGRADED_TEXT}"
            answer_text += suffix
            yield "token", {"text": suffix}
            return

    # 商品被删除时只给固定提示
    if product is None:
        intent_name = "unknown"
        handoff_required = True
        async for event in stream_fixed(MISSING_PRODUCT_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    # 1. 意图路由
    try:
        async with asyncio.timeout(settings.llm_timeout_seconds):
            intent_result = await llm.route_intent(question, product.title)
    except (TimeoutError, LLMError) as exc:
        degraded = True
        handoff_required = True
        can_answer = False
        yield "meta", {"intent": "unknown", "need_clarify": False, "degraded": True}
        yield "error", {
            "code": _error_code(exc),
            "message": "服务繁忙，请稍后再试",
        }
        async for event in stream_fixed(DEGRADED_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    intent_name = intent_result.intent
    question_topic = (intent_result.entities or {}).get("question_topic")
    yield "meta", {
        "intent": intent_name,
        "need_clarify": intent_name == "unknown",
    }

    # 2. 固定话术意图
    if intent_name in FIXED_HANDOFF_INTENTS:
        handoff_required = True
        text = ORDER_QA_TEXT if intent_name == "order_qa" else COMPLAINT_TEXT
        async for event in stream_fixed(text):
            yield event
        async for event in finalize():
            yield event
        return

    if intent_name == "chitchat":
        can_answer = True
        confidence = 0.9
        async for event in stream_fixed(CHITCHAT_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    if intent_name == "unknown":
        if clarify_count == 0:
            _set_clarify_count(session, 1)
            clarify_count = 1
            handoff_required = False
            async for event in stream_fixed(CLARIFY_TEXT):
                yield event
        else:
            handoff_required = True
            async for event in stream_fixed(FALLBACK_TEXT):
                yield event
        async for event in finalize():
            yield event
        return

    # 3. RAG 意图：检索 + 可回答性
    try:
        retrieval = await retrieve_context(
            db, product.id, question, embedding_client
        )
    except Exception:
        degraded = True
        handoff_required = True
        yield "error", {"code": "RETRIEVAL_ERROR", "message": "检索失败"}
        async for event in stream_fixed(DEGRADED_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    retrieval_stats = _retrieval_stats(retrieval)
    if not retrieval.chunks and retrieval.max_similarity < MIN_ANSWER_SIMILARITY:
        answerability = AnswerabilityResult(
            can_answer=False,
            confidence=0.0,
            partial=False,
            missing="knowledge",
        )
    else:
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                answerability = await llm.judge_answerable(
                    question,
                    retrieval.facts_text,
                    format_chunks_for_llm(retrieval.chunks),
                    retrieval.max_similarity,
                )
        except (TimeoutError, LLMError) as exc:
            degraded = True
            handoff_required = True
            yield "error", {
                "code": _error_code(exc),
                "message": "服务繁忙，请稍后再试",
            }
            async for event in stream_fixed(DEGRADED_TEXT):
                yield event
            async for event in finalize():
                yield event
            return

    if not answerability.can_answer or answerability.confidence < MIN_ANSWER_CONFIDENCE:
        confidence = answerability.confidence
        if clarify_count == 0:
            _set_clarify_count(session, 1)
            clarify_count = 1
            handoff_required = False
            async for event in stream_fixed(CLARIFY_TEXT):
                yield event
        else:
            handoff_required = True
            async for event in stream_fixed(FALLBACK_TEXT):
                yield event
        async for event in finalize():
            yield event
        return

    can_answer = True
    confidence = answerability.confidence
    partial = answerability.partial
    handoff_required = partial
    citation_items = _citations(retrieval)

    async for event in stream_llm(retrieval, answerability):
        yield event

    if not answer_text:
        degraded = True
        handoff_required = True
        can_answer = False
        confidence = 0.0
        partial = False
        citation_items.clear()
        answer_text = DEGRADED_TEXT
        yield "token", {"text": DEGRADED_TEXT}

    if partial and "转人工" not in answer_text:
        answer_text += PARTIAL_SUFFIX
        yield "token", {"text": PARTIAL_SUFFIX}

    if citation_items:
        yield "citations", {"items": citation_items}

    async for event in finalize():
        yield event
