from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel, Field

IntentName = Literal[
    "product_qa",
    "size_qa",
    "policy_qa",
    "order_qa",
    "complaint",
    "chitchat",
    "unknown",
]


class IntentResult(BaseModel):
    """客服意图路由结果；entities 只放问题主题等轻量信息。"""

    intent: IntentName
    entities: dict = Field(default_factory=dict)


class AnswerabilityResult(BaseModel):
    """可回答性判断结果。"""

    can_answer: bool
    confidence: float = Field(ge=0.0, le=1.0)
    partial: bool = False
    missing: str | None = None


SupportAction = Literal["rag", "handoff", "chitchat", "clarify"]
ToolName = Literal["product_facts", "search_knowledge", "size_stock"]
HandoffKind = Literal["order", "complaint"]

GuideIntent = Literal["search", "refine", "chitchat"]


class GuidePrice(BaseModel):
    """导购价格区间；null 表示未限制。"""

    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)


class GuideSizeProfile(BaseModel):
    """本轮/档案中的身材信息；身高体重用于尺码推荐。"""

    height_cm: int | None = Field(default=None, ge=100, le=250)
    weight_kg: int | None = Field(default=None, ge=20, le=300)
    usual_size: str | None = None


class GuideQuery(BaseModel):
    """导购槽位：每轮只描述新增/修改项，由 merge_guide_query 合并。"""

    intent: GuideIntent = "search"
    semantic: str | None = None
    category_path: list[str] = Field(default_factory=list)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    price: GuidePrice = Field(default_factory=GuidePrice)
    size_profile: GuideSizeProfile = Field(default_factory=GuideSizeProfile)


class GuideRerankItem(BaseModel):
    product_id: int
    reason: str = ""


class GuideRerank(BaseModel):
    items: list[GuideRerankItem] = Field(default_factory=list)


class SupportPlan(BaseModel):
    """Agent 规划结果：选择动作与工具，不直接生成最终回答。"""

    action: SupportAction = "rag"
    tools: list[ToolName] = Field(default_factory=list)
    search_query: str | None = None
    size: str | None = None
    handoff_kind: HandoffKind | None = None


class LLMError(RuntimeError):
    """LLM 调用或结构化输出失败；由管线转成 SSE error 事件。"""

    code = "LLM_ERROR"


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"


class SupportLLM(Protocol):
    """商品客服所需的最小 LLM 能力，便于 DashScope/本地/Fake 切换。"""

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
        ...

    async def plan_support(self, question: str, product_title: str) -> SupportPlan:
        ...

    async def judge_answerable(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        max_similarity: float,
    ) -> AnswerabilityResult:
        ...

    def stream_answer(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        partial: bool,
    ) -> AsyncIterator[str]:
        ...


class EmbeddingClient(Protocol):
    """向量化能力；不可用时返回 None，检索退化为关键词。"""

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        ...

    async def embed_query(self, text: str) -> list[float] | None:
        ...


class GuideLLM(Protocol):
    """导购所需 LLM 能力：槽位解析、候选重排、流式总结。"""

    async def parse_guide_query(
        self,
        message: str,
        slot_state: dict,
        profile: dict,
        category_hint: str,
    ) -> GuideQuery:
        ...

    async def rerank_products(
        self,
        query: GuideQuery,
        candidates: list[dict],
    ) -> GuideRerank:
        ...

    def stream_guide_answer(
        self,
        query: GuideQuery,
        products: list[dict],
        relaxed: list[str],
        profile: dict,
    ) -> AsyncIterator[str]:
        ...
