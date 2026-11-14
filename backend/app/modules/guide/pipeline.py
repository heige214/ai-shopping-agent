from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    EmbeddingClient,
    GuideLLM,
    GuideQuery,
    GuideRerank,
    LLMError,
    VisionClient,
    VisionResult,
)
from app.ai.guide_local import (
    CHITCHAT_TEXT,
    NO_RESULT_TEXT,
    build_local_guide_answer,
)
from app.ai.guide_slots import (
    default_reason,
    extract_local_guide_query,
    merge_guide_query,
)
from app.core.config import settings
from app.modules.auth.models import User
from app.modules.catalog.models import Category, Product
from app.modules.guide.cart import stream_cart_turn
from app.modules.guide.schemas import GuideProductCard
from app.modules.guide.search import GuideSearchResult, search_products
from app.modules.guide.size import (
    SizeRecommendation,
    recommend_product_size,
)
from app.modules.support.models import ChatMessage, ChatSession
from app.modules.uploads.service import media_type_for_url, resolve_upload_path

CHITCHAT_QUICK_REPLIES = ["推荐几件衬衫", "通勤双肩包", "跑步运动鞋"]
EMPTY_QUICK_REPLIES = ["看看衬衫", "看看运动鞋", "看看双肩包"]
PRICE_QUICK_REPLIES = ["100 元以内", "300 元以内", "不限预算"]
PRICE_CLARIFY_TEXT = "价格区间不太对，最低价不能高于最高价，能再确认一下预算吗？"
EMPTY_CLARIFY_TEXT = "没有找到完全匹配的商品。要不要换个品类或预算？"
DEGRADED_TEXT = "服务繁忙，以上为部分推荐，请稍后再试。"
IMAGE_FAILED_TEXT = "图片识别失败，已按文字条件搜索。"
CARD_ATTRIBUTE_KEYS = ("color", "material", "thickness", "fit", "style", "season")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _error_code(exc: BaseException) -> str:
    if isinstance(exc, TimeoutError):
        return "LLM_TIMEOUT"
    return getattr(exc, "code", "LLM_ERROR")


async def load_category_hint(db: AsyncSession) -> str:
    """把品类树压成“一级 > 二级”文本，供解析提示使用。"""
    categories = list(
        (
            await db.scalars(
                select(Category).order_by(
                    Category.level.asc(),
                    Category.sort_order.asc(),
                    Category.id.asc(),
                )
            )
        ).all()
    )
    by_id = {category.id: category for category in categories}
    lines: list[str] = []
    for category in categories:
        parent = by_id.get(category.parent_id) if category.parent_id else None
        if parent is not None:
            lines.append(f"{parent.name} > {category.name}")
        else:
            lines.append(category.name)
    return "\n".join(lines)


