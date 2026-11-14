from __future__ import annotations

from collections.abc import AsyncIterator

from app.ai.base import AnswerabilityResult, IntentResult, LLMError
from app.ai.local import LocalSupportLLM, _extract_topic


class FakeSupportLLM(LocalSupportLLM):
    """测试与 E2E 使用：默认走本地规则，可按用例注入固定结果或失败。"""

    def __init__(
        self,
        *,
        intent: str | None = None,
        answerability: AnswerabilityResult | dict | None = None,
        answer_text: str | None = None,
        fail_intent: bool = False,
        fail_answerability: bool = False,
        fail_stream: bool = False,
    ) -> None:
        self.intent = intent
        self.answerability = answerability
        self.answer_text = answer_text
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
