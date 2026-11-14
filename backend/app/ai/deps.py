from __future__ import annotations

import logging

from app.ai.base import EmbeddingClient, SupportLLM
from app.ai.dashscope import DashScopeSupportLLM
from app.ai.embeddings import (
    DashScopeEmbeddingClient,
    FakeEmbeddingClient,
    NoopEmbeddingClient,
)
from app.ai.fake import FakeSupportLLM
from app.ai.local import LocalSupportLLM
from app.core.config import settings

logger = logging.getLogger(__name__)


def _dashscope_enabled() -> bool:
    if settings.ai_provider == "dashscope":
        return bool(settings.dashscope_api_key)
    if settings.ai_provider == "auto":
        return bool(settings.dashscope_api_key)
    return False


def get_support_llm() -> SupportLLM:
    """FastAPI 依赖：按 AI_PROVIDER 选择 LLM，key 缺失时退化为本地规则。"""
    if settings.ai_provider == "fake":
        return FakeSupportLLM()
    if _dashscope_enabled():
        return DashScopeSupportLLM(
            api_key=settings.dashscope_api_key or "",
            base_url=settings.dashscope_base_url,
            chat_model=settings.chat_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.ai_provider == "dashscope":
        logger.warning("AI_PROVIDER=dashscope 但未配置 DASHSCOPE_API_KEY，使用本地规则")
    return LocalSupportLLM()


def get_embedding_client() -> EmbeddingClient:
    """FastAPI 依赖：无 key 时返回 Noop，检索退化为关键词。"""
    if settings.ai_provider == "fake":
        return FakeEmbeddingClient(dim=settings.embedding_dim)
    if _dashscope_enabled():
        return DashScopeEmbeddingClient(
            api_key=settings.dashscope_api_key or "",
            base_url=settings.dashscope_base_url,
            model=settings.embedding_model,
            dim=settings.embedding_dim,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return NoopEmbeddingClient()
