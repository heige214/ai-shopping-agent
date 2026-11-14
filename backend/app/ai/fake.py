from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.base import (
    AnswerabilityResult,
    ASRError,
    GuideQuery,
    GuideRerank,
    IntentResult,
    LLMError,
    SupportPlan,
    VisionError,
    VisionResult,
)
from app.ai.guide_local import LocalGuideLLM
from app.ai.local import LocalSupportLLM, _extract_topic
from app.ai.size_rules import parse_size_query


class FakeVisionClient:
    """测试与 E2E 使用：返回确定性的蓝色薄款纯棉衬衫。"""

    def __init__(
        self,
        *,
        result: VisionResult | dict | None = None,
        fail: bool = False,
    ) -> None:
        self.result = result
        self.fail = fail

    async def describe_image(
        self, image_bytes: bytes, mime_type: str
    ) -> VisionResult:
        if self.fail:
            raise VisionError("fake vision failure")
        if self.result is not None:
            return VisionResult.model_validate(self.result)
        return VisionResult(
            category_path=["服装", "衬衫"],
            attributes={
                "color": ["蓝色"],
                "material": ["棉"],
                "thickness": ["薄款"],
                "pattern": ["纯色"],
            },
            description="一件蓝色纯棉长袖薄款衬衫",
            confidence=0.92,
        )


class FakeASRClient:
    """测试与 E2E 使用：默认转写为“推荐几件衬衫”。"""

    def __init__(
        self,
        *,
        transcript: str = "推荐几件衬衫",
        fail: bool = False,
    ) -> None:
        self.transcript = transcript
        self.fail = fail

    async def transcribe(
        self, audio_bytes: bytes, mime_type: str, filename: str
    ) -> str:
        if self.fail:
            raise ASRError("fake asr failure")
        return self.transcript


class FakeSupportLLM(LocalSupportLLM):
    """测试与 E2E 使用：默认走本地规则，可按用例注入固定结果或失败。"""

    def __init__(
        self,
        *,
        intent: str | None = None,
        answerability: AnswerabilityResult | dict | None = None,
        answer_text: str | None = None,
        plan: SupportPlan | dict | None = None,
        fail_intent: bool = False,
        fail_answerability: bool = False,
        fail_stream: bool = False,
    ) -> None:
        self.intent = intent
        self.answerability = answerability
        self.answer_text = answer_text
        self.plan = plan
        self.fail_intent = fail_intent
        self.fail_answerability = fail_answerability
        self.fail_stream = fail_stream

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
        if self.fail_intent:
            raise LLMError("fake intent failure")
        if self.intent is not None:
            return IntentResult(
                intent=self.intent,  # type: ignore[arg-type]
                entities={"question_topic": _extract_topic(question)},
            )
        return await super().route_intent(question, product_title)

    async def plan_support(
        self,
        question: str,
        product_title: str,
    ) -> SupportPlan:
        if self.fail_intent:
            raise LLMError("fake plan failure")
        if self.plan is not None:
            if isinstance(self.plan, SupportPlan):
                return self.plan
            return SupportPlan.model_validate(self.plan)
        if self.intent is None:
            return await super().plan_support(question, product_title)

        if self.intent == "order_qa":
            return SupportPlan(action="handoff", handoff_kind="order")
        if self.intent == "complaint":
            return SupportPlan(action="handoff", handoff_kind="complaint")
        if self.intent == "chitchat":
            return SupportPlan(action="chitchat")
        if self.intent == "unknown":
            return SupportPlan(action="clarify")

        tools = ["product_facts", "search_knowledge"]
        if self.intent == "policy_qa":
            tools = ["search_knowledge"]
        size = parse_size_query(question).requested_size
        if self.intent == "size_qa" and size:
            tools.append("size_stock")
        return SupportPlan(
            action="rag",
            tools=tools,
            search_query=question,
            size=size,
        )

    async def judge_answerable(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        max_similarity: float,
    ) -> AnswerabilityResult:
        if self.fail_answerability:
            raise LLMError("fake answerability failure")
        if self.answerability is not None:
            if isinstance(self.answerability, AnswerabilityResult):
                return self.answerability
            return AnswerabilityResult.model_validate(self.answerability)
        return await super().judge_answerable(
            question, facts_text, chunks_text, max_similarity
        )

    async def stream_answer(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        partial: bool,
    ) -> AsyncIterator[str]:
        if self.fail_stream:
            raise LLMError("fake stream failure")
        if self.answer_text is None:
            async for token in super().stream_answer(
                question, facts_text, chunks_text, partial
            ):
                yield token
            return
        for index in range(0, len(self.answer_text), 4):
            yield self.answer_text[index : index + 4]


class FakeGuideLLM(LocalGuideLLM):
    """测试与 E2E 使用：默认走本地规则，可按用例注入固定结果或失败。"""

    def __init__(
        self,
        *,
        query: GuideQuery | dict | None = None,
        rerank: GuideRerank | dict | None = None,
        answer_text: str | None = None,
        fail_parse: bool = False,
        fail_rerank: bool = False,
        fail_stream: bool = False,
    ) -> None:
        self.query = query
        self.rerank = rerank
        self.answer_text = answer_text
        self.fail_parse = fail_parse
        self.fail_rerank = fail_rerank
        self.fail_stream = fail_stream

    async def parse_guide_query(
        self,
        message: str,
        slot_state: dict,
        profile: dict,
        category_hint: str,
    ) -> GuideQuery:
        if self.fail_parse:
            raise LLMError("fake guide parse failure")
        if self.query is not None:
            return GuideQuery.model_validate(self.query)
        return await super().parse_guide_query(
            message, slot_state, profile, category_hint
        )

    async def rerank_products(
        self,
        query: GuideQuery,
        candidates: list[dict],
    ) -> GuideRerank:
        if self.fail_rerank:
            raise LLMError("fake guide rerank failure")
        if self.rerank is not None:
            return GuideRerank.model_validate(self.rerank)
        return await super().rerank_products(query, candidates)

    async def stream_guide_answer(
        self,
        query: GuideQuery,
        products: list[dict],
        relaxed: list[str],
        profile: dict,
    ) -> AsyncIterator[str]:
        if self.fail_stream:
            raise LLMError("fake guide stream failure")
        if self.answer_text is None:
            async for token in super().stream_guide_answer(
                query, products, relaxed, profile
            ):
                yield token
            return
        for index in range(0, len(self.answer_text), 4):
            yield self.answer_text[index : index + 4]
