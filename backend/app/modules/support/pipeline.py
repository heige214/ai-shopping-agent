from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, LLMError, SupportLLM, SupportPlan
from app.ai.size_rules import (
    build_size_availability_answer,
    collect_size_options,
    has_stock_word,
    parse_size_query,
)
from app.core.config import settings
from app.modules.knowledge.retrieval import (
    RetrievalResult,
    citations_from_chunks,
    load_product_doc_chunk,
    load_product_facts,
)
from app.modules.support.agent import run_support_agent
from app.modules.support.models import ChatMessage, ChatSession

SIZE_FACT_EXCLUDE_WORDS = (
    "订单",
    "物流",
    "快递",
    "投诉",
    "退款",
    "退货",
    "发票",
    "优惠券",
    "售后",
)
POLICY_WORDS = (
    "退货",
    "退款",
    "退换",
    "发票",
    "优惠券",
    "运费",
    "包邮",
    "支付",
    "售后",
    "政策",
)

CLARIFY_TEXT = "方便再具体说说想问商品的哪方面吗？比如材质、尺码、适用人群或平台政策。"
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
MISSING_PRODUCT_TEXT = "商品资料暂时不可用，建议转人工客服进一步确认。"
NO_ANSWER_PHRASE = "知识库暂未检索到有效信息"
MIN_ANSWER_SIMILARITY = 0.35


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


def _retrieval_stats(retrieval: RetrievalResult | None) -> dict[str, Any]:
    if retrieval is None:
        return {}
    return {
        "chunks": len(retrieval.chunks),
        "vector_hits": retrieval.vector_hits,
        "keyword_hits": retrieval.keyword_hits,
        "max_similarity": round(retrieval.max_similarity, 4),
        "ancestor_category_ids": retrieval.ancestor_category_ids,
    }


