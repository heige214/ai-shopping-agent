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


class LLMError(RuntimeError):
    """LLM 调用或结构化输出失败；由管线转成 SSE error 事件。"""

    code = "LLM_ERROR"


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"


class SupportLLM(Protocol):
    """商品客服所需的最小 LLM 能力，便于 DashScope/本地/Fake 切换。"""

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
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
