from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.ai.base import (
    AnswerabilityResult,
    IntentResult,
    LLMError,
    LLMTimeoutError,
    SupportPlan,
)
from app.ai.prompts.support_answer import ANSWER_SYSTEM, build_answer_user
from app.ai.prompts.support_answerable import (
    ANSWERABLE_SYSTEM,
    build_answerable_user,
)
from app.ai.prompts.support_intent import INTENT_SYSTEM, build_intent_user
from app.ai.prompts.support_plan import PLAN_SYSTEM, build_plan_user

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _parse_json_content(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


class DashScopeSupportLLM:
    """DashScope OpenAI 兼容接口：结构化输出 + 流式回答。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        chat_model: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.timeout_seconds = timeout_seconds

    async def _chat(
        self,
        system: str,
        user: str,
        temperature: float,
        json_mode: bool,
    ) -> str:
        payload: dict = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                # 部分兼容端点不识别 response_format；去掉后重试一次
                if response.status_code == 400 and json_mode:
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM 请求超时") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 请求失败：{exc}") from exc

        if response.status_code >= 400:
            raise LLMError(
                f"LLM HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError("LLM 返回结构异常") from exc

    async def _structured(
        self,
        system: str,
        user: str,
        schema: type[SchemaT],
        temperature: float,
    ) -> SchemaT:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                content = await self._chat(system, user, temperature, json_mode=True)
                return schema.model_validate(_parse_json_content(content))
            except LLMTimeoutError:
                raise
            except (LLMError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.2)
        raise LLMError(f"结构化输出校验失败：{last_error}") from last_error

    async def route_intent(self, question: str, product_title: str) -> IntentResult:
        return await self._structured(
            INTENT_SYSTEM,
            build_intent_user(question, product_title),
            IntentResult,
            temperature=0.1,
        )

    async def plan_support(
        self,
        question: str,
        product_title: str,
    ) -> SupportPlan:
        return await self._structured(
            PLAN_SYSTEM,
            build_plan_user(question, product_title),
            SupportPlan,
            temperature=0.1,
        )

    async def judge_answerable(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        max_similarity: float,
    ) -> AnswerabilityResult:
        return await self._structured(
            ANSWERABLE_SYSTEM,
            build_answerable_user(question, facts_text, chunks_text),
            AnswerabilityResult,
            temperature=0.1,
        )

    async def stream_answer(
        self,
        question: str,
        facts_text: str,
        chunks_text: str,
        partial: bool,
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": ANSWER_SYSTEM},
                {
                    "role": "user",
                    "content": build_answer_user(
                        question, facts_text, chunks_text, partial
                    ),
                },
            ],
            "temperature": 0.2,
            "stream": True,
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise LLMError(
                            f"LLM HTTP {response.status_code}: "
                            f"{body.decode('utf-8', 'ignore')[:200]}"
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield str(text)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM 流式回答超时") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM 流式请求失败：{exc}") from exc