def _intent_from_plan(plan: SupportPlan, question: str) -> str:
    if plan.action == "handoff":
        return "order_qa" if plan.handoff_kind == "order" else "complaint"
    if plan.action == "chitchat":
        return "chitchat"
    if plan.action == "clarify":
        return "unknown"
    if plan.size or parse_size_query(question).requested_size:
        return "size_qa"
    if any(word in question for word in POLICY_WORDS):
        return "policy_qa"
    return "product_qa"


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
    handoff_required = False
    degraded = False
    retrieval_stats: dict[str, Any] = {}
    clarify_count = _clarify_count(session)
    question_topic: str | None = None
    agent_meta: dict[str, Any] = {}

    async def finalize() -> AsyncIterator[tuple[str, dict[str, Any]]]:
        latency_ms = int((time.monotonic() - started) * 1000)
        yield "answer_meta", {
            "intent": intent_name,
            "can_answer": can_answer,
            "confidence": round(float(confidence), 3),
            "partial": False,
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
                "partial": False,
                "handoff_required": handoff_required,
                "degraded": degraded,
                "citations": citation_items,
                "clarify_count": clarify_count,
                "retrieval": retrieval_stats,
                "agent": agent_meta or None,
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

    async def stream_llm(state: dict[str, Any]) -> AsyncIterator[
        tuple[str, dict[str, Any]]
    ]:
        nonlocal answer_text, handoff_required, degraded, can_answer, confidence
        nonlocal citation_items
        try:
            async with asyncio.timeout(settings.llm_timeout_seconds):
                async for token in llm.stream_answer(
                    question,
                    str(state.get("facts_text") or ""),
                    str(state.get("chunks_text") or ""),
                    False,
                ):
                    answer_text += token
                    yield "token", {"text": token}
        except (TimeoutError, LLMError) as exc:
            degraded = True
            handoff_required = True
            can_answer = False
            confidence = 0.0
            citation_items.clear()
            yield "error", {
                "code": _error_code(exc),
                "message": "服务繁忙，请稍后再试",
            }
            suffix = DEGRADED_TEXT if not answer_text else f"\n{DEGRADED_TEXT}"
            answer_text += suffix
            yield "token", {"text": suffix}

    # 商品被删除时只给固定提示
    if product is None:
        intent_name = "unknown"
        handoff_required = True
        async for event in stream_fixed(MISSING_PRODUCT_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    facts = await load_product_facts(db, product)

    # 0. 尺码/库存结构性问题：先查商品事实，避免“搜不到文档就说不知道”
    size_options = collect_size_options(
        facts.stock_by_size,
        facts.attributes.get("size"),
        facts.size_chart,
    )
    size_query = parse_size_query(question, size_options)
    if (
        size_query.is_availability
        and (
            size_query.requested_size
            or size_query.mentions_size
            or has_stock_word(question)
        )
        and not any(word in question for word in SIZE_FACT_EXCLUDE_WORDS)
    ):
        size_answer = build_size_availability_answer(
            facts.stock_by_size,
            size_options,
            size_query,
        )
        if size_answer:
            intent_name = "size_qa"
            question_topic = size_query.requested_size or "尺码"
            can_answer = True
            confidence = 0.95
            size_chunk = await load_product_doc_chunk(db, product.id, "size")
            if size_chunk:
                citation_items = citations_from_chunks([size_chunk])
            else:
                citation_items = [
                    {
                        "doc_type": "size",
                        "title": f"{product.title} · 尺码指南",
                        "chunk_id": None,
                        "content": "",
                    }
                ]
            retrieval_stats = {
                "chunks": 1 if size_chunk else 0,
                "vector_hits": 0,
                "keyword_hits": 0,
                "max_similarity": 0.0,
                "ancestor_category_ids": [],
                "source": "product_facts",
            }
            agent_meta = {
                "action": "rag",
                "tools": ["size_stock"],
                "trace": ["tool:size_stock"],
                "source": "product_facts",
            }
            yield "meta", {
                "intent": "size_qa",
                "need_clarify": False,
                "agent": agent_meta,
            }
            async for event in stream_fixed(size_answer):
                yield event
            yield "citations", {"items": citation_items}
            async for event in finalize():
                yield event
            return

    # 1. LangGraph Agent：规划动作/工具并读取商品事实与知识库
    try:
        async with asyncio.timeout(settings.llm_timeout_seconds):
            state = await run_support_agent(
                db,
                product,
                facts,
                question,
                llm,
                embedding_client,
            )
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
    except Exception:
        degraded = True
        handoff_required = True
        can_answer = False
        yield "meta", {"intent": "unknown", "need_clarify": False, "degraded": True}
        yield "error", {"code": "RETRIEVAL_ERROR", "message": "检索失败"}
        async for event in stream_fixed(DEGRADED_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    plan = state.get("plan")
    if plan is None:
        degraded = True
        handoff_required = True
        yield "meta", {"intent": "unknown", "need_clarify": False, "degraded": True}
        yield "error", {"code": "LLM_ERROR", "message": "规划失败"}
        async for event in stream_fixed(DEGRADED_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    retrieval = state.get("retrieval")
    retrieval_stats = _retrieval_stats(retrieval)
    intent_name = _intent_from_plan(plan, question)
    agent_meta = {
        "action": plan.action,
        "tools": list(plan.tools or []),
        "trace": list(state.get("tool_trace") or []),
    }
    yield "meta", {
        "intent": intent_name,
        "need_clarify": plan.action == "clarify",
        "agent": agent_meta,
    }

    # 2. 固定动作
    if plan.action == "handoff":
        handoff_required = True
        text = ORDER_QA_TEXT if plan.handoff_kind == "order" else COMPLAINT_TEXT
        async for event in stream_fixed(text):
            yield event
        async for event in finalize():
            yield event
        return

    if plan.action == "chitchat":
        can_answer = True
        confidence = 0.9
        async for event in stream_fixed(CHITCHAT_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    if plan.action == "clarify":
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

    # 3. 尺码工具直接给出确定答案
    size_answer = state.get("size_answer")
    if size_answer:
        can_answer = True
        confidence = 0.95
        question_topic = plan.size or "尺码"
        size_citation = state.get("size_citation")
        citation_items = [size_citation] if size_citation else []
        retrieval_stats = {
            "chunks": 1 if size_citation else 0,
            "vector_hits": 0,
            "keyword_hits": 0,
            "max_similarity": 0.0,
            "ancestor_category_ids": [],
            "source": "product_facts",
        }
        async for event in stream_fixed(str(size_answer)):
            yield event
        if citation_items:
            yield "citations", {"items": citation_items}
        async for event in finalize():
            yield event
        return

    # 4. RAG 回答：工具无结果时直接兜底，不额外调用可回答性模型
    if retrieval is None or (
        not retrieval.chunks
        and retrieval.max_similarity < MIN_ANSWER_SIMILARITY
    ):
        handoff_required = True
        async for event in stream_fixed(FALLBACK_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    can_answer = True
    confidence = 0.85
    citation_items = state.get("citations") or citations_from_chunks(
        retrieval.chunks
    )
    question_topic = plan.search_query

    async for event in stream_llm(state):
        yield event

    if NO_ANSWER_PHRASE in answer_text or "建议转人工" in answer_text:
        can_answer = False
        confidence = 0.0
        handoff_required = True
        citation_items.clear()
        suffix = "建议转人工客服进一步确认。"
        if "转人工" not in answer_text:
            answer_text += suffix
            yield "token", {"text": suffix}

    if not answer_text:
        degraded = True
        handoff_required = True
        can_answer = False
        confidence = 0.0
        citation_items.clear()
        answer_text = DEGRADED_TEXT
        yield "token", {"text": DEGRADED_TEXT}

    if citation_items:
        yield "citations", {"items": citation_items}

    async for event in finalize():
        yield event
