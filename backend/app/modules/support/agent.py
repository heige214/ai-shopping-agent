from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import EmbeddingClient, SupportLLM, SupportPlan
from app.ai.size_rules import (
    SizeQuery,
    build_size_availability_answer,
    collect_size_options,
    parse_size_query,
)
from app.modules.catalog.models import Product
from app.modules.knowledge.retrieval import (
    ProductFacts,
    RetrievalResult,
    citations_from_chunks,
    format_chunks_for_llm,
    format_product_facts,
    load_product_doc_chunk,
    retrieve_context,
)


CITATION_TYPES_BY_TOPIC = {
    "policy": {"policy", "faq"},
    "care": {"care", "detail", "faq"},
    "attribute": {"detail", "faq"},
    "suitability": {"detail", "faq", "size"},
    "size": {"size", "faq", "detail"},
}


def citation_types_for_question(question: str) -> set[str]:
    """按问题主题收窄引用类型，避免材质问答附上平台政策等无关引用。"""
    if any(
        word in question
        for word in ("退货", "退款", "退换", "发票", "优惠券", "运费", "包邮", "支付", "售后", "政策")
    ):
        return CITATION_TYPES_BY_TOPIC["policy"]
    if any(word in question for word in ("洗", "护理", "清洁", "保养")):
        return CITATION_TYPES_BY_TOPIC["care"]
    if any(word in question for word in ("尺码", "码数", "码", "号", "身高", "体重", "脚长")):
        return CITATION_TYPES_BY_TOPIC["size"]
    if any(
        word in question
        for word in ("小孩子", "小孩", "儿童", "孩子", "宝宝", "年龄", "适合", "送礼", "送人")
    ):
        return CITATION_TYPES_BY_TOPIC["suitability"]
    if any(
        word in question
        for word in ("材质", "面料", "成分", "颜色", "版型", "厚薄", "起球", "缩水", "掉色")
    ):
        return CITATION_TYPES_BY_TOPIC["attribute"]
    return {"detail", "faq", "size", "care", "policy"}


class SupportAgentState(TypedDict, total=False):
    """LangGraph 状态：商品事实、规划、工具结果与引用。"""

    question: str
    product: Product
    facts: ProductFacts
    plan: SupportPlan
    facts_text: str
    size_options: list[str]
    size_answer: str | None
    size_citation: dict[str, Any] | None
    retrieval: RetrievalResult | None
    chunks_text: str
    citations: list[dict[str, Any]]
    max_similarity: float
    tool_trace: list[str]


async def run_support_agent(
    db: AsyncSession,
    product: Product,
    facts: ProductFacts,
    question: str,
    llm: SupportLLM,
    embedding_client: EmbeddingClient,
) -> SupportAgentState:
    """执行 plan -> tools 的 LangGraph 工作流，回答生成由调用方流式完成。"""
    size_options = collect_size_options(
        facts.stock_by_size,
        facts.attributes.get("size"),
        facts.size_chart,
    )

    async def plan_node(state: SupportAgentState) -> SupportAgentState:
        plan = await llm.plan_support(question, product.title)
        return {"plan": plan, "tool_trace": [f"plan:{plan.action}"]}

    async def tools_node(state: SupportAgentState) -> SupportAgentState:
        plan = state["plan"]
        trace = list(state.get("tool_trace") or [])
        if plan.action != "rag":
            return {"tool_trace": trace}

        tools = list(plan.tools or [])
        if "product_facts" in tools:
            trace.append("tool:product_facts")

        if "size_stock" in tools:
            query = parse_size_query(question, size_options)
            if plan.size:
                query = SizeQuery(
                    requested_size=plan.size,
                    is_availability=True,
                    mentions_size=True,
                )
            size_answer = build_size_availability_answer(
                facts.stock_by_size,
                size_options,
                query,
            )
            trace.append("tool:size_stock")
            if size_answer:
                chunk = await load_product_doc_chunk(db, product.id, "size")
                citation = (
                    citations_from_chunks([chunk])
                    if chunk
                    else [
                        {
                            "doc_type": "size",
                            "title": f"{product.title} · 尺码指南",
                            "chunk_id": None,
                            "content": "",
                        }
                    ]
                )
                return {
                    "size_answer": size_answer,
                    "size_citation": citation[0],
                    "tool_trace": trace,
                }

        # 没有确定性尺码答案时，默认至少检索一次知识库
        retrieval = await retrieve_context(
            db,
            product.id,
            plan.search_query or question,
            embedding_client,
            facts=facts,
        )
        allowed_types = citation_types_for_question(question)
        focused_chunks = [
            chunk
            for chunk in retrieval.chunks
            if chunk.doc_type in allowed_types
        ] or retrieval.chunks
        trace.append("tool:search_knowledge")
        return {
            "retrieval": retrieval,
            "chunks_text": format_chunks_for_llm(focused_chunks),
            "citations": citations_from_chunks(focused_chunks),
            "max_similarity": retrieval.max_similarity,
            "tool_trace": trace,
        }

    graph = StateGraph(SupportAgentState)
    graph.add_node("plan", plan_node)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "tools")
    graph.add_edge("tools", END)
    compiled = graph.compile()

    initial: SupportAgentState = {
        "question": question,
        "product": product,
        "facts": facts,
        "facts_text": format_product_facts(facts),
        "size_options": size_options,
        "size_answer": None,
        "size_citation": None,
        "retrieval": None,
        "chunks_text": "",
        "citations": [],
        "max_similarity": 0.0,
        "tool_trace": [],
    }
    return await compiled.ainvoke(initial)