async def _stream_text(
    text: str, chunk_size: int = 8
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    for index in range(0, len(text), chunk_size):
        yield "token", {"text": text[index : index + chunk_size]}


def _candidate_summary(product: Product) -> dict[str, Any]:
    attributes = {
        key: value
        for key, value in (product.attributes or {}).items()
        if key in CARD_ATTRIBUTE_KEYS and value not in (None, "", [])
    }
    return {
        "product_id": product.id,
        "title": product.title,
        "brand": product.brand,
        "price": float(product.price),
        "attributes": attributes,
        "description": (product.description or "")[:120],
    }


def _select_products(
    products: list[Product],
    rerank: GuideRerank | None,
    query: GuideQuery,
    limit: int = 8,
) -> tuple[list[Product], dict[int, str]]:
    """按重排结果取 8 个；重排缺项时用 RRF 顺序补足。"""
    by_id = {product.id: product for product in products}
    selected: list[Product] = []
    reasons: dict[int, str] = {}
    if rerank is not None:
        for item in rerank.items:
            product = by_id.get(item.product_id)
            if product is None or product.id in reasons:
                continue
            selected.append(product)
            reasons[product.id] = item.reason or default_reason(
                _candidate_summary(product)
            )
            if len(selected) >= limit:
                break
    for product in products:
        if len(selected) >= limit:
            break
        if product.id in reasons:
            continue
        selected.append(product)
        reasons[product.id] = default_reason(_candidate_summary(product))
    return selected[:limit], reasons


def _card(
    product: Product,
    reason: str,
    recommendation: SizeRecommendation,
) -> GuideProductCard:
    attributes = {
        key: value
        for key, value in (product.attributes or {}).items()
        if key in CARD_ATTRIBUTE_KEYS and value not in (None, "", [])
    }
    return GuideProductCard(
        id=product.id,
        title=product.title,
        price=float(product.price),
        original_price=(
            float(product.original_price)
            if product.original_price is not None
            else None
        ),
        main_image=product.main_image,
        brand=product.brand,
        attributes=attributes,
        reason=reason,
        recommended_size=recommendation.recommended_size,
        size_reason=recommendation.size_reason,
        sales_count=product.sales_count,
    )


def _message_question(message: ChatMessage) -> str:
    content = message.content or {}
    if message.content_type == "voice":
        return str(content.get("text") or content.get("transcript") or "").strip()
    return str(content.get("text") or "").strip()


def _question_with_vision(question: str, vision: VisionResult) -> str:
    """把结构化描述拼进解析文本，复用 M4 的本地/LLM 槽位解析。"""
    parts = [question] if question else []
    if vision.description:
        parts.append(vision.description)
    attribute_words = [
        value
        for values in vision.attributes.values()
        for value in values
        if value
    ]
    if attribute_words:
        parts.append(" ".join(attribute_words))
    if vision.category_path:
        # 只补叶子品类，避免“服装 衬衫”同时命中一级与二级导致品类停在父级
        parts.append(vision.category_path[-1])
    return " ".join(parts).strip()


def _merge_vision_query(query: GuideQuery, vision: VisionResult) -> GuideQuery:
    """视觉结构化结果只补空缺；品类路径比文本解析更深时采用视觉结果。"""
    if vision.category_path and (
        not query.category_path
        or (
            len(vision.category_path) > len(query.category_path)
            and query.category_path[0] == vision.category_path[0]
        )
    ):
        query.category_path = list(vision.category_path)
    for key in ("color", "material", "thickness"):
        values = vision.attributes.get(key) or []
        if values and not query.filters.get(key):
            query.filters[key] = list(values)
    if not query.semantic and vision.description:
        query.semantic = vision.description
    return query


async def _understand_image(
    db: AsyncSession,
    message: ChatMessage,
    vision_client: VisionClient,
) -> tuple[VisionResult | None, bool]:
    """图片理解失败不抛错：返回 (None, True) 让管线降级文字搜索。"""
    content = dict(message.content or {})
    image_url = str(content.get("image_url") or "")
    path = resolve_upload_path(image_url)
    if path is None or not path.exists():
        return None, True
    try:
        vision = await vision_client.describe_image(
            path.read_bytes(), media_type_for_url(image_url)
        )
    except Exception:
        return None, True
    if (
        not vision.category_path
        and not vision.attributes
        and not vision.description
    ):
        return None, True
    content["vision"] = vision.model_dump()
    message.content = content
    await db.commit()
    return vision, False


async def stream_guide_turn(
    db: AsyncSession,
    session: ChatSession,
    user_message: ChatMessage,
    user: User,
    llm: GuideLLM,
    embedding_client: EmbeddingClient,
    vision_client: VisionClient,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    """执行一轮导购回答，按 meta → token* → products → done 产出 SSE。"""
    started = time.monotonic()
    question = _message_question(user_message)
    vision: VisionResult | None = None
    image_failed = False
    if user_message.content_type == "image":
        vision, image_failed = await _understand_image(
            db, user_message, vision_client
        )
        if vision is not None:
            question = _question_with_vision(question, vision)
    slot_state = dict(session.slot_state or {})
    profile = {
        "height_cm": user.height_cm,
        "weight_kg": user.weight_kg,
        "usual_size": user.usual_size,
    }
    previous: GuideQuery | None = None
    if slot_state.get("query"):
        try:
            previous = GuideQuery.model_validate(slot_state["query"])
        except (TypeError, ValueError):
            previous = None
    try:
        clarify_count = int(slot_state.get("clarify_count", 0) or 0)
    except (TypeError, ValueError):
        clarify_count = 0

    answer_text = ""
    cards: list[GuideProductCard] = []
    relaxed: list[str] = []
    quick_replies: list[str] = []
    need_clarify = False
    degraded = False
    error_code: str | None = None

    category_hint = await load_category_hint(db)
    try:
        async with asyncio.timeout(settings.llm_timeout_seconds):
            raw_query = await llm.parse_guide_query(
                question, slot_state, profile, category_hint
            )
    except (TimeoutError, LLMError) as exc:
        degraded = True
        error_code = _error_code(exc)
        raw_query = extract_local_guide_query(
            question, slot_state, profile, category_hint
        )
    except Exception:
        degraded = True
        error_code = "LLM_ERROR"
        raw_query = extract_local_guide_query(
            question, slot_state, profile, category_hint
        )

    if raw_query.intent == "add_to_cart":
        async for event in stream_cart_turn(
            db,
            session,
            user_message,
            user,
            raw_query,
            slot_state,
            degraded=degraded,
        ):
            yield event
        return
    if vision is not None:
        raw_query = _merge_vision_query(raw_query, vision)
    query = merge_guide_query(previous, raw_query, profile)
    price_bad = (
        query.price.min is not None
        and query.price.max is not None
        and query.price.min > query.price.max
    )
    search_result: GuideSearchResult | None = None
    if query.intent != "chitchat" and not price_bad:
        try:
            search_result = await search_products(
                db, query, embedding_client
            )
        except Exception:
            degraded = True
            error_code = error_code or "RETRIEVAL_ERROR"
            search_result = None

    if query.intent == "chitchat":
        quick_replies = list(CHITCHAT_QUICK_REPLIES)
    elif price_bad:
        if clarify_count == 0:
            clarify_count = 1
            need_clarify = True
        quick_replies = list(PRICE_QUICK_REPLIES)
    elif search_result is None or not search_result.candidates:
        relaxed = search_result.relaxed if search_result is not None else []
        if clarify_count == 0:
            clarify_count = 1
            need_clarify = True
        quick_replies = list(EMPTY_QUICK_REPLIES)
    else:
        relaxed = search_result.relaxed

    if image_failed:
        degraded = True

    yield "meta", {
        "intent": query.intent,
        "query": query.model_dump(),
        "need_clarify": need_clarify,
        "relaxed": list(relaxed),
        "quick_replies": list(quick_replies),
        "degraded": degraded,
        "vision": vision.model_dump() if vision is not None else None,
        "image_failed": image_failed,
    }
    if error_code:
        yield "error", {
            "code": error_code,
            "message": "服务繁忙，正在使用降级结果",
        }
    if image_failed:
        answer_text = IMAGE_FAILED_TEXT
        yield "token", {"text": IMAGE_FAILED_TEXT}

    async def finalize() -> AsyncIterator[tuple[str, dict[str, Any]]]:
        latency_ms = int((time.monotonic() - started) * 1000)
        message = ChatMessage(
            session_id=session.id,
            sender_type="ai",
            content_type="text",
            content={"text": answer_text or NO_RESULT_TEXT},
            meta={
                "intent": query.intent,
                "query": query.model_dump(),
                "products": [card.model_dump() for card in cards],
                "relaxed": list(relaxed),
                "need_clarify": need_clarify,
                "quick_replies": list(quick_replies),
                "degraded": degraded,
                "latency_ms": latency_ms,
            },
        )
        state = {
            **slot_state,
            "query": query.model_dump(),
            "clarify_count": clarify_count,
        }
        if cards:
            state["last_products"] = [
                {
                    "product_id": card.id,
                    "title": card.title,
                    "price": card.price,
                    "main_image": card.main_image,
                    "recommended_size": card.recommended_size,
                }
                for card in cards[:8]
            ]
        session.slot_state = state
        session.updated_at = _now()
        db.add(message)
        await db.flush()
        message_id = message.id
        await db.commit()
        yield "done", {"message_id": message_id, "latency_ms": latency_ms}

    if query.intent == "chitchat":
        answer_text += CHITCHAT_TEXT
        async for event in _stream_text(CHITCHAT_TEXT):
            yield event
        async for event in finalize():
            yield event
        return

    if price_bad or search_result is None or not search_result.candidates:
        if price_bad:
            reply = PRICE_CLARIFY_TEXT if need_clarify else NO_RESULT_TEXT
        else:
            reply = EMPTY_CLARIFY_TEXT if need_clarify else NO_RESULT_TEXT
        answer_text += reply
        async for event in _stream_text(reply):
            yield event
        async for event in finalize():
            yield event
        return

    candidates = [
        _candidate_summary(product)
        for product in search_result.candidates[:30]
    ]
    rerank: GuideRerank | None = None
    try:
        async with asyncio.timeout(settings.llm_timeout_seconds):
            rerank = await llm.rerank_products(query, candidates)
    except (TimeoutError, LLMError) as exc:
        degraded = True
        yield "error", {
            "code": _error_code(exc),
            "message": "重排失败，使用默认排序",
        }
    except Exception:
        degraded = True
        yield "error", {
            "code": "LLM_ERROR",
            "message": "重排失败，使用默认排序",
        }

    selected, reasons = _select_products(
        search_result.candidates, rerank, query
    )
    for product in selected:
        recommendation = await recommend_product_size(db, product, user)
        cards.append(_card(product, reasons[product.id], recommendation))

    product_summaries = [
        {
            "title": card.title,
            "price": card.price,
            "attributes": card.attributes,
            "recommended_size": card.recommended_size,
            "size_reason": card.size_reason,
        }
        for card in cards
    ]
    prefix_len = len(answer_text)
    try:
        async with asyncio.timeout(settings.llm_timeout_seconds):
            async for token in llm.stream_guide_answer(
                query, product_summaries, relaxed, profile
            ):
                answer_text += token
                yield "token", {"text": token}
    except (TimeoutError, LLMError) as exc:
        degraded = True
        yield "error", {
            "code": _error_code(exc),
            "message": "服务繁忙，请稍后再试",
        }
        fallback = build_local_guide_answer(
            query, product_summaries, relaxed
        )
        if len(answer_text) == prefix_len:
            suffix = f"{fallback}\n{DEGRADED_TEXT}"
            answer_text += suffix
            async for event in _stream_text(suffix):
                yield event
        else:
            suffix = f"\n{DEGRADED_TEXT}"
            answer_text += suffix
            yield "token", {"text": suffix}
    except Exception:
        degraded = True
        yield "error", {
            "code": "LLM_ERROR",
            "message": "服务繁忙，请稍后再试",
        }
        fallback = build_local_guide_answer(
            query, product_summaries, relaxed
        )
        if len(answer_text) == prefix_len:
            suffix = f"{fallback}\n{DEGRADED_TEXT}"
            answer_text += suffix
            async for event in _stream_text(suffix):
                yield event

    if len(answer_text) == prefix_len:
        fallback = build_local_guide_answer(
            query, product_summaries, relaxed
        )
        answer_text += fallback
        async for event in _stream_text(fallback):
            yield event

    yield "products", {
        "items": [card.model_dump() for card in cards],
        "relaxed": list(relaxed),
        "query": query.model_dump(),
    }
    async for event in finalize():
        yield event
