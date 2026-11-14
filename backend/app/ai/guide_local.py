from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.base import GuideQuery, GuideRerank, GuideRerankItem
from app.ai.guide_slots import (
    default_reason,
    extract_local_guide_query,
    query_condition_text,
)

CHITCHAT_TEXT = "你好，我是 AI 导购。告诉我品类、颜色、材质或预算，我帮你挑合适的款。"
NO_RESULT_TEXT = "暂时没有找到完全符合的商品，可以换个品类、颜色或预算试试。"


def build_local_guide_answer(
    query: GuideQuery,
    products: list[dict[str, Any]],
    relaxed: list[str],
) -> str:
    """无 key 时的确定性导购总结，不列举商品明细。"""
    if not products:
        return NO_RESULT_TEXT
    condition = query_condition_text(query)
    prefix = (
        f"按{condition}为你挑了 {len(products)} 款："
        if condition
        else f"为你挑了 {len(products)} 款热门商品："
    )
    if relaxed:
        prefix = f"没有完全匹配的，已放宽{'、'.join(relaxed)}条件，{prefix}"
    has_size = any(product.get("recommended_size") for product in products)
    suffix = (
        "商品卡里已按你的身材标注推荐尺码。"
        if has_size
        else "点商品卡可以查看详情和尺码表。"
    )
    return prefix + suffix


class LocalGuideLLM:
    """无 DashScope key 时的确定性导购实现：规则槽位 + 顺序重排 + 模板总结。"""

    async def parse_guide_query(
        self,
        message: str,
        slot_state: dict,
        profile: dict,
        category_hint: str,
    ) -> GuideQuery:
        return extract_local_guide_query(
            message, slot_state, profile, category_hint
        )

    async def rerank_products(
        self,
        query: GuideQuery,
        candidates: list[dict],
    ) -> GuideRerank:
        return GuideRerank(
            items=[
                GuideRerankItem(
                    product_id=int(candidate["product_id"]),
                    reason=default_reason(candidate),
                )
                for candidate in candidates[:8]
            ]
        )

    async def stream_guide_answer(
        self,
        query: GuideQuery,
        products: list[dict],
        relaxed: list[str],
        profile: dict,
    ) -> AsyncIterator[str]:
        text = build_local_guide_answer(query, products, relaxed)
        for index in range(0, len(text), 8):
            yield text[index : index + 8]
