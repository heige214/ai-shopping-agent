from __future__ import annotations

import asyncio
import base64
import json
import re

import httpx
from pydantic import ValidationError

from app.ai.base import LLMError, LLMTimeoutError, VisionError, VisionResult
from app.ai.prompts.guide_vision import (
    GUIDE_VISION_SYSTEM,
    build_guide_vision_user,
)


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


class LocalVisionClient:
    """无 key 时的降级实现：不识别图片，由导购管线转文字搜索。"""

    async def describe_image(
        self, image_bytes: bytes, mime_type: str
    ) -> VisionResult:
        return VisionResult(confidence=0.0)


class DashScopeVisionClient:
    """DashScope OpenAI 兼容多模态接口（qwen3-vl-flash）。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def _chat(self, image_bytes: bytes, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": GUIDE_VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{encoded}"
                            },
                        },
                        {
                            "type": "text",
                            "text": build_guide_vision_user(mime_type),
                        },
                    ],
                },
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                if response.status_code == 400:
                    payload.pop("response_format", None)
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("图片理解超时") from exc
        except httpx.HTTPError as exc:
            raise VisionError(f"图片理解请求失败：{exc}") from exc

        if response.status_code >= 400:
            raise VisionError(
                f"图片理解 HTTP {response.status_code}: {response.text[:200]}"
            )
        try:
            data = response.json()
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise VisionError("图片理解返回结构异常") from exc

    async def describe_image(
        self, image_bytes: bytes, mime_type: str
    ) -> VisionResult:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                content = await self._chat(image_bytes, mime_type)
                return VisionResult.model_validate(_parse_json_content(content))
            except LLMTimeoutError:
                raise
            except (LLMError, ValidationError, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(0.2)
        raise VisionError(f"图片结构化输出校验失败：{last_error}") from last_error
