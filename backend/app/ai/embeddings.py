from __future__ import annotations

import hashlib
import math

import httpx

from app.ai.base import LLMError, LLMTimeoutError


class NoopEmbeddingClient:
    """未配置 key 时使用：不生成向量，检索自动退化为关键词。"""

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        return [None for _ in texts]

    async def embed_query(self, text: str) -> list[float] | None:
        return None


class FakeEmbeddingClient:
    """确定性假向量：字符 1~2 gram 哈希到固定维度，供测试与 E2E 使用。"""

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = list(text)
        tokens.extend(text[index : index + 2] for index in range(len(text) - 1))
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float] | None:
        return self._vector(text)


class DashScopeEmbeddingClient:
    """DashScope OpenAI 兼容 embeddings 接口，批量上限 10。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dim: int,
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dim = dim
        self.timeout_seconds = timeout_seconds

    async def embed_texts(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        results: list[list[float] | None] = [None] * len(texts)
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for start in range(0, len(texts), 10):
                batch = texts[start : start + 10]
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "model": self.model,
                            "input": batch,
                            "dimensions": self.dim,
                        },
                    )
                except httpx.TimeoutException as exc:
                    raise LLMTimeoutError("embedding timeout") from exc
                except httpx.HTTPError as exc:
                    raise LLMError(f"embedding request failed: {exc}") from exc

                if response.status_code >= 400:
                    raise LLMError(
                        f"embedding HTTP {response.status_code}: {response.text[:200]}"
                    )
                payload = response.json()
                rows = sorted(
                    payload.get("data", []), key=lambda item: item.get("index", 0)
                )
                if len(rows) != len(batch):
                    raise LLMError("embedding 返回数量不一致")
                for offset, row in enumerate(rows):
                    vector = [float(value) for value in row.get("embedding", [])]
                    if len(vector) != self.dim:
                        raise LLMError(
                            f"embedding 维度错误：{len(vector)} != {self.dim}"
                        )
                    results[start + offset] = vector
        return results

    async def embed_query(self, text: str) -> list[float] | None:
        vectors = await self.embed_texts([text])
        return vectors[0] if vectors else None
